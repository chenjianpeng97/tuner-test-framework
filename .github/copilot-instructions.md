# Copilot instructions for tuner-test-framework

This file gives concise, actionable guidance for an AI coding assistant working in this repository.

- **Big picture:** This repository is a pytest-based test framework for API + browser tests. Key pieces:
  - `main.py` — top-level entry / utility (start here to see script-level behavior).
  - `docs/architecture.md`, `docs/test-case-design.md` — explain the framework design, test patterns and intent.
  - `examples/apimodel_example.py` — a small runnable example showing how the API model is used.
  - `tests/` — contains pytest test modules (see `test_apimodel_*` files for API-model patterns).

- **Languages & versions:** Project targets Python >= 3.13 (see `pyproject.toml`). Prefer modern typing and Ruff formatting rules.

- **How to run tests locally:**
  - Use Python 3.13+.
  - Run tests with: `python -m pytest tests` (or `pytest tests`).
  - Lint/format with Ruff per `pyproject.toml`: `ruff check .` and `ruff format .`.

- **Project-specific patterns to follow**
  - Tests are case-driven and often integrate API-model calls and local utilities (SQL, Excel, JSONPath). Inspect `tests/test_apimodel_*` for concrete patterns.
  - API model objects are exercised via examples in `examples/apimodel_example.py` — follow its request/response handling and assertion style when adding new tests.
  - Documentation in `docs/` is treated as source-of-truth for test design and architecture — prefer aligning code changes with docs updates.

- **Conventions & style**
  - Use Ruff rules configured in `pyproject.toml` (do not change formatting outside these rules).
  - Keep tests small and focused; reuse helpers rather than duplicating SQL/excel/jsonpath logic.
  - Docstrings and inline comments may be in Chinese; preserve intent and mirror language when editing nearby text.

- **Integration points / external tooling**
  - Playwright is referenced in the README as the browser driver used in some end-to-end flows — search for `playwright` if adding browser tests.
  - API modeling and import/export utilities are core integrations; changes to them often require corresponding test updates under `tests/`.

- **What commits should look like**
  - Small, single-purpose commits (e.g., "add API model helper for X", "fix test fixture for Y").
  - Update `docs/` for any architectural or test-pattern changes.

- **Examples to reference when making changes**
  - Example usage: [examples/apimodel_example.py](examples/apimodel_example.py)
  - Core tests: [tests/test_apimodel_core.py](tests/test_apimodel_core.py)
  - Test design guidance: [docs/test-case-design.md](docs/test-case-design.md)

If anything in these notes is unclear or you want expansions (e.g., commands to install optional dev dependencies), tell me which section to expand and I'll iterate.
