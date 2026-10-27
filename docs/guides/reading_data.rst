.. currentmodule:: uataq

Reading data
============

.. note::

    The examples on this page read the UATAQ archive, which is only
    available on CHPC. They are shown as code and are not run when the
    documentation is built. Where an example shows output, it is from a run on
    CHPC on 14 October 2026.

For a walk-through from a site to a month of data in local time and a plot,
start with :doc:`/getting_started/first_month`. This page shows the other ways to read: each
instrument's data on its own, all of a site's observations in one table, one
pollutant from several sites, and the mobile sites.

Research Sites
--------------

The :class:`~sites.Site` object is the primary interface for accessing data from a UATAQ site.
Each site has a unique site identifier (SID) that corresponds to a key in the configuration file.
The :data:`laboratory` is responsible for constructing :class:`~sites.Site` objects from the configuration file,
including building the :class:`~instruments.InstrumentEnsemble` for each site.
The :class:`~instruments.InstrumentEnsemble` is a container object that hold different
:class:`~instruments.Instrument` objects which provide the linkage between a :class:`~sites.Site` and the data files.

.. code-block:: python

    import uataq

    lab = uataq.laboratory
    sites = lab.sites          # list of sites
    wbb = lab.get_site('wbb')  # site object

For convenience, ``lab.get_site`` is also available as :func:`uataq.get_site`.

The :class:`~sites.Site` object contains the following information as attributes:

 - SID : The site identifier.
 - config : A dictionary containing configuration information for the site from the config file.
 - instruments : An instance of the InstrumentEnsemble class representing the instruments at the site.
 - groups : The research groups that collect data at the site.
 - loggers : The loggers used by research groups that record data at a site.
 - pollutants : The pollutants measured at the site.

There are two primary methods for reading data from a site:

1. `Reading Instrument Data`_ - Data for each instrument at a site is read individually and stored in a dictionary with the instrument name as the key.
2. `Getting Observations`_ - Finalized observations from all instruments at a site are aggregated into a single dataframe.

    :meth:`Site.read_data <uataq.sites.Site.read_data>` and
    :meth:`Site.get_obs <uataq.sites.Site.get_obs>` have been wrapped in
    :meth:`uataq.read_data` and :meth:`uataq.get_obs` respectively for convenience
    with an added `SID` parameter.

Reading Instrument Data
-----------------------

Using a :class:`~sites.Site` object we can read the data from each instrument
at the site for a specified time range:

.. code-block:: python

    data = wbb.read_data(instruments='all', time_range='2024-02')

With no ``lvl`` each instrument is read at the highest level it has, ``final``
for these. To read another level, such as ``lvl='qaqc'`` with its flagged rows,
pass ``lvl``: what each level is for, and how to choose one, is under
:ref:`input-level`.

The data is returned as a dictionary of pandas dataframes, one for each instrument.
The dataframes are indexed by time and have columns for each variable:

.. code-block:: python

    lgr_ugga = data['lgr_ugga']
    lgr_ugga.head()

Here ``lgr_ugga`` is indexed by ``Time_UTC`` and its columns are
``CO2d_ppm_cal``, ``CO2d_ppm_raw``, ``CH4d_ppm_cal``, ``CH4d_ppm_raw`` and
``H2O_ppm``. The columns of each level are on the :doc:`/reference/columns` page.

Getting Observations
--------------------

Or we can only get the finalized observations for a site which aggregates
the instruments into a single dataframe:

.. code-block:: python

    obs = wbb.get_obs(pollutants=['CO2', 'CH4', 'O3', 'NO2', 'NO', 'CO'],
                      time_range=['2024-02-08', '2024-02-15'])
    obs.head()

:ref:`What the final level keeps <what-final-keeps>` is explained on the
:doc:`/reference/columns` page, with the check that proves it. That page also says what
each column of each level holds.
The observations dataframe is indexed by time and aggregates pollutants into a single dataframe.
Two formats are available: ``wide`` or ``long``.
The ``wide`` format has columns for each pollutant
(``CO2d_ppm_cal``, ``CH4d_ppm_cal``, ``O3_ppb`` and so on; see :ref:`column-names`) and
the ``long`` format has a ``pollutant`` column with those names
and a ``value`` column with the measurement value.

