"""Mock upload service tests."""

from __future__ import annotations

import asyncio
import unittest

from backend.models.config import AppConfig
from backend.services.upload_service import UploadPayload, UploadService


def make_payload() -> UploadPayload:
    return UploadPayload(
        original_image=b"original-jpeg",
        original_filename="original.jpg",
        original_content_type="image/jpeg",
        roi_image=b"roi-jpeg",
        roi_filename="roi.jpg",
        roi_content_type="image/jpeg",
        rgb={"r": 120, "g": 35, "b": 40},
        lab={"l": 27.84, "a": 37.0, "b": 18.0},
        hex="#782328",
        roi={"x": 10, "y": 20, "width": 60, "height": 40},
        camera_id="CAM-TEST",
        timestamp="2026-09-14T14:00:00+08:00",
    )


class UploadServiceTests(unittest.TestCase):
    def test_mock_upload_returns_request_id(self) -> None:
        service = UploadService(
            config_provider=lambda: AppConfig(mock_mode=True),
        )
        result = asyncio.run(service.upload(make_payload()))

        self.assertTrue(result.success)
        self.assertEqual(result.mode, "mock")
        self.assertTrue(result.request_id.startswith("MOCK-"))


if __name__ == "__main__":
    unittest.main()
