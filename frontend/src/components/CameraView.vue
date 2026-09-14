<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";

import {
  closeCamera,
  detectCamera,
  getCameraStatus,
  listCameras,
  reconnectCamera,
  useMockCamera,
} from "@/services/camera";
import { getApiErrorDetails } from "@/services/api";
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
const streamSession = ref(0);
const streamFailed = ref(false);

let statusPollTimer: number | null = null;

const cameraFeedActive = computed(
  () =>
    status.value.opened &&
    (status.value.state === "available" || status.value.state === "mock"),
);

const streamUrl = computed(() => {
  if (!cameraFeedActive.value || props.frozen || streamFailed.value) {
    return "";
  }
  return `/api/camera/stream?session=${streamSession.value}`;
});

const displayImageUrl = computed(() => {
  if (props.frozen && props.capturedImageUrl) {
    return props.capturedImageUrl;
  }
  return streamUrl.value;
});

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
  if (
    nextStatus.opened &&
    (nextStatus.state === "available" || nextStatus.state === "mock")
  ) {
    streamFailed.value = false;
    streamSession.value += 1;
  }
  emit("statusChange", nextStatus);
}

function handleCameraError(error: unknown): void {
  const details = getApiErrorDetails(error);
  const stateByCode: Partial<Record<string, CameraState>> = {
    CAMERA_NOT_FOUND: "not_found",
    CAMERA_OPEN_FAILED: "open_failed",
    CAMERA_DEVICE_BUSY: "busy",
    CAMERA_DISCONNECTED: "disconnected",
    CAMERA_READ_FAILED: "read_failed",
  };
  const state = (details.code && stateByCode[details.code]) || "open_failed";
  updateStatus(createStatus(state, details.message, details.code));
}

async function runCameraOperation(
  operation: () => Promise<CameraStatus>,
  refreshDeviceList = true,
): Promise<void> {
  if (busy.value) {
    return;
  }

  busy.value = true;
  try {
    const nextStatus = await operation();
    updateStatus(nextStatus);
    if (refreshDeviceList) {
      await loadCameraList();
    }
  } catch (error) {
    handleCameraError(error);
  } finally {
    busy.value = false;
  }
}

async function loadCameraList(): Promise<void> {
  try {
    const listed = await listCameras();
    cameras.value = listed.cameras;
  } catch {
    cameras.value = [];
  }
}

async function detectSelected(): Promise<void> {
  await runCameraOperation(detectCamera);
}

async function reconnectSelected(): Promise<void> {
  await runCameraOperation(() => reconnectCamera(selectedIndex.value));
}

async function openSelected(): Promise<void> {
  await reconnectSelected();
}

async function switchToMock(): Promise<void> {
  await runCameraOperation(useMockCamera, false);
}

async function switchToReal(): Promise<void> {
  await runCameraOperation(() => reconnectCamera(selectedIndex.value));
}

async function closeSelected(): Promise<void> {
  await runCameraOperation(closeCamera, false);
}

async function syncStatus(): Promise<void> {
  try {
    const nextStatus = await getCameraStatus();
    if (
      nextStatus.opened &&
      (nextStatus.state === "available" || nextStatus.state === "mock")
    ) {
      status.value = nextStatus;
      emit("statusChange", nextStatus);
      return;
    }
    updateStatus(nextStatus);
  } catch {
    // The health indicator reports local service failures.
  }
}

function restartPreview(): void {
  streamFailed.value = false;
  streamSession.value += 1;
}

function handleStreamError(): void {
  if (!cameraFeedActive.value || props.frozen) {
    return;
  }
  streamFailed.value = true;
  updateStatus({
    ...status.value,
    state: "disconnected",
    opened: false,
    available: false,
    message: "实时画面连接中断",
    code: "CAMERA_DISCONNECTED",
  });
  void syncStatus();
}

onMounted(async () => {
  await detectSelected();
  statusPollTimer = window.setInterval(() => {
    if (cameraFeedActive.value) {
      void syncStatus();
    }
  }, 2_000);
});

onBeforeUnmount(() => {
  if (statusPollTimer !== null) {
    window.clearInterval(statusPollTimer);
  }
  if (cameraFeedActive.value) {
    void closeCamera();
  }
});

defineExpose({
  restartPreview,
  closeSelected,
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
      <img
        v-if="displayImageUrl"
        :src="displayImageUrl"
        class="camera-image"
        alt="摄像头实时画面"
        @error="handleStreamError"
      />
      <div v-else class="camera-empty">
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
            v-if="streamFailed && cameraFeedActive"
            class="button compact"
            type="button"
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
