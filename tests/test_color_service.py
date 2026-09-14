"""Color conversion and ROI validation tests."""

from __future__ import annotations

import unittest

import numpy as np

from backend.models.common import ErrorCode
from backend.services.color_service import ColorService
from backend.utils.errors import AppException


class ColorServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = ColorService()

    def test_primary_and_neutral_colors(self) -> None:
        cases = {
            "red": ((255, 0, 0), "#FF0000"),
            "green": ((0, 255, 0), "#00FF00"),
            "blue": ((0, 0, 255), "#0000FF"),
            "white": ((255, 255, 255), "#FFFFFF"),
            "black": ((0, 0, 0), "#000000"),
        }

        for name, (expected_rgb, expected_hex) in cases.items():
            with self.subTest(name=name):
                red, green, blue = expected_rgb
                bgr_roi = np.full(
                    (20, 20, 3),
                    (blue, green, red),
                    dtype=np.uint8,
                )
                measured_rgb = self.service.calculate_rgb(bgr_roi)
                measured_lab = self.service.calculate_lab(measured_rgb)

                self.assertEqual(measured_rgb, expected_rgb)
                self.assertEqual(self.service.rgb_to_hex(measured_rgb), expected_hex)
                self.assertGreaterEqual(measured_lab[0], 0.0)
                self.assertLessEqual(measured_lab[0], 100.0)
                self.assertGreaterEqual(measured_lab[1], -128.0)
                self.assertLessEqual(measured_lab[1], 127.0)
                self.assertGreaterEqual(measured_lab[2], -128.0)
                self.assertLessEqual(measured_lab[2], 127.0)

    def test_roi_out_of_bounds_is_rejected(self) -> None:
        image = np.zeros((80, 120, 3), dtype=np.uint8)
        with self.assertRaises(AppException) as context:
            self.service.analyze_roi(image, 100, 20, 40, 20)
        self.assertEqual(context.exception.code, ErrorCode.INVALID_ROI)

    def test_zero_sized_roi_is_rejected(self) -> None:
        image = np.zeros((80, 120, 3), dtype=np.uint8)
        with self.assertRaises(AppException) as context:
            self.service.analyze_roi(image, 20, 20, 0, 20)
        self.assertEqual(context.exception.code, ErrorCode.INVALID_ROI)


if __name__ == "__main__":
    unittest.main()
