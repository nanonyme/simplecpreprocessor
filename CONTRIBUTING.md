# Contributing Guidelines

Thank you for considering a contribution to this project. This document describes expectations for code contributions, environment setup, and testing.

## Licensing

By submitting a pull request, you confirm that:
- You have the right to release the contributed code.
- Your contribution will be licensed under the terms described in LICENSE.txt.

## Branching and scope

- Feature branches are strongly recommended, though not required.
- All new functionality must include unit tests.
- Test‑driven development is encouraged to ensure testability.
- Reports of incomplete or incorrect behavior will be evaluated for scope fit; scope may be adjusted if there is willingness to contribute features.

## Development setup

Create and use a virtual environment, then install development tools:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r dev-requirements.txt
```

You do not need to install the package itself to run tests.

## Linting

Run flake8 on the main package (matches CI):

```bash
flake8 simplecpreprocessor
```

All contributions must pass linting with no errors.

## Testing and coverage

Run tests with coverage (matches CI):

```bash
 py.test -v --cov=simplecpreprocessor --cov-config .coveragerc --cov-report=term-missing
```

Coverage must remain at or above the current threshold. Coverage reports are generated automatically in CI.

## Pull requests

- Keep PRs focused and scoped to a single feature or fix.
- Include relevant tests and documentation updates.
- CI will enforce linting and coverage before merge.
