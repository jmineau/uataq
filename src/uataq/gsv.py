"""
Google Street View cars' observations in Salt Lake City, 2019 to 2020.

Two Google Street View cars, ``lone`` and ``star``, measured CH4, CO2, O3, black
carbon, CO, NO, NO2 and PM2.5 once a second on the roads of the Salt Lake Valley
from May 2019 to March 2020 (Lin et al., 2023,
`doi:10.1016/j.atmosenv.2023.119995 <https://doi.org/10.1016/j.atmosenv.2023.119995>`_).
The Lin group keeps the campaign's tables on CHPC, in ``data/gsv/tables`` under
:data:`uataq.filesystem.groupspaces.lin.MEASUREMENTS_DIR`. :func:`get_obs` reads
the merged one, ``3_primary_keys.csv``: a row for each car and second, with the
car's position and, for each pollutant, its value, its enhancement above a
baseline (``_ex``), the baseline (``_base``, the 1 % quantile of the hour before
and the hour after) and the instrument's QC flag.

The same table is public, as ``GSV_SLC.csv`` at
`doi:10.5281/zenodo.7605718 <https://doi.org/10.5281/zenodo.7605718>`_, whose
README describes the columns and the flags. Off CHPC, download it and pass its
path to :func:`get_obs`. (The group's table also has rows from June 2020, none
with a good position; the rest is the same, row for row.)

The cars are a campaign, not UATAQ sites, so they are not part of the
:doc:`configuration </reference/config>` and are read here rather than with
:func:`uataq.get_obs`.

Not every pollutant was measured the whole time: CH4 from June to October 2019
(on ``star`` until 13 August, on ``lone`` from 16 August), CO on ``star`` in the
second half of August 2019, and O3 on ``star`` only.

Examples
--------
The examples read the table, so the tests do not run them; the output is from a
run on CHPC on 13 November 2026. The rows of the table are not in time order,
so every read passes over the whole 2.8 GB file: about 20 s and 1 GB of memory
for one pollutant, 40 s and 10 GB for all of them. Run it on a compute node.

The cars' methane on one day, good data only:

>>> from uataq import gsv
>>> obs = gsv.get_obs("CH4", time_range="2019-07-16", good_only=True)  # doctest: +SKIP
>>> obs  # doctest: +SKIP
                    system_id  Latitude_deg  Longitude_deg polygon  qc_gps  CH4d_ppm  CH4d_ppm_ex  CH4d_ppm_base  qc_lgr_mgga
Time_UTC
2019-07-16 15:07:23      star     40.786317    -111.929843     RP2     0.0   1.94733     0.000693       1.946637          0.0
2019-07-16 15:07:24      star     40.786392    -111.929847     RP2     0.0   1.94722     0.000583       1.946637          0.0
2019-07-16 15:07:25      star     40.786467    -111.929847     RP2     0.0   1.94869     0.002053       1.946637          0.0
2019-07-16 15:07:26      star     40.786540    -111.929845     RP2     0.0   1.95081     0.004173       1.946637          0.0
2019-07-16 15:07:27      star     40.786620    -111.929840     RP2     0.0   1.95279     0.006153       1.946637          0.0
...                       ...           ...            ...     ...     ...       ...          ...            ...          ...
2019-07-16 20:57:27      star     40.761777    -111.830288    UofU     0.0   1.88465     0.003969       1.880681          0.0
2019-07-16 20:57:28      star     40.761722    -111.830232    UofU     0.0   1.88510     0.004417       1.880683          0.0
2019-07-16 20:57:29      star     40.761662    -111.830182    UofU     0.0   1.88550     0.004816       1.880684          0.0
2019-07-16 20:57:30      star     40.761602    -111.830147    UofU     0.0   1.88484     0.004154       1.880686          0.0
2019-07-16 20:57:31      star     40.761542    -111.830128    UofU     0.0   1.88721     0.006523       1.880687          0.0
<BLANKLINE>
[20800 rows x 9 columns]

Without ``good_only`` every row with a value comes back, for you to filter on
the flags. :data:`QC_FLAGS` says what a flag's value means:

>>> obs = gsv.get_obs("CH4", time_range="2019-07-16")  # doctest: +SKIP
>>> len(obs)  # doctest: +SKIP
21399
>>> int((obs["qc_lgr_mgga"] == -71).sum())  # doctest: +SKIP
300
>>> gsv.QC_FLAGS[-71]
'time recent outage > 1 hour'
"""

