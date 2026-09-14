"""Camera lifecycle and source behavior tests without physical hardware."""

from __future__ import annotations

import unittest
from unittest.mock import patch

import numpy as np

from backend.models.camera import CameraInfo, CameraState
from backend.models.common import ErrorCode
from backend.services.camera_service import (
    FRAME_VALIDATION_COUNT,
    CameraOpenError,
    CameraReadError,
    CameraService,
    RealCameraSource,
)
from backend.utils.errors import AppException


class FakeCapture:
    """Minimal OpenCV capture double with a scripted read result."""

    def __init__(self, results: list[tuple[bool, np.ndarray | None]]) -> None:
        self.results = results
        self.opened = True
        self.released = False

    def isOpened(self) -> bool:
        return self.opened and not self.released

    def read(self) -> tuple[bool, np.ndarray | None]:
        if self.results:
            return self.results.pop(0)
        return False, None

    def set(self, *_: object) -> bool:
        return True

    def get(self, *_: object) -> float:
        return 15.0

    def release(self) -> None:
        self.released = True


class CameraServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = CameraService(camera_id_provider=lambda: "CAM-TEST")

    def tearDown(self) -> None:
        self.service.close_camera()

    def test_no_camera_sets_not_found(self) -> None:
        with patch.object(
            self.service,
            "_scan_cameras_unlocked",
            return_value=[],
        ):
            cameras = self.service.detect_cameras()

        self.assertEqual(cameras, [])
        status = self.service.get_status()
        self.assertEqual(status.state, CameraState.NOT_FOUND)
        self.assertEqual(status.code, ErrorCode.CAMERA_NOT_FOUND)
        self.assertFalse(status.opened)

    def test_mock_camera_produces_frames(self) -> None:
        status = self.service.switch_to_mock()
        frame = self.service.read_frame()

        self.assertEqual(status.state, CameraState.MOCK)
        self.assertEqual(status.camera_id, "MOCK-CAMERA")
        self.assertTrue(status.opened)
        self.assertEqual(frame.shape, (540, 960, 3))

    def test_read_failure_marks_disconnected(self) -> None:
        self.service.switch_to_mock()

        with patch(
            "backend.services.camera_service.MockCameraSource.read_frame",
            side_effect=CameraReadError("device removed", disconnected=True),
        ):
            with self.assertRaises(AppException) as raised:
                self.service.read_frame()

        self.assertEqual(raised.exception.code, ErrorCode.CAMERA_DISCONNECTED)
        status = self.service.get_status()
        self.assertEqual(status.state, CameraState.DISCONNECTED)
        self.assertFalse(status.opened)

    def test_busy_camera_sets_busy_state(self) -> None:
        detected = [CameraInfo(index=0, name="Default Camera", available=True)]
        with (
            patch.object(
                self.service,
                "_scan_cameras_unlocked",
                return_value=detected,
            ),
            patch.object(
                RealCameraSource,
                "start",
                side_effect=CameraOpenError("camera is busy", busy=True),
            ),
        ):
            with self.assertRaises(AppException) as raised:
                self.service.reconnect()

        self.assertEqual(raised.exception.code, ErrorCode.CAMERA_DEVICE_BUSY)
        status = self.service.get_status()
        self.assertEqual(status.state, CameraState.BUSY)
        self.assertFalse(status.opened)

    def test_open_success_with_failed_reads_is_not_available(self) -> None:
        capture = FakeCapture([(False, None)] * 12)
        source = RealCameraSource(0)

        with (
            patch.object(
                RealCameraSource,
                "_create_capture",
                return_value=capture,
            ),
            patch("backend.services.camera_service.time.sleep"),
        ):
            with self.assertRaises(CameraReadError):
                source.start()

        self.assertFalse(source.is_available())

    def test_open_success_with_none_frame_is_not_available(self) -> None:
        capture = FakeCapture([(True, None)] * 12)
        source = RealCameraSource(0)

        with (
            patch.object(
                RealCameraSource,
                "_create_capture",
                return_value=capture,
            ),
            patch("backend.services.camera_service.time.sleep"),
        ):
            with self.assertRaises(CameraReadError):
                source.start()

        self.assertFalse(source.is_available())

    def test_single_frame_before_read_failures_is_not_available(self) -> None:
        black_frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        capture = FakeCapture(
            [(True, black_frame)] + [(False, None)] * 11
        )
        source = RealCameraSource(0)

        with (
            patch.object(
                RealCameraSource,
                "_create_capture",
                return_value=capture,
            ),
            patch("backend.services.camera_service.time.sleep"),
        ):
            with self.assertRaises(CameraReadError):
                source.start()

        self.assertFalse(source.is_available())

    def test_consecutive_valid_frames_mark_camera_available(self) -> None:
        black_frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        capture = FakeCapture(
            [(True, black_frame)] * FRAME_VALIDATION_COUNT
        )
        source = RealCameraSource(0)

        with patch.object(
            RealCameraSource,
            "_create_capture",
            return_value=capture,
        ):
            source.start()

        self.assertTrue(source.is_available())
        self.assertEqual(source.get_status().width, 1280)
        self.assertEqual(source.get_status().height, 720)
        source.stop()

    def test_scan_ignores_open_device_without_valid_frames(self) -> None:
        with (
            patch.object(
                RealCameraSource,
                "_create_capture",
                side_effect=lambda _: FakeCapture([(False, None)] * 12),
            ),
            patch("backend.services.camera_service.time.sleep"),
        ):
            cameras = self.service.detect_cameras()

        self.assertEqual(cameras, [])
        status = self.service.get_status()
        self.assertEqual(status.state, CameraState.NOT_FOUND)
        self.assertFalse(status.opened)

    def test_reconnect_without_valid_frames_sets_read_failed(self) -> None:
        detected = [CameraInfo(index=0, name="Default Camera", available=True)]
        with (
            patch.object(
                self.service,
                "_scan_cameras_unlocked",
                return_value=detected,
            ),
            patch.object(
                RealCameraSource,
                "start",
                side_effect=CameraReadError("no consecutive frames"),
            ),
        ):
            with self.assertRaises(AppException) as raised:
                self.service.reconnect()

        self.assertEqual(raised.exception.code, ErrorCode.CAMERA_READ_FAILED)
        status = self.service.get_status()
        self.assertEqual(status.state, CameraState.READ_FAILED)
        self.assertFalse(status.opened)


if __name__ == "__main__":
    unittest.main()
