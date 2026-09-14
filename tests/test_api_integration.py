"""FastAPI integration tests for the main business endpoints."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np
from fastapi.testclient import TestClient

from backend.api import upload as upload_api
from backend.main import app
from backend.models.config import AppConfig
from backend.services.camera_service import get_camera_service
from backend.services.upload_service import UploadService


class ApiIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client_context = TestClient(app)
        cls.client = cls.client_context.__enter__()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client_context.__exit__(None, None, None)

    def test_health_docs_and_frontend(self) -> None:
        health = self.client.get("/api/health")
        docs = self.client.get("/docs")
        frontend = self.client.get("/")

        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json()["data"]["app"], "颜色识别系统")
        self.assertEqual(docs.status_code, 200)
        self.assertEqual(frontend.status_code, 200)
        self.assertIn("text/html", frontend.headers["content-type"])

    def test_missing_frontend_returns_html_not_api_json(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            with patch(
                "backend.main.get_frontend_dist_directory",
                return_value=Path(temporary_directory),
            ):
                response = self.client.get("/")

        self.assertEqual(response.status_code, 503)
        self.assertIn("text/html", response.headers["content-type"])
        self.assertNotIn("application/json", response.headers["content-type"])
        self.assertIn("Vue production bundle was not found", response.text)

    def test_color_analysis_and_roi_validation(self) -> None:
        image = np.full((120, 160, 3), (40, 35, 120), dtype=np.uint8)
        ok, encoded = cv2.imencode(".jpg", image)
        self.assertTrue(ok)
        image_bytes = encoded.tobytes()

        response = self.client.post(
            "/api/color/analyze",
            files={"image": ("solid.jpg", image_bytes, "image/jpeg")},
            data={"x": "20", "y": "30", "width": "80", "height": "60"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["data"]["hex"], "#782328")

        invalid = self.client.post(
            "/api/color/analyze",
            files={"image": ("solid.jpg", image_bytes, "image/jpeg")},
            data={"x": "100", "y": "30", "width": "80", "height": "60"},
        )
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(invalid.json()["code"], "INVALID_ROI")

    def test_mock_upload_endpoint(self) -> None:
        original = np.full((80, 120, 3), (40, 35, 120), dtype=np.uint8)
        roi = original[20:60, 30:90]
        ok_original, original_encoded = cv2.imencode(".jpg", original)
        ok_roi, roi_encoded = cv2.imencode(".jpg", roi)
        self.assertTrue(ok_original and ok_roi)

        mock_service = UploadService(
            config_provider=lambda: AppConfig(mock_mode=True),
        )
        with patch.object(upload_api, "get_upload_service", return_value=mock_service):
            response = self.client.post(
                "/api/upload",
                files={
                    "original_image": (
                        "original.jpg",
                        original_encoded.tobytes(),
                        "image/jpeg",
                    ),
                    "roi_image": (
                        "roi.jpg",
                        roi_encoded.tobytes(),
                        "image/jpeg",
                    ),
                },
                data={
                    "rgb": json.dumps({"r": 120, "g": 35, "b": 40}),
                    "lab": json.dumps({"l": 27.84, "a": 37.0, "b": 18.0}),
                    "hex": "#782328",
                    "roi": json.dumps(
                        {"x": 30, "y": 20, "width": 60, "height": 40}
                    ),
                    "camera_id": "CAM-TEST",
                    "timestamp": "2026-09-14T14:00:00+08:00",
                },
            )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["data"]["mode"], "mock")
        self.assertTrue(
            response.json()["data"]["request_id"].startswith("MOCK-")
        )

    def test_camera_mock_capture_lifecycle(self) -> None:
        opened = self.client.post("/api/camera/mock")
        self.assertEqual(opened.status_code, 200, opened.text)
        self.assertEqual(opened.json()["data"]["state"], "mock")
        self.assertTrue(opened.json()["data"]["opened"])

        captured = self.client.post("/api/camera/capture")
        self.assertEqual(captured.status_code, 200, captured.text)
        image_url = captured.json()["data"]["image_url"]
        preview = self.client.get(image_url)
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(preview.headers["content-type"], "image/jpeg")

        closed = self.client.post("/api/camera/close")
        self.assertEqual(closed.status_code, 200, closed.text)
        self.assertEqual(closed.json()["data"]["state"], "closed")

    def test_camera_detect_error_uses_unified_envelope(self) -> None:
        service = get_camera_service()
        with patch.object(
            service,
            "_scan_cameras_unlocked",
            return_value=[],
        ):
            response = self.client.post("/api/camera/detect")

        self.assertEqual(response.status_code, 404, response.text)
        payload = response.json()
        self.assertFalse(payload["success"])
        self.assertIsNone(payload["data"])
        self.assertEqual(payload["code"], "CAMERA_NOT_FOUND")


if __name__ == "__main__":
    unittest.main()
