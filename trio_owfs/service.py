# base implementation

import trio
from async_generator import asynccontextmanager

from .server import Server
from .device import Device
from .event import ServerRegistered, ServerDeregistered
from .event import DeviceAdded, DeviceDeleted

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

        Parameters:

            scan: time between directory scans.
                0: only after connecting
                None: do not scan

        NB: trio-OWFS is opinionated. Device codes will contain checksums,
        temperature is in degC, pressure is in mbar.
        """

    def __init__(self, nursery, scan=0):
        self.nursery = nursery
        self._servers = set()  # typ.MutableSet[Server]  # Server
        self._devices = dict()  # ID => Device
        self._tasks = set()  # typ.MutableSet[]  # actually their cancel scopes
        self._event_queue = None  # typ.Optional[trio.Queue]
        self.scan = scan

    async def add_server(self, host: str, port: int = 4304):
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
            if self.scan is not None:
                await s.start_scan(self.scan)
        return s

    async def ensure_struct(self, dev):
        cls = type(dev)
        if cls._did_setup:
            return
        for s in list(self._servers):
            await cls.setup_struct(s)
            return

    def add_device(self, dev, bus=None):
        """Add a device, possibly seen on a bus."""
        self._devices[dev.id] = dev
        self.push_event(DeviceAdded(dev))
        if bus is not None:
            dev.locate(bus)

    def get_device(self, id):
        try:
            return self._devices[id]
        except KeyError:
            dev = Device(self, id)
            self.add_device(dev)
            return dev

    async def _add_task(self, proc, *args, task_status=trio.TASK_STATUS_IGNORED):
        with trio.open_cancel_scope() as scope:
            task_status.started(scope)
            try:
                await proc(*args)
            finally:
                try:
                    self._tasks.remove(scope)
                except KeyError:
                    pass

    async def scan_now(self, task_status=trio.TASK_STATUS_IGNORED):
        """Scan the whole system."""
        task_status.started()
        async with trio.open_nursery() as n:
            for s in list(self._servers):
                await n.start(s.scan_now)

    async def add_task(self, proc, *args):
        """
        Add a background task. It is auto-cancelled when the service ends.
        Alternately, this call returns its cancel scope.
        """
        scope = await self.nursery.start(self._add_task, proc, *args)
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
                await trio.sleep(0)
        for t in list(self._tasks):
            t.cancel()

    # listen to events

    @property
    def events(self):
        class EventWrapper:
            def __enter__(slf):
                assert self._event_queue is None
                self._event_queue = trio.Queue(1000)  # bus events
                return slf

            def __exit__(slf, *tb):
                if tb[1] is None:
                    assert self._event_queue.is_empty()
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
async def OWFS(**kwargs):
    async with trio.open_nursery() as n:
        s = Service(n, **kwargs)
        async with s:
            yield s
