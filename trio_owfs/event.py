"""
Events: whatever is happening on the bus
"""

import attr

class Event:
    """Base class for all events"""
    pass

class ServerEvent(Event):
    """Base class for all server-related events"""
    pass

@attr.s
class ServerRegistered(ServerEvent):
    """A new known server appears. The server is not yet connected!"""
    server = attr.ib()

@attr.s
class ServerConnected(ServerEvent):
    """We have connected to a server"""
    server = attr.ib()

@attr.s
class ServerDisconnected(ServerEvent):
    """We have disconnected from a server"""
    server = attr.ib()

@attr.s
class ServerDeregistered(ServerEvent):
    """This server is no longer known"""
    server = attr.ib()

class BusEvent(Event):
    """Base class for all Bus-related events"""
    pass

@attr.s
class BusAdded(BusEvent):
    """The Bus has been created. Its location is not yet known!"""
    bus = attr.ib()

class BusAdded_Path:
    """Not an event. Used for storing the bus path for comparisons in tests."""
    def __init__(self, *path):
        self.path = path
    def __repr__(self):
        return "<%s: %s>" % (self.__class__.__name__,'/'.join(self.path))
    def __eq__(self,x):
        if isinstance(x,BusAdded_Path):
            x=x.path
        elif isinstance(x,BusAdded):
            x=x.bus.path
        elif not isinstance(x,(list,tuple)):
            return False
        return self.path == x

@attr.s
class BusDeleted(BusEvent):
    """The Bus has been deleted"""
    bus = attr.ib()

class DeviceEvent(Event):
    """Base class for all device-related events"""
    pass

@attr.s
class DeviceAdded(DeviceEvent):
    """The device has been created. Its location is not yet known!"""
    device = attr.ib()

@attr.s
class DeviceDeleted(DeviceEvent):
    """The device has been deleted"""
    device = attr.ib()

@attr.s
class DeviceLocated(DeviceEvent):
    """The device has been found"""
    device = attr.ib()

    @property
    def server(self):
        return self.device.server
    @property
    def path(self):
        return self.device.path

@attr.s
class DeviceNotFound(DeviceEvent):
    """The device's location is no longer known"""
    device = attr.ib()
