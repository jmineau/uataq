"""
GPS helpers: great-circle geometry and motion estimated from positions.

When a receiver logs only ``GPGGA`` sentences (position, altitude, fix quality)
and not ``GPRMC``, there is no recorded speed or course. Both can be recovered
from the positions themselves, which is what :func:`estimate_speed_course`
does; :class:`uataq.instruments.GPS` calls it to fill whatever the files did
not record.

Formulas from https://www.movable-type.co.uk/scripts/latlong.html. They assume
a spherical Earth, which is well under GPS noise at these distances.
"""

from __future__ import annotations

import logging

import numpy as np
import numpy.typing as npt
import pandas as pd

_logger = logging.getLogger(__name__)

#: Mean Earth radius (m).
EARTH_RADIUS_M = 6_371_000.0

__all__ = [
    "EARTH_RADIUS_M",
    "bearing",
    "estimate_speed_course",
    "haversine",
]


def haversine(
    lat1: npt.ArrayLike,
    lon1: npt.ArrayLike,
    lat2: npt.ArrayLike,
    lon2: npt.ArrayLike,
    R: float = EARTH_RADIUS_M,
) -> np.ndarray:
    """
    Great-circle distance between two points (haversine formula).

    Parameters
    ----------
    lat1, lon1 : array_like
        First point, in degrees.
    lat2, lon2 : array_like
        Second point, in degrees.
    R : float
        Sphere radius. The result carries its units. Default is
        :data:`EARTH_RADIUS_M`, so distances come back in meters.

    Returns
    -------
    numpy.ndarray
        Distance in the units of ``R``. Inputs are broadcast together, so a
        single point against an array of points works.
    """
    lat1, lon1, lat2, lon2 = (
        np.deg2rad(np.asarray(v, dtype=float)) for v in (lat1, lon1, lat2, lon2)
    )
    a = (
        np.sin((lat2 - lat1) / 2) ** 2
        + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    )
    return 2 * R * np.arctan2(np.sqrt(a), np.sqrt(1 - a))


def bearing(
    lat1: npt.ArrayLike,
    lon1: npt.ArrayLike,
    lat2: npt.ArrayLike,
    lon2: npt.ArrayLike,
) -> np.ndarray:
    """
    Initial great-circle bearing from the first point to the second.

    Parameters
    ----------
    lat1, lon1 : array_like
        Start point, in degrees.
    lat2, lon2 : array_like
        End point, in degrees.

    Returns
    -------
    numpy.ndarray
        Bearing in degrees clockwise from true north, in ``[0, 360)``.
        Inputs are broadcast together. Coincident points give 0.
    """
    lat1, lon1, lat2, lon2 = (
        np.deg2rad(np.asarray(v, dtype=float)) for v in (lat1, lon1, lat2, lon2)
    )
    dlon = lon2 - lon1
    y = np.sin(dlon) * np.cos(lat2)
    x = np.cos(lat1) * np.sin(lat2) - np.sin(lat1) * np.cos(lat2) * np.cos(dlon)
    return (np.rad2deg(np.arctan2(y, x)) + 360) % 360


def estimate_speed_course(
    latitude: npt.ArrayLike,
    longitude: npt.ArrayLike,
    time: npt.ArrayLike | None = None,
    window: int = 1,
    max_gap: str | pd.Timedelta | None = "60s",
) -> pd.DataFrame:
    """
    Estimate speed and course from a sequence of positions.

    Both are centered differences: the sample at position ``i`` is described by
    the displacement from ``i - window`` to ``i + window``, so the estimate is
    symmetric in time and does not lag the track. Speed is the great-circle
    distance over the elapsed time; course is the bearing along it.

    Parameters
    ----------
    latitude, longitude : array_like
        Positions in degrees, **ordered in time**. A pandas Series with a
        DatetimeIndex supplies ``time`` on its own.
    time : array_like, optional
        Sample times, convertible by :func:`pandas.to_datetime`. Defaults to
        the index of ``latitude`` when that is a Series.
    window : int
        Number of samples on each side of the centered difference. ``1`` uses
        the immediate neighbors. A larger window averages over a longer
        baseline, which suppresses position noise at the cost of smoothing
        real accelerations and turns.
    max_gap : str or pandas.Timedelta, optional
        Longest interval between *consecutive* samples that may fall inside
        the difference. Where a larger gap is spanned the estimate is NaN,
        because a straight chord across a gap is not the path travelled.
        ``None`` disables the check.

    Returns
    -------
    pandas.DataFrame
        ``Speed_m_s`` and ``Course_deg``, indexed by ``time`` (named
        ``Time_UTC``). The first and last ``window`` samples are NaN, as are
        samples spanning a gap or a non-increasing time step.

    Notes
    -----
    Position noise becomes speed noise: a receiver jittering by a few meters
    looks like it is moving at a few m/s when differenced over 1 s. Use a
    longer ``window`` (or aggregate first) before thresholding a stationary
    platform, and treat the course as meaningless wherever the speed is at or
    below the noise level.
    """
    if window < 1:
        raise ValueError(f"window must be >= 1, got {window}")

    if time is None:
        if not isinstance(latitude, pd.Series) or not isinstance(
            latitude.index, pd.DatetimeIndex
        ):
            raise ValueError(
                "time is required unless latitude is a Series with a DatetimeIndex"
            )
        time = latitude.index

    index = pd.DatetimeIndex(pd.to_datetime(np.asarray(time)), name="Time_UTC")
    lat = np.asarray(latitude, dtype=float)
    lon = np.asarray(longitude, dtype=float)
    if not (len(lat) == len(lon) == len(index)):
        raise ValueError(
            f"latitude, longitude and time must be the same length, "
            f"got {len(lat)}, {len(lon)}, {len(index)}"
        )

    out = pd.DataFrame(
        {"Speed_m_s": np.nan, "Course_deg": np.nan}, index=index, dtype=float
    )
    n = len(index)
    if n < 2 * window + 1:
        return out
    if not index.is_monotonic_increasing:
        _logger.warning(
            "GPS times are not in increasing order; speed/course estimates "
            "assume time-ordered positions."
        )

    w = window
    lo = slice(None, n - 2 * w)  # i - w
    hi = slice(2 * w, None)  # i + w
    center = slice(w, n - w)  # i

    seconds = index.to_series().diff().dt.total_seconds().to_numpy()
    dt = index[hi].to_numpy() - index[lo].to_numpy()
    dt = dt / np.timedelta64(1, "s")

    dist = haversine(lat[lo], lon[lo], lat[hi], lon[hi])
    course = bearing(lat[lo], lon[lo], lat[hi], lon[hi])

    valid = dt > 0
    if max_gap is not None:
        # Largest single step inside each difference: seconds[k] is t[k] - t[k-1],
        # so the steps spanning i-w -> i+w are seconds[i-w+1 : i+w+1].
        step = (
            pd.Series(seconds).rolling(2 * w).max().to_numpy()[2 * w :]
        )  # aligned to i + w
        valid &= step <= pd.Timedelta(max_gap).total_seconds()

    speed = np.where(valid, dist / np.where(dt > 0, dt, np.nan), np.nan)
    out.iloc[center, out.columns.get_loc("Speed_m_s")] = speed
    out.iloc[center, out.columns.get_loc("Course_deg")] = np.where(
        valid, course, np.nan
    )
    return out
