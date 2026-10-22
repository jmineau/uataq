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
- Docs: each fact is written on one page, and three pages are renamed to match
  their titles, with no redirects. `docs/general.rst` is now
  `docs/input_parameters.rst` (retitled "Input Parameters", each section
  labeled), `docs/availability.rst` is `docs/what_data_exists.rst` and
  `docs/catalog.rst` is `docs/sites_and_instruments.rst`, so `general.html`,
  `availability.html` and `catalog.html` no longer exist. Moved: the column-name
  pattern and `_cal` against `_raw` from "Pollutants" to "Columns and flags"
  ("Column names"); the "Time" section of "Your first month of data" to "Input
  Parameters" ("Time Range"); "Which sites and pollutants" from "What data
  exists" to "Sites and instruments" ("The same in code"). Quick Start's
  paragraph on what `final` keeps is now a link to "Columns and flags". Pointers
  by section name ("see *Processing Level* on the general functions page") are
  links.
- Docs: "Quick Start" is now "Reading data", and the error cases have their own
  page. `docs/quickstart.rst` is `docs/reading_data.rst`, so `quickstart.html`
  no longer exists. "When there is nothing to read", the last section of "What
  data exists", is now the page `errors.html` with its text unchanged, so
  `what_data_exists.html#when-there-is-nothing-to-read` no longer exists.
  "Several sites at once" moved from "What data exists" to "Reading data"
  (`reading_data.html#several-sites-at-once`). The `read_data` example reads
  the default level instead of `qaqc`, and the page's opening on the
  `laboratory` object is now the docstring of `uataq.laboratory`, shown on the
  "Laboratory" page.
- Docs: the API reference is generated, with a page for each module, class,
  function and class member, as in the docs of the other packages (the page
  "Functions and modules", `functions_and_modules.html`, lists them).
  `gps.html`, `instruments.html`, `pollutants.html`, `sodar.html` and
  `filesystem.html` no longer exist: the module pages are
  `api/uataq.gps.html`, `api/uataq.instruments.html`,
  `api/uataq.pollutants.html`, `api/uataq.sodar.html` and
  `api/uataq.filesystem.html`, and each class and function is under `api/`
  (`api/uataq.instruments.GPS.html`). What the GPS, Pollutants and File System
  pages said by hand is the docstring of the module, shown at the top of its
  page. The File System page's `DataFile`, `GroupSpace` and functions are now
  under `uataq.filesystem.core`, and the group spaces' pages under
  `api/uataq.filesystem.groupspaces.horel.html` and `.lin.html` have one page
  for each class. `read_data` and `get_obs` moved from "Input Parameters"
  (`input_parameters.html#uataq.read_data` and `#uataq.get_obs`), and
  `get_recent_obs`, `get_network_obs` and `Network` from the closing
  "Reference" section of "What data exists" (`what_data_exists.html#reference`,
  `#uataq.get_recent_obs`, `#uataq.get_network_obs` and `#uataq.Network`), to
  `api/uataq.read_data.html`, `api/uataq.get_obs.html` and so on. `TimeRange`
  (`api/uataq.timerange.html`) and the exceptions and warning
  (`api/uataq.errors.html`), which had no page, are documented.
- Docs: the "Laboratory" and "Sites" pages are generated like the rest of the
  API reference, so `laboratory.html` and `sites.html` no longer exist.
  `laboratory`, `get_site` and the `Laboratory` class have pages under `api/`
  (`api/uataq.laboratory.html`, `api/uataq.get_site.html` and
  `api/uataq.Laboratory.html`; the class is documented as `uataq.Laboratory`,
  no longer as `uataq._laboratory.Laboratory`), and `Site` and `MobileSite` are
  listed on the module page `api/uataq.sites.html`, each with its own page
  (`api/uataq.sites.Site.html`). The anchors `laboratory.html#uataq.laboratory`,
  `#uataq.get_site`, `#uataq._laboratory.Laboratory`,
  `sites.html#uataq.sites.Site` and `#uataq.sites.MobileSite` moved to those
  pages. `uataq.laboratory` hides its value, which would be the whole
  configuration. `Site.pollutant_instruments` has a docstring.
