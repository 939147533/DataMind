<template>
  <div class="reports-view">
    <n-tabs v-model:value="activeTab" type="line" size="medium">
      <n-tab-pane name="charts" tab="图表管理">
        <div class="toolbar">
          <n-button type="primary" size="small" @click="openCreate">＋ 新建图表</n-button>
        </div>
        <n-grid :cols="2" :x-gap="16" :y-gap="16" responsive="screen" item-responsive>
          <n-grid-item v-for="c in charts" :key="c.id" span="12 m:12 l:12">
            <n-card :title="c.name" size="small">
              <template #header-extra>
                <div class="card-actions">
                  <n-button size="tiny" text @click="openEdit(c)">编辑</n-button>
                  <n-popconfirm @positive-click="removeChart(c.id)">
                    <template #trigger><n-button size="tiny" text type="error">删除</n-button></template>
                    确定删除该图表？
                  </n-popconfirm>
                </div>
              </template>
              <div style="height: 240px">
                <ChartCard :chart="c" :data="chartData[c.id] ?? null" />
              </div>
              <div class="chart-sql">{{ c.sql_text }}</div>
            </n-card>
          </n-grid-item>
        </n-grid>
        <n-empty v-if="!charts.length" description="暂无图表，点击右上角新建" style="padding: 60px 0" />
      </n-tab-pane>

      <n-tab-pane name="dashboards" tab="仪表盘">
        <div class="toolbar">
          <n-button type="primary" size="small" @click="openDashboardCreate">＋ 新建仪表盘</n-button>
        </div>
        <n-grid :cols="3" :x-gap="16" :y-gap="16" responsive="screen" item-responsive>
          <n-grid-item v-for="d in dashboards" :key="d.id" span="8 m:8 l:8">
            <n-card :title="d.name" size="small">
              <template #header-extra>
                <div class="card-actions">
                  <n-button size="tiny" text @click="viewDashboard(d)">查看</n-button>
                  <n-button size="tiny" text @click="shareDashboard(d)">分享</n-button>
                  <n-popconfirm @positive-click="removeDashboard(d.id)">
                    <template #trigger><n-button size="tiny" text type="error">删除</n-button></template>
                    确定删除该仪表盘？
                  </n-popconfirm>
                </div>
              </template>
              <div class="dash-meta">{{ d.chart_ids.length }} 个图表 · {{ d.is_public ? "已分享" : "未分享" }}</div>
            </n-card>
          </n-grid-item>
        </n-grid>
        <n-empty v-if="!dashboards.length" description="暂无仪表盘" style="padding: 60px 0" />
      </n-tab-pane>
    </n-tabs>

    <!-- 图表编辑 -->
    <n-modal v-model:show="chartModal" preset="card" :title="editingChart ? '编辑图表' : '新建图表'" style="width: 640px">
      <n-form label-placement="left" label-width="100px">
        <n-form-item label="名称"><n-input v-model:value="chartForm.name" placeholder="图表名称" /></n-form-item>
        <n-form-item label="数据源">
          <n-select v-model:value="chartForm.datasource_id" :options="dsOptions" placeholder="选择数据源" />
        </n-form-item>
        <n-form-item label="SQL">
          <n-input v-model:value="chartForm.sql_text" type="textarea" :rows="4" placeholder="SELECT status, COUNT(*) AS cnt FROM orders GROUP BY status" />
        </n-form-item>
        <n-grid :cols="3" :x-gap="12">
          <n-form-item-gi label="图表类型">
            <n-select v-model:value="chartForm.chart_type" :options="chartTypeOptions" />
          </n-form-item-gi>
          <n-form-item-gi label="X 列"><n-input v-model:value="chartForm.x_column" placeholder="分类列" /></n-form-item-gi>
          <n-form-item-gi label="Y 列"><n-input v-model:value="chartForm.y_column" placeholder="数值列" /></n-form-item-gi>
        </n-grid>
        <n-form-item label="聚合方式">
          <n-select v-model:value="chartForm.aggregation" :options="aggOptions" />
        </n-form-item>
      </n-form>
      <template #footer>
        <div style="display: flex; justify-content: flex-end; gap: 8px">
          <n-button :loading="previewLoading" @click="previewChart">预览</n-button>
          <n-button type="primary" :loading="chartSaving" @click="saveChart">保存</n-button>
        </div>
      </template>
    </n-modal>

    <!-- 图表预览 -->
    <n-modal v-model:show="previewShow" preset="card" title="图表预览" style="width: 680px">
      <div style="height: 320px">
        <ChartCard :chart="previewChartObj" :data="previewData" />
      </div>
    </n-modal>

    <!-- 仪表盘创建 -->
    <n-modal v-model:show="dashModal" preset="card" title="新建仪表盘" style="width: 480px">
      <n-form label-placement="left" label-width="80px">
        <n-form-item label="名称"><n-input v-model:value="dashForm.name" placeholder="仪表盘名称" /></n-form-item>
        <n-form-item label="图表">
          <n-select v-model:value="dashForm.chart_ids" multiple :options="chartSelectOptions" placeholder="选择要加入的图表" />
        </n-form-item>
      </n-form>
      <template #footer>
        <div style="display: flex; justify-content: flex-end">
          <n-button type="primary" @click="saveDashboard">创建</n-button>
        </div>
      </template>
    </n-modal>

    <!-- 仪表盘查看 -->
    <n-modal v-model:show="viewDash" preset="card" :title="viewingDashboard?.name || '仪表盘'" style="width: 960px">
      <n-grid :cols="2" :x-gap="12" :y-gap="12">
        <n-grid-item v-for="cid in viewingDashboard?.chart_ids || []" :key="cid">
          <n-card size="small" :title="chartName(cid)">
            <div style="height: 240px">
              <ChartCard v-if="chartById(cid)" :chart="chartById(cid)!" :data="chartData[cid] ?? null" />
            </div>
          </n-card>
        </n-grid-item>
      </n-grid>
    </n-modal>

    <!-- 分享 -->
    <n-modal v-model:show="shareShow" preset="card" title="分享仪表盘" style="width: 520px">
      <p>任何人持有以下链接均可查看该仪表盘：</p>
      <n-input v-model:value="shareUrl" readonly />
      <template #footer>
        <div style="display: flex; justify-content: flex-end">
          <n-button type="primary" @click="copyShare">复制链接</n-button>
        </div>
      </template>
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { useMessage } from "naive-ui";
import { chartApi, sqlApi } from "../api";
import type { Chart, Dashboard } from "../api";
import ChartCard from "../components/ChartCard.vue";
import { useConnectionsStore } from "../stores/connections";

