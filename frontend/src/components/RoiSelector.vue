<template>
  <section class="panel roi-panel">
    <div class="panel-header">
      <h2>ROI 框选</h2>
      <span class="muted">原图坐标</span>
    </div>
    <div class="roi-stage">
      <div class="roi-empty">
        <span class="roi-corners" aria-hidden="true"></span>
        <strong>尚未拍摄图片</strong>
        <small>等待拍摄结果</small>
      </div>
    </div>
  </section>
</template>

<style scoped>
.roi-stage {
  display: grid;
  place-items: center;
  min-height: 320px;
  padding: 24px;
  background:
    linear-gradient(45deg, #edf1f0 25%, transparent 25%),
    linear-gradient(-45deg, #edf1f0 25%, transparent 25%),
    linear-gradient(45deg, transparent 75%, #edf1f0 75%),
    linear-gradient(-45deg, transparent 75%, #edf1f0 75%);
  background-color: #f7f9f8;
  background-position:
    0 0,
    0 10px,
    10px -10px,
    -10px 0;
  background-size: 20px 20px;
}

.roi-empty {
  display: grid;
  justify-items: center;
  color: var(--text-muted);
  text-align: center;
}

.roi-empty strong {
  margin-top: 18px;
  color: var(--text);
}

.roi-empty small {
  margin-top: 6px;
}

.roi-corners {
  position: relative;
  width: 82px;
  height: 64px;
  border: 1px dashed #95a6a2;
}

.roi-corners::before,
.roi-corners::after {
  position: absolute;
  width: 14px;
  height: 14px;
  border-color: var(--accent);
  border-style: solid;
  content: "";
}

.roi-corners::before {
  top: -2px;
  left: -2px;
  border-width: 3px 0 0 3px;
}

.roi-corners::after {
  right: -2px;
  bottom: -2px;
  border-width: 0 3px 3px 0;
}
</style>
