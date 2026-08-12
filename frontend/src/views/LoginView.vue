<template>
  <div class="login-wrap">
    <n-card class="login-card" :bordered="true">
      <div class="login-header">
        <div class="login-logo">🗄️</div>
        <h2>数据库 Agent Web 应用</h2>
        <p class="login-sub">自然语言查询 · SQL 工作台 · 多数据库管理</p>
      </div>
      <n-form @keyup.enter="doLogin">
        <n-form-item label="用户名">
          <n-input v-model:value="username" placeholder="admin" />
        </n-form-item>
        <n-form-item label="密码">
          <n-input v-model:value="password" type="password" show-password-on="click" placeholder="admin123" />
        </n-form-item>
        <n-button type="primary" block :loading="loading" @click="doLogin">登 录</n-button>
      </n-form>
      <div class="login-hint">默认账户：admin / admin123</div>
    </n-card>
  </div>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { useMessage } from "naive-ui";
import { useRoute, useRouter } from "vue-router";
import { useAuthStore } from "../stores/auth";

const auth = useAuthStore();
const router = useRouter();
const route = useRoute();
const message = useMessage();
const username = ref("admin");
const password = ref("");
const loading = ref(false);

async function doLogin() {
  if (!username.value || !password.value) {
    message.warning("请输入用户名和密码");
    return;
  }
  loading.value = true;
  try {
    await auth.login(username.value, password.value);
    message.success("登录成功");
    router.push(String(route.query.redirect || "/" + (auth.defaultHome() || "workspace")));
  } catch (e) {
    message.error((e as Error).message);
  } finally {
    loading.value = false;
  }
}
</script>

<style scoped>
.login-wrap {
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #eef2f7 0%, #dbe4ee 100%);
}
.login-card {
  width: 380px;
  padding: 12px 8px;
}
.login-header {
  text-align: center;
  margin-bottom: 20px;
}
.login-logo {
  font-size: 42px;
}
.login-header h2 {
  margin: 8px 0 4px;
}
.login-sub {
  color: #888;
  font-size: 13px;
  margin: 0;
}
.login-hint {
  margin-top: 16px;
  text-align: center;
  color: #999;
  font-size: 12px;
}
</style>
