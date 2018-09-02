"""
Access to an owserver.
"""

import trio
from collections import deque
import struct

from .event import ServerConnected, ServerDisconnected
from .event import BusAdded, BusDeleted
from .protocol import NOPMsg, DirMsg, AttrGetMsg, AttrSetMsg
from .bus import Bus

import logging
logger = logging.getLogger(__name__)

class Server:
    """\
        This 
    """
    MAX_LENGTH=10000

    def __init__(self, service, host="localhost", port=4304):
        self.service = service
        self.host = host
        self.port = port
        self.stream = None
        self.requests = deque()
        self._wlock = trio.Lock()
        self._buf = b''
        self._scan_task = None
        self._buses = dict()  # path => bus

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

    async def _read_buf(self, nbytes):
        while len(self._buf) < nbytes:
            self._buf += await self.stream.receive_some(4096)
        res = self._buf[:nbytes]
        self._buf = self._buf[nbytes:]
        return res

    async def _read_msg(self):
        while True:
            hdr = await self._read_buf(24)
            version, payload_len, ret_value, format_flags, data_len, offset = struct.unpack('!6i', hdr)
            if offset & 0x8000:
                offset = 0
            elif offset != 0:
                import pdb;pdb.set_trace()
            if version != 0:
                raise RuntimeError(f"Wrong version: {version}")
            if payload_len == -1 and data_len == 0 and offset == 0:
                raise RuntimeError("Server is busy?")
            if payload_len > self.MAX_LENGTH:
                raise RuntimeError(f"Server tried to send too much: {payload_len}")
            if payload_len == 0:
                data_len = 0
            data = await self._read_buf(payload_len)
            logger.debug("OW recv %x %x %x %x %x %x %s",version, payload_len, ret_value, format_flags, data_len, offset, repr(data))
            data = data[offset:data_len]
            yield ret_value, data
            
    async def _reader(self, task_status=trio.TASK_STATUS_IGNORED):
        with trio.open_cancel_scope() as scope:
            task_status.started(scope)
            async for res,data in self._read_msg():
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
            await msg.write(self.stream)
            self.requests.append(msg)
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
                try:
                    old_paths.remove(d)
                except KeyError:
                    pass
                buses = await bus._scan_one()
                old_paths -= buses
        for p in old_paths:
            bus = self._buses.pop(p, None)
            if bus is None:
                continue
            bus.delocate()


    async def start_scan(self, interval):
        self._scan_task = await self.service.add_task(self._scan, interval)

    async def attr_get(self, *path):
        return await self.chat(AttrGetMsg(path))

    async def attr_set(self, *path, value):
        return await self.chat(AttrSetMsg(path, value))

