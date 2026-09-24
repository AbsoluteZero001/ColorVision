<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";

import {
  captureFrame as captureMockFrame,
  closeCamera,
  useMockCamera,
} from "@/services/camera";
import type { CameraState, CameraStatus } from "@/types/camera";

interface BrowserCamera {
  deviceId: string;
  label: string;
}

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

const cameras = ref<BrowserCamera[]>([]);
const selectedDeviceId = ref<string>("");
const status = ref<CameraStatus>(
  createStatus("initializing", "摄像头服务初始化中"),
);
const busy = ref(false);

const videoRef = ref<HTMLVideoElement | null>(null);
let mediaStream: MediaStream | null = null;
let resizeObserver: ResizeObserver | null = null;

// 以下参数全部来自浏览器真实 API，未提供时保持空值，UI 显示 “--”
const sourceWidth = ref(0);
const sourceHeight = ref(0);
const frameRate = ref<number | null>(null);
const facingMode = ref<string | null>(null);
const capabilitiesText = ref("");
const previewWidth = ref(0);
const previewHeight = ref(0);

const isMobileDevice =
  /Android|iPhone|iPad|iPod|Mobile/i.test(navigator.userAgent) ||
  (navigator.maxTouchPoints > 1 && /Macintosh/i.test(navigator.userAgent));

const VIRTUAL_CAMERA_KEYWORDS = [
  "virtualcamera",
  "virtual camera",
  "obs virtual",
  "webcastmate",
  "manycam",
  "droidcam virtual",
  "xsplit",
];

function isVirtualCamera(label: string): boolean {
  const normalized = label.toLowerCase();
  return VIRTUAL_CAMERA_KEYWORDS.some((keyword) =>
    normalized.includes(keyword),
  );
}

const cameraFeedActive = computed(
  () =>
    status.value.opened &&
    (status.value.state === "available" || status.value.state === "mock"),
);

const resolutionText = computed(() => {
  if (!cameraFeedActive.value) {
    return status.value.name || "未连接";
  }
  if (!sourceWidth.value || !sourceHeight.value) {
    return "分辨率读取中";
  }
  return `${sourceWidth.value} × ${sourceHeight.value}`;
});

function gcd(a: number, b: number): number {
  return b === 0 ? a : gcd(b, a);
}

const deviceNameText = computed(() => status.value.name || "--");

const sourceSizeText = computed(() =>
  sourceWidth.value && sourceHeight.value
    ? `${sourceWidth.value} × ${sourceHeight.value} px`
    : "--",
);

const previewSizeText = computed(() =>
  previewWidth.value && previewHeight.value
    ? `${previewWidth.value} × ${previewHeight.value} px`
    : "--",
);

const fpsText = computed(() =>
  frameRate.value ? `${Math.round(frameRate.value)} FPS` : "--",
);

const aspectRatioText = computed(() => {
  if (!sourceWidth.value || !sourceHeight.value) {
    return "--";
  }
  const divisor = gcd(sourceWidth.value, sourceHeight.value);
  return `${sourceWidth.value / divisor}:${sourceHeight.value / divisor}`;
});

