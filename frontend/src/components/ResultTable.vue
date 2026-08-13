<template>
  <div class="result-table">
    <div v-if="result" class="result-meta">
      <n-tag size="small" type="info">{{ result.operation_type }}</n-tag>
      <span v-if="result.total_rows !== undefined">共 {{ result.total_rows }} 行</span>
      <span v-if="result.affected_rows !== undefined">影响 {{ result.affected_rows }} 行</span>
      <span v-if="result.duration_ms !== undefined">耗时 {{ result.duration_ms }} ms</span>
      <span v-if="result.truncated" class="truncated">结果已截断</span>
      <span v-if="editable" class="edit-hint">双击单元格编辑</span>
      <span style="flex: 1"></span>
      <n-button v-if="editable" size="tiny" type="primary" ghost @click="openInsert">＋ 新增行</n-button>
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
      virtual-scroll
    />
    <n-empty v-else-if="result" description="无结果" style="padding: 40px 0" />
    <n-alert v-if="error" type="error" :title="error" closable style="margin-top: 8px" @close="error = ''" />

    <!-- 单元格编辑 -->
    <n-modal v-model:show="editState.show" preset="card" title="编辑单元格" style="width: 480px">
      <n-form label-placement="left" label-width="100px">
        <n-form-item label="列名">
          <n-input :value="editState.col" disabled />
        </n-form-item>
        <n-form-item label="当前值">
          <n-input :value="String(editState.oldValue ?? '')" disabled />
        </n-form-item>
        <n-form-item label="新值">
          <n-input v-model:value="editState.value" @keydown.enter="saveEdit" />
        </n-form-item>
      </n-form>
      <template #footer>
        <div style="display: flex; justify-content: flex-end; gap: 8px">
          <n-button size="small" @click="editState.show = false">取消</n-button>
          <n-button size="small" type="primary" :loading="mutating" @click="saveEdit">保存</n-button>
        </div>
      </template>
    </n-modal>

    <!-- 新增行 -->
    <n-modal v-model:show="insertState.show" preset="card" title="新增行" style="width: 560px">
      <n-form label-placement="left" label-width="140px">
        <n-form-item v-for="c in insertColumns" :key="c.name" :label="c.name">
          <n-input v-model:value="insertValues[c.name]" placeholder="留空表示 NULL" />
        </n-form-item>
      </n-form>
      <template #footer>
        <div style="display: flex; justify-content: flex-end; gap: 8px">
          <n-button size="small" @click="insertState.show = false">取消</n-button>
          <n-button size="small" type="primary" :loading="mutating" @click="saveInsert">保存</n-button>
        </div>
      </template>
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, h, ref, watch } from "vue";
import { NButton, useMessage } from "naive-ui";
import type { ColumnInfo, SqlResult } from "../api";
import { exportApi, metadataApi } from "../api";
import { useConnectionsStore } from "../stores/connections";

const props = defineProps<{ result: SqlResult | null; error: string }>();
const emit = defineEmits<{ (e: "edit-confirm", result: SqlResult): void; (e: "reload"): void }>();
const message = useMessage();
const connections = useConnectionsStore();
const error = ref(props.error);
const mutating = ref(false);

watch(
  () => props.error,
  (v) => (error.value = v),
);

