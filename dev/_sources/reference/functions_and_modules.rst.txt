Functions and modules
=====================

Each class and function has a page of its own. A class page lists its
attributes and methods, each with a page of its own, and links to what it
inherits from the classes it extends.

Reading data
------------

What each argument means is written once, on :doc:`/reference/input_parameters`.

.. currentmodule:: uataq

.. autosummary::
   :toctree: ../api
   :nosignatures:

   get_obs
   read_data
   get_recent_obs
   get_network_obs
   get_site
   Network

Sites, columns and errors
-------------------------

The site objects :func:`get_site` returns, the functions that pick and parse
column names, the errors and warnings a read raises, and the time range.

.. autosummary::
   :toctree: ../api
   :recursive:

   sites
   pollutants
   errors
   timerange

SODAR
-----

Wind profiles from the horel group's SODAR stations, which are not UATAQ sites
and are read on their own.

.. autosummary::
   :toctree: ../api
   :recursive:

   sodar

Internals
---------

How uataq finds and parses the files: the configuration it builds the sites
from, the instrument classes, each research group's archive, and the GPS
helpers. You need these only to change uataq.

.. autosummary::
   :toctree: ../api
   :nosignatures:

   laboratory
   Laboratory

.. autosummary::
   :toctree: ../api
   :recursive:

   instruments
   filesystem
   gps
