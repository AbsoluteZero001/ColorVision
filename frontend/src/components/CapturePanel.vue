<template>
  <section class="panel">
    <div class="panel-header">
      <h2>拍摄控制</h2>
      <span class="muted">准备就绪后可用</span>
    </div>
    <div class="panel-body capture-actions">
      <button class="button" type="button" disabled>拍照</button>
      <button class="button secondary" type="button" disabled>重新拍摄</button>
    </div>
  </section>
</template>

<style scoped>
.capture-actions {
  display: flex;
  gap: 10px;
}

@media (max-width: 520px) {
  .capture-actions {
    flex-direction: column;
  }
}
</style>
