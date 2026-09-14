"""Camera discovery, lifecycle, and unified real/mock frame sources."""

from __future__ import annotations

import logging
import os
import platform
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol

import cv2
import numpy as np
import numpy.typing as npt

from backend.models.camera import (
    CameraInfo,
    CameraSourceType,
    CameraState,
    CameraStatusData,
)
from backend.models.common import ErrorCode
from backend.utils.errors import AppException

logger = logging.getLogger(__name__)

DEFAULT_SCAN_LIMIT = 5
DEFAULT_WIDTH = 1280
DEFAULT_HEIGHT = 720
FRAME_READ_ATTEMPTS = 4
MOCK_WIDTH = 960
MOCK_HEIGHT = 540
MOCK_FPS = 15.0

FrameArray = npt.NDArray[np.uint8]


class CameraSourceError(RuntimeError):
    """Base error raised by a frame source."""


class CameraOpenError(CameraSourceError):
    """A frame source could not open its selected device."""

    def __init__(self, message: str, *, busy: bool = False) -> None:
        super().__init__(message)
        self.busy = busy


class CameraReadError(CameraSourceError):
    """A frame source could not return a frame."""

    def __init__(self, message: str, *, disconnected: bool = False) -> None:
        super().__init__(message)
        self.disconnected = disconnected


@dataclass(frozen=True, slots=True)
class SourceStatus:
    """Frame-source metadata used to build the shared camera status."""

    width: int | None = None
    height: int | None = None
    fps: float | None = None


class FrameSource(Protocol):
    """Common interface implemented by real and mock camera sources."""

    source_type: CameraSourceType
    index: int | None
    name: str

    def start(self) -> None:
        """Acquire the source and verify that it can produce frames."""

    def stop(self) -> None:
        """Release all resources owned by the source."""

    def read_frame(self) -> FrameArray:
        """Return the next frame."""

    def is_available(self) -> bool:
        """Return whether the source is ready to read frames."""

    def get_status(self) -> SourceStatus:
        """Return current source metadata."""


class RealCameraSource:
    """OpenCV-backed camera source for one physical device."""

    source_type = CameraSourceType.REAL

    def __init__(self, index: int) -> None:
        self.index: int | None = index
        self.name = self._camera_name(index)
        self._capture: cv2.VideoCapture | None = None
        self._last_frame: FrameArray | None = None

    def start(self) -> None:
        if self.is_available():
            return

        capture = self._create_capture(self.index)
        if not capture.isOpened():
            capture.release()
            raise CameraOpenError(
                f"Camera {self.index} is unavailable or already in use",
                busy=True,
            )

        capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, DEFAULT_WIDTH)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, DEFAULT_HEIGHT)

        frame = self._read_from_capture(capture)
        if frame is None:
            capture.release()
            raise CameraOpenError(
                f"Camera {self.index} opened but no frame is available"
            )

        self._capture = capture
        self._last_frame = frame
        logger.info(
            "Camera initialized successfully: index=%d resolution=%dx%d",
            self.index,
            frame.shape[1],
            frame.shape[0],
        )

    def stop(self) -> None:
        capture = self._capture
        self._capture = None
        self._last_frame = None
        if capture is not None:
            try:
                capture.release()
            finally:
                logger.info("Camera stopped: index=%s", self.index)

    def read_frame(self) -> FrameArray:
        capture = self._capture
        if capture is None or not capture.isOpened():
            raise CameraReadError("Camera is not available", disconnected=True)

        frame = self._read_from_capture(capture)
        if frame is None:
            disconnected = not capture.isOpened()
            message = (
                "Camera disconnected while reading a frame"
                if disconnected
                else "Camera frame could not be read"
            )
            raise CameraReadError(message, disconnected=disconnected)

        self._last_frame = frame
        return frame

    def is_available(self) -> bool:
        return bool(self._capture and self._capture.isOpened())

    def get_status(self) -> SourceStatus:
        frame = self._last_frame
        width = int(frame.shape[1]) if frame is not None else None
        height = int(frame.shape[0]) if frame is not None else None
        fps = None
        if self._capture is not None and self._capture.isOpened():
            configured_fps = float(self._capture.get(cv2.CAP_PROP_FPS))
            if 0 < configured_fps < 1000:
                fps = round(configured_fps, 2)
        return SourceStatus(width=width, height=height, fps=fps)

    @staticmethod
    def _read_from_capture(capture: cv2.VideoCapture) -> FrameArray | None:
        for _ in range(FRAME_READ_ATTEMPTS):
            try:
                ok, frame = capture.read()
            except cv2.error:
                logger.exception("OpenCV frame read raised an exception")
                return None

            if ok and frame is not None and frame.size > 0:
                return frame
            time.sleep(0.05)
        return None

    @staticmethod
    def _create_capture(index: int) -> cv2.VideoCapture:
        if platform.system() == "Windows":
            capture = cv2.VideoCapture(index, cv2.CAP_DSHOW)
            if capture.isOpened():
                return capture
            capture.release()
        return cv2.VideoCapture(index)

    @staticmethod
    def _camera_name(index: int) -> str:
        return "Default Camera" if index == 0 else f"Camera {index}"


