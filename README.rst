1wire for Trio
==============

Welcome to `1wire for Trio <https://github.com/python-trio/trio-owfs>`__!

This library allows you to access the 1wire bus with Python, using Trio.
This code does *not* try to talk to any 1wire interface by itself; it
uses TCP port 4304 (by default) to talk to one or more ``owserver``\ s.

Bus enumeration (either when starting up or periodically in the background)
is automatic and can be turned off if desired.

This code does not yet support background polling, alerts, or simultaneous
conversions. All of that is fairly high on the TODO list.

Use `trio_asyncio <https://github.com/python-trio/trio-asyncio` if you need
to use this library from an asyncio-based program.

License: Your choice of MIT or Apache License 2.0

