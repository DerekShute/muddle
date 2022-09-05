#!/usr/bin/env python

# https://www.piesocket.com/blog/python-websocket

import asyncio
import websockets

uri = "ws://localhost:9000"


async def test():
    async with websockets.connect(uri) as websocket:
        while True:
            incoming = await websocket.recv()
            print("got: " + incoming)
            msg = input(">")
            await websocket.send(msg)


if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(test())
        loop.run_forever()
    except (KeyboardInterrupt, EOFError):
        print("Quitting!")

# EOF