import logging
import os
import warnings
from collections.abc import Iterable

import pandas as pd

from uataq import errors
from uataq.filesystem.groupspaces import lin
from uataq.timerange import TimeRange, TimeRangeTypes

_logger = logging.getLogger(__name__)

#: File name of the merged table.
TABLE: str = "3_primary_keys.csv"

#: The two cars, as the table's ``system_id`` names them.
CARS: tuple[str, ...] = ("lone", "star")

# Each pollutant's column in the table, its column in the table get_obs
# returns (uataq's name), and its QC flag column, in the table's order.
_COLUMNS: dict[str, tuple[str, str, str]] = {
    "O3": ("o3_ppb", "O3_ppb", "qc_2b_205"),
    "CH4": ("ch4d_ppm", "CH4d_ppm", "qc_lgr_mgga"),
    "CO2": ("co2d_ppm", "CO2d_ppm", "qc_licor_7000"),
    # the table's bc_ngm3 is the aethalometer's channel 6 (880 nm)
    "BC": ("bc_ngm3", "BC6_ngm3", "qc_magee_ae33"),
    "CO": ("co_ppb", "CO_ppb", "qc_picarro_g2401"),
    "NO": ("no_ppb", "NO_ppb", "qc_teledyne_t200"),
    "NO2": ("no2_ppb", "NO2_ppb", "qc_teledyne_t500u"),
    "PM2.5": ("pm25_ugm3", "PM2.5_ugm3", "qc_thermo_pdr_1500"),
}

#: The pollutants the cars measured, in the table's order.
POLLUTANTS: tuple[str, ...] = tuple(_COLUMNS)

# The table's columns every read returns, and their names in the result.
_POSITION = {
    "system_id": "system_id",
    "latitude": "Latitude_deg",
    "longitude": "Longitude_deg",
    "polygon": "polygon",
    "qc_gps": "qc_gps",
}

#: What each value of a ``qc_*`` column means, from the README of the published
#: dataset. 0 is good, a positive flag is for conditional use, and a negative
#: one marks data that should not be used.
#:
#: :meta hide-value:
QC_FLAGS: dict[int, str] = {
    0: "ok",
    1: "failed automated checks but manually passed",
    -1: "manually removed",
    -2: "calibration",
    # gps
    11: "position at vehicle storage",
    -11: "time recent outage > 1 hour",
    -12: "position out of range",
    -13: "fix quality indicator < 1",
    -14: "number of satellites < 4",
    -15: "altitude out of range (1000, 2000)",
    # thermo_pdr_1500
    -21: "time recent outage > 1 hour",
    -22: "pm25_ugm3 measurement > 1000",
    -23: "relative humidity > 95%",
    # licor_7000
    -31: "time recent outage > 1 hour",
    -32: "co2d_ppm measurement > 3000",
    -33: "water vapor out of range (0, 30)",
    -34: "cavity pressure out of range (75, 95)",
    -35: "instrument reported diagnostic status > 0",
    # teledyne_t200
    -41: "time recent outage > 1 hour",
    -42: "no_ppb measurement > 2000",
    -43: "operating temperature out of range (5, 50)",
    -44: "flow rate out of range (450, 550)",
    -45: "ozone flow rate out of range (50, 150)",
    -46: "molybdenum converter temperature out of range (310, 320)",
    -47: "photomultiplier tube temperature out of range (5, 12)",
    -48: "reaction cell pressure out of range (3, 6)",
    # teledyne_t500u
    -51: "time recent outage > 1 hour",
    -52: "no2_ppb measurement > 2000",
    -53: "operating temperature out of range (5, 50)",
    -54: "chamber temperature out of range (15, 35)",
    -55: "sample pressure out of range (15, 35)",
    -56: "auto reference loss out of range (400, 800)",
    -57: "no2_ppb value repeated at least 10 times indicating autocalibration",
    # magee_ae33
    -61: "time recent outage > 1 hour",
    -62: "bc6_ngm3 measurement > 100000",
    -63: "flow rate out of range (4.9, 5.1)",
    # lgr_mgga
    -71: "time recent outage > 1 hour",
    -72: "co2d_ppm measurement > 3000",
    -73: "ch4d_ppm measurement > 40",
    -74: "water vapor > 30000",
    -75: "cavity pressure out of range (490, 520)",
    # picarro_g2401
    -81: "time recent outage > 1 hour",
    -82: "co2d_ppm measurement > 3000",
    -83: "ch4d_ppb measurement > 20000",
    -84: "co_ppb measurement > 100000",
    -85: "water vapor > 3",
    # 2b_205
    -101: "time recent outage > 1 hour",
    -102: "o3_ppb out of range (-10, 200)",
    -103: "cell temperature out of range (0, 50)",
    -104: "flow rate out of range (1800, 3000)",
    -105: "o3_ppb more than 15 ppb from its centered 1-minute rolling median",
}

