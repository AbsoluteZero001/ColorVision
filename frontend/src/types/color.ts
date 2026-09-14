export interface RoiCoordinates {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface RgbColor {
  r: number;
  g: number;
  b: number;
}

export interface LabColor {
  l: number;
  a: number;
  b: number;
}

export interface ColorAnalysisResult {
  rgb: RgbColor;
  lab: LabColor;
  hex: string;
  roi: RoiCoordinates;
}
