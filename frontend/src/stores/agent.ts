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
  /** 用户主动停止生成：保留已产出的内容，并打上「已停止」标记 */
  stopped?: boolean;
}

// 流式请求的中断句柄：放在 store 之外，避免把不可序列化的 AbortController 塞进响应式 state
let activeAbort: AbortController | null = null;

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
      // 切换会话前终止在途生成，否则流式事件会继续写进已被替换的消息列表
      this.stop();
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
      this.stop();
      await agentApi.deleteSession(id);
      if (this.activeSessionId === id) {
        this.activeSessionId = null;
        this.items = [];
      }
      await this.loadSessions();
    },
    async sendMessage(message: string, datasourceId: number | null, modelConfigId: number | null) {
      // 一次只允许一条在途请求，避免连点造成两个流同时写同一份消息列表
      if (this.streaming) return null;
      if (!this.activeSessionId) {
        const sess = await this.createSession(datasourceId, modelConfigId);
        this.activeSessionId = sess.id;
      }
      this.items.push({ role: "user", type: "text", content: message });
      const assistant: ChatItem = { role: "assistant", type: "text", content: "", streaming: true };
      this.items.push(assistant);
      this.streaming = true;
      this.inputEnabled = false;

      const controller = new AbortController();
      activeAbort = controller;
      let lastAuthz: ChatItem["authz"] | null = null;

      try {
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
          // 用户点「停止生成」时中断连接：后端收到断开后取消在途的 LLM 调用
          signal: controller.signal,
        });
        if (!resp.ok || !resp.body) {
          const body = await resp.json().catch(() => null);
          assistant.content = (body && body.message) || `请求失败 (${resp.status})`;
          return null;
        }
        const reader = resp.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
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
            }
          }
        }
      } catch (e) {
        if (controller.signal.aborted) {
          // 用户主动停止：保留已产出的内容（思考过程 / 已出的表格），只打标记，不报错
          assistant.stopped = true;
          if (!assistant.content.trim()) assistant.content = "已停止生成";
        } else {
          assistant.content = `❌ 请求失败：${(e as Error).message || e}`;
        }
      } finally {
        assistant.streaming = false;
        this.streaming = false;
        this.inputEnabled = true;
        if (activeAbort === controller) activeAbort = null;
      }
      return lastAuthz;
    },
    /** 主动终止当前生成（前端断流 → 后端取消 LLM 调用） */
    stop() {
      activeAbort?.abort();
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
        case "tool":
          this.items.push({
            role: "assistant",
            type: "tool",
            content: `🔧 ${String(event.tool || "工具")}：${String(event.content || "")}`,
          });
          break;
        case "retry":
          this.items.push({ role: "assistant", type: "tool", content: `🔄 ${String(event.content || "")}` });
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
        case "warning":
          // 后端降级提示（如 Schema 拉取失败、图表配置与结果列不匹配）
          this.items.push({ role: "assistant", type: "warning", content: String(event.content || "") });
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
