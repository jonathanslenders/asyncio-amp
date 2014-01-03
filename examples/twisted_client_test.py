from twisted.internet import reactor, defer, endpoints
from twisted.internet.endpoints import TCP4ClientEndpoint, connectProtocol
from twisted.protocols.amp import AMP
from twisted.protocols import amp

class EchoCommand(amp.Command):
        arguments = [
            ('text', amp.String()),
            ('times', amp.Integer()),
        ]
        response = [
            ('text', amp.String()),
        ]

def testAsyncioAmpServer():
    destination = TCP4ClientEndpoint(reactor, '127.0.0.1', 8000)
    echoDeferred = connectProtocol(destination, AMP())

    def connected(ampProto):
        return ampProto.callRemote(EchoCommand, text='Goodbye python2 '*4, times=7)
    echoDeferred.addCallback(connected)

    def done(result):
        print('Done with echo:', result)
        reactor.stop()
    echoDeferred.addCallback(done)

if __name__ == '__main__':
    testAsyncioAmpServer()
    reactor.run()
