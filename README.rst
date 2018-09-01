Onewire for Trio
================

Welcome to `Onewire for Trio <https://github.com/python-trio/trio-owfs>`__!

This library allows you to access the 1wire bus with Python, using Trio.
This code does *not* try to talk to any 1wire interface by itself; it
uses TCP port 4304 (by default) to talk to one or more ``owserver``\ s.

Bus access is transparent, i.e. if a device moves from one bus to another
you won't notice (unless you *want* to get notified).

Bus enumeration (either when starting up or periodically in the background)
is transparent and can be turned off if desired.

The interface supports background polling, alerts, and simultaneous conversions.

Use `trio_asyncio <https://github.com/python-trio/trio-asyncio` if you need
to use this library from an asyncio-based program.

License: Your choice of MIT or Apache License 2.0

