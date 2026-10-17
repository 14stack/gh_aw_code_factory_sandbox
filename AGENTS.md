# AGENTS.md

Instructions for AI agents (and humans) working in this repository. The gh_aw_code_factory agents read this file
before changing code.

## What this is

`todo_app` is a deliberately tiny in-memory todo service with a CLI. It is the sandbox product used to test
[gh_aw_code_factory](https://github.com/14stack/gh_aw_code_factory) end to end.

## Layout

- `src/todo_app/store.py`: the `TodoStore` domain logic.
- `src/todo_app/cli.py`: the command-line interface (`todo add "x" done 1 list`).
- `tests/`: pytest tests, one file per module (`test_<module>.py`).

## Commands

| Task | Command |
|---|---|
| Install | `pip install -e ".[dev]"` |
| Lint | `ruff check .` |
| Format check | `ruff format --check .` (fix with `ruff format .`) |
| Test | `pytest` |

CI (`.github/workflows/ci.yml`) runs lint, format check and tests on every PR to `main` and `story/**`. A change is
only done when all three pass.

## Conventions

- Python 3.12+, standard library only at runtime. No new runtime dependencies without an explicit requirement.
- Type hints on public functions. Keep modules small and focused.
- Every behaviour change comes with tests in `tests/`. Bug fixes add a regression test.
- Do not edit `.github/workflows/**`.
