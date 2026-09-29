"""Сборка приложения FastAPI."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api import errors, guest_routes, staff_routes
from app.clock import OffsetClock, SystemClock
from app.config import Settings, load_settings
from app.db.database import Database
from app.db.seed import ensure_demo
from app.services.context import Context

STATIC = Path(__file__).parent / "static"

CSP = ("default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; "
       "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")


def create_app(settings: Settings | None = None, clock=None) -> FastAPI:
    settings = settings or load_settings()
    if clock is None:
        clock = OffsetClock(settings.start_now) if settings.start_now else SystemClock()
    db = Database(settings.db_path)
    ensure_demo(db)

    app = FastAPI(title="Skuratov Coffee — учебный предзаказ", version="0.1.0")
    app.state.settings = settings
    app.state.ctx = Context(db=db, clock=clock, profile=settings.profile)

    errors.install(app)
    app.include_router(guest_routes.router)
    app.include_router(staff_routes.public)
    app.include_router(staff_routes.router)

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        if not request.url.path.startswith(("/docs", "/redoc", "/openapi")):
            response.headers["Content-Security-Policy"] = CSP
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/", include_in_schema=False)
    def guest_page():
        return FileResponse(STATIC / "index.html")

    @app.get("/staff", include_in_schema=False)
    def staff_page():
        return FileResponse(STATIC / "staff.html")

    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    return app
