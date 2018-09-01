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
    Bus = attr.ib()

@attr.s
class BusDeleted(BusEvent):
    """The Bus has been deleted"""
    Bus = attr.ib()

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
