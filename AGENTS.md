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

`uataq` (Utah Atmospheric Trace-gas and Air Quality) is a reader for UATAQ
project data. It abstracts over the on-disk layout maintained by UATAQ groups
(group spaces) and exposes a high-level Laboratory → Site → Instrument model
plus convenience top-level functions for reading time-bounded data.

PyPI/import name: `uataq`. Source in `src/uataq/`. Built with **hatchling**
— unlike the user's other packages, which use setuptools.

## Module layout

```
src/uataq/
  __init__.py        top-level API: read_data, get_obs, get_recent_obs,
                     get_network_obs; re-exports Laboratory, Network, etc.
  config.json        UATAQ laboratory configuration (sites + instruments)
                     loaded at import via `_laboratory`
  _laboratory.py     Laboratory factory; builds sites + instruments from
                     config.json (importlib.resources)
  sites.py           Site classes — stationary + mobile; per-site read_data
                     and get_obs methods
  instruments.py     Instrument ABC + concrete subclasses; defines how each
                     instrument's files are parsed
  network.py         Network — multi-site aggregator (used by
                     get_network_obs); returns GeoDataFrame
  errors.py          custom exceptions (DataFileInitializationError,
                     ParserError, ...)
  timerange.py       TimeRange + TimeRangeTypes (str | tuple | list | slice
                     | None)
  gps.py             great-circle helpers (haversine, bearing) +
                     estimate_speed_course(); used by instruments.GPS to fill
                     speed/course the receiver did not record
  sodar.py           Horel/MesoWest SODAR wind-profile reader (Sodar,
                     list_stations). Standalone: NOT wired into config.json /
                     Instrument / GroupSpace (see "SODAR" below). Moved here
                     from lair.mesowest.
  filesystem/
    __init__.py      DataFile, GroupSpace, DEFAULT_GROUP="lin",
                     groups dict, lvls dict, list_files,
                     filter_datafiles, parse_datafiles, get_group
    core.py          implementations of the above
    groupspaces/     per-group disk layout adapters
      __init__.py
      lin.py         Lin group layout
      horel.py       Horel group layout
  py.typed           ships type hints
tests/               pytest
docs/                Sphinx
```

## Public API (from `uataq.__init__`)

Top-level convenience functions:

| Function | Returns | Notes |
|---|---|---|
| `read_data(SID, instruments="all", group=None, lvl=None, time_range=None, num_processes=1, file_pattern=None)` | `dict[str, pd.DataFrame]` | Raw instrument data, per-instrument |
| `get_obs(SID, pollutants="all", format="wide", group=None, time_range=None, num_processes=1, **kwargs)` | `pd.DataFrame` | Processed observations |
| `get_recent_obs(SID, recent=timedelta(days=10), pollutants="all", format="wide", group=None)` | `pd.DataFrame` | Last N days |
| `get_network_obs(sites, pollutant, time_range=None, group=None, num_processes=1)` | `gpd.GeoDataFrame` | Multi-site aggregate, single pollutant; EPSG:4326, indexed by `Time_UTC` |

Re-exported objects:
`sites`, `instruments`, `laboratory` (module-level Laboratory instance,
built from `config.json`), `filesystem`, `DEFAULT_GROUP`, `get_site`,
`Network`.

`uataq.sodar` is **not** imported by `uataq/__init__.py` (keeps xarray off the
`import uataq` path). Use `from uataq.sodar import Sodar`.

## SODAR (`uataq.sodar`)

Reads the Horel group's MesoWest SODAR HDF5 archive:
`horel.MESOWEST_DIR/sodar_data/hdf5archive/` (`horel.MESOWEST_DIR` =
`HOREL_DIR/oper/mesowest`, defined in `filesystem/groupspaces/horel.py`).
Files: `{SID}_full_metadata_log.h5` (`/metagroup/metadata`, `/metagroup/variables`
with `MULT` scale factors) and monthly `{SID}_{YYYY}_{MM}_sodar.h5`
(`/obsdata/observations`: `STATION_ID`, `DATTIM` epoch s, `(n_levels,)` int
columns `HEIGHT` [m, unscaled], `WS`/`WD`/`MXWS` [x MULT]). Stations seen:
USDR1-5, WSLSA, WSMLI. Stray files (`USDR2_2018_12_sodar_p1.h5`,
`all_sodar_metadata.h5`, `_Processed/`) are ignored by the exact-name regex.

API (kept lair-compatible so callers only change the import):

