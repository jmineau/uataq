.. currentmodule:: uataq

When there is nothing to read
=============================

.. note::

    The examples on this page read the UATAQ archive, which is only available
    on CHPC. They are shown as code and are not run when the documentation is
    built. The output under each one is from a run on CHPC on 14 October 2026.
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
    WARNING:uataq.sites:Error reading lgr_ugga@WBB data from lin groupspace: No files found within the specified time range (files run from 2014-02 to 2026-10, with gaps).
    Traceback (most recent call last):
      ...
    uataq.errors.ReaderError: No final data found for CO2 at WBB: lgr_ugga in lin groupspace: No files found within the specified time range (files run from 2014-02 to 2026-10, with gaps).

Nothing in the archive holds data for that instrument, in that range, at the
level that was read. ``get_obs`` and ``get_recent_obs`` read the final level.
Three cases that gave this:

- A month with no final file (WBB, August 2021, above).
- Dates after a site stopped sending data but before its instruments have a
  removal date in the configuration. Once they have one, these dates raise
  the error under `Instrument inactive`_ instead.
- Dates in the future.

The message names what you asked for (``CO2``), the level that was read and the
site. Then it says, for each **instrument** that measures it (``lgr_ugga``
measures CO2 and CH4), what was found. ``lin`` is the research group whose
archive was searched (see :ref:`input-group`). The brackets say which files
exist: the first and last period they cover (a month at the final level), and
"with gaps" when a period in between has none, as August 2021 has none here.
When the message lists several instruments, ``name in lin groupspace`` means it
was looked for and not found, and ``name not read: ...`` means it was skipped,
with the reason.

A file can hold no rows, so the periods are not the days with data. To see those,
use :meth:`Network.get_availability`, and add ``"qaqc"`` to ``lvls`` to see
whether the instrument measured at all.

Instrument inactive
-------------------

.. code-block:: pycon

    >>> wbb.get_obs("CO2", time_range="2010")
    WARNING:uataq.sites:Not reading lgr_ugga@WBB: lgr_ugga@WBB is inactive in given time_range
    Traceback (most recent call last):
      ...
    uataq.errors.ReaderError: No final data found for CO2 at WBB: lgr_ugga not read: lgr_ugga@WBB is inactive in given time_range.

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
    <stdin>:1: EmptyResultWarning: No final data found for CO2 at WBB (2024-03-04 00:00:00 to 2024-03-05 00:00:00): the files for lgr_ugga exist but hold no data in that range.
    0

The month has a file, but there are no rows on that day, at any level (``raw``
too): the instrument recorded nothing. The read did not fail, so you get an empty
table and a warning, ``uataq.errors.EmptyResultWarning``. It is a Python warning,
so it shows without the log. ``get_recent_obs`` and ``get_network_obs`` warn the
same way when their table has no rows. To silence it, for a loop over days that
may be empty:

.. code-block:: python

    import warnings

    warnings.filterwarnings("ignore", category=uataq.errors.EmptyResultWarning)

To see where the gaps in a month are, look at the time between rows:

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
    WARNING:uataq.sites:Not reading lgr_ugga@HDP: lgr_ugga@HDP is inactive in given time_range
    WARNING:uataq.network:Error reading data from HDP: No data found for ['lgr_ugga'] at HDP: lgr_ugga not read: lgr_ugga@HDP is inactive in given time_range.
    Traceback (most recent call last):
      ...
    uataq.errors.ReaderError: No data found for CO2 in any site.

None of the sites had data in the range. The log says why for each site.

.. code-block:: pycon

    >>> Network(["WBB", "WBBB"], "CO2")
    WARNING:uataq.network:Site 'WBBB' not found: Site 'WBBB' not found in the configuration file.
    Network(sites=['WBB'], pollutant='CO2')
    >>> Network(["CSP"], "O3")
    Traceback (most recent call last):
      ...
    ValueError: No sites found that measure pollutant 'O3'. Sites that measure it: BUS01, BUS02, BUS03, BUS04, BUS05, BUS06, BUS07, BUS08, BUS09, BUS10, BUS11, BUS12, BUS13, BUS14, BUS15, TRX01, TRX02, TRX03, WBB.

A misspelled site, or a site that does not measure the pollutant, is dropped from
a ``Network`` without an error. The log warns about a misspelled site; a site
that does not measure the pollutant is dropped without a warning. Print the
``Network`` to see the sites it kept. If none is left you get the second error,
which lists the sites in the configuration that measure the pollutant, or says
that none does. A site named twice, in any case (``"WBB"`` and ``"wbb"``), is
read once.

If the error is about ``time_range`` itself, see :ref:`input-time-range`.
