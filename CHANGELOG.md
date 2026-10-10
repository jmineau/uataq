# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/), and versions
follow [PEP 440](https://peps.python.org/pep-0440/): calendar-based,
`YYYY.M.PATCH`.

## [Unreleased]

## [2026.10.0] - 2026-10-09

The first release since 2025.11.0.

### Added

- **Research groups per instrument.** `group` can map each instrument to a
  group, and with no `group` each part of a time range is read from the group
  that has it (`group_dates` in `config.json`): TRAX ozone comes from lin before
  2017-10-28 and from Horel after.
- `uataq.pollutants`: helpers for UATAQ's concentration column names
  (`CO2d_ppm_cal` and the like).
- `uataq.gps`: great-circle helpers and `estimate_speed_course`. `GPS.read_data`
  fills missing `Speed_m_s` and `Course_deg` from the positions and marks them
  in `Speed_Estimated` and `Course_Estimated`. Recorded values are never
  overwritten.
- Horel raw GPS reads carry `GPS_Time_UTC`, the receiver's own time. The Horel
  logger's clock runs 1 to 20 s ahead of GPS time. Rows without a fix get NaT.
- Mobile observations carry `GPS_Group`, the group whose GPS located each row.
- `Network.get_availability` and `Network.plot_availability`: data availability
  by site and level.

### Changed

- **Mobile observations are located only with the GPS of the group they were
  read from** (breaking): lin rows on the Pi's clock, Horel rows on the logger's
  clock. Naming another group's GPS for some rows raises `ValueError`. Horel rows
  used to be joined to lin's GPS, which put moving TRAX rows a median 120 m from
  where they were measured and dropped rows.
- **Time ranges are half-open** (breaking): a range's stop is excluded, in row
  slicing and in `TimeRange` membership. A date string still covers its whole
  day.
- **Network observations keep `_cal` and `_raw` columns** and have an
  `instrument` column (breaking), so two instruments measuring the same species
  no longer produce duplicate columns.
- A time range that only touches an instrument's installation or removal date
  raises `InactiveInstrumentError`. It used to return empty data.
- uataq no longer turns on pandas' copy-on-write option. Setting it changed
  pandas for the caller's whole session.
- Notices are logged, not printed.
- Off CHPC, `import uataq` fails after 10 s with a clear message when it cannot
  fetch the pipeline's configuration. It used to hang.
- **Requires Python 3.11 or newer** (breaking): Python 3.10 reaches its end of
  life in October 2026. Tested on 3.11 through 3.14.
- The version now comes from git tags (setuptools-scm). An install from git
  between releases reports a development version such as
  `2025.11.1.dev3+g1a2b3c4` rather than the last release's number.
- The documentation no longer describes class attributes and methods twice: the
  API pages drop a class docstring's `Methods` section and the `Attributes`
  entries that the page documents anyway. Entries that described methods that no
  longer exist (`Site.read_obs`) are gone from the pages.

### Fixed

- Horel GPS speed is read as m/s. It was treated as knots, so speeds came out at
  about half their value.
- lin pipeline files: the header line is skipped. It was read as a row, which
  made every column text, and a repeated value in the first row of a headerless
  file was altered.
- Horel finalized rows with no observations are dropped.
- lin MetOne air-trend files are read with their own column layout. They were
  matched to the met sensor's, which lost the PM2.5 column.
- Raw LGR files are dated from the style of their file name, not from a table
  of analyzer software versions, so an unknown version no longer stops a read.
- `TimeRange` keeps the minutes and seconds of a string and rejects malformed
  strings.
- `Site.get_obs` matches pollutant names in any case.
- Reads are confined to the time an instrument was installed.
- A read raises `ReaderError` when none of its files can be parsed, and skips a
  level directory the instrument does not have.
- Raw MetOne pressure columns are named in hPa, as the qaqc and final levels
  name them.
- `num_processes="max"` sizes its pool by the CPUs the process may use.
- Parsing a file no longer fails on Windows when the file and the archive root
  are on different drives.
