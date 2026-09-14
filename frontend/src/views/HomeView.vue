<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import CameraView from "@/components/CameraView.vue";
import CapturePanel from "@/components/CapturePanel.vue";
import ColorResult from "@/components/ColorResult.vue";
import RoiSelector from "@/components/RoiSelector.vue";
import { captureFrame } from "@/services/camera";
import { analyzeRoi } from "@/services/color";
import { apiClient, getApiErrorMessage } from "@/services/api";
import { uploadResult as sendUpload } from "@/services/upload";
import type { ApiResponse } from "@/types/api";
import type { CameraStatus, CaptureResult } from "@/types/camera";
import type {
  ColorAnalysisResult,
  RoiCoordinates,
} from "@/types/color";
import type { AppConfig } from "@/types/config";
import type { UploadResult } from "@/types/upload";

interface CameraViewHandle {
  restartPreview: () => void;
}

const camera = ref<CameraViewHandle | null>(null);
const cameraStatus = ref<CameraStatus | null>(null);
const capture = ref<CaptureResult | null>(null);
const capturedImageBlob = ref<Blob | null>(null);
const roi = ref<RoiCoordinates | null>(null);
const colorResult = ref<ColorAnalysisResult | null>(null);
const frozen = ref(false);
const capturing = ref(false);
const analyzing = ref(false);
const uploading = ref(false);
const uploadState = ref<UploadResult | null>(null);
const config = ref<AppConfig | null>(null);
const errorMessage = ref("");

const cameraReady = computed(() => Boolean(cameraStatus.value?.opened));
const workflowState = computed(() => {
  if (frozen.value) {
    return "已拍照";
  }
  return cameraReady.value ? "实时预览" : "设备未连接";
});

function handleCameraStatus(status: CameraStatus): void {
  cameraStatus.value = status;
}

async function handleCapture(): Promise<void> {
  capturing.value = true;
  errorMessage.value = "";
  try {
    const result = await captureFrame();
    const response = await fetch(result.image_url);
    if (!response.ok) {
      throw new Error("拍摄图片无法加载");
    }
    capturedImageBlob.value = await response.blob();
    capture.value = result;
    colorResult.value = null;
    uploadState.value = null;
    frozen.value = true;
    roi.value = null;
  } catch (error) {
    errorMessage.value = getApiErrorMessage(error);
  } finally {
    capturing.value = false;
  }
}

function resetCapture(): void {
  capture.value = null;
  capturedImageBlob.value = null;
  roi.value = null;
  colorResult.value = null;
  uploadState.value = null;
  frozen.value = false;
  errorMessage.value = "";
  camera.value?.restartPreview();
}

function handleRoiChange(nextRoi: RoiCoordinates | null): void {
  roi.value = nextRoi;
  colorResult.value = null;
  uploadState.value = null;
}

async function handleRoiConfirm(nextRoi: RoiCoordinates): Promise<void> {
  roi.value = nextRoi;
  if (!capturedImageBlob.value) {
    errorMessage.value = "拍摄图片尚未准备好";
    return;
  }

  analyzing.value = true;
  errorMessage.value = "";
  try {
    colorResult.value = await analyzeRoi(capturedImageBlob.value, nextRoi);
    if (config.value?.auto_upload) {
      await handleUpload();
    }
  } catch (error) {
    colorResult.value = null;
    errorMessage.value = getApiErrorMessage(error);
  } finally {
    analyzing.value = false;
  }
}

async function handleUpload(): Promise<void> {
  if (
    !capturedImageBlob.value ||
    !capture.value ||
    !colorResult.value ||
    !config.value
  ) {
    errorMessage.value = "上传所需的图片、颜色结果或配置不完整";
    return;
  }

  uploading.value = true;
  errorMessage.value = "";
  try {
    const roiImage = await createRoiImage(
      capturedImageBlob.value,
      colorResult.value.roi,
    );
    uploadState.value = await sendUpload({
      originalImage: capturedImageBlob.value,
      roiImage,
      result: colorResult.value,
      cameraId: config.value.camera_id,
      timestamp: capture.value.captured_at,
      timeoutMs: config.value.timeout * 1000 + 2_000,
    });
  } catch (error) {
    uploadState.value = null;
    errorMessage.value = getApiErrorMessage(error);
  } finally {
    uploading.value = false;
  }
}