const message = useMessage();
const connections = useConnectionsStore();
const activeTab = ref("charts");
const charts = ref<Chart[]>([]);
const dashboards = ref<Dashboard[]>([]);
const chartData = reactive<Record<number, { columns: string[]; rows: unknown[][] } | null>>({});

const chartModal = ref(false);
const chartSaving = ref(false);
const previewLoading = ref(false);
const editingChart = ref<Chart | null>(null);
const chartForm = reactive({ name: "", datasource_id: null as number | null, sql_text: "", chart_type: "bar", x_column: "", y_column: "", aggregation: "none" });

const previewShow = ref(false);
const previewData = ref<{ columns: string[]; rows: unknown[][] } | null>(null);
const previewChartObj = ref<Chart>({ id: -1, name: "预览", datasource_id: null, sql_text: "", chart_type: "bar", x_column: "", y_column: "", aggregation: "none", options: "{}" });

const dashModal = ref(false);
const dashForm = reactive({ name: "", chart_ids: [] as number[] });
const viewDash = ref(false);
const viewingDashboard = ref<Dashboard | null>(null);
const shareShow = ref(false);
const shareUrl = ref("");

const dsOptions = computed(() => connections.list.map((c) => ({ label: c.name, value: c.id })));
const chartTypeOptions = [
  { label: "柱状图", value: "bar" },
  { label: "折线图", value: "line" },
  { label: "饼图", value: "pie" },
];
const aggOptions = [
  { label: "无", value: "none" },
  { label: "求和", value: "sum" },
  { label: "计数", value: "count" },
  { label: "平均", value: "avg" },
  { label: "最小", value: "min" },
  { label: "最大", value: "max" },
];
const chartSelectOptions = computed(() => charts.value.map((c) => ({ label: c.name, value: c.id })));
const chartMap = computed(() => {
  const m: Record<number, Chart> = {};
  charts.value.forEach((c) => (m[c.id] = c));
  return m;
});

function chartById(id: number): Chart | undefined {
  return chartMap.value[id];
}
function chartName(id: number) {
  return chartMap.value[id]?.name || `图表 ${id}`;
}