const facingText = computed(() => {
  if (facingMode.value === "environment") {
    return "后置";
  }
  if (facingMode.value === "user") {
    return "前置";
  }
  if (facingMode.value === "left" || facingMode.value === "right") {
    return facingMode.value;
  }
  return "未知";
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
  () => status.value.state === "available" && !props.frozen,
);

const showFrozenImage = computed(
  () => props.frozen && Boolean(props.capturedImageUrl),
);

const mockStreamFailed = ref(false);
const mockStreamSession = ref(0);

const mockStreamUrl = computed(() => {
  if (status.value.state !== "mock" || props.frozen || mockStreamFailed.value) {
    return "";
  }
  return `/api/camera/stream?session=${mockStreamSession.value}`;
});

const showEmptyState = computed(
  () =>
    !showLiveVideo.value && !showFrozenImage.value && !mockStreamUrl.value,
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
  // 清空上一设备参数，避免切换后残留旧数据
  sourceWidth.value = 0;
  sourceHeight.value = 0;
  frameRate.value = null;
  facingMode.value = null;
  capabilitiesText.value = "";
  previewWidth.value = 0;
  previewHeight.value = 0;
}

interface ExtendedTrackCapabilities extends MediaTrackCapabilities {
  zoom?: { min: number; max: number };
  focusMode?: string[];
}

function buildCapabilitiesText(
  capabilities: MediaTrackCapabilities | undefined,
): string {
  if (!capabilities) {
    return "";
  }
  const caps = capabilities as ExtendedTrackCapabilities;
  const parts: string[] = [];
  if (caps.width?.max && caps.height?.max) {
    parts.push(`最大 ${caps.width.max} × ${caps.height.max}`);
  }
  if (caps.frameRate?.max) {
    parts.push(`最高 ${Math.round(caps.frameRate.max)} FPS`);
  }
  if (caps.zoom) {
    parts.push(`变焦 ${caps.zoom.min} - ${caps.zoom.max}`);
  }
  if (caps.focusMode?.length) {
    parts.push(`对焦 ${caps.focusMode.join(" / ")}`);
  }
  return parts.join("  ·  ");
}

function updatePreviewSize(): void {
  const video = videoRef.value;
  if (!video || !showLiveVideo.value) {
    return;
  }
  const rect = video.getBoundingClientRect();
  previewWidth.value = Math.round(rect.width);
  previewHeight.value = Math.round(rect.height);
}

function handleVideoMetadata(): void {
  const video = videoRef.value;
  if (!video) {
    return;
  }
  // 摄像头原始像素以 video 元素实际解码尺寸为准
  sourceWidth.value = video.videoWidth;
  sourceHeight.value = video.videoHeight;
  updatePreviewSize();
}

async function listBrowserCameras(): Promise<void> {
  try {
    if (!navigator.mediaDevices?.enumerateDevices) {
      cameras.value = [];
      return;
    }
    const devices = await navigator.mediaDevices.enumerateDevices();
    const videoDevices = devices
      .filter((d) => d.kind === "videoinput")
      .filter((d) => !isVirtualCamera(d.label));
    cameras.value = videoDevices.map((device) => ({
      deviceId: device.deviceId,
      // 授权前 label 可能为空；不做人工编号，统一回退为 "Camera"
      label: device.label || "Camera",
    }));
    if (
      cameras.value.length > 0 &&
      !cameras.value.some((c) => c.deviceId === selectedDeviceId.value)
    ) {
      selectedDeviceId.value = cameras.value[0].deviceId;
    }
  } catch {
    cameras.value = [];
  }
}

async function applyStream(stream: MediaStream): Promise<MediaTrackSettings> {
  mediaStream = stream;

  const videoTrack = stream.getVideoTracks()[0];
  const settings = videoTrack ? videoTrack.getSettings() : {};
  const capabilities = videoTrack?.getCapabilities?.();

  // 每次打开/切换都重新读取真实参数，不保留上一设备数据
  frameRate.value = settings.frameRate ?? null;
  facingMode.value = settings.facingMode ?? null;
  capabilitiesText.value = buildCapabilitiesText(capabilities);

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
    index: null,
    name: videoTrack?.label || "",
    available: true,
    width: null,
    height: null,
    fps: null,
    message: null,
    code: null,
  });

  await nextTick();
  const video = videoRef.value;
  if (video) {
    video.srcObject = stream;
    video.onloadedmetadata = () => handleVideoMetadata();
    try {
      await video.play();
      // 若 loadedmetadata 已触发则补一次
      handleVideoMetadata();
    } catch {
      // Autoplay may be rejected by the browser; the video element still renders frames.
    }
  }
  return settings;
}

async function startStream(
  getStream: () => Promise<MediaStream>,
): Promise<void> {
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
    let settings = await applyStream(await getStream());

    // 授权后重新枚举，获取完整设备名称（此时才能识别虚拟摄像头 label）
    await listBrowserCameras();

    let activeId = settings.deviceId ?? "";
    if (
      cameras.value.length > 0 &&
      !cameras.value.some((c) => c.deviceId === activeId)
    ) {
      // 默认打开的设备被识别为虚拟摄像头，自动切换到第一个物理摄像头
      const target = cameras.value[0].deviceId;
      stopStream();
      settings = await applyStream(
        await navigator.mediaDevices.getUserMedia({
          video: { deviceId: { exact: target } },
        }),
      );
      activeId = settings.deviceId ?? target;
    }
    if (activeId) {
      selectedDeviceId.value = activeId;
    }
  } catch (error) {
    handleCameraError(error);
  } finally {
    busy.value = false;
  }
}

async function openBrowserCamera(deviceId: string): Promise<void> {
  await startStream(() =>
    navigator.mediaDevices.getUserMedia({
      video: deviceId ? { deviceId: { exact: deviceId } } : true,
    }),
  );
}

async function detectSelected(): Promise<void> {
  await startStream(async () => {
    if (isMobileDevice) {
      // 手机端优先后置主摄，设备不支持时回退到默认摄像头
      try {
        return await navigator.mediaDevices.getUserMedia({
          video: { facingMode: { ideal: "environment" } },
        });
      } catch (error) {
        if (
          error instanceof DOMException &&
          (error.name === "OverconstrainedError" ||
            error.name === "NotFoundError")
        ) {
          return navigator.mediaDevices.getUserMedia({ video: true });
        }
        throw error;
      }
    }
    // 桌面端使用系统默认摄像头
    return navigator.mediaDevices.getUserMedia({ video: true });
  });
}

async function reconnectSelected(): Promise<void> {
  await openBrowserCamera(selectedDeviceId.value);
}

async function openSelected(): Promise<void> {
  await openBrowserCamera(selectedDeviceId.value);
}

async function handleCameraChange(): Promise<void> {
  const target = selectedDeviceId.value;
  if (!target || !cameraFeedActive.value || busy.value) {
    return;
  }
  const current = mediaStream?.getVideoTracks()[0]?.getSettings().deviceId;
  if (current === target) {
    return;
  }
  await openBrowserCamera(target);
}

