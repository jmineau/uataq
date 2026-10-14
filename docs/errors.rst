.. currentmodule:: uataq

When there is nothing to read
=============================

.. note::

    The examples on this page read the UATAQ archive, which is only available
    on CHPC. They are shown as code and are not run when the documentation is
    built. The output under each one is from a run on CHPC on 11 October 2026.
    The archive keeps growing, so what a read returns will have moved on by the
    time you read this.

The archive has gaps. Sites close, instruments are removed or break, and some
months are missing. A read then raises an error or comes back empty. Each case
below says what you see, what it means and what to do.

First, turn on the log. The package reports why it skipped something as a
warning, and Python shows nothing from a library unless you ask:

.. code-block:: python

    import logging

    logging.basicConfig(level=logging.WARNING)

The log lines are shown with each case below.

The examples start from these lines:

.. code-block:: pycon

    >>> import uataq
    >>> from uataq import Network
    >>> wbb = uataq.get_site("WBB")

No data found
-------------

.. code-block:: pycon

    >>> wbb.get_obs("CO2", time_range="2021-08")
    WARNING:uataq.sites:Error reading lgr_ugga@WBB data from lin groupspace: No files found within the specified time range.
    Traceback (most recent call last):
      ...
    uataq.errors.ReaderError: No data found for ['lgr_ugga'] at WBB (lgr_ugga in lin groupspace).

Nothing in the archive holds data for that instrument, in that range, at the
level that was read. ``get_obs`` and ``get_recent_obs`` read the final level.
Three cases that gave this:

- A month with no final file (WBB, August 2021, above).
- Dates after a site stopped sending data but before its instruments have a
  removal date in the configuration. Once they have one, these dates raise
  the error under `Instrument inactive`_ instead.
- Dates in the future.

The name in the brackets is the **instrument** that measures what you asked for
(``lgr_ugga`` measures CO2 and CH4), not the pollutant, and the message does not
say which dates do exist. ``lin`` is the research group whose archive was
searched (see :ref:`input-group`). When the message lists several
instruments, ``name in lin groupspace`` means it was looked for and not found,
and ``name not read: ...`` means it was skipped, with the reason.

To find the dates that do exist, use :meth:`Network.get_availability`, and add
``"qaqc"`` to ``lvls`` to see whether the instrument measured at all.

Instrument inactive
-------------------

.. code-block:: pycon

    >>> wbb.get_obs("CO2", time_range="2010")
    WARNING:uataq.sites:Not reading lgr_ugga@WBB: lgr_ugga@WBB is inactive in given time_range
    Traceback (most recent call last):
      ...
    uataq.errors.ReaderError: No data found for ['lgr_ugga'] at WBB (lgr_ugga not read: lgr_ugga@WBB is inactive in given time_range).

The instrument was not installed at the site in that range. Its window is its
``active_range`` (see :ref:`The same in code <sites-in-code>`, on the
:doc:`sites_and_instruments` page). A range that only touches the window, such
as one that ends the day the instrument was installed, counts as outside it. A
range that overlaps the window only in part is cut down to it, with no error.

Dates after a site was taken down give this error too: HDP after 7 February
2025, and SUG's CO2 after 22 August 2025. That includes
``get_recent_obs("HDP", pollutants="CO2")``: nothing is recent at a site that
stopped.

Zero rows, no error
-------------------

.. code-block:: pycon

    >>> wbb_obs = wbb.get_obs("CO2", time_range="2024-03")
    >>> print(len(wbb_obs))
    206114
    >>> print(len(wbb.get_obs("CO2", time_range="2024-03-04")))
    0

The month has a file, but there are no rows on that day, at any level (``raw``
too): the instrument recorded nothing. You get an empty table and no warning, so
check ``len`` of what you get back. To see where the gaps in a month are, look at
the time between rows:

.. code-block:: pycon

    >>> import pandas as pd
    >>> gaps = wbb_obs.index.to_series().diff()
    >>> gaps[gaps > pd.Timedelta("6h")]
    Time_UTC
    2024-03-05 19:29:38   2 days 06:00:42
    2024-03-20 00:42:51   0 days 22:58:15
    2024-03-25 18:02:30   2 days 14:47:56
    Name: Time_UTC, dtype: timedelta64[us]

