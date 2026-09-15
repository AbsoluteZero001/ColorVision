"""Image decoding, persistence, cropping, and media URL helpers."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from threading import Lock
from uuid import uuid4

import cv2
import numpy as np
import numpy.typing as npt

from backend.models.common import ErrorCode
from backend.models.config import AppConfig
from backend.services.config_service import get_config_service
from backend.utils.errors import AppException
from backend.utils.paths import get_data_directory, get_project_root

logger = logging.getLogger(__name__)

MEDIA_ROOT = get_data_directory()
CAPTURES_DIRECTORY = MEDIA_ROOT / "captures"
RESULTS_DIRECTORY = MEDIA_ROOT / "results"
CAPTURE_FILE_SUFFIXES = {".jpg", ".jpeg", ".png"}


class ImageService:
    """Own image I/O and ROI cropping independently of HTTP and algorithms."""

    def __init__(
        self,
        captures_directory: Path | None = None,
        results_directory: Path | None = None,
        config_provider: Callable[[], AppConfig] | None = None,
    ) -> None:
        self._captures_directory = captures_directory or CAPTURES_DIRECTORY
        self._results_directory = results_directory or RESULTS_DIRECTORY
        self._config_provider = config_provider or get_config_service().get_config
        self._retention_lock = Lock()

    def save_capture(self, frame: npt.NDArray[np.uint8]) -> Path:
        """Persist a BGR frame as a timestamped JPEG capture."""
        self._validate_frame(frame, "captured frame")
        now = datetime.now().astimezone()
        filename = (
            f"capture_{now:%Y%m%d_%H%M%S_%f}"
            f"_{uuid4().hex[:8]}.jpg"
        )
        destination = self._captures_directory / filename
        self.save_jpeg(destination, frame)
        logger.info("Capture saved: %s", destination)
        self.enforce_retention()
        return destination

    def enforce_retention(self) -> int:
        """Delete old captures according to the configured retention policy.

        Zero values disable the corresponding policy. Cleanup failures are
        logged without rejecting the capture that triggered the check.
        """
        try:
            config_data = self._config_provider()
        except Exception:
            logger.warning("Image retention configuration could not be read")
            return 0

        with self._retention_lock:
            files = self._capture_files_by_age()
            if not files:
                return 0

            deleted = 0
            remaining: list[Path] = []
            cutoff = (
                time.time() - config_data.image_retention_days * 86400
                if config_data.image_retention_days > 0
                else None
            )

            for path in files:
                try:
                    is_expired = cutoff is not None and path.stat().st_mtime < cutoff
                except OSError:
                    logger.warning("Capture metadata could not be read: %s", path)
                    remaining.append(path)
                    continue

                if is_expired:
                    if self._delete_capture(path):
                        deleted += 1
                else:
                    remaining.append(path)

            if config_data.max_image_count > 0:
                excess_count = max(0, len(remaining) - config_data.max_image_count)
                for path in remaining[:excess_count]:
                    if self._delete_capture(path):
                        deleted += 1

            if deleted:
                logger.info("Capture retention removed %d file(s)", deleted)
            return deleted

    def read_image(self, path: Path) -> npt.NDArray[np.uint8]:
        """Read an image from disk as an OpenCV BGR array."""
        try:
            image = cv2.imread(str(path), cv2.IMREAD_COLOR)
        except cv2.error as exc:
            logger.exception("OpenCV failed to read image: %s", path)
            raise AppException(
                message="Image could not be read",
                code=ErrorCode.IMAGE_READ_FAILED,
                status_code=422,
            ) from exc

        if image is None or image.size == 0:
            raise AppException(
                message="Image file is empty or unsupported",
                code=ErrorCode.IMAGE_READ_FAILED,
                status_code=422,
            )
        return image

    def decode_image(self, content: bytes) -> npt.NDArray[np.uint8]:
        """Decode uploaded image bytes as an OpenCV BGR array."""
        if not content:
            raise AppException(
                message="Uploaded image is empty",
                code=ErrorCode.IMAGE_READ_FAILED,
                status_code=422,
            )

        try:
            encoded = np.frombuffer(content, dtype=np.uint8)
            image = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
        except (ValueError, cv2.error) as exc:
            logger.exception("Uploaded image could not be decoded")
            raise AppException(
                message="Uploaded image could not be decoded",
                code=ErrorCode.IMAGE_READ_FAILED,
                status_code=422,
            ) from exc

        if image is None or image.size == 0:
            raise AppException(
                message="Uploaded image format is unsupported",
                code=ErrorCode.IMAGE_READ_FAILED,
                status_code=422,
            )
        return image

    def save_jpeg(
        self,
        path: Path,
        image: npt.NDArray[np.uint8],
        quality: int = 92,
    ) -> None:
        """Encode an image without relying on Unicode-sensitive cv2.imwrite."""
        self._validate_frame(image, "image")
        encode_options = [cv2.IMWRITE_JPEG_QUALITY, max(1, min(quality, 100))]
        try:
            ok, encoded = cv2.imencode(".jpg", image, encode_options)
            if not ok:
                raise ValueError("OpenCV returned an unsuccessful encode result")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(encoded.tobytes())
        except (OSError, ValueError, cv2.error) as exc:
            logger.exception("JPEG could not be saved: %s", path)
            raise AppException(
                message="Image could not be saved",
                code=ErrorCode.CAPTURE_FAILED,
                status_code=500,
            ) from exc

    def crop_roi(
        self,
        image: npt.NDArray[np.uint8],
        x: int,
        y: int,
        width: int,
        height: int,
    ) -> npt.NDArray[np.uint8]:
        """Validate and crop an ROI using original-image coordinates."""
        self._validate_roi(image, x, y, width, height)
        return image[y : y + height, x : x + width].copy()

    @staticmethod
    def build_media_url(path: Path) -> str:
        """Map a runtime file below data/ to its public media URL."""
        try:
            relative_path = path.resolve().relative_to(MEDIA_ROOT.resolve())
        except ValueError as exc:
            raise AppException(
                message="Image is outside the configured media directory",
                code=ErrorCode.IMAGE_READ_FAILED,
                status_code=500,
            ) from exc
        return f"/media/{relative_path.as_posix()}"

    @staticmethod
    def build_project_path(path: Path) -> str:
        """Return a portable project-relative path for API metadata."""
        try:
            relative_path = path.resolve().relative_to(get_project_root().resolve())
        except ValueError:
            return path.name
        return relative_path.as_posix()

    @staticmethod
    def _validate_frame(
        image: npt.NDArray[np.uint8],
        label: str,
    ) -> None:
        if image is None or image.size == 0 or image.ndim not in (2, 3):
            raise AppException(
                message=f"The {label} is empty or invalid",
                code=ErrorCode.IMAGE_READ_FAILED,
                status_code=422,
            )

    @staticmethod
    def _validate_roi(
        image: npt.NDArray[np.uint8],
        x: int,
        y: int,
        width: int,
        height: int,
    ) -> None:
        if image is None or image.size == 0:
            raise AppException(
                message="The source image is empty or invalid",
                code=ErrorCode.IMAGE_READ_FAILED,
                status_code=422,
            )
        image_height, image_width = image.shape[:2]
        if width <= 0 or height <= 0:
            raise AppException(
                message="ROI width and height must be greater than zero",
                code=ErrorCode.INVALID_ROI,
                status_code=400,
            )
        if x < 0 or y < 0 or x + width > image_width or y + height > image_height:
            raise AppException(
                message=(
                    f"ROI is outside the image bounds "
                    f"({image_width}x{image_height})"
                ),
                code=ErrorCode.INVALID_ROI,
                status_code=400,
            )

    def _capture_files_by_age(self) -> list[Path]:
        if not self._captures_directory.is_dir():
            return []

        files = [
            path
            for path in self._captures_directory.iterdir()
            if path.is_file() and path.suffix.lower() in CAPTURE_FILE_SUFFIXES
        ]
        return sorted(files, key=self._capture_sort_key)

    @staticmethod
    def _capture_sort_key(path: Path) -> tuple[float, str]:
        try:
            modified_at = path.stat().st_mtime
        except OSError:
            modified_at = 0.0
        return modified_at, path.name

    @staticmethod
    def _delete_capture(path: Path) -> bool:
        try:
            path.unlink()
            logger.info("Capture retention deleted: %s", path)
            return True
        except OSError:
            logger.warning("Capture could not be deleted: %s", path)
            return False


@lru_cache(maxsize=1)
def get_image_service() -> ImageService:
    """Return the process-wide image service."""
    return ImageService()
