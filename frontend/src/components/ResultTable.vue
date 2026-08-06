<template>
  <div class="result-table">
    <div v-if="result" class="result-meta">
      <n-tag size="small" type="info">{{ result.operation_type }}</n-tag>
      <span v-if="result.total_rows !== undefined">共 {{ result.total_rows }} 行</span>
      <span v-if="result.affected_rows !== undefined">影响 {{ result.affected_rows }} 行</span>
      <span v-if="result.duration_ms !== undefined">耗时 {{ result.duration_ms }} ms</span>
      <span v-if="result.truncated" class="truncated">结果已截断</span>
      <span style="flex: 1"></span>
      <n-button size="tiny" @click="exportCsv">CSV</n-button>
      <n-button size="tiny" @click="exportExcel">Excel</n-button>
      <n-button size="tiny" @click="exportJson">JSON</n-button>
    </div>
    <n-data-table
      v-if="result && result.columns && result.columns.length"
      size="small"
      :columns="tableColumns"
      :data="tableRows"
      :max-height="420"
      :scroll-x="1200"
    />
    <n-empty v-else-if="result" description="无结果" style="padding: 40px 0" />
    <n-alert v-if="error" type="error" :title="error" closable style="margin-top: 8px" @close="error = ''" />
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useMessage } from "naive-ui";
import type { SqlResult } from "../api";
import { exportApi } from "../api";
import { useConnectionsStore } from "../stores/connections";

const props = defineProps<{ result: SqlResult | null; error: string }>();
const message = useMessage();
const connections = useConnectionsStore();
const error = ref(props.error);

watch(
  () => props.error,
  (v) => (error.value = v),
);

const tableColumns = computed(() =>
  (props.result?.columns || []).map((col, i) => ({
    title: col,
    key: `c${i}`,
    ellipsis: { tooltip: true },
    render: (row: Record<string, unknown>) => String(row[`c${i}`] ?? ""),
  })),
);

const tableRows = computed(() => {
  const cols = props.result?.columns || [];
  return (props.result?.rows || []).map((row, r) => {
    const obj: Record<string, unknown> = { __row: r + 1 };
    cols.forEach((c, i) => (obj[`c${i}`] = row[i]));
    return obj;
  });
});

async function doExport(format: string) {
  if (!props.result) return;
  const dsId = connections.currentDsId;
  if (!dsId) {
    message.warning("请先选择数据源");
    return;
  }
  // 结果导出需要 SQL：使用最近执行的 SQL
  const sql = (props.result.sql_text as string) || lastSql || "";
  if (!sql) {
    message.warning("缺少 SQL，无法导出（请从工作台执行查询）");
    return;
  }
  try {
    await exportApi.result(dsId, sql, format);
    message.success("导出成功");
  } catch (e) {
    message.error((e as Error).message);
  }
}

let lastSql = "";
function exportCsv() {
  doExport("csv");
}
function exportExcel() {
  doExport("excel");
}
function exportJson() {
  doExport("json");
}

defineExpose({ setLastSql: (sql: string) => (lastSql = sql) });
</script>

<style scoped>
.result-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 6px 0;
  font-size: 12px;
  color: #888;
}
.truncated {
  color: #e6a23c;
}
</style>

