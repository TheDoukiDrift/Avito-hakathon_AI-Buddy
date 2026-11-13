"""FastAPI application factory."""

from __future__ import annotations

import asyncio
import contextlib
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.db import dispose_engine, get_engine
from app.errors import AppError
from app.models import Base
from app.routers import (
    absences,
    audit,
    auth,
    chat,
    checklist,
    contacts,
    health,
    reminders,
)
from app.services.reminder_cron import cron_loop


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Idempotent: alembic owns the real schema in docker, this keeps `uvicorn app.main:app`
    # working on a fresh checkout without a migration step.
    async with get_engine().begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    # S3: the AI-cron imitation lives in the API process. It ticks once on start, then
    # every REMINDER_INTERVAL_SEC; a failing tick is logged and the loop survives.
    stop_event = asyncio.Event()
    cron = asyncio.create_task(cron_loop(stop_event), name="reminder-cron")
    try:
        yield
    finally:
        stop_event.set()
        with contextlib.suppress(asyncio.CancelledError):
            await cron
        await dispose_engine()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="AI-buddy backend",
        version="0.1.0",
        description="ИИ-наставник для стажёров: чат, чек-лист, отсутствия (имитации).",
        lifespan=lifespan,
    )

    origins = settings.cors_origin_list
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=origins != ["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    @app.get("/", include_in_schema=False)
    async def root() -> dict:
        return {"service": settings.app_name, "docs": "/docs", "health": "/api/health"}

    api_prefix = "/api"
    app.include_router(health.router, prefix=api_prefix)
    app.include_router(auth.router, prefix=api_prefix)
    app.include_router(chat.router, prefix=api_prefix)
    app.include_router(checklist.router, prefix=api_prefix)
    app.include_router(reminders.router, prefix=api_prefix)
    app.include_router(absences.router, prefix=api_prefix)
    app.include_router(contacts.router, prefix=api_prefix)
    app.include_router(audit.router, prefix=api_prefix)
    return app


app = create_app()
