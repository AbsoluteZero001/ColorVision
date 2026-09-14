"""External API and mock upload service boundary."""

from __future__ import annotations

from pathlib import Path
from typing import Any


class UploadService:
    """Upload capture data without coupling routes to an HTTP client."""

    async def upload(
        self,
        original_image: Path,
        roi_image: Path,
        color_result: dict[str, Any],
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        raise NotImplementedError("Uploading is implemented in Phase 8")
