.. currentmodule:: uataq

Columns
=======

.. note::

    The output under each example on this page is from runs on CHPC on 12
    October 2026 (:ref:`why it is recorded <recorded-examples>`).

The columns you get depend on the **instrument** and on the **data level** you
read (``raw``, ``qaqc``, ``calibrated`` or ``final``; see :ref:`data-levels`). This page says what the columns are, level by level,
for the instruments you are most likely to use. Each section says which
instrument and level its examples come from.

.. _wide-tables:

The examples print wide tables. These two pandas settings print them in full,
whatever the width of your terminal:

.. code-block:: pycon

    >>> import pandas as pd
    >>> import uataq
    >>> pd.set_option("display.width", 120)
    >>> pd.set_option("display.max_columns", None)

In every table
--------------

- The index is ``Time_UTC``, the time of the measurement in UTC, without a time
  zone attached. :doc:`/getting_started/first_data` shows how to convert it to local time.
- The concentration columns follow one naming pattern for every instrument,
  level and research group: ``CO2d_ppm_cal``, ``O3_ppb``, ``PM2.5_ugm3`` and so
  on. `Column names`_ explains the pattern.
- :func:`get_obs` and :func:`get_network_obs` add an ``instrument`` column after
  the concentration columns, a text column that names the instrument each row
  came from. Take a mean with ``mean(numeric_only=True)`` to leave it out.
- uataq renames many of the instruments' other columns to common names, so
  that a quantity has the same name across instruments and groups. For example,
  the ``lgr_ugga``'s cavity pressure is ``Cavity_P_torr`` in the pipeline's
  files and ``Internal_P_torr`` in uataq. The renaming is in
  :data:`lin.column_mapping <uataq.filesystem.groupspaces.lin.column_mapping>`
  and
  :data:`horel.column_mapping <uataq.filesystem.groupspaces.horel.column_mapping>`.
  Keep this in mind when you read the pipeline's own documentation, which uses
  the names in its files.

.. _column-names:

Column names
------------

Concentration columns follow ``{pollutant}[d|channel]_{units}[_cal|_raw]``:
``O3_ppb``, ``CO2d_ppm_cal`` (dry mole fraction, calibrated), ``CH4d_ppm_raw``,
``PM2.5_ugm3``, ``BC6_ngm3`` (aethalometer channel 6).

.. code-block:: python

   import uataq
   from uataq.pollutants import concentration_columns, parse_column

   obs = uataq.get_obs("WBB", "CO2", time_range="2024-01")
   obs[concentration_columns("CO2", obs.columns)]  # CO2d_ppm_cal, not diagnostics
   parse_column("CH4d_ppm_raw")  # pollutant='CH4', units='ppm', dry=True, calibration='raw'

The two functions are documented on the :mod:`uataq.pollutants` page.

``_cal`` vs ``_raw``: in lin final data ``_cal`` is the calibrated value and
``_raw`` the uncalibrated one, except for TRX01's ``lgr_ugga_manual_cal``. That
exception, and the rows where ``_cal`` is empty, are explained under
:ref:`when-cal-is-empty`.

Labels, units and expected ranges for plotting are the same for every instrument,
so uataq leaves them to `lair <https://github.com/jmineau/lair>`_, the group's
atmospheric-science toolkit: ``lair.pollutants.get_pollutant("CH4").label()``.

The CO2 and CH4 analyzers
-------------------------

This section is about the lin group's greenhouse gas analyzers: the
``lgr_ugga`` (a Los Gatos Research analyzer, which measures CO2 and CH4) and the
``licor_6262`` and ``licor_7000`` (LI-COR analyzers, which measure CO2 only).
They are the only instruments with a ``calibrated`` level. Each row is one
record of the analyzer, about every 10 seconds. The examples read the
``lgr_ugga`` at WBB on 2 June 2025 and the ``licor_7000`` at SUG on the same day.


What each level holds, and which rows ``final`` keeps, is on
:doc:`/guides/data_levels_and_flags`.


Final
^^^^^

.. code-block:: pycon

    >>> final = uataq.read_data("WBB", "lgr_ugga", time_range="2025-06-02")["lgr_ugga"]
    >>> final.head(3)
                         CO2d_ppm_cal  CO2d_ppm_raw  CH4d_ppm_cal  CH4d_ppm_raw   H2O_ppm
    Time_UTC
    2025-06-02 00:00:01    431.852558      434.8026      1.981142      1.979105  7088.775
    2025-06-02 00:00:11    431.612346      434.5594      1.980728      1.978685  7101.099
    2025-06-02 00:00:21    431.812938      434.7615      1.980816      1.978773  7150.829

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Column
     - Meaning
   * - ``CO2d_ppm_cal``
     - CO2 dry mole fraction in ppm, calibrated against the site's reference
       tanks. Can be empty; see :ref:`when-cal-is-empty`.
   * - ``CO2d_ppm_raw``
     - The same measurement before calibration.
   * - ``CH4d_ppm_cal``, ``CH4d_ppm_raw``
     - The same for CH4, in ppm (``lgr_ugga`` only).
   * - ``H2O_ppm``
     - Water vapor in ppm, taken from the ``qaqc`` level.