| Call | Returns |
|---|---|
| `Sodar(SID, mesowest_dir=None)` | reads metadata log eagerly; attrs `SID`, `sodar_dir`, `archive_dir`, `metafile`, `meta`, `variables` (indexed by `SHORTNAME`) |
| `Sodar.get_files(lvl="raw", time_range=None)` | `list[str]` of monthly files overlapping `[start, stop)` |
| `Sodar.parse(file, variables)` (static) | `xr.Dataset` `(Time_UTC, level)`; -9999 -> NaN; vars / `MULT`; `level` coord = 0..n-1 |
| `Sodar.read_data(lvl="raw", time_range=None, num_processes=1)` | concat along `Time_UTC` (outer join pads if gate count changes), sorted, sliced `[start, stop)` |
| `Sodar.get_winds_at_height(data, height)` (static) | `pd.DataFrame[direction, speed]` indexed by `Time_UTC`; level matched per timestamp |
| `list_stations(mesowest_dir=None)` | SIDs with a metadata log |

Design: standalone because SODAR stations are MesoWest stations (not UATAQ
sites in `config.json`), output is 2-D `(time, level)` which the pandas
`DataFile`/`parse_datafiles` pipeline can't carry (its xarray driver is a
stub), and the `MULT` scaling lives in a per-station file outside the data
file. Only `lvl="raw"` exists; anything else raises ValueError.

