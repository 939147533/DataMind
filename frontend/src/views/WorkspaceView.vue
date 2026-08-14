<template>
  <div class="workspace-view">
    <n-layout has-sider style="height: 100%">
      <n-layout-sider bordered width="280" :native-scrollbar="false">
        <div class="side-panel">
          <div class="ds-row">
            <n-select v-model:value="dsId" :options="dsOptions" placeholder="选择数据源" size="small" clearable />
          </div>
          <n-tabs v-model:value="sideTab" size="small" class="side-tabs">
            <n-tab-pane name="tree" tab="对象">
              <ObjectTree :ds-id="dsId" :ds-name="dsName" @open-table="openTable" @show-ddl="showObjectDdl" @show-sequence="showSequence" />
            </n-tab-pane>
            <n-tab-pane name="history" tab="历史">
              <div class="history-list">
                <div v-for="item in historyItems" :key="item.id" class="history-item" @click="loadHistoryItem(item)">
                  <div class="history-sql">{{ item.sql_text }}</div>
                  <div class="history-meta">
                    <n-tag size="tiny" :type="item.status === 'success' ? 'success' : 'error'">{{ item.status === "success" ? "成功" : "失败" }}</n-tag>
                    <span>{{ item.row_count }} 行 · {{ item.duration_ms }} ms</span>
                  </div>
                </div>
                <n-empty v-if="!historyItems.length" description="暂无执行历史" style="padding: 30px 0" />
                <div v-if="historyItems.length < historyTotal" class="history-more">
                  <n-button size="tiny" text type="primary" @click="loadMoreHistory">加载更多（{{ historyItems.length }}/{{ historyTotal }}）</n-button>
                </div>
              </div>
            </n-tab-pane>
            <n-tab-pane name="saved" tab="收藏">
              <div class="history-list">
                <div v-for="item in savedItems" :key="item.id" class="history-item" @click="loadSavedItem(item)">
                  <div class="history-sql">{{ item.name }}</div>
                  <div class="history-meta">
                    <span>{{ (item.sql_text || "").slice(0, 60) }}</span>
                    <n-button size="tiny" text type="error" @click.stop="removeSaved(item.id)">删除</n-button>
                  </div>
                </div>
                <n-empty v-if="!savedItems.length" description="暂无收藏，点击工具栏「收藏」保存当前 SQL" style="padding: 30px 0" />
              </div>
            </n-tab-pane>
          </n-tabs>
        </div>
      </n-layout-sider>
      <n-layout class="main-col">
        <div class="tabbar">
          <n-tabs type="card" closable size="small" :value="activeTabKey" @update:value="onTabChange" @close="onCloseTab">
            <n-tab-pane v-for="tab in tabs" :key="tab.id" :name="String(tab.id)" :tab="tab.title" />
          </n-tabs>
          <div class="toolbar">
            <n-button size="small" @click="newTab">＋ 新建</n-button>
            <n-button size="small" type="primary" :loading="activeTab?.loading" @click="runActive">▶ 执行</n-button>
            <n-button size="small" :loading="formatting" @click="formatSql">格式化</n-button>
            <n-button size="small" :disabled="!activeTab?.sql.trim()" @click="openSaveModal">收藏</n-button>
            <n-dropdown :options="exportDbOptions" @select="exportDatabase">
              <n-button size="small" :loading="dbExporting">导出库文档 ▾</n-button>
            </n-dropdown>
          </div>
        </div>
        <div class="editor-box" v-if="activeTab">
          <SqlEditor :model-value="activeTab.sql" @update:model-value="(v: string) => { if (activeTab) setTabSql(activeTab.id, v); }" />
        </div>
        <div class="editor-box editor-empty" v-else>
          <n-empty description="新建查询，或在左侧选择数据源与对象" style="margin-top: 60px">
            <template #extra>
              <n-button size="small" type="primary" @click="newTab">＋ 新建查询</n-button>
            </template>
          </n-empty>
        </div>
        <div class="result-box">
          <ResultTable
            ref="resultTableRef"
            :result="activeTab?.result ?? null"
            :error="activeTab?.error ?? ''"
            @clear-error="clearActiveError"
            @edit-confirm="onEditConfirm"
            @reload="reloadResult"
          />
        </div>
      </n-layout>
      <n-layout-sider bordered :width="agentCollapsed ? 48 : 396" :native-scrollbar="false">
        <AgentPanel v-model:collapsed="agentCollapsed" :ds-id="dsId" :ds-name="dsName" @fill-editor="fillEditor" @run-sql="runAgentSql" />
      </n-layout-sider>
    </n-layout>

    <ConfirmExecModal v-model:show="confirmShow" :info="confirmInfo" :loading="confirmLoading" @confirm="onConfirmExec" />

    <n-modal v-model:show="saveModalShow" preset="card" title="收藏 SQL" style="width: 460px">
      <n-form label-placement="left" label-width="80px">
        <n-form-item label="名称">
          <n-input v-model:value="saveModalName" placeholder="给这条 SQL 起个名字" />
        </n-form-item>
      </n-form>
      <template #footer>
        <div style="display: flex; justify-content: flex-end; gap: 8px">
          <n-button size="small" @click="saveModalShow = false">取消</n-button>
          <n-button size="small" type="primary" @click="saveCurrentSql">保存</n-button>
        </div>
      </template>
    </n-modal>

    <n-modal v-model:show="ddlShow" preset="card" title="对象定义 (DDL)" style="width: 720px">
      <pre class="ddl-pre">{{ ddlText }}</pre>
      <template #footer>
        <div style="display: flex; justify-content: flex-end">
          <n-button size="small" @click="copyDdl">复制</n-button>
        </div>
      </template>
    </n-modal>

  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useMessage } from "naive-ui";
