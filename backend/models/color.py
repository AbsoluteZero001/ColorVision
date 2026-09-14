"""Color-analysis API models."""

from pydantic import BaseModel, ConfigDict, Field


class RGBColor(BaseModel):
    """8-bit sRGB channel values."""

    model_config = ConfigDict(extra="forbid")

    r: int = Field(ge=0, le=255)
    g: int = Field(ge=0, le=255)
    b: int = Field(ge=0, le=255)


class LABColor(BaseModel):
    """CIELAB values normalized to the standard output convention."""

    model_config = ConfigDict(extra="forbid")

    l: float = Field(ge=0.0, le=100.0)
    a: float
    b: float


class RoiCoordinates(BaseModel):
    """ROI rectangle in original-image pixel coordinates."""

    model_config = ConfigDict(extra="forbid")

    x: int = Field(ge=0)
    y: int = Field(ge=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)


class ColorAnalysisData(BaseModel):
    """Color analysis result returned to the frontend."""

    model_config = ConfigDict(extra="forbid")

    rgb: RGBColor
    lab: LABColor
    hex: str
    roi: RoiCoordinates
