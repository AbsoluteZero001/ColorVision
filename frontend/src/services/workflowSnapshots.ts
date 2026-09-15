import type { CaptureResult } from "../types/camera";
import type { ColorAnalysisResult, RoiCoordinates } from "../types/color";
import type { AppConfig } from "../types/config";

export interface RecognitionSnapshot {
  image: Blob;
  roi: RoiCoordinates;
}

export interface UploadSnapshot {
  originalImage: Blob;
  result: ColorAnalysisResult;
  cameraId: string;
  timestamp: string;
  timeoutMs: number;
}

function cloneRoi(roi: RoiCoordinates): RoiCoordinates {
  return {
    x: roi.x,
    y: roi.y,
    width: roi.width,
    height: roi.height,
  };
}

function cloneResult(result: ColorAnalysisResult): ColorAnalysisResult {
  return {
    rgb: { ...result.rgb },
    lab: { ...result.lab },
    hex: result.hex,
    roi: cloneRoi(result.roi),
  };
}

export function createRecognitionSnapshot(
  image: Blob,
  roi: RoiCoordinates,
): RecognitionSnapshot {
  return {
    image,
    roi: cloneRoi(roi),
  };
}

export function createUploadSnapshot(
  originalImage: Blob,
  capture: CaptureResult,
  result: ColorAnalysisResult,
  config: AppConfig,
): UploadSnapshot {
  return {
    originalImage,
    result: cloneResult(result),
    cameraId: config.camera_id,
    timestamp: capture.captured_at,
    timeoutMs: config.timeout * 1000 + 2_000,
  };
}