import { exportApi, metadataApi, savedQueryApi, sqlApi } from "../api";
import type { SavedQuery, SqlHistoryItem, SqlResult } from "../api";
import AgentPanel from "../components/AgentPanel.vue";
import ConfirmExecModal from "../components/ConfirmExecModal.vue";
import ObjectTree from "../components/ObjectTree.vue";
import ResultTable from "../components/ResultTable.vue";
import SqlEditor from "../components/SqlEditor.vue";
import { useConnectionsStore } from "../stores/connections";
import { useWorkspaceStore } from "../stores/workspace";

const message = useMessage();
const connections = useConnectionsStore();
const workspace = useWorkspaceStore();

const sideTab = ref("tree");
const historyItems = ref<SqlHistoryItem[]>([]);
const historyTotal = ref(0);
const historyPage = ref(1);
const formatting = ref(false);
const dbExporting = ref(false);
const confirmShow = ref(false);
const confirmLoading = ref(false);
const confirmInfo = ref<{ sql_text: string; operation_type: string; risk_level: string; preview?: string; execution_id: string } | null>(null);
const ddlShow = ref(false);
const ddlText = ref("");
const agentCollapsed = ref(true);
const resultTableRef = ref<InstanceType<typeof ResultTable>>();
const savedItems = ref<SavedQuery[]>([]);
const saveModalShow = ref(false);
const saveModalName = ref("");

const dsId = computed({
  get: () => connections.currentDsId,
  set: (v) => connections.setCurrent(v as number | null),
});
const dsOptions = computed(() => connections.list.map((c) => ({ label: c.name, value: c.id })));
const dsName = computed(() => connections.list.find((c) => c.id === dsId.value)?.name || "");
const tabs = computed(() => workspace.tabs);
const activeTab = computed(() => workspace.activeTab);
const activeTabKey = computed({
  get: () => String(workspace.activeTabId),
  set: (v) => workspace.setActive(Number(v)),
});

const exportDbOptions = [
  { label: "Word 文档 (.docx)", key: "word" },
  { label: "Excel 表格 (.xlsx)", key: "excel" },
  { label: "Markdown (.md)", key: "markdown" },
  { label: "HTML (.html)", key: "html" },
];

onMounted(async () => {
  await connections.load();
  if (!workspace.tabs.length) {
    workspace.addTab(
      "-- 在此输入 SQL，例如：\nSELECT * FROM users LIMIT 50;\n\n-- 支持多条语句；写操作需要二次确认",
      "查询 1",
    );
  }
  loadHistory();
  loadSaved();
});

async function loadSaved() {
  try {
    const data = await savedQueryApi.list({ page: 1, page_size: 100 });
    savedItems.value = data.list;
  } catch {
    /* ignore */
  }
}

function openSaveModal() {
  const tab = workspace.activeTab;
  if (!tab || !tab.sql.trim()) return;
  saveModalName.value = tab.title && tab.title !== "新查询" ? tab.title : (tab.sql.trim().split("\n")[0] || "收藏 SQL").slice(0, 40);
  saveModalShow.value = true;
}

async function saveCurrentSql() {
  const tab = workspace.activeTab;
  if (!tab) return;
  if (!saveModalName.value.trim()) {
    message.warning("请输入名称");
    return;
  }
  try {
    await savedQueryApi.create({
      name: saveModalName.value.trim(),
      sql_text: tab.sql,
      datasource_id: dsId.value,
    });
    message.success("已收藏");
    saveModalShow.value = false;
    loadSaved();
  } catch (e) {
    message.error((e as Error).message);
  }
}

