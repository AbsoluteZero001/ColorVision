<script setup lang="ts">
import { computed, ref, watch } from "vue";

import type { ColorAnalysisResult } from "@/types/color";
import type { UploadResult } from "@/types/upload";

const props = defineProps<{
  result?: ColorAnalysisResult | null;
  analysisPending?: boolean;
  uploading?: boolean;
  canUpload?: boolean;
  uploadResult?: UploadResult | null;
}>();

const emit = defineEmits<{
  upload: [];
}>();

const copyState = ref<"idle" | "copied" | "error">("idle");
const previewColor = computed(() => props.result?.hex ?? "#f5f8f7");
const rgbText = computed(() =>
  props.result
    ? `${props.result.rgb.r}, ${props.result.rgb.g}, ${props.result.rgb.b}`
    : "—",
);
const labText = computed(() =>
  props.result
    ? `${props.result.lab.l.toFixed(1)}, ${props.result.lab.a.toFixed(1)}, ${props.result.lab.b.toFixed(1)}`
    : "—",
);

async function copyHex(): Promise<void> {
  if (!props.result) {
    return;
  }
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(props.result.hex);
    } else if (!copyWithExecCommand(props.result.hex)) {
      throw new Error("Clipboard API is unavailable");
    }
    copyState.value = "copied";
  } catch {
    copyState.value = copyWithExecCommand(props.result.hex) ? "copied" : "error";
  }
}

function copyWithExecCommand(text: string): boolean {
  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.setAttribute("readonly", "");
  textarea.style.position = "fixed";
  textarea.style.opacity = "0";
  document.body.appendChild(textarea);
  textarea.select();
  const copied = document.execCommand("copy");
  textarea.remove();
  return copied;
}

watch(
  () => props.result?.hex,
  () => {
    copyState.value = "idle";
  },
);
</script>

<template>
  <section class="panel">
    <div class="panel-header">
      <h2>颜色识别结果</h2>
      <span class="muted">{{ analysisPending ? "分析中" : "CIELAB" }}</span>
    </div>
    <div class="panel-body result-layout">
      <div
        class="color-preview"
        :style="{ backgroundColor: previewColor }"
        aria-label="颜色预览"
      ></div>
      <dl class="color-values">
        <div>
          <dt>RGB</dt>
          <dd>{{ rgbText }}</dd>
        </div>
        <div>
          <dt>LAB</dt>
          <dd>{{ labText }}</dd>
        </div>
        <div>
          <dt>HEX</dt>
          <dd>
            {{ result?.hex ?? "—" }}
            <button
              class="copy-button"
              type="button"
              :disabled="!result"
              @click="copyHex"
            >
              {{
                copyState === "copied"
                  ? "已复制"
                  : copyState === "error"
                    ? "复制失败"
                    : "复制 HEX"
              }}
            </button>
          </dd>
        </div>
      </dl>
    </div>
    <div class="result-actions">
      <div class="upload-status">
        <strong v-if="uploadResult">
          {{ uploadResult.success ? "上传成功" : "上传失败" }}
        </strong>
        <span v-if="uploadResult">
          {{ uploadResult.message }} · {{ uploadResult.request_id }}
        </span>
      </div>
      <button
        class="button"
        type="button"
        :disabled="!canUpload || uploading"
        @click="emit('upload')"
      >
        {{ uploading ? "上传中" : "上传服务器" }}
      </button>
    </div>
  </section>
</template>

<style scoped>
.result-layout {
  display: grid;
  grid-template-columns: 130px 1fr;
  gap: 18px;
}

.color-preview {
  min-height: 130px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: #f5f8f7;
}

.color-values {
  display: grid;
  gap: 8px;
  margin: 0;
}

.color-values > div {
  display: grid;
  grid-template-columns: 54px 1fr;
  align-items: center;
  min-height: 38px;
  padding: 0 11px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--surface-muted);
}

.color-values dt {
  color: var(--text-muted);
  font-size: 0.78rem;
}

.color-values dd {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin: 0;
  font-family: Consolas, "Cascadia Mono", monospace;
  font-size: 0.9rem;
}

.result-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  padding: 14px 16px;
  border-top: 1px solid var(--border);
}

.upload-status {
  display: grid;
  gap: 3px;
  min-width: 0;
  color: var(--text-muted);
  font-size: 0.78rem;
}

.upload-status strong {
  color: var(--success);
  font-size: 0.86rem;
}

.upload-status span {
  overflow-wrap: anywhere;
}

.copy-button {
  min-height: 28px;
  padding: 0 9px;
  border: 1px solid var(--border);
  border-radius: 5px;
  color: var(--accent-strong);
  background: var(--surface);
  font-family: "Segoe UI", sans-serif;
  font-size: 0.76rem;
  cursor: pointer;
}

.copy-button:disabled {
  color: var(--text-muted);
  cursor: not-allowed;
}

@media (max-width: 560px) {
  .result-layout {
    grid-template-columns: 1fr;
  }

  .color-preview {
    min-height: 92px;
  }

  .result-actions {
    align-items: stretch;
    flex-direction: column;
  }
}
</style>
