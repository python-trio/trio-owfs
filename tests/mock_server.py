import trio
from trio_owfs import OWFS
from trio_owfs.protocol import MessageProtocol, OWMsg
from async_generator import asynccontextmanager
from functools import partial

import logging
logger = logging.getLogger(__name__)

def _chk(v):
    if v is None:
        return False
    v[0] += 1
    if v[0] >= len(v):
        v[0] = 1
    return v[v[0]]

async def some_server(tree, msgs, options, socket):
    rdr = MessageProtocol(socket, is_server=True)
    logger.debug("START Server")
    if msgs:
        midx = 0
        if isinstance(msgs[0],list):
            msgs.insert(0,0)
        if isinstance(msgs[0],int):
            midx = msgs[0]
            msgs[0] += 1
            msgs = msgs[msgs[0]]
        msgs = iter(msgs)
        mpos = 0

    def _end(msgs):
        nonlocal mpos
        if msgs:
            mpos += 1
            try:
                m = next(msgs)
            except StopIteration:
                pass
            else:
                raise RuntimeError("Message '%s' not seen (%d,%d)" % (m,midx,mpos))

    each_busy = options.get("busy_every",None)
    each_close = options.get("close_every",None)
    try:
        if _chk(each_close):
            _end(msgs)
            return
        async for command, format_flags, data, offset in rdr:
            if _chk(each_busy):
                await rdr.write(0,format_flags,0, data=None)
                continue
            if msgs:
                try:
                    m = next(msgs)
                except StopIteration:
                    raise RuntimeError("Unexpected command: %d %x %s %d" % (command, format_flags, repr(data), offset)) from None
                try:
                    m._check(command, data)
                except Exception:
                    raise RuntimeError("Message '%s' wrong seen (%d,%d)" % (m,midx,mpos))
            if _chk(each_close):
                _end(msgs)
                return
            if command == OWMsg.nop:
                await rdr.write(0,format_flags,0)
            elif command == OWMsg.dirall:
                subtree = tree
                path = []
                for k in data.split(b'/'):
                    if k == b'':
                        continue
                    path.append(k)
                    k = k.decode("utf-8")
                    subtree = subtree[k]
                res = []
                for k,v in subtree.items():
                    k = k.encode('utf-8')
                    res.append(k)
                if path:
                    path = b'/'+b'/'.join(path)+b'/'
                else:
                    path = b'/'
                data = b','.join(path+k for k in res)
                await rdr.write(0,format_flags,len(data),data+b'\0')
            else:
                raise RuntimeError("Unknown command: %d %x %s %d" % (command, format_flags, repr(data), offset))

        _end(msgs)
    finally:
        logger.debug("END Server")

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
                    logger.debug("Event %s",e)
                    self.check_next(e)
        except Exception as exc:
            self.check_last()
        else:
            self.check_last()
        # don't check on BaseException =Cancellation

    def check_next(self, e):
        try:
            t = self.events[self.pos]
        except IndexError:
            raise RuntimeError("Unexpected event %s" % (e,))
        self.pos += 1
        if type(e) == type(t):
            assert e == t, (e,t)
        elif isinstance(t,type) and isinstance(e,t):
            pass
        else:
            raise RuntimeError("Event #%d: Want %s, got %s" % (self.pos,t,e))

    def check_last(self):
        logger.debug("Event END")
        assert self.pos == len(self.events), (self.pos,self.events[self.pos])

@asynccontextmanager
async def server(tree={}, msgs=(), options={}, events=None):
    async with OWFS() as ow:
        async with trio.open_nursery() as n:
            s = None
            try:
                server = await n.start(partial(trio.serve_tcp, host="127.0.0.1"), partial(some_server, tree, msgs, options), 0)
                if events is not None:
                    await n.start(events, ow)
                addr = server[0].socket.getsockname()

                s = await ow.add_server(*addr)
                await s.scan_done
                yield ow
            finally:
                if s is not None:
                    await s.drop()
                await trio.sleep(0.1)
                n.cancel_scope.cancel()