Behavior vs. the old `lair.mesowest` (intentional fixes): `get_winds_at_height`
raises ValueError (listing available heights) instead of IndexError and no
longer reads only the first record's `HEIGHT`; the time slice is half-open
(no extra sample at the next day's 00:00); file names parsed by regex, not
`file[6:13]` (works for any SID length, no `USDR1`/`USDR10` prefix clash);
`FileNotFoundError` when no files match; never `Pool(0)`. The
`LAIR_MESOWEST_DIR` env var / `resolve_mesowest_dir` were dropped (uataq is
CHPC-bound; use `mesowest_dir=`).

## GPS (`uataq.gps` + `instruments.GPS`)

Receivers logging only `GPGGA` (position, altitude, fix quality) record no
speed or course; `GPRMC` carries both. `GPS.read_data` converts recorded speed
from knots to `Speed_m_s`, then calls `GPS.estimate_motion`, which fills
missing `Speed_m_s` / `Course_deg` from the positions and adds the booleans
`Speed_Estimated` / `Course_Estimated` (True exactly where the value came from
positions). **Recorded values are never overwritten** — only NaNs are filled.
Disable with `instrument.read_data(..., estimate_motion=False)`; that keyword
is not forwarded by the top-level `uataq.read_data`.

`estimate_speed_course` is a *centered* difference over `window` samples each
side (class attrs `GPS.estimate_window` = 1, `GPS.estimate_max_gap` = "60s"):
speed = great-circle distance / elapsed time, course = bearing along it. The
first/last `window` samples are NaN, as is anything spanning a gap longer than
`max_gap` (a chord across a gap is not the path travelled) or a non-increasing
time step (duplicate timestamps give NaN, not inf).

Gotchas:
- **Position noise becomes speed noise.** ~3 m of jitter differenced over 1 s
  looks like a few m/s. Validated on TRAX 1 Hz: 2024 matches recorded speed at
  r=0.995 (median diff 0.00 m/s, course 0.4 deg while moving), but 2019 shows
  r=0.82 and a 2.8 m/s p95 while parked. Widen `estimate_window` before
  thresholding a stationary platform.
- **All-NA columns can arrive as strings** (the GPGGA-only years, pandas 3 /
  Arrow). `estimate_motion` coerces a non-numeric `Speed_m_s`/`Course_deg` to
  float before filling — that TypeError was a real crash on 2016 trx01 data.
- lin's `true_course` mapped to `True_Course` while horel mapped to
  `Course_deg`, so lin GPS course silently never reached code expecting the
  horel name (slv's mobile reader). Unified to `Course_deg` (2026-09-22).

## Mental model

```
config.json
   │
   ▼
Laboratory ──── builds ────► Site ──── owns ────► InstrumentEnsemble
                              │                        │
                              ▼                        ▼
                          GroupSpace             Instrument(s)
                          (lin / horel)          (per instrument class)
                              │                        │
                              └──── DataFile(s) ◄──────┘
                                       │
                                       ▼
                                   pandas / geopandas
```

- **`laboratory`** is a process-global singleton built from packaged
  `config.json` at import time.
- **`get_site(SID)`** returns the configured `Site`; `read_data` /
  `get_obs` / `get_recent_obs` delegate to it.
- **`groups`** (in `uataq.filesystem`) is a dict of registered
  `GroupSpace`s keyed by group name. `DEFAULT_GROUP = "lin"`.
- **`lvls`** holds level conventions used by `read_data(lvl=...)`.

## Time range handling

`uataq.timerange.TimeRange` accepts:

- a single string (parsed via pandas)
- a `(start, end)` tuple of `str | datetime | np.datetime64 | None`
- a list of times
- a Python `slice`
- `None` → all available data

Type alias: `TimeRangeTypes = str | TimeRangeTuple | TimeRangeList | slice | None`.
When changing time semantics, update both `timerange.py` and every
public function's docstring — they hand the same alias around.

## Invariants to respect

- **`config.json` is the source of truth** for sites and instruments. Add
  a new site by editing config (and updating any per-instrument parser),
  not by hardcoding it.
- **Group abstraction**: read paths go through `GroupSpace`. Don't bypass
  with raw filesystem walks. New groups live in
  `filesystem/groupspaces/<name>.py`.
- **`DEFAULT_GROUP = "lin"`** is the *tie-breaker*, not a blanket default.
  `Instrument.resolve_group(group)` picks per instrument: an explicit name (or
  a `{instrument: group}` mapping entry) is used as given; otherwise the
  default group when it operates that instrument, else its sole operator, else
  the first configured. `Site.read_data` calls it once per instrument, so one
  site's lin and horel instruments can be read in the same call. It is a
  config lookup, not an archive search -- it does not check whether that group
  holds data for the time range. Before 2026-09-22 `group=None` always meant
  `"lin"`, so the 75 horel-only instruments (of 114) raised ReaderError unless
  the caller named the group. `MobileSite.get_obs` resolves the **gps**
  instrument's group specifically, since the Pi_Time vs Time_UTC merge depends
  on who logged it. If you change the default, update the documented line
  numbers in docs (per the in-file comment).
- **Reads are clipped to the instrument's installed window.**
  `Instrument.clip_to_active` intersects the requested range with
  `active_range` (config `installation_date` / `removal_date`) and the clipped
  range drives **both** file selection and the row slice. Only clipping file
  selection is not enough: a monthly file straddling a swap would still hand
  back the replacement's rows. Groups reuse a file name across an instrument
  change -- the horel group calls both MetOne models `esampler`
  (`{SID}_{YYYY}_{MM}_esampler.h5`) -- so the name cannot tell them apart but
  the dates can. Before 2026-09-22, `read_data("TRX01", "metone_es642")` with
  no time range returned 142 files, 21 of them ES405-era, and the ES405's
  extra `PM01`/`PM04`/`PM10` columns were dropped while `ITMP` was relabelled
  with the ES642's meaning. A request that misses the window entirely still
  raises `InactiveInstrumentError`. Checked against the archive: the only
  horel raw files this excludes are the 441 mis-attributed MetOne ones; no
  other instrument loses a file. Five configured swaps (TRX01/02/03,
  BUS02/03), all non-overlapping, though three share a boundary date exactly
  -- with the inclusive `.loc[start:stop]` slice noted below, a sample landing
  on that timestamp can appear in both.
- **Read-only at the UATAQ data location**. Never write back to source
  data paths.
- **`tables>3.10`** is a hard runtime dep (PyTables). The pin is for
  numpy 2.0 compatibility — keep it when bumping.
- **`xarray`** is a hard runtime dep (only `uataq.sodar` uses it). Keep it
  out of the `import uataq` path.
- **Time ranges are half-open `[start, stop)`** per the docs
  (`general.rst`). `uataq.sodar` implements this exactly. Note
  `filesystem.parse_datafiles` still slices with inclusive `.loc[start:stop]`
  (can include a sample exactly at `stop`) — known inconsistency, not yet fixed.
- **Laboratory instance is shared.** Don't mutate `laboratory.sites` in
  application code; it's the import-time singleton.

## Dev commands

Driven by `just` + `uv`. There is **no `just install`** recipe — use
`uv sync` directly.

| Command | What it does |
|---|---|
| `just test` | `uv run pytest -v` |
| `just quality-check` | ruff (`src/uataq`) + pyright (`src/uataq`) + tests |
| `just ruff` | `uv run ruff check --fix` + `uv run ruff format` on `src/uataq` |
| `just build-docs` | clean + Sphinx HTML build |
| `just pre-commit` | `uv run pre-commit run --all-files` |
| `just clean` | wipe build artifacts, caches, coverage, docs (note:
  cleans `src/*.egg-info`, not bare `*.egg-info`) |

CI: `.github/workflows/` has `tests.yml`, `quality.yml`, `docs.yml`. **All
three are green as of 2026-09-22 — keep them that way.** What that took, and
what will break them again:

- `tests.yml` runs `pytest -m "not chpc"`. Tests needing the real CHPC archive
  carry `@pytest.mark.chpc` (the marker is declared in `pyproject.toml`); the
  `TestNetworkDataRetrieval` class is the current set. Off-cluster they cannot
  pass, so mark new ones rather than letting the job go red. `test_sodar.py`
  separately uses a `skipif` on the archive path.
- `quality.yml` gates on **three** steps, all now clean: ruff, pyright (0
  errors), and `docstr-coverage` at **100%** — that tool fails under 100 by
  default, so a new public function without a docstring turns the job red.
- Intentional lint violations carry an inline `# noqa` with the reason: the
  `E402` imports in `uataq/__init__.py` must follow the NullHandler, and the
  `E402,F403` star import in `groupspaces/__init__.py` must follow the
  `__all__` built from the directory listing.
- **pyright sees a different pandas in CI.** The lock pins pandas 2.3.3 for
  Python < 3.11 and 3.0.1 above it, and the quality workflow runs on 3.10 --
  so the local venv (3.14, pandas 3) can be clean while CI fails on pandas 2
  stubs. That happened once already. Reproduce CI's view before pushing a
  typing change, using a scratch env so the project venv is left alone:
  `UV_PROJECT_ENVIRONMENT=$TMPDIR/venv310 uv sync --frozen --python 3.10` then
  `UV_PROJECT_ENVIRONMENT=$TMPDIR/venv310 uv run --no-sync --python 3.10
  pyright src/uataq`. Never pass `--python` to a bare `uv run` in the repo: it
  recreates `.venv`, and the delete half-fails on NFS, leaving it unusable
  until `rm -rf .venv && uv sync --frozen`.
- Where pyright is wrong rather than the code (pandas overloads, pytables
  nodes, the optional cartopy/matplotlib imports, `File.__exit__` making
  with-block bindings look conditional), suppress inline with a reason. Fix
  real narrowing problems instead of suppressing them.
- `docs.yml` builds with **uv**, not pip + `just`: the `build-docs` recipe
  shells out to `uv run`, so a workflow without uv dies with exit 127 (it did,
  silently, for a while). Autosummary stubs generate into `docs/api/`
  (gitignored); a `:toctree:` pointing outside `docs/` litters the repo root.

## Conventions and tooling

- **Build backend**: hatchling (`pyproject.toml: [tool.hatch.build.targets.wheel]`).
  Wheel packs `src/uataq`. Coverage XML and HTML are checked in via
  `.coverage`, `coverage.xml`, `htmlcov/` — these are test outputs, not
  source.
- **Python**: 3.10+ (`ruff.target-version = "py310"`).
- **Linting**: ruff selects `E, F, UP, B, SIM, I` and ignores `E501`. No
  pydocstyle rules.
- **Types**: pyright. `py.typed` shipped.
- **Logging**: library uses `logging.getLogger(__name__)`; `__init__.py`
  attaches a `NullHandler`. Don't `print()` in library code.

## Common workflows

### Read one site's data
```python
import uataq
df_by_instr = uataq.read_data("WBB", instruments="all", time_range="2024-01")
```

### Get observations (wide format, default)
```python
obs = uataq.get_obs("WBB", pollutants=["CO2", "CH4"], time_range="2024-01")
```

### Network aggregate (single pollutant, multiple sites)
```python
obs = uataq.get_network_obs(
    sites=["WBB", "SUG", "RPK"],
    pollutant="CO2",
    time_range="2024-01",
)
# Returns geopandas.GeoDataFrame:
#   index = Time_UTC
#   columns = SID, [pollutant columns], Latitude_deg, Longitude_deg, zagl, geometry
#   CRS = EPSG:4326
```

### SODAR wind profiles (Horel/MesoWest archive)
```python
from uataq.sodar import Sodar
usdr1 = Sodar("USDR1")
data = usdr1.read_data(time_range=["2019-01-01", "2019-01-31"])  # xr.Dataset
winds = Sodar.get_winds_at_height(data, 100)  # direction/speed at 100 m
```

### Adding a new instrument
1. Implement parser as an `Instrument` subclass in `instruments.py`.
2. Add the instrument to the relevant site entry in `config.json`.
3. Add tests reading a sample file (under `tests/`).

### Adding a new group space
1. Add `filesystem/groupspaces/<name>.py` mirroring the layout of
   `lin.py` / `horel.py`.
2. Register it in `filesystem/groupspaces/__init__.py` so it ends up in
   the `groups` dict.

## Gotchas

- `laboratory` is built at import. Heavy import → slow first `import uataq`.
  Don't add expensive logic to `_laboratory.py`'s import path.
- `read_data(instruments="all")` returns a dict; `get_obs("wide")` returns
  a single DataFrame. Don't confuse the two when wrapping.
- `get_network_obs` is single-pollutant on purpose — multi-pollutant
  aggregates across mixed sites are ill-defined.
- `lvls` and `groups` are module-level dicts in `uataq.filesystem`. They
  are populated by the `groupspaces` subpackage's import side effects —
  don't reorder imports in `filesystem/__init__.py` without checking.
- `filesystem/groupspaces/__init__.py` does `from . import *` over **every**
  non-underscore `.py` in that dir, so only put group-space modules there
  (that's why SODAR lives in `uataq/sodar.py`, not `groupspaces/`).
- Tests needing the real CHPC archive are guarded with
  `pytest.mark.skipif(not os.path.isdir(...))` (no custom markers here).
