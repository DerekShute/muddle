#!/usr/bin/env python3
'''main script for creating swampy MUDs'''

import asyncio
import sys
import logging
import errno
import argparse
import warnings
from muddle.mudserver import MudServer


#
# Player
#
class Player():
    def __init__(self, start):
        self.msgs = asyncio.Queue()
        self.location = start
        # TODO need game world?

    def message(self, message):
        '''
        Place incoming message (character command) into queue
        '''
        # TODO: is this processed by some worker thread or other coroutine?
        # Has to go into a second asyncio Queue for command dispatch
        self.msgs.put_nowait(message)

    def get_message(self):
        return self.msgs.get()


#
# Game World
#
class GameWorld():
    def __init__(self, rooms, start_location):
        self.start_location = start_location  # TODO must be in rooms
        self.players = {}
        self.rooms = rooms

    # ===== Player callbacks

    def on_connect(self, pid):
        """Executed whenever a new player [pid] joins the server"""
        logging.info("%s joined.", pid)
        character = Player(self.start_location)  # TODO need world reference?
        self.players[pid] = character
        character.message("Welcome to MUD")

        # TODO general announcement

    def on_disconnect(self, pid):
        """This method is executed whenever a player [pid] disconnects"""
        logging.info("%s quit.", pid)

        character = self.players.get(pid)
        if not character:
            return

        # only send a message if character had provided a name
        if str(character) != "[nameless character]":
            self.message_all(f"{character} quit the game.")
        # TODO purge self.players[]

    # ==== Input / Output to players

    def on_input(self, pid, msg):
        """Executed whenever a msg is received from [pid]'s connection"""
        character = self.players.get(pid)
        if not character:
            return
        character.message(msg)  # To command processing / execution queue

    def get_output(self, pid):
        """Get something from the player's outgoing queue"""
        character = self.players.get(pid)
        if character:
            return character.get_message()
        return None

    # ==== Utilities

    def message_all(self, message):
        """Sends the 'message' text to every connected player"""
        for character in self.players.values():
            character.message(message)


#
# MAIN
#

rooms = {
    "Tavern": {
        "description": "You're in a cozy tavern warmed by an open fire.",
        "exits": {"outside": "Outside"},
    },
    "Outside": {
        "description": "You're standing outside a tavern. It's raining.",
        "exits": {"inside": "Tavern"},
    }
}

if __name__ == "__main__":
    # Setup the logger
    logging.basicConfig(format='%(asctime)s [%(levelname)s] %(message)s',
                        level=logging.INFO,
                        handlers=[
                            logging.FileHandler("server.log"),
                            logging.StreamHandler(sys.stdout)
                        ])

    # Redirect warnings to the logger
    logging.captureWarnings(True)
    warnings.simplefilter('always')

    parser = argparse.ArgumentParser(
        description="Launch a Multi-User Dungeon."
    )
    parser.add_argument(
        "--ws", type=int, metavar="PORT",
        help="Specify a port for a WebSocket Server. [Default: 9000]"
    )
    parser.add_argument(
        "--tcp", type=int, metavar="PORT",
        help="Specify a port for a TCP Server. [Default: no TCP server]"
    )

    args = parser.parse_args()
    ws_port = args.ws
    tcp_port = args.tcp

    if ws_port is None and tcp_port is None:
        ws_port = 9000
    elif ws_port == tcp_port:
        print("Error: TCP server and WebSocket server cannot use the "
              f"same port '{ws_port}'.\nProvide different ports "
              "for each server.",
              file=sys.stderr)
        exit(1)

    if tcp_port is not None:
        logging.info(f"Launching a TCP Server on port {tcp_port}")
    if ws_port is not None:
        logging.info(f"Launching a WebSocket Server on port {ws_port}")

    world = GameWorld(rooms, "Tavern")

    try:
        server = MudServer(world, ws_port, tcp_port)
    # TODO: these excepts are no longer necessary, since port is bound
    # until server.run() is called
    except PermissionError:
        print(f"Error. Do not have permission to use port '{args.port}'",
              file=sys.stderr)
        exit(-1)
    except OSError as ex:
        if ex.errno == errno.EADDRINUSE:
            print(f"Error. Port '{args.port}' is already in use.",
                  file=sys.stderr)
        else:
            print(ex, file=sys.stderr)
        exit(-1)

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(server.run())
        loop.run_forever()
    except KeyboardInterrupt:
        logging.info("Keyboard interrupt detected")
        server.shutdown()

    logging.info("Server shutdown. Good bye!!")

# EOF
