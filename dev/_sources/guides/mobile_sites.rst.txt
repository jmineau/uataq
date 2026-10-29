.. currentmodule:: uataq

Mobile sites
============

.. note::

    The examples on this page read the UATAQ archive, which is only available
    on CHPC, and are not run when the documentation is built. The output under
    each one is from runs on CHPC on 26 October 2026.

The mobile sites are instruments on TRAX light-rail trains (``TRX01`` to
``TRX03``) and on buses (``BUS01`` and up) in the Salt Lake Valley. They have no
fixed position: each measurement is placed with the vehicle's GPS. They are read
with the same functions as the fixed sites, and this page says what is
different. :doc:`/reference/sites_and_instruments` lists them and their
instruments.

Where each measurement was
--------------------------

:func:`get_obs` at a mobile site gives a ``geopandas.GeoDataFrame``: the
concentrations, for each row the ``instrument`` that logged it, its position
(``Latitude_deg``, ``Longitude_deg`` and ``geometry``), the vehicle's speed and
course, and ``GPS_Group``:

.. code-block:: pycon

    >>> import uataq
    >>> trx01 = uataq.get_site("TRX01")
    >>> obs = trx01.get_obs(["CO2", "CH4", "O3"], time_range="2024-06-01")
    >>> obs.columns.tolist()
    ['CO2d_ppm_cal', 'CO2d_ppm_raw', 'CH4d_ppm_cal', 'CH4d_ppm_raw', 'O3_ppb', 'instrument', 'Latitude_deg', 'Longitude_deg', 'Altitude_msl', 'Speed_m_s', 'Course_deg', 'Speed_Estimated', 'Course_Estimated', 'geometry', 'GPS_Group']
    >>> obs["GPS_Group"].value_counts()
    GPS_Group
    horel    35135
    lin       8611
    Name: count, dtype: int64

It took 11 seconds. A row has values from one instrument, as at a fixed site
(see :doc:`/guides/read_data`): here 8,611 rows of CO2 and CH4 and 35,135 of
ozone. Where the GPS did not record a speed or course, they are computed from
the positions, and ``Speed_Estimated`` and ``Course_Estimated`` are ``True`` on
those rows.

.. _mobile-clocks:

Two groups, two clocks
----------------------

The trains carry instruments of both research groups (see :ref:`input-group`):
here the CO2 and CH4 analyzer is the lin group's and the ozone monitor is the
horel group's. Each group logs its instruments with its own clock and has its
own GPS, so uataq places each group's rows with that group's GPS.
``GPS_Group`` says which one placed a row, and so which clock its ``Time_UTC``
is on:

- ``lin``: GPS time.
- ``horel``: the horel logger's clock, which on TRX01 ran 1 to 20 seconds ahead
  of GPS time (dates sampled from 2019 to 2026), drifting between resets.

So two rows of different groups with the same ``Time_UTC`` can be seconds apart
in truth. Each row's position is right for its own time; to compare the two
groups' measurements, average over a period longer than that, such as a minute.
On a few days the lin computer's clock was hours or days off, and then a lin row
can have a ``Time_UTC`` outside the range you asked for.

To read one group only, name it. The horel group's GPS records no altitude, so
the table has no ``Altitude_msl``:

.. code-block:: pycon

    >>> o3 = trx01.get_obs("O3", group="horel", time_range="2024-06-01")
    >>> o3.columns.tolist()
    ['O3_ppb', 'instrument', 'Latitude_deg', 'Longitude_deg', 'Speed_m_s', 'Speed_Estimated', 'Course_deg', 'Course_Estimated', 'geometry', 'GPS_Group']

TRX01's CO2 and CH4
-------------------

TRX01's CO2 and CH4 analyzer has two :term:`instrument names <instrument name>`,
for two ways it was calibrated, and the same columns mean different things in
each:

.. list-table::
   :header-rows: 1
   :widths: 25 35 40

   * - Instrument
     - When it has data
     - Columns
   * - ``lgr_ugga``
     - Before November 2023, and May to August 2024
     - ``_cal`` is calibrated against reference tanks, ``_raw`` is not
       calibrated, as at the fixed sites.
   * - :term:`lgr_ugga_manual_cal`
     - 18 November 2023 to March 2024, and from 27 August 2024
     - No tanks. ``_raw`` holds the value calibrated by the analyzer's own
       software, and ``_cal`` is empty.

(The months are those of the files in the archive in October 2026.)
:func:`get_obs` reads both, and its ``instrument`` column says which one a row
came from. On 1 September 2024, ``_cal`` is empty:

.. code-block:: pycon

    >>> obs = trx01.get_obs(["CO2", "CH4", "O3"], time_range="2024-09-01")
    >>> obs.groupby("instrument")[["CO2d_ppm_cal", "CO2d_ppm_raw", "O3_ppb"]].count()
                         CO2d_ppm_cal  CO2d_ppm_raw  O3_ppb
    instrument
    2b_205                          0             0   26954
    lgr_ugga_manual_cal             0          7188       0

(The analyzer logged 7,200 rows that day; :func:`get_obs` keeps the 7,188 the
GPS could place.) So take ``_cal`` from the rows of ``lgr_ugga`` and ``_raw``
from those of ``lgr_ugga_manual_cal``. :func:`get_network_obs` has the same
``instrument`` column:

.. code-block:: pycon

    >>> net = uataq.get_network_obs(["TRX01"], "CO2", time_range="2024-09-01")
    >>> net[["SID", "instrument", "CO2d_ppm_cal", "CO2d_ppm_raw", "GPS_Group"]].head(3)
                           SID           instrument  CO2d_ppm_cal  CO2d_ppm_raw GPS_Group
    Time_UTC
    2024-09-01 00:00:07  TRX01  lgr_ugga_manual_cal           NaN      432.9656       lin
    2024-09-01 00:00:17  TRX01  lgr_ugga_manual_cal           NaN      432.9974       lin
    2024-09-01 00:00:27  TRX01  lgr_ugga_manual_cal           NaN      432.6543       lin

.. _mobile-raw-only:

Months that are only raw
------------------------

Some of the horel group's data are only at the ``raw`` level, so
:func:`get_obs`, which reads ``final``, has nothing for them (see
:doc:`/guides/data_levels_and_flags`):

- **The trains' ozone and particles before 19 November 2018**, from horel's
  first (pilot) archive. TRX01's ozone comes from the lin group until 27
  October 2017 (see :ref:`input-group`), so at the ``final`` level it has a gap
  from then to 19 November 2018.
- **The month of each particle monitor swap**, when the MetOne ES-642 was
  replaced by an ES-405: from the start of that month to the swap, on BUS03 in
  December 2024, BUS02 in March 2025, and TRX01, TRX02 and TRX03 in January 2025
  (with the trains' ozone too).

Read them with ``uataq.read_data(..., lvl="raw")``.

Next
----

- :doc:`/guides/find_sites_and_data`: when each vehicle has data.
- :doc:`/guides/errors`: what a read that finds nothing tells you.
