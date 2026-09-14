<script setup lang="ts">
import { RouterLink, RouterView } from "vue-router";

import ApiStatus from "./components/ApiStatus.vue";
</script>

<template>
  <div class="app-shell">
    <header class="app-header">
      <RouterLink class="brand" to="/">
        <span class="brand-mark" aria-hidden="true"></span>
        <span>
          <strong>颜色识别系统</strong>
          <small>V1.2.0</small>
        </span>
      </RouterLink>

      <nav class="main-nav" aria-label="主导航">
        <RouterLink to="/">工作台</RouterLink>
        <RouterLink to="/settings">设置</RouterLink>
      </nav>

      <ApiStatus />
    </header>

    <main class="app-main">
      <RouterView />
    </main>
  </div>
</template>
