.. currentmodule:: uataq

Columns and flags
=================

.. note::

    The examples on this page read the UATAQ archive, which is only available
    on CHPC. They are shown as code and are not run when the documentation is
    built. The output under each one is from runs on CHPC on 12 October 2026,
    except in `The start of a month`_, which is from 13 October 2026. If the
    data are reprocessed, the numbers can change a little.

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
  on. The
  :doc:`pollutants` page explains the pattern of the names (the ``d`` means a
  dry mole fraction, the last part is the unit).
- uataq renames many of the instruments' other columns to common names, so
  that a quantity has the same name across instruments and groups. For example,
  the ``lgr_ugga``'s cavity pressure is ``Cavity_P_torr`` in the pipeline's
  files and ``Internal_P_torr`` in uataq. The renaming is in
  :data:`lin.column_mapping <uataq.filesystem.groupspaces.lin.column_mapping>`
  and
  :data:`horel.column_mapping <uataq.filesystem.groupspaces.horel.column_mapping>`.
  Keep this in mind when you read the pipeline's own documentation, which uses
  the names in its files.

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

When _cal is empty
^^^^^^^^^^^^^^^^^^

Some rows of the ``final`` level have a ``_raw`` value and an empty ``_cal``.
There are two reasons.

**The instrument has no calibrated level.** The pipeline then fills only the
``_raw`` columns. This is the case for TRX01's ``lgr_ugga_manual_cal`` (see
:doc:`pollutants` for what its ``_raw`` holds):

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
not flagged, so they are in the ``final`` level. This happens at the turn of a
year and, at four sites, at the start of each month written since the archive
was last rewritten (see `The start of a month`_). The pipeline calibrates each
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

The start of a month
^^^^^^^^^^^^^^^^^^^^

The ``lgr_ugga`` at four sites (WBB, CSP, HPL and FRU) has a second kind of
empty stretch: the first hours of a month, in UTC. In the months written since
the site's archive was last rewritten (the dates are below), ``CO2d_ppm_cal``
and ``CH4d_ppm_cal`` are empty from the first row of the month until a few hours
in, while the ``_raw`` columns and ``H2O_ppm`` are filled. At WBB on 1 September
2025, the first rows, the last empty rows and the first row with a calibrated
value:

.. code-block:: pycon

    >>> sep = uataq.read_data("WBB", "lgr_ugga", time_range="2025-09-01")["lgr_ugga"]
    >>> sep.head(2)
                         CO2d_ppm_cal  CO2d_ppm_raw  CH4d_ppm_cal  CH4d_ppm_raw   H2O_ppm
    Time_UTC
    2025-09-01 00:00:04           NaN      437.7226           NaN      2.005058  9110.648
    2025-09-01 00:00:14           NaN      437.7273           NaN      2.006462  9133.776
    >>> empty = sep["CO2d_ppm_cal"].isna() & sep["CO2d_ppm_raw"].notna()
    >>> int(empty.sum()), sep.index[empty].min(), sep.index[empty].max()
    (1333, Timestamp('2025-09-01 00:00:04'), Timestamp('2025-09-01 03:47:22'))
    >>> (sep["CH4d_ppm_cal"].isna() == sep["CO2d_ppm_cal"].isna()).all()
    np.True_
    >>> sep[empty].tail(2)
                         CO2d_ppm_cal  CO2d_ppm_raw  CH4d_ppm_cal  CH4d_ppm_raw   H2O_ppm
    Time_UTC
    2025-09-01 03:47:12           NaN      437.4495           NaN      1.989803  8913.968
    2025-09-01 03:47:22           NaN      437.6748           NaN      1.990324  8913.212
    >>> sep[~empty].head(2)
                         CO2d_ppm_cal  CO2d_ppm_raw  CH4d_ppm_cal  CH4d_ppm_raw   H2O_ppm
    Time_UTC
    2025-09-01 03:47:32    435.516761      437.3266      1.987546      1.990496  8891.017
    2025-09-01 03:47:41    435.825459      437.6382      1.988239      1.991194  8938.798

The first 1,333 rows of the month, up to 03:47 UTC, have no calibrated value.
The ``calibrated`` level shows why: there was no fit (``CO2d_n`` is 0, and so
``CO2d_m`` and ``CO2d_b`` are empty), and the rows are not flagged, so ``final``
keeps them:

.. code-block:: pycon

    >>> cal = uataq.read_data("WBB", "lgr_ugga", lvl="calibrated", time_range="2025-09-01")["lgr_ugga"]
    >>> cal[["CO2d_ppm_raw", "CO2d_ppm_cal", "CO2d_n", "CO2d_m", "CO2d_b", "QAQC_Flag", "ID_CO2"]].head(2)
                         CO2d_ppm_raw  CO2d_ppm_cal  CO2d_n  CO2d_m  CO2d_b  QAQC_Flag  ID_CO2
    Time_UTC
    2025-09-01 00:00:04      437.7226           NaN       0     NaN     NaN          0   -10.0
    2025-09-01 00:00:14      437.7273           NaN       0     NaN     NaN          0   -10.0

The value is missing, not wrong: on the first day of each month we read (see the
next paragraph), every row with ``CO2d_n`` 0 has an empty ``_cal``.

