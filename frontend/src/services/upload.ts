import { apiClient } from "./api";

import type { ApiResponse } from "@/types/api";
import type { ColorAnalysisResult } from "@/types/color";
import type { UploadResult } from "@/types/upload";

export interface UploadPayload {
  originalImage: Blob;
  roiImage: Blob;
  result: ColorAnalysisResult;
  cameraId: string;
  timestamp: string;
  timeoutMs?: number;
}

export async function uploadResult(
  payload: UploadPayload,
): Promise<UploadResult> {
  const formData = new FormData();
  formData.append("original_image", payload.originalImage, "original.jpg");
  formData.append("roi_image", payload.roiImage, "roi.jpg");
  formData.append("rgb", JSON.stringify(payload.result.rgb));
  formData.append("lab", JSON.stringify(payload.result.lab));
  formData.append("hex", payload.result.hex);
  formData.append("roi", JSON.stringify(payload.result.roi));
  formData.append("camera_id", payload.cameraId);
  formData.append("timestamp", payload.timestamp);

  const response = await apiClient.post<ApiResponse<UploadResult>>(
    "/upload",
    formData,
    {
      timeout: payload.timeoutMs ?? 12_000,
    },
  );
  return response.data.data;
}
