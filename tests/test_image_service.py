"""Image persistence, Unicode paths, and retention policy tests."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from backend.models.config import AppConfig
from backend.services.image_service import ImageService
from backend.utils.paths import APP_ROOT_ENV


class ImageServiceRetentionTests(unittest.TestCase):
    def _create_service(
        self,
        directory: str,
        **config_values: int,
    ) -> ImageService:
        captures = Path(directory) / "data" / "photos" / "captures"
        captures.mkdir(parents=True)
        return ImageService(
            captures_directory=captures,
            results_directory=Path(directory) / "data" / "history",
            config_provider=lambda: AppConfig(**config_values),
        )

    def test_retention_is_disabled_by_default_values(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            service = self._create_service(directory)
            captures = service._captures_directory
            for index in range(3):
                (captures / f"capture-{index}.jpg").write_bytes(b"jpeg")

            deleted = service.enforce_retention()

            self.assertEqual(deleted, 0)
            self.assertEqual(len(list(captures.glob("*.jpg"))), 3)

    def test_max_image_count_removes_oldest_captures(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            service = self._create_service(directory, max_image_count=2)
            captures = service._captures_directory
            for index in range(4):
                path = captures / f"capture-{index}.jpg"
                path.write_bytes(b"jpeg")
                os.utime(path, (100 + index, 100 + index))

            deleted = service.enforce_retention()

            self.assertEqual(deleted, 2)
            self.assertEqual(
                sorted(path.name for path in captures.glob("*.jpg")),
                ["capture-2.jpg", "capture-3.jpg"],
            )

    def test_retention_days_removes_expired_captures(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            service = self._create_service(
                directory,
                image_retention_days=1,
            )
            captures = service._captures_directory
            old_file = captures / "old.jpg"
            recent_file = captures / "recent.jpg"
            old_file.write_bytes(b"old")
            recent_file.write_bytes(b"recent")
            os.utime(old_file, (1, 1))

            deleted = service.enforce_retention()

            self.assertEqual(deleted, 1)
            self.assertFalse(old_file.exists())
            self.assertTrue(recent_file.exists())

    def test_default_captures_save_under_data_photos_not_exe_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            app_root = (Path(directory) / "测试目录" / "ColorVision").resolve()
            app_root.mkdir(parents=True)
            with patch.dict(os.environ, {APP_ROOT_ENV: str(app_root)}):
                service = ImageService(config_provider=lambda: AppConfig())
                frame = np.full((32, 48, 3), (40, 80, 120), dtype=np.uint8)
                saved = service.save_capture(frame)

                self.assertTrue(saved.is_file())
                self.assertEqual(
                    saved.parent.resolve(),
                    (app_root / "data" / "photos" / "captures").resolve(),
                )
                self.assertNotEqual(saved.parent.resolve(), app_root)
                self.assertEqual(
                    service.build_media_url(saved),
                    f"/media/photos/captures/{saved.name}",
                )
                decoded = service.read_image(saved)
                self.assertEqual(decoded.shape, (32, 48, 3))


if __name__ == "__main__":
    unittest.main()