.. code-block:: python

    obs_long = wbb.get_obs(pollutants=['CO2', 'CH4', 'O3', 'NO2', 'NO', 'CO'],
                           time_range=['2024-02-08', '2024-02-15'],
                           format='long')
    obs_long.head(10)

Mobile Sites & Observations
^^^^^^^^^^^^^^^^^^^^^^^^^^^

The mobile sites are instruments on TRAX trains and buses (the TRAX/eBus project).
The :class:`~sites.MobileSite` object is a subclass of the :class:`~sites.Site` object.
The :obj:`laboratory` determines whether to build a :class:`~sites.Site` or
:class:`~sites.MobileSite` object based on the ``is_mobile`` attribute in the configuration file.

Mobile sites provide the same functionality as fixed sites, but merge location
data with observations when using the :meth:`~sites.MobileSite.get_obs` method
and return a geodataframe.

Each instrument's rows are located with the GPS of the research group they were
read from, since that GPS was stamped by the same logger clock (see
:meth:`~sites.MobileSite.locate`). With no ``group`` given, a TRAX read can take
methane from lin and ozone from horel, each joined to its own group's GPS. The
``GPS_Group`` column says which GPS located each row. It also says which clock
the row's ``Time_UTC`` is on: lin rows are on GPS time, horel rows on the horel
logger's clock, which runs a few seconds ahead.

.. code-block:: python

    trx01 = lab.get_site('TRX01')
    mobile_data = trx01.get_obs(group='horel', time_range=['2019-07-01', '2019-07-08'])
    mobile_data.head()

Besides the pollutant columns (``O3_ppb`` and ``PM2.5_ugm3`` here), each row
has its position (``Latitude_deg``, ``Longitude_deg`` and ``geometry``), its
speed and course, and ``GPS_Group``.

Or in the long format:

.. code-block:: python

    mobile_data_long = trx01.get_obs(group='horel', time_range=['2019-07-01', '2019-07-08'], format='long')
    mobile_data_long.head()

.. _several-sites:

Several sites at once
---------------------

:func:`get_network_obs` reads one pollutant from several sites and stacks them in
one table:

.. code-block:: pycon

    >>> obs = uataq.get_network_obs(
    ...     ["WBB", "SUG", "RPK"], "CO2", time_range=["2025-06-01", "2025-06-08"]
    ... )
    >>> obs[["SID", "instrument", "CO2d_ppm_cal", "zagl"]].head(3)
                         SID instrument  CO2d_ppm_cal  zagl
    Time_UTC
    2025-06-01 00:00:03  WBB   lgr_ugga    432.407511    35
    2025-06-01 00:00:13  WBB   lgr_ugga    432.561390    35
    2025-06-01 00:00:23  WBB   lgr_ugga    433.129237    35
    >>> obs.groupby("SID").size()
    SID
    RPK    63936
    SUG    63936
    WBB    66821
    dtype: int64

The table is a ``geopandas.GeoDataFrame`` indexed by ``Time_UTC``. Besides the
concentration columns (:ref:`column-names`) each row has the ``SID`` and
``instrument`` it came from, its position (``Latitude_deg``, ``Longitude_deg``
and ``geometry``) and ``zagl`` (height above ground level, from the site's
configuration). It reads every instrument that measures the pollutant at the
highest level the archive has for it, which is the final level for the
instruments in these examples, and it takes only one pollutant per call.
:meth:`Network.get_obs` does the same from a ``Network`` you already made.

A site with nothing in the range is left out without an error. HDP stopped in
February 2025, so asking for June 2025 returns the other two sites:

.. code-block:: pycon

    >>> obs = uataq.get_network_obs(["WBB", "HDP", "CSP"], "CO2", time_range="2025-06")
    >>> sorted(obs["SID"].unique())
    ['CSP', 'WBB']

Look at the sites you got back, or ask :meth:`Network.get_availability` first.
