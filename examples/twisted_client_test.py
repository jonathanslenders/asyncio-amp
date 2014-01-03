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

    def failed(failure):
        failure.printTraceback()
        if reactor.running:
            reactor.stop()

    def connected(ampProto, msg, x=7):
        return ampProto.callRemote(EchoCommand, text=msg, times=x)
    echoDeferred.addCallback(connected, 'Goodbye python 2 ' * 4)
    echoDeferred.addErrback(failed)

    def done(result, stop=False):
        print('Done with echo:', result)
        if reactor.running and stop:
            reactor.stop()
        
    echoDeferred.addCallback(done)
    echoDeferred = connectProtocol(destination, AMP())
    echoDeferred.addCallback(connected, 'Welcome python 3 ')
    echoDeferred.addErrback(failed)
    echoDeferred.addCallback(done, True)

if __name__ == '__main__':
    testAsyncioAmpServer()
    reactor.run()
