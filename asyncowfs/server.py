"""
Access to an owserver.
"""

import anyio
from anyio.exceptions import IncompleteRead,ClosedResourceError
from collections import deque
from random import random
from typing import Union
from functools import partial
from concurrent.futures import CancelledError

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
        self._wqueue = anyio.create_queue(100)
        self._read_task = None
        self._write_task = None
        self._scan_task = None
        self._buses = dict()  # path => bus
        self._scan_lock = anyio.create_lock()
        self._scan_args = {}

    async def get_bus(self, *path):
        """Return the bus at this path. Allocate new if not existing."""
        try:
            return self._buses[path]
        except KeyError:
            bus = Bus(self, *path)
            self._buses[bus.path] = bus
            await self.service.push_event(BusAdded(bus))
            return bus

    def __repr__(self):
        return "<%s:%s:%d %s>" % (
            self.__class__.__name__, self.host, self.port, "OK" if self.stream else "closed"
        )

    async def _reader(self, val):
        async with anyio.open_cancel_scope() as scope:
            await val.set(scope)
            it = self._msg_proto.__aiter__()
            while True:
                try:
                    async with anyio.fail_after(15):
                        res, data = await it.__anext__()
                except ServerBusy as exc:
                    logger.info("Server %s busy", self.host)
                    msg = self.requests.popleft()
                    if not msg.cancelled:
                        await self._wqueue.put(msg)

                except (StopAsyncIteration, TimeoutError, IncompleteRead, ConnectionResetError, ClosedResourceError):
                    await self._reconnect()
                    it = self._msg_proto.__aiter__()
                else:
                    msg = self.requests.popleft()
                    await msg.process_reply(res, data, self)
                    if not msg.done():
                        self.requests.appendleft(msg)

    async def _reconnect(self):
        await self.service.push_event(ServerDisconnected(self))
        if self._write_task is not None:
            await self._write_task.cancel()
            self._write_task = None
        if self._scan_task is not None:
            await self._scan_task.cancel()
            self._scan_task = None
        await self.stream.close()
        self.stream = None

        backoff = 0.2

        while True:
            try:
                self.stream = await anyio.connect_tcp(self.host, self.port)
            except OSError:
                await anyio.sleep(backoff)
                if backoff < 10:
                    backoff *= 1.5
            except BaseException as exc:
                logger.exception("Owch")
            else:
                self._msg_proto = MessageProtocol(self, is_server=False)
                # re-send messages, but skip those that have been cancelled
                logger.warning("Server %s restarting", self.host)
                ml, self.requests = list(self.requests), deque()
                self._wqueue = anyio.create_queue(100)
                await self.service.push_event(ServerConnected(self))
                v_w = ValueEvent()
                await self.service.nursery.spawn(self._writer, v_w)
                self._write_task = await v_w.get()
                for msg in ml:
                    if not msg.cancelled:
                        await self._wqueue.put(msg)
                await self.service.nursery.spawn(partial(self.start_scan,**self._scan_args))
                return

    async def start(self, background=None):
        """Start talking. Returns when the connection is established,
        raises an error if that's not possible.

        TODO: if the connection subsequently drops, it's re-established
        transparently.
        """
        if background:
            await self.service.add_task(self._start)
            return
            
        if self.stream is not None:
            if background is False:
                return
            raise RuntimeError("already open")
        self.stream = await anyio.connect_tcp(self.host, self.port)
        self._msg_proto = MessageProtocol(self, is_server=False)
        await self.service.push_event(ServerConnected(self))
        v_w = ValueEvent()
        v_r = ValueEvent()
        await self.service.nursery.spawn(self._writer, v_w)
        await self.service.nursery.spawn(self._reader, v_r)
        self._write_task = await v_w.get()
        self._read_task = await v_r.get()

        try:
            await self.chat(NOPMsg(), fail=True)
        except BaseException:
            await self.aclose()
            raise

    async def _start(self):
        # try to start repeatedly
        dly = 0.2
        while True:
            try:
                await self.start(background=False)
            except ConnectionRefusedError as exc:
                logger.warning("Connection to %s:%s failed, will retry",
                        self.host,self.port)
            else:
                await self.start_scan(**self._scan_args)
                return
            dly *= 1.5
            if dly > 10:
                dly = 10
            await anyio.sleep(dly)

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
        except BaseException as exc:
            await msg.cancel()
            raise

    async def _writer(self, val):
        async with anyio.open_cancel_scope() as scope:
            await val.set(scope)
            while True:
                try:
                    async with anyio.fail_after(10):
                        msg = await self._wqueue.get()
                except TimeoutError:
                    msg = NOPMsg()

                self.requests.append(msg)
                try:
                    await msg.write(self._msg_proto)
