<script setup lang="ts">
import { computed } from "vue";

import type { ColorAnalysisResult } from "@/types/color";

const props = defineProps<{
  result?: ColorAnalysisResult | null;
}>();

const previewColor = computed(() => props.result?.hex ?? "transparent");
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
</script>

<template>
  <section class="panel">
    <div class="panel-header">
      <h2>颜色识别结果</h2>
      <span class="muted">CIELAB</span>
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
          <dd>{{ result?.hex ?? "—" }}</dd>
        </div>
      </dl>
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
  background-image:
    linear-gradient(45deg, #dfe5e3 25%, transparent 25%),
    linear-gradient(-45deg, #dfe5e3 25%, transparent 25%),
    linear-gradient(45deg, transparent 75%, #dfe5e3 75%),
    linear-gradient(-45deg, transparent 75%, #dfe5e3 75%);
  background-position:
    0 0,
    0 8px,
    8px -8px,
    -8px 0;
  background-size: 16px 16px;
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
  margin: 0;
  font-family: Consolas, "Cascadia Mono", monospace;
  font-size: 0.9rem;
}

@media (max-width: 560px) {
  .result-layout {
    grid-template-columns: 1fr;
  }

  .color-preview {
    min-height: 92px;
  }
}
</style>
