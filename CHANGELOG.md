# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/), and versions
follow [PEP 440](https://peps.python.org/pep-0440/): calendar-based,
`YYYY.M.PATCH`.

## [Unreleased]

### Changed

- **Requires Python 3.11 or newer** (breaking): Python 3.10 reaches its end of
  life in October 2026. Tested on 3.11 through 3.14.
- The version now comes from git tags (setuptools-scm). An install from git
  between releases reports a development version such as
  `2025.11.1.dev3+g1a2b3c4` rather than the last release's number.
- The documentation no longer describes class attributes and methods twice: the
  API pages drop a class docstring's `Methods` section and the `Attributes`
  entries that the page documents anyway. Entries that described methods that no
  longer exist (`Site.read_obs`) are gone from the pages.
