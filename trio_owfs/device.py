"""
Devices.
"""

import attr

from .event import DeviceLocated, DeviceNotFound

import logging
logger = logging.getLogger(__name__)

__all__ = ["Device"]

@attr.s
class NoLocationKnown(RuntimeError):
    device = attr.ib()

@attr.s
class NotADevice(RuntimeError):
    id = attr.ib()

dev_classes = dict()
def register(cls):
    dev_classes[cls.family] = cls

def split_id(id):
    try:
        a,b,c = (int(x, 16) for x in id.split('.'))
    except ValueError:
        raise NotADevice(id)
    return a,b,c

class Device:
    """Base class for devices.

    A device may or may not have a known location.
    """

    def __init__(self, service, id):
        logger.debug("NewDev %s",id)

    def __new__(cls, service, id):
        family, code, chksum = split_id(id)
        self = object.__new__(dev_classes.get(family, Device))

        self.id = id.upper()
        self.family = family
        self.code = code
        self.chksum = chksum

        self.service = service
        self.bus = None

        self._unseen = 0

        return self

    def __eq__(self, x):
        x = getattr(x,'id',x)
        return self.id == x

    def __hash__(self):
        return hash(self.id)

    def __repr__(self):
        return "<%s:%s @ %s>" % (self.__class__.__name__,self.id, self.bus)

    def buses(self):
        return set()

    def locate(self, bus):
        """The device has been seen here."""
        if self.bus is bus:
            return
        self.bus = bus
        self.service.push_event(DeviceLocated(self))

    def delocate(self, bus):
        """The device is no longer located here."""
        if self.bus is bus:
            self._delocate()

    def _delocate(self):
        self.bus._del_device(self)
        self.bus = None
        self.service.push_event(DeviceNotFound(self))

    async def attr_get(self, *attr):
        """Read this attribute"""
        if self.server is None:
            raise NoLocationKnown(self)
        return await self.server.attr_get(self.bus.path + (self.id,) + attr)

    async def attr_set(self, *attr, value):
        """Write this attribute"""
        if self.server is None:
            raise NoLocationKnown(self)
        return await self.server.attr_set(self.bus.path + (self.id,) + attr, value)

@register
class SwitchDevice(Device):
    family = 0x1F
    def buses(self):
        b = []
        b.append(self.bus.path+(self.id,"main"))
        b.append(self.bus.path+(self.id,"aux"))
        return b

    def delocate(self):
        s = self.bus.server
        for b in self.buses():
            b = s._buses[b]
            b.delocate()
        super().delocate(self)

@register
class TemperatureDevice(Device):
    family = 0x10

