# base implementation

import anyio
from functools import partial
try:
    from contextlib import asynccontextmanager
except ImportError:
    from async_generator import asynccontextmanager

from typing import Optional,Union

from .server import Server
from .device import Device
from .event import ServerRegistered, ServerDeregistered
from .event import DeviceAdded, DeviceDeleted
from .util import ValueEvent

import logging
logger = logging.getLogger(__name__)

__all__ = ["OWFS"]


class Service:
    """\
        This is the master class you use for communicating with OWFS.
        You typically start it thus::

            async def rdr(ow):
                async for evt in ow:
                    process(evt)

            async with OWFS() as ow:
                await ow.add_task(rdr, ow)
                s = await ow.add_server("localhost",4304")

        :param scan: time between directory scanning.
            None: do not scan repeatedly

        :param initial_scan: time to first scan
            False: no initial scal
            True: scan immediately, block before returning

        :param polling: flag whether to poll devices.
            Default: True.

        :param load_structs: Flag whether to generate accessors from OWFS data.
            Default: True
        """

    def __init__(self, nursery, scan: Union[float,None] = None, initial_scan: Union[float,bool] = True, load_structs: bool = True, polling: bool = True, random: int = 0):
        self.nursery = nursery
        self._servers = set()  # typ.MutableSet[Server]  # Server
        self._devices = dict()  # ID => Device
        self._tasks = set()  # typ.MutableSet[]  # actually their cancel scopes
        self._event_queue = None  # typ.Optional[anyio.Queue]
        self._random = random
        self._scan = scan
        self._initial_scan = initial_scan
        self._polling = polling
        self._load_structs = load_structs

    async def add_server(self, host: str, port: int = 4304, polling: Optional[bool] = None,
            scan: Union[float,bool,None] = None, initial_scan: Union[float,bool,None] = None,
            random: Optional[int] = None):
        """Add this server to the list.
        
        :param polling: if False, don't poll.
        :param scan: Override ``self._scan`` for this server.
        :param initial_scan: Override ``self._initial_scan`` for this server.
        """
        if scan is None:
            scan = self._scan
        if initial_scan is None:
            initial_scan = self._initial_scan
        if polling is None:
            polling = self._polling
        if random is None:
            random = self._random

        s = Server(self, host, port)
        await self.push_event(ServerRegistered(s))
        try:
            await s.start()
        except BaseException as exc:
            logger.error("Could not start %s:%s", host,port)
            await self.push_event(ServerDeregistered(s))
            raise
        self._servers.add(s)
        await s.start_scan(scan=scan, initial_scan=initial_scan, polling=polling, random=random)
        return s

    async def ensure_struct(self, dev, server=None, maybe=False):
        """
        Load a device's class's structure definition from any server.

        :param dev: The device whose class to set up
        :param server: Try this server, not all of them
        :param maybe: if set, don't load if ``load_structs`` is set

        """
        if maybe and not self._load_structs:
            return
        cls = type(dev)
        if cls._did_setup:
            return
        if server is not None:
            await cls.setup_struct(server)
        else:
            for s in list(self._servers):
                await cls.setup_struct(s)
                return

    async def get_device(self, id):
        """
        Return the :class:`anyio_owfs.device.Device` instance for the device
        with this ID. Create it if it doesn't exist (this will trigger a
        `DeviceAdded` event).
        """
        try:
            return self._devices[id]
        except KeyError:
            dev = Device(self, id)
            self._devices[dev.id] = dev
            await self.push_event(DeviceAdded(dev))
            return dev

    async def _add_task(self, val, proc, *args):
        async with anyio.open_cancel_scope() as scope:
            await val.set(scope)
            try:
                await proc(*args)
            finally:
                try:
                    self._tasks.remove(scope)
                except KeyError:
                    pass

    async def scan_now(self, polling=True):
        """
        Task to scan the whole system.
        
        :param polling: if False, do not add polling tasks
        """
        async with anyio.create_task_group() as n:
            for s in list(self._servers):
                await n.spawn(partial(s.scan_now, polling=polling))

    async def add_task(self, proc, *args):
        """
        Add a background task. It is auto-cancelled when the service ends.
        Alternately, this call returns its cancel scope.
        """
        val = ValueEvent()
        await self.nursery.spawn(self._add_task, val, proc, *args)
        scope = await val.get()
        self._tasks.add(scope)
        return scope

    async def push_event(self, event):
        if self._event_queue is not None:
            await self._event_queue.put(event)

    async def _del_server(self, s):
        self._servers.remove(s)
        await self.push_event(ServerDeregistered(s))

    async def _del_device(self, d):
        self._devices.remove(d)
        await self.push_event(DeviceDeleted(d))

    @property
    def devices(self):
        return self._devices.values()

    # context

    async def __aenter__(self):
        return self

    async def __aexit__(self, *tb):
        for s in list(self._servers):
            await s.drop()
        if self._event_queue is not None:
            await self._event_queue.put(None)
        for t in list(self._tasks):
            await t.cancel()

    # listen to events

    @property
    def events(self):
        class EventWrapper:
            async def __aenter__(slf):
                assert self._event_queue is None
                self._event_queue = anyio.create_queue(1000)  # bus events
                return slf

            async def __aexit__(slf, *tb):
                if tb[1] is None and not self._event_queue.empty():
                    async with anyio.open_cancel_scope(shield=True):
                        while not self._event_queue.empty():
                            evt = await self._event_queue.get()
                            if evt is not None:
                                logger.error("Unprocessed: %s",evt)
                self._event_queue = None

            def __aiter__(slf):
                return slf

            async def __anext__(slf):
                if self._event_queue is None:
                    raise StopAsyncIteration
                res = await self._event_queue.get()
                if res is None:
                    raise StopAsyncIteration
                return res

        return EventWrapper()


@asynccontextmanager
async def OWFS(**kwargs):
    async with anyio.create_task_group() as n:
        s = Service(n, **kwargs)
        async with s:
            yield s