async function switchToMock(): Promise<void> {
  if (busy.value) {
    return;
  }
  busy.value = true;
  try {
    stopStream();
    const nextStatus = await useMockCamera();
    mockStreamFailed.value = false;
    mockStreamSession.value += 1;
    updateStatus(nextStatus);
  } catch (error) {
    handleCameraError(error);
  } finally {
    busy.value = false;
  }
}

async function switchToReal(): Promise<void> {
  if (status.value.state === "mock") {
    try {
      await closeCamera();
    } catch {
      // 忽略服务器 Mock 关闭失败
    }
  }
  await reconnectSelected();
}

async function closeSelected(): Promise<void> {
  if (busy.value) {
    return;
  }
  busy.value = true;
  try {
    if (status.value.state === "mock") {
      try {
        await closeCamera();
      } catch {
        // 忽略服务器 Mock 关闭失败
      }
    }
    stopStream();
    updateStatus(createStatus("closed", "摄像头已关闭"));
  } finally {
    busy.value = false;
  }
}

function handleMockStreamError(): void {
  if (props.frozen) {
    return;
  }
  mockStreamFailed.value = true;
}

async function restartPreview(): Promise<void> {
  if (status.value.state === "mock") {
    mockStreamFailed.value = false;
    mockStreamSession.value += 1;
    return;
  }
  await detectSelected();
}

async function captureFrame(): Promise<Blob> {
  if (status.value.state === "mock") {
    const result = await captureMockFrame();
    const response = await fetch(result.image_url);
    if (!response.ok) {
      throw new Error("拍摄图片无法加载");
    }
    return response.blob();
  }
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
  window.addEventListener("resize", updatePreviewSize);
  window.addEventListener("orientationchange", updatePreviewSize);
  if (typeof ResizeObserver !== "undefined" && videoRef.value) {
    resizeObserver = new ResizeObserver(() => updatePreviewSize());
    resizeObserver.observe(videoRef.value);
  }
  await listBrowserCameras();
  await detectSelected();
});

onBeforeUnmount(() => {
  window.removeEventListener("resize", updatePreviewSize);
  window.removeEventListener("orientationchange", updatePreviewSize);
  resizeObserver?.disconnect();
  resizeObserver = null;
  stopStream();
  if (status.value.state === "mock") {
    closeCamera().catch(() => undefined);
  }
});

watch(showLiveVideo, (visible) => {
  if (visible) {
    void nextTick(() => updatePreviewSize());
  }
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
          v-if="cameras.length > 1"
          v-model="selectedDeviceId"
          :disabled="busy"
          aria-label="摄像头"
          @change="handleCameraChange"
        >
          <option
            v-for="camera in cameras"
            :key="camera.deviceId"
            :value="camera.deviceId"
          >
            {{ camera.label }}
          </option>
        </select>
        <button
          v-if="!cameraFeedActive && cameras.length > 0"
          class="button compact"
          type="button"
          :disabled="busy || !selectedDeviceId"
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

    <div v-if="status.state === 'available'" class="camera-metrics">
      <span>设备：{{ deviceNameText }}</span>
      <span>视频源：{{ sourceSizeText }}</span>
      <span>预览区域：{{ previewSizeText }}</span>
      <span>帧率：{{ fpsText }}</span>
      <span>比例：{{ aspectRatioText }}</span>
      <span>方向：{{ facingText }}</span>
      <span v-if="capabilitiesText">能力：{{ capabilitiesText }}</span>
    </div>

    <div class="camera-stage" aria-label="摄像头预览区域">
      <span v-if="showLiveVideo" class="live-badge" aria-hidden="true">LIVE</span>
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
        v-if="mockStreamUrl"
        :src="mockStreamUrl"
        class="camera-image"
        alt="Mock 测试画面"
        @error="handleMockStreamError"
      />
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
            v-if="status.state === 'disconnected' || mockStreamFailed"
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

/* 元素尺寸即内容显示尺寸，边框严格贴合实际画面，object-fit 保证不变形 */
.camera-image {
  display: block;
  width: auto;
  max-width: 100%;
  height: auto;
  max-height: 68vh;
  object-fit: contain;
  border: 1px solid rgba(105, 210, 197, 0.35);
  border-radius: 8px;
  background: #101716;
}

.live-badge {
  position: absolute;
  top: 10px;
  left: 10px;
  z-index: 2;
  padding: 3px 10px;
  border-radius: 999px;
  color: #0f1716;
  background: #69d2c5;
  font-size: 0.68rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  box-shadow: 0 1px 6px rgba(0, 0, 0, 0.35);
}

.camera-metrics {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 16px;
  padding: 8px 12px;
  border-bottom: 1px solid var(--border);
  color: var(--text-muted);
  background: var(--surface-muted);
  font-size: 0.75rem;
  line-height: 1.6;
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
}

.camera-metrics span {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
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

  .camera-metrics {
    gap: 2px 12px;
    font-size: 0.7rem;
  }

  .camera-metrics span {
    max-width: 100%;
  }
}

@media (max-width: 760px) {
  .camera-stage {
    min-height: 260px;
  }
}
</style>
