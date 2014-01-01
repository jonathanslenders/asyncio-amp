asyncio-amp
===========

AMP client and server library for asyncio.


About
-----

AMP, short for asynchronous messaging protocol, is a protocol for asynchronous
interprocess communication. You can call exposed functions in another process
and receive the answer when it's ready.

It appeared originally in Twisted. This is the Twisted documentation:
http://twistedmatrix.com/documents/8.2.0/api/twisted.protocols.amp.html

More information about the protocol:
http://amp-protocol.net/


Example
-------

First, you have to decide which remote calls you want to expose, what
parameters these calls accept, what the returned result looks like and which
exceptions can occur. This should be defined in a ``Command``, for instance:

.. code:: python

    import asyncio_amp

    class RepeatCommand(asyncio_amp.Command):
        arguments = [
            ('text', asyncio_amp.String()),
            ('times', asyncio_amp.Integer())
        ]
        response = [
            ('text', asyncio_amp.String()),
        ]

This is a simple command which takes a string and an integer as input and
returns the given string that many times concatenated. So, if the input is
("abc", 3), the output will be "abcabcabc".

Now we are going to write a client and a server. It is important that both the
client and the server know about this ``RepeatCommand`` definition. You can
write it in a separate python file and include it from the server and clients.


The server
----------

Now, in order to implement the server, the ``AMPProtocol`` must be inherited
and have responders attached as shown below. A responder answers such a
command. The parameter of a responder method should always match the arguments
of the command and a responder should always return a dictionary, where the keys
match the response as defined by the command.

.. code:: python

    import asyncio
    import asyncio_amp

    class MyRepeatProtocol(asyncio_amp.AMPProtocol):
        @RepeatCommand.responder
        def repeat(self, text, times):
            return {
                'text': text * times,
            }

    loop = asyncio.get_event_loop()

    # Run the create_server coroutine, which returns a server object.
    server = loop.run_until_complete(loop.create_server(
                                    MyRepeatProtocol, 'localhost', 8000))
    print(server.sockets[0].getsockname())

    # Keep running the event loop, wait for incoming connections.
    loop.run_forever()


Note that a responder can be a coroutine, You can use ``yield from`` inside the
responder.


The client
----------

The client consists of a coroutine which first sets up the server connection
and then uses the ``call_remote`` coroutine to do the actual call.


.. code:: python

    @asyncio.coroutine
    def run():
        # Establish server connection
        transport, protocol = yield from loop.create_connection(
                                            asyncio_amp.AMPProtocol, 'localhost', 8000)

        # Call remote command.
        result = yield from protocol.call_remote(EchoCommand(text='Hello world', times=4))
        print(result)

    loop = asyncio.get_event_loop()
    loop.run_until_complete(run())


Passing exceptions from the server to the client
------------------------------------------------

TODO


Doing a call from the server to the client
------------------------------------------

AMP is fully bidirectional.

TODO

Limitations of the protocol
---------------------------

The AMP protocol is designed to pass many small messages. The length of a field
is actually encoded in a single byte, and therefore each of the arguments
should not exceed the 255 bytes limit when encoded.
