"""
Buses.
"""

from random import random
import anyio

from .device import NotADevice, split_id, NoLocationKnown
from .event import BusAdded, BusDeleted, DeviceAlarm

import logging
logger = logging.getLogger(__name__)


class Bus:
    """Describes one bus.
    """

    def __init__(self, server, *path):
        self.service = server.service
        self.server = server
        self.path = path

        self._buses = dict()  # subpath => bus
        self._devices = dict()  # id => device
        self._unseen = 0  # didn't find when scanning
        self._tasks = dict()  # polltype => task
        self._intervals = dict()

    def __repr__(self):
        return "<%s:%s %s>" % (self.__class__.__name__, self.server, '/' + '/'.join(self.path))

    def __eq__(self, x):
        x = getattr(x, 'path', x)
        return self.path == x

    def __hash__(self):
        return hash(self.path)

    @property
    def devices(self):
        """Iterate over the devices on this bus"""
        return list(self._devices.values())

    @property
    def buses(self):
        """Iterate over the sub.buses on this bus"""
        return list(self._buses.values())

    def delocate(self):
        """This bus can no longer be found"""
        if self._buses:
            for b in self.buses:
                b.delocate()
            self._buses = None
        if self._devices:
            for d in self.devices:
                d.delocate(bus=self)
            self._devices = None
        self.service.push_event(BusDeleted(self))

    @property
    def all_buses(self):
        yield self
        for b in self.buses:
            yield from b.all_buses

    def get_bus(self, *path):
        try:
            return self._buses[path]
        except KeyError:
            bus = Bus(self.server, *(self.path + path))
            self._buses[path] = bus
            self.service.push_event(BusAdded(bus))
            return bus

    async def _scan_one(self, polling=True):
        """Scan a single bus, plus all buses attached to it"""
        buses = set()
        res = await self.dir()
        old_devs = set(self._devices.keys())
        for d in res:
            try:
                split_id(d)  # only tests for conformity
            except NotADevice as err:
                logger.debug("Not a device: %s", err)
                continue
            dev = self.service.get_device(d)
            await self.service.ensure_struct(dev, server=self.server, maybe=True)
            if dev.bus is self:
                old_devs.remove(d)
            else:
                self.add_device(dev)
            dev._unseen = 0
            logger.debug("Found %s/%s", '/'.join(self.path), d)
            for b in dev.buses():
                buses.add(b)
                bus = self.get_bus(*b)
                buses.update(await bus._scan_one(polling=polling))

        for d in old_devs:
            dev = self._devices[d]
            if dev._unseen > 2:
                dev.delocate(self)
            else:
                dev._unseen += 1
        if polling:
            await self.update_poll()
        return buses

    async def update_poll(self):
        """Start all new polling jobs, terminate old ones"""
        items = set()
        intervals = dict()
        for dev in self.devices:
            for k in dev.polling_items():
                items.add(k)
                i = dev.polling_interval(k)
                if i is None:
                    continue
                oi = intervals.get(k, i)
                intervals[k] = min(oi, i)

        old_items = set(self._tasks.keys()) - items
        for x in old_items:
            j = self._jobs.pop(x)
            j.cancel()

        self._intervals.update(intervals)
        for x in items:
            if x not in self._tasks:
                self._tasks[x] = await self.service.add_task(self._poll, x)

    async def _poll(self, name):
        """Task to run a specific poll in the background"""
        while True:
            i = self._intervals[name] * (1+(random()-0.5)/20)
            logger.info("Delay %s for %f" % (name,i))
            await anyio.sleep(i)
            await self.poll(name)

    def add_device(self, dev):
        dev.locate(self)
        self._devices[dev.id] = dev

    def _del_device(self, dev):
        del self._devices[dev.id]

    def dir(self, *subpath):
        return self.server.dir(*(self.path+subpath))

    async def attr_get(self, *attr):
        """Read this attribute"""
        return await self.server.attr_get(*(self.path + attr))

    async def attr_set(self, *attr, value):
        """Write this attribute"""
        if self.server is None:
            raise NoLocationKnown(self)
        return await self.server.attr_set(*(self.path + attr), value=value)

    ### Support for polling and alarm handling

    async def poll(self, name):
        """Run one poll.

        This typically runs via a :meth:`_poll` task, started by :meth:`update_poll`.
        """
        try:
            p = getattr(self, 'poll_'+name)
        except AttributeError:
            for d in self.devices:
                p = getattr(d, 'poll_'+name, None)
                if p is not None:
                    await p()
        else:
            await p()

    async def poll_alarm(self):
        """Scan the 'alarm' subdirectory"""
        for dev in await self.dir("alarm"):
            dev = self.service.get_device(dev)
            self.add_device(dev)
            await dev.poll_alarm()
            self.service.push_event(DeviceAlarm(dev))

    async def _poll_simul(self, name, delay):
        """Write to a single 'simultaneous' entry"""
        await self.attr_set("simultaneous", name, value=1)
        await anyio.sleep(delay)
        for dev in self.devices:
            try:
                p = getattr(dev, "poll_"+name)
            except AttributeError:
                pass
            else:
                await p()

    def poll_temperature(self):
        """Read all temperature data"""
        return self._poll_simul("temperature", 1.2)

