<template>
  <div class="monitor-view">
    <n-tabs v-model:value="activeTab" type="line" size="medium">
      <n-tab-pane v-if="canViewMonitor" name="overview" tab="连接概览">
        <div class="toolbar">
          <n-button size="small" type="primary" @click="loadOverview">刷新</n-button>
          <span class="hint">基于执行历史统计（query_history）</span>
        </div>
        <n-descriptions v-if="overview" label-placement="left" :column="3" size="small" style="margin-bottom: 12px">
          <n-descriptions-item label="累计查询">{{ overview.total_queries }}</n-descriptions-item>
          <n-descriptions-item label="今日查询">{{ overview.today_queries }}</n-descriptions-item>
          <n-descriptions-item label="数据源数">{{ overview.datasources.length }}</n-descriptions-item>
        </n-descriptions>
        <n-data-table :columns="overviewColumns" :data="overview?.datasources || []" size="small" :loading="loadingOverview" :bordered="false" />
      </n-tab-pane>

      <n-tab-pane v-if="canViewAudit" name="audit" tab="审计日志">
        <AuditView />
      </n-tab-pane>

      <n-tab-pane v-if="canViewMonitor" name="slow" tab="慢查询">
        <div class="toolbar">
          <span class="hint">耗时 ≥</span>
          <n-input-number v-model:value="thresholdMs" :min="1" size="small" style="width: 150px" />
          <span class="hint">ms</span>
          <n-button size="small" type="primary" @click="loadSlow(1, true)">查询</n-button>
        </div>
        <n-data-table :columns="slowColumns" :data="slowItems" size="small" :loading="loadingSlow" :bordered="false" :max-height="520" />
        <div v-if="slowTotal > slowItems.length" style="text-align: center; padding: 10px">
          <n-button size="tiny" text type="primary" @click="loadSlow(slowPage + 1)">加载更多（{{ slowItems.length }}/{{ slowTotal }}）</n-button>
        </div>
      </n-tab-pane>

      <n-tab-pane v-if="canViewMonitor" name="diff" tab="表结构对比">
        <div class="toolbar">
          <n-select v-model:value="diffForm.source_ds_id" :options="dsOptions" placeholder="源数据源" size="small" style="width: 240px" clearable />
          <n-select v-model:value="diffForm.target_ds_id" :options="dsOptions" placeholder="目标数据源" size="small" style="width: 240px" clearable />
          <n-button size="small" type="primary" :loading="loadingDiff" :disabled="!diffForm.source_ds_id || !diffForm.target_ds_id" @click="runDiff">对比</n-button>
        </div>
        <template v-if="diffResult">
          <n-alert
            v-if="!diffResult.only_source.length && !diffResult.only_target.length && !diffResult.table_diffs.length"
            type="success"
            title="两个数据源结构一致"
          />
          <template v-else>
            <div v-if="diffResult.only_source.length" class="diff-block">
              <div class="diff-title">仅存在于源库</div>
              <n-tag v-for="t in diffResult.only_source" :key="t" size="small" style="margin-right: 6px">{{ t }}</n-tag>
            </div>
            <div v-if="diffResult.only_target.length" class="diff-block">
              <div class="diff-title">仅存在于目标库</div>
              <n-tag v-for="t in diffResult.only_target" :key="t" size="small" type="warning" style="margin-right: 6px">{{ t }}</n-tag>
            </div>
            <n-data-table v-if="diffResult.table_diffs.length" :columns="diffColumns" :data="diffResult.table_diffs" size="small" :bordered="false" />
          </template>
        </template>
      </n-tab-pane>

      <n-tab-pane v-if="canViewSchedule" name="schedule" tab="定时任务">
        <div class="toolbar">
          <n-button size="small" type="primary" @click="openScheduleModal">新建任务</n-button>
          <n-button size="small" @click="loadSchedules">刷新</n-button>
          <span class="hint">按间隔周期导出报表/订阅推送（复用导出服务）</span>
        </div>
        <n-data-table :columns="scheduleColumns" :data="scheduleItems" size="small" :loading="loadingSchedule" :bordered="false" />
        <n-modal v-model:show="scheduleModalShow" preset="card" title="新建定时任务" style="width: 560px">
          <div class="schedule-form">
            <div class="form-row">
              <span class="form-label">名称</span>
              <n-input v-model:value="scheduleForm.name" placeholder="任务名称" />
            </div>
            <div class="form-row">
              <span class="form-label">数据源</span>
              <n-select v-model:value="scheduleForm.datasource_id" :options="dsOptions" placeholder="选择数据源" />
            </div>
            <div class="form-row">
              <span class="form-label">SQL</span>
              <n-input v-model:value="scheduleForm.sql_text" type="textarea" :rows="4" placeholder="SELECT ..." />
            </div>
            <div class="form-row">
              <span class="form-label">格式</span>
              <n-select v-model:value="scheduleForm.format" :options="[{ label: 'CSV', value: 'csv' }, { label: 'Excel', value: 'xlsx' }, { label: 'JSON', value: 'json' }]" />
            </div>
            <div class="form-row">
              <span class="form-label">间隔(分钟)</span>
              <n-input-number v-model:value="scheduleForm.interval_minutes" :min="1" style="width: 160px" />
            </div>
            <div class="form-row">
              <span class="form-label">启用</span>
              <n-switch v-model:value="scheduleForm.enabled" />
            </div>
          </div>
          <template #footer>
            <div style="text-align: right">
              <n-button size="small" style="margin-right: 8px" @click="scheduleModalShow = false">取消</n-button>
              <n-button size="small" type="primary" :loading="savingSchedule" @click="createSchedule">创建</n-button>
            </div>
          </template>
        </n-modal>
      </n-tab-pane>

    </n-tabs>
  </div>
