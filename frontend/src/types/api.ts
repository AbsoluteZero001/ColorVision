export interface ApiResponse<T> {
  success: true;
  data: T;
  message?: string | null;
  code?: string | null;
}

export interface ApiError {
  success: false;
  data: null;
  message: string;
  code: string;
}
