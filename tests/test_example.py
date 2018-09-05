import trio
import pytest
from copy import deepcopy

from trio_owfs.protocol import NOPMsg, DirMsg, AttrGetMsg, AttrSetMsg
from trio_owfs.error import NoEntryError
from trio_owfs.event import ServerRegistered, ServerConnected, ServerDisconnected, \
    ServerDeregistered, DeviceAdded, DeviceLocated, DeviceNotFound, BusAdded_Path, \
    BusAdded, BusDeleted
from trio_owfs.bus import Bus

from .mock_server import server, EventChecker

import logging
logger = logging.getLogger(__name__)

# We can just use 'async def test_*' to define async tests.
# This also uses a virtual clock fixture, so time passes quickly and
# predictably.

structs = {
    "10":
        {
            "address": "a,000000,000001,ro,000016,f,",
            "alias": "l,000000,000001,rw,000256,f,",
            "crc8": "a,000000,000001,ro,000002,f,",
            "family": "a,000000,000001,ro,000002,f,",
            "id": "a,000000,000001,ro,000012,f,",
            "latesttemp": "t,000000,000001,ro,000012,v,",
            "locator": "a,000000,000001,ro,000016,f,",
            "power": "y,000000,000001,ro,000001,v,",
            "r_address": "a,000000,000001,ro,000016,f,",
            "r_id": "a,000000,000001,ro,000012,f,",
            "r_locator": "a,000000,000001,ro,000016,f,",
            "scratchpad": "b,000000,000001,ro,000009,v,",
            "temperature": "t,000000,000001,ro,000012,v,",
            "temphigh": "t,000000,000001,rw,000012,s,",
            "templow": "t,000000,000001,rw,000012,s,",
            "type": "a,000000,000001,ro,000032,f,",
        },
}

basic_tree = {
    "bus.0":
        {
            "10.345678.90":
                {
                    "whatever": "hello",
                    "temperature": "12.5",
                    "templow": "10",
                    "temphigh": "20",
                }
        },
    "structure": structs,
}

coupler_tree = {
    "bus.0":
        {
            "10.345678.90": {
                "whatever": "hello",
                "temperature": "12.5",
            },
            "1F.ABCDEF.F1":
                {
                    "main": {
                        "20.222222.22": {
                            "some": "chip",
                        },
                    },
                    "aux": {
                        "28.282828.28": {
                            "another": "chip",
                        },
                    },
                }
        },
    "structure": structs,
}


async def test_empty_server():
    msgs = [
        NOPMsg(),
        DirMsg(()),
    ]
    e1 = EventChecker(
        [
            ServerRegistered,
            ServerConnected,
            ServerDisconnected,
            ServerDeregistered,
        ]
    )
    async with server(msgs=msgs, events=e1):  # as ow:
        await trio.sleep(0)


async def test_send_idle(mock_clock):
    mock_clock.autojump_threshold = 0.1
    msgs = [
        NOPMsg(),
        DirMsg(()),
        NOPMsg(),
    ]
    e1 = EventChecker(
        [
            ServerRegistered,
            ServerConnected,
            ServerDisconnected,
            ServerDeregistered,
        ]
    )
    async with server(msgs=msgs, events=e1):  # as ow:
        await trio.sleep(15)


async def test_missing_event():
    msgs = [
        NOPMsg(),
        DirMsg(()),
    ]
    e1 = EventChecker([
        ServerRegistered,
        ServerConnected,
        ServerDisconnected,
    ])
    with pytest.raises(RuntimeError) as r:
        async with server(msgs=msgs, events=e1):  # as ow:
            await trio.sleep(0)
    assert "Unexpected event " in r.value.args[0]


async def test_more_event():
    msgs = [
        NOPMsg(),
        DirMsg(()),
    ]
    e1 = EventChecker(
        [
            ServerRegistered,
            ServerConnected,
            ServerDisconnected,
            ServerDeregistered,
            ServerDeregistered,
        ]
    )
    with pytest.raises(RuntimeError) as r:
        async with server(msgs=msgs, events=e1):  # as ow:
            await trio.sleep(0)
    assert "Superfluous event " in r.value.args[0]


async def test_bad_event():
    msgs = [
        NOPMsg(),
        DirMsg(()),
    ]
    e1 = EventChecker([
        ServerRegistered,
        ServerConnected,
        ServerConnected,
        ServerDeregistered,
    ])
    with pytest.raises(RuntimeError) as r:
        async with server(msgs=msgs, events=e1):  # as ow:
            await trio.sleep(0)
    assert "Wrong event: want " in r.value.args[0]


