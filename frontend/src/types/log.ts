import type { LabColor, RgbColor, RoiCoordinates } from "./color";

export interface UploadLogEntry {
  id: number;
  uploaded_at: string;
  uploaded_at_beijing: string;
  captured_at: string;
  camera_id: string;
  rgb: RgbColor;
  lab: LabColor;
  hex: string;
  roi: RoiCoordinates;
  upload_mode: "mock" | "api";
  request_id: string;
  message: string;
  original_image_url: string | null;
  roi_image_url: string | null;
}

export interface UploadLogPage {
  items: UploadLogEntry[];
  total: number;
  limit: number;
  offset: number;
}

export interface UploadLogDeleteResult {
  deleted: number;
}
