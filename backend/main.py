"""FastAPI application entry point for ColorVision."""

from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from html import escape
from pathlib import Path
from typing import AsyncIterator

# Allow ``python backend/main.py`` in addition to ``python -m backend.main``.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from backend import __version__
from backend.api import camera, color, config, health, system, upload
from backend.models.common import ErrorCode, ErrorResponse
from backend.services.camera_service import get_camera_service
from backend.services.config_service import get_config_service
from backend.utils.errors import AppException
from backend.utils.logging_utils import setup_logging
from backend.utils.paths import (
    ensure_runtime_directories,
    get_frontend_dist_directory,
)

APP_NAME = "ColorVision"


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Initialize shared runtime resources without starting camera hardware."""
    setup_logging()

    import logging

    logger = logging.getLogger(__name__)
    logger.info("ColorVision backend starting")

    try:
        config_data = get_config_service().get_config()
        logger.info(
            "Configuration loaded (camera_id=%s, mock_mode=%s)",
            config_data.camera_id,
            config_data.mock_mode,
        )
    except AppException as exc:
        logger.warning("Configuration could not be loaded at startup: %s", exc.message)

    yield
    get_camera_service().close_camera()
    logger.info("ColorVision backend stopped")


app = FastAPI(
    title=APP_NAME,
    description="Local machine-vision color capture and recognition service.",
    version=__version__,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

captures_directory, results_directory, _ = ensure_runtime_directories()
app.mount(
    "/media/captures",
    StaticFiles(directory=captures_directory),
    name="capture-media",
)
app.mount(
    "/media/results",
    StaticFiles(directory=results_directory),
    name="result-media",
)


@app.exception_handler(AppException)
async def app_exception_handler(_: Request, exc: AppException) -> JSONResponse:
    payload = ErrorResponse(message=exc.message, code=exc.code)
    return JSONResponse(status_code=exc.status_code, content=payload.model_dump())


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    _: Request, exc: RequestValidationError
) -> JSONResponse:
    payload = ErrorResponse(
        message="Request validation failed",
        code=ErrorCode.INVALID_REQUEST,
    )
    return JSONResponse(
        status_code=422,
        content={**payload.model_dump(), "details": jsonable_encoder(exc.errors())},
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
    message = exc.detail if isinstance(exc.detail, str) else "HTTP request failed"
    payload = ErrorResponse(message=message, code=ErrorCode.HTTP_ERROR)
    return JSONResponse(status_code=exc.status_code, content=payload.model_dump())


@app.exception_handler(Exception)
async def unexpected_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    import logging

    logging.getLogger(__name__).exception("Unhandled backend error", exc_info=exc)
    payload = ErrorResponse(
        message="Internal server error",
        code=ErrorCode.INTERNAL_ERROR,
    )
    return JSONResponse(status_code=500, content=payload.model_dump())


api_prefix = "/api"
app.include_router(health.router, prefix=api_prefix)
app.include_router(system.router, prefix=api_prefix)
app.include_router(camera.router, prefix=api_prefix)
app.include_router(color.router, prefix=api_prefix)
app.include_router(upload.router, prefix=api_prefix)
app.include_router(config.router, prefix=api_prefix)

frontend_dist = get_frontend_dist_directory()
frontend_index = frontend_dist / "index.html"

frontend_assets = frontend_dist / "assets"
if frontend_assets.is_dir():
    app.mount(
        "/assets",
        StaticFiles(directory=frontend_assets),
        name="frontend-assets",
    )


def _frontend_response(full_path: str = "") -> Response:
    """Serve a Vue file or return a diagnostic HTML response when absent."""
    current_index = get_frontend_dist_directory() / "index.html"
    if not current_index.is_file():
        return HTMLResponse(
            status_code=503,
            content=(
                "<!doctype html><html lang=\"en\"><head>"
                "<meta charset=\"utf-8\"><title>ColorVision frontend unavailable</title>"
                "</head><body>"
                "<h1>ColorVision frontend is not available</h1>"
                "<p>The Vue production bundle was not found. Run "
                "<code>npm run build</code> in the frontend directory, then restart "
                "ColorVision.</p>"
                f"<p>Expected file: <code>{escape(str(current_index))}</code></p>"
                "</body></html>"
            ),
            headers={"Cache-Control": "no-store"},
        )

    resolved_root = current_index.parent.resolve()
    if not full_path:
        return FileResponse(current_index)

    candidate = (resolved_root / full_path).resolve()
    try:
        candidate.relative_to(resolved_root)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="File not found") from exc

    if candidate.is_file():
        return FileResponse(candidate)
    return FileResponse(current_index)


@app.get("/", include_in_schema=False)
async def serve_frontend() -> Response:
    """Serve the Vue application entry point."""
    return _frontend_response()


@app.get("/{full_path:path}", include_in_schema=False)
async def serve_frontend_fallback(
    full_path: str,
) -> Response:
    """Serve static frontend files and the Vue history fallback."""
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="API route not found")
    return _frontend_response(full_path)


def run() -> None:
    """Run the managed local service used by both Python and EXE launches."""
    from backend.launcher import main

    raise SystemExit(main())


if __name__ == "__main__":
    run()
