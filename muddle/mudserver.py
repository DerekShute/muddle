"""
Basic MUD server module for creating text-based Multi-User Dungeon
(MUD) games.

Adapted from SwampyMud

This module and the MudServer claass was originally written by Mark
Frimston (mfrimston@gmail.com). We based MuddySwamp on Mark's code for
over 2 years, before ultimately replacing it with an asynchronous server
that would work better with the websockets package. Without Mark's
original module, this project would have never gotten off the ground.
Thank you, Mark.
"""

import logging
import asyncio
import websockets


class MudServer:
    '''
    A high-level game server that coordinates between a network interface
    and the in-game world.
    '''

    def __init__(self, game, ws_port=None, tcp_port=None):
        logging.debug("Server %r created", self)
        self.game = game
        self.tcp_port = tcp_port
        self.tcp_server = None
        self.tcp_clients = {}
        self.ws_port = ws_port
        self.ws_server = None
        self.next_id = 0
        self.running = False

        # at least one port must be provided
        if tcp_port is None and ws_port is None:
            raise ValueError("Server requires TCP port or WS port.")

    async def run(self):
        """
        Begin this MudServer.
        """

        logging.debug("Starting server...")

        if self.running:
            raise RuntimeError(f"server {self!r} is already running")
        self.running = True

        # We create a list of coroutines, since we might be running more
        # than just one if we have a TCP Server AND a WebSocketServer.
        coroutines = []

        if self.tcp_port is not None:
            self.tcp_server = await asyncio.start_server(
                self.register_tcp,
                port=self.tcp_port
            )
            # add it to the list of coroutines
            coroutines.append(self.tcp_server.serve_forever())

        if self.ws_port is not None:
            self.ws_server = await websockets.serve(
                self.register_ws,
                port=self.ws_port
            )
            # use a simple coro so that MudServer doesn't close
            # with WebSocketServer still running
            coroutines.append(self.ws_server.wait_closed())

        # We use asyncio.gather() to execute multiple coroutines.
        await asyncio.gather(*coroutines, return_exceptions=True)

    def shutdown(self):
        """
        Shut down this server and disconnect all clients. (Both TCP
        and WebSocket clients are disconnected.)
        """
        if self.tcp_server is not None:
            self.tcp_server.close()
            # asyncio.Server doesn't automatically close existing
            # sockets, so we manually close them all now
            for stream_writer in self.tcp_clients.values():
                stream_writer.close()
        if self.ws_server is not None:
            self.ws_server.close()
        self.running = False

    #
    # TCP methods
    #

    async def register_tcp(self, reader, writer):
        """
        Register a new TCP client with this server.

        This internal method is sent to asyncio.start_server().
        See https://docs.python.org/3/library/asyncio-stream.html to
        get a better idea of what's going on here.
        """
        # First, grab a new unique identifier.
        pid = self.next_id
        self.next_id += 1

        # Closure
        self.tcp_clients[pid] = writer

        self.game.on_connect(pid)

        # Now we create two coroutines, one for handling incoming messages,
        # and one for handling outgoing messages.

        # If a player disconnects, the incoming_tcp coroutine will wake up,
        # and run to completion. However, the outgoing_tcp coroutine
        # will be stuck waiting until the player's Character receives a
        # message.
        # We want to move on immediately when the player disconnects, so
        # we return_when=asyncio.FIRST_COMPLETED here.
        await asyncio.wait(
            [
                asyncio.create_task(self.incoming_tcp(pid, reader)),
                asyncio.create_task(self.outgoing_tcp(pid, writer))
            ],
            return_when=asyncio.FIRST_COMPLETED
        )

        # If the interpreter reaches this line, that means an EOF has
        # been detected and this player has disconnected.

        writer.close()
        self.game.on_disconnect(pid)

    async def incoming_tcp(self, pid, reader):
        """Handle incoming messages from a Tcp Client."""

        # When the user disconnects, asyncio will call it "EOF" (end of
        # file). Until then, we simply try to read a line from the
        # user.
        while not reader.at_eof():
            # reader.readline() is an asynchronous method
            # This means that it won't actually execute on its own
            # unless we 'await' it.
            # Under the hood, using this 'await' actually switches to
            # execute some other code until this player sends us
            # a message.
            msg = await reader.readline()

            # The player just sent us a message!
            # Remove any whitespace and convert from bytes to str
            msg = msg.strip().decode(encoding="latin1")

            if msg:
                self.game.on_input(pid, msg)

        logging.debug("incoming_tcp closed for %s", pid)

    async def outgoing_tcp(self, pid, writer):
        """
        Handles outgoing messages: messages that must be forwarded
        """

        # This coroutine just loops forever, and will eventually be
        # broken once the client disconnects.
        while True:
            # Try to get a message from the Character's queue.
            # This will block until the character receives a message.
            msg = await self.game.get_output(pid)

            # Add a newline character and convert the message into bytes
            msg = (msg + "\n\r").encode('latin-1')
            writer.write(msg)

            # Once we've written to a StreamWriter, we have to call
            # writer.drain(), which blocks.
            try:
                await writer.drain()
            # If the player disconnected, we will get an error.
            # We will break and finish the coroutine.
            except ConnectionResetError:
                break

        logging.debug("outgoing_tcp closed for %s", pid)

    #
    # Websocket methods
    #

    async def register_ws(self, websocket, path):
        # we don't currently do anything with the path, so just log it
        logging.debug("WebSocket %s connected at path %s", websocket, path)

        # First, grab a new unique identifier.
        pid = self.next_id
        self.next_id += 1

        self.game.on_connect(pid)

        # WebSockets have a slightly different API than the tcp streams
        # rather than a reading and writing stream, which just have
        # one socket.
        # As with register_tcp, we want to quit immediately the player
        # disconnects, so we use return_when=asyncio.FIRST_COMPLETED
        await asyncio.wait(
            [
                asyncio.create_task(self.incoming_ws(pid, websocket)),
                asyncio.create_task(self.outgoing_ws(pid, websocket))
            ],
            return_when=asyncio.FIRST_COMPLETED
        )

        # If this code is reached, then the WebSocket has disconnected.
        # This should already be closed, but just in case.
        await websocket.close()
        self.game.on_disconnect(pid)

    async def incoming_ws(self, pid, websocket):
        """Handle incoming messages from a Websocket Client."""
        # websockets have a convenient __aiter__ interface, allowing
        # us to just iterate over the messages forever.
        # Under the hood, if there are no messages available from the
        # WebSocket, this code will yield and until another message is
        # received.

        # If the WebSocket is disconnected unexpectedly, the for loop
        # will produce an exception.
        try:
            async for msg in websocket:
                msg = msg.strip()
                if msg:
                    self.game.on_input(pid, msg)
        # If we get this error, then player probably just logged off.
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            logging.debug("incoming_ws closed for %s", pid)

    async def outgoing_ws(self, pid, websocket):
        """
        Handles outgoing messages: messages that must be forwarded
        """

        while not websocket.closed:
            msg = await self.game.get_output(pid)

            try:
                await websocket.send(msg + "\n\r")
            except websockets.exceptions.ConnectionClosed:
                break

        logging.debug("outgoing_ws closed for %s", pid)

# EOF