#                except trio.ClosedResourceError:
#                    # will get restarted by .reconnect()
#                    return
                except EnvironmentError as err:
                    logger.warning("Write error: %r", err)
                    return  # will be noticed by the reader
                except IncompleteRead:
                    await self.stream.close()
                    return  # wil be restarted by the reader
                except BaseException:
                    async with anyio.open_cancel_scope(shield=True):
                        await self.aclose()
                    raise

    async def drop(self):
        """Stop talking and delete yourself"""
        try:
            await self.aclose()
        finally:
            await self.service._del_server(self)

    async def aclose(self):
        if self._scan_task is not None:
            await self._scan_task.cancel()
            self._scan_task = None
        if self._write_task is not None:
            await self._write_task.cancel()
            self._write_task = None
        if self._read_task is not None:
            await self._read_task.cancel()
            self._read_task = None

        if self.stream is None:
            return

        try:
            await self.stream.close()
        finally:
            self.stream = None
            await self.service.push_event(ServerDisconnected(self))

        for b in list(self._buses.values()):
            await b.delocate()
        self._buses = None
        for m in self.requests:
            await m.cancel()

    @property
    def all_buses(self):
        for b in list(self._buses.values()):
            yield from b.all_buses

    async def dir(self, *path):
        return await self.chat(DirMsg(path))

    async def _scan(self, interval, initial_interval, polling, random=0):
        if not initial_interval:
            initial_interval = interval
        # 5% variation, to prevent clustering
        if random:
            initial_interval *= 1+(random()-0.5)/random
        await anyio.sleep(initial_interval)

        while True:
            async with self._scan_lock:
                await self.scan_now(polling=polling)
            if not interval:
                return
            i = interval
            if random:
                i *= 1+(random()-0.5)/random
            await anyio.sleep(i)

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
        try:
            for d in await self.dir():
                if d.startswith("bus."):
                    bus = await self.get_bus(d)
                    bus._unseen = 0
                    try:
                        old_paths.remove(d)
                    except KeyError:
                        pass
                    buses = await bus._scan_one(polling=polling)
                    old_paths -= buses
        except CancelledError:
            return

        # step 2: deregister buses, if not seen often enough
        for p in old_paths:
            bus = self._buses.get(p, None)
            if bus is None:
                continue
            if bus._unseen > 2:
                await bus.delocate()
            else:
                bus._unseen += 1

    async def start_scan(self, scan: Union[float,None] = None,
            initial_scan: Union[float,bool] = True, polling = True,
            random: int = 0):
        """Scan this server.

        :param scan: Flag how often to re-scan the bus.
            None: don't scan at all
            >0: repeat in the background
        :param initial_scan: Flag when to initially scan the bus.
            False: don't.
            True: immediately, wait until complete.
            >0: return immediately, delay initial scan that many seconds.
        :type scan: :class:`float` or ``None``
        :type initial_scan: :class:`float` or :class:`bool`
        :param polling: Flag whether to start tasks for periodic polling
            (alarm handling, temperature, …). Defaults to ``True``.
        """
        self._scan_args = dict(scan=scan,initial_scan=initial_scan,polling=polling,random=random)
        if self.stream is None:
            return
        if not scan and not initial_scan:
            return
        if scan and scan < 1:
            raise RuntimeError("You can't scan that often.")
        if initial_scan is True:
            await self.scan_now(polling=polling)
            initial_scan = False
        if initial_scan or scan:
            self._scan_task = await self.service.add_task(self._scan, scan, initial_scan, polling, random)

    async def attr_get(self, *path):
        return await self.chat(AttrGetMsg(*path))

    async def attr_set(self, *path, value):
        return await self.chat(AttrSetMsg(*path, value=value))
