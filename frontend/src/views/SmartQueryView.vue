<template>
  <div class="smart-query-view">
    <div class="sq-toolbar">
      <n-select v-model:value="dsId" :options="dsOptions" placeholder="选择数据源" size="small" clearable style="width: 240px" />
      <n-select v-if="modelOptions.length" v-model:value="modelConfigId" :options="modelOptions" placeholder="选择模型" size="small" style="width: 200px" />
      <n-select v-model:value="activeSessionId" :options="sessionOptions" placeholder="选择对话" size="small" style="width: 170px" />
      <n-button size="small" @click="newSession">新建对话</n-button>
      <n-button size="small" secondary type="error" :disabled="!agent.activeSessionId" @click="deleteCurrent">删除</n-button>
      <div style="flex: 1"></div>
      <n-tag v-if="dsName" size="small" type="info">{{ dsName }}</n-tag>
    </div>

    <div ref="msgBox" class="sq-messages">
      <div v-if="!agent.items.length" class="sq-empty">
        <div class="sq-empty-title">👋 你好，我是数据库 Agent</div>
        <p class="sq-empty-hint">用自然语言描述你的需求，AI 会自动生成查询并返回结果：</p>
        <div class="sq-examples">
          <n-tag v-for="ex in examples" :key="ex" size="small" round style="cursor: pointer" @click="useExample(ex)">{{ ex }}</n-tag>
        </div>
      </div>
      <template v-for="(item, idx) in agent.items" :key="idx">
        <div v-if="item.role === 'user'" class="msg user">{{ item.content }}</div>
        <div v-else-if="item.type === 'sql'" class="msg assistant">
          <div class="sql-block">
            <div class="sql-head"><span>生成的查询</span><n-button size="tiny" text type="primary" @click="copySql(item.content)">复制</n-button></div>
            <pre><code>{{ item.content }}</code></pre>
          </div>
        </div>
        <div v-else-if="item.type === 'tool'" class="msg assistant tool-msg">{{ item.content }}</div>
        <div v-else-if="item.type === 'result' && item.result" class="msg assistant">
          <n-data-table size="small" :columns="resultColumns(item.result)" :data="resultRows(item.result)" :max-height="300" :scroll-x="800" />
          <div class="result-actions">
            <span class="result-meta">共 {{ item.result.total_rows }} 行 · {{ item.result.duration_ms }} ms</span>
            <div style="flex: 1"></div>
            <n-button size="tiny" @click="exportResult(item, 'csv')">CSV</n-button>
            <n-button size="tiny" @click="exportResult(item, 'excel')">Excel</n-button>
            <n-button size="tiny" @click="exportResult(item, 'json')">JSON</n-button>
          </div>
        </div>
        <div v-else-if="item.type === 'chart' && item.chart" class="msg assistant">
          <div class="chart-box">
            <div class="chart-title">{{ item.chart.title || "AI 生成图表" }}</div>
            <ChartCard v-if="chartRows(item) > 0" :chart="toChart(item)" :data="chartData(item)" />
            <div v-else-if="chartData(item)" class="chart-empty">查询结果为空，请调整问题重试</div>
            <div v-else class="chart-empty">图表数据未保存，请重新提问以生成图表</div>
            <div class="chart-actions">
              <n-button size="tiny" type="primary" @click="saveChart(item)">保存到可视化报表</n-button>
            </div>
          </div>
        </div>
        <div v-else-if="item.type === 'authz'" class="msg assistant">
          <n-alert type="warning" title="需要人工确认">该操作涉及数据变更，请在 SQL 工作台中由技术管理员确认执行。</n-alert>
        </div>
        <div v-else-if="item.role === 'assistant'" class="msg assistant">
          <span v-if="item.streaming" class="cursor">▍</span>
          {{ item.content }}
        </div>
      </template>
    </div>

    <div class="sq-input">
      <n-input
        v-model:value="input"
        type="textarea"
        :rows="2"
        placeholder="输入自然语言查询，Enter 发送，Shift+Enter 换行；例如：统计各订单状态的数量"
        :disabled="!agent.inputEnabled"
        @keydown="onKeydown"
      />
      <div class="input-actions">
        <span class="input-hint">{{ agent.streaming ? "正在生成…" : "AI 将自动生成并执行只读查询，结果可导出" }}</span>
        <n-button type="primary" :loading="agent.streaming" :disabled="!input.trim() || !dsId" @click="send">发送</n-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from "vue";
