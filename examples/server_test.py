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
    f = loop.create_server(MyProtocol, 'localhost', 8000)
    s = loop.run_until_complete(f)
    print (s.sockets[0].getsockname())
    loop.run_forever()
