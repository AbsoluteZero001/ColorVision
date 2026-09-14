export type CameraState =
  | "initializing"
  | "available"
  | "not_found"
  | "open_failed"
  | "busy"
  | "disconnected"
  | "read_failed"
  | "mock"
  | "closed";

export type CameraSourceType = "real" | "mock";

export interface CameraInfo {
  index: number;
  name: string;
  available: boolean;
}

export interface CameraListData {
  cameras: CameraInfo[];
  state: CameraState;
  message: string | null;
  code: string | null;
}

export interface CameraStatus {
  state: CameraState;
  source: CameraSourceType | null;
  camera_id: string | null;
  opened: boolean;
  index: number | null;
  name: string | null;
  available: boolean;
  width: number | null;
  height: number | null;
  fps: number | null;
  message: string | null;
  code: string | null;
}

export interface CaptureResult {
  image_path: string;
  image_url: string;
  captured_at: string;
}
