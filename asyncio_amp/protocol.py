import asyncio

from .arguments import String, Integer

__all__ = ('Command', 'AMPProtocol')

class RemoteAmpError(Exception):
    def __init__(self, error_code, error_description):
        self.error_code = error_code
        self.error_description = error_description


class Command:
    arguments = []
    response = []
    errors = dict()

    def __init__(self, **kwargs):
        # Check input data.
        for k, v in self.arguments:
            if not isinstance(kwargs[k], v.type):
                raise TypeError('Expected type %s for argument %s, got %r' % (v.type, k, kwargs[k]))

        self._kwargs = kwargs

    @classmethod
    def responder(cls, methodfunc):
        methodfunc._responds_to_amp_command = cls
        return asyncio.coroutine(methodfunc)


def _serialize_command(command):
    return { k: v.encode(command._kwargs[k]) for k, v in command.arguments if k in command._kwargs }

def _deserialize_command(command_cls, packet):
    return { k: v.decode(packet[k]) for k, v in command_cls.arguments }

def _serialize_answer(command_cls, answer_dict):
    return { k: v.encode(answer_dict[k]) for k, v in command_cls.response if k in answer_dict }

def _deserialize_answer(command_cls, packet):
    return { k: v.decode(packet[k]) for k, v in command_cls.response }


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
            # First, receive NULL byte
            b = yield 1
            assert b == b'\0'

            # Next receive either SIZE or another NULL.
            length = (yield 1)[0]

            # Another NULL means the end of a packet
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
            @asyncio.coroutine
            def handle_query():
                command = String().decode(packet.pop('_command'))
                id = packet.pop('_ask', None)

                responder = self.responders[command]
                command_cls = responder._responds_to_amp_command

                # Decode
                kwargs = _deserialize_command(command_cls, packet)

                # Call responder
                try:
                    result = yield from responder(self, ** kwargs)
                except Exception as e:
                    # When this is an known error, send it back.
                    if type(e).__name__ in command_cls.errors:
                        if id is not None:
                            reply = {
                                    '_error': id,
                                    '_error_code': String().encode(type(e).__name__),
                                    '_error_description': String().encode(e.args[0]),
                                    }
                            self._send_packet(reply)
                        return
                    else:
                        raise

                # Send answer.
                if id is not None:
                    reply = { '_answer': id }
                    reply.update(_serialize_answer(command_cls, result))
                    self._send_packet(reply)

            asyncio.Task(handle_query())

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

        def write_value(value):
            write(bytes((0, len(value))))
            write(value)

        for k, v in packet.items():
            write_value(k.encode('ascii'))
            write_value(v)

        write(bytes((0, 0)))

    @asyncio.coroutine
    def call_remote(self, command, return_answer=True):
        """
        ::

            yield from protocol.call_remote(EchoCommand, message='text')
        """
        # Send packet
        self._counter += 1
        packet = _serialize_command(command)

        if return_answer:
            packet['_ask'] = Integer().encode(self._counter)
        packet['_command'] = String().encode(command.__class__.__name__)

        self._send_packet(packet)

        # Receive packet from remote end.
        if return_answer:
            f = asyncio.Future()
            self._queries[self._counter] = f

            try:
                packet = yield from f
                return _deserialize_answer(command.__class__, packet)
            except RemoteAmpError as e:
                if e.error_code in command.errors:
                    raise command.errors[e.error_code](e.error_description) from e
