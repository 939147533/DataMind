<template>
  <div class="audit-view">
    <div class="toolbar">
      <n-input v-model:value="actionType" placeholder="操作类型（login / execute_sql / agent_action）" clearable style="width: 280px" @update:value="reload" />
      <n-select v-model:value="status" :options="statusOptions" placeholder="状态" clearable style="width: 140px" @update:value="reload" />
      <div style="flex: 1"></div>
      <n-button size="small" @click="reload">刷新</n-button>
    </div>
    <n-data-table :columns="columns" :data="items" :loading="loading" :bordered="false" size="small" />
    <div class="pager">
      <n-pagination v-model:page="page" :item-count="total" :page-size="pageSize" @update:page="load" />
      <span class="total">共 {{ total }} 条</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { h, onMounted, ref } from "vue";
import { NTag, useMessage } from "naive-ui";
import { auditApi } from "../api";
import type { AuditItem } from "../api";

const message = useMessage();
const items = ref<AuditItem[]>([]);
const total = ref(0);
const page = ref(1);
const pageSize = 20;
const loading = ref(false);
const actionType = ref("");
const status = ref<string | null>(null);

const statusOptions = [
  { label: "成功", value: "success" },
  { label: "失败", value: "failed" },
  { label: "待确认", value: "pending" },
  { label: "已批准", value: "approved" },
  { label: "已拒绝", value: "rejected" },
];

const actionLabels: Record<string, string> = {
  login: "登录",
  execute_sql: "执行 SQL",
  agent_action: "AI Agent",
};

function statusTag(status: string) {
  const type = status === "success" || status === "approved" ? "success" : status === "failed" ? "error" : status === "pending" ? "warning" : "default";
  return h(NTag, { size: "small", type }, { default: () => status });
}

const columns = [
  { title: "ID", key: "id", width: 60 },
  { title: "时间", key: "created_at", width: 170 },
  {
    title: "操作",
    key: "action_type",
    width: 110,
    render: (row: AuditItem) => actionLabels[row.action_type] || row.action_type,
  },
  { title: "类型", key: "operation_type", width: 90 },
  { title: "状态", key: "status", width: 100, render: (row: AuditItem) => statusTag(row.status) },
  { title: "数据源", key: "datasource_id", width: 80 },
  { title: "用户", key: "user_id", width: 70 },
  { title: "IP", key: "client_ip", width: 130 },
  { title: "内容 / SQL", key: "sql_text", ellipsis: { tooltip: true } },
];

async function load() {
  loading.value = true;
  try {
    const data = await auditApi.logs({
      page: page.value,
      page_size: pageSize,
      action_type: actionType.value || undefined,
      status: status.value || undefined,
    });
    items.value = data.list;
    total.value = data.total;
  } catch (e) {
    message.error((e as Error).message);
  } finally {
    loading.value = false;
  }
}

function reload() {
  page.value = 1;
  load();
}

onMounted(load);
</script>

<style scoped>
.audit-view {
  padding: 16px;
}
.toolbar {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
  align-items: center;
}
.pager {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 12px;
  margin-top: 16px;
}
.total {
  font-size: 12px;
  color: #888;
}
</style>

