<template>
  <n-layout has-sider style="height: 100vh">
    <n-layout-sider bordered :width="200" :native-scrollbar="false" collapse-mode="width" :collapsed-width="64" :collapsed="collapsed" show-trigger @collapse="collapsed = true" @expand="collapsed = false">
      <div class="logo" @click="router.push('/workspace')">
        <span class="logo-icon">🗄️</span>
        <span v-if="!collapsed" class="logo-text">数据库 Agent</span>
      </div>
      <n-menu :collapsed="collapsed" :collapsed-width="64" :value="activeKey" :options="menuOptions" @update:value="onMenuSelect" />
    </n-layout-sider>
    <n-layout>
      <n-layout-header bordered class="topbar">
        <div class="topbar-title">{{ pageTitle }}</div>
        <div class="topbar-actions">
          <n-button quaternary circle @click="toggleTheme" :title="settings.isDark ? '切换亮色' : '切换暗色'">
            {{ settings.isDark ? "🌙" : "☀️" }}
          </n-button>
          <n-dropdown :options="userOptions" @select="onUserSelect">
            <n-button quaternary>
              <template #icon><span>👤</span></template>
              {{ auth.user?.display_name || auth.user?.username }}
            </n-button>
          </n-dropdown>
        </div>
      </n-layout-header>
      <n-layout-content :native-scrollbar="false" class="content">
        <router-view />
      </n-layout-content>
    </n-layout>
  </n-layout>
</template>

<script setup lang="ts">
import { computed, h, ref } from "vue";
import { NIcon, useMessage } from "naive-ui";
import { useRoute, useRouter } from "vue-router";
import { useAuthStore } from "../stores/auth";
import { useSettingsStore } from "../stores/settings";

const router = useRouter();
const route = useRoute();
const message = useMessage();
const auth = useAuthStore();
const settings = useSettingsStore();
const collapsed = ref(false);

const menuItems = [
  { label: "智能查询", key: "smart-query", permission: "ai_query", icon: () => h(NIcon, null, { default: () => "🤖" }) },
  { label: "SQL 工作台", key: "workspace", permission: "workspace", icon: () => h(NIcon, null, { default: () => "🖥️" }) },
  { label: "可视化报表", key: "reports", permission: "reports", icon: () => h(NIcon, null, { default: () => "📊" }) },
  { label: "用户管理", key: "users", permission: "users", icon: () => h(NIcon, null, { default: () => "👥" }) },
  { label: "角色管理", key: "roles", permission: "roles", icon: () => h(NIcon, null, { default: () => "🛡️" }) },
  { label: "系统设置", key: "settings", permissionAny: ["settings", "connections"], icon: () => h(NIcon, null, { default: () => "⚙️" }) },
  { label: "运维监控", key: "monitor", permissionAny: ["monitor", "audit"], icon: () => h(NIcon, null, { default: () => "📈" }) },
];
const menuOptions = computed(() =>
  menuItems
    .filter((m) => (m.permission ? auth.hasPermission(m.permission) : m.permissionAny ? auth.hasAnyPermission(...m.permissionAny) : true))
    .map((m) => ({ label: m.label, key: m.key, icon: m.icon })),
);

const activeKey = computed(() => String(route.name || "workspace"));
const pageTitle = computed(() => {
  const map: Record<string, string> = {
    "smart-query": "智能查询",
    workspace: "SQL 工作台",
    reports: "可视化报表",
    users: "用户管理",
    roles: "角色管理",
    settings: "系统设置",
    monitor: "运维监控",
  };
  return map[String(route.name)] || "数据库 Agent";
});

const userOptions = [
  { label: "退出登录", key: "logout" },
];

function onMenuSelect(key: string) {
  router.push({ name: key });
}

function onUserSelect(key: string) {
  if (key === "logout") {
    auth.logout().then(() => router.push("/login"));
  }
}

function toggleTheme() {
  settings.setTheme(settings.isDark ? "light" : "dark");
}
</script>

<style scoped>
.logo {
  display: flex;
  align-items: center;
  gap: 8px;
  height: 56px;
  padding: 0 16px;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
}
.logo-icon {
  font-size: 20px;
}
.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 56px;
  padding: 0 16px;
}
.topbar-title {
  font-size: 16px;
  font-weight: 600;
}
.topbar-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
.content {
  height: calc(100vh - 56px);
  overflow: auto;
}
</style>
