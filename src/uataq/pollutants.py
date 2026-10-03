"""
How UATAQ names pollutant columns.

UATAQ concentration columns follow ``{pollutant}[d|channel]_{units}[_cal|_raw]``:
``O3_ppb``, ``CO2d_ppm_cal`` (dry mole fraction, calibrated), ``CH4d_ppm_raw``
(uncalibrated), ``PM2.5_ugm3``, ``BC6_ngm3`` (aethalometer channel 6). This
module picks those columns out of a DataFrame and parses their names.

Display metadata (long names, LaTeX labels, expected ranges) is
instrument-independent and lives in ``lair.pollutants``; uataq does not import
lair.
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass

from uataq.instruments import catalog

#: Units a UATAQ concentration column can carry.
UNITS: tuple[str, ...] = ("ppm", "ppb", "ugm3", "ngm3")

#: Every pollutant some configured instrument model measures, in declared case.
POLLUTANTS: tuple[str, ...] = tuple(
    sorted({p for model in catalog.values() for p in getattr(model, "pollutants", ())})
)


def _pattern(pollutant: str, raw: bool) -> re.Pattern:
    """The column-name pattern for one pollutant."""
    # BC is reported per wavelength channel (BC1..BC7); everything else may
    # carry a "d" for dry mole fraction. Kept apart so PM1 can't match PM10.
    infix = r"(?P<channel>\d)" if pollutant.upper() == "BC" else "(?P<dry>d)?"
    suffix = "(?:_(?P<calibration>cal|raw))?" if raw else "(?:_(?P<calibration>cal))?"
    return re.compile(
        rf"^{re.escape(pollutant)}{infix}_(?P<units>{'|'.join(UNITS)}){suffix}$",
        re.IGNORECASE,
    )


def concentration_columns(
    pollutant: str, columns: Iterable[str], raw: bool = False
) -> list[str]:
    """
    Pick the columns holding a pollutant's measured concentration.

    Matches ``{pollutant}_{unit}`` with a concentration unit, e.g. ``O3_ppb``,
    ``CO2d_ppm`` (dry mole fraction), ``CH4d_ppm_cal`` (calibrated),
    ``PM2.5_ugm3`` or ``BC6_ngm3`` (an aethalometer channel). Instrument
    diagnostics that share the prefix, like ``O3_Meas_mV`` or ``NO2_Slope``,
    spreads like ``O3_ppb_std``, and other pollutants sharing the prefix (``NO``
    vs ``NO2_ppb``) are not matches.

    Parameters
    ----------
    pollutant : str
        The pollutant, matched case-insensitively.
    columns : Iterable[str]
        Column names to search.
    raw : bool
        Also match the uncalibrated ``..._raw`` columns that sit beside
        ``..._cal`` in lin final data. Default False.

    Returns
    -------
    list[str]
        The matching columns, in their original order.
    """
    pattern = _pattern(pollutant, raw)
    return [col for col in columns if pattern.match(col)]


@dataclass(frozen=True)
class ConcentrationColumn:
    """
    A parsed concentration column name.

    Parameters
    ----------
    name : str
        The column name, e.g. ``'CO2d_ppm_cal'``.
    pollutant : str
        The pollutant in declared case (see :data:`POLLUTANTS`), e.g. ``'CO2'``.
    units : str
        One of :data:`UNITS`.
    dry : bool
        Dry mole fraction (the ``d`` after the pollutant).
    calibration : str | None
        ``'cal'``, ``'raw'``, or None when the name carries no suffix.
    channel : int | None
        Aethalometer wavelength channel, for black carbon.
    """

    name: str
    pollutant: str
    units: str
    dry: bool = False
    calibration: str | None = None
    channel: int | None = None


def parse_column(column: str) -> ConcentrationColumn | None:
    """
    Parse a concentration column name.

    Parameters
    ----------
    column : str
        A column name, e.g. ``'CH4d_ppm_raw'`` or ``'BC6_ngm3'``.

    Returns
    -------
    ConcentrationColumn | None
        The parts of the name, or None if it is not a concentration column
        of a known pollutant (``'Time_UTC'``, ``'O3_Meas_mV'``, ...).
    """
    # Longest names first, so NO2 is tried before NO and PM10 before PM1
    for pollutant in sorted(POLLUTANTS, key=len, reverse=True):
        match = _pattern(pollutant, raw=True).match(column)
        if match:
            parts = match.groupdict()
            return ConcentrationColumn(
                name=column,
                pollutant=pollutant,
                units=parts["units"].lower(),
                dry=bool(parts.get("dry")),
                calibration=(parts["calibration"] or "").lower() or None,
                channel=int(parts["channel"]) if parts.get("channel") else None,
            )
    return None
