++++++++++++
Introduction
++++++++++++

… or "how to talk to 1wire in five minutes"[#]_.

.. [#] Setting up an `owserver <http://owfs.org/uploads/owserver.html>`_ instance not included.

First, create an OWFS instance::

    import trio
    from trio_owfs import OWFS

    async def main():
        async with OWFS() as ow:
            await setup_onewire(ow)
            pass # do whatever you want with 1wire

    trio.run(main)

Optionally, start an event monitor::

    async def setup_onewire(ow):
        await ow.add_task(monitor, ow)

    async def monitor(ow):
        with ow.events as events:
            async for msg in events:
                logger.info("%s", msg)

Connect to one or more owserver instances::

    async def setup_onewire(ow):
        # … continued
        s = await ow.add_server("127.0.0.1")

At this point, the server is connected and its bus has been enumerated.
The connection to the server is kept alive and will automatically be
re-established until you leave the ``with OWFS()`` block, or call
``await s.aclose()``.

Your event monitor receives a :class:`trio_owfs.event.DeviceLocated` event
for each 1wire slave; in a more complicated program, it should match them with
your configuration file.

You can also ask by device ID, and get/set attributes if the device is present::

    dev = await ow.get_device("10.DBDB39010800.EF")
    # triggers a :class:`trio_owfs.event.DeviceAdded` event if not yet known
    if dev.bus is not None:
        # make sure that the data accessor methods are loaded
        await ow.ensure_struct(dev)

        heat = await dev.temperature
        await dev.set_temphigh(99)

This includes elements in subdirectories and array members::

        await dev.voltage[2]
        await dev.set_PIO(3, True)
        
        await dev.T8A.volt[0]

Note that all IDs are in FDIDC format (family, dot, ID, dot, checksum).

You can arrange for periodic bus scans, or trigger them yourself::

    await ow.scan_now()

Re-scanning will automatically add new buses and devices, relocate moved
devices, free buses which have been disconnected, and de-locate
(i.e. remove the bus attribute from) devices that can no longer be found.

Trio-OWFS transparently supports the `DS2509 <http://owfs.org/uploads/DS2409.html>` 
bus coupler, by creating (and auto-scanning) two buses for its ``main`` and ``aux`` ports.
Don't change its settings yourself; you're likely to confuse your ``owserver``.

