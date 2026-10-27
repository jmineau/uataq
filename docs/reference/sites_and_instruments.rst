.. currentmodule:: uataq

Sites and instruments
=====================

The tables on this page are made from the package's
:doc:`configuration </reference/config>` each time the documentation is built, so they
always match the version of uataq they document. They say what the
configuration says, not what the archive holds: to see which days have data,
use :doc:`/guides/what_data_exists`. The words in the headings are explained in the
:ref:`glossary <glossary>` at the end of the page. Every site is in Utah, so the
local time of all of them is ``America/Denver`` (see :ref:`first-month-utc`).

In both site tables:

- **Active** is "yes" when at least one instrument at the site has no removal
  date in the configuration. Otherwise it gives the date the last instrument
  was removed. A site can stop sending data before its instruments are marked
  removed, so check with :doc:`/guides/what_data_exists` before you plan on recent data.
- **Groups** are the research :term:`groups <group>` whose archives hold the
  site's data.
- **Pollutants** are every pollutant measured at the site, by its instruments
  past and present. **Instruments** gives the dates each one was there; reads
  are cut to those dates.

Fixed sites
-----------

.. site-catalog::

Mobile sites
------------

Instruments on TRAX trains (``TRX``) and buses (``BUS``). These
:term:`mobile sites <mobile site>` have no fixed location: the position of each
measurement comes from the site's ``gps``.

.. site-catalog::
   :mobile:

Instruments
-----------

One row per :term:`instrument name` in the configuration, with the class that
reads it and the pollutants it measures. The class pages are under
:mod:`uataq.instruments`, and what the columns of each level hold is on the
:doc:`/reference/columns` page.

``cr1000`` and ``gps`` have no pollutants: one is a datalogger that records
housekeeping (battery voltage, enclosure temperature), the other a GPS receiver.
``get_obs`` never reads them, ``read_data`` does, and a :term:`mobile site`'s
``get_obs`` uses its ``gps`` to place each measurement.

.. instrument-catalog::

.. _sites-in-code:

The same in code
----------------

Everything in these tables comes from objects you can use yourself. This block
runs when the documentation is built, so its output is current:

.. ipython:: python

    import uataq
    from uataq import Network

    site = uataq.get_site("WBB")
    site.config["name"], site.config["zagl"]
    sorted(site.pollutants)
    [instrument.name for instrument in site.instruments]
    site.instruments["teledyne_t400"].active_range
    type(site.instruments["teledyne_t400"]).__name__

``uataq.laboratory.sites`` lists every site ID, and ``site.config`` holds the
site's own keys (see :doc:`/reference/config`). ``repr(site)``, which is what a notebook
shows for ``site``, prints the whole entry, with the ``notes`` of the instruments
that have one: why its dates are what they are, and where its data end.

Pollutant names are upper case (``NOx`` is ``'NOX'`` here), but you can type
them in any case when you read data. To go the other way and find the sites that
measure a pollutant, make a :class:`Network` of ``"all"`` sites. A ``Network``
is a list of sites and one pollutant; it is how the package asks a question
across sites:

.. ipython:: python

    Network("all", "CH4")

An instrument's window, its ``active_range``, says when it was installed, not
when it recorded data. That is why ``PM2.5`` is in WBB's list although both of
WBB's PM2.5 instruments, ``metone_es642`` and ``teom_1400ab``, have an end date:

.. ipython:: python

    print("\n".join(f"{i.name:15} {i.active_range}" for i in site.instruments))

.. _glossary:

Glossary
--------

.. glossary::

    SID
        The site ID: the key of a site in the configuration, such as ``WBB``
        or ``TRX01``. It is the first argument of :func:`read_data`,
        :func:`get_obs` and :func:`get_site`, which turn it to upper case, so
        ``"wbb"`` works too. Each site also has a longer ``name`` (the Name
        column above).

    mobile site
        A site on a vehicle: a TRAX train (``TRX``) or a bus (``BUS``). Its
        configuration says ``"is_mobile": true`` and has no latitude or
        longitude. :func:`get_site` gives a :class:`~sites.MobileSite` for it,
        whose :meth:`~sites.MobileSite.get_obs` adds the position of each
        measurement from the site's ``gps``. Every other site is a fixed site
        (:class:`~sites.Site`), with its latitude and longitude in the
        configuration.

    zagl
        The height above ground level of a fixed site's measurements, in
        meters, from the site's configuration. :func:`get_network_obs` gives
        it in a column of the same name. Mobile sites have none.

    group
        The research group whose archive holds an instrument's data: ``lin``
        (John Lin's group: every fixed site, and some of the TRAX
        instruments) or ``horel`` (John Horel's group: the buses and the
        other TRAX instruments). Some TRAX instruments are in both archives,
        for different years. ``group=None``,
        the default of every read, picks the group for you; see
        :ref:`input-group`. ``uataq.filesystem.groups`` holds the two groups'
        readers.

    logger
        How a group records an instrument, which sets the format of its
        ``raw`` files. The configuration gives it per site or per instrument,
        under ``loggers``: ``{"lin": "campbellsci"}``. The lin group's loggers
        are ``campbellsci`` (monthly ``.dat`` files from a Campbell Scientific
        datalogger), :term:`air-trend` (daily ``.csv`` files) and ``lgr_ugga``
        (the daily ``.txt`` files the Los Gatos analyzer writes itself). The
        horel group's only logger is ``campbellsci``. For lin, the logger
        matters only at the ``raw`` level: the lin pipeline writes the other
        levels in a format of its own.

    air-trend
        A lin :term:`logger`. The lin pipeline's
        `README <https://github.com/uataq/data-pipeline#raw>`_ says the raw
        files with a ``csv`` extension "are recorded via a raspberry pi
        running `air-trend <https://github.com/jmineau/air-trend>`_". There
        is one file per day, named by its date.

    instrument name
        The key of an instrument under a site's ``instruments`` in the
        configuration, such as ``lgr_ugga`` or ``teledyne_t400``. It is what
        you pass to ``read_data(..., instruments=...)``, the key of the
        dictionary :func:`read_data` returns, and the name of the instrument's
        folder in the lin archive. uataq reads it with the class that
        :data:`uataq.instruments.catalog` gives for the entry's ``model``, or
        for the name itself when the entry has no ``model``. The class says
        which pollutants the instrument measures.

    lgr_ugga_manual_cal
        A second :term:`instrument name` for TRX01's ``lgr_ugga``, from
        2023-11-18. The note in the configuration says: "Removed calibration
        tank and manually calibrated with lgr software periodically." It has
        ``"model": "lgr_ugga"``, so it is read like any ``lgr_ugga``, from a
        folder of its own in the lin archive. For what its ``_cal`` and
        ``_raw`` columns hold, see :ref:`when-cal-is-empty`. The
        configuration also lists TRX01's ``lgr_ugga`` with no removal date; to
        see which of the two has data in a period, use :doc:`/guides/what_data_exists`.