</template>

<script setup lang="ts">
import { computed, h, onMounted, reactive, ref } from "vue";
import { NButton, NSwitch, NTag, useMessage } from "naive-ui";
import type { DatasourceStat, MonitorOverview, SchemaDiffResult, SchemaTableDiff, ScheduleTask, SlowQueryItem } from "../api";
import { monitorApi, scheduleApi } from "../api";
import { useAuthStore } from "../stores/auth";
import { useConnectionsStore } from "../stores/connections";
import AuditView from "./AuditView.vue";

const connections = useConnectionsStore();
const auth = useAuthStore();
const message = useMessage();
const canViewMonitor = computed(() => auth.hasPermission("monitor"));
const canViewAudit = computed(() => auth.hasPermission("audit"));
const canViewSchedule = computed(() => auth.hasPermission("reports_manage"));
const activeTab = ref(canViewMonitor.value ? "overview" : canViewSchedule.value ? "schedule" : "audit");
const overview = ref<MonitorOverview | null>(null);
const loadingOverview = ref(false);
const thresholdMs = ref(1000);
const slowItems = ref<SlowQueryItem[]>([]);
const slowTotal = ref(0);
const slowPage = ref(1);
const loadingSlow = ref(false);
const diffForm = reactive<{ source_ds_id: number | null; target_ds_id: number | null }>({ source_ds_id: null, target_ds_id: null });
const diffResult = ref<SchemaDiffResult | null>(null);
const loadingDiff = ref(false);
const scheduleItems = ref<ScheduleTask[]>([]);
const loadingSchedule = ref(false);
const scheduleModalShow = ref(false);
const savingSchedule = ref(false);
const scheduleForm = reactive({
  name: "",
  datasource_id: null as number | null,
  sql_text: "",
  format: "csv",
  interval_minutes: 1440,
  enabled: true,
});

const dsOptions = computed(() => connections.list.map((c) => ({ label: c.name, value: c.id })));

onMounted(async () => {
  await connections.load();
  if (canViewMonitor.value) {
    loadOverview();
    loadSlow(1, true);
  }
  if (canViewSchedule.value) loadSchedules();
});

async function loadOverview() {
  loadingOverview.value = true;
  try {
    overview.value = await monitorApi.overview();
  } finally {
    loadingOverview.value = false;
  }
}

async function loadSlow(page: number, reset = false) {
  loadingSlow.value = true;
  try {
    const data = await monitorApi.slowQueries({ threshold_ms: thresholdMs.value, page, page_size: 20 });
    slowItems.value = reset ? data.list : [...slowItems.value, ...data.list];
    slowTotal.value = data.total;
    slowPage.value = page;
  } finally {
    loadingSlow.value = false;
  }
}

async function runDiff() {
  if (!diffForm.source_ds_id || !diffForm.target_ds_id) return;
  loadingDiff.value = true;
  try {
    diffResult.value = await monitorApi.schemaDiff({
      source_ds_id: diffForm.source_ds_id,
      target_ds_id: diffForm.target_ds_id,
    });
  } finally {
    loadingDiff.value = false;
  }
}

async function loadSchedules() {
  loadingSchedule.value = true;
  try {
    scheduleItems.value = await scheduleApi.list();
  } catch {
    message.warning("加载定时任务失败（需要报表维护权限）");
  } finally {
    loadingSchedule.value = false;
  }
}

function openScheduleModal() {
  scheduleForm.name = "";
  scheduleForm.datasource_id = null;
  scheduleForm.sql_text = "";
  scheduleForm.format = "csv";
  scheduleForm.interval_minutes = 1440;
  scheduleForm.enabled = true;
  scheduleModalShow.value = true;
}

async function createSchedule() {
  if (!scheduleForm.name.trim() || !scheduleForm.sql_text.trim() || !scheduleForm.datasource_id) {
    message.warning("请填写名称、SQL 与数据源");
    return;
  }
  savingSchedule.value = true;
  try {
    await scheduleApi.create({ ...scheduleForm });
    message.success("已创建");
    scheduleModalShow.value = false;
    loadSchedules();
  } catch {
    message.error("创建失败");
  } finally {
    savingSchedule.value = false;
  }
}

async function toggleSchedule(row: ScheduleTask) {
  try {
    await scheduleApi.update(row.id, { enabled: row.enabled });
    message.success(row.enabled ? "已启用" : "已停用");
  } catch {
    row.enabled = !row.enabled;
    message.error("操作失败");
  }
}

