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

4. Run test suite:
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

## Releasing

The version comes from git tags (setuptools-scm), so there is no version string
to bump. Releases are calendar-based: `YYYY.M.PATCH`.

1. Run `just changelog` to draft entries from the commit messages, edit them
   into `CHANGELOG.md` under `## [Unreleased]`, then rename that heading to
   `## [YYYY.M.PATCH] - YYYY-MM-DD` and start a new empty `## [Unreleased]`
   above it. Commit (`chore(release): YYYY.M.PATCH`) and push to `main`.
2. Run `just release YYYY.M.PATCH`. It checks that the tree is clean, that
   `main` is in sync with GitHub, and that the version is newer than every
   existing tag, then pushes the tag `vYYYY.M.PATCH`.
3. The Publish workflow builds the tag and creates the GitHub Release from the
   CHANGELOG section (uataq is not on PyPI); Zenodo archives it. The
   Documentation workflow publishes its docs in the version dropdown.

## Template

The tooling (CI workflows, pre-commit, justfile, packaging configuration) comes
from [jmineau/python-template](https://github.com/jmineau/python-template).
`.copier-answers.yml` records the template version; `copier update` pulls in
later template changes. Improvements that would help every package are best
made in the template.

## Pull Request Guidelines

- Keep pull requests focused on a single feature or bugfix
- Write clear, descriptive commit messages
- Update the changelog if applicable
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
