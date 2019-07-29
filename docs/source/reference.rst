AsyncOWFS Reference
===================

.. module:: asyncowfs


Entry point
-----------

The base for accessing the 1wire system is an async context::

    async with OWFS() as ow:
        pass  # do whatever

.. autofunction:: OWFS

.. automodule:: asyncowfs.service
   :members:

.. automodule:: asyncowfs.server
   :members:

.. automodule:: asyncowfs.bus
   :members:

.. automodule:: asyncowfs.device
   :members:

.. automodule:: asyncowfs.event
   :members:

.. automodule:: asyncowfs.error
   :members:

