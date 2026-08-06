<template>
  <div class="agent-panel" :style="panelStyle" v-show="!collapsed">
    <div class="agent-header" @mousedown="startDrag">
      <span class="agent-title">🤖 AI Agent</span>
      <n-tag v-if="dsName" size="tiny" type="info" style="margin-left: 6px">{{ dsName }}</n-tag>
      <div style="flex: 1"></div>
      <n-button size="tiny" quaternary @mousedown.stop @click="collapsed = true" title="收起">—</n-button>
    </div>

    <div class="agent-toolbar">
      <n-select v-model:value="activeSessionId" size="small" :options="sessionOptions" placeholder="选择对话" @update:value="onSessionChange" />
      <n-button size="small" @click="newSession">新建</n-button>
      <n-button size="small" secondary type="error" @click="deleteCurrent">删除</n-button>
    </div>
    <div class="agent-toolbar" v-if="aiConfigs.length">
      <span class="toolbar-label">模型</span>
      <n-select v-model:value="modelConfigId" size="small" :options="modelOptions" placeholder="选择模型" />
    </div>

    <div ref="msgBox" class="agent-messages">
      <div v-if="!agent.items.length" class="agent-empty">
        <p>👋 你好，我是数据库 Agent</p>
        <p class="hint">可以用自然语言查询数据，例如：<br />「统计各订单状态的数量并按状态分组」</p>
      </div>
      <template v-for="(item, idx) in agent.items" :key="idx">
        <div v-if="item.role === 'user'" class="msg user">{{ item.content }}</div>
        <div v-else-if="item.type === 'authz' && item.authz" class="msg authz">
          <n-alert :type="item.authz.risk_level === 'danger' ? 'error' : 'warning'" :title="item.authz.risk_level === 'danger' ? '危险操作确认' : '写操作确认'">
            <div class="authz-preview">{{ item.authz.preview || item.authz.sql_text }}</div>
            <div style="margin-top: 8px; display: flex; gap: 8px">
              <n-button size="small" type="primary" @click="confirmAuthz(item.authz, true)">确认执行</n-button>
              <n-button size="small" @click="confirmAuthz(item.authz, false)">取消</n-button>
            </div>
          </n-alert>
        </div>
        <div v-else-if="item.type === 'sql'" class="msg assistant">
          <div class="sql-block">
            <pre><code>{{ item.content }}</code></pre>
            <div class="sql-actions">
              <n-button size="tiny" @click="emit('fill-editor', item.content)">填入编辑器</n-button>
              <n-button size="tiny" type="primary" @click="emit('run-sql', item.content)">执行</n-button>
            </div>
          </div>
        </div>
        <div v-else-if="item.type === 'result' && item.result" class="msg assistant">
          <n-data-table size="tiny" :columns="resultColumns(item.result)" :data="resultRows(item.result)" :max-height="220" :scroll-x="800" />
          <div class="result-meta">共 {{ item.result.total_rows }} 行 · {{ item.result.duration_ms }} ms</div>
        </div>
        <div v-else-if="item.role === 'assistant'" class="msg assistant">
          <span v-if="item.streaming" class="cursor">▍</span>
          {{ item.content }}
        </div>
      </template>
    </div>

    <div class="agent-input">
      <n-input
        v-model:value="input"
        type="textarea"
        :rows="2"
        placeholder="输入自然语言查询，Enter 发送，Shift+Enter 换行"
        :disabled="!agent.inputEnabled"
        @keydown="onKeydown"
      />
      <div class="input-actions">
        <span class="input-hint">{{ agent.streaming ? "正在生成…" : "模型将自动生成并执行 SQL" }}</span>
        <n-button type="primary" :loading="agent.streaming" :disabled="!input.trim()" @click="send">发送</n-button>
      </div>
    </div>
  </div>

  <div v-if="collapsed" class="agent-fab" @click="collapsed = false">🤖</div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from "vue";
import { useMessage } from "naive-ui";
import type { SqlResult } from "../api";
import { configApi } from "../api";
import type { AIConfig } from "../api";
import { useAgentStore } from "../stores/agent";
import type { ChatItem } from "../stores/agent";

const emit = defineEmits<{ (e: "fill-editor", sql: string): void; (e: "run-sql", sql: string): void }>();
const props = defineProps<{ dsId: number | null; dsName: string }>();
const agent = useAgentStore();
const message = useMessage();
const input = ref("");
const msgBox = ref<HTMLElement>();
const collapsed = ref(false);
const aiConfigs = ref<AIConfig[]>([]);
const modelConfigId = ref<number | null>(null);

const activeSessionId = computed({
  get: () => agent.activeSessionId,
  set: (v) => {
    if (v) agent.selectSession(v);
  },
});

const sessionOptions = computed(() => agent.sessions.map((s) => ({ label: s.title || `对话 ${s.id}`, value: s.id })));
const modelOptions = computed(() => aiConfigs.value.filter((c) => c.is_active).map((c) => ({ label: `${c.provider} · ${c.model_name}`, value: c.id })));

const panelStyle = ref({ right: "16px", bottom: "16px", width: "380px", height: "440px" });

let dragStart = { x: 0, y: 0, right: 0, bottom: 0 };

