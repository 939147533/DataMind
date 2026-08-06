import { defineStore } from "pinia";
import { connectionApi, metadataApi } from "../api";
import type { Connection } from "../api";

export const useConnectionsStore = defineStore("connections", {
  state: () => ({
    list: [] as Connection[],
    total: 0,
    search: "",
    environment: "",
    currentDsId: null as number | null,
    loading: false,
  }),
  actions: {
    async load() {
      this.loading = true;
      try {
        const data = await connectionApi.list({ search: this.search, environment: this.environment, page: 1, page_size: 100 });
        this.list = data.list;
        this.total = data.total;
      } finally {
        this.loading = false;
      }
    },
    async refresh() {
      await this.load();
    },
    setCurrent(dsId: number | null) {
      this.currentDsId = dsId;
    },
    async remove(id: number) {
      await connectionApi.remove(id);
      if (this.currentDsId === id) this.currentDsId = null;
      await this.load();
    },
    async test(data: Record<string, unknown>) {
      return await connectionApi.test(data);
    },
    async clone(id: number) {
      await connectionApi.clone(id);
      await this.load();
    },
    async loadSchemas(dsId: number) {
      return await metadataApi.schemas(dsId);
    },
  },
});
