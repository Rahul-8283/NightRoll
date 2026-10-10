# Infrastructure

Local and deployment configuration.

- `docker-compose.yml`: currently empty. Redis is hosted on Upstash, so no container is needed. Phase 12 adds `api`, `scheduler`, `face-worker` and `nginx`.
- Start the compose file from the repo root: `docker compose -f infra/docker-compose.yml up -d`.
- Phase 12 adds `nginx/` (reverse proxy and TLS) and the runbook.

Secrets never go in this folder. Use the `.env` files of each service.
