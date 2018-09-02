# for message type classification see
# http://owfs.org/index.php?page=owserver-message-types
# and 'enum msg_classification' from module/owlib/src/include/ow_message.h

import struct
from .util import ValueEvent

import logging
logger = logging.getLogger(__name__)

class OWMsg:
    """Constants for the owserver api message types."""
    error       = 0
    nop         = 1
    read        = 2
    write       = 3
    dir         = 4
    size        = 5
    presence    = 6
    dirall      = 7
    get         = 8
    dirallslash = 9
    getslash    = 10

class OWFlag:
    cache = 0x1 # ?
    busret = 0x2 # enumeration includes bus names
    persist = 0x4 # use persistent connections
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

class Message:
    def __init__(self,typ,data,rlen):
        #self.persist = persist
        self.typ = typ
        self.data = data
        self.rlen = rlen
        self.event = ValueEvent()
        
    async def write(self, stream):
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

        logger.debug("OW send %x %x %x %x %x %x %s",0,len(self.data), self.typ, flags, self.rlen, 0, repr(self.data))
        await stream.send_all(struct.pack("!6i",
            0, len(self.data), self.typ, flags, self.rlen, 0) + self.data)
    
    def process_reply(self, res, data):
        if res != 0:
            raise RuntimeError("Result for %s is %d (%s)!" % (repr(self), res, repr(data)))
        data = self._process(data)
        if data is not None:
            self.event.set(data)
    
    def _process(self, data):
        return data

    @property
    def get_reply(self):
        return self.event.get

    @property
    def done(self):
        return self.event.is_set

def _path(path):
    """Helper to build an OWFS path from a list"""
    if path:
        path = '/'+'/'.join(str(x) for x in path)
    else:
        path = ""
    return path.encode('utf-8')+b'\0'

class NOPMsg(Message):
    def __init__(self):
        super().__init__(OWMsg.nop,b'',0)

class AttrGetMsg(Message):
    """read an OWFS value"""
    def __init__(self,path):
        assert path is not None
        self.path = path
        super().__init__(OWMsg.read,_path(self.path),8192)
        
class AttrSetMsg(Message):
    """write an OWFS value"""
    def __init__(self,path,value):
        assert path is not None
        self.path = path
        self.value = value
        val = str(val).encode("utf-8")
        super().__init__(OWMsg.write,_path(self.path)+val.encode('utf-8'),len(val))

class DirMsg(Message):
    """Read an owfs directory"""
    def __init__(self,path):
        self.path = path
        super().__init__(OWMsg.dirall, _path(self.path), 0)
    
    def _process(self, data):
        res = []
        for entry in data.split(b","):
            entry = entry.decode("utf-8")
            s = entry.rfind('/')
            if s > -1:
                entry = entry[s+1:]
            entry = entry.rstrip("\0")
            res.append(entry)
        return res

