.. currentmodule:: uataq

Input Parameters
================

What each argument of :func:`read_data` and :func:`get_obs` means is written
once, here: the two functions come first, then one section for each argument.

.. autosummary::

  read_data
  get_obs

.. _input-sid:

SID
---

``SID`` is the site identifier for a UATAQ site.
It is a key in the configuration file, such as ``WBB``; case does not matter.
The :doc:`sites_and_instruments` page lists them.

.. _input-instruments:

Instruments
-----------

``instruments`` is a single instrument name or a list of instrument names.
The instrument name is a key under the site's ``instruments`` in the configuration
(listed on the :doc:`sites_and_instruments` page).

.. _input-pollutants:

Pollutants
----------

``pollutants`` is a single pollutant name or a list of pollutant names.
The pollutant name is a capitalized molecule abbreviation.

.. _input-group:

Research Group
--------------

``group`` is the research group that collected the data.
It is a string that corresponds to a key in the ``uataq.filesystem.groups`` dictionary,
or a mapping of instrument name to group name to choose per instrument.

With ``group=None`` (the default), each instrument picks its own group: the
default group (``lin``) when it operates the instrument, otherwise the
configured operator. When the groups' archives cover different periods (the
instrument's ``group_dates`` in the :doc:`configuration <config>`), a time
range that crosses a boundary is read from each group in turn and the pieces
are concatenated in time. For example, TRX01 ozone comes from lin through
October 2017 and from horel after that. Naming a group reads the whole range
from that group.


.. _input-level:

Processing Level
----------------

``lvl`` is the processing level of the data.
Available levels, from least to most processed, are:

- ``raw`` : Raw data.
- ``qaqc`` : `QAQC flags <https://github.com/uataq/data-pipeline/blob/main/QAQC_Flags.md>`_ applied to data. Flagged rows are kept, with their flag in ``QAQC_Flag``.
- ``calibrated`` : Calibrated data. (Only available for instruments which receive calibration in post-processing.)
- ``final`` : Finalized data, with the pipeline's default flags applied. (Flagged data and measurements of calibration tanks are dropped.)

``final`` is the ready-to-share level: it can go to people outside the group
as it is. The lower levels (``raw``, ``qaqc`` and ``calibrated``) are for finer
control. Which one to use depends on how clean the data need to be for what you
are doing, and on how much control you want over the QAQC.

:func:`get_obs` always reads the ``final`` level. :func:`read_data` reads the
level you give it. With no ``lvl`` it reads the highest (most processed) level
the instrument has. :doc:`first_month` shows the same day at ``final`` and at
``qaqc``, and :doc:`columns` says what each level holds.

.. _input-time-range:

Time Range
----------

``time_range`` filters the returned data to the specified time range.
Times are UTC, and so are the times in the data. To read a month in local
time, see :doc:`first_month`.

There are three primary formats for ``time_range``:

1. ``None``: Returns all available data.
2. Single string in ISO8601 format (UTC), down to fractions of a second:

   - The string is interpreted as a range from the start of the string to the start of the next time unit.
   - Examples:

     - '2020' represents the year 2020.
     - '2020-01' represents January 2020 to February 2020.
     - '2020-01-01' represents January 1st, 2020 to January 2nd, 2020.
     - '2020-01-01T12' represents January 1st, 2020 from 12:00 to 13:00.
     - '2020-01-01T12:30' represents January 1st, 2020 from 12:30 to 12:31.
     - '2020-01-01T12:30:45.5' represents 12:30:45.5 to 12:30:45.6 (one unit of the last digit given).

   - Dashes and colons may be omitted ('20200101'), and a trailing 'Z' or '+00:00' is accepted.
     Other strings, including other UTC offsets, raise a ``ValueError``.

3. List, tuple, or slice of two datetime-like objects:
    - Datetime-like objects include datetime objects, Timestamp objects, and strings in ISO8601 format.
    - The first object is the start of the range and the second object is the end of the range.
      The range is inclusive of the start and exclusive of the end.
      An end given as a string is taken as the end of the period it names, as above,
      so ``['2020-01-01', '2020-01-31']`` includes all of January 31st.
    - The use of ``None`` in place of a datetime-like object will set the range to be unbounded in that direction.

Time zones
^^^^^^^^^^

The examples in this section read the UATAQ archive, which is only available on
CHPC. They are shown as code and are not run when the documentation is built;
the output is from runs on CHPC on 12 October 2026.

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

That reads exactly June in local time, the same 250,685 rows as the cut in
:ref:`first-month-local-month`. Both ways are right; use the one you find
clearer.

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

Number of Processes
-------------------

``num_processes`` is the number of processes to use when reading data from each instrument. The default is 1.
 - If ``num_processes`` is set to 1, the data is read serially.
 - Setting ``num_processes`` to a number greater than 1 will read the data in parallel using the minimum of ``num_processes`` and the number of files for an instrument.
 - Setting ``num_processes`` to 'max' will use the minimum of the number of files for an instrument and the number of available CPU cores.
    Warning: Frequent use of ``num_processes='max'`` may upset your fellow node users.

.. _input-file-pattern:

File Pattern
------------

``file_pattern`` is a string that is used to filter the files. The primary use for this parameter is to filter raw lin gps data by nmea sentence type. The default is ``None``.
