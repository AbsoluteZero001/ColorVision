<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";

import { getApiErrorMessage } from "@/services/api";
import {
  clearUploadLogs,
  deleteUploadLog,
  listUploadLogs,
} from "@/services/log";
import type { UploadLogEntry } from "@/types/log";

interface PreviewImage {
  url: string;
  label: string;
}

const PAGE_SIZE = 20;

const entries = ref<UploadLogEntry[]>([]);
const total = ref(0);
const currentPage = ref(1);
const loading = ref(true);
const mutating = ref(false);
const errorMessage = ref("");
const previewImage = ref<PreviewImage | null>(null);

const totalPages = computed(() =>
  Math.max(1, Math.ceil(total.value / PAGE_SIZE)),
);
const pageStart = computed(() =>
  total.value === 0 ? 0 : (currentPage.value - 1) * PAGE_SIZE + 1,
);
const pageEnd = computed(() =>
  Math.min(currentPage.value * PAGE_SIZE, total.value),
);
const pageRangeText = computed(() =>
  total.value === 0 ? "0 / 0" : `${pageStart.value}-${pageEnd.value} / ${total.value}`,
);

async function loadLogs(): Promise<void> {
  loading.value = true;
  errorMessage.value = "";
  try {
    const offset = (currentPage.value - 1) * PAGE_SIZE;
    const page = await listUploadLogs(PAGE_SIZE, offset);
    const lastPage = Math.max(1, Math.ceil(page.total / PAGE_SIZE));
    if (currentPage.value > lastPage) {
      currentPage.value = lastPage;
      await loadLogs();
      return;
    }
    entries.value = page.items;
    total.value = page.total;
  } catch (error) {
    errorMessage.value = getApiErrorMessage(error);
  } finally {
    loading.value = false;
  }
}

async function removeLog(entry: UploadLogEntry): Promise<void> {
  if (
    mutating.value ||
    !window.confirm(`删除 ${entry.uploaded_at_beijing} 的日志记录？`)
  ) {
    return;
  }
  mutating.value = true;
  errorMessage.value = "";
  try {
    await deleteUploadLog(entry.id);
    if (entries.value.length === 1 && currentPage.value > 1) {
      currentPage.value -= 1;
    }
    await loadLogs();
  } catch (error) {
    errorMessage.value = getApiErrorMessage(error);
  } finally {
    mutating.value = false;
  }
}

async function removeAllLogs(): Promise<void> {
  if (
    mutating.value ||
    !window.confirm("清空全部日志和本地图片？该操作无法恢复。")
  ) {
    return;
  }
  mutating.value = true;
  errorMessage.value = "";
  try {
    await clearUploadLogs();
    currentPage.value = 1;
    await loadLogs();
  } catch (error) {
    errorMessage.value = getApiErrorMessage(error);
  } finally {
    mutating.value = false;
  }
}

function changePage(page: number): void {
  if (
    loading.value ||
    page < 1 ||
    page > totalPages.value ||
    page === currentPage.value
  ) {
    return;
  }
  currentPage.value = page;
  void loadLogs();
}

function openPreview(url: string | null, label: string): void {
  if (url) {
    previewImage.value = { url, label };
  }
}

function closePreview(): void {
  previewImage.value = null;
}

function handleKeydown(event: KeyboardEvent): void {
  if (event.key === "Escape" && previewImage.value) {
    closePreview();
  }
}

function formatRoi(entry: UploadLogEntry): string {
  const { x, y, width, height } = entry.roi;
  return `${x}, ${y} · ${width} × ${height}`;
}

onMounted(() => {
  window.addEventListener("keydown", handleKeydown);
  void loadLogs();
});

onBeforeUnmount(() => {
  window.removeEventListener("keydown", handleKeydown);
});
</script>