// ---------- 简单表查询识别（SELECT * FROM table） ----------
const simpleTable = computed<{ table: string; schema: string } | null>(() => {
  const sql = (props.result?.sql_text || lastSql.value || "").trim();
  const m = sql.match(/^\s*select\s+\*\s+from\s+([`"']?)([\w.]+)\1/i);
  if (!m) return null;
  const parts = m[2].split(".");
  return parts.length === 2 ? { schema: parts[0], table: parts[1] } : { schema: "", table: m[2] };
});

const lastSql = ref("");

const columnMeta = ref<ColumnInfo[]>([]);
const pkColumns = ref<string[]>([]);

watch(
  () => simpleTable.value,
  async (t) => {
    columnMeta.value = [];
    pkColumns.value = [];
    if (!t || !connections.currentDsId) return;
    try {
      const cols = await metadataApi.columns(connections.currentDsId, t.table, t.schema || undefined);
      columnMeta.value = cols;
      pkColumns.value = cols.filter((c) => c.primary_key).map((c) => c.name);
    } catch {
      /* 非可编辑查询忽略 */
    }
  },
  { immediate: true },
);

const editable = computed(() => !!simpleTable.value && pkColumns.value.length > 0 && !!connections.currentDsId);

function colIndex(name: string): number {
  return (props.result?.columns || []).indexOf(name);
}

function rowValue(row: Record<string, unknown>, name: string): unknown {
  const i = colIndex(name);
  return i >= 0 ? row[`c${i}`] : undefined;
}

const tableColumns = computed(() => {
  const cols = (props.result?.columns || []).map((col, i) => ({
    title: col,
    key: `c${i}`,
    ellipsis: { tooltip: true },
    render: (row: Record<string, unknown>) => {
      const text = String(row[`c${i}`] ?? "");
      if (!editable.value || pkColumns.value.includes(col)) return text;
      return h("span", { class: "cell-edit", onDblclick: () => openEdit(row, col) }, { default: () => text });
    },
  }));
  if (editable.value) {
    cols.push({
      title: "操作",
      key: "__ops",
      width: 90,
      render: (row: Record<string, unknown>) =>
        h(
          NButton,
          {
            size: "tiny",
            text: true,
            type: "error",
            onClick: () => removeRow(row),
          },
          { default: () => "删除" },
        ),
    });
  }
  return cols;
});

const tableRows = computed(() => {
  const cols = props.result?.columns || [];
  return (props.result?.rows || []).map((row, r) => {
    const obj: Record<string, unknown> = { __row: r + 1 };
    cols.forEach((c, i) => (obj[`c${i}`] = row[i]));
    return obj;
  });
});

// ---------- 单元格编辑 ----------
const editState = ref<{ show: boolean; col: string; oldValue: unknown; value: string; row: Record<string, unknown> }>({
  show: false,
  col: "",
  oldValue: null,
  value: "",
  row: {},
});

function openEdit(row: Record<string, unknown>, col: string) {
  editState.value = { show: true, col, oldValue: row[`c${colIndex(col)}`], value: String(row[`c${colIndex(col)}`] ?? ""), row };
}

async function applyMutation(promise: Promise<SqlResult>): Promise<boolean> {
  try {
    const result = await promise;
    if (result?.need_confirm && result.execution_id) {
      emit("edit-confirm", result);
    } else {
      emit("reload");
    }
    return true;
  } catch (e) {
    message.error((e as Error).message);
    return false;
  }
}

async function saveEdit() {
  const st = editState.value;
  const t = simpleTable.value;
  if (!st.show || !t || !connections.currentDsId) return;
  mutating.value = true;
  try {
    const where: Record<string, unknown> = {};
    for (const pk of pkColumns.value) where[pk] = rowValue(st.row, pk);
    const okFlag = await applyMutation(
      metadataApi.updateRow(connections.currentDsId, t.table, {
        schema_name: t.schema,
        set_values: { [st.col]: st.value },
        where,
      }),
    );
    if (okFlag) st.show = false;
  } finally {
    mutating.value = false;
  }
}

async function removeRow(row: Record<string, unknown>) {
  const t = simpleTable.value;
  if (!t || !connections.currentDsId) return;
  const where: Record<string, unknown> = {};
  for (const pk of pkColumns.value) where[pk] = rowValue(row, pk);
  await applyMutation(metadataApi.deleteRow(connections.currentDsId, t.table, { schema_name: t.schema, where }));
}

// ---------- 新增行 ----------
const insertState = ref<{ show: boolean }>({ show: false });
const insertValues = ref<Record<string, string>>({});

const insertColumns = computed(() => columnMeta.value.filter((c) => !(c.primary_key && c.auto_increment)));

function openInsert() {
  insertValues.value = {};
  for (const c of insertColumns.value) insertValues.value[c.name] = "";
  insertState.value.show = true;
}

async function saveInsert() {
  const t = simpleTable.value;
  if (!t || !connections.currentDsId) return;
  mutating.value = true;
  try {
    const values: Record<string, unknown> = {};
    for (const c of insertColumns.value) {
      const v = (insertValues.value[c.name] || "").trim();
      if (v !== "") values[c.name] = v;
    }
    const okFlag = await applyMutation(
      metadataApi.insertRow(connections.currentDsId, t.table, { schema_name: t.schema, values }),
    );
    if (okFlag) insertState.value.show = false;
  } finally {
    mutating.value = false;
  }
}

// ---------- 导出 ----------
async function doExport(format: string) {
  if (!props.result) return;
  const dsId = connections.currentDsId;
  if (!dsId) {
    message.warning("请先选择数据源");
    return;
  }
  const sql = (props.result.sql_text as string) || lastSql.value || "";
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

function exportCsv() {
  doExport("csv");
}
function exportExcel() {
  doExport("excel");
}
function exportJson() {
  doExport("json");
}

defineExpose({ setLastSql: (sql: string) => (lastSql.value = sql) });
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
.edit-hint {
  color: #18a058;
}
.cell-edit {
  cursor: text;
}
</style>
