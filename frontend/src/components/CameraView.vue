<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from "vue";

import type {
  CameraInfo,
  CameraState,
  CameraStatus,
} from "@/types/camera";

const props = withDefaults(
  defineProps<{
    frozen?: boolean;
    capturedImageUrl?: string | null;
  }>(),
  {
    frozen: false,
    capturedImageUrl: null,
  },
);

const emit = defineEmits<{
  statusChange: [status: CameraStatus];
}>();

const cameras = ref<CameraInfo[]>([]);
const selectedIndex = ref<number | null>(null);
const status = ref<CameraStatus>(
  createStatus("initializing", "摄像头服务初始化中"),
);
const busy = ref(false);

const videoRef = ref<HTMLVideoElement | null>(null);
let mediaStream: MediaStream | null = null;

const cameraFeedActive = computed(
  () =>
    status.value.opened &&
    (status.value.state === "available" || status.value.state === "mock"),
);

const resolutionText = computed(() => {
  if (!cameraFeedActive.value) {
    return status.value.name || "未连接";
  }
  if (!status.value.width || !status.value.height) {
    return "分辨率读取中";
  }
  return `${status.value.width} × ${status.value.height}`;
});

const statusTitle = computed(() => {
  const titles: Record<CameraState, string> = {
    initializing: "正在初始化摄像头",
    available: "摄像头已连接",
    not_found: "未检测到可用摄像头",
    open_failed: "摄像头打开失败",
    busy: "摄像头可能正在被其他程序使用",
    disconnected: "摄像头已断开",
    read_failed: "无法读取摄像头画面",
    mock: "Mock Camera",
    closed: "摄像头未连接",
  };
  return titles[status.value.state];
});

const statusDetail = computed(() => {
  if (status.value.state === "available") {
    return `Camera ID: ${status.value.camera_id || "CAM-001"}`;
  }
  if (status.value.state === "mock") {
    return "Camera ID: MOCK-CAMERA";
  }
  if (status.value.state === "not_found") {
    return "请连接摄像头后重新检测，或使用 Mock 模式继续体验。";
  }
  if (status.value.state === "open_failed") {
    return "请检查摄像头占用、驱动状态和设备连接。";
  }
  if (status.value.state === "busy") {
    return "请关闭相机、会议软件等可能占用摄像头的程序。";
  }
  if (status.value.state === "disconnected" || status.value.state === "read_failed") {
    return status.value.message || "请重新连接摄像头，或切换到 Mock 模式。";
  }
  return status.value.message || "等待摄像头状态更新";
});

const canRetry = computed(
  () =>
    status.value.state !== "available" &&
    status.value.state !== "mock" &&
    status.value.state !== "initializing",
);

const canUseMock = computed(
  () => status.value.state !== "mock" && status.value.state !== "initializing",
);

const retryLabel = computed(() =>
  status.value.state === "disconnected" ? "重新连接" : "重新检测",
);

const showLiveVideo = computed(
  () => cameraFeedActive.value && !props.frozen,
);

const showFrozenImage = computed(
  () => props.frozen && Boolean(props.capturedImageUrl),
);

const showEmptyState = computed(
  () => !showLiveVideo.value && !showFrozenImage.value,
);

function createStatus(
  state: CameraState,
  message: string | null = null,
  code: string | null = null,
): CameraStatus {
  return {
    state,
    source: null,
    camera_id: null,
    opened: false,
    index: null,
    name: null,
    available: false,
    width: null,
    height: null,
    fps: null,
    message,
    code,
  };
}

function updateStatus(nextStatus: CameraStatus): void {
  status.value = nextStatus;
  if (nextStatus.index !== null) {
    selectedIndex.value = nextStatus.index;
  }
  emit("statusChange", nextStatus);
}

