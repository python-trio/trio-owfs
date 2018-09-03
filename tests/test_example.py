import trio
from .mock_server import server, EventChecker
from trio_owfs.protocol import NOPMsg, DirMsg
from trio_owfs.event import ServerRegistered,ServerConnected,ServerDisconnected,ServerDeregistered,DeviceAdded,DeviceLocated,DeviceNotFound
from copy import deepcopy

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
        DirMsg(("bus.0",)),
    ]
    e1 = EventChecker([
        ServerRegistered,
        ServerConnected,
        DeviceAdded("10.345678.90"),
        DeviceLocated("10.345678.90"),
        ServerDisconnected,
        ServerDeregistered,
    ])
    async with server(msgs=msgs, events=e1, tree=basic_tree) as ow:
        await trio.sleep(0)

async def test_busy_server():
    msgs = [
        NOPMsg(),
        DirMsg(()),
        DirMsg(("bus.0",)),
    ]
    e1 = EventChecker([
        ServerRegistered,
        ServerConnected,
        DeviceAdded("10.345678.90"),
        DeviceLocated("10.345678.90"),
        ServerDisconnected,
        ServerDeregistered,
    ])
    async with server(msgs=msgs, events=e1, tree=basic_tree, options={'busy_every':1}) as ow:
        await trio.sleep(0)

async def test_dropped_device():
    msgs = [
        NOPMsg(),
        DirMsg(()),
        DirMsg(("bus.0",)),
        DirMsg(()),
        DirMsg(("bus.0",)),
        DirMsg(()),
        DirMsg(("bus.0",)),
        DirMsg(()),
        DirMsg(("bus.0",)),
        DirMsg(()),
        DirMsg(("bus.0",)),
    ]
    e1 = EventChecker([
        ServerRegistered,
        ServerConnected,
        DeviceAdded("10.345678.90"),
        DeviceLocated("10.345678.90"),
        DeviceNotFound("10.345678.90"),
        ServerDisconnected,
        ServerDeregistered,
    ])
    my_tree = deepcopy(basic_tree)
    async with server(msgs=msgs, events=e1, tree=my_tree) as ow:
        await trio.sleep(0)
        del my_tree['bus.0']['10.345678.90']
        dev = ow.get_device('10.345678.90')
        assert dev._unseen == 0
        await ow.scan_now()
        assert dev._unseen == 1
        await ow.scan_now()
        assert dev._unseen == 2
        await ow.scan_now()
        assert dev._unseen == 3
        assert dev.bus is not None
        await ow.scan_now()
        assert dev._unseen == 3
        assert dev.bus is None

