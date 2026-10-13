"""
Tables of the configured sites and instruments, built when the docs build.

``.. site-catalog::`` writes a table with one row per site, and
``.. instrument-catalog::`` one with a row per instrument name. Both read
``uataq.laboratory`` (built from ``config.json``) and
``uataq.instruments.catalog``, so they always match the package. Neither
reads the data archive, so they build the same anywhere.

``.. site-catalog::`` takes the flag ``:mobile:`` for the mobile sites
(without it, the fixed sites).
"""

import inspect
from pathlib import Path

from docutils.parsers.rst import directives
from sphinx.util.docutils import SphinxDirective

import uataq
from uataq import instruments

SOURCES = [
    Path(uataq.__file__).with_name("config.json"),
    Path(instruments.__file__),
]


def _list_table(header: list[str], rows: list[list[str]], widths: str) -> str:
    """Return reStructuredText for a list-table; a cell may hold several lines."""
    lines = [".. list-table::", "   :header-rows: 1", f"   :widths: {widths}", ""]
    for row in [header, *rows]:
        for i, cell in enumerate(row):
            first, *rest = cell.splitlines() or [""]
            lines.append(("   * - " if i == 0 else "     - ") + first)
            lines.extend(f"       {line}" for line in rest)
    return "\n".join(lines)


def _dates(instrument: instruments.Instrument) -> str:
    """Return when an instrument was installed, and removed if it was."""
    start, stop = instrument.active_range
    assert start is not None  # installation_date is required
    if stop is None:
        return f"since {start:%Y-%m-%d}"
    return f"{start:%Y-%m-%d} to {stop:%Y-%m-%d}"


def _status(site) -> str:
    """Return "yes" when an instrument is still installed, else when the last left."""
    stops = [instrument.active_range.stop for instrument in site.instruments]
    if None in stops:
        return "yes"
    return f"no, since {max(stops):%Y-%m-%d}"


def _pollutants(site) -> str:
    """Return the pollutants of a site's instruments, in configuration order."""
    names: list[str] = []
    for instrument in site.instruments:
        for pollutant in getattr(instrument, "pollutants", ()):
            if pollutant not in names:
                names.append(pollutant)
    return ", ".join(names)


def site_rows(mobile: bool) -> list[list[str]]:
    """Return a row per configured site, fixed or mobile."""
    rows = []
    for SID in uataq.laboratory.sites:
        site = uataq.get_site(SID)
        if isinstance(site, uataq.sites.MobileSite) != mobile:
            continue
        config = site.config
        row = [f"``{SID}``", config["name"]]
        if not mobile:
            zagl = config.get("zagl")
            row += [
                f"{config['latitude']}, {config['longitude']}",
                "" if zagl is None else str(zagl),
            ]
        row += [
            _status(site),
            ", ".join(sorted(site.groups)),
            _pollutants(site),
            "\n".join(
                f"- ``{instrument.name}`` {_dates(instrument)}"
                for instrument in site.instruments
            ),
        ]
        rows.append(row)
    return rows


def instrument_rows() -> list[list[str]]:
    """Return a row per instrument name used in the configuration."""
    used: dict[str, list[str]] = {}
    for SID in uataq.laboratory.sites:
        for instrument in uataq.get_site(SID).instruments:
            used.setdefault(instrument.name, []).append(SID)
    rows = []
    for name in sorted(used):
        site = uataq.get_site(used[name][0])
        cls = type(site.instruments[name])
        link = f":class:`~uataq.instruments.{cls.__name__}`"
        if cls.model != name:
            link += f" (``model``: ``{cls.model}``)"
        summary = (inspect.getdoc(cls) or "").split("\n\n")[0].replace("\n", " ")
        rows.append(
            [
                f"``{name}``",
                link,
                summary,
                ", ".join(getattr(cls, "pollutants", ())),
                ", ".join(used[name]),
            ]
        )
    return rows


class SiteCatalog(SphinxDirective):
    """Render the table of fixed sites, or of mobile ones with ``:mobile:``."""

    option_spec = {"mobile": directives.flag}

    def run(self):
        """Build the table from the configuration."""
        for path in SOURCES:
            self.env.note_dependency(str(path))
        mobile = "mobile" in self.options
        header = ["SID", "Name"]
        widths = "8 14"
        if not mobile:
            header += ["Latitude, longitude", "zagl (m)"]
            widths += " 14 6"
        header += ["Active", "Groups", "Pollutants", "Instruments"]
        widths += " 10 8 12 28"
        text = _list_table(header, site_rows(mobile), widths)
        return self.parse_text_to_nodes(text)


class InstrumentCatalog(SphinxDirective):
    """Render the table of instrument names, their classes and sites."""

    def run(self):
        """Build the table from the configuration and the instrument classes."""
        for path in SOURCES:
            self.env.note_dependency(str(path))
        header = ["Name", "Class", "What it is", "Pollutants", "Sites"]
        text = _list_table(header, instrument_rows(), "14 16 34 12 24")
        return self.parse_text_to_nodes(text)


def setup(app):
    """Register the two directives."""
    app.add_directive("site-catalog", SiteCatalog)
    app.add_directive("instrument-catalog", InstrumentCatalog)
    return {"parallel_read_safe": True, "parallel_write_safe": True}
