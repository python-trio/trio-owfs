import trio
from anyio.exceptions import ClosedResourceError
from asyncowfs import OWFS
from asyncowfs.protocol import MessageProtocol, OWMsg
from asyncowfs.error import OWFSReplyError, NoEntryError, IsDirError
try:
    from contextlib import asynccontextmanager
except ImportError:
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


async def _schk(v):
    if v is None:
        return
    v[0] += 1
    if v[0] >= len(v):
        v[0] = 1
    if v[v[0]] > 0:
        logger.debug("Slow reply %s", v[v[0]])
    await trio.sleep(v[v[0]])


class FakeMaster:
    def __init__(self, stream):
        self.stream = stream

async def some_server(tree, options, socket):
    rdr = MessageProtocol(FakeMaster(socket), is_server=True)
    logger.debug("START Server")

    each_busy = options.get("busy_every", None)
    each_close = options.get("close_every", None)
    each_slow = options.get("slow_every", None)
    try:
        if _chk(each_close):
            return
        async for command, format_flags, data, offset in rdr:
            try:
                if _chk(each_busy):
                    await rdr.write(0, format_flags, 0, data=None)
                await _schk(each_slow)
                if _chk(each_close):
                    return
                if command == OWMsg.nop:
                    await rdr.write(0, format_flags, 0)
                elif command == OWMsg.dirall:
                    data = data.rstrip(b'\0')
                    subtree = tree
                    path = []
                    for k in data.split(b'/'):
                        if k == b'':
                            continue
                        path.append(k)
                        k = k.decode("utf-8")
                        try:
                            subtree = subtree[k]
                        except KeyError:
                            raise NoEntryError(command, data)
                    res = []
                    for k, v in sorted(subtree.items()):
                        k = k.encode('utf-8')
                        res.append(k)
                    if path:
                        path = b'/' + b'/'.join(path) + b'/'
                    else:
                        path = b'/'
                    data = b','.join(path + k for k in res)
                    await rdr.write(0, format_flags, len(data), data + b'\0')
                elif command == OWMsg.read:
                    data = data.rstrip(b'\0')
                    res = tree
                    for k in data.split(b'/'):
                        if k == b'':
                            continue
                        k = k.decode("utf-8")
                        try:
                            res = res[k]
                        except KeyError:
                            raise NoEntryError(command, data)
                    if isinstance(res, dict):
                        raise IsDirError(command, data)
                    if not isinstance(res, bytes):
                        res = str(res).encode('utf-8')
                    await rdr.write(0, format_flags, len(res), res + b'\0')
                elif command == OWMsg.write:
                    val = data[-offset:].decode("utf-8")
                    data = data[:-offset]
                    data = data.rstrip(b'\0')
                    res = tree
                    last = None
                    for k in data.split(b'/'):
                        if k == b'':
                            continue
                        if last is not None:
                            try:
                                res = res[last]
                            except KeyError:
                                raise NoEntryError(command, data)
                        last = k.decode("utf-8")
                    assert last is not None
                    if last not in res:
                        raise NoEntryError(command, data)
                    res[last] = val
                    await rdr.write(0, format_flags, 0)
                else:
                    raise RuntimeError(
                        "Unknown command: %d %x %s %d" %
                        (command, format_flags, repr(data), offset)
                    )
            except OWFSReplyError as err:
                logger.info("Error: %s", err)
                await rdr.write(-err.err, format_flags)

    except (trio.BrokenResourceError, ClosedResourceError):
        await socket.aclose()
    finally:
        await socket.aclose()
        logger.debug("END Server")


class EventChecker:
    def __init__(self, events=[]):
        self.events = events[:]

    def add(self, event):
        self.events.push(event)

    async def __call__(self, ow, task_status=trio.TASK_STATUS_IGNORED):
        self.pos = 0
        try:
            async with ow.events as ev:
                task_status.started()
                async for e in ev:
                    logger.debug("Event %s", e)
                    self.check_next(e)
        except RuntimeError:
            raise
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
        if isinstance(t, type) and isinstance(e, t):
            pass
        elif not (t == e):
            raise RuntimeError("Wrong event: want %s but has %s" % (t, e))

    def check_last(self):
        logger.debug("Event END")
        if self.pos != len(self.events):
            raise RuntimeError("Superfluous event #%d: %s" % (self.pos, self.events[self.pos]))


@asynccontextmanager
async def server(tree={}, options={}, events=None, polling=False, scan=None, initial_scan=True, **kw):
    async with OWFS(**kw) as ow:
        async with trio.open_nursery() as n:
            s = None
            try:
                server = await n.start(
                    partial(trio.serve_tcp, host="127.0.0.1"),
                    partial(some_server, tree, options), 0
                )
                if events is not None:
                    await n.start(events, ow)
                addr = server[0].socket.getsockname()

                s = await ow.add_server(*addr, polling=polling, scan=scan, initial_scan=initial_scan)
                ow.test_server = s
                yield ow
            finally:
                ow.test_server = None
                with trio.CancelScope(shield=True):
                    if s is not None:
                        await s.drop()
                    await ow.push_event(None)
                    await trio.sleep(0.1)
                n.cancel_scope.cancel()

