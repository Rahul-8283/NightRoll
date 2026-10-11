# Infrastructure

Everything that runs the server side as one system: nginx (the dashboard, HTTPS and the proxy), the API, the scheduler and the face worker. Redis is hosted on Upstash and the database on Supabase, so neither has a container.

| File | What it is |
|---|---|
| `docker-compose.yml` | The four services, their health checks and their one shared network |
| `nginx/nightroll.conf` | HTTPS, the proxy to the API and the live socket, upload limits, security headers |
| `nginx/proxy-headers.conf` | The headers every proxied request gets, including the real client address |
| `certs/` | The server certificate (git-ignored). See `certs/README.md` |
| `.env.example` | The few values Compose itself needs. Copy to `.env` |

## Start

From the repo root, once the files below are filled in:

```bash
docker compose -f infra/docker-compose.yml up -d --build
docker compose -f infra/docker-compose.yml ps        # every service should say "healthy"
```

Needed first:

1. `backend/.env`, `face/.env`, `infra/.env`, each copied from its `.env.example`.
2. `backend/secrets/google-service-account.json`.
3. The face models in `face/models`, from `python scripts/download_models.py` in `face/`. They are mounted read-only and checked against their recorded checksums every time the face worker starts.
4. `infra/certs/nightroll.pem` and `nightroll-key.pem`, made as described in `certs/README.md`.

`APP_ENV` in `infra/.env` overrides the one in `backend/.env`. With `pilot` or `production` the API refuses to start with unsafe settings and says which. With `demo` it starts and prints a banner listing every relaxed setting.

## What is open

Only nginx publishes ports: 80 (redirects to HTTPS) and 443. The API and the face worker are reachable inside the Compose network only. nginx has the fixed address `172.28.0.10`, which is what `TRUSTED_PROXY_IPS` is set to, so the API believes the client address nginx reports and nobody else's.

Secrets never go in this folder or in an image. Use the service env files.
