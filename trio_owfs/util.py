# utility code

import attr
import outcome

import anyio


@attr.s
class ValueEvent:
    """A waitable value useful for inter-task synchronization,
    inspired by :class:`threading.Event`.

    An event object manages an internal value, which is initially
    unset, and tasks can wait for it to become True.

    """

    event = attr.ib(factory=anyio.create_event)
    value = attr.ib(default=None, init=False)

    async def set(self, value):
        """Set the internal flag value to True, and wake any waiting tasks.

        """
        self.value = outcome.Value(value)
        await self.event.set()

    def is_set(self):
        return self.value is not None

    async def set_error(self, exc):
        """Set the internal flag value to True, and wake any waiting tasks.

        """
        self.value = outcome.Error(exc)
        await self.event.set()

    def cancel(self):
        import pdb;pdb.set_trace()
        self.set_error(anyio.CancelledError)

    async def get(self):
        """Block until the internal flag value becomes True.

        If it's already True, then this method is still a checkpoint, but
        otherwise returns immediately.

        """
        await self.event.wait()
        return self.value.unwrap()