# Rows parsed at a time: memory stays near one chunk whatever the range asked for.
_CHUNK_ROWS = 1_000_000


def _table_file(path: str | os.PathLike | None = None) -> str:
    """Return the merged table's file: ``path``, the table in it, or the one on CHPC."""
    file = (
        os.fspath(path) if path else os.path.join(lin.DATA_DIR, "gsv", "tables", TABLE)
    )
    if os.path.isdir(file):
        file = os.path.join(file, TABLE)
    if not os.path.isfile(file):
        raise FileNotFoundError(
            f"No Street View table at '{file}'. Off CHPC, download GSV_SLC.csv "
            "from https://doi.org/10.5281/zenodo.7605718 and pass its path."
        )
    return file


def _choose(asked: str | Iterable[str], known: tuple[str, ...], what: str) -> list[str]:
    """Return the ``known`` names asked for, in ``known``'s order, matched without case."""
    if isinstance(asked, str):
        asked = known if asked.lower() == "all" else [asked]
    by_lower = {name.lower(): name for name in known}
    chosen = []
    for name in asked:
        if str(name).lower() not in by_lower:
            raise ValueError(f"Unknown {what} {name!r}: choose from {', '.join(known)}")
        chosen.append(by_lower[str(name).lower()])
    if not chosen:
        raise ValueError(f"No {what} given: choose from {', '.join(known)}")
    return [name for name in known if name in chosen]


def _value_columns(table_column: str, header: Iterable[str]) -> list[str]:
    """Return a pollutant's value, enhancement and baseline columns that the table has."""
    # O3 has neither an enhancement nor a baseline
    candidates = [table_column, f"{table_column}_ex", f"{table_column}_base"]
    return [col for col in candidates if col in header]