import { useMessage } from "naive-ui";
import type { DataTableColumns } from "naive-ui";
import type { AIConfig, Chart, SmartChartConfig, SqlResult } from "../api";
import { agentApi, configApi, connectionApi, exportApi } from "../api";
import { useAgentStore } from "../stores/agent";
import type { ChatItem } from "../stores/agent";
import ChartCard from "../components/ChartCard.vue";

const agent = useAgentStore();
const message = useMessage();
const input = ref("");
const msgBox = ref<HTMLElement>();
const dsId = ref<number | null>(agent.datasourceId);
const modelConfigId = ref<number | null>(agent.modelConfigId);
const aiConfigs = ref<AIConfig[]>([]);
const dsOptions = ref<{ label: string; value: number }[]>([]);

const dsName = computed(() => dsOptions.value.find((o) => o.value === dsId.value)?.label || "");
const modelOptions = computed(() =>
  aiConfigs.value.filter((c) => c.is_active).map((c) => ({ label: `${c.provider} · ${c.model_name}`, value: c.id })),
);
const activeSessionId = computed({
  get: () => agent.activeSessionId,
  set: (v) => {
    if (v) agent.selectSession(v);
  },
});
const sessionOptions = computed(() => agent.sessions.map((s) => ({ label: s.title || `对话 ${s.id}`, value: s.id })));

// 示例问题随数据源变化：银行库（oracle-free）给出业务示例，其他数据源给出通用示例
const examples = computed(() => {
  const name = dsName.value || "";
  if (name.includes("oracle-free") || name.includes("银行")) {
    return ["统计各交易渠道的交易笔数", "查询余额最高的10个账户及客户信息", "统计各分行的交易金额与笔数（生成图表）"];
  }
  return ["统计各订单状态的数量", "销售额最高的 5 个商品", "各品类订单金额占比（生成图表）"];
});

async function loadDatasources() {
  try {
    const data = await connectionApi.list({ page: 1, page_size: 100 });
    dsOptions.value = data.list.map((c) => ({ label: `${c.name} (${c.db_type})`, value: c.id }));
    const dsStillValid = dsOptions.value.some((o) => o.value === dsId.value);
    if (!dsStillValid && dsOptions.value.length) {
      const demo = dsOptions.value.find((o) => o.label.includes("sqlite"));
      dsId.value = (demo || dsOptions.value[0]).value;
    }
  } catch {
    dsOptions.value = [];
  }
}

async function loadModels() {
  try {
    aiConfigs.value = await configApi.listAi();
    const stillValid = modelOptions.value.some((o) => o.value === modelConfigId.value);
    if (!stillValid && modelOptions.value.length) {
      modelConfigId.value = modelOptions.value[0].value;
    }
  } catch {
    aiConfigs.value = [];
  }
}

onMounted(async () => {
  await Promise.all([agent.loadSessions(), loadDatasources(), loadModels()]);
});

function resultColumns(result: SqlResult): DataTableColumns {
  return (result.columns || []).map((c) => ({ title: c, key: c, ellipsis: { tooltip: true }, width: 140 }));
}

function resultRows(result: SqlResult): Record<string, unknown>[] {
  return (result.rows || []).map((r) => {
    const obj: Record<string, unknown> = {};
    (result.columns || []).forEach((c, i) => {
      obj[c] = r[i];
    });
    return obj;
  });
}

function toChart(item: ChatItem): Chart {
  const cfg = (item.chart as SmartChartConfig) || ({} as SmartChartConfig);
  const result = item.result as SqlResult;
  return {
    id: 0,
    name: cfg.title || "AI 生成图表",
    datasource_id: dsId.value,
    sql_text: result?.sql_text || "",
    chart_type: cfg.chart_type || "bar",
    x_column: cfg.x_column || "",
    y_column: cfg.y_column || "",
    aggregation: cfg.aggregation || "none",
    options: "{}",
  };
}

function chartData(item: ChatItem): { columns: string[]; rows: unknown[][] } | null {
  const result = item.result as SqlResult | undefined;
  return result ? { columns: result.columns, rows: result.rows } : null;
}

function chartRows(item: ChatItem): number {
  return chartData(item)?.rows.length ?? 0;
}

async function send() {
  const text = input.value.trim();
  if (!text) return;
  input.value = "";
  await agent.sendMessage(text, dsId.value, modelConfigId.value);
  scrollToBottom();
}

function useExample(ex: string) {
  input.value = ex;
  send();
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    send();
  }
}

async function newSession() {
  if (!dsId.value) {
    message.warning("请先选择数据源");
    return;
  }
  await agent.createSession(dsId.value, modelConfigId.value);
  scrollToBottom();
}

async function deleteCurrent() {
  if (!agent.activeSessionId) return;
  await agent.deleteSession(agent.activeSessionId);
}

