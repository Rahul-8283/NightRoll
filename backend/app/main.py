from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import get_settings
from app.db import pool as db_pool
from app.errors import register_error_handlers
from app.logging import RequestLoggingMiddleware, configure_logging, log_event
from app.redis import client as redis_client
from app.routers import health, rooms, students, windows

logger = logging.getLogger("nightroll.app")


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.LOG_LEVEL)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        await db_pool.connect(settings)
        await redis_client.connect(settings)
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
    register_error_handlers(app)
    app.include_router(health.router)
    app.include_router(rooms.router)
    app.include_router(students.router)
    app.include_router(windows.router)
    return app


app = create_app()
