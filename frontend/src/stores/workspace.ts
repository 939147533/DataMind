import { defineStore } from "pinia";
import { sqlApi } from "../api";
import type { SqlResult } from "../api";
import { useConnectionsStore } from "./connections";

export interface WorkspaceTab {
  id: number;
  title: string;
  sql: string;
  result: SqlResult | null;
  loading: boolean;
  error: string;
}

let tabSeq = 1;

export const useWorkspaceStore = defineStore("workspace", {
  state: () => ({
    tabs: [] as WorkspaceTab[],
    activeTabId: 0,
  }),
  getters: {
    activeTab: (s) => s.tabs.find((t) => t.id === s.activeTabId) || null,
  },
  actions: {
    addTab(sql = "", title = "新查询") {
      const tab: WorkspaceTab = {
        id: tabSeq++,
        title,
        sql,
        result: null,
        loading: false,
        error: "",
      };
      this.tabs.push(tab);
      this.activeTabId = tab.id;
      return tab;
    },
    closeTab(id: number) {
      const idx = this.tabs.findIndex((t) => t.id === id);
      if (idx < 0) return;
      this.tabs.splice(idx, 1);
      if (this.activeTabId === id) {
        const next = this.tabs[Math.min(idx, this.tabs.length - 1)];
        this.activeTabId = next ? next.id : 0;
      }
    },
    setActive(id: number) {
      this.activeTabId = id;
    },
    setSql(id: number, sql: string) {
      const tab = this.tabs.find((t) => t.id === id);
      if (tab) tab.sql = sql;
    },
    async executeTab(id: number): Promise<SqlResult | null> {
      const tab = this.tabs.find((t) => t.id === id);
      if (!tab) return null;
      tab.loading = true;
      tab.error = "";
      try {
        const connections = useConnectionsStore();
        const dsId = connections.currentDsId;
        if (!dsId) throw new Error("请先选择数据源");
        const result = await sqlApi.execute(dsId, tab.sql);
        tab.result = result;
        tab.loading = false;
        return result;
      } catch (e) {
        tab.loading = false;
        tab.error = (e as Error).message;
        return null;
      }
    },
    async confirmExecution(executionId: string, confirmed: boolean): Promise<SqlResult> {
      const result = await sqlApi.confirm(executionId, confirmed);
      const tab = this.activeTab;
      if (tab && confirmed && result.status === "executed") {
        tab.result = { ...result, need_confirm: false };
      }
      return result;
    },
  },
});