async def test_wrong_msg():
    msgs = [
        NOPMsg(),
        DirMsg(("foobar",)),
    ]
    e1 = EventChecker(
        [
            ServerRegistered,
            ServerConnected,
            ServerDisconnected,
            ServerDeregistered,
        ]
    )
    with pytest.raises(RuntimeError) as r:
        async with server(msgs=msgs, events=e1):  # as ow:
            await trio.sleep(0)
    assert " wrong seen " in r.value.args[0]


async def test_wrong_msg_2():
    msgs = [
        NOPMsg(),
        NOPMsg(),
    ]
    e1 = EventChecker(
        [
            ServerRegistered,
            ServerConnected,
            ServerDisconnected,
            ServerDeregistered,
        ]
    )
    with pytest.raises(RuntimeError) as r:
        async with server(msgs=msgs, events=e1):  # as ow:
            await trio.sleep(0)
    assert " wrong seen " in r.value.args[0]


async def test_missing_msg():
    msgs = [
        NOPMsg(),
    ]
    e1 = EventChecker([
        ServerRegistered,
        ServerConnected,
        ServerDisconnected,
    ])
    with pytest.raises(RuntimeError) as r:
        async with server(msgs=msgs, events=e1):  # as ow:
            await trio.sleep(0)
    assert "Unexpected command " in r.value.args[0]


async def test_more_msg():
    msgs = [
        NOPMsg(),
        DirMsg(()),
        DirMsg(()),
    ]
    e1 = EventChecker(
        [
            ServerRegistered,
            ServerConnected,
            ServerDisconnected,
            ServerDeregistered,
        ]
    )
    with pytest.raises(RuntimeError) as r:
        async with server(msgs=msgs, events=e1):  # as ow:
            await trio.sleep(0)
    assert " not seen " in r.value.args[0]


async def test_basic_server():
    msgs = [
        NOPMsg(),
        DirMsg(()),
        DirMsg(("bus.0",)),
        AttrGetMsg("bus.0", "10.345678.90", "temperature"),
        AttrSetMsg("bus.0", "10.345678.90", "temperature", value=98.25),
        AttrGetMsg("bus.0", "10.345678.90", "temperature"),
        AttrSetMsg("bus.0", "10.345678.90", "temperature", value=12.5),
    ]
    e1 = EventChecker(
        [
            ServerRegistered,
            ServerConnected,
            BusAdded_Path("bus.0"),
            DeviceAdded("10.345678.90"),
            DeviceLocated("10.345678.90"),
            ServerDisconnected,
            DeviceNotFound,
            BusDeleted,
            ServerDeregistered,
        ]
    )
    async with server(msgs=msgs, events=e1, tree=basic_tree) as ow:
        await trio.sleep(0)
        dev = ow.get_device("10.345678.90")
        assert dev.bus == ('bus.0',)
        assert isinstance(dev.bus, Bus)
        assert float(await dev.attr_get("temperature")) == 12.5
        await dev.attr_set("temperature", value=98.25)
        assert float(await dev.attr_get("temperature")) == 98.25
        await dev.attr_set("temperature", value=12.5)


async def test_basic_structs(mock_clock):
    mock_clock.autojump_threshold = 0.1
    async with server(tree=basic_tree, options={'slow_every': [0, 1], 'busy_every': [0, 0, 1],
                                                'close_every': [0, 0, 0, 1]}) as ow:
        await trio.sleep(0)
        dev = ow.get_device("10.345678.90")
        await ow.ensure_struct(dev)
        assert await dev.temperature == 12.5
        await dev.set_temphigh(98.25)
        assert await dev.temphigh == 98.25

        # while we're at it, test our ability to do things in parallel on a broken server
        dat = {}
        evt = trio.Event()

        async def get_val(tag):
            await evt.wait()
            dat[tag] = await getattr(dev, tag)

        async with trio.open_nursery() as n:
            n.start_soon(get_val, 'temperature')
            n.start_soon(get_val, 'temphigh')
            n.start_soon(get_val, 'templow')
            await trio.sleep(1)
            evt.set()
        assert dat == {'temphigh': 98.25, 'temperature': 12.5, 'templow': 10.0}, dat