function handleCameraError(error: unknown): void {
  let state: CameraState = "open_failed";
  let message = "摄像头打开失败";
  let code = "CAMERA_OPEN_FAILED";

  if (error instanceof DOMException) {
    if (error.name === "NotAllowedError" || error.name === "SecurityError") {
      state = "open_failed";
      message = "摄像头权限被拒绝，请在浏览器设置中允许访问摄像头";
      code = "CAMERA_OPEN_FAILED";
    } else if (
      error.name === "NotFoundError" ||
      error.name === "OverconstrainedError" ||
      error.name === "DevicesNotFoundError"
    ) {
      state = "not_found";
      message = "未检测到可用摄像头";
      code = "CAMERA_NOT_FOUND";
    } else if (error.name === "NotReadableError") {
      state = "busy";
      message = "摄像头可能正在被其他程序使用";
      code = "CAMERA_DEVICE_BUSY";
    } else if (error.name === "AbortError") {
      state = "open_failed";
      message = "摄像头启动被中断";
      code = "CAMERA_OPEN_FAILED";
    } else {
      message = error.message || message;
    }
  } else if (error instanceof Error) {
    message = error.message;
  }

  updateStatus(createStatus(state, message, code));
}

function stopStream(): void {
  if (mediaStream) {
    mediaStream.getTracks().forEach((track) => {
      track.onended = null;
      track.stop();
    });
    mediaStream = null;
  }
  const video = videoRef.value;
  if (video) {
    video.srcObject = null;
  }
}

async function listBrowserCameras(): Promise<void> {
  try {
    if (!navigator.mediaDevices?.enumerateDevices) {
      cameras.value = [];
      return;
    }
    const devices = await navigator.mediaDevices.enumerateDevices();
    const videoDevices = devices.filter((d) => d.kind === "videoinput");
    cameras.value = videoDevices.map((device, index) => ({
      index,
      name: device.label || `Camera ${index + 1}`,
      available: true,
    }));
  } catch {
    cameras.value = [];
  }
}

async function openBrowserCamera(deviceIndex: number | null): Promise<void> {
  if (busy.value) {
    return;
  }
  if (!navigator.mediaDevices?.getUserMedia) {
    updateStatus(
      createStatus(
        "not_found",
        "当前浏览器不支持摄像头访问，请使用 HTTPS 或 localhost 访问",
        "CAMERA_NOT_FOUND",
      ),
    );
    return;
  }

  busy.value = true;
  stopStream();

  try {
    const constraints: MediaStreamConstraints = { video: true };
    if (deviceIndex !== null) {
      const devices = await navigator.mediaDevices.enumerateDevices();
      const videoDevices = devices.filter((d) => d.kind === "videoinput");
      const target = videoDevices[deviceIndex];
      if (target?.deviceId) {
        constraints.video = { deviceId: { exact: target.deviceId } };
      }
    }

    const stream = await navigator.mediaDevices.getUserMedia(constraints);
    mediaStream = stream;

    const videoTrack = stream.getVideoTracks()[0];
    const settings = videoTrack ? videoTrack.getSettings() : {};
    videoTrack.onended = () => {
      if (!mediaStream) {
        return;
      }
      updateStatus({
        ...status.value,
        state: "disconnected",
        opened: false,
        available: false,
        message: "摄像头已断开",
        code: "CAMERA_DISCONNECTED",
      });
    };

    updateStatus({
      state: "available",
      source: "real",
      camera_id: "CAM-001",
      opened: true,
      index: deviceIndex ?? 0,
      name: videoTrack?.label || "Browser Camera",
      available: true,
      width: settings.width ?? null,
      height: settings.height ?? null,
      fps: settings.frameRate ?? null,
      message: null,
      code: null,
    });

    await nextTick();
    const video = videoRef.value;
    if (video) {
      video.srcObject = stream;
      try {
        await video.play();
      } catch {
        // Autoplay may be rejected by the browser; the video element still renders frames.
      }
    }

    await listBrowserCameras();
  } catch (error) {
    handleCameraError(error);
  } finally {
    busy.value = false;
  }
}

async function detectSelected(): Promise<void> {
  await openBrowserCamera(null);
}

async function reconnectSelected(): Promise<void> {
  await openBrowserCamera(selectedIndex.value);
}

