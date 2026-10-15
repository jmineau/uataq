> **Keep this file current.** If you change the module layout, the build/test
> commands, or learn a new invariant or gotcha, update the matching section in
> the same change. A section that no longer matches the code is worse than no
> section: fix it or delete it.
>
> Personal or machine-specific notes (local paths, cluster setup) belong in an
> untracked file, not here. Anything matching `*.local.md` is gitignored for
> this (e.g. `CLAUDE.local.md`); add your tool's local files to `.gitignore` if
> they are not covered. Some agents stop reading `AGENTS.md` once a local
> instruction file exists, so import or reference it from yours.

# AGENTS.md — Developer and Agent Guide for uataq

`uataq` (Utah Atmospheric Trace-gas and Air Quality) reads UATAQ data from the
archives the research groups keep on CHPC. It hides each group's on-disk layout
behind a Laboratory → Site → Instrument model and a few top-level functions
(`read_data`, `get_obs`, `get_recent_obs`, `get_network_obs`). Distribution and
import name `uataq`; installed from GitHub, not on PyPI. Contribution mechanics
are in [CONTRIBUTING.md](CONTRIBUTING.md); longer developer notes (mobile clocks,
the MetOne swap files, availability, SODAR) in
[docs/contributing.rst](docs/contributing.rst).

## Module layout

```
src/uataq/
  __init__.py        read_data, get_obs, get_recent_obs, get_network_obs;
                     re-exports laboratory, get_site, Network, DEFAULT_GROUP,
                     TimeRange and the modules below
  config.json        sites and instruments; read at import (importlib.resources)
  _laboratory.py     Laboratory: builds sites and instruments from config.json
  sites.py           Site (stationary) and MobileSite (GPS-located rows)
  instruments.py     Instrument ABC, one subclass per model, and `catalog`
  network.py         Network: many sites, one pollutant (GeoDataFrame);
                     get_availability / plot_availability
  pollutants.py      column grammar {pollutant}[d|channel]_{units}[_cal|_raw]:
                     concentration_columns, parse_column, POLLUTANTS
  gps.py             haversine, bearing, estimate_speed_course,
                     gps_time_from_time_of_day
  sodar.py           Horel/MesoWest SODAR profiles (Sodar, list_stations);
                     standalone, not in config.json, not imported by uataq
  timerange.py       TimeRange and the TimeRangeTypes alias
  errors.py          ReaderError and its subclasses, ParserError, EmptyResultWarning, ...
  filesystem/
    __init__.py      DEFAULT_GROUP, get_group; re-exports core
    core.py          DataFile, GroupSpace, groups, lvls, list_files,
                     filter_datafiles, parse_datafiles, cpu_count
    groupspaces/     one module per research group's archive (lin, horel)
tests/               pytest
docs/                Sphinx; docs/_ext/ holds two local extensions
```

How a read flows: `laboratory` (a process-wide singleton built at import) holds
the `Site`s; `get_site(SID)` returns one, and the top-level functions delegate
to it. A `Site` asks each `Instrument` which group to read each part of the
range from (`plan_reads`); the instrument gets its files from that group's
`GroupSpace` (`filesystem.groups[name]`), whose `DataFile` classes parse them;
the frames are standardized to uataq's column names and concatenated in time.
`filesystem.lvls` ranks the levels (`raw` < `qaqc` < `calibrated` < `final`).

## Invariants

- **`config.json` is the source of truth** for sites and instruments. A new
  site or instrument is a config entry (plus a parser if the model is new),
  never a hard-coded case. `docs/config.rst` documents its keys.