async function createRoiImage(
  source: Blob,
  roi: RoiCoordinates,
): Promise<Blob> {
  const bitmap = await createImageBitmap(source);
  try {
    const canvas = document.createElement("canvas");
    canvas.width = roi.width;
    canvas.height = roi.height;
    const context = canvas.getContext("2d");
    if (!context) {
      throw new Error("浏览器无法创建 ROI 图片");
    }
    context.drawImage(
      bitmap,
      roi.x,
      roi.y,
      roi.width,
      roi.height,
      0,
      0,
      roi.width,
      roi.height,
    );
    const blob = await new Promise<Blob | null>((resolve) => {
      canvas.toBlob(resolve, "image/jpeg", 0.92);
    });
    if (!blob) {
      throw new Error("ROI 图片编码失败");
    }
    return blob;
  } finally {
    bitmap.close();
  }
}

async function loadConfig(): Promise<void> {
  try {
    const response =
      await apiClient.get<ApiResponse<AppConfig>>("/config");
    config.value = response.data.data;
  } catch (error) {
    errorMessage.value = getApiErrorMessage(error);
  }
}

onMounted(loadConfig);
</script>

<template>
  <div class="home-view">
    <div class="page-heading">
      <div>
        <h1>颜色采集工作台</h1>
        <p>实时采集与 ROI 颜色分析</p>
      </div>
      <span class="workflow-state">{{ workflowState }}</span>
    </div>

    <p v-if="errorMessage" class="workflow-error" role="alert">
      {{ errorMessage }}
    </p>

    <div class="workspace-grid">
      <CameraView
        ref="camera"
        class="camera-area"
        :frozen="frozen"
        :captured-image-url="capture?.image_url"
        @status-change="handleCameraStatus"
        @error="errorMessage = $event"
      />
      <CapturePanel
        class="capture-area"
        :camera-ready="cameraReady"
        :has-capture="Boolean(capture)"
        :capturing="capturing"
        @capture="handleCapture"
        @retake="resetCapture"
      />
      <RoiSelector
        class="roi-area"
        :image-url="capture?.image_url"
        :disabled="!capturedImageBlob"
        :analysis-pending="analyzing"
        @change="handleRoiChange"
        @confirm="handleRoiConfirm"
      />
      <ColorResult
        class="result-area"
        :result="colorResult"
        :analysis-pending="analyzing"
        :uploading="uploading"
        :can-upload="Boolean(colorResult && capturedImageBlob && config)"
        :upload-result="uploadState"
        @upload="handleUpload"
      />
    </div>
  </div>
</template>

<style scoped>
.workflow-state {
  padding: 7px 11px;
  border: 1px solid var(--border);
  border-radius: 999px;
  color: var(--text-muted);
  background: var(--surface);
  font-size: 0.82rem;
  white-space: nowrap;
}

.workflow-error {
  margin: 0 0 16px;
  padding: 10px 12px;
  border: 1px solid rgba(182, 65, 55, 0.32);
  border-radius: 6px;
  color: var(--danger);
  background: rgba(182, 65, 55, 0.06);
}

.workspace-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(340px, 0.65fr);
  gap: 18px;
  align-items: start;
}

.camera-area {
  grid-column: 1;
}

.capture-area {
  grid-column: 2;
}

.roi-area {
  grid-column: 1;
}

.result-area {
  grid-column: 2;
}

@media (max-width: 960px) {
  .workspace-grid {
    grid-template-columns: 1fr;
  }

  .camera-area,
  .capture-area,
  .roi-area,
  .result-area {
    grid-column: 1;
  }
}
</style>