function loadSavedItem(item: SavedQuery) {
  workspace.addTab(item.sql_text || "", item.name);
}

async function removeSaved(id: number) {
  try {
    await savedQueryApi.remove(id);
    loadSaved();
  } catch (e) {
    message.error((e as Error).message);
  }
}

function newTab() {
  workspace.addTab("", `查询 ${workspace.tabs.length + 1}`);
}

function setTabSql(id: number, v: string) {
  workspace.setSql(id, v);
}

function onTabChange(key: string) {
  workspace.setActive(Number(key));
}

function onCloseTab(name: string) {
  workspace.closeTab(Number(name));
}

function clearActiveError() {
  const tab = workspace.activeTab;
  if (tab) tab.error = "";
}

async function runActive() {
  const tab = workspace.activeTab;
  if (!tab) return;
  if (!dsId.value) {
    message.warning("请先选择数据源");
    return;
  }
  await runTab(tab.id);
}

async function runTab(id: number) {
  const result = await workspace.executeTab(id);
  const tab = workspace.tabs.find((t) => t.id === id);
  if (tab) resultTableRef.value?.setLastSql(tab.sql);
  if (result?.need_confirm && result.execution_id) {
    confirmInfo.value = {
      execution_id: result.execution_id,
      sql_text: result.sql_text || tab?.sql || "",
      operation_type: result.operation_type,
      risk_level: result.risk_level || "warning",
      preview: result.preview,
    };
    confirmShow.value = true;
  } else if (result) {
    message.success(`执行完成：${result.total_rows ?? 0} 行 · ${result.duration_ms} ms`);
  }
  loadHistory();
}

async function onConfirmExec(confirmed: boolean) {
  const info = confirmInfo.value;
  if (!info) return;
  confirmLoading.value = true;
  try {
    const result = await workspace.confirmExecution(info.execution_id, confirmed);
    if (confirmed) {
      message.success(`已执行，影响 ${result.affected_rows ?? 0} 行`);
      resultTableRef.value?.setLastSql(info.sql_text);
      // 结果编辑场景（SELECT 表浏览）确认后刷新结果
      const tab = workspace.activeTab;
      if (tab && /^\s*select\b/i.test(tab.sql) && dsId.value) {
        await runTab(tab.id);
      }
    } else {
      message.info("已取消执行");
    }
    confirmShow.value = false;
    confirmInfo.value = null;
    loadHistory();
  } catch (e) {
    message.error((e as Error).message);
  } finally {
    confirmLoading.value = false;
  }
}

function onEditConfirm(result: SqlResult) {
  if (!result?.need_confirm || !result.execution_id) return;
  confirmInfo.value = {
    execution_id: result.execution_id,
    sql_text: result.sql_text || "",
    operation_type: result.operation_type,
    risk_level: result.risk_level || "warning",
    preview: result.preview,
  };
  confirmShow.value = true;
}

function reloadResult() {
  const tab = workspace.activeTab;
  if (tab && dsId.value) runTab(tab.id);
}

async function formatSql() {
  const tab = workspace.activeTab;
  if (!tab || !tab.sql.trim()) return;
  formatting.value = true;
  try {
    const r = await sqlApi.format(tab.sql);
    workspace.setSql(tab.id, r.sql);
  } catch (e) {
    message.error((e as Error).message);
  } finally {
    formatting.value = false;
  }
}

function quoteIdentifier(name: string, dbType?: string): string {
  const mysqlLike = dbType === "mysql" || dbType === "oceanbase" || dbType === "goldendb";
  if (mysqlLike) {
    return `\`${name.replace(/`/g, "``")}\``;
  }
  return `"${name.replace(/"/g, '""')}"`;
}

function openTable(name: string, schema?: string) {
  const conn = connections.list.find((c) => c.id === dsId.value);
  const dbType = conn?.db_type;
  const limitClause = dbType === 'oracle' ? 'FETCH FIRST 100 ROWS ONLY' : 'LIMIT 100';
  const sql = 'SELECT * FROM ' + quoteIdentifier(name, dbType) + ' ' + limitClause + ';';
  const tab = workspace.addTab(sql, name);
  if (dsId.value) runTab(tab.id);
}

