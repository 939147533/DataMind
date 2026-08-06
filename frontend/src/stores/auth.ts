import { defineStore } from "pinia";
import { ref } from "vue";
import { authApi } from "../api";
import type { User } from "../api";

export const useAuthStore = defineStore("auth", {
  state: () => ({
    user: null as User | null,
  }),
  getters: {
    isLoggedIn: (s) => !!s.user,
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
  },
});
