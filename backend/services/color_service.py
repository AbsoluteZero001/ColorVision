"""Color statistics and CIELAB conversion service."""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

import cv2
import numpy as np
import numpy.typing as npt

from backend.models.color import (
    ColorAnalysisData,
    LABColor,
    RGBColor,
    RoiCoordinates,
)
from backend.models.common import ErrorCode
from backend.services.image_service import get_image_service
from backend.utils.errors import AppException

logger = logging.getLogger(__name__)

MIN_LUMA = 8.0
MAX_LUMA = 247.0
MIN_VALID_PIXEL_RATIO = 0.05


class ColorService:
    """Convert ROI pixels into normalized RGB, CIELAB, and HEX values."""

    def calculate_rgb(self, roi: npt.NDArray[np.uint8]) -> tuple[int, int, int]:
        """Return robust median RGB values from BGR ROI pixels.

        Clearly dark and bright pixels are removed when enough valid pixels
        remain. This avoids shadows and specular highlights dominating fabric
        color while preserving black and very light ROI samples.
        """
        if roi is None or roi.size == 0:
            raise AppException(
                message="ROI is empty",
                code=ErrorCode.INVALID_ROI,
                status_code=400,
            )

        rgb_pixels = self._to_rgb_pixels(roi)
        luminance = (
            rgb_pixels[:, 0] * 0.2126
            + rgb_pixels[:, 1] * 0.7152
            + rgb_pixels[:, 2] * 0.0722
        )
        usable_mask = (luminance >= MIN_LUMA) & (luminance <= MAX_LUMA)
        usable_pixels = rgb_pixels[usable_mask]

        if usable_pixels.size == 0:
            usable_pixels = rgb_pixels
        elif usable_pixels.shape[0] < max(
            1,
            int(rgb_pixels.shape[0] * MIN_VALID_PIXEL_RATIO),
        ):
            usable_pixels = rgb_pixels

        median = np.median(usable_pixels, axis=0)
        red, green, blue = np.clip(np.rint(median), 0, 255).astype(np.uint8)
        return int(red), int(green), int(blue)

    def calculate_lab(self, rgb: tuple[int, int, int]) -> tuple[float, float, float]:
        """Convert sRGB to standard CIELAB: L=0..100 and a/b around -128..127.

        OpenCV's 8-bit LAB output stores L as 0..255 and offsets a/b by 128.
        Those raw values must be converted before returning them to clients.
        """
        red, green, blue = self._validate_rgb(rgb)
        bgr_pixel = np.array([[[blue, green, red]]], dtype=np.uint8)
        opencv_lab = cv2.cvtColor(bgr_pixel, cv2.COLOR_BGR2LAB)[0, 0]

        lightness = float(opencv_lab[0]) * 100.0 / 255.0
        a_channel = float(opencv_lab[1]) - 128.0
        b_channel = float(opencv_lab[2]) - 128.0
        return (
            round(lightness, 2),
            round(a_channel, 2),
            round(b_channel, 2),
        )

    def rgb_to_hex(self, rgb: tuple[int, int, int]) -> str:
        red, green, blue = self._validate_rgb(rgb)
        return f"#{red:02X}{green:02X}{blue:02X}"

    def analyze_roi(
        self,
        image: npt.NDArray[np.uint8],
        x: int,
        y: int,
        width: int,
        height: int,
        **options: Any,
    ) -> ColorAnalysisData:
        del options
        image_service = get_image_service()
        roi_pixels = image_service.crop_roi(
            image,
            x,
            y,
            width,
            height,
        )

        rgb = self.calculate_rgb(roi_pixels)
        lab = self.calculate_lab(rgb)
        hex_value = self.rgb_to_hex(rgb)
        logger.info(
            "ROI analysis success: roi=(%d,%d,%d,%d) rgb=%s hex=%s",
            x,
            y,
            width,
            height,
            rgb,
            hex_value,
        )

        return ColorAnalysisData(
            rgb=RGBColor(r=rgb[0], g=rgb[1], b=rgb[2]),
            lab=LABColor(l=lab[0], a=lab[1], b=lab[2]),
            hex=hex_value,
            roi=RoiCoordinates(
                x=x,
                y=y,
                width=width,
                height=height,
            ),
        )

    @staticmethod
    def _to_rgb_pixels(
        roi: npt.NDArray[np.uint8],
    ) -> npt.NDArray[np.float64]:
        try:
            rgb_image = cv2.cvtColor(roi, cv2.COLOR_BGR2RGB)
        except cv2.error as exc:
            logger.exception("ROI could not be converted from BGR to RGB")
            raise AppException(
                message="ROI image format is unsupported",
                code=ErrorCode.COLOR_ANALYSIS_FAILED,
                status_code=422,
            ) from exc
        return rgb_image.reshape(-1, 3).astype(np.float64)

    @staticmethod
    def _validate_rgb(rgb: tuple[int, int, int]) -> tuple[int, int, int]:
        if len(rgb) != 3 or any(value < 0 or value > 255 for value in rgb):
            raise AppException(
                message="RGB values must be between 0 and 255",
                code=ErrorCode.COLOR_ANALYSIS_FAILED,
                status_code=422,
            )
        return int(rgb[0]), int(rgb[1]), int(rgb[2])


@lru_cache(maxsize=1)
def get_color_service() -> ColorService:
    """Return the process-wide color service."""
    return ColorService()
