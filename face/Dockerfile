# NightRoll face worker. Internal only: nginx never proxies to it and Compose publishes no port for it.
# Dependencies come from uv.lock exactly. Model files are never in the image: mount face/models read-only
# at /app/models. On start, entrypoint.sh checks every model file against the SHA-256 list in
# scripts/download_models.py and refuses to run if one is missing or different.

FROM python:3.12-slim-bookworm AS build
# insightface compiles a small C extension when it is installed.
RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential \
 && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir uv==0.12.19
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

FROM python:3.12-slim-bookworm
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PATH="/app/.venv/bin:$PATH"
RUN apt-get update \
 && apt-get install -y --no-install-recommends libgomp1 libglib2.0-0 \
 && rm -rf /var/lib/apt/lists/* \
 && groupadd --system --gid 10001 nightroll \
 && useradd --system --uid 10001 --gid nightroll --home-dir /app --shell /usr/sbin/nologin nightroll
WORKDIR /app
COPY --from=build --chown=nightroll:nightroll /app/.venv /app/.venv
COPY --chown=nightroll:nightroll worker ./worker
COPY --chown=nightroll:nightroll scripts/download_models.py ./scripts/download_models.py
COPY --chown=nightroll:nightroll entrypoint.sh ./entrypoint.sh
RUN mkdir -p /app/models && chown nightroll:nightroll /app/models
USER nightroll
EXPOSE 8100
ENTRYPOINT ["./entrypoint.sh"]
CMD ["uvicorn", "worker.main:app", "--host", "0.0.0.0", "--port", "8100", "--no-access-log"]
