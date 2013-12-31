import unittest
import asyncio

from asyncio_amp import (
    Integer,
    Bytes,
    Float,
    Boolean,
    String,
    AMPProtocol,

    Command,
)

class MyException(Exception):
    pass

class EchoCommand(Command):
    arguments = [
            ('text', String()),
            ('times', Integer()),
    ]
    response = [
            ('text', String()),
    ]
    errors = { 'MyException': MyException }


class ArgumentsTest(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_arguments(self):
        # encoded/decoded pairs
        tuples = [
                (Integer(), 1234567890, b'1234567890'),
                (Float(), 3.99, b'3.99'),
                (Bytes(), b'data', b'data'),
                (String(), 'my-string', b'my-string'),
                (Boolean(), True, b'True'),
                (Boolean(), False, b'False'),
        ]
        for type, value, encoded in tuples:
            self.assertEqual(type.encode(value), encoded)
            self.assertEqual(type.decode(encoded), value)


class RemoteCallTest(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.get_event_loop()

    def test_simple_call(self):
        class ServerProtocol(AMPProtocol):
            @EchoCommand.responder
            def echo(self, text, times):
                return { 'text': text * times }

        def run():
            # Create server and client
            server = yield from self.loop.create_server(ServerProtocol, 'localhost', 8000)
            transport, protocol =  yield from self.loop.create_connection(AMPProtocol, 'localhost', 8000)

            # Test call
            result = yield from protocol.call_remote(EchoCommand(text='my-text', times=2))
            self.assertEqual(result['text'], 'my-textmy-text')

            # Shut down server.
            server.close()

        self.loop.run_until_complete(run())

    def test_coroutine_responder(self):
        class ServerProtocol(AMPProtocol):
            @EchoCommand.responder
            def echo(self, text, times):
                yield from asyncio.sleep(.1)
                return { 'text': text * times }

        def run():
            # Create server and client
            server = yield from self.loop.create_server(ServerProtocol, 'localhost', 8000)
            transport, protocol =  yield from self.loop.create_connection(AMPProtocol, 'localhost', 8000)

            # Test call
            result = yield from protocol.call_remote(EchoCommand(text='my-text', times=2))
            self.assertEqual(result['text'], 'my-textmy-text')

            # Shut down server.
            server.close()

        self.loop.run_until_complete(run())

    def test_exception_in_responder(self):
        class ServerProtocol(AMPProtocol):
            @EchoCommand.responder
            def echo(self, text, times):
                yield from asyncio.sleep(.1)
                raise MyException('Something went wrong')

        def run():
            # Create server and client
            server = yield from self.loop.create_server(ServerProtocol, 'localhost', 8000)
            transport, protocol =  yield from self.loop.create_connection(AMPProtocol, 'localhost', 8000)

            # Test call
            with self.assertRaises(MyException) as e:
                yield from protocol.call_remote(EchoCommand(text='my-text', times=2))
            self.assertEqual(e.exception.args[0], 'Something went wrong')

            # Shut down server.
            server.close()

        self.loop.run_until_complete(run())


if __name__ == '__main__':
    unittest.main()
