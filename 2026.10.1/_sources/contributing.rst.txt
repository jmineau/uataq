Contributing
============

Contributions are welcome. `CONTRIBUTING.md <https://github.com/jmineau/uataq/blob/main/CONTRIBUTING.md>`_
explains how to set up a development environment, run the checks, and propose a change.
`AGENTS.md <https://github.com/jmineau/uataq/blob/main/AGENTS.md>`_ is the short guide
for contributors and coding agents: the rules the code keeps, the commands, and the
gotchas. This page holds the development setup on CHPC and the longer notes it points
to: the module layout, how to add
an instrument or a group space, how the docs are organized and generated, and what the
mobile clocks, the MetOne swap files, data availability and the SODAR archive need.

Development setup
-----------------

This sets up a copy of uataq to change and send back, the way its maintainer
works. Three tools do the work:

* `uv <https://docs.astral.sh/uv/>`_ installs the packages the project needs
  into a ``.venv`` folder inside your copy of the code, at the versions
  recorded in ``uv.lock``.
* `just <https://just.systems/>`_ runs the project's named tasks, listed in
  its ``justfile`` (``just --list`` shows them). ``uv sync`` installs it, and
  you run it as ``uv run just``.
* `pre-commit <https://pre-commit.com/>`_ checks your changes for style
  problems each time you ``git commit``, before the commit is made.

uataq needs uv 0.12 or newer, and CHPC's ``uv`` module is older (0.11.14 in
October 2026). Install your own copy with pip. Do this in a shell where the
uataq environment is not active: run ``deactivate`` first, or pip stops with
``Can not perform a '--user' install``.

.. code-block:: bash

   module load python
   pip install --user uv
   uv --version

The last command should print ``uv 0.12`` or newer. Then get the code and set
it up:

.. code-block:: bash

   git clone https://github.com/jmineau/uataq.git
   cd uataq
   uv sync                       # the packages, into .venv (about two minutes)
   uv run pre-commit install     # turn on the checks at commit time

To run the checks that CI runs (lint, types, docstrings and the tests), use a
compute node, not the login node:

.. code-block:: bash

   srun --account=lin-np --partition=lin-np --nodes=1 --ntasks=1 --cpus-per-task=4 --mem=8G --time=00:30:00 uv run just quality-check

It takes about a minute and ends with the number of tests that passed. The tests do
not need the archive, so you can also develop on your own computer.
`CONTRIBUTING.md <https://github.com/jmineau/uataq/blob/main/CONTRIBUTING.md>`_
has the rest of the workflow: branches and pull requests.

To work on the code while you use it for your own analysis, install your clone
into the environment from the steps above (an *editable* install, which runs
the code in your folder as you change it):

.. code-block:: bash

   source ~/venvs/uataq/bin/activate
   cd uataq
   pip install -e .

If ``uv sync`` fails with ``Required uv version ... does not match the running
version``, you are running CHPC's ``uv`` module: run ``module unload uv`` and open
a new shell so your own copy comes first.

Module layout
-------------

::

    src/uataq/
      __init__.py        read_data, get_obs, get_recent_obs, get_network_obs;
                         re-exports laboratory, get_site, Network, DEFAULT_GROUP,
                         TimeRange and the modules below
      config.json        sites and instruments; read at import (importlib.resources)
      _laboratory.py     Laboratory: builds sites and instruments from config.json
      sites.py           Site (stationary) and MobileSite (GPS-located rows)
      instruments.py     Instrument ABC, one subclass per model, and `catalog`
      network.py         Network: many sites, one pollutant (GeoDataFrame);
                         get_availability / plot_availability
      pollutants.py      column grammar {pollutant}[d|channel]_{units}[_cal|_raw]:
                         concentration_columns, parse_column, POLLUTANTS
      gps.py             haversine, bearing, estimate_speed_course,
                         gps_time_from_time_of_day
      sodar.py           Horel/MesoWest SODAR profiles (Sodar, list_stations);
                         standalone, not in config.json, not imported by uataq
      timerange.py       TimeRange and the TimeRangeTypes alias
      errors.py          ReaderError and its subclasses, ParserError, EmptyResultWarning,
                         DroppedPollutantWarning, ...
      filesystem/
        __init__.py      DEFAULT_GROUP, get_group; re-exports core
        core.py          DataFile, GroupSpace, groups, lvls, list_files,
                         filter_datafiles, parse_datafiles, cpu_count
        groupspaces/     one module per research group's archive (lin, horel)
    tests/               pytest
    docs/                Sphinx; docs/_ext/ holds two local extensions

