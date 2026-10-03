Pollutants
==========

How UATAQ names concentration columns, and how to pick them out.

Concentration columns follow ``{pollutant}[d|channel]_{units}[_cal|_raw]``:
``O3_ppb``, ``CO2d_ppm_cal`` (dry mole fraction, calibrated), ``CH4d_ppm_raw``,
``PM2.5_ugm3``, ``BC6_ngm3`` (aethalometer channel 6).

.. code-block:: python

   import uataq
   from uataq.pollutants import concentration_columns, parse_column

   obs = uataq.get_obs("WBB", "CO2", time_range="2024-01")
   obs[concentration_columns("CO2", obs.columns)]  # CO2d_ppm_cal, not diagnostics
   parse_column("CH4d_ppm_raw")  # pollutant='CH4', units='ppm', dry=True, calibration='raw'

``_cal`` vs ``_raw``: in lin final data ``_cal`` is the calibrated value and
``_raw`` the uncalibrated one, except for TRX01's ``lgr_ugga_manual_cal``
(from 2023-11-18), which leaves ``_cal`` empty and writes the LGR-software
calibrated value to ``_raw``.

Labels, units and expected ranges for plotting are instrument-independent and
live in ``lair.pollutants`` (``get_pollutant("CH4").label()``).

.. automodule:: uataq.pollutants
   :members:
