export interface CameraInfo {
  index: number;
  name: string;
  available: boolean;
}

export interface CameraListData {
  cameras: CameraInfo[];
}

export interface CameraStatus {
  opened: boolean;
  index: number | null;
  name: string | null;
  available: boolean;
  width: number | null;
  height: number | null;
  fps: number | null;
}

export interface CaptureResult {
  image_path: string;
  image_url: string;
  captured_at: string;
}