async function showObjectDdl(kind: string, name: string) {
  if (!dsId.value) return;
  try {
    ddlText.value = "加载中…";
    ddlShow.value = true;
    const r = await metadataApi.objectDdl(dsId.value, kind, name);
    ddlText.value = r.ddl || "(无 DDL 信息)";
  } catch (e) {
    ddlText.value = `加载失败：${(e as Error).message}`;
  }
}

async function showSequence(name: string) {
  await showObjectDdl("sequences", name);
}

function copyDdl() {
  navigator.clipboard?.writeText(ddlText.value).then(() => message.success("已复制"));
}

function fillEditor(sql: string) {
  const tab = workspace.activeTab;
  if (!tab) return;
  const current = tab.sql.trim();
  workspace.setSql(tab.id, current ? `${current}\n\n${sql}` : sql);
  message.success("已填入编辑器");
}

async function runAgentSql(sql: string) {
  let tab = workspace.activeTab;
  if (!tab) {
    tab = workspace.addTab(sql, "Agent SQL");
  } else {
    workspace.setSql(tab.id, sql);
  }
  if (!dsId.value) {
    message.warning("请先在左上角选择数据源");
    return;
  }
  await runTab(tab.id);
}

async function loadHistory() {
  try {
    const data = await sqlApi.history({ datasource_id: dsId.value || undefined, page: 1, page_size: 50 });
    historyItems.value = data.list;
    historyTotal.value = data.total;
    historyPage.value = 1;
  } catch {
    /* ignore */
  }
}

async function loadMoreHistory() {
  historyPage.value += 1;
  const data = await sqlApi.history({ datasource_id: dsId.value || undefined, page: historyPage.value, page_size: 50 });
  historyItems.value = [...historyItems.value, ...data.list];
}

function loadHistoryItem(item: SqlHistoryItem) {
  const tab = workspace.addTab(item.sql_text, `历史 ${item.id}`);
  if (dsId.value) runTab(tab.id);
}

async function exportDatabase(format: string) {
  if (!dsId.value) {
    message.warning("请先选择数据源");
    return;
  }
  dbExporting.value = true;
  try {
    message.info("导出任务已提交，请稍候…");
    const { task_id } = await exportApi.database(dsId.value, format);
    for (let i = 0; i < 60; i++) {
      await new Promise((r) => setTimeout(r, 1500));
      const st = await exportApi.poll(task_id);
      if (st.status === "done" && st.download_url) {
        window.location.href = st.download_url;
        message.success("导出完成，开始下载");
        return;
      }
      if (st.status === "failed" || st.error) {
        message.error(st.error || "导出失败");
        return;
      }
    }
    message.warning("导出超时，请稍后重试");
  } catch (e) {
    message.error((e as Error).message);
  } finally {
    dbExporting.value = false;
  }
}
</script>

<style scoped>
.workspace-view {
  height: 100%;
  display: flex;
}
.main-col {
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.tabbar {
  display: flex;
  align-items: flex-start;
  padding: 4px 8px 0;
  gap: 8px;
  border-bottom: 1px solid rgba(128, 128, 128, 0.15);
}
.tabbar .n-tabs {
  flex: 1;
  min-width: 0;
}
.toolbar {
  display: flex;
  gap: 6px;
  padding: 2px 0 6px;
  flex-shrink: 0;
}
.editor-box {
  height: 230px;
  min-height: 140px;
  padding: 8px;
  border-bottom: 1px solid rgba(128, 128, 128, 0.15);
}
.editor-empty {
  display: flex;
  align-items: flex-start;
  justify-content: center;
}
.result-box {
  flex: 1;
  min-height: 180px;
  overflow: auto;
  padding: 8px 12px;
}
.side-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
}
.ds-row {
  padding: 8px;
  border-bottom: 1px solid rgba(128, 128, 128, 0.15);
}
.side-tabs {
  flex: 1;
  min-height: 0;
  padding: 0 8px;
}
.history-list {
  padding: 4px 0;
}
.history-item {
  padding: 8px;
  border-bottom: 1px solid rgba(128, 128, 128, 0.12);
  cursor: pointer;
  border-radius: 6px;
}
.history-item:hover {
  background: rgba(128, 128, 128, 0.08);
}
.history-sql {
  font-size: 12px;
  font-family: monospace;
  white-space: pre-wrap;
  word-break: break-all;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.history-meta {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-top: 4px;
  font-size: 11px;
  color: #888;
}
.history-more {
  text-align: center;
  padding: 8px;
}
.ddl-pre {
  max-height: 60vh;
  overflow: auto;
  background: rgba(128, 128, 128, 0.08);
  padding: 12px;
  border-radius: 6px;
  font-size: 12px;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
