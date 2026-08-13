<template>
  <div class="big-screen">
    <n-button v-if="showClose" size="tiny" quaternary class="close-btn" @click="emit('close')">✕ 关闭</n-button>
    <div ref="screenEl" class="screen" :class="{ fullscreen: isFullscreen }">
      <div v-if="showHeader" class="screen-header">
        <div class="screen-title">
          <span class="title-dot"></span>{{ dashboard.name || "数据大屏" }}
        </div>
        <div class="screen-info">
          <span v-if="minInterval > 0" class="info-item">
            <span class="live-dot"></span>自动刷新 {{ minInterval }}s
          </span>
          <span class="info-item">最后更新 {{ lastUpdated || "--" }}</span>
          <span class="info-item">{{ charts.length }} 个图表</span>
          <n-button size="tiny" quaternary class="fs-btn" @click="toggleFullscreen">
            {{ isFullscreen ? "退出全屏" : "全屏" }}
          </n-button>
        </div>
      </div>
      <div class="screen-body">
        <DashboardGrid
          v-if="gridLayout"
          :charts="charts"
          :layout="gridLayout"
          :dark="true"
          :data-map="dataMap"
          :error-map="errorMap"
        />
        <div v-if="!charts.length" class="screen-empty">暂无图表</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";
import { NButton } from "naive-ui";
import type { ChartWithData, Dashboard } from "../api";
import DashboardGrid from "./DashboardGrid.vue";

const props = withDefaults(
  defineProps<{
    dashboard: Dashboard;
    charts: ChartWithData[];
    loadChart?: (chartId: number) => Promise<{ columns: string[]; rows: unknown[][] }>;
    showHeader?: boolean;
    showClose?: boolean;
  }>(),
  { loadChart: undefined, showHeader: true, showClose: false }
);

const emit = defineEmits<{ (e: "close"): void }>();

const screenEl = ref<HTMLElement>();
const size = reactive({ w: 1280, h: 720 });
const isFullscreen = ref(false);
const dataMap = reactive<Record<number, { columns: string[]; rows: unknown[][] } | null>>({});
const errorMap = reactive<Record<number, string>>({});
const lastUpdated = ref("");
const minInterval = ref(0);
let timers: Record<number, number> = {};
let ro: ResizeObserver | null = null;
let fullscreenListener: (() => void) | null = null;

function parseLayout(): Record<string, any> {
  try {
    const o = JSON.parse(props.dashboard.layout || "{}");
    return o && typeof o === "object" ? o : {};
  } catch {
    return {};
  }
}

function parseOptions(chart: ChartWithData): Record<string, any> {
  try {
    const o = JSON.parse(chart.options || "{}");
    return o && typeof o === "object" ? o : {};
  } catch {
    return {};
  }
}

const chartMap = computed(() => {
  const m: Record<number, ChartWithData> = {};
  props.charts.forEach((c) => (m[c.id] = c));
  return m;
});

function intervalFor(chart: ChartWithData): number {
  const own = Number(parseOptions(chart).refresh_interval);
  if (own > 0) return own;
  const g = Number(parseLayout().refresh_interval);
  return g > 0 ? g : 0;
}

const gridLayout = computed(() => {
  const lo = parseLayout();
  const items = (lo.items || []).filter((it: any) => chartMap.value[it.chart_id]);
  const maxRow = Math.max(1, ...items.map((it: any) => (it.y || 0) + (it.h || 4)));
  const headerH = props.showHeader ? 58 : 0;
  const rowHeight = Math.max(32, Math.min(140, Math.floor((size.h - headerH - 20) / maxRow)));
  return JSON.stringify({ ...lo, columns: 12, rowHeight, margin: 8, items });
});

async function refreshChart(chart: ChartWithData) {
  if (!props.loadChart) return;
  try {
    const res = await props.loadChart(chart.id);
    dataMap[chart.id] = res;
    errorMap[chart.id] = (res as { error?: string }).error || "";
  } catch (e) {
    errorMap[chart.id] = (e as Error).message;
  } finally {
    lastUpdated.value = new Date().toLocaleTimeString("zh-CN", { hour12: false });
  }
}

