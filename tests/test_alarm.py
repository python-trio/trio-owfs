import trio
import pytest
from copy import deepcopy

from trio_owfs.protocol import NOPMsg, DirMsg, AttrGetMsg, AttrSetMsg
from trio_owfs.error import NoEntryError
from trio_owfs.event import ServerRegistered, ServerConnected, ServerDisconnected, \
    ServerDeregistered, DeviceAdded, DeviceLocated, DeviceNotFound, BusAdded_Path, \
    BusAdded, BusDeleted, DeviceValue, DeviceAlarm
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
            "temperature": "t,000000,000001,ro,000012,v,",
            "temphigh": "t,000000,000001,rw,000012,s,",
            "templow": "t,000000,000001,rw,000012,s,",
            "type": "a,000000,000001,ro,000032,f,",
        },
}

basic_tree = {
    "bus.0":
        {
            "alarm": {},
            "simultaneous": {
                "temperature": 0,
                },
            "10.345678.90":
                {
                    "latesttemp": "12.5",
                    "templow": "15",
                    "temphigh": "20",
                }
        },
    "structure": structs,
}


async def test_alarm(mock_clock):
    e1 = EventChecker(
        [
            ServerRegistered,
            ServerConnected,
            BusAdded,
            DeviceAdded("10.345678.90"),
            DeviceLocated("10.345678.90"),
            DeviceAlarm("10.345678.90"),
            DeviceValue("10.345678.90", "temperature",12.5),
            #DeviceValue("10.345678.90", "temperature",12.5),
            #DeviceNotFound("10.345678.90"),
            ServerDisconnected,
            DeviceNotFound("10.345678.90"),
            BusDeleted,
            ServerDeregistered,
        ]
    )
    mock_clock.autojump_threshold = 0.1
    my_tree = deepcopy(basic_tree)
    dt = my_tree['bus.0'].pop('10.345678.90')
    async with server(tree=my_tree, polling=True, events=e1) as ow:
        dev = ow.get_device("10.345678.90")
        dev.interval_alarm = 10
        dev.interval_temperature = 15

        my_tree['bus.0']['10.345678.90'] = dt
        await ow.scan_now()
        my_tree['bus.0']['alarm']['10.345678.90'] = dt
        await trio.sleep(12) # allow alarm poll to trigger
        assert int(dt['temphigh']) == 20
        assert int(dt['templow']) == 11
        assert dev.alarm_temperature == 12.5
        await trio.sleep(5) # allow temperature poll to trigger

