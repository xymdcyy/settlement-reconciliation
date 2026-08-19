# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**结算对账中心 (Settlement Reconciliation Center)** — a Python project for settlement reconciliation workflows. Currently in initial scaffold state.

- Python 3.10+ (see `.python-version`)
- Package name: `settlement-reconciliation`
- Build system: standard `pyproject.toml` (no build tool specified yet; uses the default setuptools)
- Dependencies: none yet

## Commands

```bash
# Run the project
python main.py
# or
uv run main.py          # if using uv

# Install dependencies (when added)
uv sync                 # if using uv
pip install -e .        # standard pip

# Run tests (when added)
pytest                  # root-level tests
pytest tests/           # all tests
pytest tests/test_foo.py -v  # single test file
```

## Project Structure

```
D:\结算对账中心\
├── main.py              # Entry point — currently prints "Hello from settlement-reconciliation!"
├── pyproject.toml       # Project metadata and dependencies
├── .python-version      # Python version pin (3.10)
├── README.md            # Project readme (empty)
└── CLAUDE.md            # This file
```

The project is in its initial state. Future development will add:
- Business logic for settlement reconciliation
- Test suite
- Configuration management
- Data processing pipelines

## Conventions

- Use `pyproject.toml` for all dependency and tool configuration (no `setup.py` or `setup.cfg` unless needed)
- Keep the entry point (`main.py`) thin — delegate logic to modules in a `src/` or package directory
- Pin Python version in `.python-version` for `pyenv`/`uv` consistency