- `Instrument.model`, `SensorMixin.pollutants`, `Sodar.model` and
  `Sodar.species_measured` have docstrings, and the Attributes of
  `LinDatFile` and `LGR_UGGA_File` name the ones their `__init__` sets
  (`instrument` and `lvl`; `meta`).
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
- The error for a read that finds no data at a site says what you asked for and
  which files exist. `Site.get_obs("CO2", time_range="2021-08")` at WBB, which
  has no final file that month, raised `No data found for ['lgr_ugga'] at WBB
  (lgr_ugga in lin groupspace).` It now raises `No final data found for CO2 at
  WBB: lgr_ugga in lin groupspace: No files found within the specified time
  range (files run from 2014-02 to 2026-10, with gaps).` The first and last
  period come from the files the read had already listed, so the error costs
  no extra read. `read_data` names
  its instruments where `get_obs` names the pollutants, a read with no `lvl`
  leaves the level out, and the warning for each instrument and `Network`'s
  warning for a site carry the same periods. `ReaderError.detail` holds what
  follows the colon (#63).
- A read with files for the range but no rows in them now warns. `get_obs`
  of WBB's CO2 for 2024-03-04, a day with no rows in the March 2024 file,
  returned an empty table and said nothing. It still returns the empty table,
  and now warns `No final data found for CO2 at WBB (2024-03-04 00:00:00 to
  2024-03-05 00:00:00): the files for lgr_ugga exist but hold no data in that
  range.` `get_recent_obs` and `Network.get_obs` (and so `get_network_obs`)
  warn the same way when their table has no rows. It is a Python warning,
  `uataq.errors.EmptyResultWarning` (a `UserWarning`), so it shows without
  turning the log on. A table with rows from any instrument or site does not
  warn, and `read_data` is unchanged (#63).
- Raw `lgr_ugga` files are parsed with pandas' C engine instead of its
  python engine, about three times faster: 0.2 s to 0.07 s for a day's file,
  and 76 to 26 minutes of CPU for the whole archive (19,554 files at six
  sites). Every one of those files gives the same table as before.
- A raw `lgr_ugga` read (WBB, CSP, FRU, HDP, HPL, ROO) opens only the files
  of the days in its range, plus the day on either side as before. It opened
  every raw file the site has to read its header, before the range was
  applied: a one-day read at WBB, the first on a node, took nearly 5 minutes,
  4 of them opening its 4,472 files; it now takes about 30 s, most of it
  listing the folders. The same files are read and the same rows returned; a
  file outside the range whose header cannot be read is no longer reported.
- A read at a level the instrument does not have says which levels it has.
  `read_data("WBB", "teledyne_t400", lvl="calibrated")`, where the archive has
  no `calibrated` folder for that instrument, raised `FileNotFoundError` for
  the folder; horel, which has no `calibrated` level at all, raised
  `ValueError: DataFile class not found for key: calibrated in horel group.`
  Both now raise `ReaderError: No calibrated data found for ['teledyne_t400'] at
  WBB: teledyne_t400 in lin groupspace: teledyne_t400@WBB has no calibrated
  level (it has raw, qaqc and final).` Because it is a `ReaderError`,
  `Site.read_data` of several instruments logs the ones without the level and
  returns the others, where the first `FileNotFoundError` used to end the read.
  `Instrument.get_files` and `Instrument.get_datafiles` raise it too. A
  `GroupSpace` has a new method, `get_lvls(SID, instrument)`, that lists the
  levels it keeps, from least to most processed. lin lists the level folders of
  the instrument and horel keeps `raw`, `qaqc` and `final`. `get_highest_lvl` is
  the last of them, except for horel, which still looks for the site's
  finalized files (#63).
- Docs: "Input Parameters" no longer says pollutant names are capitalized (case
  does not matter, and the three spellings of NOx are written out);
  "Configuration" lists the site keys (`name`, `latitude`, `longitude`, `zagl`,
  `is_mobile`, `is_active`, `loggers`); "Your first month of data" says
  `America/Denver` is the zone for every site; "Sites and instruments" says that
  `cr1000` and `gps` have no pollutants and that `repr(site)` shows the
  instruments' `notes`; "Installation" no longer lists `abrb`, which is not a
  site, among the site folders.

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
- `MobileSite.merge_gps` (and so `MobileSite.get_obs`, `MobileSite.locate`
  and `Network` for mobile sites) returns each observation once. When two GPS
  fixes fell in the same second of the joining clock (the Pi stamps lin's
  fixes with jitter, so one logged late in a second and the next early in the
  following one can share it), every observation in that second came out
  twice, once with each fix, and nothing marked the copies: 2,194 extra rows
  in TRX01's methane for March 2015 (1,692,767 rows for 1,690,573
  observations). The observation now keeps the fix nearest to it in time
  (#93).
- Mobile reads (`MobileSite.get_obs`, `MobileSite.locate`, and `Network` for
  mobile sites) keep the lin rows near the ends of a time range when the Pi's
  clock is off GPS time. lin rows are joined to lin's GPS on the Pi's clock,
  but the GPS was read over the rows' range in GPS time, so the fixes of the
  rows near the ends were never read and those rows were dropped without a
  warning: on TRX01 from 2016-11-09 00:00 to 06:00, when the Pi ran about 70
  minutes behind, 15,792 rows with methane could be located and 14,399 were.
  lin's GPS is now read a week past the rows' range on each side; the Pi has
  been up to 5 days off (TRX01, 2022-11) (#94).
- `Network.get_availability` counts a `_raw` value as data, as `Network.get_obs`
  keeps it. It looked only at the calibrated columns, so TRX01's
  `lgr_ugga_manual_cal`, whose final files fill only `_raw`, showed as `qaqc`
  (from 2023-11-18 to 2024-03-26 and from 2024-08-21), though `get_obs`
  returned its rows. In the CO2 figure of the docs, TRX01's final data now run to
  July 2026, and a few months at LG2 (October 2019), RPK (December 2012) and
  TRX01 that showed as `qaqc` are `final` (#89).
- Raw lin air-trend files (TRAX, WBB, LDF and the other sites' raw `.csv`
  files) keep the rows whose time has no fraction of a second. The logger
  leaves out the fraction when it is exactly 0 (`2026-10-18T11:05:03` among
  `2026-10-18T00:00:06.116312`), and the times were parsed with a format
  inferred from the first row, so a row of the other shape was dropped: 862
  of 1.45 billion rows across the archive. A file starting with a whole
  second would have lost nearly every row (#95).

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
