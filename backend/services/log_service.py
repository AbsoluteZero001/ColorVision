"""SQLite-backed upload logs with local image retention."""

from __future__ import annotations

import logging
import sqlite3
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from threading import Lock
from uuid import uuid4

from backend.models.common import ErrorCode
from backend.models.config import AppConfig
from backend.models.log import UploadLogData, UploadLogPage
from backend.models.upload import UploadResultData
from backend.services.config_service import get_config_service
from backend.services.upload_service import UploadPayload
from backend.utils.errors import AppException
from backend.utils.paths import get_logs_directory

logger = logging.getLogger(__name__)

BEIJING_TIMEZONE = timezone(timedelta(hours=8))
IMAGE_EXTENSIONS = {
    "image/bmp": ".bmp",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
SAFE_IMAGE_SUFFIXES = {".bmp", ".jpg", ".jpeg", ".png", ".webp"}


class LogService:
    """Persist upload metadata in SQLite and associated images on local disk."""

    def __init__(
        self,
        logs_directory: Path | None = None,
        config_provider: Callable[[], AppConfig] | None = None,
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self._logs_directory = logs_directory or get_logs_directory()
        self._data_directory = self._logs_directory.parent
        self._images_directory = self._logs_directory / "images"
        self._database_path = self._logs_directory / "colorvision.db"
        self._config_provider = config_provider or get_config_service().get_config
        self._now_provider = now_provider or (
            lambda: datetime.now(BEIJING_TIMEZONE)
        )
        self._lock = Lock()
        self._initialized = False

    @property
    def database_path(self) -> Path:
        """Return the local SQLite database path."""
        return self._database_path

    @property
    def images_directory(self) -> Path:
        """Return the directory used for upload-log images."""
        return self._images_directory

    def initialize(self) -> None:
        """Create the database and empty schema without inserting seed data."""
        with self._lock:
            if self._initialized:
                return
            try:
                self._images_directory.mkdir(parents=True, exist_ok=True)
                with self._connect() as connection:
                    connection.execute("PRAGMA journal_mode=WAL")
                    connection.execute(
                        """
                        CREATE TABLE IF NOT EXISTS upload_logs (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            uploaded_at TEXT NOT NULL,
                            captured_at TEXT NOT NULL,
                            camera_id TEXT NOT NULL,
                            rgb_r INTEGER NOT NULL,
                            rgb_g INTEGER NOT NULL,
                            rgb_b INTEGER NOT NULL,
                            lab_l REAL NOT NULL,
                            lab_a REAL NOT NULL,
                            lab_b REAL NOT NULL,
                            hex TEXT NOT NULL,
                            roi_x INTEGER NOT NULL,
                            roi_y INTEGER NOT NULL,
                            roi_width INTEGER NOT NULL,
                            roi_height INTEGER NOT NULL,
                            upload_mode TEXT NOT NULL
                                CHECK (upload_mode IN ('mock', 'api')),
                            request_id TEXT NOT NULL,
                            message TEXT NOT NULL,
                            original_image_path TEXT,
                            roi_image_path TEXT
                        )
                        """
                    )
                    connection.execute(
                        """
                        CREATE INDEX IF NOT EXISTS idx_upload_logs_uploaded_at
                        ON upload_logs(uploaded_at DESC)
                        """
                    )
                    connection.commit()
                self._initialized = True
                logger.info("Upload log database initialized: %s", self._database_path)
            except (OSError, sqlite3.Error) as exc:
                logger.exception("Upload log database could not be initialized")
                raise AppException(
                    message="Upload log storage could not be initialized",
                    code=ErrorCode.LOG_WRITE_FAILED,
                    status_code=500,
                ) from exc

    def record_upload(
        self,
        payload: UploadPayload,
        result: UploadResultData,
    ) -> UploadLogData | None:
        """Record a successful upload when local logging is enabled."""
        self._initialize_if_needed()
        config_data = self._config_provider()
        if not config_data.log_enabled:
            return None

        now = self._beijing_now()
        original_relative: str | None = None
        roi_relative: str | None = None
        written_paths: list[Path] = []
        try:
            with self._lock:
                if config_data.log_image_storage_enabled:
                    original_path = self._new_image_path(
                        payload.original_filename,
                        payload.original_content_type,
                        "original",
                    )
                    roi_path = self._new_image_path(
                        payload.roi_filename,
                        payload.roi_content_type,
                        "roi",
                    )
                    self._write_image(original_path, payload.original_image)
                    written_paths.append(original_path)
                    self._write_image(roi_path, payload.roi_image)
                    written_paths.append(roi_path)
                    original_relative = self._relative_image_path(original_path)
                    roi_relative = self._relative_image_path(roi_path)

                with self._connect() as connection:
                    cursor = connection.execute(
                        """
                        INSERT INTO upload_logs (
                            uploaded_at,
                            captured_at,
                            camera_id,
                            rgb_r,
                            rgb_g,
                            rgb_b,
                            lab_l,
                            lab_a,
                            lab_b,
                            hex,
                            roi_x,
                            roi_y,
                            roi_width,
                            roi_height,
                            upload_mode,
                            request_id,
                            message,
                            original_image_path,
                            roi_image_path
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            now.isoformat(timespec="seconds"),
                            payload.timestamp,
                            payload.camera_id,
                            payload.rgb["r"],
                            payload.rgb["g"],
                            payload.rgb["b"],
                            payload.lab["l"],
                            payload.lab["a"],
                            payload.lab["b"],
                            payload.hex,
                            payload.roi["x"],
                            payload.roi["y"],
                            payload.roi["width"],
                            payload.roi["height"],
                            result.mode,
                            result.request_id,
                            result.message,
                            original_relative,
                            roi_relative,
                        ),
                    )
                    log_id = int(cursor.lastrowid)
                    connection.commit()
        except (
            KeyError,
            OSError,
            TypeError,
            ValueError,
            sqlite3.Error,
        ) as exc:
            self._delete_paths(written_paths)
            logger.exception("Upload log could not be saved")
            raise AppException(
                message="Upload log could not be saved",
                code=ErrorCode.LOG_WRITE_FAILED,
                status_code=500,
            ) from exc

        self._enforce_retention(config_data, now)
        return UploadLogData(
            id=log_id,
            uploaded_at=now.isoformat(timespec="seconds"),
            uploaded_at_beijing=now.strftime("%Y-%m-%d %H:%M:%S"),
            captured_at=payload.timestamp,
            camera_id=payload.camera_id,
            rgb=payload.rgb,
            lab=payload.lab,
            hex=payload.hex,
            roi=payload.roi,
            upload_mode=result.mode,
            request_id=result.request_id,
            message=result.message,
            original_image_url=self._image_url(original_relative),
            roi_image_url=self._image_url(roi_relative),
        )

    def list_entries(self, limit: int = 20, offset: int = 0) -> UploadLogPage:
        """Return newest upload logs first."""
        self._initialize_if_needed()
        try:
            with self._connect() as connection:
                total = int(
                    connection.execute(
                        "SELECT COUNT(*) FROM upload_logs"
                    ).fetchone()[0]
                )
                rows = connection.execute(
                    """
                    SELECT *
                    FROM upload_logs
                    ORDER BY id DESC
                    LIMIT ? OFFSET ?
                    """,
                    (limit, offset),
                ).fetchall()
        except sqlite3.Error as exc:
            logger.exception("Upload logs could not be read")
            raise AppException(
                message="Upload logs could not be read",
                code=ErrorCode.LOG_READ_FAILED,
                status_code=500,
            ) from exc

        return UploadLogPage(
            items=[self._row_to_data(row) for row in rows],
            total=total,
            limit=limit,
            offset=offset,
        )

    def enforce_retention(self) -> int:
        """Apply the configured log retention policy immediately."""
        self._initialize_if_needed()
        config_data = self._config_provider()
        return self._enforce_retention(config_data, self._beijing_now())

    def delete_entry(self, log_id: int) -> int:
        """Delete one upload log and its local image files."""
        self._initialize_if_needed()
        with self._lock:
            try:
                with self._connect() as connection:
                    row = connection.execute(
                        """
                        SELECT original_image_path, roi_image_path
                        FROM upload_logs
                        WHERE id = ?
                        """,
                        (log_id,),
                    ).fetchone()
                    if row is None:
                        raise AppException(
                            message="Upload log was not found",
                            code=ErrorCode.LOG_NOT_FOUND,
                            status_code=404,
                        )
                    cursor = connection.execute(
                        "DELETE FROM upload_logs WHERE id = ?",
                        (log_id,),
                    )
                    connection.commit()
            except sqlite3.Error as exc:
                logger.exception("Upload log could not be deleted: id=%s", log_id)
                raise AppException(
                    message="Upload log could not be deleted",
                    code=ErrorCode.LOG_WRITE_FAILED,
                    status_code=500,
                ) from exc

            self._delete_relative_images(
                row["original_image_path"],
                row["roi_image_path"],
            )
            return int(cursor.rowcount)

    def clear_entries(self) -> int:
        """Delete every upload log and all managed log images."""
        self._initialize_if_needed()
        with self._lock:
            try:
                with self._connect() as connection:
                    deleted = int(
                        connection.execute(
                            "SELECT COUNT(*) FROM upload_logs"
                        ).fetchone()[0]
                    )
                    connection.execute("DELETE FROM upload_logs")
                    connection.commit()
            except sqlite3.Error as exc:
                logger.exception("Upload logs could not be cleared")
                raise AppException(
                    message="Upload logs could not be cleared",
                    code=ErrorCode.LOG_WRITE_FAILED,
                    status_code=500,
                ) from exc

            self._clear_image_directory()
            return deleted

    def _initialize_if_needed(self) -> None:
        if not self._initialized:
            self.initialize()

    def _enforce_retention(
        self,
        config_data: AppConfig,
        now: datetime,
    ) -> int:
        if config_data.log_retention_days <= 0 and config_data.max_log_count <= 0:
            return 0

        ids: set[int] = set()
        try:
            with self._lock:
                with self._connect() as connection:
                    if config_data.log_retention_days > 0:
                        cutoff = (
                            now - timedelta(days=config_data.log_retention_days)
                        ).isoformat(timespec="seconds")
                        expired_rows = connection.execute(
                            """
                            SELECT id
                            FROM upload_logs
                            WHERE uploaded_at < ?
                            """,
                            (cutoff,),
                        ).fetchall()
                        ids.update(int(row["id"]) for row in expired_rows)

                    if config_data.max_log_count > 0:
                        excess_rows = connection.execute(
                            """
                            SELECT id
                            FROM upload_logs
                            ORDER BY id DESC
                            LIMIT -1 OFFSET ?
                            """,
                            (config_data.max_log_count,),
                        ).fetchall()
                        ids.update(int(row["id"]) for row in excess_rows)

                    image_paths: list[str] = []
                    for log_id in ids:
                        row = connection.execute(
                            """
                            SELECT original_image_path, roi_image_path
                            FROM upload_logs
                            WHERE id = ?
                            """,
                            (log_id,),
                        ).fetchone()
                        if row is not None:
                            image_paths.extend(
                                path
                                for path in (
                                    row["original_image_path"],
                                    row["roi_image_path"],
                                )
                                if path
                            )
                        connection.execute(
                            "DELETE FROM upload_logs WHERE id = ?",
                            (log_id,),
                        )
                    connection.commit()
        except sqlite3.Error:
            logger.exception("Upload log retention failed")
            return 0

        for image_path in image_paths:
            self._delete_relative_image(image_path)
        if ids:
            logger.info("Upload log retention removed %d entries", len(ids))
        return len(ids)

    def _row_to_data(self, row: sqlite3.Row) -> UploadLogData:
        uploaded_at = str(row["uploaded_at"])
        return UploadLogData(
            id=int(row["id"]),
            uploaded_at=uploaded_at,
            uploaded_at_beijing=self._format_beijing_time(uploaded_at),
            captured_at=str(row["captured_at"]),
            camera_id=str(row["camera_id"]),
            rgb={
                "r": int(row["rgb_r"]),
                "g": int(row["rgb_g"]),
                "b": int(row["rgb_b"]),
            },
            lab={
                "l": float(row["lab_l"]),
                "a": float(row["lab_a"]),
                "b": float(row["lab_b"]),
            },
            hex=str(row["hex"]),
            roi={
                "x": int(row["roi_x"]),
                "y": int(row["roi_y"]),
                "width": int(row["roi_width"]),
                "height": int(row["roi_height"]),
            },
            upload_mode=str(row["upload_mode"]),
            request_id=str(row["request_id"]),
            message=str(row["message"]),
            original_image_url=self._image_url(row["original_image_path"]),
            roi_image_url=self._image_url(row["roi_image_path"]),
        )

    def _new_image_path(
        self,
        filename: str,
        content_type: str,
        label: str,
    ) -> Path:
        suffix = Path(filename).suffix.lower()
        if suffix not in SAFE_IMAGE_SUFFIXES:
            suffix = IMAGE_EXTENSIONS.get(content_type.lower(), ".jpg")
        if suffix == ".jpeg":
            suffix = ".jpg"
        return self._images_directory / f"{uuid4().hex}_{label}{suffix}"

    @staticmethod
    def _write_image(path: Path, content: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    def _relative_image_path(self, path: Path) -> str:
        return path.resolve().relative_to(self._data_directory.resolve()).as_posix()

    def _image_url(self, relative_path: str | None) -> str | None:
        path = self._resolve_image(relative_path)
        if path is None or not path.is_file():
            return None
        normalized_relative = path.relative_to(
            self._data_directory.resolve()
        ).as_posix()
        return f"/media/{normalized_relative}"

    def _resolve_image(self, relative_path: str | None) -> Path | None:
        if not relative_path:
            return None
        try:
            candidate = (self._data_directory / relative_path).resolve()
            candidate.relative_to(self._images_directory.resolve())
        except (OSError, ValueError):
            logger.warning("Upload log image path is outside managed storage")
            return None
        return candidate

    def _delete_relative_images(self, *relative_paths: str | None) -> None:
        for relative_path in relative_paths:
            self._delete_relative_image(relative_path)

    def _delete_relative_image(self, relative_path: str | None) -> None:
        path = self._resolve_image(relative_path)
        if path is not None:
            self._delete_paths([path])

    def _clear_image_directory(self) -> None:
        try:
            paths = [
                path
                for path in self._images_directory.iterdir()
                if path.is_file() or path.is_symlink()
            ]
        except OSError:
            logger.warning("Upload log image directory could not be listed")
            return
        self._delete_paths(paths)

    @staticmethod
    def _delete_paths(paths: list[Path]) -> None:
        for path in paths:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                logger.warning("Upload log image could not be deleted: %s", path)

    def _beijing_now(self) -> datetime:
        value = self._now_provider()
        if value.tzinfo is None:
            return value.replace(tzinfo=BEIJING_TIMEZONE)
        return value.astimezone(BEIJING_TIMEZONE)

    @staticmethod
    def _format_beijing_time(value: str) -> str:
        try:
            parsed = datetime.fromisoformat(value)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=BEIJING_TIMEZONE)
            return parsed.astimezone(BEIJING_TIMEZONE).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        except ValueError:
            return value

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self._database_path, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout=5000")
        try:
            yield connection
        finally:
            connection.close()


@lru_cache(maxsize=1)
def get_log_service() -> LogService:
    """Return the process-wide upload log service."""
    return LogService()
