"""
Access to an owserver.
"""

import trio
from collections import deque
import struct

from .event import ServerConnected, ServerDisconnected
from .event import BusAdded, BusDeleted
from .protocol import NOPMsg, DirMsg, AttrGetMsg, AttrSetMsg, MessageProtocol
from .bus import Bus

import logging
logger = logging.getLogger(__name__)

class Server:
    """\
        Encapsulate one server connection.
    """

    def __init__(self, service, host="localhost", port=4304):
        self.service = service
        self.host = host
        self.port = port
        self.stream = None
        self._msg_proto = None
        self.requests = deque()
        self._wlock = trio.Lock()
        self._scan_task = None
        self._buses = dict()  # path => bus
        self._scan_done = trio.Event()

    @property
    def scan_done(self):
        return self._scan_done.wait()

    def get_bus(self, path):
        """Return the bus at this path. Allocate new if not existing."""
        try:
            return self._buses[path]
        except KeyError:
            bus = Bus(self, *path)
            self._buses[bus.path] = bus
            self.service.push_event(BusAdded(bus))
            return bus

    def _del_bus(self, bus):
        del self._buses[bus.path]
        self.service.push_event(BusDeleted(bus))

    def __repr__(self):
        return "<%s:%s:%d %s>" % (self.__class__.__name__, self.host, self.port, "OK" if self.stream else "closed")

    async def _reader(self, task_status=trio.TASK_STATUS_IGNORED):
        with trio.open_cancel_scope() as scope:
            task_status.started(scope)
            async for res,data in self._msg_proto:
                msg = self.requests.popleft()
                msg.process_reply(res,data)
                if not msg.done():
                    self.requests.appendleft(msg)

    async def start(self):
        """Start talking. Returns when the connection is established,
        raises an error if not possible.
        
        TODO: if the connection subsequently drops, it's re-established
        transparently.
        """
        if self.stream is not None:
            raise RuntimeError("already open")
        self.stream = await trio.open_tcp_stream(self.host, self.port)
        self._msg_proto = MessageProtocol(self.stream, is_server=False)
        self.service.push_event(ServerConnected(self))
        self._read_scope = await self.service.nursery.start(self._reader)
        try:
            await self.chat(NOPMsg())
        except BaseException:
            self._read_scope.cancel()
            await self.aclose()
            raise
        
    async def chat(self, msg):
        async with self._wlock:
            await msg.write(self._msg_proto)
            self.requests.append(msg)
        with trio.fail_after(msg.timeout):
            return await msg.get_reply()

    async def drop(self):
        """Stop talking and delete yourself"""
        try:
            await self.aclose()
        finally:
            self.service._del_server(self)

    async def aclose(self):
        if self.stream is None:
            return
        if self._read_scope is not None:
            self._read_scope.cancel()
            self._read_scope = None
        try:
            await self.stream.aclose()
        finally:
            self.stream = None
            self.service.push_event(ServerDisconnected(self))

    async def dir(self, *path):
        return await self.chat(DirMsg(path))

    async def _scan(self, interval):
        try:
            await self._scan_base()
            self._scan_done.set()
            if interval > 0:
                while True:
                    await trio.sleep(interval)
                    await self._scan_base()
        finally:
            self._scan_task = None

    async def _scan_base(self):
        old_paths = set()
        for d in await self.dir():
            if d.startswith("bus."):
                bus = self._buses.get(d, None)
                if bus is None:
                    bus = Bus(self, d)
                bus._unseen = 0
                try:
                    old_paths.remove(d)
                except KeyError:
                    pass
                buses = await bus._scan_one()
                old_paths -= buses
        for p in old_paths:
            bus = self._buses.get(p, None)
            if bus is None:
                continue
            if bus._unseen > 2:
                bus.delocate()
            else:
                bus._unseen += 1


    async def start_scan(self, interval):
        self._scan_task = await self.service.add_task(self._scan, interval)

    async def attr_get(self, *path):
        return await self.chat(AttrGetMsg(path))

    async def attr_set(self, *path, value):
        return await self.chat(AttrSetMsg(path, value))

