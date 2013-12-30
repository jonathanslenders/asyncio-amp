import asyncio
import asyncio_amp

if __name__ == '__main__':
    class EchoCommand(asyncio_amp.Command):
        arguments = {
            'text': asyncio_amp.String(),
            'times': asyncio_amp.Integer(),
        }
        response = {
            'text': asyncio_amp.String(),
        }

    @asyncio.coroutine
    def run():
        transport, protocol = yield from loop.create_connection(asyncio_amp.AMPProtocol, 'localhost', 8000)
        result = yield from protocol.call_remote(EchoCommand(text='Hello world', times=4))
        print(result)

    loop = asyncio.get_event_loop()
    s = loop.run_until_complete(run())
    #print (s.sockets[0].getsockname())
    #loop.run_forever()
