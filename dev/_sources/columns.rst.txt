.. currentmodule:: uataq

Columns and flags
=================

.. note::

    The examples on this page read the UATAQ archive, which is only available
    on CHPC. They are shown as code and are not run when the documentation is
    built. The output under each one is from runs on CHPC on 12 October 2026.
    If the data are reprocessed, the numbers can change a little.

The columns you get depend on the **instrument** and on the **data level** you
read (``raw``, ``qaqc``, ``calibrated`` or ``final``; see :doc:`first_month` for
what each level is for). This page says what the columns are, level by level,
for the instruments you are most likely to use. Each section says which
instrument and level its examples come from.

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
  zone attached. :doc:`first_month` shows how to convert it to local time.
- The concentration columns follow one naming pattern for every instrument,
  level and research group: ``CO2d_ppm_cal``, ``O3_ppb``, ``PM2.5_ugm3`` and so
  on. `Column names`_ explains the pattern.
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

The two functions are documented on the :doc:`pollutants` page.

``_cal`` vs ``_raw``: in lin final data ``_cal`` is the calibrated value and
``_raw`` the uncalibrated one, except for TRX01's ``lgr_ugga_manual_cal``. That
exception, and the rows where ``_cal`` is empty, are explained under
:ref:`when-cal-is-empty`.

Labels, units and expected ranges for plotting are instrument-independent and
live in ``lair.pollutants`` (``get_pollutant("CH4").label()``).

The CO2 and CH4 analyzers
-------------------------

This section is about the lin group's greenhouse gas analyzers: the
``lgr_ugga`` (a Los Gatos Research analyzer, which measures CO2 and CH4) and the
``licor_6262`` and ``licor_7000`` (LI-COR analyzers, which measure CO2 only).
They are the only instruments with a ``calibrated`` level. Each row is one
record of the analyzer, about every 10 seconds. The examples read the
``lgr_ugga`` at WBB on 2 June 2025 and the ``licor_7000`` at SUG on the same day.

.. list-table::
   :header-rows: 1
   :widths: 15 85

   * - Level
     - What it has
   * - ``final``
     - The concentrations and ``H2O_ppm``, for the outside-air rows that passed
       QAQC. No ``ID`` or flag columns.
   * - ``calibrated``
     - Every row, with the calibrated and uncalibrated concentrations, the
       calibration fit, the ``ID_CO2`` (and ``ID_CH4``) columns and
       ``QAQC_Flag``.
   * - ``qaqc``
     - Every row, with all of the analyzer's columns, ``ID``, ``ID_CO2`` (and
       ``ID_CH4``), and ``QAQC_Flag``. Not calibrated.
   * - ``raw``
     - The analyzer's columns as they were logged, with ``ID`` but without
       ``ID_CO2``, ``ID_CH4`` or ``QAQC_Flag``. Reading one day of the WBB
       ``lgr_ugga`` at this level took 159 seconds, against 1 or 2 seconds at
       the others.

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
       tanks. Can be empty; see `When _cal is empty`_.
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
     - What the analyzer was sampling; see `What the analyzer was sampling`_.
   * - ``QAQC_Flag``
     - The ``qaqc`` level's flag, unless the calibration flagged the row itself
       (see `Flags`_).

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
     - What the analyzer was sampling; see the next section.
   * - ``QAQC_Flag``
     - The pipeline's flag; see `Flags`_.
   * - ``Internal_*``, ``Ambient_T_C``, ``RingDown*``
     - The analyzer's own measurements of its state (cavity pressure and
       temperature, and so on), with their ``_sd``.