<template>
  <div class="logs-view">
    <div class="page-heading">
      <div>
        <h1>上传日志</h1>
        <p>北京时间的本地上传记录与颜色识别结果</p>
      </div>
      <span class="storage-badge">仅保存在本机</span>
    </div>

    <p v-if="errorMessage" class="workflow-error" role="alert">
      {{ errorMessage }}
    </p>

    <div class="log-toolbar">
      <div>
        <strong>{{ total }} 条记录</strong>
        <span>按上传时间倒序排列</span>
      </div>
      <button
        class="button secondary danger-button"
        type="button"
        :disabled="loading || mutating || total === 0"
        @click="removeAllLogs"
      >
        {{ mutating ? "处理中" : "清空全部" }}
      </button>
    </div>

    <div v-if="loading" class="log-state" role="status">
      <span class="loading-line"></span>
      <strong>正在读取本地日志</strong>
    </div>

    <div v-else-if="entries.length === 0" class="log-state empty-state">
      <strong>暂无上传日志</strong>
      <span>上传成功后，记录会显示在这里。</span>
    </div>

    <div v-else class="log-list">
      <article v-for="entry in entries" :key="entry.id" class="log-entry">
        <header class="log-entry-header">
          <div class="log-time">
            <span>北京时间</span>
            <strong>{{ entry.uploaded_at_beijing }}</strong>
          </div>
          <div class="entry-meta">
            <span>{{ entry.upload_mode === "mock" ? "Mock 上传" : "API 上传" }}</span>
            <span>{{ entry.camera_id }}</span>
            <button
              class="text-button danger-text"
              type="button"
              :disabled="mutating"
              @click="removeLog(entry)"
            >
              删除
            </button>
          </div>
        </header>

        <div class="log-entry-body">
          <div class="log-media">
            <button
              v-if="entry.original_image_url"
              class="media-button"
              type="button"
              @click="openPreview(entry.original_image_url, '上传原图')"
            >
              <img :src="entry.original_image_url" alt="上传原图" />
              <span>上传原图</span>
            </button>
            <div v-else class="media-placeholder">
              <strong>原图未保存</strong>
              <span>日志图片存储已关闭</span>
            </div>

            <button
              v-if="entry.roi_image_url"
              class="media-button"
              type="button"
              @click="openPreview(entry.roi_image_url, '识别区域图')"
            >
              <img :src="entry.roi_image_url" alt="识别区域图" />
              <span>识别区域图</span>
            </button>
            <div v-else class="media-placeholder">
              <strong>识别图未保存</strong>
              <span>日志图片存储已关闭</span>
            </div>
          </div>

          <div class="log-data">
            <div class="color-heading">
              <span
                class="color-swatch"
                :style="{ backgroundColor: entry.hex }"
                aria-hidden="true"
              ></span>
              <div>
                <span>颜色参数</span>
                <strong>{{ entry.hex }}</strong>
              </div>
            </div>
            <dl>
              <div>
                <dt>RGB</dt>
                <dd>
                  {{ entry.rgb.r }}, {{ entry.rgb.g }}, {{ entry.rgb.b }}
                </dd>
              </div>
              <div>
                <dt>LAB</dt>
                <dd>
                  {{
                    entry.lab.l.toFixed(2)
                  }}, {{ entry.lab.a.toFixed(2) }},
                  {{ entry.lab.b.toFixed(2) }}
                </dd>
              </div>
              <div>
                <dt>ROI</dt>
                <dd>{{ formatRoi(entry) }}</dd>
              </div>
              <div>
                <dt>请求</dt>
                <dd class="request-id">{{ entry.request_id }}</dd>
              </div>
            </dl>
            <p class="upload-message">{{ entry.message }}</p>
          </div>
        </div>
      </article>
    </div>

    <div v-if="!loading && total > 0" class="pagination">
      <span>{{ pageRangeText }}</span>
      <div>
        <button
          class="button secondary"
          type="button"
          :disabled="currentPage <= 1 || mutating"
          @click="changePage(currentPage - 1)"
        >
          上一页
        </button>
        <span>{{ currentPage }} / {{ totalPages }}</span>
        <button
          class="button secondary"
          type="button"
          :disabled="currentPage >= totalPages || mutating"
          @click="changePage(currentPage + 1)"
        >
          下一页
        </button>
      </div>
    </div>

    <div
      v-if="previewImage"
      class="image-modal"
      role="dialog"
      aria-modal="true"
      :aria-label="previewImage.label"
      @click.self="closePreview"
    >
      <div class="image-modal-content">
        <div class="image-modal-header">
          <strong>{{ previewImage.label }}</strong>
          <button class="text-button" type="button" @click="closePreview">
            关闭
          </button>
        </div>
        <img :src="previewImage.url" :alt="previewImage.label" />
      </div>
    </div>
  </div>
</template>

<style scoped>
.logs-view {
  max-width: 1180px;
}

.storage-badge {
  padding: 7px 11px;
  border: 1px solid var(--border);
  border-radius: 999px;
  color: var(--accent-strong);
  background: var(--accent-soft);
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

.log-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  margin-bottom: 16px;
  padding: 14px 0;
  border-top: 1px solid var(--border);
  border-bottom: 1px solid var(--border);
}

.log-toolbar > div {
  display: grid;
  gap: 3px;
}

.log-toolbar strong {
  font-size: 0.96rem;
}

.log-toolbar span {
  color: var(--text-muted);
  font-size: 0.8rem;
}

.danger-button {
  color: var(--danger);
}

.log-state {
  display: grid;
  justify-items: center;
  gap: 8px;
  min-height: 260px;
  place-content: center;
  border: 1px dashed var(--border);
  border-radius: 8px;
  color: var(--text-muted);
  text-align: center;
}

.log-state strong {
  color: var(--text);
}

.loading-line {
  width: 42px;
  height: 3px;
  border-radius: 999px;
  background: var(--accent);
  animation: loading-pulse 900ms ease-in-out infinite alternate;
}

@keyframes loading-pulse {
  from {
    opacity: 0.35;
    transform: scaleX(0.55);
  }

  to {
    opacity: 1;
    transform: scaleX(1);
  }
}

.log-list {
  display: grid;
  gap: 14px;
}

.log-entry {
  overflow: hidden;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface);
  box-shadow: var(--shadow);
}

.log-entry-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  padding: 13px 16px;
  border-bottom: 1px solid var(--border);
  background: var(--surface-muted);
}

.log-time {
  display: flex;
  align-items: baseline;
  gap: 10px;
}

