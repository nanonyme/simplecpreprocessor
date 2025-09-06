# Copilot Instructions

Follow the development, linting, and testing process described in
[CONTRIBUTING.md](../CONTRIBUTING.md).

## Key rules for all code suggestions

- **Lint‑clean output only**: Code must pass `flake8` with:
  - `max-line-length = 79`
  - **No** unused imports
  - **No** unused variables
- **PEP 8 compliant**: Follow standard Python style conventions.
- **Import hygiene**: Only import what is actually used in the code.
- **Readable formatting**: Break long expressions across lines to stay within
  the 79‑character limit.
- **Testing**: Run tests with
  `pytest -v --cov=simplecpreprocessor --cov-config .coveragerc --cov-report=term-missing`
- **Coverage**: Maintain or improve test coverage; never decrease it.

When generating code, apply these rules before returning the final output.
