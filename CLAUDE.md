# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**结算对账中心 (Settlement Reconciliation Center)** — a web-based settlement reconciliation platform. Our-side receipt records (新方舟系统, standardized 98-column format) are matched against customer-side settlement records (varying formats per customer) via plugin-based matching engines.

- **GitHub**: https://github.com/xymdcyy/settlement-reconciliation
- **Python 3.10+** (see `.python-version`)
- **Package name**: `settlement-reconciliation`
- **Dependencies**: pandas, openpyxl, python-dateutil, xlrd, fastapi, uvicorn, sqlalchemy, pydantic
- **Issue tracker**: Local markdown at `.scratch/<feature-slug>/`

## Commands

```bash
# Run the project
python main.py
# or
uv run main.py

# Install dependencies
uv sync

# Run tests
pytest
pytest tests/ -v
pytest tests/engines/test_tmall_engine.py -v

# Run the FastAPI dev server
uvicorn app.main:app --reload

# Run reconciliation (migrated from script)
python -m app.engines.tmall.engine --year 2026 --month 5
```

## Project Structure

```
D:\结算对账中心\
├── main.py              # Entry point
├── pyproject.toml       # Project metadata and dependencies
├── .python-version      # Python version pin (3.10)
├── CLAUDE.md            # This file
├── docs/
│   ├── design.md        # 结算对账平台设计方案
│   ├── spec-phase1.md   # Phase 1 MVP Spec
│   ├── adr/             # Architecture Decision Records (to be created)
│   └── agents/          # Agent skill configuration
│       ├── issue-tracker.md
│       ├── triage-labels.md
│       └── domain.md
├── .scratch/            # Local issue tracker
│   └── phase1-mvp/
│       └── spec.md      # Phase 1 MVP spec
└── app/                 # Backend application (to be built)
    ├── main.py
    ├── routers/
    ├── models/
    ├── schemas/
    ├── services/
    ├── engines/
    └── utils/
```

The project is actively under development. Phase 1 MVP focuses on migrating the **天猫优品经销** reconciliation workflow to a web platform.

## Conventions

- Use `pyproject.toml` for all dependency and tool configuration (no `setup.py` or `setup.cfg` unless needed)
- Keep the entry point (`app/main.py`) thin — delegate logic to modules
- Pin Python version in `.python-version` for `pyenv`/`uv` consistency
- Chinese is the project language: all variable names, comments, output, and UI text are in Chinese
- Column names in Excel files are authoritative — do not rename source columns
- Each customer's matching engine is an independent plugin under `app/engines/` — do not modify other customers' engines

## Key Documents

| Document | Location | Purpose |
|----------|----------|---------|
| Design doc | `docs/design.md` | Overall architecture, data model, engine interface |
| Phase 1 spec | `docs/spec-phase1.md` / `.scratch/phase1-mvp/spec.md` | MVP scope, testing decisions, user stories |
| CLAUDE.md | This file | Project guide for Claude Code |

## Agent skills

### Issue tracker

Issues live as local markdown files under `.scratch/<feature-slug>/`. See `docs/agents/issue-tracker.md`.

### Triage labels

Five canonical roles mapped to their label strings. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context layout — root `CONTEXT.md` + `docs/adr/`. See `docs/agents/domain.md`.