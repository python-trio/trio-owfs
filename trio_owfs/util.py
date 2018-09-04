# utility code

import operator
from collections import deque, OrderedDict

import attr
import outcome

import trio


class CancelledError(RuntimeError):
    """\
        A queued request has been cancelled.
        """
    pass


@attr.s
class ValueEvent:
    """A waitable value useful for inter-task synchronization,
    inspired by :class:`threading.Event`.

    An event object manages an internal value, which is initially
    unset, and tasks can wait for it to become True.

    """

    _lot = attr.ib(default=attr.Factory(trio.hazmat.ParkingLot), init=False)
    _value = attr.ib(default=None, init=False)

    def is_set(self):
        """Return the current value of the internal flag.

        """
        return self._value is not None

    @trio.hazmat.enable_ki_protection
    def set(self, value):
        """Set the internal flag value to True, and wake any waiting tasks.

        """
        self._value = outcome.Value(value)
        self._lot.unpark_all()

    @trio.hazmat.enable_ki_protection
    def set_error(self, exc):
        """Set the internal flag value to True, and wake any waiting tasks.

        """
        self._value = outcome.Error(exc)
        self._lot.unpark_all()

    def cancel(self):
        self.set_error(CancelledError)

    def clear(self):
        """Set the internal flag value to False.

        """
        self._value = None

    async def get(self):
        """Block until the internal flag value becomes True.

        If it's already True, then this method is still a checkpoint, but
        otherwise returns immediately.

        """
        if self._value is not None:
            await trio.hazmat.checkpoint()
        else:
            await self._lot.park()
        return self._value.unwrap()

    def statistics(self):
        """Return an object containing debugging information.

        Currently the following fields are defined:

        * ``tasks_waiting``: The number of tasks blocked on this event's
          :meth:`get` method.

        """
        return self._lot.statistics()
