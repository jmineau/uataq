Utah Atmospheric Trace-gas and Air Quality (UATAQ)
==================================================

.. image:: https://zenodo.org/badge/DOI/10.5281/zenodo.22900090.svg
   :target: https://doi.org/10.5281/zenodo.22900090
   :alt: DOI

uataq reads UATAQ data: greenhouse-gas and air-quality measurements in northern
Utah, from fixed sites in the Salt Lake Valley, the mountains and valleys around
it and the Uintah Basin, and from instruments on TRAX light-rail trains and on
buses. Two research groups at the University of Utah keep the archives on CHPC:
John Lin's group (every fixed site, and some of the trains' instruments) and
John Horel's group (the buses, and the trains' other instruments). uataq reads
both, so you do not need to know where or how either stores its files.

It is written for members of the groups who work on CHPC, where the archives
are. A month of CO2 and CH4 from one site is one call:

.. code-block:: pycon

    >>> import uataq
    >>> obs = uataq.get_obs("WBB", ["CO2", "CH4"], time_range="2025-06")
    >>> obs.head(3)
                         CO2d_ppm_cal  CO2d_ppm_raw  CH4d_ppm_cal  CH4d_ppm_raw instrument
    Time_UTC
    2025-06-01 00:00:03    432.407511      435.5981      2.010693      2.010473   lgr_ugga
    2025-06-01 00:00:13    432.561390      435.7535      2.010209      2.009984   lgr_ugga
    2025-06-01 00:00:23    433.129237      436.3271      2.010649      2.010428   lgr_ugga

Every time in uataq is UTC. Start with :doc:`/getting_started/installation`,
then :doc:`/getting_started/first_data`.

- :doc:`getting_started/index`: install uataq and read your first data
- :doc:`guides/index`: find the sites and data you need, read them, and
  understand the data levels, the mobile sites and the errors
- :doc:`reference/index`: the sites, columns, arguments and configuration, and
  every function and class
- :doc:`contributing`: how uataq is laid out, and how to change it

.. _citing:

Citing the data
---------------

When you publish with UATAQ data, cite the papers that describe the
measurements:

- The fixed sites' CO2 and CH4: Bares et al. (2019), "The Utah urban carbon
  dioxide (UUCON) and Uintah Basin greenhouse gas networks: instrumentation,
  data, and measurement uncertainty", *Earth System Science Data* 11,
  1291–1308, `doi:10.5194/essd-11-1291-2019 <https://doi.org/10.5194/essd-11-1291-2019>`_.
- The TRAX trains: Mitchell et al. (2018), "Monitoring of greenhouse gases and
  pollutants across an urban area using a light-rail public transit platform",
  *Atmospheric Environment* 187, 9–23,
  `doi:10.1016/j.atmosenv.2018.05.044 <https://doi.org/10.1016/j.atmosenv.2018.05.044>`_.
- The electric buses (the Electric Bus Air Quality Observation Project, which
  began in July 2021): Mendoza et al. (2024), "Electric buses as an air
  pollution and meteorological observation network: Methodology and preliminary
  results", *Science of the Total Environment* 951, 175327,
  `doi:10.1016/j.scitotenv.2024.175327 <https://doi.org/10.1016/j.scitotenv.2024.175327>`_.

To cite uataq itself, use its DOI, in the badge at the top of this page.

.. toctree::
   :maxdepth: 2
   :hidden:

   getting_started/index
   guides/index
   reference/index
   contributing