async def test_coupler_server():
    msgs = [
        NOPMsg(),
        DirMsg(()),
        DirMsg(("bus.0",)),
        DirMsg(("bus.0", "1F.ABCDEF.F1", "main")),
        DirMsg(("bus.0", "1F.ABCDEF.F1", "aux")),
    ]
    e1 = EventChecker(
        [
            ServerRegistered,
            ServerConnected,
            BusAdded_Path("bus.0"),
            DeviceAdded("10.345678.90"),
            DeviceLocated("10.345678.90"),
            DeviceAdded("1F.ABCDEF.F1"),
            DeviceLocated("1F.ABCDEF.F1"),
            BusAdded_Path("bus.0", "1F.ABCDEF.F1", "main"),
            DeviceAdded("20.222222.22"),
            DeviceLocated("20.222222.22"),
            BusAdded_Path("bus.0", "1F.ABCDEF.F1", "aux"),
            DeviceAdded("28.282828.28"),
            DeviceLocated("28.282828.28"),
            ServerDisconnected,
            DeviceNotFound("20.222222.22"),
            BusDeleted,
            DeviceNotFound("28.282828.28"),
            BusDeleted,
            DeviceNotFound("10.345678.90"),
            DeviceNotFound("1F.ABCDEF.F1"),
            BusDeleted,
            ServerDeregistered,
        ]
    )
    async with server(msgs=msgs, events=e1, tree=coupler_tree):  # as ow:
        await trio.sleep(0)


async def test_wrong_bus():
    msgs = [
        NOPMsg(),
        DirMsg(()),
        DirMsg(("bus.0",)),
    ]
    e1 = EventChecker(
        [
            ServerRegistered,
            ServerConnected,
            BusAdded_Path("bus-whatever"),
            #       DeviceAdded("10.345678.90"),
            #       DeviceLocated("10.345678.90"),
            #       ServerDisconnected,
            #       ServerDeregistered,
        ]
    )
    with pytest.raises(RuntimeError) as r:
        async with server(msgs=msgs, events=e1, tree=basic_tree):  # as ow:
            await trio.sleep(0)
    assert "Wrong event: want " in r.value.args[0]


async def test_slow_server(mock_clock):
    mock_clock.autojump_threshold = 0.1
    msgs = [
        [
            NOPMsg(),
            DirMsg(()),
            NOPMsg(),
        ], [
            DirMsg(()),
            NOPMsg(),
            DirMsg(("bus.0",)),
            NOPMsg(),
        ], [
            DirMsg(("bus.0",)),
            NOPMsg(),
        ], [
            DirMsg(("bus.0",)),
        ]
    ]
    e1 = EventChecker(
        [
            ServerRegistered,
            ServerConnected,
            ServerDisconnected,
            ServerConnected,
            BusAdded,
            ServerDisconnected,
            ServerConnected,
            DeviceAdded("10.345678.90"),
            DeviceLocated("10.345678.90"),
            ServerDisconnected,
            DeviceNotFound("10.345678.90"),
            BusDeleted,
            ServerDeregistered,
        ]
    )
    async with server(msgs=msgs, events=e1, tree=basic_tree,
                      options={'slow_every': [0, 0, 15, 0, 0]}):  # as ow:
        await trio.sleep(0)


async def test_busy_server():
    msgs = [
        NOPMsg(),
        DirMsg(()),
        DirMsg(("bus.0",)),
    ]
    e1 = EventChecker(
        [
            ServerRegistered,
            ServerConnected,
            BusAdded,
            DeviceAdded("10.345678.90"),
            DeviceLocated("10.345678.90"),
            ServerDisconnected,
            DeviceNotFound("10.345678.90"),
            BusDeleted,
            ServerDeregistered,
        ]
    )
    async with server(msgs=msgs, events=e1, tree=basic_tree, options={'busy_every': [0, 0, 1]}):
        await trio.sleep(0)
    async with server(msgs=msgs, events=e1, tree=basic_tree, options={'busy_every': [1, 0, 1]}):
        await trio.sleep(0)


async def test_disconnecting_server():
    msgs = [[
        NOPMsg(),
        DirMsg(()),
    ], [
        DirMsg(()),
        DirMsg(("bus.0",)),
    ], [
        DirMsg(("bus.0",)),
    ]]
    e1 = EventChecker(
        [
            ServerRegistered,
            ServerConnected,
            ServerDisconnected,
            ServerConnected,
            BusAdded,
            ServerDisconnected,
            ServerConnected,
            DeviceAdded("10.345678.90"),
            DeviceLocated("10.345678.90"),
            ServerDisconnected,
            DeviceNotFound("10.345678.90"),
            BusDeleted,
            ServerDeregistered,
        ]
    )
    async with server(msgs=msgs, events=e1, tree=basic_tree,
                      options={'close_every': [0, 0, 0, 1]}):  # as ow:
        await trio.sleep(0)


