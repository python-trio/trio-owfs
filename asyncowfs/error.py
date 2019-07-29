# for message type classification see
# http://owfs.org/index.php?page=owserver-message-types
# and 'enum msg_classification' from module/owlib/src/include/ow_message.h

import attr

import logging
logger = logging.getLogger(__name__)


class OWFSReplyError(Exception):
    pass


@attr.s(cmp=False)
class GenericOWFSReplyError(OWFSReplyError):
    err = attr.ib()
    req = attr.ib()
    server = attr.ib()


_errors = {}


@attr.s(cmp=False)
class OWFSReplyError_(OWFSReplyError):
    req = attr.ib()
    server = attr.ib()


def _register(cls):
    _errors[cls.err] = cls
    return cls


@_register
@attr.s(cmp=False)
class PermissionError(OWFSReplyError_):
    err = 13


@_register
@attr.s(cmp=False)
class InUseError(OWFSReplyError_):
    err = 98


@_register
@attr.s(cmp=False)
class NotAvailableError(OWFSReplyError_):
    err = 99


@_register
@attr.s(cmp=False)
class TryAgainError(OWFSReplyError_):
    err = 11


@_register
@attr.s(cmp=False)
class BadFSError(OWFSReplyError_):
    err = 9


@_register
@attr.s(cmp=False)
class BadMsgError(OWFSReplyError_):
    err = 74


@_register
@attr.s(cmp=False)
class BusyError(OWFSReplyError_):
    err = 16


@_register
@attr.s(cmp=False)
class ConnAbortedError(OWFSReplyError_):
    err = 103


@_register
@attr.s(cmp=False)
class FaultError(OWFSReplyError_):
    err = 14


@_register
@attr.s(cmp=False)
class InterruptedError(OWFSReplyError_):
    err = 4


@_register
@attr.s(cmp=False)
class InvalidDataError(OWFSReplyError_):
    err = 22


@_register
@attr.s(cmp=False)
class BusIOError(OWFSReplyError_):
    err = 5


@_register
@attr.s(cmp=False)
class IsDirError(OWFSReplyError_):
    err = 21


@_register
@attr.s(cmp=False)
class LoopError(OWFSReplyError_):
    err = 40


@_register
@attr.s(cmp=False)
class MsgSizeError(OWFSReplyError_):
    err = 90


@_register
@attr.s(cmp=False)
class NameTooLongError(OWFSReplyError_):
    err = 36


@_register
@attr.s(cmp=False)
class NoBufsError(OWFSReplyError_):
    err = 105


@_register
@attr.s(cmp=False)
class NoDeviceError(OWFSReplyError_):
    err = 19


@_register
@attr.s(cmp=False)
class NoEntryError(OWFSReplyError_):
    err = 2


@_register
@attr.s(cmp=False)
class NoFreeMemoryError(OWFSReplyError_):
    err = 12


@_register
@attr.s(cmp=False)
class NoMessageError(OWFSReplyError_):
    err = 42


@_register
@attr.s(cmp=False)
class NoDirectoryError(OWFSReplyError_):
    err = 20


@_register
@attr.s(cmp=False)
class NotSupportedError(OWFSReplyError_):
    err = 95


@_register
@attr.s(cmp=False)
class RangeError(OWFSReplyError_):
    err = 34


@_register
@attr.s(cmp=False)
class ReadOnlyError(OWFSReplyError_):
    err = 30


@_register
@attr.s(cmp=False)
class InputPathTooLongError(OWFSReplyError_):
    err = 26


@_register
@attr.s(cmp=False)
class BadPathSyntaxError(OWFSReplyError_):
    err = 27


@_register
@attr.s(cmp=False)
class TextInPathError(OWFSReplyError_):
    err = 77


@_register
@attr.s(cmp=False)
class BadCRC8Error(OWFSReplyError_):
    err = 28


@_register
@attr.s(cmp=False)
class UnknownNameError(OWFSReplyError_):
    err = 29


@_register
@attr.s(cmp=False)
class AliasTooLongError(OWFSReplyError_):
    err = 31


@_register
@attr.s(cmp=False)
class UnknownPropertyError(OWFSReplyError_):
    err = 32


@_register
@attr.s(cmp=False)
class NotAnArrayError(OWFSReplyError_):
    err = 33


