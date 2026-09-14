"""FastAPI application entry point for ColorVision."""

from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

# Allow ``python backend/main.py`` in addition to ``python -m backend.main``.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from backend import __version__
from backend.api import camera, color, config, health, upload
from backend.models.common import ApiResponse, ErrorCode, ErrorResponse
from backend.services.camera_service import get_camera_service
from backend.services.config_service import get_config_service
from backend.utils.errors import AppException
from backend.utils.logging_utils import setup_logging
from backend.utils.paths import get_data_directory

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

data_directory = get_data_directory()
captures_directory = data_directory / "captures"
results_directory = data_directory / "results"
captures_directory.mkdir(parents=True, exist_ok=True)
results_directory.mkdir(parents=True, exist_ok=True)
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


@app.get("/", response_model=ApiResponse[dict[str, str]], tags=["system"])
async def root() -> ApiResponse[dict[str, str]]:
    """Expose a small discovery response for local integrations."""
    return ApiResponse(
        data={
            "name": APP_NAME,
            "version": __version__,
            "docs": "/docs",
        }
    )


api_prefix = "/api"
app.include_router(health.router, prefix=api_prefix)
app.include_router(camera.router, prefix=api_prefix)
app.include_router(color.router, prefix=api_prefix)
app.include_router(upload.router, prefix=api_prefix)
app.include_router(config.router, prefix=api_prefix)


def run() -> None:
    """Run the local service for direct and future packaged execution."""
    uvicorn.run(
        "backend.main:app",
        host="127.0.0.1",
        port=8000,
        reload=False,
    )


if __name__ == "__main__":
    run()
