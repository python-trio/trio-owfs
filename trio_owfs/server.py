"""
Access to an owserver.
"""

import anyio
from anyio.exceptions import IncompleteRead
from collections import deque
from random import random

from .event import ServerConnected, ServerDisconnected
from .event import BusAdded
from .protocol import NOPMsg, DirMsg, AttrGetMsg, AttrSetMsg, MessageProtocol, ServerBusy, Retry
from .bus import Bus
from .util import ValueEvent

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
        self._wlock = anyio.create_lock()
        self._connect_lock = anyio.create_lock()
        self._wqueue = anyio.create_queue(10)
        self._wmsg = None
        self._scan_task = None
        self._buses = dict()  # path => bus
        self._scan_lock = anyio.create_lock()

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
        return "<%s:%s:%d %s>" % (
            self.__class__.__name__, self.host, self.port, "OK" if self.stream else "closed"
        )

    async def _reader(self, val):
        async with anyio.open_cancel_scope() as scope:
            await val.set(scope)
            while True:
                it = self._msg_proto.__aiter__()
                while True:
                    try:
                        async with anyio.fail_after(15):
                            res, data = await it.__anext__()
                    except ServerBusy as exc:
                        msg = self.requests.popleft()
                        await msg.process_error(exc)
                    except (StopAsyncIteration, TimeoutError, IncompleteRead, ConnectionResetError):
                        await self._reconnect(from_reader=True)
                        break
#                    except trio.ClosedResourceError:
#                        return  # exiting
                    else:
                        msg = self.requests.popleft()
                        await msg.process_reply(res, data, self)
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
            self.stream.close()
            backoff = 0.5
            while True:
                try:
                    self.stream = await anyio.connect_tcp(self.host, self.port)
                except OSError:
                    await anyio.sleep(backoff)
                    if backoff < 10:
                        backoff *= 1.5
                else:
                    self._msg_proto = MessageProtocol(self.stream, is_server=False)
                    # re-send messages, but skip those that have been cancelled
                    ml, self.requests = list(self.requests), deque()
                    for msg in ml:
                        if not msg.cancelled:
                            self.requests.append(msg)
                            await msg.write(self._msg_proto)
                    self.service.push_event(ServerConnected(self))
                    v_w = ValueEvent()
                    await self.service.nursery.spawn(self._writer, v_w)
                    self._write_scope = await v_w.get()
                    if not from_reader:
                        v_r = ValueEvent()
                        await self.service.nursery.spawn(self._reader, v_r)
                        self._read_scope = await v_r.get()
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
            self.stream = await anyio.connect_tcp(self.host, self.port)
            self._msg_proto = MessageProtocol(self.stream, is_server=False)
            self.service.push_event(ServerConnected(self))
            v_w = ValueEvent()
            v_r = ValueEvent()
            await self.service.nursery.spawn(self._writer, v_w)
            await self.service.nursery.spawn(self._reader, v_r)
            self._write_scope = await v_w.get()
            self._read_scope = await v_r.get()
        try:
            await self.chat(NOPMsg(), fail=True)
        except BaseException:
            self.close()
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
                    await anyio.sleep(backoff)
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

    async def _writer(self, val):
        async with anyio.open_cancel_scope() as scope:
            await val.set(scope)
            while True:
                if self._wmsg is None:
                    try:
                        async with anyio.fail_after(10):
                            self._wmsg = await self._wqueue.get()
                    except TimeoutError:
                        self._wmsg = NOPMsg()

                self.requests.append(self._wmsg)
                try:
                    await self._wmsg.write(self._msg_proto)
#                except trio.ClosedResourceError:
#                    # will get restarted by .reconnect()
#                    return
                except IncompleteRead:
                    self.stream.close()
                    return  # wil be restarted by the reader
                else:
                    self._wmsg = None

    async def drop(self):
        """Stop talking and delete yourself"""
        try:
            self.close()
        finally:
            self.service._del_server(self)

    def close(self):
        if self.stream is None:
            return
        try:
            self.stream.close()
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

    async def _scan(self, interval, polling):
        try:
            while True:
                # 5% variation, to prevent clustering
                await anyio.sleep(interval*(1+(random()-0.5)/10))
                async with self._scan_lock:
                    await self._scan_base(polling=polling)
        finally:
            self._scan_task = None

    async def scan_now(self, polling=True):
        if self._scan_lock.locked():
            # scan in progress: just wait for it to finish
            async with self._scan_lock:
                pass
        else:
            async with self._scan_lock:
                await self._scan_base(polling=polling)

    async def _scan_base(self, polling=True):
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
                buses = await bus._scan_one(polling=polling)
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

    async def start_scan(self, interval, polling=True):
        """Scan this server.

        :param interval: Flag how often to re-scan the bus.
            None: don't scan at all, return immediately.
            Zero: scan once, return after scan is complete.
            >0: return after the first scan, but also start a background
            tasks that re-scans every ``interval`` seconds
        :type interval: :class:`int` or ``None``
        :param polling: Flag whether to start tasks for periodic polling
            (alarm handling, temperature, …). Defaults to ``True``.
        """
        if interval is None:
            return
        await self.scan_now(polling=polling)
        if interval > 0:
            self._scan_task = await self.service.add_task(self._scan, interval, polling)

    async def attr_get(self, *path):
        return await self.chat(AttrGetMsg(*path))

    async def attr_set(self, *path, value):
        return await self.chat(AttrSetMsg(*path, value=value))
