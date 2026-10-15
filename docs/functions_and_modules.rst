Functions and modules
=====================

Each class and function has a page of its own. A class page lists its
attributes and methods, each with a page of its own, and links to what it
inherits from the classes it extends.

Reading data
------------

What each argument means is written once, on :doc:`input_parameters`.

.. currentmodule:: uataq

.. autosummary::
   :toctree: api
   :nosignatures:

   read_data
   get_obs
   get_recent_obs
   get_network_obs
   Network

The laboratory and its sites
----------------------------

``laboratory`` and ``get_site`` are on :doc:`laboratory`, and ``Site`` and
``MobileSite`` on :doc:`sites`.

Modules
-------

.. autosummary::
   :toctree: api
   :recursive:

   instruments
   pollutants
   filesystem
   gps
   sodar
   timerange
   errors