class MockCameraSource:
    """Deterministic synthetic camera source with no hardware dependency."""

    source_type = CameraSourceType.MOCK
    index = None
    name = "Mock Camera"

    def __init__(self) -> None:
        self._started_at = 0.0
        self._active = False
        self._last_frame: FrameArray | None = None

    def start(self) -> None:
        if self._active:
            return
        self._started_at = time.monotonic()
        self._active = True
        self._last_frame = self._render_frame()
        logger.info("Mock camera initialized successfully")

    def stop(self) -> None:
        if self._active:
            logger.info("Mock camera stopped")
        self._active = False
        self._last_frame = None

    def read_frame(self) -> FrameArray:
        if not self._active:
            raise CameraReadError("Mock camera is not running")
        self._last_frame = self._render_frame()
        return self._last_frame

    def is_available(self) -> bool:
        return self._active

    def get_status(self) -> SourceStatus:
        return SourceStatus(
            width=MOCK_WIDTH,
            height=MOCK_HEIGHT,
            fps=MOCK_FPS,
        )

    def _render_frame(self) -> FrameArray:
        elapsed = max(0.0, time.monotonic() - self._started_at)
        frame = np.zeros((MOCK_HEIGHT, MOCK_WIDTH, 3), dtype=np.uint8)

        horizontal = np.linspace(24, 220, MOCK_WIDTH, dtype=np.uint8)
        vertical = np.linspace(60, 30, MOCK_HEIGHT, dtype=np.uint8)
        frame[:, :, 0] = horizontal[np.newaxis, :]
        frame[:, :, 1] = vertical[:, np.newaxis]
        frame[:, :, 2] = np.clip(
            90 + np.sin(np.linspace(0, 8, MOCK_WIDTH)) * 60,
            0,
            255,
        ).astype(np.uint8)[np.newaxis, :]

        center = (
            int(MOCK_WIDTH * (0.5 + 0.32 * np.sin(elapsed * 1.4))),
            int(MOCK_HEIGHT * 0.5),
        )
        cv2.circle(frame, center, 42, (42, 214, 194), -1)
        cv2.rectangle(
            frame,
            (24, 24),
            (MOCK_WIDTH - 25, MOCK_HEIGHT - 25),
            (225, 232, 230),
            2,
        )
        cv2.putText(
            frame,
            "MOCK CAMERA",
            (34, MOCK_HEIGHT - 38),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.85,
            (235, 242, 240),
            2,
            cv2.LINE_AA,
        )
        return frame