def get_obs(
    pollutants: str | Iterable[str] = "all",
    cars: str | Iterable[str] = "all",
    time_range: TimeRange | TimeRangeTypes = None,
    good_only: bool = False,
    path: str | os.PathLike | None = None,
) -> pd.DataFrame:
    """
    Get the Street View cars' observations, with their positions.

    Parameters
    ----------
    pollutants : str | Iterable[str]
        One or several of :data:`POLLUTANTS` (``'CH4'``, ``'CO2'``, ``'O3'``,
        ``'BC'``, ``'CO'``, ``'NO'``, ``'NO2'``, ``'PM2.5'``), in any case.
        Default ``'all'``.
    cars : str | Iterable[str]
        ``'lone'``, ``'star'`` or both. Default ``'all'``.
    time_range : TimeRange | TimeRangeTypes
        The time range to read, in UTC, ``start <= Time_UTC < stop`` (see
        :ref:`input-time-range`). Default None reads the whole campaign.
    good_only : bool
        Keep only good data. Rows whose position flag ``qc_gps`` is not 0 are
        dropped (a car with no fix, or parked where it is stored), each
        pollutant's value, enhancement and baseline are emptied where its own
        flag is not 0, and rows left with no value are dropped. Default False
        returns every row as the table has it, for you to filter on the flags.
    path : str | os.PathLike | None
        The merged table, or the folder that holds ``3_primary_keys.csv``.
        Default None reads the Lin group's copy on CHPC. The published
        ``GSV_SLC.csv`` reads the same way.

    Returns
    -------
    pandas.DataFrame
        One row for each car and second in which one of the pollutants has a
        value, indexed by ``Time_UTC`` and sorted by time, then car. Both cars
        can sample in the same second, so the index repeats. The columns are
        ``system_id`` (the car), ``Latitude_deg``, ``Longitude_deg``,
        ``polygon`` (the drive area the car was in, if any), ``qc_gps`` and,
        for each pollutant, its value, enhancement (``_ex``), baseline
        (``_base``) and QC flag: for CH4, ``CH4d_ppm``, ``CH4d_ppm_ex``,
        ``CH4d_ppm_base`` and ``qc_lgr_mgga``. :data:`QC_FLAGS` says what a
        flag's value means.

    Raises
    ------
    ValueError
        If a pollutant or a car is not one the campaign had.
    FileNotFoundError
        If there is no table at ``path`` (or, with no ``path``, on this machine).
    ParserError
        If the file lacks one of the merged table's columns.

    Warns
    -----
    EmptyResultWarning
        If no row matches, so the table has no rows.

    See Also
    --------
    uataq.get_obs : The same for a UATAQ site, the TRAX trains among them.

    Examples
    --------
    Two pollutants from one car over a month (it reads the table, so the tests
    do not run it):

    >>> from uataq import gsv
    >>> obs = gsv.get_obs(  # doctest: +SKIP
    ...     ["CH4", "CO2"], cars="star", time_range="2019-07", good_only=True
    ... )
    """
    chosen = _choose(pollutants, POLLUTANTS, "pollutant")
    chosen_cars = _choose(cars, CARS, "car")
    time_range = TimeRange(time_range)
    start, stop = time_range.start, time_range.stop
    file = _table_file(path)

    header = pd.read_csv(file, nrows=0).columns
    needed = ["time", *_POSITION]
    for pollutant in chosen:
        table_column, _, flag = _COLUMNS[pollutant]
        needed += [table_column, flag]
    missing = [col for col in needed if col not in header]
    if missing:
        raise errors.ParserError(
            f"{file} is not the merged Street View table: it has no {', '.join(missing)}"
        )

    # Each pollutant's value columns in the table, and every column to read
    values = {p: _value_columns(_COLUMNS[p][0], header) for p in chosen}
    flags = {p: _COLUMNS[p][2] for p in chosen}
    usecols = ["time", *_POSITION]
    for pollutant in chosen:
        usecols += [*values[pollutant], flags[pollutant]]
    measured = [_COLUMNS[p][0] for p in chosen]

    _logger.debug(f"Reading {usecols} from {file}")
    # The rows are not in time order, so every read passes over the whole file.
    kept = []
    for chunk in pd.read_csv(
        file,
        usecols=usecols,
        dtype={"system_id": str, "polygon": str},
        chunksize=_CHUNK_ROWS,
    ):
        rows = chunk[
            chunk["system_id"].isin(chosen_cars) & chunk[measured].notna().any(axis=1)
        ].copy()
        # "2019-07-16 18:22:10+00:00" on CHPC, "2019-07-16 18:22:10" on Zenodo
        rows["time"] = pd.to_datetime(
            rows["time"].str.slice(0, 19), format="%Y-%m-%d %H:%M:%S"
        )
        if start is not None:
            rows = rows[rows["time"] >= pd.Timestamp(start)]
        if stop is not None:
            rows = rows[rows["time"] < pd.Timestamp(stop)]
        if good_only:
            rows = rows[rows["qc_gps"] == 0].copy()
            for pollutant in chosen:
                bad = rows[flags[pollutant]] != 0
                rows.loc[bad, values[pollutant]] = float("nan")
            rows = rows[rows[measured].notna().any(axis=1)]
        kept.append(rows)

    if not kept:  # a file with a header and no rows
        kept = [pd.DataFrame(columns=usecols)]
    obs = pd.concat(kept, ignore_index=True)[usecols]
    names = {"time": "Time_UTC", **_POSITION}
    for pollutant in chosen:
        table_column, name, _ = _COLUMNS[pollutant]
        for col in values[pollutant]:
            names[col] = name + col.removeprefix(table_column)
    obs = obs.rename(columns=names)
    obs["Time_UTC"] = pd.to_datetime(obs["Time_UTC"]).dt.as_unit("ns")
    obs = obs.sort_values(["Time_UTC", "system_id"], kind="stable")
    obs = obs.set_index("Time_UTC")

    if obs.empty:
        warnings.warn(
            f"No Street View rows with {', '.join(chosen)} for "
            f"{' and '.join(chosen_cars)} ({time_range})"
            + (" that pass the QC flags." if good_only else "."),
            errors.EmptyResultWarning,
            stacklevel=2,
        )
    return obs
