# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/), and versions
follow [PEP 440](https://peps.python.org/pep-0440/): calendar-based,
`YYYY.M.PATCH`.

## [Unreleased]

### Added

- Raw horel reads take the `*.h5_prior405upgrade` file of a month beside its
  `.h5`. horel split the raw files of the month of each MetOne ES642-to-ES405
  swap (BUS02 2025-03, BUS03 2024-12, TRX01, TRX02 and TRX03 2025-01): the rows
  before the swap are in the second file, which uataq did not read. The
  ES642's last 3 to 13 days before each swap can now be read (raw only; horel's
  qaqc and final files do not have them), and so can TRX01-03's raw ozone
  (`2b_205`) and GPS from 1 January 2025 to the swap, which locate those rows.
  The ES405 does not read these files.

### Changed

- Docs: the front page says what uataq is, who it is for and where to start,
  and lists the pages in groups (Getting started, Guides, Reference, API
  reference, then Contributing). Its "Naming Convention" section, its table of
  four functions and its second "Contributing" heading are gone: the column
  renaming is in "Columns and flags", the four functions are documented on
  "Laboratory" and "General Functions", and the Contributing page stays. "Configuration" moved from under "Laboratory"
  to the Reference group. No address changed.
- Configuration: HDP, HEB and SUG were taken down, so they are marked
  `is_active: false` and their instruments now have removal dates (HDP
  `lgr_ugga` 2025-02-08, HEB `licor_6262` 2025-05-30, SUG `licor_7000`
  2025-08-23). Each is the midnight after the last sample in the archive,
  except HEB's `licor_6262`, which is the day HEB switched to a `licor_7000`.
  A read after one now reports the instrument as inactive instead of finding
  no files. HEB's `licor_7000`, which replaced its `licor_6262` from
  2025-05-30 to 2025-09-16, is added.
- Configuration: WBB's `magee_ae33` and TRX02's `lgr_no2` now have removal
  dates, 2024-06-20 and 2017-06-21, the midnight after their last samples
  (2024-06-19 17:41:53 and 2017-06-20 05:28:52 UTC, at raw, qaqc and final).
  No row is read differently: neither has data after its last sample. A
  `get_obs` of WBB's BC, or of TRX02's NO2 before its `teledyne_t500u` was
  installed (2020-12-22), for a range wholly after the date now raises
  `ReaderError` saying the instrument is inactive, instead of returning an
  empty frame.

### Fixed

- Configuration: 15 removal dates fell on a day that still had data, so a read
  dropped that day's rows and a request for that day reported the instrument
  inactive. Each is now the midnight after the instrument's last sample, with
  the evidence in its `notes`: ASB, DBK, IMC, LG2, LGN, MSA, MUR, SUG and SUN
  `licor_6262`; LDF and ROO `lgr_ugga`; BUS01 `2b_405`; SUG and WBB
  `metone_es642`; WBB `teom_1400ab`. Each date moves one day later. BUS02's
  `2b_405` and WBB's `teledyne_t500u` keep their dates: the rows on those days
  are an instrument being switched on, as their `notes` say.
- Configuration: at the five MetOne swaps (BUS02, BUS03, TRX01, TRX02,
  TRX03), the ES642's `removal_date` and the ES405's `installation_date` are
  now one instant with a time of day, the ES405's first raw row (for example
  TRX01 2025-01-06 19:30:00). The ES642's removal dates had been midnights
  before its last row (up to four days before, at TRX01 and TRX02), so its
  newly read rows would have been cut off; the ES405's first row is after its
  old installation date in every case, so no ES405 row is lost.
- Docs: the quickstart shows its examples again, and the configuration and
  file system pages show the files they quote (`config.json` and the
  `DEFAULT_GROUP` line). All three had been dropped from the built pages.
- `Network` reads a site once when the list names it in two spellings
  (`["WBB", "wbb"]`); it had read the site twice, doubling its rows (#62).
- `Site.get_obs` (and `uataq.get_obs`) returns its columns in the same order on
  every call. It joined the instruments in the order of a set, which changes
  with each Python session (`PYTHONHASHSEED`), so `obs.iloc[:, 0]` was a
  different column from one session to the next, and so was the order of rows
  that share a timestamp. The instruments now follow the order of the
  pollutants asked for (a set of pollutants is sorted; `"all"` follows the
  site's config). Selecting columns by name was never affected (#74).

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
