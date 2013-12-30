import asyncio

from .arguments import String, Integer

__all__ = ('Command', 'AMPProtocol')

class Command:
    arguments = dict()
    response = dict()

    def __init__(self, **kwargs):
        for k, v in self.arguments.items():
            assert isinstance(kwargs[k], v.type)

        self._kwargs = kwargs

    @classmethod
    def responder(cls, methodfunc):
        methodfunc._responds_to_amp_command = cls
        return methodfunc


def serialize_command(command):
    return { k.encode('ascii'): v.encode(command._kwargs[k]) for k, v in command.arguments.items() if k in command._kwargs }

def deserialize_command(command_cls, packet):
    return { k.decode('ascii'): command_cls.arguments[k.decode('ascii')].decode(v) for k, v in packet.items() }

def serialize_answer(command_cls, answer_dict):
    return { k.encode('ascii'): v.encode(answer_dict[k]) for k, v in command_cls.response.items() if k in answer_dict }

def deserialize_answer(command_cls, packet):
    return { k.decode('ascii'): command_cls.response[k.decode('ascii')].decode(v) for k, v in packet.items() }



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
                name = yield length
            else:
                value = yield length
                packet[name] = value
                name = None

    def _handle_incoming_packet(self, packet):
        # Incoming query.
        if b'_command' in packet:
            @asyncio.coroutine
            def handle_query():
                command = String().decode(packet.pop(b'_command'))
                id = packet.pop(b'_ask', None)

                responder = self.responders[command]
                command_cls = responder._responds_to_amp_command

                # Decode
                kwargs = deserialize_command(command_cls, packet)

                # Call responder
                result = yield from responder(self, ** kwargs)

                # Send answer.
                if id is not None:
                    reply = { b'_answer': id }
                    reply.update(serialize_answer(command_cls, result))
                    self._send_packet(reply)

            asyncio.Task(handle_query())

        # Incoming answer.
        elif b'_answer' in packet:
            id = Integer().decode(packet.pop(b'_answer'))
            future = self._queries.get(id, None)
            if future is not None:
                future.set_result(packet)
            else:
                raise Exception('Received answer to unknown query.')

    def _send_packet(self, packet):
        write = self.transport.write

        def write_value(value):
            write(bytes((0, len(value))))
            write(value)

        for k, v in packet.items():
            write_value(k)
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
        packet = serialize_command(command)

        if return_answer:
            packet[b'_ask'] = Integer().encode(self._counter)
        packet[b'_command'] = String().encode(command.__class__.__name__)

        self._send_packet(packet)

        # Receive packet from remote end.
        if return_answer:
            f = asyncio.Future()
            self._queries[self._counter] = f
            packet = yield from f

            return deserialize_answer(command.__class__, packet)