class CameraService:
    """Own one frame source and serialize all lifecycle operations."""

    def __init__(
        self,
        camera_id_provider: Callable[[], str] | None = None,
    ) -> None:
        self._source: FrameSource | None = None
        self._source_type: CameraSourceType | None = None
        self._state = CameraState.INITIALIZING
        self._index: int | None = None
        self._name: str | None = None
        self._message = "Camera service is initializing"
        self._code: str | None = None
        self._detected_indices: set[int] = set()
        self._camera_id_provider = camera_id_provider
        self._lock = threading.RLock()

    @property
    def is_open(self) -> bool:
        with self._lock:
            return bool(self._source and self._source.is_available())

    def list_cameras(self) -> list[CameraInfo]:
        """Probe a bounded index range without assuming camera zero exists."""
        with self._lock:
            cameras = self._scan_cameras_unlocked()
            self._detected_indices = {camera.index for camera in cameras}
            logger.info(
                "Camera scan completed: %d device(s) available",
                len(cameras),
            )
            return cameras

    def detect_cameras(self) -> list[CameraInfo]:
        """Release the active camera and enumerate physical devices."""
        with self._lock:
            self._release_source_unlocked(clear_identity=True)
            self._set_state(
                CameraState.INITIALIZING,
                message="Detecting camera devices",
            )
            cameras = self._scan_cameras_unlocked()
            self._detected_indices = {camera.index for camera in cameras}
            if not cameras:
                logger.warning("No camera device detected")
                self._set_state(
                    CameraState.NOT_FOUND,
                    message="未检测到可用摄像头",
                    code=ErrorCode.CAMERA_NOT_FOUND,
                )
            return cameras

    def open_camera(self, index: int) -> CameraStatusData:
        """Open a selected camera through the reconnect lifecycle."""
        return self.reconnect(index=index)

    def reconnect(self, index: int | None = None) -> CameraStatusData:
        """Safely release, redetect, and open a real camera."""
        with self._lock:
            self._release_source_unlocked(clear_identity=True)
            self._set_state(
                CameraState.INITIALIZING,
                message="Initializing camera",
            )
            cameras = self._scan_cameras_unlocked()
            self._detected_indices = {camera.index for camera in cameras}

            if not cameras:
                logger.warning("No camera device detected")
                self._set_state(
                    CameraState.NOT_FOUND,
                    message="未检测到可用摄像头",
                    code=ErrorCode.CAMERA_NOT_FOUND,
                )
                raise AppException(
                    message="未检测到可用摄像头",
                    code=ErrorCode.CAMERA_NOT_FOUND,
                    status_code=404,
                )

            available_indices = {camera.index for camera in cameras}
            target_index = index if index is not None else cameras[0].index
            if target_index not in available_indices:
                self._set_state(
                    CameraState.NOT_FOUND,
                    message=f"Camera {target_index} was not found",
                    code=ErrorCode.CAMERA_NOT_FOUND,
                )
                raise AppException(
                    message=f"Camera {target_index} was not found",
                    code=ErrorCode.CAMERA_NOT_FOUND,
                    status_code=404,
                )

            source = RealCameraSource(target_index)
            try:
                source.start()
            except CameraOpenError as exc:
                source.stop()
                state = CameraState.BUSY if exc.busy else CameraState.OPEN_FAILED
                code = (
                    ErrorCode.CAMERA_DEVICE_BUSY
                    if exc.busy
                    else ErrorCode.CAMERA_OPEN_FAILED
                )
                logger.error("Failed to open camera %d: %s", target_index, exc)
                self._set_state(state, message=str(exc), code=code)
                raise AppException(
                    message=str(exc),
                    code=code,
                    status_code=409,
                ) from exc

            self._source = source
            self._source_type = source.source_type
            self._index = source.index
            self._name = source.name
            self._set_state(
                CameraState.AVAILABLE,
                message="Camera initialized successfully",
            )
            logger.info("Camera detected and opened: index=%d", target_index)
            return self._status_unlocked()

    def switch_to_mock(self) -> CameraStatusData:
        """Release hardware and activate the synthetic camera source."""
        with self._lock:
            logger.info("Switching to mock camera")
            self._release_source_unlocked(clear_identity=True)
            source = MockCameraSource()
            source.start()
            self._source = source
            self._source_type = source.source_type
            self._index = source.index
            self._name = source.name
            self._set_state(
                CameraState.MOCK,
                message="Mock camera is active",
            )
            return self._status_unlocked()

    def close_camera(self) -> CameraStatusData:
        """Release the active source and return the resulting state."""
        with self._lock:
            self._release_source_unlocked(clear_identity=False)
            self._set_state(
                CameraState.CLOSED,
                message="Camera is closed",
                code=ErrorCode.CAMERA_CLOSED,
            )
            return self._status_unlocked()

    def get_status(self) -> CameraStatusData:
        """Return the current source state without starting hardware."""
        with self._lock:
            source = self._source
            if source is not None and not source.is_available():
                logger.warning("Camera disconnected")
                self._release_source_unlocked(clear_identity=False)
                self._set_state(
                    CameraState.DISCONNECTED,
                    message="摄像头已断开",
                    code=ErrorCode.CAMERA_DISCONNECTED,
                )
            return self._status_unlocked()

    def read_frame(self) -> FrameArray:
        """Read one frame or convert source failures into stable states."""
        with self._lock:
            source = self._source
            if source is None or not source.is_available():
                self._release_source_unlocked(clear_identity=False)
                self._set_state(
                    CameraState.CLOSED,
                    message="Camera is not open",
                    code=ErrorCode.CAMERA_CLOSED,
                )
                raise AppException(
                    message="Camera is not open",
                    code=ErrorCode.CAMERA_CLOSED,
                    status_code=409,
                )

            try:
                frame = source.read_frame()
            except CameraReadError as exc:
                self._release_source_unlocked(clear_identity=False)
                if exc.disconnected:
                    logger.warning("Camera disconnected: %s", exc)
                    self._set_state(
                        CameraState.DISCONNECTED,
                        message="摄像头已断开",
                        code=ErrorCode.CAMERA_DISCONNECTED,
                    )
                    code = ErrorCode.CAMERA_DISCONNECTED
                else:
                    logger.error("Camera frame read failed: %s", exc)
                    self._set_state(
                        CameraState.READ_FAILED,
                        message="摄像头画面读取失败",
                        code=ErrorCode.CAMERA_READ_FAILED,
                    )
                    code = ErrorCode.CAMERA_READ_FAILED
                raise AppException(
                    message=str(exc),
                    code=code,
                    status_code=503,
                ) from exc

            return frame.copy()

    def _scan_cameras_unlocked(self) -> list[CameraInfo]:
        scan_limit = self._scan_limit()
        cameras: list[CameraInfo] = []
        active_index = (
            self._index
            if self._source_type == CameraSourceType.REAL
            and self._source
            and self._source.is_available()
            else None
        )

        for index in range(scan_limit):
            if index == active_index:
                cameras.append(
                    CameraInfo(
                        index=index,
                        name=self._camera_name(index),
                        available=True,
                    )
                )
                continue

            capture = RealCameraSource._create_capture(index)
            try:
                if capture.isOpened():
                    cameras.append(
                        CameraInfo(
                            index=index,
                            name=self._camera_name(index),
                            available=True,
                        )
                    )
            finally:
                capture.release()
        return cameras

    def _release_source_unlocked(self, *, clear_identity: bool) -> None:
        source = self._source
        self._source = None
        if source is not None:
            source.stop()
        if clear_identity:
            self._source_type = None
            self._index = None
            self._name = None

    def _status_unlocked(self) -> CameraStatusData:
        source = self._source
        opened = bool(source and source.is_available())
        source_status = source.get_status() if source is not None else SourceStatus()
        return CameraStatusData(
            state=self._state,
            source=self._source_type,
            camera_id=self._camera_id(),
            opened=opened,
            index=self._index,
            name=self._name,
            available=opened,
            width=source_status.width,
            height=source_status.height,
            fps=source_status.fps,
            message=self._message,
            code=self._code,
        )

    def _camera_id(self) -> str:
        if self._source_type == CameraSourceType.MOCK:
            return "MOCK-CAMERA"
        try:
            if self._camera_id_provider is not None:
                return self._camera_id_provider()
            from backend.services.config_service import get_config_service

            return get_config_service().get_config().camera_id
        except Exception:
            logger.warning("Could not read configured camera_id", exc_info=True)
            return "CAM-001"

    def _set_state(
        self,
        state: CameraState,
        *,
        message: str | None = None,
        code: ErrorCode | str | None = None,
    ) -> None:
        self._state = state
        self._message = message
        self._code = str(code) if code is not None else None

    @staticmethod
    def _scan_limit() -> int:
        try:
            return max(
                1,
                int(os.getenv("COLORVISION_CAMERA_SCAN_LIMIT", DEFAULT_SCAN_LIMIT)),
            )
        except ValueError:
            return DEFAULT_SCAN_LIMIT

    @staticmethod
    def _camera_name(index: int) -> str:
        return RealCameraSource._camera_name(index)


@lru_cache(maxsize=1)
def get_camera_service() -> CameraService:
    """Return the process-wide camera service."""
    return CameraService()
