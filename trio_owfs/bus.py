"""
Buses.
"""

from .device import Device, NotADevice, split_id
from .event import BusAdded, BusDeleted

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

    def __repr__(self):
        return "<%s:%s %s>" % (self.__class__.__name__, self.server, '/' + '/'.join(self.path))

    def __eq__(self, x):
        x = getattr(x, 'path', x)
        return self.path == x

    def __hash__(self):
        return hash(self.path)

    def delocate(self):
        """This bus can no longer be found"""
        if self._buses:
            for b in list(self._buses.values()):
                b.delocate()
            self._buses = None
        if self._devices:
            for d in list(self._devices.values()):
                d.delocate(bus=self)
            self._devices = None
        self.service.push_event(BusDeleted(self))

    @property
    def all_buses(self):
        yield self
        for b in self._buses.values():
            yield from b.all_buses

    def get_bus(self, *path):
        try:
            return self._buses[path]
        except KeyError:
            bus = Bus(self.server, *(self.path + path))
            self._buses[path] = bus
            self.service.push_event(BusAdded(bus))
            return bus

    async def _scan_one(self):
        buses = set()
        res = await self.dir()
        old_devs = set(self._devices.keys())
        for d in res:
            try:
                ids = split_id(d)
            except NotADevice as err:
                logger.debug("Not a device: %s", err)
                continue
            dev = self.service.get_device(d)
            if dev.bus is self:
                old_devs.remove(d)
            else:
                self.add_device(dev)
            dev._unseen = 0
            logger.debug("Found %s/%s", '/'.join(self.path), d)
            self.add_device(dev)
            for b in dev.buses():
                buses.add(b)
                bus = self.get_bus(*b)
                buses.update(await bus._scan_one())

        for d in old_devs:
            dev = self._devices[d]
            if dev._unseen > 2:
                dev.delocate(self)
            else:
                dev._unseen += 1
        return buses

    def add_device(self, dev):
        dev.locate(self)
        self._devices[dev.id] = dev

    def _del_device(self, dev):
        del self._devices[dev.id]

    def dir(self):
        return self.server.dir(*self.path)

    async def scan(self):
        pass

    async def attr_get(self, *attr):
        """Read this attribute"""
        return await self.server.attr_get(*(self.path + attr))

    async def attr_set(self, *attr, value):
        """Write this attribute"""
        if self.server is None:
            raise NoLocationKnown(self)
        return await self.server.attr_set(*(self.path + attr), value=value)
