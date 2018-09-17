Release history
===============

.. currentmodule:: trio_owfs

.. towncrier release notes start

Trio_Owfs 0.3.0 (2018-09-17)
----------------------------

Features
~~~~~~~~

- Trio-OWFS now auto-generates accessors for reading and writing attributes by
  interrogating ``owserver`` for device attributes. This includes
  subdirectories and arrays.
