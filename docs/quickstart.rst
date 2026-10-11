.. currentmodule:: uataq

Quick Start
===========

.. note::

    The examples on this page read the UATAQ archive, which is only
    available on CHPC. They are shown as code and are not run when the
    documentation is built.

Laboratory
----------

It all starts in the lab...

.. code-block:: python

    import uataq

    lab = uataq.laboratory

The :data:`laboratory` object is a singleton instance of the :class:`~uataq._laboratory.Laboratory`
class which is initialized with the :doc:`UATAQ configuration file <config>`.
The configuration file is a JSON file which specifies UATAQ site characteristics
including name, location, status, research groups collecting data, and installed instruments.

The :class:`~uataq._laboratory.Laboratory` object contains the following attributes:

 - sites : A list of site identifiers.
 - instruments : A list of instrument names.

Research Sites
--------------

The :class:`~sites.Site` object is the primary interface for accessing data from a UATAQ site.
Each site has a unique site identifier (SID) that corresponds to a key in the configuration file.
The :data:`lab <laboratory>` is responsible for constructing :class:`~sites.Site` objects from the configuration file,
including building the :class:`~instruments.InstrumentEnsemble` for each site.
The :class:`~instruments.InstrumentEnsemble` is a container object that hold different
:class:`~instruments.Instrument` objects which provide the linkage between a :class:`~sites.Site` and the data files.

.. code-block:: python

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

    :meth:`Site.read_data` and :meth:`Site.get_obs` have been wrapped in
    :meth:`uataq.read_data` and :meth:`uataq.get_obs` respectively for convenience
    with an added `SID` parameter.

Reading Instrument Data
-----------------------

Using a :class:`~sites.Site` object we can read the data from each instrument
at the site for a specified processing lvl and time range:

.. code-block:: python

    data = wbb.read_data(instruments='all', lvl='qaqc', time_range='2024-02')

The data is returned as a dictionary of pandas dataframes, one for each instrument.
The dataframes are indexed by time and have columns for each variable:

.. code-block:: python

    lgr_ugga = data['lgr_ugga']
    lgr_ugga.head()

Here ``lgr_ugga`` is indexed by ``Time_UTC`` and its columns include
``CO2d_ppm``, ``CH4d_ppm``, ``ID`` and ``QAQC_Flag``.

Getting Observations
--------------------

Or we can only get the finalized observations for a site which aggregates
the instruments into a single dataframe:

.. code-block:: python

    obs = wbb.get_obs(pollutants=['CO2', 'CH4', 'O3', 'NO2', 'NO', 'CO'],
                      time_range=['2024-02-08', '2024-02-15'])
    obs.head()

Finalized observations only include data which has passed QAQC (``QAQC_Flag >= 0``)
and that are measurements of the ambient atmosphere (``ID == -10``).
The observations dataframe is indexed by time and aggregates pollutants into a single dataframe.
Two formats are available: ``wide`` or ``long``.
The ``wide`` format has columns for each pollutant
(``CO2d_ppm_cal``, ``CH4d_ppm_cal``, ``O3_ppb`` and so on; see :doc:`pollutants`) and
the ``long`` format has a ``pollutant`` column with those names
and a ``value`` column with the measurement value.

.. code-block:: python

    obs_long = wbb.get_obs(pollutants=['CO2', 'CH4', 'O3', 'NO2', 'NO', 'CO'],
                           time_range=['2024-02-08', '2024-02-15'],
                           format='long')
    obs_long.head(10)

Mobile Sites & Observations
^^^^^^^^^^^^^^^^^^^^^^^^^^^

Included as part of UATAQ is the TRAX/eBus project, which collects data from mobile sites.
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