async function load() {
  try {
    charts.value = await chartApi.list();
    dashboards.value = await chartApi.dashboards();
    for (const c of charts.value) loadChartData(c.id);
  } catch (e) {
    message.error((e as Error).message);
  }
}

async function loadChartData(id: number) {
  try {
    chartData[id] = await chartApi.data(id);
  } catch {
    chartData[id] = null;
  }
}

function openCreate() {
  editingChart.value = null;
  Object.assign(chartForm, { name: "", datasource_id: connections.currentDsId, sql_text: "", chart_type: "bar", x_column: "", y_column: "", aggregation: "none" });
  chartModal.value = true;
}

function openEdit(c: Chart) {
  editingChart.value = c;
  Object.assign(chartForm, {
    name: c.name,
    datasource_id: c.datasource_id,
    sql_text: c.sql_text,
    chart_type: c.chart_type,
    x_column: c.x_column,
    y_column: c.y_column,
    aggregation: c.aggregation,
  });
  chartModal.value = true;
}

async function previewChart() {
  if (!chartForm.datasource_id) {
    message.warning("请选择数据源");
    return;
  }
  if (!chartForm.sql_text.trim()) {
    message.warning("请填写 SQL");
    return;
  }
  previewLoading.value = true;
  try {
    const res = await sqlApi.execute(chartForm.datasource_id, chartForm.sql_text);
    if (res.need_confirm) {
      message.warning("预览仅支持只读查询");
      return;
    }
    previewData.value = { columns: res.columns, rows: res.rows };
    previewChartObj.value = {
      id: -1,
      name: "预览",
      datasource_id: chartForm.datasource_id,
      sql_text: chartForm.sql_text,
      chart_type: chartForm.chart_type,
      x_column: chartForm.x_column,
      y_column: chartForm.y_column,
      aggregation: chartForm.aggregation,
      options: "{}",
    };
    previewShow.value = true;
  } catch (e) {
    message.error((e as Error).message);
  } finally {
    previewLoading.value = false;
  }
}

async function saveChart() {
  if (!chartForm.name) {
    message.warning("请输入图表名称");
    return;
  }
  chartSaving.value = true;
  try {
    if (editingChart.value) {
      await chartApi.update(editingChart.value.id, { ...chartForm });
      message.success("更新成功");
    } else {
      await chartApi.create({ ...chartForm });
      message.success("创建成功");
    }
    chartModal.value = false;
    await load();
  } catch (e) {
    message.error((e as Error).message);
  } finally {
    chartSaving.value = false;
  }
}

async function removeChart(id: number) {
  try {
    await chartApi.remove(id);
    message.success("已删除");
    await load();
  } catch (e) {
    message.error((e as Error).message);
  }
}

function openDashboardCreate() {
  dashForm.name = "";
  dashForm.chart_ids = [];
  dashModal.value = true;
}

async function saveDashboard() {
  if (!dashForm.name) {
    message.warning("请输入名称");
    return;
  }
  try {
    await chartApi.createDashboard({ name: dashForm.name, chart_ids: dashForm.chart_ids });
    dashModal.value = false;
    message.success("创建成功");
    await load();
  } catch (e) {
    message.error((e as Error).message);
  }
}

async function removeDashboard(id: number) {
  try {
    await chartApi.deleteDashboard(id);
    message.success("已删除");
    await load();
  } catch (e) {
    message.error((e as Error).message);
  }
}

function viewDashboard(d: Dashboard) {
  viewingDashboard.value = d;
  viewDash.value = true;
  for (const cid of d.chart_ids) loadChartData(cid);
}

async function shareDashboard(d: Dashboard) {
  try {
    const r = await chartApi.shareDashboard(d.id);
    shareUrl.value = `${window.location.origin}${r.share_url}`;
    shareShow.value = true;
    await load();
  } catch (e) {
    message.error((e as Error).message);
  }
}

function copyShare() {
  navigator.clipboard?.writeText(shareUrl.value).then(() => message.success("已复制链接"));
}

onMounted(async () => {
  await connections.load();
  await load();
});
</script>

<style scoped>
.reports-view {
  padding: 16px;
  height: 100%;
  overflow: auto;
}
.toolbar {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 16px;
}
.card-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}
.chart-sql {
  margin-top: 8px;
  font-size: 12px;
  color: #888;
  font-family: monospace;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.dash-meta {
  font-size: 13px;
  color: #666;
}
</style>