@_register
@attr.s(cmp=False)
class IsAnArrayError(OWFSReplyError_):
    err = 35


@_register
@attr.s(cmp=False)
class NotBitfieldError(OWFSReplyError_):
    err = 37


@_register
@attr.s(cmp=False)
class IndexTooLargeError(OWFSReplyError_):
    err = 38


@_register
@attr.s(cmp=False)
class NoSubpathError(OWFSReplyError_):
    err = 39


@_register
@attr.s(cmp=False)
class DeviceNotFoundError(OWFSReplyError_):
    err = 41


@_register
@attr.s(cmp=False)
class DeviceError(OWFSReplyError_):
    err = 43


@_register
@attr.s(cmp=False)
class BusShortError(OWFSReplyError_):
    err = 44


@_register
@attr.s(cmp=False)
class NoSuchBusError(OWFSReplyError_):
    err = 45


@_register
@attr.s(cmp=False)
class BusNotAppropriateError(OWFSReplyError_):
    err = 46


@_register
@attr.s(cmp=False)
class BusNotRespondingError(OWFSReplyError_):
    err = 47


@_register
@attr.s(cmp=False)
class BusResetError(OWFSReplyError_):
    err = 48


@_register
@attr.s(cmp=False)
class BusClosedError(OWFSReplyError_):
    err = 49


@_register
@attr.s(cmp=False)
class BusNotOpenedError(OWFSReplyError_):
    err = 50


@_register
@attr.s(cmp=False)
class BusCommunicationError(OWFSReplyError_):
    err = 51


@_register
@attr.s(cmp=False)
class BusTimeoutError(OWFSReplyError_):
    err = 52


@_register
@attr.s(cmp=False)
class TelnetError(OWFSReplyError_):
    err = 53


@_register
@attr.s(cmp=False)
class TCPError(OWFSReplyError_):
    err = 54


@_register
@attr.s(cmp=False)
class BusIsLocalError(OWFSReplyError_):
    err = 55


@_register
@attr.s(cmp=False)
class BusIsRemoteError(OWFSReplyError_):
    err = 56


@_register
@attr.s(cmp=False)
class ReadTooLargeError(OWFSReplyError_):
    err = 57


@_register
@attr.s(cmp=False)
class DataCommunicationError(OWFSReplyError_):
    err = 58


@_register
@attr.s(cmp=False)
class NotRPropertyError(OWFSReplyError_):
    err = 59


@_register
@attr.s(cmp=False)
class NotReadablePropertyError(OWFSReplyError_):
    err = 60


@_register
@attr.s(cmp=False)
class DataTooLargeError(OWFSReplyError_):
    err = 61


@_register
@attr.s(cmp=False)
class DataTooSmallError(OWFSReplyError_):
    err = 62


@_register
@attr.s(cmp=False)
class DataFormatError(OWFSReplyError_):
    err = 63


@_register
@attr.s(cmp=False)
class NotWPropertyError(OWFSReplyError_):
    err = 64


@_register
@attr.s(cmp=False)
class NotWritablePropertyError(OWFSReplyError_):
    err = 65


@_register
@attr.s(cmp=False)
class ReadOnlyModeError(OWFSReplyError_):
    err = 66


@_register
@attr.s(cmp=False)
class DataCommError(OWFSReplyError_):
    err = 67


@_register
@attr.s(cmp=False)
class OutputPathTooLongError(OWFSReplyError_):
    err = 68


@_register
@attr.s(cmp=False)
class NotADirectoryError(OWFSReplyError_):
    err = 69


@_register
@attr.s(cmp=False)
class NotADeviceError(OWFSReplyError_):
    err = 70


@_register
@attr.s(cmp=False)
class UnknownQueryError(OWFSReplyError_):
    err = 71


@_register
@attr.s(cmp=False)
class SocketError(OWFSReplyError_):
    err = 72


@_register
@attr.s(cmp=False)
class TimeoutError(OWFSReplyError_):
    err = 73


@_register
@attr.s(cmp=False)
class VersionError(OWFSReplyError_):
    err = 75


@_register
@attr.s(cmp=False)
class PacketSizeError(OWFSReplyError_):
    err = 76


@_register
@attr.s(cmp=False)
class UnexpectedNullError(OWFSReplyError_):
    err = 78


@_register
@attr.s(cmp=False)
class NoMemoryError(OWFSReplyError_):
    err = 79
