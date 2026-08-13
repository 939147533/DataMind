import { defineStore } from "pinia";
import { agentApi } from "../api";
import type { AgentMessage, AgentSession, SmartChartConfig, SqlResult } from "../api";

export interface ChatItem {
  role: string;
  type: string;
  content: string;
  sql?: string;
  result?: SqlResult;
  authz?: {
    execution_id: string;
    sql_text: string;
    operation_type: string;
    risk_level: string;
    preview: string;
    session_id?: number;
  };
  chart?: SmartChartConfig | null;
  streaming?: boolean;
}

export const useAgentStore = defineStore("agent", {
  state: () => ({
    sessions: [] as AgentSession[],
    activeSessionId: null as number | null,
    items: [] as ChatItem[],
    streaming: false,
    inputEnabled: true,
    datasourceId: (() => {
      const raw = localStorage.getItem("agent.datasourceId");
      return raw ? Number(raw) : null;
    })(),
    modelConfigId: (() => {
      const raw = localStorage.getItem("agent.modelConfigId");
      return raw ? Number(raw) : null;
    })(),
  }),
  actions: {
    async loadSessions() {
      this.sessions = await agentApi.listSessions();
    },
    async createSession(datasourceId: number | null, modelConfigId: number | null) {
      const sess = await agentApi.createSession({ datasource_id: datasourceId, model_config_id: modelConfigId });
      await this.loadSessions();
      await this.selectSession(sess.id);
      return sess;
    },
    async selectSession(id: number) {
      this.activeSessionId = id;
      const msgs = await agentApi.messages(id);
      this.items = msgs.map((m) => {
        if (m.message_type === "chart") {
          try {
            const parsed = JSON.parse(m.content);
            if (parsed && typeof parsed === "object" && parsed.chart && parsed.result) {
              return {
                role: m.role,
                type: "chart",
                content: "",
                chart: parsed.chart as SmartChartConfig,
                result: parsed.result as SqlResult,
              };
            }
            return { role: m.role, type: "chart", content: "", chart: parsed as SmartChartConfig };
          } catch {
            return { role: m.role, type: "chart", content: "", chart: null };
          }
        }
        return { role: m.role, type: m.message_type, content: m.content };
      });
    },
    async deleteSession(id: number) {
      await agentApi.deleteSession(id);
      if (this.activeSessionId === id) {
        this.activeSessionId = null;
        this.items = [];
      }
      await this.loadSessions();
    },
    async sendMessage(message: string, datasourceId: number | null, modelConfigId: number | null) {
      if (!this.activeSessionId) {
        const sess = await this.createSession(datasourceId, modelConfigId);
        this.activeSessionId = sess.id;
      }
      this.items.push({ role: "user", type: "text", content: message });
      const assistant: ChatItem = { role: "assistant", type: "text", content: "", streaming: true };
      this.items.push(assistant);
      this.streaming = true;
      this.inputEnabled = false;

      let lastAuthz: ChatItem["authz"] | null = null;
      let pendingSql = "";

      const resp = await fetch("/api/agent/chat", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: this.activeSessionId,
          datasource_id: datasourceId,
          model_config_id: modelConfigId,
          message,
        }),
      });
      if (!resp.ok || !resp.body) {
        const body = await resp.json().catch(() => null);
        assistant.content = (body && body.message) || `请求失败 (${resp.status})`;
        assistant.streaming = false;
        this.streaming = false;
        this.inputEnabled = true;
        return;
      }
      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() || "";
          for (const line of lines) {
            if (!line.startsWith("data: ")) continue;
            let event: Record<string, unknown>;
            try {
              event = JSON.parse(line.slice(6));
            } catch {
              continue;
            }
            this.handleEvent(event, assistant);
            if (event.type === "authorization_required") {
              lastAuthz = event as unknown as ChatItem["authz"];
              pendingSql = (event as { sql_text?: string }).sql_text || "";
            }
          }
        }
      } finally {
        assistant.streaming = false;
        this.streaming = false;
        this.inputEnabled = true;
      }
      return lastAuthz;
    },
    handleEvent(event: Record<string, unknown>, assistant: ChatItem) {
      switch (event.type) {
        case "session_title": {
          const t = String(event.content || "");
          if (t) {
            const s = this.sessions.find((x) => x.id === this.activeSessionId);
            if (s) s.title = t;
          }
          break;
        }
        case "thought":
          assistant.content = String(event.content || "");
          break;
        case "sql": {
          const sql = String(event.content || "");
          assistant.sql = sql;
          assistant.content = "";
          this.items.push({ role: "assistant", type: "sql", content: sql });
          break;
        }
        case "result":
          this.items.push({ role: "assistant", type: "result", content: "", result: event.content as SqlResult });
          break;
        case "chart": {
          const chartItem: ChatItem = {
            role: "assistant",
            type: "chart",
            content: "",
            chart: (event.content as SmartChartConfig) || null,
          };
          for (let i = this.items.length - 1; i >= 0; i--) {
            const it = this.items[i];
            if (it.type === "result" && it.result) {
              chartItem.result = it.result;
              break;
            }
          }
          this.items.push(chartItem);
          break;
        }
        case "text":
          assistant.content += String(event.content || "");
          break;
        case "execution_result":
          this.items.push({
            role: "assistant",
            type: "execution_result",
            content: `✅ 已执行：影响 ${(event.content as { affected_rows?: number })?.affected_rows ?? "?"} 行`,
          });
          break;
        case "authorization_required":
          this.items.push({
            role: "assistant",
            type: "authz",
            content: "",
            authz: event as unknown as ChatItem["authz"],
          });
          break;
        case "error":
          assistant.content = `❌ ${String(event.content || "出错了")}`;
          break;
        default:
          break;
      }
    },
    async confirmExecution(authz: ChatItem["authz"], confirmed: boolean) {
      if (!authz) return;
      const result = await agentApi.confirm(authz.execution_id, confirmed);
      const idx = this.items.findIndex((it) => it.authz?.execution_id === authz.execution_id);
      if (idx >= 0) {
        this.items[idx].content = confirmed
          ? `✅ 已执行：影响 ${result.affected_rows ?? "?"} 行`
          : "已取消执行";
        this.items[idx].authz = undefined;
      }
    },
  },
});
