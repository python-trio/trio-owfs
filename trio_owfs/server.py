"""
Access to an owserver.
"""

import trio
from collections import deque
import struct

from .event import ServerConnected, ServerDisconnected
from .event import BusAdded, BusDeleted
from .protocol import NOPMsg, DirMsg, AttrGetMsg, AttrSetMsg, MessageProtocol, ServerBusy, Retry
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
        self._connect_lock = trio.Lock()
        self._wqueue = trio.Queue(10)
        self._wmsg = None
        self._scan_task = None
        self._buses = dict()  # path => bus
        self._scan_done = trio.Event()
        self._scan_lock = trio.Lock()

    @property
    def scan_done(self):
        return self._scan_done.wait()

    def get_bus(self, *path):
        """Return the bus at this path. Allocate new if not existing."""
        try:
            return self._buses[path]
        except KeyError:
            bus = Bus(self, *path)
            self._buses[bus.path] = bus
            self.service.push_event(BusAdded(bus))
            return bus

    def __repr__(self):
        return "<%s:%s:%d %s>" % (self.__class__.__name__, self.host, self.port, "OK" if self.stream else "closed")

    async def _reader(self, task_status=trio.TASK_STATUS_IGNORED):
        with trio.open_cancel_scope() as scope:
            task_status.started(scope)
            while True:
                it = self._msg_proto.__aiter__()
                while True:
                    try:
                        with trio.fail_after(15):
                            res,data = await it.__anext__()
                    except ServerBusy as exc:
                        msg = self.requests.popleft()
                        msg.process_error(exc)
                    except (StopAsyncIteration,trio.TooSlowError,trio.BrokenStreamError):
                        await self._reconnect(from_reader=True)
                        break
                    except trio.ClosedResourceError:
                        return # exiting
                    else:
                        msg = self.requests.popleft()
                        msg.process_reply(res,data, self)
                        if not msg.done():
                            self.requests.appendleft(msg)

    async def _reconnect(self, from_reader=False):
        if self._connect_lock.locked():
            async with self._connect_lock:
                return
        async with self._connect_lock:
            self.service.push_event(ServerDisconnected(self))
            self._write_scope.cancel()
            self._write_scope = None
            if not from_reader:
                self._read_scope.cancel()
                self._read_scope = None
            await self.stream.aclose()
            backoff = 0.5
            while True:
                try:
                    self.stream = await trio.open_tcp_stream(self.host, self.port)
                except OSError:
                    await trio.sleep(backoff)
                    if backoff < 10:
                        backoff *= 1.5
                else:
                    self._msg_proto = MessageProtocol(self.stream, is_server=False)
                    # re-send messages, but skip those that have been cancelled
                    ml,self.requests = list(self.requests),deque()
                    for msg in ml:
                        if not msg.cancelled:
                            self.requests.append(msg)
                            await msg.write(self._msg_proto)
                    self.service.push_event(ServerConnected(self))
                    self._write_scope = await self.service.nursery.start(self._writer)
                    if not from_reader:
                        self._read_scope = await self.service.nursery.start(self._reader)
                    return

    async def start(self):
        """Start talking. Returns when the connection is established,
        raises an error if not possible.
        
        TODO: if the connection subsequently drops, it's re-established
        transparently.
        """
        async with self._connect_lock:
            if self.stream is not None:
                raise RuntimeError("already open")
            self.stream = await trio.open_tcp_stream(self.host, self.port)
            self._msg_proto = MessageProtocol(self.stream, is_server=False)
            self.service.push_event(ServerConnected(self))
            self._write_scope = await self.service.nursery.start(self._writer)
            self._read_scope = await self.service.nursery.start(self._reader)
        try:
            await self.chat(NOPMsg(), fail=True)
        except BaseException:
            await self.aclose()
            raise

    async def setup_struct(self, dev):
        await dev.setup_struct(self)

    async def chat(self, msg, fail=False):
        backoff = 0.1
        await self._wqueue.put(msg)
        try:
            while True:
                try:
                    res = await msg.get_reply()
                    return res
                except ServerBusy:
                    await trio.sleep(backoff)
                    if backoff < 2:
                        backoff *= 1.5
                    msg._resubmit()
                    await self._wqueue.put(msg)
                except Retry:
                    # The message has been repeated.
                    pass
        except BaseException:
            msg.cancel()
            raise

    async def _writer(self, task_status=trio.TASK_STATUS_IGNORED):
        with trio.open_cancel_scope() as scope:
            task_status.started(scope)
            backoff = 0.1
            while True:
                if self._wmsg is None:
                    try:
                        with trio.fail_after(10):
                            self._wmsg = await self._wqueue.get()
                    except trio.TooSlowError:
                        self._wmsg = NOPMsg()

                try:
                    await self._wmsg.write(self._msg_proto)
                except trio.ClosedResourceError:
                    # will get restarted by .reconnect()
                    return
                except trio.BrokenStreamError:
                    await self.stream.aclose()
                    return # wil be restarted by the reader
                else:
                    self.requests.append(self._wmsg)
                    self._wmsg = None


    async def drop(self):
        """Stop talking and delete yourself"""
        try:
            await self.aclose()
        finally:
            self.service._del_server(self)

    async def aclose(self):
        if self.stream is None:
            return
        try:
            await self.stream.aclose()
        finally:
            self.stream = None
            self.service.push_event(ServerDisconnected(self))

        if self._write_scope is not None:
            self._write_scope.cancel()
            self._write_scope = None
        if self._read_scope is not None:
            self._read_scope.cancel()
            self._read_scope = None

        for b in list(self._buses.values()):
            b.delocate()
        self._buses = None

    @property
    def all_buses(self):
        for b in list(self._buses.values()):
            yield from b.all_buses

    async def dir(self, *path):
        return await self.chat(DirMsg(path))

    async def _scan(self, interval):
        try:
            async with self._scan_lock:
                await self._scan_base()
            self._scan_done.set()
            if interval > 0:
                while True:
                    await trio.sleep(interval)
                    async with self._scan_lock:
                        await self._scan_base()
        finally:
            self._scan_task = None

    async def scan_now(self, task_status=trio.TASK_STATUS_IGNORED):
        task_status.started()
        if self._scan_lock.locked():
            # scan in progress: just wait for it to finish
            async with self._scan_lock:
                pass
        else:
            async with self._scan_lock:
                await self._scan_base()

    async def _scan_base(self):
        old_paths = set()

        # step 1: enumerate
        for d in await self.dir():
            if d.startswith("bus."):
                bus = self.get_bus(d)
                bus._unseen = 0
                try:
                    old_paths.remove(d)
                except KeyError:
                    pass
                buses = await bus._scan_one()
                old_paths -= buses

        # step 2: deregister buses, if not seen often enough
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
        return await self.chat(AttrGetMsg(*path))

    async def attr_set(self, *path, value):
        return await self.chat(AttrSetMsg(*path, value=value))

