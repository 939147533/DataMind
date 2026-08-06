<template>
  <n-config-provider :theme="settings.isDark ? darkTheme : null" :locale="zhCN" :date-locale="dateZhCN">
    <n-message-provider>
      <n-dialog-provider>
        <n-notification-provider>
          <router-view />
        </n-notification-provider>
      </n-dialog-provider>
    </n-message-provider>
  </n-config-provider>
</template>

<script setup lang="ts">
import { onMounted } from "vue";
import { darkTheme, dateZhCN, zhCN } from "naive-ui";
import { useSettingsStore } from "./stores/settings";

const settings = useSettingsStore();
onMounted(() => settings.load());
</script>