.log-time span {
  color: var(--text-muted);
  font-size: 0.78rem;
}

.log-time strong {
  font-family: Consolas, "Cascadia Mono", monospace;
  font-size: 0.98rem;
}

.entry-meta {
  display: flex;
  align-items: center;
  gap: 8px;
}

.entry-meta > span {
  padding: 4px 8px;
  border: 1px solid var(--border);
  border-radius: 5px;
  color: var(--text-muted);
  background: var(--surface);
  font-size: 0.75rem;
}

.text-button {
  min-height: 30px;
  padding: 0 8px;
  border-radius: 5px;
  color: var(--accent-strong);
  background: transparent;
  cursor: pointer;
}

.text-button:hover:not(:disabled) {
  background: var(--accent-soft);
}

.text-button:disabled {
  color: var(--text-muted);
  cursor: not-allowed;
}

.danger-text {
  color: var(--danger);
}

.log-entry-body {
  display: grid;
  grid-template-columns: minmax(360px, 1fr) minmax(310px, 0.82fr);
}

.log-media {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  padding: 16px;
}

.media-button {
  position: relative;
  display: grid;
  gap: 0;
  overflow: hidden;
  min-width: 0;
  padding: 0;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: #edf1f0;
  cursor: zoom-in;
}

.media-button img {
  display: block;
  width: 100%;
  aspect-ratio: 4 / 3;
  object-fit: contain;
}

.media-button span {
  padding: 7px 9px;
  border-top: 1px solid var(--border);
  color: var(--text-muted);
  background: var(--surface);
  font-size: 0.76rem;
  text-align: left;
}

.media-placeholder {
  display: grid;
  align-content: center;
  justify-items: center;
  gap: 6px;
  min-height: 180px;
  padding: 16px;
  border: 1px dashed var(--border);
  border-radius: 6px;
  color: var(--text-muted);
  background: var(--surface-muted);
  text-align: center;
}

.media-placeholder strong {
  color: var(--text);
  font-size: 0.86rem;
}

.media-placeholder span {
  font-size: 0.76rem;
}

.log-data {
  display: grid;
  align-content: start;
  gap: 14px;
  padding: 16px;
  border-left: 1px solid var(--border);
}

.color-heading {
  display: flex;
  align-items: center;
  gap: 12px;
}

.color-swatch {
  width: 48px;
  height: 48px;
  flex: 0 0 auto;
  border: 1px solid var(--border);
  border-radius: 6px;
}

.color-heading > div {
  display: grid;
  gap: 2px;
}

.color-heading span {
  color: var(--text-muted);
  font-size: 0.76rem;
}

.color-heading strong {
  font-family: Consolas, "Cascadia Mono", monospace;
  font-size: 1rem;
}

.log-data dl {
  display: grid;
  gap: 0;
  margin: 0;
}

.log-data dl > div {
  display: grid;
  grid-template-columns: 58px minmax(0, 1fr);
  gap: 10px;
  align-items: baseline;
  padding: 8px 0;
  border-bottom: 1px solid var(--border);
}

.log-data dt {
  color: var(--text-muted);
  font-size: 0.76rem;
}

.log-data dd {
  min-width: 0;
  margin: 0;
  font-family: Consolas, "Cascadia Mono", monospace;
  font-size: 0.86rem;
}

.request-id {
  overflow-wrap: anywhere;
}

.upload-message {
  margin: 0;
  color: var(--text-muted);
  font-size: 0.78rem;
}

.pagination {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  margin-top: 18px;
  color: var(--text-muted);
  font-size: 0.82rem;
}

.pagination > div {
  display: flex;
  align-items: center;
  gap: 10px;
}

.image-modal {
  position: fixed;
  z-index: 50;
  inset: 0;
  display: grid;
  place-items: center;
  padding: 24px;
  background: rgba(14, 23, 22, 0.78);
}

.image-modal-content {
  display: grid;
  width: min(1100px, 100%);
  max-height: calc(100vh - 48px);
  overflow: hidden;
  border: 1px solid rgba(255, 255, 255, 0.24);
  border-radius: 8px;
  background: #101817;
}

.image-modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 10px 12px 10px 16px;
  color: #ffffff;
  border-bottom: 1px solid rgba(255, 255, 255, 0.16);
}

.image-modal-header .text-button {
  color: #ffffff;
}

.image-modal-content img {
  display: block;
  width: 100%;
  max-height: calc(100vh - 116px);
  object-fit: contain;
}

@media (max-width: 900px) {
  .log-entry-body {
    grid-template-columns: 1fr;
  }

  .log-data {
    border-top: 1px solid var(--border);
    border-left: 0;
  }
}

@media (max-width: 620px) {
  .log-toolbar,
  .log-entry-header,
  .pagination {
    align-items: stretch;
    flex-direction: column;
  }

  .entry-meta {
    flex-wrap: wrap;
  }

  .log-media {
    grid-template-columns: 1fr;
  }

  .pagination > div {
    display: grid;
    grid-template-columns: 1fr auto 1fr;
  }

  .image-modal {
    padding: 10px;
  }
}
</style>
