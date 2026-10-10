from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db import pool as db_pool
from app.errors import register_error_handlers
from app.logging import RequestLoggingMiddleware, configure_logging, log_event
from app.redis import client as redis_client
from app.routers import attendance, audit, enrollment, exports, health, live, reviews, rooms, students, windows

logger = logging.getLogger("nightroll.app")


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.LOG_LEVEL)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        # A dependency that is down at boot must not take the whole API down with it;
        # /v1/health has to stay reachable and report "degraded" instead of failing to start.
        try:
            await db_pool.connect(settings)
        except Exception:
            logger.exception("database pool failed to connect at startup")
        try:
            await redis_client.connect(settings)
        except Exception:
            logger.exception("redis client failed to connect at startup")
        log_event(
            logger,
            logging.INFO,
            "startup",
            app_env=settings.APP_ENV,
            settings_loaded=settings.safe_field_names(),
        )
        yield
        await redis_client.disconnect()
        await db_pool.disconnect()

    app = FastAPI(title="NightRoll API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(RequestLoggingMiddleware)
    origins = [o.strip() for o in settings.DASHBOARD_ORIGINS.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH"],
        allow_headers=["Authorization", "Content-Type"],
    )
    register_error_handlers(app)
    app.include_router(health.router)
    app.include_router(rooms.router)
    app.include_router(students.router)
    app.include_router(windows.router)
    app.include_router(attendance.router)
    app.include_router(live.router)
    app.include_router(reviews.router)
    app.include_router(exports.router)
    app.include_router(audit.router)
    app.include_router(enrollment.router)
    return app


app = create_app()
