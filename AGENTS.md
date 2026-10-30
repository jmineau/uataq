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
are in [CONTRIBUTING.md](CONTRIBUTING.md); the module layout and how a read flows,
adding an instrument or a group space, how the docs are organized and generated,
and longer developer notes (mobile clocks, the MetOne swap files, availability,
SODAR) are in [docs/contributing.rst](docs/contributing.rst).

## Invariants

- **`config.json` is the source of truth** for sites and instruments. A new
  site or instrument is a config entry (plus a parser if the model is new),
  never a hard-coded case. `docs/reference/config.rst` documents its keys.
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
  both file selection and the row slice (why both: `docs/contributing.rst`,
  "The MetOne swap files"). A request that misses or only touches the window
  raises `InactiveInstrumentError`.
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
- **A period can have two raw files** (the month of each MetOne swap; see
  `docs/contributing.rst`), so `filter_datafiles` drops every file that starts at
  the range's stop, not only the last one.
- **One group's mobile rows are located only with that group's own GPS**,
  because each group's instruments share their GPS's logger clock.
  `MobileSite._gps_group` raises `ValueError` rather than borrow another
  group's GPS. Every located row carries `GPS_Group`, which says which clock
  its `Time_UTC` is on.
- **Time ranges are half-open `[start, stop)`** everywhere: `TimeRange`
  (including `__contains__`), `filesystem.parse_datafiles` and `uataq.sodar`
  exclude a sample exactly at `stop` (`.loc[start:stop]` alone is inclusive).
  A string stop is the end of the period it names (`"2024"` stops at
  2025-01-01). If time semantics change, change `timerange.py` and every
  public docstring that describes them (`docs/reference/input_parameters.rst` too).
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
  rows, a pollutant left out) is a `warnings.warn` of a category defined in
  `errors.py` (`EmptyResultWarning`, `DroppedPollutantWarning`).

## Development workflow

Driven by `just` and `uv`; CI runs the same recipes.

| Command | What it does |
|---|---|
| `just sync` / `just lock` | `uv sync`: uataq (editable) and the dev tools / `uv lock` after changing dependencies (commit `uv.lock` with them) |
| `just quality-check` | `lint` + `type-check` + `docstr` + `test` |
| `just test` | pytest in parallel (up to 8 workers) over `tests` and the `>>>` examples under `src`, skipping `network`, `slow` and `chpc`; extra args go to pytest (`-n 0` for serial) |
| `just cov` | `just test` with coverage (what `tests.yml` runs) |
| `just lint` / `just format` | ruff check and format check / fix and format |
| `just type-check` / `just docstr` | pyrefly / docstring coverage of the public API, at 100% |
| `just build-docs` | Sphinx HTML into `docs/_build`, running every example; a warning fails the build |
| `just docs-serve` / `just pre-commit` | live docs preview on port 8000 / every pre-commit hook on every file |
| `just changelog` | at release, draft the CHANGELOG entries from the commits since the last tag |
| `just dist` / `just version` | build and check the sdist and wheel / print the version |
| `just release X.Y.Z` | tag and push a release (the maintainer runs it) |

CI runs the same recipes (CONTRIBUTING.md describes it, and `lock-upgrade.yml`,
which upgrades `uv.lock` monthly). A pull request leaves `CHANGELOG.md` alone:
the maintainer writes it at release. The version comes from git tags
(setuptools-scm); release steps are in CONTRIBUTING.md. Tooling comes from
[jmineau/python-template](https://github.com/jmineau/python-template) via copier:
change it there and run `copier update`.

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
  `.venv`, check in a separate environment so `.venv` is left alone (recipe in
  CONTRIBUTING.md). Never pass `--python` to a bare `uv run` in the repo: it
  recreates `.venv`.
- **`just docstr` is at 100%**: a public function, class or module without a
  docstring turns the quality job red.

## Docs

**Each page answers one question a student has, and each fact is written on
one page; other pages link to it.** The front page (`docs/index.rst`) lists four
sections, the navbar: Getting started, Guides, Reference (folders of `docs/`,
each with an `index.rst` listing its pages in the order a student asks them),
and Contributing. A new fact goes on the page that holds its kind; a new page
needs a question no page answers, and goes in one section's folder and index. A change that moves a fact or renames or retitles a page updates
its row in the table in `docs/contributing.rst` ("Writing the docs").

- **The build fails on any warning** (`-W`). It loads intersphinx inventories,
  so it needs network access. In a docstring, write types that exist
  (`dict[str, str]`, not `dict[group, logger]`): Sphinx tries to link every
  name.
- **Examples run when the docs build**, and a broken one fails it: a
  `.. plot::` directive in a docstring's Examples section (`>>>` lines work),
  or a `.. ipython:: python` block in an `.rst` page (options in
  `docs/contributing.rst`). All `.rst` pages share one IPython session, so each
  page imports what it uses; no multi-line statement may be a block's 10th (or
  100th): the directive runs only its first line. Notebooks are off.
- **A running example must not read the archive**, which CI does not have. It
  may use the packaged config (`uataq.get_site`, as on the Sites and
  instruments page), synthetic data, or a public download, and seeds any random
  numbers. Examples that need the archive (listed in `docs/contributing.rst`)
  are plain `code-block` or `pycon` blocks holding the output of a run on CHPC.
  `just test` also runs every `>>>` example under `src/` (`--doctest-modules`):
  one that needs the archive gets `# doctest: +SKIP` on its `>>>` line.
  When the API they show changes, rerun them there and update the page, and its
  figure in `docs/_static/` if it has one.
- **The site and instrument tables are generated** on every build
  (`docs/_ext/catalog.py`): a config or class change needs no docs edit.
- **The API reference is generated** (`docs/contributing.rst`). A class member
  gets its own page when it has a docstring (a `#:` comment on a class-level
  attribute, whose first line holds no colon: napoleon reads it as
  `type: description`); one set in `__init__` is described in the class
  docstring's Attributes section instead. In a docstring, write a `:doc:` path
  from the docs root (`/columns`). A data attribute whose repr is long
  (`uataq.laboratory`) ends its `#:` comment with `:meta hide-value:`.

## Gotchas

- **`import uataq` reads the lin pipeline's `data_config.json`**: from the
  archive on CHPC, otherwise fetched from the `uataq/data-pipeline` repository
  on GitHub. Off-cluster, importing uataq (and so the test suite) needs
  network access.
- **Only group-space modules go in `filesystem/groupspaces/`**: anything else
  there would be imported as one. That is why SODAR is `uataq/sodar.py`.
- **`filesystem.groups` is filled by importing the group-space modules**, so
  don't reorder the imports in `filesystem/__init__.py` without checking.
- `read_data` returns a dict of frames, one per instrument; `get_obs` one frame
  with a text `instrument` column (take means with `numeric_only=True`).
- `get_network_obs` and `Network` take one pollutant on purpose: several
  pollutants across mixed sites have no common shape.
- The top-level `uataq.read_data` does not forward `estimate_motion=False`
  (what the estimate fills, and its flags, are in the `GPS` docstring).
- **Use `filesystem.cpu_count()`**, not `multiprocessing.cpu_count()`, for
  `num_processes="max"`: it respects the CPU affinity a scheduler sets. A
  script that uses `num_processes > 1` needs a `__main__` guard (Python 3.14
  defaults to forkserver).
- `Network.get_availability` parses every file, so a whole network is
  thousands of files: run it on a compute node.