- **`installation_date`, `removal_date` and `group_dates` are instants**
  (`pd.to_datetime`; a date alone is midnight UTC) and windows are half-open.
  So a `removal_date` is **the midnight after the last sample** at any level;
  a date on a day that still has data hides that day. Take the last sample
  from the data (the last row with a value in the instrument's own columns:
  horel's qaqc and final files hold a whole platform) and write it in the
  instrument's `notes`; a date set otherwise says why there. At a swap the
  replacement's `installation_date` must not fall before the removed one's
  `removal_date` (`tests/test_config.py` lists the swaps); at the MetOne
  swaps both are one instant with a time of day, the ES405's first raw row.
- **Reads are clipped to the installed window.** `Instrument.clip_to_active`
  intersects the request with `active_range`, and the clipped range drives
  both file selection and the row slice. Both are needed: groups reuse a file
  name across an instrument change (horel calls both MetOne models
  `esampler`), so a monthly file that straddles a swap holds the replacement's
  rows. A request that misses or only touches the window raises
  `InactiveInstrumentError`.
- **Every read goes through a `GroupSpace`.** No raw filesystem walks outside
  `filesystem/`.
- **`DEFAULT_GROUP = "lin"` is a tie-breaker, not a default for everything.**
  With `group=None`, `Instrument.resolve_group` takes the default group if it
  operates the instrument, else its sole operator, else the first configured.
  It is a config lookup: it never checks the archive and ignores
  `group_dates`. Anything that wraps `Site.read_data` must pass `group=None`
  through, never replace it with `get_group(None)`, which would send
  horel-only instruments to lin.
- **Reads are planned by time.** `Instrument.plan_reads(group, time_range)`
  returns `[(group, portion), ...]`: one portion for a named group; with none,
  the clipped range is cut at each `group_dates` edge and each piece goes to
  the most preferred group covering it (default group, then `loggers` order).
  `Site.read_data` reads each portion and concatenates them; a failing portion
  is logged and skipped, and all failing raises `ReaderError`.
- **A period can have two raw files.** horel split the month of each MetOne
  swap into `{SID}_{YYYY}_{MM}_esampler.h5` and the same name plus
  `horel.PRIOR_405_SUFFIX` (the month up to the swap), and `HorelGroup.get_datafiles`
  adds the suffixed file to every raw read except the ES405's. So
  `filter_datafiles` drops every file that starts at the range's stop, not
  only the last one.
- **One group's mobile rows are located only with that group's own GPS**,
  because each group's instruments share their GPS's logger clock (lin: the
  Pi, joined on `Pi_Time`; horel: the CR1000, joined on `Time_UTC`).
  `MobileSite.locate` replays each instrument's `plan_reads` to split its frame
  by group, and `_gps_group` raises `ValueError` rather than borrow another
  group's GPS. Every located row carries `GPS_Group`, which says which clock
  its `Time_UTC` is on.
- **Time ranges are half-open `[start, stop)`** everywhere: `TimeRange`
  (including `__contains__`), `filesystem.parse_datafiles` and `uataq.sodar`
  exclude a sample exactly at `stop` (`.loc[start:stop]` alone is inclusive).
  A string stop is the end of the period it names (`"2024"` stops at
  2025-01-01). If time semantics change, change `timerange.py` and every
  public docstring that describes them (`docs/input_parameters.rst` too).
- **Never write to the data archives.** uataq only reads.
- **`laboratory` is shared**: don't mutate `laboratory.sites`.
- **`import uataq` stays light.** `uataq.sodar` (the only xarray user) is not
  imported by `__init__`; matplotlib and cartopy are optional imports inside
  the plotting methods. uataq never imports lair (its import downloads the CCG
  filter); display metadata for pollutants lives in `lair.pollutants`.
- **uataq does not set pandas options.** Code must be right with copy-on-write
  on or off: no chained assignment, and `.copy()` a filtered frame before
  setting values on it.
- **Dependencies:** `tables>3.10` is pinned for numpy 2 compatibility; keep
  it when bumping. `xarray` is a runtime dependency for `uataq.sodar` only.
- **Logging:** modules use `logging.getLogger(__name__)`; `__init__.py`
  attaches a `NullHandler`. No `print()` in library code. Logging is off
  until the user turns it on, so what a user must see anyway (a table with no
  rows) is a `warnings.warn` of a category defined in `errors.py`
  (`EmptyResultWarning`).

## Development workflow

Driven by `just` and `uv`; CI runs the same recipes.

| Command | What it does |
|---|---|
| `just sync` | `uv sync`: uataq (editable) and the dev tools |
| `just lock` | `uv lock` after changing dependencies; commit `uv.lock` with them |
| `just quality-check` | `lint` + `type-check` + `docstr` + `test` |
| `just test` | pytest in parallel (up to 8 workers), skipping `network`, `slow` and `chpc`; extra args go to pytest (`-n 0` for serial) |
| `just cov` | the same with coverage (what `tests.yml` runs) |
| `just lint` / `just format` | ruff check and format check / fix and format |
| `just type-check` | pyrefly |
| `just docstr` | docstring coverage of the public API, at 100% |
| `just build-docs` | Sphinx HTML into `docs/_build`, running every example; a warning fails the build |
| `just docs-serve` | live docs preview on port 8000 |
| `just pre-commit` | every pre-commit hook on every file |
| `just changelog` | draft CHANGELOG entries from the commits since the last tag |
| `just dist` / `just version` | build and check the sdist and wheel / print the version |
| `just release X.Y.Z` | tag and push a release (the maintainer runs it) |

CI (`.github/workflows/`): `tests.yml` runs `just cov` on Linux, macOS and
Windows × Python 3.11–3.14; `quality.yml` runs lint, type-check and docstr on
3.11; `docs.yml` builds the docs for every pull request and publishes `dev/`,
each release and `stable/` to `gh-pages`; `publish.yml` makes a GitHub Release
from a `vYYYY.M.PATCH` tag. The version comes from git tags (setuptools-scm);
release steps are in CONTRIBUTING.md. Tooling comes from
[jmineau/python-template](https://github.com/jmineau/python-template) via
copier: change it there and run `copier update`.

Conventions: Python 3.11+; ruff rules in `pyproject.toml`; numpy-style
docstrings with a one-line imperative summary on the second line (D213; tests
need none and are not held to the imperative); Conventional Commits, which
`just changelog` groups.

What keeps CI green:

- **Tests that need the real archive carry `@pytest.mark.chpc`** (declared in
  `pyproject.toml`; `just test` and CI skip it), or a `skipif` on the archive
  path (`tests/test_sodar.py`). Off-cluster they cannot pass, so mark new ones.
- **Parser tests run off-cluster** on a few synthetic lines written to
  `tmp_path` in the real format, never on checked-in archive data:
  `tests/test_horel.py` has `write_h5` and `write_csv_gz`, `tests/test_lin.py`
  has `write_ugga` and patches `lin.DATA_CONFIG` entries.
- **Suppress only with a reason**: an inline `# noqa` (as on the `E402`
  imports in `uataq/__init__.py`) or, where pyrefly is wrong rather than the
  code (pandas-stubs overloads, PyTables nodes), `# pyrefly: ignore[<code>]`.
  Fix real narrowing problems instead.
- **CI type-checks on Python 3.11.** If CI disagrees with your newer local
  `.venv`, check in a separate environment so `.venv` is left alone:
  `UV_PROJECT_ENVIRONMENT=<dir> uv sync --frozen --python 3.11`, then
  `UV_PROJECT_ENVIRONMENT=<dir> uv run --no-sync pyrefly check`. Never pass
  `--python` to a bare `uv run` in the repo: it recreates `.venv`.
- **`just docstr` is at 100%**: a public function, class or module without a
  docstring turns the quality job red.

## Docs

**Each page answers one question a student has, and each fact is written on
one page; other pages link to it.** The front page (`docs/index.rst`) lists the
pages in the order a student asks them, in captioned groups: Getting started,
Guides, Reference, API reference, then Contributing. A new fact goes on the
page that holds its kind; a new page needs a question no page answers, and goes
in one group. A change that moves a fact or renames or retitles a page updates
its row in the table below.

| Fact | Page (file) |
|---|---|
| Install, environments, Slurm | Installation (`installation`) |
| A first read, in local time | Your first month of data (`first_month`) |
| When a site has data, the newest data | What data exists (`what_data_exists`) |
| `read_data` and `get_obs`, the `long` format, several sites, mobile sites | Reading data (`reading_data`) |
| Errors and empty results | When there is nothing to read (`errors`) |
| Sites, instruments, what each measures, glossary | Sites and instruments (`sites_and_instruments`) |
| Columns of each level, column names, `ID`, flags, what `final` keeps, empty `_cal` | Columns and flags (`columns`) |
| Arguments: site, instruments, group, level, time range (every form), processes | Input Parameters (`input_parameters`) |
| Config keys | Configuration (`config`) |
| Developer notes | Contributing (`contributing`) |
| Function and class details, what a module is for | the docstrings, on the generated API pages (`api`) |

- **The build fails on any warning** (`-W`). It loads intersphinx inventories,
  so it needs network access. In a docstring, write types that exist
  (`dict[str, str]`, not `dict[group, logger]`): Sphinx tries to link every
  name.
- **Examples run when the docs build**, and a broken one fails it: a
  `.. plot::` directive in a docstring's Examples section (`>>>` lines work),
  or a `.. ipython:: python` block in an `.rst` page (`@savefig name.png`
  above a plot keeps it; `:okexcept:` / `:okwarning:` allow a block meant to
  raise or warn). All `.rst` pages share one IPython session, so each page
  imports what it uses. Notebooks are off (`docs_notebooks` in copier).
- **A running example must not read the archive**, which CI does not have. It
  may use the packaged config (`uataq.get_site`, as on the Sites and
  instruments page), synthetic data, or a public download, and seeds any random
  numbers. Examples that need the archive (the reading-data, what-data-exists,
  errors, first-month, columns and input-parameters pages) are plain
  `code-block` or `pycon` blocks holding the output of a run on CHPC (in a
  docstring, `>>>` lines without `.. plot::` are not run: `uataq.gps`). When the
  API they show changes, rerun them there and update the page, and its figure
  in `docs/_static/` if it has one.
- **The site and instrument tables are generated.** The `site-catalog` and
  `instrument-catalog` directives in `docs/sites_and_instruments.rst`
  (`docs/_ext/catalog.py`) build them from `uataq.laboratory` and
  `uataq.instruments.catalog` on every build, so a config or class change needs
  no docs edit. A site is "active" there when one of its instruments has no
  `removal_date`; the site-level `is_active` key is read by no code.
- **The API reference is generated**, except `laboratory.rst` and `sites.rst`:
  `docs/api.rst` lists the functions and modules, and each module, class,
  function and class member gets a page in `docs/api/` (gitignored; a
  `:toctree:` pointing outside `docs/` litters the repo root). A module's
  docstring is its page's text. A class member gets its own page when it has a
  docstring (a `#:` comment on a class-level attribute, whose first line holds
  no colon: napoleon reads it as `type: description`); one set in `__init__` is
  described in the class docstring's Attributes section instead.
  `docs/_templates/autosummary/` and `docs/_ext/api_pages.py` (from
  python-template) build the pages. In a docstring, write a `:doc:` path from
  the docs root (`/columns`).

## Common changes

**A new instrument.** An `Instrument` subclass in `instruments.py` (and a
`DataFile` in the group's module if the format is new), its entry in
`config.json` with dates and `notes`, and parser tests on synthetic lines.

**A new group space.** Add `filesystem/groupspaces/<name>.py` with a
`GroupSpace` subclass, its `DataFile` classes and a `column_mapping` dict (the
group's column names to uataq's, applied by its `standardize_data`), modeled on
`lin.py` and `horel.py`, and register it at the bottom of that module:
`filesystem.groups["<name>"] = <Name>Group()`. Nothing else needs to import
it: `groupspaces/__init__.py` star-imports every non-underscore module in the
folder. Its API page appears by itself (`docs/api.rst` lists `filesystem` recursively).

## Gotchas

- **`import uataq` reads the lin pipeline's `data_config.json`**: from the
  archive on CHPC, otherwise fetched from the `uataq/data-pipeline` repository
  on GitHub. Off-cluster, importing uataq (and so the test suite) needs
  network access.
- **Only group-space modules go in `filesystem/groupspaces/`**: anything else
  there would be imported as one. That is why SODAR is `uataq/sodar.py`.
- **`filesystem.groups` is filled by importing the group-space modules**, so
  don't reorder the imports in `filesystem/__init__.py` without checking.
- `read_data` returns a dict of frames, one per instrument; `get_obs` returns
  one frame. Don't confuse them when wrapping.
- `get_network_obs` and `Network` take one pollutant on purpose: several
  pollutants across mixed sites have no common shape.
- GPS speed and course estimated from positions only fill NaNs (flagged in
  `Speed_Estimated` / `Course_Estimated`). All-NA columns can arrive as
  strings, so `estimate_motion` coerces them first. The top-level
  `uataq.read_data` does not forward `estimate_motion=False`.
- **Use `filesystem.cpu_count()`**, not `multiprocessing.cpu_count()`, for
  `num_processes="max"`: it respects the CPU affinity a scheduler sets. A
  script that uses `num_processes > 1` needs a `__main__` guard (Python 3.14
  defaults to forkserver).
- `Network.get_availability` parses every file, so a whole network is
  thousands of files: run it on a compute node.