async function runScheduleNow(row: ScheduleTask) {
  try {
    const res = await scheduleApi.run(row.id);
    message.success(res.message || "执行完成");
    loadSchedules();
  } catch {
    message.error("执行失败");
  }
}

function downloadSchedule(row: ScheduleTask) {
  scheduleApi.download(row.id, row.last_file || `schedule_${row.id}.csv`);
}

async function removeSchedule(row: ScheduleTask) {
  try {
    await scheduleApi.remove(row.id);
    message.success("已删除");
    loadSchedules();
  } catch {
    message.error("删除失败");
  }
}

const overviewColumns = [
  { title: "数据源", key: "name" },
  { title: "类型", key: "db_type", width: 110 },
  { title: "查询次数", key: "query_count", width: 110 },
  { title: "平均耗时(ms)", key: "avg_duration_ms", width: 120 },
  { title: "最大耗时(ms)", key: "max_duration_ms", width: 120 },
  {
    title: "成功率",
    key: "success_rate",
    width: 100,
    render: (row: DatasourceStat) => `${row.success_rate}%`,
  },
  {
    title: "最近执行",
    key: "last_executed_at",
    render: (row: DatasourceStat) => (row.last_executed_at ? new Date(row.last_executed_at).toLocaleString() : "—"),
  },
];

const slowColumns = [
  { title: "数据源", key: "datasource_name", width: 150 },
  { title: "耗时(ms)", key: "duration_ms", width: 100, sortable: true },
  { title: "行数", key: "row_count", width: 80 },
  { title: "状态", key: "status", width: 90 },
  {
    title: "SQL",
    key: "sql_text",
    ellipsis: { tooltip: true },
  },
  {
    title: "时间",
    key: "created_at",
    width: 170,
    render: (row: SlowQueryItem) => (row.created_at ? new Date(row.created_at).toLocaleString() : "—"),
  },
];

const diffColumns = [
  { title: "表", key: "table", width: 160 },
  {
    title: "目标新增列",
    key: "added_columns",
    render: (row: SchemaTableDiff) => (row.added_columns.length ? row.added_columns.join(", ") : "—"),
  },
  {
    title: "目标缺少列",
    key: "removed_columns",
    render: (row: SchemaTableDiff) => (row.removed_columns.length ? row.removed_columns.join(", ") : "—"),
  },
  {
    title: "类型变化",
    key: "changed_columns",
    render: (row: SchemaTableDiff) =>
      row.changed_columns.length
        ? row.changed_columns.map((c) => `${c.column}: ${c.source_type} → ${c.target_type}`).join("; ")
        : "—",
  },
];

const scheduleColumns = [
  { title: "名称", key: "name", width: 150 },
  {
    title: "数据源",
    key: "datasource_id",
    width: 140,
    render: (row: ScheduleTask) => {
      const ds = connections.list.find((c) => c.id === row.datasource_id);
      return ds ? ds.name : row.datasource_id;
    },
  },
  { title: "格式", key: "format", width: 80 },
  {
    title: "间隔",
    key: "interval_minutes",
    width: 110,
    render: (row: ScheduleTask) =>
      row.interval_minutes >= 1440 ? `${row.interval_minutes / 1440} 天` : `${row.interval_minutes} 分钟`,
  },
  {
    title: "启用",
    key: "enabled",
    width: 80,
    render: (row: ScheduleTask) =>
      h(NSwitch, {
        value: row.enabled,
        size: "small",
        "onUpdate:value": (v: boolean) => {
          row.enabled = v;
          toggleSchedule(row);
        },
      }),
  },
  {
    title: "上次执行",
    key: "last_run_at",
    width: 160,
    render: (row: ScheduleTask) => (row.last_run_at ? new Date(row.last_run_at).toLocaleString() : "—"),
  },
  { title: "状态", key: "last_status", width: 140, ellipsis: { tooltip: true } },
  {
    title: "下次执行",
    key: "next_run_at",
    width: 160,
    render: (row: ScheduleTask) => (row.next_run_at ? new Date(row.next_run_at).toLocaleString() : "—"),
  },
  {
    title: "操作",
    key: "actions",
    width: 210,
    render: (row: ScheduleTask) =>
      h("div", { style: "display: flex; gap: 6px" }, [
        h(NButton, { size: "tiny", onClick: () => runScheduleNow(row) }, { default: () => "执行" }),
        row.last_file
          ? h(NButton, { size: "tiny", secondary: true, onClick: () => downloadSchedule(row) }, { default: () => "下载" })
          : null,
        h(NButton, { size: "tiny", type: "error", quaternary: true, onClick: () => removeSchedule(row) }, { default: () => "删除" }),
      ]),
  },
];
</script>

<style scoped>
.monitor-view {
  padding: 12px 16px;
}
.toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}
.hint {
  font-size: 12px;
  color: #888;
}
.diff-block {
  margin-bottom: 12px;
}
.diff-title {
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 6px;
}
.schedule-form .form-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}
.schedule-form .form-label {
  width: 80px;
  flex-shrink: 0;
  font-size: 13px;
  color: #888;
}
</style>
