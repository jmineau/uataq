.. currentmodule:: uataq

Data levels and flags
=====================

.. note::

    The examples on this page read the UATAQ archive, which is only available
    on CHPC, and are not run when the documentation is built. Their output is
    from runs on CHPC on 12 October 2026.

The archive keeps each instrument's data at up to four **data levels**: the
same measurements, processed further at each level. This page says what each
level holds, which level each function reads, what the flags mean and what the
``final`` level keeps. The columns of each level are on
:doc:`/reference/columns`.

.. _data-levels:

The four levels
---------------

From least to most processed:

``raw``
    The instrument's data as it was logged.
``qaqc``
    Every row, with the pipeline's QAQC flag in ``QAQC_Flag``. Flagged rows are
    kept.
``calibrated``
    The ``qaqc`` rows calibrated against reference tanks, with the calibration
    fit. Only the lin group's CO2 and CH4 analyzers have this level.
``final``
    The rows that pass, with the pipeline's default flags applied: flagged rows
    are dropped, and for the CO2 and CH4 analyzers so are the rows that measured
    calibration tanks.

``final`` is the ready-to-share level: it can go to people outside the group as
it is. The lower levels are for finer control. Which one to use depends on how
clean the data need to be for what you are doing, and on how much control you
want over the QAQC. The pipeline describes the levels too, in its
`README <https://github.com/uataq/data-pipeline#processing-levels>`_.

For the CO2 and CH4 analyzers (the ``lgr_ugga``, ``licor_6262`` and
``licor_7000``), each level holds:

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
       ``ID_CO2``, ``ID_CH4`` or ``QAQC_Flag``.

.. _which-level:

Which level a read gives
------------------------

- :func:`get_obs` and :func:`get_recent_obs` read ``final``. They take no level:
  one given raises an error (see :doc:`/guides/errors`).
- :func:`get_network_obs` reads the highest level each instrument has. That is
  ``final`` too, except at a horel vehicle with no finalized files at all, which
  is read at ``raw``.
- :func:`read_data` reads the level you give as ``lvl``. With none, it reads the
  highest level the instrument has, ``final`` when it has one.

Not every instrument has every level. Only the lin group's CO2 and CH4
analyzers have ``calibrated``, and TRX01's :term:`lgr_ugga_manual_cal` does not.
The horel group's instruments have ``raw``, ``qaqc`` and ``final``, and some
months of them are only at ``raw`` (see :doc:`/guides/mobile_sites`). Asking for a
level an instrument does not have raises an error that lists the levels it has
(see :doc:`/guides/errors`).

The same day at two levels
--------------------------

The examples below read the ``lgr_ugga`` at WBB on 2 June 2025. ``final`` is
its highest level, so :func:`read_data` reads it with no ``lvl``:

.. code-block:: pycon

    >>> import pandas as pd
    >>> import uataq
    >>> final = uataq.read_data("WBB", "lgr_ugga", time_range="2025-06-02")["lgr_ugga"]
    >>> final.columns.tolist()
    ['CO2d_ppm_cal', 'CO2d_ppm_raw', 'CH4d_ppm_cal', 'CH4d_ppm_raw', 'H2O_ppm']
    >>> len(final)
    8390

The ``qaqc`` level of the same day has every row the analyzer logged, with the
columns that say what each row is:

.. code-block:: pycon

    >>> qaqc = uataq.read_data("WBB", "lgr_ugga", lvl="qaqc", time_range="2025-06-02")["lgr_ugga"]
    >>> len(qaqc)
    8845
    >>> qaqc["QAQC_Flag"].value_counts()
    QAQC_Flag
     0    8586
    -2     259
    Name: count, dtype: int64
    >>> cal = uataq.read_data("WBB", "lgr_ugga", lvl="calibrated", time_range="2025-06-02")["lgr_ugga"]

The 8,845 rows are the 8,390 final ones, 259 rows flagged ``-2`` (`Flags`_) and
196 rows that measured calibration tanks (`What the analyzer was sampling`_).

.. _analyzer-id:

What the analyzer was sampling
------------------------------

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

What the final level keeps
--------------------------

The flush rows are flagged (``-2``), but the
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
``licor_6262`` at SUG in June 2019, the calibration flagged 566 rows ``-4``
(517 of them outside air; the other 49 measured tanks, which the rule drops
anyway), and the rule above gives the 238,632 ``final`` rows from the ``calibrated`` level,
but 239,149 from the ``qaqc`` level.

.. _flags:

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
names the columns as they are in the pipeline's files (see :doc:`/reference/columns`, "In every table"):
its ``Flow_CCmin``, for example, is uataq's ``Flow_mLpm``, or ``Flow_Lpm`` for
the ``2b_205``.

The horel group's ozone (``2b_205``) and particle (``metone_es642``,
``metone_es405``) monitors mark a flagged row with 1, and uataq turns that into
``QAQC_Flag = -1``, so their flag is 0 (passes) or -1 (flagged). Their ``final``
level is the ``qaqc`` rows that pass and have a value.
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

.. _when-cal-is-empty:

When _cal is empty
------------------

Some rows of the ``final`` level have a ``_raw`` value and an empty ``_cal``.
There are two causes you can see in the data.

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
not flagged, so they are in the ``final`` level. A row gets a fit only after
the analyzer has measured the tanks, and the first tank measurement of a new
year comes some hours in. At WBB on 1 January 2025:

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
on 31 December 2024). Rows can lack a fit at other times too; CO2 and CH4 are
empty on the same rows. Find them with the line below rather than assuming
where they are.

To find these rows in your data:

.. code-block:: python

    empty = df["CO2d_ppm_cal"].isna() & df["CO2d_ppm_raw"].notna()

Their ``_raw`` value is not calibrated.
