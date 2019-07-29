.. image:: https://img.shields.io/badge/chat-join%20now-blue.svg
   :target: https://gitter.im/python-trio/general
   :alt: Join chatroom

.. image:: https://img.shields.io/badge/docs-read%20now-blue.svg
   :target: https://asyncowfs.readthedocs.io/en/latest/?badge=latest
   :alt: Documentation Status
   
.. image:: https://img.shields.io/pypi/v/asyncowfs.svg
   :target: https://pypi.org/project/asyncowfs
   :alt: Latest PyPi version

.. image:: https://travis-ci.org/python-trio/asyncowfs.svg?branch=master
   :target: https://travis-ci.org/python-trio/asyncowfs
   :alt: Automated test status

.. image:: https://codecov.io/gh/python-trio/asyncowfs/branch/master/graph/badge.svg
   :target: https://codecov.io/gh/python-trio/asyncowfs
   :alt: Test coverage


Async 1wire
===========

Welcome to `Async 1wire <https://github.com/smurfix/asyncowfs>`__!

This library allows you to access 1wire buses with Python, using any
async library (trio, asyncio, curio).

This code does *not* try to talk to any 1wire interface by itself; it
uses TCP port 4304 (by default) to access one or more ``owserver``\ s.

Bus enumeration (when starting up, plus periodically in the background
if desired) is automatic and can be turned off.

This code supports background polling, alerts, and simultaneous
conversions. Bus couplers (DS2509) are handled transparently. Accessors to
device attributes are created from device descriptors, read from
``owserver`` and augmented by device-specific classes when necessary.

License: Your choice of MIT or Apache License 2.0

The name of this library is (a) historic, (b) its main author strongly
prefers Trio.
