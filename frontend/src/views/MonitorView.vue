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

    </n-tabs>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import type { DatasourceStat, MonitorOverview, SchemaDiffResult, SchemaTableDiff, SlowQueryItem } from "../api";
import { monitorApi } from "../api";
import { useAuthStore } from "../stores/auth";
import { useConnectionsStore } from "../stores/connections";
import AuditView from "./AuditView.vue";

const connections = useConnectionsStore();
const auth = useAuthStore();
const canViewMonitor = computed(() => auth.hasPermission("monitor"));
const canViewAudit = computed(() => auth.hasPermission("audit"));
const activeTab = ref(canViewMonitor.value ? "overview" : "audit");
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

const dsOptions = computed(() => connections.list.map((c) => ({ label: c.name, value: c.id })));

onMounted(async () => {
  await connections.load();
  if (canViewMonitor.value) {
    loadOverview();
    loadSlow(1, true);
  }
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
    title: "类型/长度变化",
    key: "changed_columns",
    render: (row: SchemaTableDiff) =>
      row.changed_columns.length
        ? row.changed_columns
            .map((c) => `${c.column}: ${formatType(c.source_type, c.source_length)} → ${formatType(c.target_type, c.target_length)}`)
            .join("; ")
        : "—",
  },
];

function formatType(type: string, length?: string) {
  const base = type || "—";
  return length ? `${base}(${length})` : base;
}
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
</style>