The ``licor_7000`` has the same columns without the CH4 ones:

.. code-block:: pycon

    >>> uataq.read_data("SUG", "licor_7000", time_range="2025-06-02")["licor_7000"].columns.tolist()
    ['CO2d_ppm_cal', 'CO2d_ppm_raw', 'H2O_ppm']

:func:`get_obs` returns the concentration columns of this level, so
``get_obs("WBB", "CO2")`` gives ``CO2d_ppm_cal`` and ``CO2d_ppm_raw``.

Calibrated
^^^^^^^^^^

.. code-block:: pycon

    >>> cal = uataq.read_data("WBB", "lgr_ugga", lvl="calibrated", time_range="2025-06-02")["lgr_ugga"]
    >>> cal.columns.tolist()
    ['CO2d_ppm_cal', 'CO2d_ppm_raw', 'CO2d_m', 'CO2d_b', 'CO2d_n', 'CO2d_rsq', 'CO2d_rmse', 'ID_CO2', 'CH4d_ppm_cal', 'CH4d_ppm_raw', 'CH4d_m', 'CH4d_b', 'CH4d_n', 'CH4d_rsq', 'CH4d_rmse', 'ID_CH4', 'QAQC_Flag']
    >>> cal[["CO2d_ppm_cal", "CO2d_ppm_raw", "CO2d_m", "CO2d_b", "CO2d_n", "CO2d_rsq", "CO2d_rmse"]].head(3)
                         CO2d_ppm_cal  CO2d_ppm_raw    CO2d_m    CO2d_b  CO2d_n  CO2d_rsq  CO2d_rmse
    Time_UTC
    2025-06-02 00:00:01    431.852558      434.8026  1.010199 -1.454323       3  0.999998   0.060986
    2025-06-02 00:00:11    431.612346      434.5594  1.010198 -1.454345       3  0.999998   0.060964
    2025-06-02 00:00:21    431.812938      434.7615  1.010196 -1.454367       3  0.999998   0.060943

The pipeline calibrates each analyzer with the reference tanks it measures every
few hours: it fits a straight line between the tanks' measured and known
values, for every row. The pipeline's
`calibration page <https://github.com/uataq/data-pipeline/blob/main/Calibration.md>`_
describes the method. The fit columns, for CO2 (the CH4 ones start with
``CH4d_``):

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Column
     - Meaning
   * - ``CO2d_ppm_raw``
     - The uncalibrated value: the ``qaqc`` level's ``CO2d_ppm``. Empty on
       flagged rows (all 8,362 flush rows at WBB in June 2025), except rows
       flagged for an out-of-range reading, which keep it.
   * - ``CO2d_m``, ``CO2d_b``
     - The slope and intercept of the fit. The calibrated value is
       ``CO2d_ppm_cal = (CO2d_ppm_raw - CO2d_b) / CO2d_m``.
   * - ``CO2d_n``
     - How many reference tanks the fit used at that time. With one tank the fit
       is a slope only (``CO2d_b`` is 0). With none, there is no fit and
       ``CO2d_ppm_cal`` is empty.
   * - ``CO2d_rsq``, ``CO2d_rmse``
     - The fit's R² and root mean square error (in ppm). Empty when the fit used
       fewer than three tanks.
   * - ``ID_CO2``, ``ID_CH4``
     - What the analyzer was sampling; see :ref:`analyzer-id`.
   * - ``QAQC_Flag``
     - The ``qaqc`` level's flag, unless the calibration flagged the row itself
       (see :ref:`flags`).

The formula holds to rounding:

.. code-block:: pycon

    >>> ((cal["CO2d_ppm_raw"] - cal["CO2d_b"]) / cal["CO2d_m"] - cal["CO2d_ppm_cal"]).abs().max()
    np.float64(2.8421709430404007e-12)

QAQC
^^^^