The ``licor_6262`` and ``licor_7000`` have other instrument columns at this
level (flow, pressure, temperature, the logger's battery voltage). Print
``columns`` to see them.

What the analyzer was sampling
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The analyzers do not only sample the outside air. A valve switches them to the
reference tanks for a few minutes every few hours, and the rows logged while the
lines are flushed after a switch are marked as well. Three columns say which is
which.

``ID`` is the label logged with each row. For the ``lgr_ugga`` it is **text**,
the description set on the analyzer's Multi Inlet Unit (the valve box).
``ID_CO2`` and ``ID_CH4`` are **numbers** that the pipeline makes from it:

.. code-block:: pycon

    >>> qaqc.groupby(["ID", "ID_CO2", "ID_CH4"]).size()
    ID                      ID_CO2   ID_CH4
    ~406.49~1.91             406.49   1.91       70
    ~478.24~2.62             478.24   2.62       63
    ~520.00~5.63             520.00   5.63       63
    ~Atmosphere~Atmosphere  -10.00   -10.00    8390
    ~flush~flush            -99.00   -99.00     259
    dtype: int64

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - ``ID_CO2`` / ``ID_CH4``
     - Meaning
   * - ``-10``
     - The outside air (``ID`` is ``~Atmosphere~Atmosphere``).
   * - ``-99``
     - A flush (``ID`` is ``~flush~flush``).
   * - a positive number
     - A reference tank. The number is the tank's known CO2 (or CH4) in ppm,
       which ``ID`` holds as ``~CO2~CH4``.

So for the ``lgr_ugga``, select the outside air with ``ID_CO2 == -10``.
``ID == -10`` selects no rows, because ``ID`` is text.

For the ``licor_6262`` and ``licor_7000``, ``ID`` is already a number, with the
same codes, and ``ID_CO2`` is equal to it. They have no ``ID_CH4``:

.. code-block:: pycon

    >>> licor = uataq.read_data("SUG", "licor_7000", lvl="qaqc", time_range="2025-06-02")["licor_7000"]
    >>> licor["ID"].value_counts()
    ID
    -10.00     7992
    -99.00      459
     398.22      60
     453.73      60
     487.55      60
     524.29       5
    Name: count, dtype: int64
    >>> (licor["ID"] == licor["ID_CO2"]).all()
    np.True_

.. _what-final-keeps:

**The tank rows pass QAQC.** The flush rows are flagged (``-2``), but the
reference tank rows have flag 0, like the outside air:

.. code-block:: pycon

    >>> pd.crosstab(qaqc["ID_CO2"], qaqc["QAQC_Flag"])
    QAQC_Flag   -2     0
    ID_CO2
    -99.00     259     0
    -10.00       0  8390
     406.49      0    70
     478.24      0    63
     520.00      0    63

So ``QAQC_Flag >= 0`` alone keeps the tank rows. The ``final`` level is the
``calibrated`` rows of the outside air that pass QAQC:

.. code-block:: pycon

    >>> kept = cal[(cal["ID_CO2"] == -10) & (cal["QAQC_Flag"] >= 0)]
    >>> len(kept), len(final)
    (8390, 8390)
    >>> kept.index.equals(final.index)
    True

The same holds for the ``licor_7000`` at SUG that day (7,992 rows). The
``final`` level follows the ``calibrated`` level's flags, which can differ from
the ``qaqc`` level's because the calibration adds flags of its own. For the
``licor_6262`` at SUG in June 2019, the calibration flagged 566 rows ``-4``;
the rule above gives the 238,632 ``final`` rows from the ``calibrated`` level,
but 239,149 from the ``qaqc`` level.

.. _when-cal-is-empty:

When _cal is empty
^^^^^^^^^^^^^^^^^^

Some rows of the ``final`` level have a ``_raw`` value and an empty ``_cal``.
There are two reasons.

**The instrument has no calibrated level.** The pipeline then fills only the
``_raw`` columns. This is the case for TRX01's :term:`lgr_ugga_manual_cal`,
whose ``_raw`` columns hold the value the LGR software calibrated, not an
uncalibrated one:

.. code-block:: pycon

    >>> trax = uataq.read_data("TRX01", "lgr_ugga_manual_cal", time_range="2024-09-01")["lgr_ugga_manual_cal"]
    >>> trax.notna().sum()
    CO2d_ppm_cal       0
    CO2d_ppm_raw    7200
    CH4d_ppm_cal       0
    CH4d_ppm_raw    7200
    H2O_ppm         7200
    dtype: int64

**There was no calibration fit at that time** (``CO2d_n`` is 0). These rows are
not flagged, so they are in the ``final`` level. The pipeline calibrates each
calendar year on its own, so the hours of a new year before the first tank
measurement have no fit. At WBB on 1 January 2025:

.. code-block:: pycon

    >>> jan1 = uataq.read_data("WBB", "lgr_ugga", time_range="2025-01-01")["lgr_ugga"]
    >>> empty = jan1["CO2d_ppm_cal"].isna() & jan1["CO2d_ppm_raw"].notna()
    >>> int(empty.sum()), jan1.index[empty].max()
    (824, Timestamp('2025-01-01 02:14:01'))

The ``calibrated`` level shows the fit starting as the analyzer measures the
three tanks, one after another. Here is the first row with each value of
``CO2d_n``:

.. code-block:: pycon

    >>> cal = uataq.read_data("WBB", "lgr_ugga", lvl="calibrated", time_range="2025-01-01T02")["lgr_ugga"]
    >>> cols = ["CO2d_ppm_raw", "CO2d_ppm_cal", "CO2d_n", "CO2d_b", "CO2d_rsq", "ID_CO2"]
    >>> cal.drop_duplicates("CO2d_n")[cols]
                         CO2d_ppm_raw  CO2d_ppm_cal  CO2d_n    CO2d_b  CO2d_rsq  ID_CO2
    Time_UTC
    2025-01-01 02:00:00      445.0774           NaN       0       NaN       NaN  -10.00
    2025-01-01 02:15:48      406.0314    406.425037       1  0.000000       NaN  406.49
    2025-01-01 02:18:44      477.9684    478.134889       2 -1.685318       NaN  478.24
    2025-01-01 02:21:40      519.6304    519.871474       3 -0.750496  0.999997  520.00

The same happens after the last tank measurement of a year (at WBB from 23:14
on 31 December 2024). In every case seen, CO2 and CH4 were empty on the same
rows.

To find these rows in your data:

.. code-block:: python

    empty = df["CO2d_ppm_cal"].isna() & df["CO2d_ppm_raw"].notna()

Their ``_raw`` value is not calibrated.

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
    ['O3_std_ppb', 'O3_Meas_mV', 'O3_Ref_mV', 'O3_Gen_mV', 'O3_Drive_mV', 'Photo_Power_mV', 'Internal_P_inHgA', 'Flow_mLpm', 'Internal_T_C', 'Photo_Lamp_T_C', 'O3_Scrub_T_C', 'O3_Gen_T_C', 'Instrument_T_C', 'Slope', 'Offset', 'O3_ppb', 'Test_mV', 'QAQC_Flag']
    >>> uataq.read_data("WBB", "teledyne_t400", time_range="2025-06-02")["teledyne_t400"].columns.tolist()
    ['O3_ppb']

The pipeline lists the columns of every instrument and level in its
`data_config.json <https://github.com/uataq/data-pipeline/blob/main/config/data_config.json>`_,
with the names in its files, before uataq renames them.

The horel group's instruments
-----------------------------

The TRAX trains and the buses also carry instruments run by the horel group
(ozone, particles, NOx; see :ref:`input-group`). Their ``qaqc`` and ``final`` levels
are read from the same horel files. For the ozone (``2b_205``) and particle
(``metone_es642``, ``metone_es405``) monitors, the horel files mark a flagged
row with 1, and uataq turns that into ``QAQC_Flag = -1``, so the flag is 0
(passes) or -1 (flagged). The ``final`` level is the ``qaqc`` rows that pass and
have a value. The days before a vehicle's ES-642 was replaced by an ES-405
(from the start of that month: December 2024 on BUS03, March 2025 on BUS02,
January 2025 on TRX01, TRX02 and TRX03, with the trains' ozone too) are only
at the ``raw`` level: horel's ``qaqc`` and ``final`` files do not have them.
For the ``2b_205`` on TRX01 on 1 June 2024:

.. code-block:: pycon

    >>> o3 = uataq.read_data("TRX01", "2b_205", lvl="qaqc", group="horel", time_range="2024-06-01")["2b_205"]
    >>> o3.columns.tolist()
    ['O3_ppb', 'Flow_Lpm', 'Internal_T_C', 'Internal_P_hPa', 'QAQC_Flag']
    >>> o3["QAQC_Flag"].value_counts()
    QAQC_Flag
     0    39134
    -1     4066
    Name: count, dtype: int64
    >>> final_o3 = uataq.read_data("TRX01", "2b_205", group="horel", time_range="2024-06-01")["2b_205"]
    >>> kept = o3[(o3["QAQC_Flag"] >= 0) & o3["O3_ppb"].notna()]
    >>> kept.index.equals(final_o3.index)
    True

The ``-1`` of a horel row means only that the horel group flagged it. The flag
numbers on the pipeline's page are the lin group's.

Flags
-----

``QAQC_Flag`` is in the ``qaqc`` and ``calibrated`` levels of the lin
group's instruments, and in the ``qaqc`` level of the horel group's ozone and
particle monitors. **Zero and positive flags pass; a negative flag fails**,
and its number says why. The ``final`` level has no flag column: it holds only
rows that passed.

What each number means is on the pipeline's
`QAQC flag page <https://github.com/uataq/data-pipeline/blob/main/QAQC_Flags.md>`_,
grouped by instrument, with the calibration's own flags under *Calibration*. It
names the columns as they are in the pipeline's files (see `In every table`_):
its ``Flow_CCmin``, for example, is uataq's ``Flow_mLpm``, or ``Flow_Lpm`` for
the ``2b_205``.

Next
----

- :doc:`pollutants`: the functions that pick the concentration columns out of a
  table and parse their names.
- :doc:`first_month`: what each data level is for, and times in local time.
