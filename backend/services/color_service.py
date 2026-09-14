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
MAD_SCALE_FACTOR = 1.4826
OUTLIER_SIGMA_LIMIT = 3.0
MIN_INLIER_PIXEL_RATIO = 0.1


class ColorService:
    """Convert ROI pixels into normalized RGB, CIELAB, and HEX values."""

    def calculate_rgb(self, roi: npt.NDArray[np.uint8]) -> tuple[int, int, int]:
        """Return robust RGB values from BGR ROI pixels.

        Clearly dark and bright pixels are removed when enough valid pixels
        remain. A median/MAD filter then removes per-channel outliers before
        averaging the remaining pixels. This improves repeatability without
        changing the measured color through software white balance or gain.
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

        estimate = self._robust_rgb(usable_pixels)
        red, green, blue = np.clip(np.rint(estimate), 0, 255).astype(np.uint8)
        return int(red), int(green), int(blue)

    def calculate_lab(self, rgb: tuple[int, int, int]) -> tuple[float, float, float]:
        """Convert sRGB to standard CIELAB: L=0..100 and a/b around -128..127.

        The sRGB value is converted as float32 rather than quantized uint8 LAB
        to avoid OpenCV's 8-bit offset/scale conversion error.
        """
        red, green, blue = self._validate_rgb(rgb)
        bgr_pixel = (
            np.array([[[blue, green, red]]], dtype=np.float32) / 255.0
        )
        lab = cv2.cvtColor(bgr_pixel, cv2.COLOR_BGR2LAB)[0, 0]
        return (
            round(float(lab[0]), 2),
            round(float(lab[1]), 2),
            round(float(lab[2]), 2),
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
    def _robust_rgb(
        pixels: npt.NDArray[np.float64],
    ) -> npt.NDArray[np.float64]:
        """Estimate RGB with a median/MAD inlier filter."""
        median = np.median(pixels, axis=0)
        deviations = np.abs(pixels - median)
        mad = np.median(deviations, axis=0) * MAD_SCALE_FACTOR
        robust_scale = np.maximum(mad, 1.0)
        inlier_mask = np.all(
            deviations <= OUTLIER_SIGMA_LIMIT * robust_scale,
            axis=1,
        )
        inliers = pixels[inlier_mask]

        minimum_inliers = max(
            1,
            int(pixels.shape[0] * MIN_INLIER_PIXEL_RATIO),
        )
        if inliers.shape[0] < minimum_inliers:
            return median
        return np.mean(inliers, axis=0)

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
