import asyncio
import asyncio_amp

if __name__ == '__main__':
    class EchoCommand(asyncio_amp.Command):
        arguments = [
            ('text', asyncio_amp.String()),
            ('times', asyncio_amp.Integer()),
        ]
        response = [
            ('text', asyncio_amp.String()),
        ]

    class MyProtocol(asyncio_amp.AMPProtocol):
        @EchoCommand.responder
        def echo(self, text, times):
            yield from asyncio.sleep(1)
    #        yield from self.call_remote(Hello())
            return { 'text': ('You said:' + text) * times }

    loop = asyncio.get_event_loop()
    server = loop.run_until_complete(loop.create_server(MyProtocol, 'localhost', 8000))
    print(server.sockets[0].getsockname())
    loop.run_forever()