**Which data and when.** The stretch is in every month written since the archive
was last rewritten: WBB from September 2025, CSP from July 2025, HPL from May
2026 and FRU from December 2025, to 1 October 2026 (41 month starts in all).
The earlier months have none, except at the turn of a year, because each of
these archives was rewritten on one day (CSP on 24 June 2025, FRU on 6 November
2025, WBB on 19 August 2025 and HPL on 20 April 2026) and a rewrite calibrates a
year at a time. We checked this on 13 October 2026 by reading the first day of
every month of 2025 and 2026 that has data, for the ``lgr_ugga`` at WBB, CSP,
HPL, FRU and HDP, and for the ``licor_7000`` at DBK, RPK, HEB and SUG. HDP's
data end in February 2025 and have only the turn of the year. So does the
``licor_7000``: of the 53 month starts read at its four sites, the one with an
empty stretch is January 2026 at RPK.

**How long.** It starts at the first row of the month (00:00 UTC, except at HPL
in September 2026, when the first data came at 11:22 UTC) and holds half an hour
to six hours of data: 170 to 2,162 rows, and 33 of the 41 have 1,000 to 2,000
(about three to five and a half hours). A month has about 250,000 rows, so the
stretch is under 1% of it.

**In local time.** 00:00 UTC is 18:00 MDT (17:00 MST) on the last day of the
previous month, so the empty rows are the last evening of a month. A month cut
in local time, as in :doc:`first_month`, has them at its end. At WBB on 1
September 2025 they run from 18:00 to 21:47 MDT on 31 August:

.. code-block:: pycon

    >>> local = sep.index[empty].tz_localize("UTC").tz_convert("America/Denver")
    >>> local.min(), local.max()
    (Timestamp('2025-08-31 18:00:04-0600', tz='America/Denver'), Timestamp('2025-08-31 21:47:22-0600', tz='America/Denver'))

**What to do.**

- Find out whether your data have it. Count the empty rows of each month. This
  is WBB from July 2025 to October 2026:

  .. code-block:: pycon

      >>> obs = uataq.get_obs("WBB", "CO2", time_range=["2025-07-01", "2026-10-31"])
      >>> empty = obs["CO2d_ppm_cal"].isna() & obs["CO2d_ppm_raw"].notna()
      >>> empty.groupby(obs.index.to_period("M")).sum()
      Time_UTC
      2025-07       0
      2025-08       0
      2025-09    1333
      2025-10    1610
      2025-11    1239
      2025-12    1711
      2026-01    1701
      2026-02    1975
      2026-03    1607
      2026-04    1243
      2026-05    1237
      2026-06    1700
      2026-07    1978
      2026-08    1610
      2026-09     170
      2026-10    1516
      Freq: M, dtype: int64

  December 2025 also holds the end of the year (see above): 473 more rows than
  the 1,238 of its first hours, from 22:42 UTC on 31 December.
- Leave those rows out of anything that needs calibrated values. They are
  empty, so a mean or a plot of ``_cal`` already skips them; a count of rows
  or of hours does not.
- Do not fill them with ``_raw``. It is not calibrated, and the difference is
  not constant. On 1 September 2025 at WBB, over the rows that have both:

  .. code-block:: pycon

      >>> diff = pd.DataFrame({"CO2": sep["CO2d_ppm_raw"] - sep["CO2d_ppm_cal"], "CH4": sep["CH4d_ppm_raw"] - sep["CH4d_ppm_cal"]})
      >>> diff.agg(["min", "median", "max"])
                   CO2       CH4
      min     1.702983  0.002746
      median  1.862718  0.002989
      max     2.167899  0.004132

  That is 1.7 to 2.2 ppm of CO2 and 2.7 to 4.1 ppb of CH4 (the table is in
  ppm).
- To get calibrated values for those hours, the pipeline's archive has to be
  rewritten by the people who run the pipeline. A rewrite fills the months it
  covers, but the months written after it have the stretch again.

The check above also finds other empty stretches, which are rare. They look the
same in the data: for example 1,841 rows (from 15:56 to 21:58 UTC) on 10
November 2023 at CSP, all with ``CO2d_n`` 0 and no flag, and the first 984 rows
(2.7 hours) of the final data of the new ``lgr_ugga`` at LDF on 26 June 2023.
Their causes were not looked into.

**Why.** The pipeline's routine calibration step runs every 15 minutes. In the
first hours of a UTC month it calibrates only the new month's rows, so it has no
reference tank measurement from before the first of them, and it fits none. The
next run only appends rows that are newer, so it does not go back to fill them
in. A rewrite of the archive calibrates a year at a time, so it does. This is
from the pipeline's code, read on 13 October 2026, and it is how the pipeline
wrote the archive, not something uataq does: uataq reads the archive as it is.
If the pipeline's calibration step or the archive changes, this section will go
out of date.

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
(ozone, particles, NOx; see *Research Group* on the
:doc:`general functions page <general>`). Their ``qaqc`` and ``final`` levels
are read from the same horel files. For the ozone (``2b_205``) and particle
(``metone_es642``, ``metone_es405``) monitors, the horel files mark a flagged
row with 1, and uataq turns that into ``QAQC_Flag = -1``, so the flag is 0
(passes) or -1 (flagged). The ``final`` level is the ``qaqc`` rows that pass and
have a value. For the ``2b_205`` on TRX01 on 1 June 2024:

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

- :doc:`pollutants`: the pattern of the concentration column names, and how to
  pick them out of a table.
- :doc:`first_month`: what each data level is for, and times in local time.
