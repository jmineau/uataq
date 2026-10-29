.. currentmodule:: uataq

Read data
=========

.. note::

    The examples on this page read the UATAQ archive, which is only available
    on CHPC, and are not run when the documentation is built. The output under
    each one is from runs on CHPC on 26 October 2026, except under "One
    pollutant from several sites" (the HDP example, 14 October 2026).

:doc:`/getting_started/first_data` reads one site. This page shows the other
reads: several pollutants and several sites in one table, everything an
instrument logged at any level, and reads of a year or more. Three functions
do the reading:

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Function
     - What it gives
   * - :func:`get_obs`
     - One site's concentrations at the ``final`` level, in one table.
   * - :func:`get_network_obs`
     - One pollutant from several sites, in one table, with the site,
       instrument and position of each row.
   * - :func:`read_data`
     - Everything one or more instruments logged, at any level, as one table
       per instrument.

The arguments they share (site, pollutants, time range and the rest) are
described once, on :doc:`/reference/input_parameters`. Every time is UTC
(see :ref:`first-data-utc`).

Several pollutants from one site
--------------------------------

Name the pollutants in a list. WBB measures ozone with another instrument than
CO2 and CH4:

.. code-block:: pycon

    >>> import pandas as pd
    >>> import uataq
    >>> obs = uataq.get_obs("WBB", ["CO2", "CH4", "O3"], time_range="2025-06-02")
    >>> obs.head(3)
                             CO2d_ppm_cal  CO2d_ppm_raw  CH4d_ppm_cal  CH4d_ppm_raw  O3_ppb
    Time_UTC
    2025-06-02 00:00:01.000    431.852558      434.8026      1.981142      1.979105     NaN
    2025-06-02 00:00:01.740           NaN           NaN           NaN           NaN    58.7
    2025-06-02 00:00:03.780           NaN           NaN           NaN           NaN    58.6
    >>> obs.notna().sum()
    CO2d_ppm_cal     8390
    CO2d_ppm_raw     8390
    CH4d_ppm_cal     8390
    CH4d_ppm_raw     8390
    O3_ppb          41937
    dtype: int64

**Each instrument logs on its own times**, so a row has values from one
instrument and is empty in the other columns. The CO2 and CH4 analyzer logs
about every 10 seconds, the ozone monitor about every 2. To put them on common
times, average them over a period, as under :doc:`/getting_started/first_data`
("Hourly means"): ``obs.resample("h").mean()``.

With ``format="long"``, the table has one row per measurement instead, with the
column name in ``pollutant`` and the measurement in ``value``:

.. code-block:: pycon

    >>> long = uataq.get_obs("WBB", ["CO2", "CH4", "O3"], time_range="2025-06-02", format="long")
    >>> long.head(5)
                                pollutant       value
    Time_UTC
    2025-06-02 00:00:01.000  CO2d_ppm_cal  431.852558
    2025-06-02 00:00:01.000  CO2d_ppm_raw  434.802600
    2025-06-02 00:00:01.000  CH4d_ppm_cal    1.981142
    2025-06-02 00:00:01.000  CH4d_ppm_raw    1.979105
    2025-06-02 00:00:01.740        O3_ppb   58.700000

.. _several-sites:

Several sites and pollutants
----------------------------

For several sites, read each one and stack them. This reads June 2025 at three
sites in Mountain time (as under :ref:`first-data-local-month`), averages each
to hourly means, and stacks them with the site ID as the first level of the
index:

.. code-block:: pycon

    >>> frames = {}
    >>> for sid in ["WBB", "CSP", "HPL"]:
    ...     obs = uataq.get_obs(sid, ["CO2", "CH4"], time_range=["2025-06-01", "2025-07-01"])
    ...     obs = obs.tz_localize("UTC").tz_convert("America/Denver").loc["2025-06"]
    ...     frames[sid] = obs.resample("h").mean()
    ...
    >>> hourly = pd.concat(frames, names=["SID"])
    >>> hourly.head(3)
                                   CO2d_ppm_cal  CO2d_ppm_raw  CH4d_ppm_cal  CH4d_ppm_raw
    SID Time_UTC
    WBB 2025-06-01 00:00:00-06:00    441.390343    444.442363      2.003455      2.003101
        2025-06-01 01:00:00-06:00    440.615488    443.567585      1.996306      1.995796
        2025-06-01 02:00:00-06:00    435.172711    437.986351      1.995488      1.994749
    >>> hourly.groupby(level="SID").size()
    SID
    CSP    720
    HPL    720
    WBB    720
    dtype: int64

It took 2 seconds. Every site's hourly means are on the same hours, so one
pollutant can be laid out with a column per site:

.. code-block:: pycon

    >>> hourly["CH4d_ppm_cal"].unstack("SID").head(3)
    SID                             WBB       CSP       HPL
    Time_UTC
    2025-06-01 00:00:00-06:00  2.003455  2.293712  2.035616
    2025-06-01 01:00:00-06:00  1.996306  2.433641  2.013554
    2025-06-01 02:00:00-06:00  1.995488  2.233682  2.049384

This loop is the way to read a few pollutants from a few sites. Use
:func:`get_network_obs`, below, for one pollutant when you need the position,
height or instrument of each row.

A site with no data in the range raises an error (see :doc:`/guides/errors`,
which shows a loop that skips such a site). :doc:`/guides/find_sites_and_data`
says which sites measure a pollutant.

One pollutant from several sites
--------------------------------

:func:`get_network_obs` reads one pollutant from several sites and stacks the
rows in time, with the site and instrument of each row and where it was
measured:

.. code-block:: pycon

    >>> net = uataq.get_network_obs(["WBB", "CSP", "HPL"], "CH4", time_range="2025-06-02")
    >>> net[["SID", "instrument", "CH4d_ppm_cal", "zagl"]].head(3)
                         SID instrument  CH4d_ppm_cal  zagl
    Time_UTC
    2025-06-02 00:00:01  WBB   lgr_ugga      1.981142    35
    2025-06-02 00:00:07  HPL   lgr_ugga      1.967279     4
    2025-06-02 00:00:11  WBB   lgr_ugga      1.980728    35
    >>> net.groupby("SID").size()
    SID
    CSP    6226
    HPL    8427
    WBB    8390
    dtype: int64

The table is a ``geopandas.GeoDataFrame``. Besides the concentration columns
(:ref:`column-names`), each row has its ``SID``, its ``instrument``, its
position (``Latitude_deg``, ``Longitude_deg`` and ``geometry``) and ``zagl``,
the height of the measurements above ground level. It takes one pollutant per call:
several pollutants at sites with different instruments have no common shape.
:meth:`Network.get_obs` does the same from a :class:`Network` you already made.

A site with nothing in the range is left out without an error. HDP stopped in
February 2025, so asking for June 2025 returns the other two sites:

.. code-block:: pycon

    >>> net = uataq.get_network_obs(["WBB", "HDP", "CSP"], "CO2", time_range="2025-06")
    >>> sorted(net["SID"].unique())
    ['CSP', 'WBB']

Check the sites you got back.

Which instrument a row came from
--------------------------------

:func:`get_obs` reads every instrument at the site that measures the pollutant.
At a fixed site its table does not say which instrument a row came from. Most
fixed sites have one instrument for each pollutant at a time, but some have had
two, one after another or at once (WBB measured NO2 with two in 2022). When it
matters, use :func:`get_network_obs`, whose ``instrument`` column says, or read
each instrument by name with :func:`read_data`. At a mobile site, :func:`get_obs`
has the ``instrument`` column too (see :doc:`/guides/mobile_sites`).
:doc:`/reference/sites_and_instruments` lists the instruments of every site,
with their dates.

Everything an instrument logged
-------------------------------

:func:`read_data` reads instruments by name and gives a dictionary with one
table for each, at the level you ask for (see
:doc:`/guides/data_levels_and_flags`):

.. code-block:: pycon

    >>> data = uataq.read_data("WBB", "lgr_ugga", lvl="qaqc", time_range="2025-06-02")
    >>> list(data)
    ['lgr_ugga']
    >>> data["lgr_ugga"].shape
    (8845, 25)

The ``qaqc`` table has every row the analyzer logged and all 25 of its columns
(:doc:`/reference/columns` says what they are). With no ``lvl``, each instrument
is read at the highest level it has. With no instrument named, it reads every
instrument at the site; the ones with nothing in the range are left out, and
the log says why (see :doc:`/guides/errors`):

.. code-block:: pycon

    >>> data = uataq.read_data("WBB", time_range="2025-06-02")
    >>> {name: table.shape for name, table in data.items()}
    {'lgr_ugga': (8390, 5), 'teledyne_t200': (41937, 3), 'teledyne_t300': (41937, 1), 'teledyne_t400': (41937, 1)}

Sites as objects
----------------

``get_obs``, ``read_data`` and ``get_recent_obs`` take the site ID first and pass
the call on to a site object, which you can also get yourself: ``uataq.get_obs("WBB", ...)`` is
``uataq.get_site("WBB").get_obs(...)``, and the same for the other two. A site object also says what the site measures and which
instruments it has (see :ref:`sites-in-code`).

.. _large-reads:

A year or more
--------------

A year of CO2 and CH4 at WBB at the ``final`` level is 2.8 million rows. It took
4 seconds to read and about 0.6 GB of memory. For a year or more of several
sites, run your script in a Slurm job (see :ref:`install-slurm`), not on a login
node, and average to hourly means as you read each site, as above, so the
table you keep stays small.

``num_processes`` reads an instrument's files in several processes at once (see
:ref:`input-num-processes`). It helps most when there are many files, as at
the ``raw`` level and in :meth:`Network.get_availability` (see
:doc:`/guides/find_sites_and_data`), and it also speeds up the ``final`` level.
On a compute node on 29 October 2026, WBB's CO2 and CH4 for 2024 (2.8 million
rows) took 3.4 seconds with one process, 2.3 with two, 1.3 with four and 1.0 with
eight; six years of CO2 (16 million rows) took 21, 7.0 and 4.7 seconds with one,
four and eight. Ask for no more processes than cores you were given. A script that uses more than one process needs the
``__main__`` guard, or Python 3.14 stops with a ``RuntimeError`` about
"bootstrapping" (Python 3.14 starts the workers with forkserver, and a script read
from stdin cannot spawn them, so run a script file):

.. code-block:: python

    import uataq


    def main():
        obs = uataq.get_obs("WBB", "CO2", time_range="2024", num_processes=4)
        ...


    if __name__ == "__main__":
        main()

Other data
----------

:mod:`uataq.sodar` reads the wind profiles of the horel group's SODAR stations.
They are not UATAQ sites, so they are read with :class:`~uataq.sodar.Sodar`
rather than the functions on this page; its page has an example.

Next
----

- :doc:`/guides/data_levels_and_flags`: the levels, the flags, and what
  ``final`` keeps.
- :doc:`/guides/mobile_sites`: the TRAX trains and the buses, and where each
  measurement was.
- :doc:`/guides/errors`: what a read that finds nothing tells you.
