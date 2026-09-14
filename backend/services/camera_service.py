"""OpenCV camera discovery, lifecycle, and frame access."""

from __future__ import annotations

import logging
import os
import platform
import threading
import time
from functools import lru_cache

import cv2
import numpy as np
import numpy.typing as npt

from backend.models.camera import CameraInfo, CameraStatusData
from backend.models.common import ErrorCode
from backend.utils.errors import AppException

logger = logging.getLogger(__name__)

DEFAULT_SCAN_LIMIT = 5
DEFAULT_WIDTH = 1280
DEFAULT_HEIGHT = 720
FRAME_READ_ATTEMPTS = 4


class CameraService:
    """Own one active OpenCV capture and serialize access to its frame buffer."""

    def __init__(self) -> None:
        self._capture: cv2.VideoCapture | None = None
        self._index: int | None = None
        self._name: str | None = None
        self._last_frame: npt.NDArray[np.uint8] | None = None
        self._lock = threading.RLock()

    @property
    def is_open(self) -> bool:
        with self._lock:
            return bool(self._capture and self._capture.isOpened())

    def list_cameras(self) -> list[CameraInfo]:
        """Probe a bounded index range without assuming camera zero exists."""
        try:
            scan_limit = max(
                1,
                int(os.getenv("COLORVISION_CAMERA_SCAN_LIMIT", DEFAULT_SCAN_LIMIT)),
            )
        except ValueError:
            scan_limit = DEFAULT_SCAN_LIMIT

        cameras: list[CameraInfo] = []
        with self._lock:
            active_index = self._index if self.is_open else None

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

                capture = self._create_capture(index)
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

        logger.info("Camera scan completed: %d device(s) available", len(cameras))
        return cameras

    def open_camera(self, index: int) -> CameraStatusData:
        """Open a selected camera and verify that at least one frame is readable."""
        if index < 0:
            raise AppException(
                message="Camera index must be zero or greater",
                code=ErrorCode.CAMERA_NOT_FOUND,
                status_code=400,
            )

        with self._lock:
            self._close_unlocked()
            capture = self._create_capture(index)

            if not capture.isOpened():
                capture.release()
                logger.warning("Camera %d could not be opened", index)
                raise AppException(
                    message=f"Camera {index} is unavailable or already in use",
                    code=ErrorCode.CAMERA_OPEN_FAILED,
                    status_code=409,
                )

            capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            capture.set(cv2.CAP_PROP_FRAME_WIDTH, DEFAULT_WIDTH)
            capture.set(cv2.CAP_PROP_FRAME_HEIGHT, DEFAULT_HEIGHT)

            frame = self._read_from_capture(capture)
            if frame is None:
                capture.release()
                logger.error("Camera %d opened but did not return a frame", index)
                raise AppException(
                    message=f"Camera {index} opened but no frame is available",
                    code=ErrorCode.CAMERA_OPEN_FAILED,
                    status_code=503,
                )

            self._capture = capture
            self._index = index
            self._name = self._camera_name(index)
            self._last_frame = frame
            logger.info(
                "Camera opened: index=%d resolution=%dx%d",
                index,
                frame.shape[1],
                frame.shape[0],
            )
            return self._status_unlocked(available=True)

    def close_camera(self) -> CameraStatusData:
        """Release the active camera and return the resulting state."""
        with self._lock:
            was_open = self._capture is not None
            index = self._index
            available = bool(was_open and self._capture and self._capture.isOpened())
            self._close_unlocked()
            logger.info("Camera closed: index=%s", index)
            return CameraStatusData(
                opened=False,
                index=index,
                name=self._camera_name(index) if index is not None else None,
                available=available,
            )

    def get_status(self) -> CameraStatusData:
        """Return the current capture state."""
        with self._lock:
            return self._status_unlocked(
                available=bool(self._capture and self._capture.isOpened())
            )

    def read_frame(self) -> npt.NDArray[np.uint8]:
        """Read one BGR frame or raise a stable application error."""
        with self._lock:
            if not self._capture or not self._capture.isOpened():
                raise AppException(
                    message="Camera is not open",
                    code=ErrorCode.CAMERA_CLOSED,
                    status_code=409,
                )

            frame = self._read_from_capture(self._capture)
            if frame is None:
                logger.error("Frame capture failed for camera %s", self._index)
                raise AppException(
                    message="Camera frame could not be read",
                    code=ErrorCode.CAPTURE_FAILED,
                    status_code=503,
                )

            self._last_frame = frame
            return frame.copy()

    def _status_unlocked(self, available: bool) -> CameraStatusData:
        opened = bool(self._capture and self._capture.isOpened())
        frame = self._last_frame
        height = int(frame.shape[0]) if frame is not None else None
        width = int(frame.shape[1]) if frame is not None else None
        fps = None
        if opened and self._capture:
            configured_fps = float(self._capture.get(cv2.CAP_PROP_FPS))
            if 0 < configured_fps < 1000:
                fps = round(configured_fps, 2)

        return CameraStatusData(
            opened=opened,
            index=self._index,
            name=self._name,
            available=available,
            width=width,
            height=height,
            fps=fps,
        )

    def _close_unlocked(self) -> None:
        if self._capture is not None:
            try:
                self._capture.release()
            finally:
                self._capture = None
        self._index = None
        self._name = None
        self._last_frame = None

    @staticmethod
    def _read_from_capture(
        capture: cv2.VideoCapture,
    ) -> npt.NDArray[np.uint8] | None:
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


@lru_cache(maxsize=1)
def get_camera_service() -> CameraService:
    """Return the process-wide camera service."""
    return CameraService()
