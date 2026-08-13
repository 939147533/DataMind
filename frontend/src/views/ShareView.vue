<template>
  <BigScreenDashboard
    v-if="payload && payload.charts"
    :dashboard="payload.dashboard"
    :charts="payload.charts"
    :load-chart="loadChart"
  />
  <div v-else class="share-page">
    <div class="share-loading">
      <div v-if="error" class="share-error">{{ error }}</div>
      <template v-else>
        <div class="spinner"></div>
        <div class="share-text">大屏加载中...</div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from "vue";
import { useRoute } from "vue-router";
import { chartApi } from "../api";
import type { SharePayload } from "../api";
import BigScreenDashboard from "../components/BigScreenDashboard.vue";

const route = useRoute();
const token = String(route.params.token || "");
const payload = ref<SharePayload | null>(null);
const error = ref("");

function loadChart(chartId: number) {
  return chartApi.shareChartData(token, chartId);
}

onMounted(async () => {
  document.title = "数据大屏";
  try {
    payload.value = await chartApi.shareData(token);
    if (payload.value.dashboard?.name) document.title = payload.value.dashboard.name + " - 数据大屏";
  } catch (e) {
    error.value = (e as Error).message || "分享不存在或已关闭";
  }
});

onBeforeUnmount(() => {
  document.title = "";
});
</script>

<style scoped>
.share-page {
  position: fixed;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: radial-gradient(1200px 700px at 20% 10%, #0e1c3c 0%, #060b1a 55%, #030612 100%);
}
.share-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 14px;
  color: #8fa3c8;
  font-size: 14px;
}
.share-error {
  color: #ff8f8f;
  font-size: 15px;
}
.spinner {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  border: 3px solid rgba(79, 141, 249, 0.25);
  border-top-color: #4f8df9;
  animation: spin 0.9s linear infinite;
}
.share-text {
  letter-spacing: 2px;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
