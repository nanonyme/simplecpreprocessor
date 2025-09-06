# Copilot Instructions

Follow the development, linting, and testing process described in [CONTRIBUTING.md](../CONTRIBUTING.md).

Key points for this repository:
- Always run linting with `flake8 simplecpreprocessor` before committing.
- Run tests with `py.test -v --cov=simplecpreprocessor --cov-config .coveragerc --cov-report=term-missing --cov-report=xml`.
- Maintain or improve coverage; do not decrease it.
