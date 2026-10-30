# Contributing to UATAQ

Thank you for considering contributing to UATAQ! We welcome contributions from the community.

This project is developed with the help of AI coding agents, directed and
reviewed by the maintainer, who owns the design and the science. If you
contribute with an agent, [AGENTS.md](AGENTS.md) at the repository root is
the orientation file it should read.

## Getting Started

1. Fork the repository on GitHub
2. Clone your fork locally:
   ```bash
   git clone https://github.com/YOUR_USERNAME/uataq.git
   cd uataq
   ```
3. Install uataq and the development tools with [uv](https://docs.astral.sh/uv/):
   ```bash
   uv sync  # .venv with uataq (editable) and the dev tools
   ```
   Without uv: `python -m venv .venv`, activate it, then
   `pip install --group dev -e .` (needs pip 25.1 or newer).

4. Install pre-commit hooks:
   ```bash
   uv run pre-commit install
   ```

## Development Workflow

1. Create a new branch for your feature or bugfix:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. Make your changes and ensure they follow our coding standards:
   - Code is formatted with ruff
   - All tests pass
   - New features include tests
   - Documentation is updated if needed

3. Run quality checks:
   ```bash
   just quality-check
   ```

4. Run the test suite (it also runs the `>>>` examples in the docstrings under
   `src/`; an example that needs data CI lacks gets `# doctest: +SKIP`):
   ```bash
   just test
   ```

5. Run pre-commit checks:
   ```bash
   just pre-commit
   ```

6. Commit your changes:
   ```bash
   git add .
   git commit -m "fix(gps): keep rows without a fix"  # Conventional Commits
   ```

7. Push to your fork:
   ```bash
   git push origin feature/your-feature-name
   ```

8. Open a Pull Request on GitHub

## Continuous integration

CI (`.github/workflows/`) runs the same `just` recipes:

- `tests.yml` runs `just cov` on Linux, macOS and Windows × Python 3.11–3.14.
- `quality.yml` runs lint, type-check and docstr on Python 3.11.
- `docs.yml` builds the docs for every pull request and publishes `dev/`, each
  release and `stable/` to `gh-pages`.
- `publish.yml` makes a GitHub Release from a `vYYYY.M.PATCH` tag (see
  Releasing).
- `lock-upgrade.yml` upgrades `uv.lock` once a month (see Dependency updates).

CI type-checks on Python 3.11. If it disagrees with your newer local `.venv`,
check in a separate environment so `.venv` is left alone:

```bash
UV_PROJECT_ENVIRONMENT=<dir> uv sync --frozen --python 3.11
UV_PROJECT_ENVIRONMENT=<dir> uv run --no-sync pyrefly check
```

## Releasing

The version comes from git tags (setuptools-scm), so there is no version string
to bump. Releases are calendar-based: `YYYY.M.PATCH`.

1. Pull requests leave `CHANGELOG.md` alone, so write it now: run `just changelog` to draft entries from the commit messages, edit them
   into `CHANGELOG.md` under `## [Unreleased]`, then rename that heading to
   `## [YYYY.M.PATCH] - YYYY-MM-DD` and start a new empty `## [Unreleased]`
   above it. In the same commit, change the tag in the install commands to the new
   release (`vYYYY.M.PATCH`); `grep -rnE 'v20[0-9]{2}\.[0-9]+\.[0-9]+' README.md docs` lists
   them (the README and the Installation page, in the commands and the text). Commit
   (`chore(release): YYYY.M.PATCH`) and push to `main`.
2. Run `just release YYYY.M.PATCH`. It checks that the tree is clean, that
   `main` is in sync with GitHub, and that the version is newer than every
   existing tag, then pushes the tag `vYYYY.M.PATCH`.
3. The Publish workflow builds the tag and creates the GitHub Release from the
   CHANGELOG section (uataq is not on PyPI); Zenodo archives it. The
   Documentation workflow publishes its docs in the version dropdown.

## Dependency updates

Dependabot opens one pull request a month for each of GitHub Actions and
pre-commit hooks. Merge it when CI passes.

`uv.lock` (the dev tools and every dependency) is updated by the Upgrade lock
workflow alone, not by Dependabot, which would leave a package at its old
version when the newest release needs a newer Python than the oldest one this
project supports. On the 1st of each month the workflow runs `uv lock --upgrade`
(`uv.lock` then holds the newest release for each Python; it never raises the
minimum versions in `pyproject.toml`) and, when the lock changes, opens the pull
request `chore/lock-upgrade` (or updates it). GitHub does not start workflows on
a pull request that its own token opened, so the workflow starts Tests, Code
Quality and Documentation on the branch itself; their results show on the pull
request. Merge it when they pass. You can also run it by hand: Actions > Upgrade
lock > Run workflow.

## Template

The tooling (CI workflows, pre-commit, justfile, packaging configuration) comes
from [jmineau/python-template](https://github.com/jmineau/python-template).
`.copier-answers.yml` records the template version; `copier update` pulls in
later template changes. Improvements that would help every package are best
made in the template.

## Pull Request Guidelines

- Keep pull requests focused on a single feature or bugfix
- Write clear, descriptive commit messages
- Leave `CHANGELOG.md` alone: the release notes are drafted from your commit
  messages at release, so write each as the line a user would read
- Ensure all tests pass
- Maintain or improve test coverage
- Update documentation as needed

## Reporting Bugs

When reporting bugs, please include:
- Your operating system and Python version
- Steps to reproduce the issue
- Expected behavior
- Actual behavior
- Any error messages or logs

## Feature Requests

We welcome feature requests! Please:
- Check if the feature has already been requested
- Provide a clear description of the feature
- Explain why it would be useful
- Consider submitting a pull request to implement it

## Questions?

If you have questions, please:
- Check existing issues and discussions
- Open a new issue with the "question" label
- Reach out to the maintainers

## Code of Conduct

Please be respectful and constructive in all interactions. We aim to maintain a welcoming and inclusive community.

## License

By contributing, you agree that your contributions will be licensed under the same license as the project (MIT License).