.. code-block:: pycon

    >>> qaqc = uataq.read_data("WBB", "lgr_ugga", lvl="qaqc", time_range="2025-06-02")["lgr_ugga"]
    >>> qaqc.columns.tolist()
    ['CH4_ppm', 'CH4_ppm_sd', 'H2O_ppm', 'H2O_ppm_sd', 'CO2_ppm', 'CO2_ppm_sd', 'CH4d_ppm', 'CH4d_ppm_sd', 'CO2d_ppm', 'CO2d_ppm_sd', 'Internal_P_torr', 'Internal_P_torr_sd', 'Internal_T_C', 'Internal_T_C_sd', 'Ambient_T_C', 'Ambient_T_C_sd', 'RingDown0_us', 'RingDown0_us_sd', 'RingDown1_us', 'RingDown1_us_sd', 'Fit_Flag', 'ID', 'ID_CO2', 'ID_CH4', 'QAQC_Flag']

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Column
     - Meaning
   * - ``CO2_ppm``, ``CH4_ppm``, ``H2O_ppm``
     - The mole fractions in the sampled (wet) air, in ppm, not calibrated.
   * - ``CO2d_ppm``, ``CH4d_ppm``
     - The dry mole fractions, not calibrated. They are the ``_raw`` values of
       the ``calibrated`` and ``final`` levels.
   * - ``*_sd``
     - A standard deviation that the ``lgr_ugga``'s software writes beside each
       value (``[CO2]d_ppm_sd`` in the analyzer's own files). The LI-COR
       analyzers have none.
   * - ``Fit_Flag``
     - A status number that the ``lgr_ugga``'s software writes with each row.
       uataq and the pipeline pass it through unchanged, and the pipeline's
       QAQC does not use it. Every row of this day has 3.
   * - ``ID``, ``ID_CO2``, ``ID_CH4``
     - What the analyzer was sampling; see :ref:`analyzer-id`.
   * - ``QAQC_Flag``
     - The pipeline's flag; see :ref:`flags`.
   * - ``Internal_*``, ``Ambient_T_C``, ``RingDown*``
     - The analyzer's own measurements of its state (cavity pressure and
       temperature, and so on), with their ``_sd``.

The ``licor_6262`` and ``licor_7000`` have other instrument columns at this
level (flow, pressure, temperature, the logger's battery voltage). Print
``columns`` to see them. Their ``Analog_H2O_ppth`` is the analyzer's own water
vapor reading, in parts per thousand (not ppm like ``H2O_ppm``, which the
pipeline computes from the cavity's humidity and pressure).


Other instruments
-----------------

The lin group's other instruments (the Teledyne analyzers, the 2B ozone
monitor, the MetOne particle monitor, and so on) have no ``calibrated`` level
and no ``_cal`` or ``_raw`` columns. Their ``qaqc`` level has the instrument's
columns and ``QAQC_Flag``; their ``final`` level keeps the rows that pass
QAQC and only a few columns. For the ``teledyne_t400`` (ozone) at
WBB on 2 June 2025:

.. code-block:: pycon

    >>> ozone = uataq.read_data("WBB", "teledyne_t400", lvl="qaqc", time_range="2025-06-02")["teledyne_t400"]
    >>> ozone.columns.tolist()
    ['O3_ppb_std', 'O3_Meas_mV', 'O3_Ref_mV', 'O3_Gen_mV', 'O3_Drive_mV', 'Photo_Power_mV', 'Internal_P_inHgA', 'Flow_mLpm', 'Internal_T_C', 'Photo_Lamp_T_C', 'O3_Scrub_T_C', 'O3_Gen_T_C', 'Instrument_T_C', 'Slope', 'Offset', 'O3_ppb', 'Test_mV', 'QAQC_Flag']
    >>> uataq.read_data("WBB", "teledyne_t400", time_range="2025-06-02")["teledyne_t400"].columns.tolist()
    ['O3_ppb']

The pipeline lists the columns of every instrument and level in its
`data_config.json <https://github.com/uataq/data-pipeline/blob/main/config/data_config.json>`_,
with the names in its files, before uataq renames them.

The horel group's instruments
-----------------------------

The TRAX trains and the buses also carry instruments run by the horel group
(ozone, particles, NOx; see :ref:`input-group`). Their ``qaqc`` and ``final`` levels
are read from the same horel files, and their columns are named like the lin
group's. The ``qaqc`` level of the ozone monitor (``2b_205``) on TRX01 on 1 June
2024 has:

.. code-block:: pycon

    >>> o3 = uataq.read_data("TRX01", "2b_205", lvl="qaqc", group="horel", time_range="2024-06-01")["2b_205"]
    >>> o3.columns.tolist()
    ['O3_ppb', 'Flow_Lpm', 'Internal_T_C', 'Internal_P_hPa', 'QAQC_Flag']

Their flags are 0 or -1 (see :ref:`flags`).

Next
----

- :doc:`/guides/data_levels_and_flags`: what each level is for, what ``final``
  keeps, the flags, and the rows where ``_cal`` is empty.
- :mod:`uataq.pollutants`: the functions that pick the concentration columns out of a
  table and parse their names.
