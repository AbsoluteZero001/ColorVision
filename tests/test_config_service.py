"""Configuration migration and persistence tests."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from backend.models.config import AppConfigUpdate
from backend.services.config_service import ConfigService


class ConfigServiceTests(unittest.TestCase):
    def test_default_and_update_are_persisted(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            service = ConfigService(path)

            defaults = service.get_config()
            self.assertEqual(defaults.port, 8000)
            self.assertEqual(defaults.timeout, 10.0)
            self.assertTrue(defaults.log_enabled)
            self.assertTrue(defaults.log_image_storage_enabled)

            service.update_config(
                AppConfigUpdate(
                    camera_id="CAM-TEST",
                    timeout=12.5,
                    port=8123,
                )
            )
            reloaded = ConfigService(path).get_config()

            self.assertEqual(reloaded.camera_id, "CAM-TEST")
            self.assertEqual(reloaded.timeout, 12.5)
            self.assertEqual(reloaded.port, 8123)
            self.assertEqual(reloaded.log_retention_days, 0)
            self.assertEqual(reloaded.max_log_count, 0)

    def test_legacy_timeout_key_is_migrated(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(
                json.dumps(
                    {
                        "api_url": "http://127.0.0.1:9000/api/color",
                        "token": "",
                        "camera_id": "CAM-OLD",
                        "auto_upload": False,
                        "mock_mode": True,
                        "request_timeout_seconds": 7.5,
                    }
                ),
                encoding="utf-8",
            )

            config_data = ConfigService(path).get_config()
            persisted = json.loads(path.read_text(encoding="utf-8"))

            self.assertEqual(config_data.timeout, 7.5)
            self.assertEqual(config_data.port, 8000)
            self.assertNotIn("request_timeout_seconds", persisted)
            self.assertEqual(persisted["timeout"], 7.5)
            self.assertEqual(persisted["port"], 8000)


if __name__ == "__main__":
    unittest.main()
