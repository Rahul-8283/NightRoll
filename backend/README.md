# Backend

FastAPI service: window management, nonces, the six hard gates, scoring and review. Built in Phases 2, 3, 8 and 9.

## Status

The project is set up with uv and has a FastAPI entry point (`app/main.py`) with a health route. Config, database, Redis and the warden routes arrive in Phase 2.

## Requirements

- uv (`brew install uv`); it installs Python 3.12 for you
- An Upstash Redis database. Put its `rediss://` URL in `backend/.env` as `REDIS_URL`.
- A filled-in `backend/.env`
- `backend/secrets/google-service-account.json` (git-ignored, from the team password manager)

## Setup

```bash
cd backend
cp .env.example .env                  # then fill in the values
uv sync                               # creates .venv and installs everything in uv.lock
```

uv reads the Python version from `.python-version` (3.12) and installs it if needed.

Add a dependency with `uv add <package>` and a dev-only tool with `uv add --dev <package>`. Commit `pyproject.toml` and `uv.lock` together.

## Run

```bash
uv run uvicorn app.main:app --reload --port 8000   # API
curl http://localhost:8000/v1/health               # expect {"status":"ok"}
```

From Phase 3, also run the window scheduler in its own terminal: `uv run python -m app.scheduler`.

## Lint

```bash
uv run ruff check .
uv run ruff format .
```
