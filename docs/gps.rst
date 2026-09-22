GPS
===

Great-circle geometry and motion estimated from positions.

Receivers that log only ``GPGGA`` sentences record position but neither speed
nor course. :class:`uataq.instruments.GPS` fills both from the positions when
they are missing, and marks every filled value with the boolean columns
``Speed_Estimated`` / ``Course_Estimated``. Recorded values are never
overwritten.

.. code-block:: python

   import uataq

   gps = uataq.read_data("trx01", instruments="gps", time_range="2017-03")["gps"]
   moving = gps[gps.Speed_m_s > 1.0]  # works in the GPGGA-only years too

Validated against a day of recorded 1 Hz speed and course from the TRAX
platform: correlation 0.995, median speed difference 0.00 m/s and median course
error 0.4 degrees while moving. Position noise becomes speed noise, so widen
:attr:`~uataq.instruments.GPS.estimate_window` before thresholding a stationary
platform.

.. automodule:: uataq.gps
   :members:
