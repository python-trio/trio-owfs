Trio-owfs Reference
===================

.. module:: trio_owfs


Entry point
-----------

The base for accessing the 1wire system is an async context::

    async with OWFS() as ow:
        pass  # do whatever

.. autofunction:: OWFS

.. automodule:: trio_owfs.service
   :members:

.. automodule:: trio_owfs.server
   :members:

.. automodule:: trio_owfs.bus
   :members:

.. automodule:: trio_owfs.device
   :members:

.. automodule:: trio_owfs.event
   :members:

.. automodule:: trio_owfs.error
   :members:

