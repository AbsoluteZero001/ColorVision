"""Opt-in real camera integration test."""

from __future__ import annotations

import os
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from backend.main import app


@unittest.skipUnless(
    os.getenv("COLORVISION_TEST_CAMERA") == "1",
    "set COLORVISION_TEST_CAMERA=1 to run hardware tests",
)
class CameraIntegrationTests(unittest.TestCase):
    def test_camera_capture_and_static_preview(self) -> None:
        with TestClient(app) as client:
            listed = client.get("/api/camera/list")
            self.assertEqual(listed.status_code, 200, listed.text)
            cameras = listed.json()["data"]["cameras"]
            available = [camera for camera in cameras if camera["available"]]
            self.assertTrue(available, "No available camera was detected")

            opened = client.post(
                "/api/camera/open",
                json={"index": available[0]["index"]},
            )
            self.assertEqual(opened.status_code, 200, opened.text)
            self.assertTrue(opened.json()["data"]["opened"])

            captured = client.post("/api/camera/capture")
            self.assertEqual(captured.status_code, 200, captured.text)
            data = captured.json()["data"]
            self.assertTrue(Path(data["image_path"]).is_file())

            preview = client.get(data["image_url"])
            self.assertEqual(preview.status_code, 200)
            self.assertEqual(preview.headers["content-type"], "image/jpeg")
            self.assertGreater(len(preview.content), 10_000)

            closed = client.post("/api/camera/close")
            self.assertEqual(closed.status_code, 200)
            self.assertFalse(closed.json()["data"]["opened"])


if __name__ == "__main__":
    unittest.main()
