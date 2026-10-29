.. currentmodule:: uataq

Input Parameters
================

The reading functions share their arguments, and each one is described once,
here. :func:`read_data` and :func:`get_obs` take most of them;
:func:`get_recent_obs` and :func:`get_network_obs` take the ones their pages
list.

.. autosummary::

  read_data
  get_obs

.. _input-sid:

SID
---

The site ID, such as ``"WBB"`` or ``"TRX01"``: a key of the
:doc:`configuration </reference/config>`. Case does not matter.
:doc:`/reference/sites_and_instruments` lists them.

.. _input-instruments:

Instruments
-----------

``instruments`` (:func:`read_data`) is one instrument name, such as
``"lgr_ugga"``, a list of them, or ``"all"`` (the default) for every instrument
at the site. The names are the keys under the site's ``instruments`` in the
configuration; :doc:`/reference/sites_and_instruments` lists them.

.. _input-pollutants:

Pollutants
----------

``pollutants`` (:func:`get_obs`) is one pollutant, such as ``"CO2"``, a list of
them, or ``"all"`` (the default) for every pollutant the site has measured.
Case does not matter: ``"nox"``, ``"NOx"`` and ``"NOX"`` all read NOx. A site's
``pollutants`` spell it ``'NOX'``, and the columns ``NOx_ppb`` (see
:ref:`column-names`).

.. _input-format:

Format
------

``format`` (:func:`get_obs`) is the shape of the table. ``"wide"`` (the
default) has a column for each concentration, such as ``CO2d_ppm_cal`` and
``CH4d_ppm_cal``. ``"long"`` has one row per measurement, with the column name
in ``pollutant`` and the measurement in ``value``. :doc:`/guides/read_data` shows
both.

.. _input-group:

Research group
--------------

``group`` is the research group whose archive is read: ``"lin"`` or ``"horel"``
(the keys of ``uataq.filesystem.groups``), or a dictionary from instrument name
to group, to choose for each instrument.

With ``group=None`` (the default), each instrument picks its own: the lin group
when it operates the instrument, otherwise the group that does. When two groups'
archives cover different periods (the instrument's ``group_dates`` in the
:doc:`configuration </reference/config>`), a range that crosses the boundary is
read from each group in turn, and the pieces are joined in time. TRX01's ozone,
for example, comes from lin through 27 October 2017 and from horel after that.
Naming a group reads the whole range from that group.

.. _input-level:

Data level
----------

``lvl`` (:func:`read_data`) is the data level: ``"raw"``, ``"qaqc"``,
``"calibrated"`` or ``"final"``. With none (the default), :func:`read_data`
reads the highest level the instrument has. :func:`get_obs` takes no level: it
always reads ``final``. What each level holds, and how to choose one, is on
:doc:`/guides/data_levels_and_flags`.

.. _input-time-range:

Time range
----------

``time_range`` is the time to read, in UTC, like the times in the data. A range
includes its start and stops before its stop. To read in local time, see
:ref:`first-data-local-month`. It takes three forms.

``None`` (the default)
    Everything the archive holds.

A string
    One period in ISO 8601, from its start to the start of the next one. It can
    name a year, a month, a day, an hour, a minute or a second, down to
    fractions of a second:

    .. list-table::
       :header-rows: 1
       :widths: 40 60

       * - String
         - Range
       * - ``"2020"``
         - the year 2020
       * - ``"2020-01"``
         - January 2020
       * - ``"2020-01-01"``
         - 1 January 2020
       * - ``"2020-01-01T12"``
         - 12:00 to 13:00 on 1 January 2020
       * - ``"2020-01-01T12:30"``
         - 12:30 to 12:31
       * - ``"2020-01-01T12:30:45.5"``
         - 12:30:45.5 to 12:30:45.6 (one unit of the last digit given)

    Dashes and colons may be left out (``"20200101"``), and a trailing ``Z`` or
    ``+00:00`` is accepted. Any other offset raises a ``ValueError``.

Two times
    A list, tuple or slice of a start and a stop: ``datetime`` objects, pandas
    ``Timestamp`` objects or strings as above. A stop given as a string is the
    end of the period it names, so ``["2020-01-01", "2020-01-31"]`` includes all
    of 31 January. ``None`` for either end leaves that side open.

Time zones
^^^^^^^^^^

The examples below read the UATAQ archive on CHPC and are not run when the
documentation is built; the output is from runs on 12 October 2026.

Times have no time zone attached. A string with an offset other than ``Z`` or
``+00:00`` is an error that says so:

.. code-block:: pycon

    >>> import uataq
    >>> uataq.get_obs("WBB", "CO2", time_range="2025-06-01T00:00-06:00")
    Traceback (most recent call last):
      ...
    ValueError: Invalid time string '2025-06-01T00:00-06:00'. Expected ISO 8601 in UTC, e.g. '2024', '2024-01', '2024-01-15', '2024-01-15T12:30:45'.

A pandas ``Timestamp`` must not carry a time zone either. One that does gives
an error that does not say what to do:

.. code-block:: pycon

    >>> import pandas as pd
    >>> start = pd.Timestamp("2025-06-01", tz="America/Denver")
    >>> stop = pd.Timestamp("2025-07-01", tz="America/Denver")
    >>> uataq.get_obs("WBB", "CO2", time_range=[start, stop])
    Traceback (most recent call last):
      ...
    TypeError: Cannot compare tz-naive and tz-aware timestamps

The same happens with ``tz="UTC"``. Convert the times to UTC and take the time
zone off:

.. code-block:: pycon

    >>> utc = [t.tz_convert("UTC").tz_localize(None) for t in (start, stop)]
    >>> utc
    [Timestamp('2025-06-01 06:00:00'), Timestamp('2025-07-01 06:00:00')]
    >>> len(uataq.get_obs("WBB", "CO2", time_range=utc))
    250685

That is June in Mountain time. :ref:`first-data-local-month` gets the same
rows by converting a longer read and cutting it.

Where a range ends
^^^^^^^^^^^^^^^^^^

An end given as a ``Timestamp`` stops at that instant, so the same end given as
a string gives a longer range:

.. code-block:: pycon

    >>> a = uataq.get_obs("WBB", "CO2", time_range=["2025-06-02T06", "2025-06-03T06"])
    >>> a.index[-1]
    Timestamp('2025-06-03 06:59:53')
    >>> b = uataq.get_obs(
    ...     "WBB", "CO2", time_range=[pd.Timestamp("2025-06-02T06"), pd.Timestamp("2025-06-03T06")]
    ... )
    >>> b.index[-1]
    Timestamp('2025-06-03 05:59:58')

So the string range is an hour longer. When you want an end at an exact time,
give it as a ``Timestamp``.

.. _input-num-processes:

Number of processes
-------------------

``num_processes`` is how many processes read an instrument's files at once.
The default, 1, reads them one after another. A larger number uses at most one
process per file, and ``"max"`` uses every core this process may run on (in a
Slurm job, the cores you asked for). Keep it at 1 on a login node, which you
share with everyone logged in. A script that uses more than one process has its own
setup: see :ref:`large-reads`.

.. _input-recent:

Recent
------

``recent`` (:func:`get_recent_obs`) is how far back from now to read: a
``datetime.timedelta`` or text pandas reads as a time span, such as ``"3D"`` or
``"12h"``. The default is 10 days.

.. _input-file-pattern:

File pattern
------------

``file_pattern`` (:func:`read_data`) keeps only the files whose names match it.
Its main use is to pick the NMEA sentence type of the lin group's raw GPS
files. The default, ``None``, keeps every file.
