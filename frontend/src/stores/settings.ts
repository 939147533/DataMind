import { defineStore } from "pinia";
import { ref } from "vue";
import { configApi } from "../api";

export const useSettingsStore = defineStore("settings", {
  state: () => ({
    theme: "light" as string,
    language: "zh" as string,
    editor_font_size: "14",
    editor_tab_size: "4",
    autocomplete: "true",
    loaded: false,
  }),
  getters: {
    isDark: (s) => s.theme === "dark",
  },
  actions: {
    async load() {
      try {
        const data = await configApi.settings();
        const v = data.values;
        this.theme = v.theme || "light";
        this.language = v.language || "zh";
        this.editor_font_size = v.editor_font_size || "14";
        this.editor_tab_size = v.editor_tab_size || "4";
        this.autocomplete = v.autocomplete || "true";
        this.loaded = true;
        this.applyTheme();
      } catch {
        /* 未登录时忽略 */
      }
    },
    async setTheme(theme: string) {
      this.theme = theme;
      this.applyTheme();
      await this.save();
    },
    async setLanguage(language: string) {
      this.language = language;
      await this.save();
    },
    applyTheme() {
      const el = document.documentElement;
      el.style.colorScheme = this.theme;
    },
    async save() {
      try {
        await configApi.saveSettings({
          theme: this.theme,
          language: this.language,
          editor_font_size: this.editor_font_size,
          editor_tab_size: this.editor_tab_size,
          autocomplete: this.autocomplete,
        });
      } catch {
        /* ignore */
      }
    },
  },
});
