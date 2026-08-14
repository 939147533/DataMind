import { defineStore } from "pinia";
import { authApi } from "../api";
import type { User } from "../api";

export const useAuthStore = defineStore("auth", {
  state: () => ({
    user: null as User | null,
  }),
  getters: {
    isLoggedIn: (s) => !!s.user,
    permissions: (s): string[] => s.user?.permissions || [],
  },
  actions: {
    async login(username: string, password: string) {
      const data = await authApi.login(username, password);
      this.user = data.user;
    },
    async fetchMe() {
      try {
        this.user = await authApi.me();
      } catch {
        this.user = null;
      }
    },
    async logout() {
      try {
        await authApi.logout();
      } finally {
        this.user = null;
      }
    },
    hasPermission(permission: string): boolean {
      const perms = this.permissions;
      return perms.includes("*") || perms.includes(permission);
    },
    hasAnyPermission(...permissions: string[]): boolean {
      const perms = this.permissions;
      if (perms.includes("*")) return true;
      return permissions.some((p) => perms.includes(p));
    },
    defaultHome(): string {
      const routePerm: Record<string, string> = {
        "smart-query": "ai_query",
        workspace: "workspace",
        reports: "reports",
        settings: "settings",
        users: "users",
        roles: "roles",
      };
      const routeAny: Record<string, string[]> = {
        monitor: ["monitor", "audit"],
      };
      const order = ["smart-query", "workspace", "reports", "settings", "users", "roles", "monitor"];
      return order.find((r) => (routeAny[r] ? this.hasAnyPermission(...routeAny[r]) : this.hasPermission(routePerm[r]))) || "";
    },
  },
});