async function openSelected(): Promise<void> {
  await reconnectSelected();
}

async function switchToMock(): Promise<void> {
  if (busy.value) {
    return;
  }
  stopStream();
  updateStatus({
    state: "mock",
    source: "mock",
    camera_id: "MOCK-CAMERA",
    opened: true,
    index: null,
    name: "Mock Camera",
    available: true,
    width: null,
    height: null,
    fps: null,
    message: "Mock 模式在浏览器部署下不提供实时画面",
    code: null,
  });
  await listBrowserCameras();
}

async function switchToReal(): Promise<void> {
  await reconnectSelected();
}

async function closeSelected(): Promise<void> {
  if (busy.value) {
    return;
  }
  busy.value = true;
  try {
    stopStream();
    updateStatus(createStatus("closed", "摄像头已关闭"));
  } finally {
    busy.value = false;
  }
}

async function restartPreview(): Promise<void> {
  await detectSelected();
}

async function captureFrame(): Promise<Blob> {
  const video = videoRef.value;
  if (!video || !video.videoWidth || !video.videoHeight) {
    throw new Error("摄像头画面尚未就绪");
  }
  const canvas = document.createElement("canvas");
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  const context = canvas.getContext("2d");
  if (!context) {
    throw new Error("浏览器无法创建画面快照");
  }
  context.drawImage(video, 0, 0, canvas.width, canvas.height);
  const blob = await new Promise<Blob | null>((resolve) => {
    canvas.toBlob(resolve, "image/jpeg", 0.92);
  });
  if (!blob) {
    throw new Error("画面编码失败");
  }
  return blob;
}

onMounted(async () => {
  await detectSelected();
});

onBeforeUnmount(() => {
  stopStream();
});

defineExpose({
  restartPreview,
  closeSelected,
  captureFrame,
});
</script>

<template>
  <section class="panel camera-panel">
    <div class="panel-header camera-toolbar">
      <div>
        <h2>实时画面</h2>
        <span class="muted">{{ resolutionText }}</span>
      </div>
      <div class="camera-controls">
        <button
          v-if="status.state === 'mock'"
          class="button secondary compact"
          type="button"
          :disabled="busy"
          @click="switchToReal"
        >
          切换真实摄像头
        </button>
        <select
          v-if="!cameraFeedActive && cameras.length > 0"
          v-model="selectedIndex"
          :disabled="busy"
          aria-label="摄像头"
        >
          <option
            v-for="camera in cameras"
            :key="camera.index"
            :value="camera.index"
          >
            {{ camera.name }}
          </option>
        </select>
        <button
          v-if="!cameraFeedActive && cameras.length > 0"
          class="button compact"
          type="button"
          :disabled="busy || selectedIndex === null"
          @click="openSelected"
        >
          {{ busy ? "连接中" : "打开" }}
        </button>
        <button
          v-else-if="cameraFeedActive"
          class="button secondary compact"
          type="button"
          :disabled="busy"
          @click="closeSelected"
        >
          关闭
        </button>
      </div>
    </div>

    <div class="camera-status" :class="status.state" role="status">
      <span class="camera-status-dot" aria-hidden="true"></span>
      <span>
        <strong>{{ statusTitle }}</strong>
        <small>{{ statusDetail }}</small>
      </span>
      <span v-if="status.code" class="camera-status-code">
        {{ status.code }}
      </span>
    </div>

    <div class="camera-stage" aria-label="摄像头预览区域">
      <video
        v-show="showLiveVideo"
        ref="videoRef"
        class="camera-image"
        autoplay
        playsinline
        muted
        aria-label="摄像头实时画面"
      ></video>
      <img
        v-if="showFrozenImage"
        :src="props.capturedImageUrl ?? ''"
        class="camera-image"
        alt="拍摄图片"
      />
      <div v-if="showEmptyState" class="camera-empty">
        <span>{{ status.state === "mock" ? "MOCK" : "LIVE" }}</span>
        <strong>{{ props.frozen ? "已冻结拍摄画面" : statusTitle }}</strong>
        <p>{{ statusDetail }}</p>
        <div class="camera-state-actions">
          <button
            v-if="canRetry"
            class="button compact"
            type="button"
            :disabled="busy"
            @click="retryLabel === '重新连接' ? reconnectSelected() : detectSelected()"
          >
            {{ busy ? "处理中" : retryLabel }}
          </button>
          <button
            v-if="canUseMock"
            class="button secondary compact"
            type="button"
            :disabled="busy"
            @click="switchToMock"
          >
            使用 Mock 模式
          </button>
          <button
            v-if="status.state === 'disconnected'"
            class="button compact"
            type="button"
            :disabled="busy"
            @click="restartPreview"
          >
            重连画面
          </button>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.camera-toolbar {
  align-items: center;
}

