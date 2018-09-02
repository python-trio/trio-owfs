import trio
from .mock_server import server, EventChecker
from trio_owfs.protocol import NOPMsg, DirMsg
from trio_owfs.event import ServerRegistered,ServerConnected,ServerDisconnected,ServerDeregistered

# We can just use 'async def test_*' to define async tests.
# This also uses a virtual clock fixture, so time passes quickly and
# predictably.

basic_tree = {
        "bus.0": {
            "10.345678.90": {
                "whatever": "hello",
                "temperature": "12.5",
            }
        }
    }

async def test_empty_server():
    msgs = [
        NOPMsg(),
        DirMsg(()),
    ]
    e1 = EventChecker([
        ServerRegistered,
        ServerConnected,
        ServerDisconnected,
        ServerDeregistered,
    ])
    async with server(msgs=msgs, events=e1) as ow:
        await trio.sleep(0)

async def test_basic_server():
    msgs = [
        NOPMsg(),
        DirMsg(()),
    ]
    e1 = EventChecker([
        ServerRegistered,
        ServerConnected,
        ServerDisconnected,
        ServerDeregistered,
    ])
    async with server(msgs=msgs, events=e1, tree=basic_tree) as ow:
        await trio.sleep(1)

