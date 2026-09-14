"""Camera lifecycle and source behavior tests without physical hardware."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from backend.models.camera import CameraInfo, CameraState
from backend.models.common import ErrorCode
from backend.services.camera_service import (
    CameraOpenError,
    CameraReadError,
    CameraService,
    RealCameraSource,
)
from backend.utils.errors import AppException


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


if __name__ == "__main__":
    unittest.main()
