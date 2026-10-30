Configuration
=============

uataq's configuration is one JSON file,
`src/uataq/config.json <https://github.com/jmineau/uataq/blob/main/src/uataq/config.json>`_,
with an entry for each site: its name and location, the research groups that log
it, and its instruments with their dates. uataq reads it when it is imported, and
:doc:`/reference/sites_and_instruments` shows it as tables. A change at a site is
written in this file (see :doc:`/contributing`). This page lists its keys.

Site keys
---------

Each site is an entry of the configuration, keyed by its :term:`SID` (``WBB``).
It accepts:

``name``
    The site's name, such as ``"William Browning"``.
``latitude`` / ``longitude``
    A fixed site's position, in degrees (longitude is negative in Utah). A mobile
    site has neither: its ``gps`` gives the position of each measurement.
``zagl``
    The height above ground level of a fixed site's measurements, in meters.
``is_mobile``
    ``true`` for a site on a vehicle (a TRAX train or a bus), which
    :func:`~uataq.get_site` returns as a :class:`~uataq.sites.MobileSite`. Omit it
    for a fixed site.
``is_active``
    ``false`` marks a site that has been taken down. Nothing reads it: whether a
    site is active is decided by its instruments' ``removal_date``.
``loggers``
    The same map as an instrument's ``loggers`` (below), for every instrument at
    the site that does not give its own.
``instruments``
    The site's instruments, keyed by instrument name; each takes the keys
    below. Required.

Instrument keys
---------------

Each entry under a site's ``instruments`` accepts:

``loggers``
    Map of research group to the logger that group records the instrument
    with. Every group listed operates the instrument.
``installation_date`` / ``removal_date``
    When the instrument was installed at and removed from the site. Reads are
    clipped to this window. Omit ``removal_date`` while it is still installed.
    Each is an instant in UTC: a date alone is that day's midnight, and a time
    of day can follow it (``"2025-01-06 19:30:00"``), as at the MetOne swaps,
    where the ES642's ``removal_date`` is the ES405's ``installation_date``.
``group_dates`` (optional)
    Map of research group to a ``[start, stop]`` pair: the half-open window
    ``[start, stop)`` that group's archive holds this instrument's data for.
    Either end may be ``null`` for unbounded. Dates are exact instants, like
    ``installation_date``: a stop of ``"2017-10-28"`` means
    ``2017-10-28 00:00``. A group not listed covers the whole installation.

    Only needed when two groups log the same instrument but one archive
    stops early. When no group is named, a read crossing a window edge is
    split there, and each portion is read from the most preferred group whose
    window covers it: the default group first, then the order of
    ``loggers``. For example, TRX01's ``2b_205`` lists
    ``"lin": ["2015-05-13", "2017-10-28"]``, so an automatic read takes lin
    data through 2017-10-27 and horel data after it. The stop dates here are
    the midnight after lin's last sample.

    .. note::

        Some of horel's data are only at the ``raw`` level, so a
        ``final``-level read, as :meth:`~uataq.sites.Site.get_obs` makes, has a
        gap between lin's stop and horel's first ``final`` data, as in the example
        above: see :ref:`mobile-raw-only`.
``es642_column_dates`` (optional)
    Only for a ``metone_es405``: map of research group to a ``[start, stop]``
    pair, the half-open window ``[start, stop)`` in which that group's qaqc and
    final files give the instrument's values under the ``metone_es642``'s column
    names (``ES642_PM2.5_Concentration`` and so on). Inside the window the
    ES405 reads those columns as its own; outside it ignores them. Horel's
    files do this at BUS01 (``["2026-02-01", "2026-04-01"]``) and BUS02
    (``["2025-11-01", "2026-04-01"]``) for the months after each swap, and use
    the ES405's own names from April 2026.
``model`` (optional)
    The instrument class to use when it differs from the instrument's name.
``notes`` (optional)
    Free text; not read by the code.
