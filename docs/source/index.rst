.. documentation master file, created by
   sphinx-quickstart on Sat Jan 21 19:11:14 2017.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.


=================================
Onewire for Trio: Access to 1wire
=================================

This project enables you to access one or more 1wire buses asynchronously.

Prerequisites:

* Trio: https://trio.readthedocs.io

* owserver: http://owfs.org

* any OWFS-compatible hardware

+++++
Usage
+++++

First, create an OWFS instance::

    from trio_owfs import OWFS

    async def main():
        async with OWFS() as ow:
            await setup_onewire(ow)

Start an event monitor::

    async def setup_onewire(ow):
        await ow.add_task(monitor, ow)

    async def monitor(ow):
        with ow.events as events:
            async for msg in events:
                logger.info("%s", msg)

Connect to one or more owserver instance::

    async def setup_onewire(ow):
        # … continued
        s = await ow.add_server("127.0.0.1")

At this point, the server is connected and its bus has been enumerated.
The connection to the server is kept alive and will automatically be
re-established until you leave the ``with OWFS()`` block, or call
``await s.aclose()``.

Your event monitor receives a :class:`trio_owfs.event.DeviceLocated` event
for each 1wire slave. You can also ask for a specific device ID::

    dev = await ow.get_device("10.DBDB39010800.EF")
    # triggers a :class:`trio_owfs.event.DeviceAdded` event if not yet known
    if dev.bus is not None:
        # we know where it is
        heat = await dev.temperature
        await dev.set_temphigh(99)

You can arrange for periodic bus scans, or trigger them yourself::

    await ow.scan_now()

Re-scanning will automatically add new buses and devices, relocate moved
devices, deregister buses which have been disconnected, and de-locate
devices that can no longer be found.

++++++++++++
Future plans
++++++++++++

* support simultaneous temperature or voltage conversion (no bus delay)

* support background polling

* auto-discover device attributes by reading ``/structure``

Non-plans
+++++++++
    
Trio-OWFS will never support

* Cached bus access. If you want to cache a value, do it in Python.

* Linked owservers (i.e. one server that forwards to another).

.. toctree::
   :maxdepth: 2

   history.rst

====================
 Indices and tables
====================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
* :ref:`glossary`
