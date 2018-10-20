# base implementation

import anyio
from functools import partial
from async_generator import asynccontextmanager
from async_generator import async_generator, yield_

from typing import Optional

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

            0: only after connecting (default)
            None: do not scan at all

        """

    def __init__(self, nursery, scan: Optional[int] = 0, load_structs: bool = True, polling: bool = True):
        self.nursery = nursery
        self._servers = set()  # typ.MutableSet[Server]  # Server
        self._devices = dict()  # ID => Device
        self._tasks = set()  # typ.MutableSet[]  # actually their cancel scopes
        self._event_queue = None  # typ.Optional[anyio.Queue]
        self.scan = scan
        self.polling = polling
        self._load_structs = load_structs

    async def add_server(self, host: str, port: int = 4304, polling: Optional[bool] = None,
            scan = -1):
        """Add this server to the list.
        
        :param polling: if False, don't poll.
        :param scan: Override ``self.scan``.
        """
        if scan == -1:
            scan = self.scan
        if polling is None:
            polling = self.polling

        s = Server(self, host, port)
        self.push_event(ServerRegistered(s))
        try:
            await s.start()
        except BaseException as exc:
            logger.exception("Could not start")
            self.push_event(ServerDeregistered(s))
            raise
        else:
            self._servers.add(s)
            await s.start_scan(scan, polling=polling)
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

    def get_device(self, id):
        """
        Return the :class:`anyio_owfs.device.Device` instance for the device
        with this ID. Create it if it doesn't exist (this will trigger a .
        """
        try:
            return self._devices[id]
        except KeyError:
            dev = Device(self, id)
            self._devices[dev.id] = dev
            self.push_event(DeviceAdded(dev))
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

    def push_event(self, event):
        if self._event_queue is not None:
            self._event_queue.put_nowait(event)

    def _del_server(self, s):
        self._servers.remove(s)
        self.push_event(ServerDeregistered(s))

    def _del_device(self, d):
        self._devices.remove(d)
        self.push_event(DeviceDeleted(d))

    # context

    async def __aenter__(self):
        return self

    async def __aexit__(self, *tb):
        for s in list(self._servers):
            await s.drop()
        if self._event_queue is not None:
            while not self._event_queue.empty():
                await anyio.sleep(0)
        for t in list(self._tasks):
            t.cancel()

    # listen to events

    @property
    def events(self):
        class EventWrapper:
            def __enter__(slf):
                assert self._event_queue is None
                self._event_queue = anyio.create_queue(1000)  # bus events
                return slf

            def __exit__(slf, *tb):
                if tb[1] is None:
                    assert self._event_queue.empty()
                self._event_queue.put_nowait(None)
                self._event_queue = None

            def __aiter__(slf):
                return slf

            async def __anext__(slf):
                res = await self._event_queue.get()
                if res is None:
                    raise StopAsyncIteration
                return res

        return EventWrapper()


@asynccontextmanager
@async_generator
async def OWFS(**kwargs):
    async with anyio.create_task_group() as n:
        s = Service(n, **kwargs)
        async with s:
            await yield_(s)
