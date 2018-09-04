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
    _did_setup = False

    def __init__(self, service, id):
        logger.debug("NewDev %s",id)

    def __new__(cls, service, id):
        family_id, code, chksum = split_id(id)

        cls = dev_classes.get(family_id)
        if cls is None:
            class cls(Device):
                family = family_id
            cls.__name__ = "Device_%02x" % (family_id,)
            dev_classes[family_id] = cls

        self = object.__new__(cls)

        self.id = id.upper()
        self.family = family_id
        self.code = code
        self.chksum = chksum

        self.service = service
        self.bus = None

        self._unseen = 0

        return self

    @classmethod
    async def setup_struct(cls, server):
        """Read the device's structural data from OWFS
        and add methods to access the fields"""

        @attr.s
        class SimpleGetter:
            name = attr.ib()
            typ = attr.ib()

            async def __get__(slf, self, cls):
                res = await self.attr_get(slf.name)
                if slf.typ in {'f','g','p','t'}:
                    res = float(res)
                elif slf.typ in {'i','u'}:
                    res = int(res)
                elif slf.typ == 'y':
                    res = bool(int(res))
                elif slf.typ == 'b':
                    pass
                else:
                    res = res.decode('utf-8')
                return res

        @attr.s
        class SimpleSetter:
            name = attr.ib()
            typ = attr.ib()

            def __get__(slf, self, cls):
                async def setter(self, typ, name, val):
                    if typ == 'b':
                        pass
                    elif typ == 'y':
                        val = b'1' if val else b'0'
                    else:
                        val = str(val).encode("utf-8")
                    await self.attr_set(name, value=val)
                return partial(setter, self, slf.name, slf.typ)

        if cls._did_setup is not False:
            return
        cls._did_setup = None
            
        try:
            fc = "%02X"%(cls.family)
            for d in await server.dir("structure",fc):
                try:
                    v = await server.attr_get("structure",fc,d)
                    v = v.decode("utf-8").split(",")
                    if v[3] in {'ro','rw'}:
                        setattr(cls, d, SimpleGetter(d,v[0]))
                    if v[3] in {'wo','rw'}:
                        setattr(cls, 'set'+d, SimpleSetter(d,v[0]))
                except Exception:
                    raise


        except BaseException:
            cls._did_setup = False
            raise
        else:
            cls._did_setup = True


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
        if self.bus is None:
            raise NoLocationKnown(self)
        return await self.bus.attr_get(*((self.id,) + attr))

    async def attr_set(self, *attr, value):
        """Write this attribute"""
        if self.bus is None:
            raise NoLocationKnown(self)
        return await self.bus.attr_set(*((self.id,) + attr), value=value)

@register
class SwitchDevice(Device):
    family = 0x1F
    def buses(self):
        b = []
        b.append(self.bus.path+(self.id,"main"))
        b.append(self.bus.path+(self.id,"aux"))
        return b

@register
class TemperatureDevice(Device):
    family = 0x10

    async def stop_alarm(self):
        t = await self.latesttemp
        if t > (await self.temphigh):
            await self.set_temphigh(int(t+2))
        if t < (await self.templow):
            await self.set_templow(int(t-1))
