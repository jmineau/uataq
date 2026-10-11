Configuration
=============

The UATAQ configuration is defined as a ``json`` file which specifies UATAQ
site characteristics including name, location, status, research groups
collecting data, and installed instruments.

.. warning::

    Changes to UATAQ site infrastructure, including instrument
    installation/removal, must be reflected in the configuration
    file for the lab to be able to properly access the data.

Instrument keys
---------------

Each entry under a site's ``instruments`` accepts:

``loggers``
    Map of research group to the logger that group records the instrument
    with. Every group listed operates the instrument.
``installation_date`` / ``removal_date``
    When the instrument was installed at and removed from the site. Reads are
    clipped to this window. Omit ``removal_date`` while it is still installed.
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

        horel's TRX ozone and particulate data are raw-only (the pilot
        archive) before 2018-11-19, so a ``final``-level read, as
        :meth:`~uataq.sites.Site.get_obs` makes, has a gap between lin's stop
        and 2018-11-19.
``model`` (optional)
    The instrument class to use when it differs from the instrument's name.
``notes`` (optional)
    Free text; not read by the code.

.. literalinclude:: /../src/uataq/config.json
    :language: json
    :caption: uataq/config.json