function startDrag(e: MouseEvent) {
  const target = e.target as HTMLElement;
  if (target.closest("button")) return;
  dragStart = { x: e.clientX, y: e.clientY, right: parseInt(panelStyle.value.right), bottom: parseInt(panelStyle.value.bottom) };
  const onMove = (ev: MouseEvent) => {
    panelStyle.value.right = `${dragStart.right - (ev.clientX - dragStart.x)}px`;
    panelStyle.value.bottom = `${dragStart.bottom - (ev.clientY - dragStart.y)}px`;
  };
  const onUp = () => {
    window.removeEventListener("mousemove", onMove);
    window.removeEventListener("mouseup", onUp);
  };
  window.addEventListener("mousemove", onMove);
  window.addEventListener("mouseup", onUp);
}

function resultColumns(r: SqlResult) {
  return (r.columns || []).map((c, i) => ({ title: c, key: `c${i}`, ellipsis: { tooltip: true }, render: (row: Record<string, unknown>) => String(row[`c${i}`] ?? "") }));
}
function resultRows(r: SqlResult) {
  const cols = r.columns || [];
  return (r.rows || []).slice(0, 20).map((row) => {
    const obj: Record<string, unknown> = {};
    cols.forEach((c, i) => (obj[`c${i}`] = row[i]));
    return obj;
  });
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    send();
  }
}

async function send() {
  const text = input.value.trim();
  if (!text) return;
  input.value = "";
  await agent.sendMessage(text, props.dsId, modelConfigId.value);
  scrollBottom();
}

async function newSession() {
  await agent.createSession(props.dsId, modelConfigId.value);
  scrollBottom();
}

async function onSessionChange(id: number) {
  await agent.selectSession(id);
  scrollBottom();
}

async function deleteCurrent() {
  if (!agent.activeSessionId) return;
  await agent.deleteSession(agent.activeSessionId);
}

async function confirmAuthz(authz: ChatItem["authz"], confirmed: boolean) {
  if (!authz) return;
  try {
    await agent.confirmExecution(authz, confirmed);
    message.success(confirmed ? "已执行" : "已取消");
  } catch (e) {
    message.error((e as Error).message);
  }
}

function scrollBottom() {
  nextTick(() => {
    if (msgBox.value) msgBox.value.scrollTop = msgBox.value.scrollHeight;
  });
}

watch(() => agent.items.length, scrollBottom);
watch(() => agent.streaming, scrollBottom);

onMounted(async () => {
  await agent.loadSessions();
  try {
    aiConfigs.value = await configApi.listAi();
    const def = aiConfigs.value.find((c) => c.is_default && c.is_active) || aiConfigs.value.find((c) => c.is_active);
    if (def) modelConfigId.value = def.id;
  } catch {
    /* ignore */
  }
});
</script>

<style scoped>
.agent-panel {
  position: fixed;
  z-index: 50;
  display: flex;
  flex-direction: column;
  background: var(--n-color);
  border: 1px solid rgba(128, 128, 128, 0.25);
  border-radius: 10px;
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.18);
  overflow: hidden;
}
.agent-header {
  display: flex;
  align-items: center;
  padding: 8px 10px;
  cursor: move;
  user-select: none;
  background: linear-gradient(135deg, #2080f0, #18a058);
  color: #fff;
  font-weight: 600;
  font-size: 14px;
}
.agent-toolbar {
  display: flex;
  gap: 6px;
  padding: 6px 10px;
  align-items: center;
  border-bottom: 1px solid rgba(128, 128, 128, 0.15);
}
.toolbar-label {
  font-size: 12px;
  color: #888;
  flex-shrink: 0;
}
.agent-messages {
  flex: 1;
  overflow-y: auto;
  padding: 10px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.agent-empty {
  text-align: center;
  color: #999;
  padding: 30px 10px;
  font-size: 13px;
}
.agent-empty .hint {
  font-size: 12px;
  line-height: 1.6;
}
.msg {
  max-width: 100%;
  font-size: 13px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}
.msg.user {
  align-self: flex-end;
  background: #2080f0;
  color: #fff;
  border-radius: 10px 10px 2px 10px;
  padding: 8px 12px;
  max-width: 85%;
}
.msg.assistant {
  align-self: flex-start;
  background: rgba(128, 128, 128, 0.12);
  border-radius: 10px 10px 10px 2px;
  padding: 8px 12px;
  max-width: 95%;
}
.msg.authz {
  align-self: stretch;
}
.sql-block {
  background: rgba(0, 0, 0, 0.06);
  border-radius: 6px;
  padding: 6px;
  width: 100%;
}
.sql-block pre {
  margin: 0;
  font-size: 12px;
  overflow-x: auto;
  white-space: pre-wrap;
}
.sql-actions {
  display: flex;
  gap: 6px;
  margin-top: 6px;
  justify-content: flex-end;
}
.result-meta {
  font-size: 11px;
  color: #888;
  margin-top: 4px;
}
.cursor {
  animation: blink 1s infinite;
}
@keyframes blink {
  50% {
    opacity: 0;
  }
}
.agent-input {
  border-top: 1px solid rgba(128, 128, 128, 0.15);
  padding: 8px 10px;
}
.input-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 6px;
}
.input-hint {
  font-size: 11px;
  color: #999;
}
.agent-fab {
  position: fixed;
  right: 16px;
  bottom: 16px;
  z-index: 50;
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background: linear-gradient(135deg, #2080f0, #18a058);
  color: #fff;
  font-size: 22px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.25);
}
</style>