How a read flows: ``laboratory`` (a process-wide singleton built at import) holds
the ``Site`` objects; ``get_site(SID)`` returns one, and the top-level functions
delegate to it. A ``Site`` asks each ``Instrument`` which group to read each part of
the range from (``plan_reads``); the instrument gets its files from that group's
``GroupSpace`` (``filesystem.groups[name]``), whose ``DataFile`` classes parse them;
the frames are standardized to uataq's column names and concatenated in time.
In one ``Site.read_data`` call, a file that several instruments read is parsed
once (horel's finalized CSVs hold a whole platform): ``filesystem.core._parse_once``
holds a dict, by path, until the call returns, and ``HorelCSVFile.parse`` keeps
its parse there for the other instruments, which copy their own columns.
``filesystem.lvls`` ranks the levels (``raw`` < ``qaqc`` < ``calibrated`` <
``final``).

Adding an instrument or a group space
-------------------------------------

A change at a site (an instrument installed, removed or swapped) must be written
in ``config.json``, or uataq cannot read the data; :doc:`/reference/config` lists its
keys.

**A new instrument.** An ``Instrument`` subclass in ``instruments.py`` (and a
``DataFile`` in the group's module if the format is new), its entry in
``config.json`` with dates and ``notes``, and parser tests on synthetic lines.

**A new group space.** Add ``filesystem/groupspaces/<name>.py`` with a
``GroupSpace`` subclass, its ``DataFile`` classes and a ``column_mapping`` dict (the
group's column names to uataq's, applied by its ``standardize_data``), modeled on
``lin.py`` and ``horel.py``, and register it at the bottom of that module:
``filesystem.groups["<name>"] = <Name>Group()``. Nothing else needs to import it:
``groupspaces/__init__.py`` star-imports every non-underscore module in the folder.
Its API page appears by itself ("Functions and modules" lists ``filesystem``
recursively).

Writing the docs
----------------

Each fact is written on one page, and the other pages link to it (the rules for
writing are in AGENTS.md). This table says which page holds which kind of fact. A
change that moves a fact, or renames or retitles a page, updates its row here.

.. list-table::
   :header-rows: 1
   :widths: 60 40

   * - Fact
     - Page
   * - What UATAQ is, a first example, how to cite the data
     - the front page (``docs/index.rst``)
   * - Install, Jupyter on Open OnDemand, Slurm jobs, updating and pinning
     - :doc:`/getting_started/installation`
   * - A first read, UTC and local time, hourly means, what to write down
     - :doc:`/getting_started/first_data`
   * - Which sites measure what, when a site has data, the newest data
     - :doc:`/guides/find_sites_and_data`
   * - Several pollutants and sites, ``get_network_obs``, ``read_data``, large reads
     - :doc:`/guides/read_data`
   * - The data levels, which level a read gives, ``ID``, what ``final`` keeps, flags, empty ``_cal``
     - :doc:`/guides/data_levels_and_flags`
   * - Mobile sites: positions, the two clocks, TRX01's two LGR names, raw-only months
     - :doc:`/guides/mobile_sites`
   * - Errors and empty results
     - :doc:`/guides/errors`
   * - Sites, instruments, their dates, glossary
     - :doc:`/reference/sites_and_instruments`
   * - Columns of each instrument and level, column names
     - :doc:`/reference/columns`
   * - Arguments: site, instruments, pollutants, format, group, level, time range (every form), processes
     - :doc:`/reference/input_parameters`
   * - Config keys
     - :doc:`/reference/config`
   * - Development setup and developer notes
     - Contributing (this page)
   * - Function and class details, what a module is for
     - the docstrings, on the generated API pages (:doc:`/reference/functions_and_modules`)

The front page (``docs/index.rst``) lists four sections, which are the navbar:
Getting started, Guides and Reference (each a folder of ``docs/`` with an
``index.rst`` that lists its pages, in the left sidebar) and this page. A new page
goes in the folder of its section and on that section's ``index.rst``.

**Examples that run in the build.** In an ``.. ipython:: python`` block, ``@savefig
name.png`` above a plot keeps the figure, and ``:okexcept:`` or ``:okwarning:``
allows a block meant to raise or warn.

**Examples that need the archive.** These pages show the output of a run on CHPC in
plain ``code-block`` or ``pycon`` blocks, because the docs build (and CI) has no
archive: your first data, find sites and data (except its first section), read
data, data levels and flags, mobile sites, errors, columns and input parameters.

**The site and instrument tables are generated.** The ``site-catalog`` and
``instrument-catalog`` directives in ``docs/reference/sites_and_instruments.rst``
(``docs/_ext/catalog.py``) build them from ``uataq.laboratory`` and
``uataq.instruments.catalog`` on every build.

**The API reference is generated.** ``docs/reference/functions_and_modules.rst``
lists the functions and modules, and each module, class, function and class member gets
a page in ``docs/api/`` (gitignored; a ``:toctree:`` pointing outside ``docs/`` litters the
repo root). A module's docstring is its page's text. ``docs/_templates/autosummary/``
and ``docs/_ext/api_pages.py`` (from python-template, which keeps class members from
being described twice) build the pages.

Clocks on mobile platforms
--------------------------

The TRAX and bus platforms carry instruments from two groups, each stamped by its
own logger clock:

- **lin**: the instruments and the GPS are stamped by the platform's Pi computer,
  whose clock cannot always be trusted. The Pi's time is kept as ``Pi_Time``, and
  lin's GPS supplies ``Time_UTC``, which is GPS time.
- **horel**: ``Time_UTC`` is the CR1000 logger's clock, which on TRX01 ran 1 to
  20 s ahead of GPS time on dates sampled from 2019 to 2026, drifting between
  resets. horel's raw GPS files
  log the receiver's own time of day (``GTIM``, read as ``Instrument_Time``), so
  :meth:`~uataq.instruments.GPS.read_data` adds ``GPS_Time_UTC`` for horel, dated
  from the logger clock across midnight and NaT on rows without a fix. The index
  stays on the logger clock, so it still lines up with the logger's other
  columns. horel's qaqc and final files have no ``GTIM``: their ozone and
  particulate rows stay on logger time, and nothing in them can correct it.

:meth:`~uataq.sites.MobileSite.locate` therefore joins each group's rows to that
group's own GPS on its own clock: lin's on ``Pi_Time``, horel's on ``Time_UTC``
(there the instrument and GPS values are one record). Joining horel's rows to lin's
GPS on the Pi clock would place them that many seconds along the track, and drop
the rows with no lin GPS record at their second.
``locate`` replays each instrument's ``plan_reads`` to split its frame by group, and
``_gps_group`` raises ``ValueError`` rather than borrow another group's GPS.

The Pi's clock has itself been hours to days off GPS time (on TRX01 about 70
minutes behind all of 2016-11-09 and 10, and up to 5 days in 2022-11). A GPS read
selects fixes by ``Time_UTC``, GPS time, while lin's rows were selected by the Pi's
clock, so ``locate`` reads lin's GPS a week past the rows' range on each side
(``_PI_CLOCK_MARGIN`` in ``sites.py``); otherwise the rows near the ends of a range
would find no fix and be dropped. A located lin row's ``Time_UTC`` can then fall
outside the requested range by as much as the Pi was off.

Each located row carries ``GPS_Group`` (``"lin"`` or ``"horel"``): which GPS located
it, and so which clock its ``Time_UTC`` is on. A TRAX read with no group can mix
the two groups' GPS, which log at different rates and with different columns, so
filter or compare by it. A GPS group that cannot be read leaves only its own rows
unlocated, with a warning; if none can be read, ``locate`` raises
``ReaderError``.

The MetOne swap files
---------------------

At five MetOne swaps (ES642 to ES405) horel split the month's raw files in two:
``{SID}_{YYYY}_{MM}_esampler.h5`` holds the ES405's rows from the swap on, and
``{SID}_{YYYY}_{MM}_esampler.h5_prior405upgrade`` the ES642's rows from the start of
the month to the swap (BUS02 2025-03, BUS03 2024-12, TRX01, TRX02 and TRX03
2025-01). TRX01 to TRX03's ``2b`` and ``cr1000`` folders have the same split for
January 2025, so their ozone and GPS rows before the swap are only in a
``prior405upgrade`` file too. The two files of a month share no timestamp. horel's
qaqc and final files have none of these rows, so raw is the only level with them.

The suffix is :data:`uataq.filesystem.groupspaces.horel.PRIOR_405_SUFFIX`.
``HorelGroup.get_datafiles`` adds the suffixed file to every raw read except the
ES405's, and clipping each instrument to its installed window keeps the two
MetOne models' rows apart. The clipped range drives both the file selection and the
row slice, and both are needed: groups reuse a file name across an instrument change
(horel calls both MetOne models ``esampler``), so a monthly file that straddles a
swap holds the replacement's rows. At each swap the ES642's ``removal_date`` and the
ES405's ``installation_date`` are the same instant, so a sample at that instant
belongs to the ES405 alone. Other suffixes in horel's raw folders
(``TRX01_2024_02_cr1000.h5_bad``, which is empty, and the pilot archive's
``cr1000/old/*.h5_old``) are not read. The four LI-COR 6262 to 7000 swaps (DBK,
HEB, RPK, SUG) are in separate lin folders, so their files cannot mix, but the
same date rule holds.

Data availability internals
---------------------------

:meth:`~uataq.Network.get_availability` parses every file rather than
trusting file listings: horel's qaqc and final files hold a whole platform, so a
file existing says nothing about one pollutant (it can hold -9999 ozone for most of
a month while the raw 2B file is full).

- A time bin counts for a level when any row in it has a non-null value in a column
  :func:`~uataq.pollutants.concentration_columns` picks (``O3_ppb``,
  ``CO2d_ppm_cal``, ``CO2d_ppm_raw``, ``BC6_ngm3``; not diagnostics such as
  ``O3_Meas_mV`` or ``O3_ppb_std``). ``_raw`` columns count (``raw=True``), as in
  ``Network.get_obs``: they are the only populated ones for TRX01's
  ``lgr_ugga_manual_cal``. Each bin takes the highest level present, so "measured
  but not in final" shows as qaqc or raw.
- With no group, every group operating the instrument is checked, ignoring
  ``group_dates``: availability reports what each archive holds, while ``get_obs``
  reads one group per portion.
- One pool runs over the whole network's files, and each worker reduces its file
  to bins at once, so memory is one file per worker. A file that cannot be read is
  logged and skipped, and the count is reported. Rows with a NaT ``Time_UTC`` are
  dropped before ``standardize_data``.
- :meth:`~uataq.Network.plot_availability` (matplotlib, an optional import)
  colors levels by ``uataq.network.LEVEL_COLORS``, one hue from light (raw) to
  dark (final). Compute the availability once and pass it in to restyle.
- ``Network("all", pollutant)`` is every configured site that measures it. Ozone at
  every site over every year is thousands of files: run it in a Slurm job with
  ``num_processes="max"``, from a script file with a ``__main__`` guard (Python 3.14
  starts workers with forkserver, and a script read from stdin cannot spawn them).

The SODAR archive
-----------------

:mod:`uataq.sodar` reads the Horel group's MesoWest SODAR archive, under
``sodar_data/hdf5archive/`` in
:data:`uataq.filesystem.groupspaces.horel.MESOWEST_DIR`:

- ``{SID}_full_metadata_log.h5``: ``/metagroup/metadata`` and
  ``/metagroup/variables``, the variables indexed by ``SHORTNAME`` with a ``MULT``
  scale factor each.
- ``{SID}_{YYYY}_{MM}_sodar.h5``: the table ``/obsdata/observations``, with
  ``STATION_ID``, ``DATTIM`` (epoch seconds) and one ``(n_levels,)`` integer column
  per profile field (``HEIGHT``, ``WS``, ``WD``, ``MXWS``). ``-9999`` becomes NaN,
  and each variable in the metadata log is divided by its ``MULT``.

Stations seen: USDR1 to USDR5, WSLSA, WSMLI. Stray files
(``USDR2_2018_12_sodar_p1.h5``, ``all_sodar_metadata.h5``, ``_Processed/``) do not
match the exact-name pattern and are ignored. Monthly files are concatenated along
``Time_UTC`` with an outer join, which pads with NaN if the number of range gates
changes; :meth:`~uataq.sodar.Sodar.get_winds_at_height` matches the height at every
timestamp.

SODAR is standalone, outside ``config.json``, ``Instrument`` and ``GroupSpace``,
because its stations are MesoWest stations rather than UATAQ sites, its output is
two-dimensional ``(Time_UTC, level)``, which the pandas ``DataFile`` pipeline
cannot carry, and its scale factors live in a per-station file outside the data
file. Only ``lvl="raw"`` exists; any other level raises ``ValueError``.
