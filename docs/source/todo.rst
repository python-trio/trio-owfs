++++++++++++
Future plans
++++++++++++

* support simultaneous temperature or voltage conversion (no bus delay)

* poll a device in the background

* auto-poll each bus's ``alert`` subdirectory

* improve auto-discovery of device attributes by reading ``/structure``

Non-plans
+++++++++
    
Trio-OWFS will never support

* Cached bus access. If you want to cache a value, do it in Python.

* Linked owservers (i.e. one server that forwards to another).

