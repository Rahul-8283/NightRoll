# Backend

FastAPI service: window management, nonces, the six hard gates, scoring and review. Built in Phases 2, 3, 8 and 9.

## Status

Phase 0 creates only the environment file. There is no code yet, so the run command below will not work until Phase 2 adds `app/main.py`.

## Requirements

- Python 3.12
- Redis running locally (see the main README)
- A filled-in `backend/.env`
- `backend/secrets/google-service-account.json` (git-ignored, from the team password manager)

## Setup

```bash
cd backend
cp .env.example .env                  # then fill in the values
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"               # Phase 2 adds pyproject.toml
```

## Run

```bash
uvicorn app.main:app --reload --port 8000     # API, from Phase 2
python -m app.scheduler                       # window scheduler, from Phase 3
```

Check: `curl http://localhost:8000/v1/health` (Phase 2).
