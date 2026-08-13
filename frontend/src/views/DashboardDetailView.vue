<template>
  <div class="detail-view">
    <div class="detail-head">
      <n-button size="small" quaternary @click="goBack">← 返回</n-button>
      <div class="detail-title">{{ dashboard?.name || "仪表盘" }}</div>
      <div class="detail-actions">
        <n-button size="small" type="primary" ghost :loading="saving" @click="saveLayout">保存布局</n-button>
        <n-button size="small" type="primary" @click="openBigScreen">大屏预览</n-button>
      </div>
    </div>
    <n-alert v-if="!canEdit" type="info" :show-icon="true" style="margin-bottom: 10px">
      当前为只读模式，仅可查看布局。
    </n-alert>
    <div class="detail-toolbar">
      <n-form inline label-placement="left" label-width="auto" size="small">
        <n-form-item label="全局刷新间隔(秒)">
          <n-input-number v-model:value="refreshInterval" :min="0" :max="3600" style="width: 130px" />
        </n-form-item>
        <n-form-item label="列数">
          <n-input-number v-model:value="columns" :min="6" :max="24" style="width: 110px" />
        </n-form-item>
        <n-form-item label="行高(px)">
          <n-input-number v-model:value="rowHeight" :min="20" :max="160" style="width: 110px" />
        </n-form-item>
        <n-form-item>
          <n-text depth="3" style="font-size: 12px">拖拽/缩放图表卡片以调整布局，保存后生效；大屏按 16:9 自适应展示。</n-text>
        </n-form-item>
      </n-form>
    </div>
    <div class="detail-grid-wrap">
      <DashboardGrid
        v-if="gridCharts.length"
        :charts="gridCharts"
        :layout="gridLayout"
        :editable="canEdit"
        :data-map="chartData"
        :error-map="chartErrors"
        @layout-change="onLayoutChange"
      />
      <n-empty v-else description="该仪表盘暂无图表" style="padding: 60px 0" />
    </div>

    <BigScreenDashboard
      v-if="bigScreen.show && bigScreen.dashboard"
      :dashboard="bigScreen.dashboard"
      :charts="bigScreen.charts"
      :load-chart="loadChartAuthed"
      :show-header="false"
      :show-close="true"
      @close="bigScreen.show = false"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from "vue";
import { useMessage } from "naive-ui";
import { useRoute, useRouter } from "vue-router";
import { chartApi } from "../api";
import type { ChartWithData, Dashboard } from "../api";
import DashboardGrid from "../components/DashboardGrid.vue";
import BigScreenDashboard from "../components/BigScreenDashboard.vue";
import { useAuthStore } from "../stores/auth";

const route = useRoute();
const router = useRouter();
const message = useMessage();
const auth = useAuthStore();

const dashboardId = Number(route.params.id);
const dashboard = ref<Dashboard | null>(null);
const charts = ref<ChartWithData[]>([]);
const chartData = reactive<Record<number, { columns: string[]; rows: unknown[][] } | null>>({});
const chartErrors = reactive<Record<number, string>>({});
const saving = ref(false);
const dirty = ref(false);

const refreshInterval = ref(0);
const columns = ref(12);
const rowHeight = ref(44);
let localLayout = "{}";

const canEdit = computed(() => auth.hasPermission("reports_manage"));

const gridCharts = computed(() => charts.value.map((c) => ({ ...c })));
const gridLayout = computed(() => {
  try {
    const lo = JSON.parse(localLayout || "{}");
    return JSON.stringify({ ...lo, columns: columns.value, rowHeight: rowHeight.value, refresh_interval: refreshInterval.value });
  } catch {
    return "{}";
  }
});

const bigScreen = reactive({ show: false, dashboard: null as Dashboard | null, charts: [] as ChartWithData[] });

async function loadChartAuthed(chartId: number) {
  return chartApi.data(chartId);
}

async function load() {
  try {
    dashboard.value = await chartApi.dashboard(dashboardId);
    const all = await chartApi.list();
    const byId = new Map(all.map((c) => [c.id, c]));
    charts.value = dashboard.value.chart_ids
      .map((id) => byId.get(id))
      .filter((c): c is ChartWithData => !!c)
      .map((c) => ({ ...c }));
    const lo = safeParse(dashboard.value.layout);
    columns.value = lo.columns || 12;
    rowHeight.value = lo.rowHeight || 44;
    refreshInterval.value = Number(lo.refresh_interval) || 0;
    localLayout = JSON.stringify(lo);
    for (const c of charts.value) loadChartData(c.id);
  } catch (e) {
    message.error((e as Error).message);
  }
}

function safeParse(s: string): Record<string, any> {
  try {
    const o = JSON.parse(s || "{}");
    return o && typeof o === "object" ? o : {};
  } catch {
    return {};
  }
}

async function loadChartData(id: number) {
  try {
    chartData[id] = await chartApi.data(id);
  } catch (e) {
    chartData[id] = null;
    chartErrors[id] = (e as Error).message;
  }
}

function onLayoutChange(layout: string) {
  localLayout = layout;
  dirty.value = true;
}

async function saveLayout() {
  saving.value = true;
  try {
    const lo = safeParse(localLayout);
    lo.columns = columns.value;
    lo.rowHeight = rowHeight.value;
    lo.refresh_interval = refreshInterval.value;
    await chartApi.updateDashboard(dashboardId, { layout: JSON.stringify(lo) });
    dirty.value = false;
    message.success("布局已保存");
  } catch (e) {
    message.error((e as Error).message);
  } finally {
    saving.value = false;
  }
}

function openBigScreen() {
  if (!dashboard.value) return;
  bigScreen.dashboard = { ...dashboard.value, layout: gridLayout.value };
  bigScreen.charts = charts.value.map((c) => ({ ...c }));
  bigScreen.show = true;
}

function goBack() {
  router.push("/reports");
}

function onBeforeUnload(e: BeforeUnloadEvent) {
  if (dirty.value) {
    e.preventDefault();
    e.returnValue = "";
  }
}

onMounted(() => {
  window.addEventListener("beforeunload", onBeforeUnload);
  load();
});
onBeforeUnmount(() => {
  window.removeEventListener("beforeunload", onBeforeUnload);
});
</script>

<style scoped>
.detail-view {
  padding: 14px 16px;
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.detail-head {
  display: flex;
  align-items: center;
  gap: 12px;
}
.detail-title {
  flex: 1;
  font-size: 17px;
  font-weight: 600;
}
.detail-actions {
  display: flex;
  gap: 8px;
}
.detail-toolbar {
  padding: 8px 12px;
  border: 1px solid #e6ebf5;
  border-radius: 8px;
  background: #fafbfe;
}
.detail-grid-wrap {
  flex: 1;
  min-height: 0;
  overflow: auto;
}
</style>
