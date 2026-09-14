"""External API and local mock upload service."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from typing import Any

import httpx

from backend.models.common import ErrorCode
from backend.models.config import AppConfig
from backend.models.upload import UploadResultData
from backend.services.config_service import get_config_service
from backend.utils.errors import AppException

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class UploadPayload:
    """Binary and metadata values forwarded to an upload target."""

    original_image: bytes
    original_filename: str
    original_content_type: str
    roi_image: bytes
    roi_filename: str
    roi_content_type: str
    rgb: dict[str, int]
    lab: dict[str, float]
    hex: str
    roi: dict[str, int]
    camera_id: str
    timestamp: str


class UploadService:
    """Upload capture data without coupling routes to an HTTP client."""

    def __init__(
        self,
        config_provider: Callable[[], AppConfig] | None = None,
    ) -> None:
        self._config_provider = config_provider or get_config_service().get_config
        self._mock_sequence = 0

    async def upload(
        self,
        payload: UploadPayload,
    ) -> UploadResultData:
        """Dispatch an upload through the configured mock or real API mode."""
        config_data = self._config_provider()
        mode = "mock" if config_data.mock_mode else "api"
        logger.info(
            "Upload started: mode=%s camera_id=%s",
            mode,
            payload.camera_id,
        )

        if config_data.mock_mode:
            return self._mock_upload(payload)
        return await self._api_upload(payload, config_data)

    def _mock_upload(self, payload: UploadPayload) -> UploadResultData:
        self._mock_sequence += 1
        date_code = datetime.now().strftime("%Y%m%d")
        request_id = f"MOCK-{date_code}-{self._mock_sequence:04d}"
        logger.info(
            "Mock upload success: request_id=%s original_bytes=%d roi_bytes=%d",
            request_id,
            len(payload.original_image),
            len(payload.roi_image),
        )
        return UploadResultData(
            success=True,
            message="Mock upload success",
            request_id=request_id,
            mode="mock",
            upstream_response={
                "camera_id": payload.camera_id,
                "hex": payload.hex,
                "roi": payload.roi,
            },
        )

    async def _api_upload(
        self,
        payload: UploadPayload,
        config_data: AppConfig,
    ) -> UploadResultData:
        headers = {"Accept": "application/json"}
        if config_data.token:
            headers["Authorization"] = f"Bearer {config_data.token}"

        data = {
            "rgb": json.dumps(payload.rgb, separators=(",", ":")),
            "lab": json.dumps(payload.lab, separators=(",", ":")),
            "hex": payload.hex,
            "roi": json.dumps(payload.roi, separators=(",", ":")),
            "camera_id": payload.camera_id,
            "timestamp": payload.timestamp,
        }
        files = {
            "original_image": (
                payload.original_filename,
                payload.original_image,
                payload.original_content_type,
            ),
            "roi_image": (
                payload.roi_filename,
                payload.roi_image,
                payload.roi_content_type,
            ),
        }

        timeout = httpx.Timeout(config_data.timeout)
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    config_data.api_url,
                    data=data,
                    files=files,
                    headers=headers,
                )
            if response.is_error:
                logger.error(
                    "External API returned HTTP %d: %s",
                    response.status_code,
                    response.text[:500],
                )
                raise AppException(
                    message=f"External API returned HTTP {response.status_code}",
                    code=ErrorCode.API_REQUEST_FAILED,
                    status_code=502,
                )
        except httpx.TimeoutException as exc:
            logger.error("External API request timed out: %s", config_data.api_url)
            raise AppException(
                message="External API request timed out",
                code=ErrorCode.API_TIMEOUT,
                status_code=504,
            ) from exc
        except httpx.RequestError as exc:
            logger.error("External API request failed: %s", exc)
            raise AppException(
                message="External API request failed",
                code=ErrorCode.API_REQUEST_FAILED,
                status_code=502,
            ) from exc

        response_data = self._parse_response(response)
        if response_data.get("success") is False:
            raise AppException(
                message=str(response_data.get("message", "External API rejected upload")),
                code=ErrorCode.API_REQUEST_FAILED,
                status_code=502,
            )

        request_id = str(
            response.headers.get("X-Request-ID")
            or response_data.get("request_id")
            or f"API-{datetime.now():%Y%m%d%H%M%S}"
        )
        logger.info(
            "External API upload success: request_id=%s status=%d",
            request_id,
            response.status_code,
        )
        return UploadResultData(
            success=True,
            message=str(response_data.get("message", "Upload success")),
            request_id=request_id,
            mode="api",
            target_url=config_data.api_url,
            upstream_status_code=response.status_code,
            upstream_response=response_data,
        )

    @staticmethod
    def _parse_response(response: httpx.Response) -> dict[str, Any]:
        try:
            parsed = response.json()
        except ValueError as exc:
            logger.error("External API returned invalid JSON")
            raise AppException(
                message="External API returned an invalid JSON response",
                code=ErrorCode.API_REQUEST_FAILED,
                status_code=502,
            ) from exc

        if not isinstance(parsed, dict):
            raise AppException(
                message="External API JSON response must be an object",
                code=ErrorCode.API_REQUEST_FAILED,
                status_code=502,
            )
        return parsed


@lru_cache(maxsize=1)
def get_upload_service() -> UploadService:
    """Return the process-wide upload service."""
    return UploadService()
