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
from .structs import structs

import logging
logger = logging.getLogger(__name__)

# We can just use 'async def test_*' to define async tests.
# This also uses a virtual clock fixture, so time passes quickly and
# predictably.

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
    async with server(tree=my_tree) as ow: # , polling=True, events=e1) as ow:
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