.camera-toolbar > div:first-child {
  display: grid;
  gap: 3px;
}

.camera-controls {
  display: flex;
  align-items: center;
  gap: 8px;
}

.camera-controls select {
  min-width: 150px;
  min-height: 36px;
  padding: 0 9px;
  border: 1px solid var(--border);
  border-radius: 6px;
  color: var(--text);
  background: var(--surface);
}

.camera-status {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-bottom: 1px solid var(--border);
  color: var(--text-muted);
  background: var(--surface-muted);
}

.camera-status > span:nth-child(2) {
  display: grid;
  gap: 2px;
  min-width: 0;
}

.camera-status strong {
  color: var(--text);
  font-size: 0.88rem;
}

.camera-status small {
  overflow-wrap: anywhere;
}

.camera-status-dot {
  width: 9px;
  height: 9px;
  flex: 0 0 auto;
  border-radius: 50%;
  background: #98a3a1;
}

.camera-status.available .camera-status-dot,
.camera-status.mock .camera-status-dot {
  background: var(--success);
  box-shadow: 0 0 0 4px rgba(36, 122, 85, 0.12);
}

.camera-status.initializing .camera-status-dot {
  background: var(--warning);
}

.camera-status.not_found .camera-status-dot,
.camera-status.open_failed .camera-status-dot,
.camera-status.busy .camera-status-dot,
.camera-status.disconnected .camera-status-dot,
.camera-status.read_failed .camera-status-dot {
  background: var(--danger);
  box-shadow: 0 0 0 4px rgba(182, 65, 55, 0.1);
}

.camera-status-code {
  margin-left: auto;
  color: var(--text-muted);
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
  font-size: 0.68rem;
  white-space: nowrap;
}

.compact {
  min-height: 36px;
  padding: 0 13px;
}

.camera-stage {
  position: relative;
  display: grid;
  place-items: center;
  min-height: 320px;
  overflow: hidden;
  background:
    linear-gradient(rgba(255, 255, 255, 0.045) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255, 255, 255, 0.045) 1px, transparent 1px),
    #17201f;
  background-size: 28px 28px;
}

.camera-image {
  display: block;
  width: 100%;
  max-height: 68vh;
  object-fit: contain;
}

.camera-empty {
  display: grid;
  max-width: 560px;
  gap: 10px;
  justify-items: center;
  padding: 28px;
  color: #d8e3e1;
  text-align: center;
}

.camera-empty > span {
  color: #69d2c5;
  font-size: 0.72rem;
}

.camera-empty strong {
  font-size: 1rem;
}

.camera-empty p {
  margin: 0;
  color: #aebdbb;
  font-size: 0.86rem;
}

.camera-state-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 8px;
  margin-top: 4px;
}

@media (max-width: 620px) {
  .camera-toolbar {
    align-items: stretch;
    flex-direction: column;
  }

  .camera-controls {
    width: 100%;
  }

  .camera-controls select {
    flex: 1;
    min-width: 0;
  }

  .camera-status {
    align-items: flex-start;
  }

  .camera-status-code {
    display: none;
  }
}

@media (max-width: 760px) {
  .camera-stage {
    min-height: 260px;
  }
}
</style>
