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

