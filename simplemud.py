"""A simple Multi-User Dungeon (MUD) game. Players can talk to each
other, examine their surroundings and move between rooms.

Based on mud-pi by Mark Frimston - mfrimston@gmail.com
"""

import time

from muddle.mudserver import MudServer


# ===== MUD CLASS

class Mud:
    def __init__(self, rooms, command_list):
        self.players = {}
        self.rooms = rooms
        self.command_list = command_list
        self.server = MudServer()

    def send_message(self, id, message):
        self.server.send_message(id, message)

    def send_to_all(self, message):
        for pid in self.players.keys():
            self.send_message(pid, message)

    def send_to_room(self, id, message):
        # Note: not sent to ID
        p_room = self.players[id]["room"]
        for pid in self.players.keys():
            if pid != id and p_room == self.players[pid]["room"]:
                self.send_message(pid, message)

    def add_new_player(self, id):
        self.players[id] = {
            "name": None,
            "room": None,
        }

        # send the new player a prompt for their name
        self.send_message(id,  "What is your name?")

    def remove_player(self, id):
        # if for any reason the player isn't in the player map, skip them and
        # move on to the next one
        if id not in self.players:
            print(f"remove_player: id {id} not in list")
            return

        p_name = self.players[id]["name"]
        self.send_to_all(f"{p_name} quit the game")

        # remove the player's entry in the player dictionary
        print(f'{id}:{p_name} has left the game')
        del self.players[id]

    def new_player(self, id, name):
        player = self.players[id]

        player["name"] = name
        player["room"] = "Tavern"
        rm = player["room"]

        print(f"Player {id}:{name} entered the game and is in room {rm}")
        self.send_to_all(f"{name} entered the game")

        self.send_message(id,
                          f"Welcome, {name}. Type 'help' for a list of commands.")
        self.send_message(id, self.rooms[rm]["description"])

    def player_action(self, id, command, params):
        # if for any reason the player isn't in the player map, skip them and
        # move on to the next one
        if id not in self.players:
            print(f"player_action: id {id} not in list")
            return

        # if the player hasn't given their name yet, use this first command as
        # their name and move them to the starting room.
        if self.players[id]["name"] is None:
            self.new_player(id, command)
        else:
            cmd_fn = self.command_list.get(
                command,
                self.command_list["unknown-command"]
            )
            cmd_fn(self, id, command, params)

    def run(self):
        while True:
            time.sleep(0.2)

            # 'update' must be called in the loop to keep the game
            # running and give us up-to-date information
            self.server.update()

            # go through any newly connected players
            for id in self.server.get_new_players():
                self.add_new_player(id)

            # go through any recently disconnected players
            for id in self.server.get_disconnected_players():
                self.remove_player(id)

            # go through any new commands sent from players
            for id, command, params in self.server.get_commands():
                self.player_action(id, command, params)


# ===== Game Commands

def unknown_cmd(mud, id, command, params):
    mud.send_message(id, "Unknown command '{}'".format(command))


def help_cmd(mud, id, command, params):
    help_str = """
Commands:
  say <message>  - Says something out loud, e.g. 'say Hello'
  look           - Examines the surroundings, e.g. 'look'
  go <exit>      - Moves through the exit specified, e.g. 'go outside'
"""
    mud.send_message(id, help_str)


def go_cmd(mud, id, command, params):
    ex = params.lower()
    p_name = mud.players[id]["name"]
    rm = mud.players[id]["room"]
    if not mud.rooms[rm]["exits"].get(ex):
        mud.send_message(id, "Unknown exit '{}'".format(ex))
        return

    mud.send_to_room(id, f"{p_name} left via exit '{ex}'")

    mud.players[id]["room"] = rooms[rm]["exits"][ex]
    rm = mud.players[id]["room"]
    print(f"Player {id}/{p_name} now in {rm}")

    mud.send_to_room(id, f"{p_name} arrived via exit '{ex}'")
    mud.send_message(id, f"You arrive at '{rm}'")


def look_cmd(mud, id, command, params):
    rm = mud.players[id]["room"]

    mud.send_message(id, rooms[rm]["description"])

    playershere = []
    for pid, pl in mud.players.items():
        # if in the same room as the player and have a name
        if pl["room"] == rm and pl["name"] is not None:
            playershere.append(pl["name"])

    mud.send_message(id, "Players here: {}".format(", ".join(playershere)))
    mud.send_message(id, "Exits are: {}".format(", ".join(rooms[rm]["exits"])))


def say_cmd(mud, id, command, params):
    p_name = mud.players[id]["name"]
    mud.send_to_room(id, f"{p_name} says: {params}")
    mud.send_message(id, f"you say: {params}")


#
# === MAIN ===
#

if __name__ == "__main__":
    command_list = {
        "go": go_cmd,
        "help": help_cmd,
        "look": look_cmd,
        "say": say_cmd,
        "unknown-command": unknown_cmd,
    }

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

    Mud(rooms, command_list).run()

# EOF