function schedule() {
  for (const k in timers) {
    clearInterval(timers[k]);
    delete timers[k];
  }
  let min = 0;
  for (const c of props.charts) {
    const sec = intervalFor(c);
    if (sec > 0) {
      timers[c.id] = window.setInterval(() => refreshChart(c), sec * 1000);
      min = min === 0 ? sec : Math.min(min, sec);
    }
  }
  minInterval.value = min;
}

function toggleFullscreen() {
  if (!screenEl.value) return;
  if (document.fullscreenElement) {
    document.exitFullscreen().catch(() => undefined);
  } else {
    screenEl.value.requestFullscreen().catch(() => undefined);
  }
}

function onFsChange() {
  isFullscreen.value = !!document.fullscreenElement;
}

onMounted(() => {
  schedule();
  ro = new ResizeObserver((entries) => {
    const r = entries[0]?.contentRect;
    if (r) {
      size.w = r.width;
      size.h = r.height;
    }
  });
  if (screenEl.value) ro.observe(screenEl.value);
  fullscreenListener = onFsChange;
  document.addEventListener("fullscreenchange", fullscreenListener);
});

watch(() => props.charts, schedule, { deep: false });

onBeforeUnmount(() => {
  for (const k in timers) clearInterval(timers[k]);
  timers = {};
  ro?.disconnect();
  ro = null;
  if (fullscreenListener) document.removeEventListener("fullscreenchange", fullscreenListener);
});
</script>

<style scoped>
.big-screen {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  background: radial-gradient(1200px 700px at 20% 10%, #0e1c3c 0%, #060b1a 55%, #030612 100%);
  overflow: hidden;
}
.screen {
  width: min(100vw, calc(100vh * 16 / 9));
  height: min(100vh, calc(100vw * 9 / 16));
  display: flex;
  flex-direction: column;
  background:
    radial-gradient(900px 500px at 15% 0%, rgba(79, 141, 249, 0.12), transparent 60%),
    radial-gradient(700px 400px at 90% 100%, rgba(54, 207, 201, 0.1), transparent 60%),
    #0a1122;
  border-radius: 12px;
  overflow: hidden;
}
.screen.fullscreen {
  border-radius: 0;
  width: 100vw;
  height: 100vh;
}
.screen-header {
  height: 58px;
  flex: none;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 22px;
  border-bottom: 1px solid rgba(79, 141, 249, 0.25);
  background: linear-gradient(180deg, rgba(20, 34, 66, 0.85), rgba(10, 17, 34, 0.4));
}
.screen-title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 20px;
  font-weight: 700;
  letter-spacing: 2px;
  color: #eaf2ff;
  text-shadow: 0 0 18px rgba(79, 141, 249, 0.6);
}
.title-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: linear-gradient(135deg, #4f8df9, #36cfc9);
  box-shadow: 0 0 12px rgba(79, 141, 249, 0.9);
}
.screen-info {
  display: flex;
  align-items: center;
  gap: 16px;
  font-size: 12px;
  color: #8fa3c8;
}
.info-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.live-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #36cfc9;
  animation: livePulse 1.6s ease-in-out infinite;
}
.fs-btn {
  color: #bcd2ff;
}
.close-btn {
  position: absolute;
  top: 14px;
  right: 18px;
  z-index: 1100;
  color: #bcd2ff;
}
.screen-body {
  flex: 1;
  min-height: 0;
  padding: 10px 12px 12px;
  overflow: hidden;
}
.screen-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #8fa3c8;
  font-size: 14px;
}
@keyframes livePulse {
  0%, 100% { opacity: 1; box-shadow: 0 0 6px rgba(54, 207, 201, 0.9); }
  50% { opacity: 0.45; box-shadow: none; }
}
</style>
