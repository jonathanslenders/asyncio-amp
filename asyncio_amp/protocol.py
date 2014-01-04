import asyncio
from struct import pack, unpack

from .arguments import String, Integer
from .exceptions import (
    ConnectionLostError,
    RemoteAmpError,
    TooLongError,
    UnhandledCommandError,
    UnknownRemoteError,

    UNHANDLED_ERROR_CODE,
    UNKNOWN_ERROR_CODE,
)

__all__ = ('Command', 'AMPProtocol', )



class Command:
    arguments = []
    response = []
    errors = dict()

    @classmethod
    def responder(cls, methodfunc):
        methodfunc._responds_to_amp_command = cls
        return asyncio.coroutine(methodfunc)


def _serialize_command(command, kwargs):
    return { k: v.encode(kwargs[k]) for k, v in command.arguments if k in kwargs }

def _deserialize_command(command_cls, packet):
    return { k: v.decode(packet[k]) for k, v in command_cls.arguments }

def _serialize_answer(command_cls, answer_dict):
    return { k: v.encode(answer_dict[k]) for k, v in command_cls.response if k in answer_dict }

def _deserialize_answer(command_cls, packet):
    return { k: v.decode(packet[k]) for k, v in command_cls.response }


# The longest key allowed
MAX_KEY_LENGTH = 0xff

# The longest value allowed
MAX_VALUE_LENGTH = 0xffff


class AMPProtocolMeta(type):
    def __new__(cls, name, bases, attrs):
        if not 'responders' in attrs:
            for a in attrs:
                try:
                    attrs[a]._responds_to_amp_command
                except: pass
            attrs['responders'] = {
                    attr._responds_to_amp_command.__name__: attr
                    for attr in attrs.values()
                    if hasattr(attr, '_responds_to_amp_command')
            }
        return super().__new__(cls, name, bases, attrs)


class AMPProtocol(asyncio.Protocol, metaclass=AMPProtocolMeta):
    def __init__(self):
        self._queries = { }
        self._counter = 0

    def connection_made(self, transport):
        self.transport = transport

        self._parser_generator = self._parser()
        self._waiting_for_bytes = self._parser_generator.send(None)
        self._buffer = b''

    def connection_lost(self, exc):
        for k, v in self._queries.items():
            v.set_exception(ConnectionLostError(exc))

        self.transport = None
        self._queries = { }

    def data_received(self, data):
        self._buffer += data

        while self._waiting_for_bytes <= len(self._buffer):
            token, self._buffer = self._buffer[:self._waiting_for_bytes], self._buffer[self._waiting_for_bytes:]
            self._waiting_for_bytes = self._parser_generator.send(token)

    def _parser(self):
        """
        Parse loop:
        (It's a generator that yields the amount of characters it wants to
        receive for the next 'token'. The state in the state machine is
        actually the progress in this generator function.)
        """
        packet = { }
        name = None

        while True:
            # First, receive the SIZE or double NULL.
            length = unpack('!H', (yield 2))[0]

            # NULL (two NULL bytes) means the end of a packet
            if length == 0:
                self._handle_incoming_packet(packet)
                packet = { }
            # A SIZE means receiving a name or value.
            elif name is None:
                name = (yield length).decode('ascii')
            else:
                value = yield length
                packet[name] = value
                name = None

    def _handle_incoming_packet(self, packet):
        # Incoming query.
        if '_command' in packet:
            asyncio.Task(self._handle_command_packet(packet))

        # Incoming answer.
        elif '_answer' in packet:
            id = Integer().decode(packet.pop('_answer'))
            future = self._queries.get(id, None)
            if future is not None:
                future.set_result(packet)
            else:
                raise Exception('Received answer to unknown query.')

        # Incoming error
        elif '_error' in packet:
            id = Integer().decode(packet.pop('_error'))
            error_code = String().decode(packet.pop('_error_code'))
            error_description = String().decode(packet.pop('_error_description'))

            future = self._queries.get(id, None)
            if future is not None:
                future.set_exception(RemoteAmpError(error_code, error_description))
            else:
                raise Exception('Received answer to unknown query.')
        else:
            raise Exception('Received unknown packet.')

    def _send_packet(self, packet):
        write = self.transport.write

        for k, v in packet.items():
            k = k.encode('ascii')

            key_length = len(k)
            value_length = len(v)

            if key_length > MAX_KEY_LENGTH:
                raise TooLongError()

            if value_length > MAX_VALUE_LENGTH:
                raise TooLongError()

            # Write key
            write(pack("!H", key_length))
            write(k)

            # Write value
            write(pack("!H", value_length))
            write(v)

        write(bytes((0, 0)))

    @asyncio.coroutine
    def _handle_command_packet(self, packet):
        command = String().decode(packet.pop('_command'))
        id = packet.pop('_ask', None) # If '_ask' is missing, we shouldn't return an answer.

        def send_error_reply(error_code, description):
            self._send_packet({
                    '_error': id,
                    '_error_code': String().encode(error_code),
                    '_error_description': String().encode(description),
                    })

        # Get responder
        if command in self.responders:
            responder = self.responders[command]
        else:
            send_error_reply(UNHANDLED_ERROR_CODE, 'Unhandled Command: %r' % command)
            return

        # Decode
        command_cls = responder._responds_to_amp_command
        kwargs = _deserialize_command(command_cls, packet)

        # Call responder
        try:
            result = yield from responder(self, ** kwargs)

            # Send answer.
            if id is not None:
                # (This can still raise TooLongError if the response is too long.)
                reply = { '_answer': id }
                reply.update(_serialize_answer(command_cls, result))
                self._send_packet(reply)
        except TooLongError as e:
            if id is not None:
                send_error_reply(UNKNOWN_ERROR_CODE, 'Response too long')
            #raise
        except Exception as e:
            if id is not None:
                # Send error to client
                error_code = (type(e).__name__ if type(e).__name__ in command_cls.errors else UNKNOWN_ERROR_CODE)
                send_error_reply(error_code, e.args[0])

    @asyncio.coroutine
    def call_remote(self, command, **kwargs):
        """
        ::

            yield from protocol.call_remote(EchoCommand, message='text')
        """
        # Send packet
        self._counter += 1
        packet = _serialize_command(command, kwargs)

        packet['_ask'] = Integer().encode(self._counter)
        packet['_command'] = String().encode(command.__name__)

        self._send_packet(packet)

        # Receive packet from remote end.
        f = asyncio.Future()
        self._queries[self._counter] = f

        try:
            packet = yield from f
            return _deserialize_answer(command, packet)
        except RemoteAmpError as e:
            if e.error_code == UNKNOWN_ERROR_CODE:
                raise UnknownRemoteError(e.error_description)

            if e.error_code == UNHANDLED_ERROR_CODE:
                raise UnhandledCommandError(e.error_description)

            elif e.error_code in command.errors:
                raise command.errors[e.error_code](e.error_description) from e
            else:
                raise
