import trio
from trio_owfs import OWFS
from trio_owfs.protocol import MessageProtocol, OWMsg
from async_generator import asynccontextmanager
from functools import partial

import logging
logger = logging.getLogger(__name__)

async def some_server(tree, msgs, socket):
    rdr = MessageProtocol(socket, is_server=True)
    logger.debug("START Server")
    msgs = iter(msgs)
    try:
        async for command, format_flags, data, offset in rdr:
            try:
                m = next(msgs)
            except StopIteration:
                raise RuntimeError("Unexpected command: %d %x %s %d" % (command, format_flags, repr(data), offset)) from None
            m.check(command, data)
            if command == OWMsg.nop:
                await rdr.write(0,format_flags,0)
            elif command == OWMsg.dirall:
                subtree = tree
                if data != b'':
                    for k in data.split(b'/'):
                        k = k.decode("utf-8")
                        subtree = subtree[k]
                res = []
                for k,v in subtree.items():
                    k = k.encode('utf-8')
                    if isinstance(v,dict):
                        k += b'/'
                    res.append(k)
                data = b','.join(res)+b'\0'
                await rdr.write(0,format_flags,0,data)
            else:
                raise RuntimeError("Unknown command: %d %x %s %d" % (command, format_flags, repr(data), offset))

    except Exception as exc:
        logger.exception(exc)
    finally:
        logger.debug("END Server")
        try:
            m = next(msgs)
        except StopIteration:
            pass
        else:
            raise RuntimeError("Message '%s' not seen",m)

class EventChecker:
    def __init__(self, events=[]):
        self.events = events[:]

    def add(self, event):
        self.events.push(event)

    async def __call__(self, ow, task_status=trio.TASK_STATUS_IGNORED):
        self.pos = 0
        try:
            with ow.events as ev:
                task_status.started()
                async for e in ev:
                    self.check_next(e)
        finally:
            self.check_last()

    def check_next(self, e):
        try:
            t = self.events[self.pos]
        except IndexError:
            raise RuntimeError("Unexpected event %s" % (e,))
        self.pos += 1
        if isinstance(e,t):
            pass
        elif type(e) == type(t):
            assert e == t
        else:
            raise RuntimeError("Want %s, got %s" % (t,e))

    def check_last(self):
        assert self.pos == len(self.events)

@asynccontextmanager
async def server(tree={}, msgs=(), events=None):
    async with OWFS() as ow:
        async with trio.open_nursery() as n:
            s = None
            try:
                server = await n.start(partial(trio.serve_tcp, host="127.0.0.1"), partial(some_server, tree, msgs), 0)
                if events is not None:
                    await n.start(events, ow)
                addr = server[0].socket.getsockname()

                s = await ow.add_server(*addr)
                yield ow
            finally:
                if s is not None:
                    await s.drop()
                await trio.sleep(0.1)
                n.cancel_scope.cancel()