async function exportResult(item: ChatItem, format: string) {
  const result = item.result as SqlResult;
  if (!result?.sql_text || !dsId.value) {
    message.warning("缺少可导出的查询");
    return;
  }
  try {
    await exportApi.result(dsId.value, result.sql_text, format);
    message.success("导出成功");
  } catch (e) {
    message.error((e as Error).message);
  }
}

async function saveChart(item: ChatItem) {
  if (!dsId.value) {
    message.warning("请先选择数据源");
    return;
  }
  const cfg = (item.chart as SmartChartConfig) || ({} as SmartChartConfig);
  const result = item.result as SqlResult;
  try {
    await agentApi.saveChart({
      name: cfg.title || "AI 生成图表",
      datasource_id: dsId.value,
      sql_text: result?.sql_text || "",
      chart_type: cfg.chart_type || "bar",
      x_column: cfg.x_column || "",
      y_column: cfg.y_column || "",
      aggregation: cfg.aggregation || "none",
    });
    message.success("已保存到可视化报表");
  } catch (e) {
    message.error((e as Error).message);
  }
}

async function copySql(sql: string) {
  try {
    await navigator.clipboard.writeText(sql);
    message.success("已复制");
  } catch {
    message.info("复制失败，请手动选择复制");
  }
}

function scrollToBottom() {
  nextTick(() => {
    if (msgBox.value) msgBox.value.scrollTop = msgBox.value.scrollHeight;
  });
}

watch(() => agent.items.length, scrollToBottom);

watch(dsId, (v) => {
  agent.datasourceId = v;
  if (v) localStorage.setItem("agent.datasourceId", String(v));
  else localStorage.removeItem("agent.datasourceId");
});
watch(modelConfigId, (v) => {
  agent.modelConfigId = v;
  if (v) localStorage.setItem("agent.modelConfigId", String(v));
  else localStorage.removeItem("agent.modelConfigId");
});
</script>

<style scoped>
.smart-query-view {
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: 12px 16px;
  box-sizing: border-box;
  gap: 10px;
}
.sq-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
  flex-wrap: wrap;
}
.sq-messages {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 8px 4px;
}
.sq-empty {
  margin: auto;
  text-align: center;
  color: #888;
}
.sq-empty-title {
  font-size: 18px;
  font-weight: 600;
  color: inherit;
  margin-bottom: 8px;
}
.sq-empty-hint {
  margin: 0 0 12px;
}
.sq-examples {
  display: flex;
  gap: 8px;
  justify-content: center;
  flex-wrap: wrap;
  max-width: 640px;
  margin: 0 auto;
}
.msg {
  max-width: 92%;
  border-radius: 8px;
  padding: 10px 12px;
  line-height: 1.6;
  font-size: 13px;
  white-space: pre-wrap;
  word-break: break-word;
}
.msg.user {
  align-self: flex-end;
  background: rgba(24, 160, 88, 0.12);
  border: 1px solid rgba(24, 160, 88, 0.25);
}
.msg.assistant {
  align-self: flex-start;
  background: rgba(128, 128, 128, 0.08);
  border: 1px solid rgba(128, 128, 128, 0.15);
}
.cursor {
  color: #18a058;
}
.sql-block {
  min-width: 320px;
}
.sql-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 12px;
  color: #888;
  margin-bottom: 6px;
}
.sql-block pre {
  margin: 0;
  background: rgba(0, 0, 0, 0.06);
  border-radius: 6px;
  padding: 10px;
  overflow: auto;
  max-height: 220px;
  font-size: 12px;
}
.result-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 8px;
}
.result-meta {
  font-size: 12px;
  color: #888;
}
.chart-box {
  min-width: 420px;
}
.chart-title {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 6px;
}
.chart-box :deep(.chart-card) {
  height: 280px;
  min-height: 280px;
}
.chart-empty {
  padding: 24px 0;
  text-align: center;
  color: #999;
  font-size: 13px;
}
.chart-actions {
  margin-top: 8px;
  text-align: right;
}
.tool-msg {
  font-size: 12px;
  color: #888;
  background: rgba(128, 128, 128, 0.08);
  border-radius: 6px;
  padding: 6px 10px;
  white-space: pre-wrap;
  word-break: break-all;
  max-width: 720px;
}
.sq-input {
  flex-shrink: 0;
  border: 1px solid rgba(128, 128, 128, 0.2);
  border-radius: 8px;
  padding: 8px;
  background: rgba(128, 128, 128, 0.04);
}
.input-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 6px;
}
.input-hint {
  font-size: 12px;
  color: #888;
}
</style>

