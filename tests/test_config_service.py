"""Configuration migration, split config/, and persistence tests."""

from __future__ import annotations

import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from backend.models.config import AppConfigUpdate
from backend.services.config_service import ConfigService
from backend.utils.paths import APP_ROOT_ENV, CONFIG_OVERRIDE_ENV


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

    def test_unified_config_directory_persists_split_files_and_ignores_cwd(
        self,
    ) -> None:
        with TemporaryDirectory() as directory:
            app_root = (Path(directory) / "CustomInstall" / "ColorVision").resolve()
            other_cwd = Path(directory) / "other_cwd"
            other_cwd.mkdir()

            original_cwd = os.getcwd()
            try:
                os.chdir(other_cwd)
                with patch.dict(
                    os.environ,
                    {
                        APP_ROOT_ENV: str(app_root),
                        CONFIG_OVERRIDE_ENV: "",
                    },
                ):
                    service = ConfigService()
                    defaults = service.get_config()
                    self.assertEqual(defaults.camera_id, "CAM-001")

                    app_json = app_root / "config" / "app.json"
                    api_json = app_root / "config" / "api-config.json"
                    camera_json = app_root / "config" / "camera.json"
                    self.assertTrue(app_json.is_file())
                    self.assertTrue(api_json.is_file())
                    self.assertTrue(camera_json.is_file())

                    service.update_config(
                        AppConfigUpdate(
                            api_url="https://example.test/color",
                            token="secret-token",
                            mock_mode=False,
                            camera_id="CAM-999",
                            port=8111,
                        )
                    )

                    reloaded = ConfigService().get_config()
                    self.assertEqual(reloaded.api_url, "https://example.test/color")
                    self.assertEqual(reloaded.token, "secret-token")
                    self.assertFalse(reloaded.mock_mode)
                    self.assertEqual(reloaded.camera_id, "CAM-999")
                    self.assertEqual(reloaded.port, 8111)

                    app_raw = json.loads(app_json.read_text(encoding="utf-8"))
                    api_raw = json.loads(api_json.read_text(encoding="utf-8"))
                    camera_raw = json.loads(camera_json.read_text(encoding="utf-8"))
                    self.assertEqual(app_raw["install_dir"], str(app_root))
                    self.assertEqual(app_raw["port"], 8111)
                    self.assertEqual(api_raw["api_url"], "https://example.test/color")
                    self.assertEqual(api_raw["token"], "secret-token")
                    self.assertFalse(api_raw["mock_mode"])
                    self.assertEqual(camera_raw["camera_id"], "CAM-999")
            finally:
                os.chdir(original_cwd)

    def test_legacy_config_json_migrates_to_split_config_files(self) -> None:
        with TemporaryDirectory() as directory:
            config_dir = Path(directory) / "config"
            config_dir.mkdir()
            legacy_file = config_dir / "config.json"
            legacy_file.write_text(
                json.dumps(
                    {
                        "api_url": "http://10.0.0.2:9000/api/color",
                        "token": "legacy-tok",
                        "camera_id": "CAM-LEGACY",
                        "mock_mode": False,
                        "request_timeout_seconds": 9.0,
                        "port": 8088,
                    }
                ),
                encoding="utf-8",
            )

            service = ConfigService(config_dir=config_dir)
            loaded = service.get_config()

            self.assertEqual(loaded.api_url, "http://10.0.0.2:9000/api/color")
            self.assertEqual(loaded.token, "legacy-tok")
            self.assertEqual(loaded.camera_id, "CAM-LEGACY")
            self.assertFalse(loaded.mock_mode)
            self.assertEqual(loaded.timeout, 9.0)
            self.assertEqual(loaded.port, 8088)
            self.assertTrue((config_dir / "app.json").is_file())
            self.assertTrue((config_dir / "api-config.json").is_file())
            self.assertTrue((config_dir / "camera.json").is_file())


if __name__ == "__main__":
    unittest.main()
