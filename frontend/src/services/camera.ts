import { apiClient } from "./api";

import type { ApiResponse } from "@/types/api";
import type {
  CameraListData,
  CameraStatus,
  CaptureResult,
} from "@/types/camera";

export async function listCameras(): Promise<CameraListData> {
  const response = await apiClient.get<ApiResponse<CameraListData>>(
    "/camera/list",
  );
  return response.data.data;
}

export async function getCameraStatus(): Promise<CameraStatus> {
  const response = await apiClient.get<ApiResponse<CameraStatus>>(
    "/camera/status",
  );
  return response.data.data;
}

export async function detectCamera(): Promise<CameraStatus> {
  const response =
    await apiClient.post<ApiResponse<CameraStatus>>("/camera/detect");
  return response.data.data;
}

export async function reconnectCamera(
  index: number | null = null,
): Promise<CameraStatus> {
  const response = await apiClient.post<ApiResponse<CameraStatus>>(
    "/camera/reconnect",
    index === null ? undefined : { index },
  );
  return response.data.data;
}

export async function useMockCamera(): Promise<CameraStatus> {
  const response =
    await apiClient.post<ApiResponse<CameraStatus>>("/camera/mock");
  return response.data.data;
}

export async function openCamera(index: number): Promise<CameraStatus> {
  const response = await apiClient.post<ApiResponse<CameraStatus>>(
    "/camera/open",
    { index },
  );
  return response.data.data;
}

export async function closeCamera(): Promise<CameraStatus> {
  const response = await apiClient.post<ApiResponse<CameraStatus>>(
    "/camera/close",
  );
  return response.data.data;
}

export async function captureFrame(): Promise<CaptureResult> {
  const response =
    await apiClient.post<ApiResponse<CaptureResult>>("/camera/capture");
  return response.data.data;
}
