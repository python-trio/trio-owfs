"""
Buses.
"""

from .device import Device, NotADevice

class Bus:
    """Describes one bus.
    """
    def __init__(self, server, *path):
        self.service = server.service
        self.server = server
        self.path = path

        self._buses = dict()  # subpath => bus
        self._devices = dict()  # id => device

    def __repr__(self):
        return "<%s:%s %s>" % (self.__class__.__name__,self.server, '/'+'/'.join(self.path))

    def delocate(self):
        """The bus can no longer be found"""
        if self._buses:
            for b in list(self._buses.values()):
                self.service.delocate(b)
            self._buses = None
        if self._devices:
            for d in list(self._devices.values()):
                d.delocate(self)
            self._devices = None
        self.service._del_bus(self)

    async def _scan_one(self):
        buses = set()
        for d in await self.dir():
            try:
                dev = Device(self.service, d)
            except NotADevice as err:
                print("No",err)
                continue
            print(self.path,d)
            self.add_device(dev)
            for b in dev.buses():
                buses.add(b)
                bus = self.server.get_bus(b)
                buses.update(await bus._scan_one())
        return buses

    def add_device(self, dev):
        self.service.add_device(dev, self)
        self._devices[dev.id] = dev

    def dir(self):
        return self.server.dir(*self.path)

    async def scan(self):
        pass
