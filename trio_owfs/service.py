# base implementation

import trio
from async_generator import asynccontextmanager
import typing as typ

from .server import Server
from .event import ServerRegistered, ServerDeregistered

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

        You can listen to bus events::

        
        NB: trio-OWFS is opinionated. Device codes will contain checksums, 
        temperature is in degC, pressure is in mbar.
        """

    def __init__(self, nursery):
        self.nursery = nursery
        self._servers = set()  # typ.MutableSet[Server]  # Server
        self._tasks = set()  # typ.MutableSet[]  # actually their cancel scopes
        self._event_queue = None  # typ.Optional[trio.Queue]

    async def add_server(self, host:str, port:int=4304):
        s = Server(self, host, port)
        self.push_event(ServerRegistered(s))
        try:
            await s.start()
        except BaseException:
            self.push_event(ServerDeregistered(s))
            raise
        else:
            self._servers.add(s)

    async def _add_task(self, proc, *args, task_status=trio.TASK_STATUS_IGNORED):
        with trio.open_cancel_scope() as scope:
            task_status.started(scope)
            try:
                await proc(*args)
            finally:
                self._tasks.remove(scope)

    async def add_task(self, proc, *args):
        """
        Add a background task. It is auto-cancelled when the service ends.
        Alternately, this call returns its cancel scope.
        """
        scope = await self.nursery.start(self._add_task, proc, *args)
        self._tasks.add(scope)
        return scope

    def push_event(self, event):
        self._event_queue.put_nowait(event)

    def _del_server(self, s):
        self._servers.remove(s)
        self.push_event(ServerDeregistered(s))

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

    def __aiter__(self):
        if self._event_queue is None:
            self._event_queue = trio.Queue(1000)  # bus events
        return self

    async def __anext__(self):
        return await self._event_queue.get()

@asynccontextmanager
async def OWFS():
    async with trio.open_nursery() as n:
        s = Service(n)
        async with s:
            yield s

