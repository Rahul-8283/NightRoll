# Face worker

Internal service that makes face embeddings and runs anti-spoof checks. It is not reachable from outside the host and has no access to attendance tables. Built in Phase 5.

## Status

Phase 5 implemented. Includes InsightFace buffalo_l embedding pipeline, anti-spoof scoring, frame quality checks, private Supabase Storage frame upload, 24-hour retention cleanup, and authenticated internal API.

## Requirements

- Python 3.12
- About 1 GB free for the models
- A filled-in `face/.env`

## Setup

```bash
cd face
cp .env.example .env                  # then fill in the values
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"               # Phase 5 adds pyproject.toml
python scripts/download_models.py     # Phase 5
```

## Run

```bash
uvicorn worker.main:app --port 8100   # from Phase 5
```

Check: `curl -H "Authorization: Bearer $FACE_WORKER_TOKEN" http://localhost:8100/health` (Phase 5).