async def test_disconnecting_server_2(mock_clock):
    mock_clock.autojump_threshold = 0.1
    msgs = [[], [
        NOPMsg(),
        DirMsg(()),
    ], [
        DirMsg(()),
        DirMsg(("bus.0",)),
    ], [
        DirMsg(("bus.0",)),
    ]]
    e1 = EventChecker(
        [
            ServerRegistered,
            ServerConnected,
            ServerDisconnected,
            ServerConnected,
            ServerDisconnected,
            ServerConnected,
            BusAdded,
            ServerDisconnected,
            ServerConnected,
            DeviceAdded("10.345678.90"),
            DeviceLocated("10.345678.90"),
            ServerDisconnected,
            DeviceNotFound("10.345678.90"),
            BusDeleted,
            ServerDeregistered,
        ]
    )
    async with server(msgs=msgs, events=e1, tree=basic_tree,
                      options={'close_every': [0, 1, 0, 0]}):  # as ow:
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
    e1 = EventChecker(
        [
            ServerRegistered,
            ServerConnected,
            BusAdded,
            DeviceAdded("10.345678.90"),
            DeviceLocated("10.345678.90"),
            DeviceNotFound("10.345678.90"),
            ServerDisconnected,
            BusDeleted,
            ServerDeregistered,
        ]
    )
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


async def test_manual_device(mock_clock):
    class Checkpoint:
        pass

    mock_clock.autojump_threshold = 0.1
    msgs = [
        NOPMsg(),
        DirMsg(()),
        DirMsg(("bus.0",)),
        NOPMsg(),
        DirMsg(()),
        DirMsg(("bus.0",)),
    ]
    e1 = EventChecker(
        [
            ServerRegistered,
            ServerConnected,
            BusAdded,
            Checkpoint,
            DeviceAdded("10.345678.90"),
            Checkpoint,
            DeviceLocated("10.345678.90"),
            ServerDisconnected,
            DeviceNotFound("10.345678.90"),
            BusDeleted,
            ServerDeregistered,
        ]
    )
    my_tree = deepcopy(basic_tree)
    entry = my_tree['bus.0'].pop('10.345678.90')
    async with server(msgs=msgs, events=e1, tree=my_tree) as ow:
        ow.push_event(Checkpoint())
        dev = ow.get_device('10.345678.90')
        assert dev.bus is None
        await trio.sleep(15)
        ow.push_event(Checkpoint())
        my_tree['bus.0']['10.345678.90'] = entry
        await ow.scan_now()
        assert dev.bus is not None


async def test_nonexistent_device(mock_clock):
    mock_clock.autojump_threshold = 0.1
    my_tree = deepcopy(basic_tree)
    entry = my_tree.pop('bus.0')
    async with server(tree=my_tree, scan=None) as ow:
        bus = ow.test_server.get_bus('bus.0')
        assert bus.server == ow.test_server

        dev = ow.get_device('10.345678.90')
        dev.locate(bus)
        with pytest.raises(NoEntryError):
            assert float(await dev.attr_get("temperature")) == 12.5


async def test_manual_bus(mock_clock):
    class Checkpoint:
        pass

    mock_clock.autojump_threshold = 0.1
    msgs = [
        NOPMsg(),
        NOPMsg(),
        AttrGetMsg("bus.0", "10.345678.90", "temperature"),
        NOPMsg(),
        DirMsg(()),
        DirMsg(("bus.0",)),
    ]
    e1 = EventChecker(
        [
            ServerRegistered,
            ServerConnected,
            BusAdded_Path("bus.0"),
            DeviceAdded("10.345678.90"),
            DeviceLocated("10.345678.90"),
            Checkpoint,
            Checkpoint,
            ServerDisconnected,
            DeviceNotFound("10.345678.90"),
            BusDeleted,
            ServerDeregistered,
        ]
    )
    async with server(  #msgs=msgs, events=e1,
            tree=basic_tree, scan=None) as ow:
        bus = ow.test_server.get_bus('bus.0')
        assert bus.server == ow.test_server

        dev = ow.get_device('10.345678.90')
        assert dev.bus is None
        dev.locate(bus)
        assert dev.bus is not None
        assert float(await dev.attr_get("temperature")) == 12.5
