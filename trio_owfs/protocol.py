# for message type classification see
# http://owfs.org/index.php?page=owserver-message-types
# and 'enum msg_classification' from module/owlib/src/include/ow_message.h

import attr
import struct
from .util import ValueEvent
from .error import _errors, GenericOWFSReplyError

import logging
logger = logging.getLogger(__name__)


class OWMsg:
    """Constants for the owserver api message types."""
    error = 0
    nop = 1
    read = 2
    write = 3
    dir = 4
    size = 5
    presence = 6
    dirall = 7
    get = 8
    dirallslash = 9
    getslash = 10


class OWFlag:
    cache = 0x1  # ?
    busret = 0x2  # enumeration includes bus names
    persist = 0x4  # use persistent connections
    alias = 0x8
    safemode = 0x10
    uncached = 0x20
    ownet = 0x100
    _offset = 0


class OWdevformat:
    fdi = 0
    fi = 1
    fdidc = 2
    fdic = 3
    fidc = 4
    fic = 5
    _offset = 24


class OWtempformat:
    celsius = 0
    fahrenheit = 1
    kelvin = 2
    rankine = 3
    _offset = 16


class OWpressureformat:
    mbar = 0
    atm = 1
    mmHg = 2
    inHg = 3
    psi = 4
    pa = 5
    _offset = 18


class ServerBusy(Exception):
    """Receiver error when the server signals it's busy"""
    pass


class Retry(Exception):
    """Sender resubmitted."""
    pass


class MessageProtocol:
    MAX_LENGTH = 9999

    def __init__(self, stream, is_server=False):
        self.stream = stream
        self.is_server = is_server
        self._buf = b''

    async def _read_buf(self, nbytes):
        while len(self._buf) < nbytes:
            more = await self.stream.receive_some(4096)
            if not more:
                raise StopAsyncIteration
            self._buf += more
        res = self._buf[:nbytes]
        self._buf = self._buf[nbytes:]
        return res

    def __aiter__(self):
        return self

    async def __anext__(self):
        hdr = await self._read_buf(24)
        version, payload_len, ret_value, format_flags, data_len, offset = struct.unpack('!6i', hdr)
        if offset & 0x8000:
            offset = 0
        elif offset != 0 and not is_server:
            import pdb
            pdb.set_trace()
        if version != 0:
            raise RuntimeError("Wrong version: %d" % (version,))
        if payload_len == -1 and data_len == 0 and offset == 0:
            raise ServerBusy
        if payload_len > self.MAX_LENGTH:
            raise RuntimeError("Server tried to send too much: %d" % (payload_len,))
        if payload_len == 0:
            data_len = 0
        data = await self._read_buf(payload_len)
        logger.debug(
            "OW recv%s %x %x %x %x %x %x %s", "S" if self.is_server else "", version, payload_len,
            ret_value, format_flags, data_len, offset, repr(data)
        )
        if self.is_server:
            return ret_value, format_flags, data, data_len
        else:
            data = data[:data_len]
            return ret_value, data

    async def write(self, typ, flags, rlen=0, data=b'', offset=0):
        if data is None:
            logger.debug(
                "OW send%s %x %x %x %x %x %x -", "S"
                if self.is_server else "", 0, -1, typ, flags, rlen, offset
            )
            await self.stream.send_all(struct.pack("!6i", 0, -1, typ, flags, rlen, offset))
        else:
            logger.debug(
                "OW send%s %x %x %x %x %x %x %s", "S"
                if self.is_server else "", 0, len(data), typ, flags, rlen, offset, repr(data)
            )
            await self.stream.send_all(
                struct.pack("!6i", 0, len(data), typ, flags, rlen, offset) + data
            )


class Message:
    timeout = 0.5
    cancelled = False

    def __init__(self, typ, data, rlen):
        #self.persist = persist
        self.typ = typ
        self.data = data
        self.rlen = rlen
        self.event = ValueEvent()

    def __repr__(self):
        return "<%s %s>" % (self.__class__.__name__, repr(self.data))

    def cancel(self):
        self.cancelled = True

    async def write(self, protocol):
        """Send an OWFS message to the other end of the connection.
        """
        # Assume a modern server
        flags = 0
        flags |= OWFlag.persist
        flags |= OWFlag.busret
        flags |= OWFlag.uncached
        flags |= OWFlag.ownet
        flags |= OWtempformat.celsius << OWtempformat._offset
        flags |= OWdevformat.fdidc << OWdevformat._offset
        flags |= OWpressureformat.mbar << OWpressureformat._offset

        # TODO
        if self.event is not None and not self.event.is_set():
            await self.event.set_error(Retry())
        self.event = ValueEvent()

        await protocol.write(self.typ, flags, self.rlen, self.data)

    def _resubmit(self):
        self.event = ValueEvent()

    async def process_reply(self, res, data, server):
        logger.debug("PROCESS %s %s %s", self, res, data)
        if res < 0:
            err = _errors.get(-res, GenericOWFSReplyError)
            if err is GenericOWFSReplyError:
                error = err(res, self, server)
            else:
                error = err(self, server)
            await self.event.set_error(error)
            return
        elif res > 0:
            assert len(data) == res, (data, res)
        data = self._process(data)
        if data is not None:
            await self.event.set(data)

    async def process_error(self, exc):
        await self.event.set_error(exc)

    def _process(self, data):
        return data

    @property
    def get_reply(self):
        return self.event.get

    @property
    def done(self):
        return self.event.is_set

    def _check(self, cmd, data=None):
        """Used in testing: verify that a message is correct."""
        assert self.typ == cmd, (self.typ, cmd)
        if data is not None:
            assert self.data == data, (cmd, self.data, data)


def _path(path):
    """Helper to build an OWFS path from a list"""
    path = '/' + '/'.join(str(x) for x in path)
    return path.encode('utf-8') + b'\0'


class NOPMsg(Message):
    def __init__(self):
        super().__init__(OWMsg.nop, b'', 0)

    def __repr__(self):
        return "<%s>" % (self.__class__.__name__)


class AttrGetMsg(Message):
    """read an OWFS value"""
    timeout = 2

    def __init__(self, *path):
        assert path
        self.path = path
        super().__init__(OWMsg.read, _path(self.path), 8192)

    def __repr__(self):
        return "<%s %s>" % (self.__class__.__name__, '/' + '/'.join(self.path))


class AttrSetMsg(Message):
    """write an OWFS value"""
    timeout = 1

    def __init__(self, *path, value):
        assert path is not None
        self.path = path
        self.value = value
        if isinstance(value, bool):
            value = b'1' if value else b'0'
        elif not isinstance(value, bytes):
            value = str(value).encode("utf-8")
        super().__init__(OWMsg.write, _path(self.path) + value, len(value))

    def __repr__(self):
        return "<%s %s =%s>" % (self.__class__.__name__, '/' + '/'.join(self.path), self.value)


class DirMsg(Message):
    """Read an owfs directory"""
    timeout = 10

    def __init__(self, path):
        self.path = path
        p = _path(self.path)
        super().__init__(OWMsg.dirall, p, len(p) - 1)

    def _process(self, data):
        if data == b'':
            return []
        res = []
        for entry in data.split(b","):
            assert b'\0' not in entry
            entry = entry.decode("utf-8")
            s = entry.rfind('/')
            if s > -1:
                entry = entry[s + 1:]
            res.append(entry)
        return res
