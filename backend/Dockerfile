# NightRoll API and scheduler. One image, two commands (see infra/docker-compose.yml).
# Dependencies come from uv.lock exactly, so a rebuild never picks up a newer package.

FROM python:3.12-slim-bookworm AS build
RUN pip install --no-cache-dir uv==0.12.19
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

FROM python:3.12-slim-bookworm
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PATH="/app/.venv/bin:$PATH"
RUN groupadd --system --gid 10001 nightroll \
 && useradd --system --uid 10001 --gid nightroll --home-dir /app --shell /usr/sbin/nologin nightroll
WORKDIR /app
COPY --from=build --chown=nightroll:nightroll /app/.venv /app/.venv
COPY --chown=nightroll:nightroll app ./app
USER nightroll
EXPOSE 8000

# nginx is the only thing that talks to the API, so uvicorn must not rewrite the client address itself:
# app/services/verification/network.py decides when the forwarded-for header can be believed.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-proxy-headers", "--no-access-log"]
