"""
Oilora Blue AI — FastAPI Application

Main application entry point for the backend API server.
"""

import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import settings
from .database import close_database, init_database
from .routers import cases, files, health, historical, sources
from .routers import map as map_routes

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("oilora_blue")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown."""
    # Startup
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    init_database()
    logger.info(f"Database initialized: {settings.DATABASE_PATH}")
    logger.info(f"Data directory: {settings.DATA_DIR}")
    logger.info(f"Local Demo Mode: {settings.ENABLE_LOCAL_DEMO_MODE}")
    yield
    # Shutdown
    close_database()
    logger.info("Application shut down")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=settings.APP_DESCRIPTION,
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# ─── CORS ──────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Request context & security headers middleware ──────────────────
@app.middleware("http")
async def add_request_context(request: Request, call_next):
    """
    Attach a request ID to every request/response and add security headers.

    The request ID is generated server-side (or propagated from an inbound
    X-Request-ID header) and is included on every response so the frontend can
    surface it for error correlation. It is also used in internal error logs.
    """
    request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Permissions-Policy"] = (
        "geolocation=(), camera=(), microphone=(), usb=(), "
        "magnetometer=(), gyroscope=(), payment=()"
    )
    return response


# ─── Request timing middleware ────────────────────────────────────────
@app.middleware("http")
async def add_timing_header(request: Request, call_next):
    start = time.monotonic()
    response = await call_next(request)
    elapsed = time.monotonic() - start
    response.headers["X-Process-Time"] = f"{elapsed:.4f}"
    return response


# ─── Global error handler ─────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", None) or "unknown"
    logger.exception(
        "Unhandled error: request_id=%s path=%s error=%s",
        request_id,
        request.url.path,
        exc,
    )
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "message": "Internal server error",
            "error_code": "INTERNAL_ERROR",
            "request_id": request_id,
        },
    )


# ─── Register routers ─────────────────────────────────────────────────
app.include_router(health.router)
app.include_router(cases.router)
app.include_router(files.router)
app.include_router(map_routes.router)
app.include_router(sources.router)
app.include_router(historical.router)


# ─── Root endpoint ─────────────────────────────────────────────────────
@app.get("/")
async def root():
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "description": settings.APP_DESCRIPTION,
        "docs": "/api/docs",
        "health": "/api/health",
    }


if __name__ == "__main__":
    import uvicorn

    # reload=False keeps the script runnable without the optional watchfiles
    # dependency; use `uvicorn app.main:app --reload` for live reload in dev.
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=False)