Each row is the time the data resumed and how long the gap before it was.

One of several pollutants missing
---------------------------------

.. code-block:: pycon

    >>> both = wbb.get_obs(["CO2", "O3"], time_range="2021-08")
    >>> both.columns.tolist()
    ['O3_ppb']

When you ask for several pollutants, the ones with data come back and the ones
without are dropped. There is no error, and no warning unless the log is on.
It raises ``ReaderError`` only when none of them has data. Check the columns you
got.

To go through many sites or months and skip the empty ones, catch the error:

.. code-block:: pycon

    >>> from uataq.errors import ReaderError
    >>> for sid in ["WBB", "SUG", "HDP"]:
    ...     try:
    ...         obs = uataq.get_obs(sid, "CO2", time_range="2025-06")
    ...         print(sid, len(obs), "rows")
    ...     except ReaderError:
    ...         print(sid, "has no CO2 data in June 2025")
    ...
    WBB 250687 rows
    SUG 239760 rows
    HDP has no CO2 data in June 2025

Pollutant or site not found
---------------------------

.. code-block:: pycon

    >>> uataq.get_obs("WBB", "NH3", time_range="2025-06")
    Traceback (most recent call last):
      ...
    ValueError: Invalid pollutant(s): '{'NH3'}'
    >>> uataq.get_obs("WBBB", "CO2", time_range="2025-06")
    Traceback (most recent call last):
      ...
    ValueError: Site 'WBBB' not found in the configuration file.

WBB does not measure NH3, or the name is misspelled; the message does not list
the valid names. Print ``sorted(site.pollutants)``. For a site, check the ID
against ``uataq.laboratory.sites``. The case does not matter for either.

``read_data`` has a similar error when you name an instrument the site does not
have (``InstrumentNotFoundError``, which lists the site's instruments).

A level the instrument does not have
------------------------------------

.. code-block:: pycon

    >>> uataq.read_data("WBB", "teledyne_t400", lvl="calibrated", time_range="2025-06")
    Traceback (most recent call last):
      ...
    FileNotFoundError: [Errno 2] No such file or directory: '.../wbb/teledyne_t400/calibrated'

The archive has no folder for that level for that instrument: not every
instrument has every level. Run :meth:`Network.get_availability` with the levels
you are curious about, or leave ``lvl`` out, which reads the highest level the
instrument has. A level that is not one of ``raw``, ``qaqc``, ``calibrated`` or
``final`` raises ``AssertionError: Invalid data level`` and lists the four.

Network surprises
-----------------

.. code-block:: pycon

    >>> uataq.get_network_obs(["HDP"], "CO2", time_range="2025-06")
    WARNING:uataq.sites:Error reading lgr_ugga@HDP data from lin groupspace: No files found within the specified time range.
    WARNING:uataq.network:Error reading data from HDP: No data found for ['lgr_ugga'] at HDP (lgr_ugga in lin groupspace).
    Traceback (most recent call last):
      ...
    uataq.errors.ReaderError: No data found for CO2 in any site.

None of the sites had data in the range. The log says why for each site.

.. code-block:: pycon

    >>> Network(["WBB", "WBBB"], "CO2")
    WARNING:uataq.network:Site 'WBBB' not found: Site 'WBBB' not found in the configuration file.
    Network(sites=['WBB'], pollutant='CO2')
    >>> Network(["WBBB"], "CO2")
    Traceback (most recent call last):
      ...
    ValueError: No sites found that measure pollutant 'CO2'. Valid sites: ['WBBB']

A misspelled site, or a site that does not measure the pollutant, is dropped from
a ``Network`` without an error, and only the log tells you. Print the
``Network`` to see the sites it kept. If none is left you get the second error,
whose "Valid sites" is just the list you typed, not a list of valid sites. Use
``Network("all", "CO2")`` to see the real ones. List each site once: a site
named twice is read twice, and its rows come back twice.

If the error is about ``time_range`` itself, see :ref:`input-time-range`.
