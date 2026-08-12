<template>
  <div class="users-view">
    <div class="toolbar">
      <n-input v-model:value="search" placeholder="搜索用户名 / 显示名" clearable style="width: 240px" @update:value="reload" />
      <n-select v-model:value="roleFilter" :options="roleOptions" placeholder="按角色筛选" clearable style="width: 180px" @update:value="reload" />
      <div style="flex: 1"></div>
      <n-button type="primary" size="small" @click="openCreate">＋ 新增用户</n-button>
    </div>
    <n-data-table :columns="columns" :data="items" :loading="loading" :bordered="false" size="small" />
    <div class="pager">
      <n-pagination v-model:page="page" :item-count="total" :page-size="pageSize" @update:page="load" />
      <span class="total">共 {{ total }} 条</span>
    </div>

    <n-modal v-model:show="formShow" preset="card" :title="editing ? '编辑用户' : '新增用户'" style="width: 480px">
      <n-form label-placement="left" label-width="90">
        <n-form-item label="用户名">
          <n-input v-model:value="form.username" :disabled="!!editing" placeholder="登录账号" />
        </n-form-item>
        <n-form-item label="显示名">
          <n-input v-model:value="form.display_name" placeholder="显示名称（留空默认用户名）" />
        </n-form-item>
        <n-form-item :label="editing ? '新密码' : '密码'">
          <n-input v-model:value="form.password" type="password" show-password-on="click" :placeholder="editing ? '留空则不修改' : '至少 4 位（默认 123456）'" />
        </n-form-item>
        <n-form-item label="角色">
          <n-select v-model:value="form.role" :options="roleOptions" />
        </n-form-item>
        <n-form-item label="启用">
          <n-switch v-model:value="form.is_active" />
        </n-form-item>
      </n-form>
      <template #footer>
        <div style="display: flex; justify-content: flex-end; gap: 8px">
          <n-button size="small" @click="formShow = false">取消</n-button>
          <n-button size="small" type="primary" :loading="saving" @click="save">保存</n-button>
        </div>
      </template>
    </n-modal>

    <n-modal v-model:show="pwdShow" preset="card" title="重置密码" style="width: 400px">
      <n-input v-model:value="pwdValue" type="password" show-password-on="click" placeholder="新密码（至少 4 位）" />
      <template #footer>
        <div style="display: flex; justify-content: flex-end; gap: 8px">
          <n-button size="small" @click="pwdShow = false">取消</n-button>
          <n-button size="small" type="primary" :loading="saving" @click="savePwd">确认重置</n-button>
        </div>
      </template>
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, h, onMounted, ref } from "vue";
import { NButton, NPopconfirm, NTag, useMessage } from "naive-ui";
import { roleApi, userApi } from "../api";
import type { Role, User } from "../api";

const message = useMessage();
const items = ref<User[]>([]);
const total = ref(0);
const page = ref(1);
const pageSize = 20;
const loading = ref(false);
const saving = ref(false);
const search = ref("");
const roleFilter = ref<string | null>(null);
const roles = ref<Role[]>([]);
const roleOptions = computed(() => roles.value.map((r) => ({ label: r.name, value: r.code })));
const formShow = ref(false);
const editing = ref<User | null>(null);
const form = ref({ username: "", display_name: "", password: "", role: "tech_query", is_active: true });
const pwdShow = ref(false);
const pwdTarget = ref<User | null>(null);
const pwdValue = ref("");

function roleName(code: string) {
  return roles.value.find((r) => r.code === code)?.name || code;
}

function renderActions(row: User) {
  return h(
    "div",
    { style: "display:flex;gap:8px" },
    [
      h(NButton, { size: "tiny", text: true, onClick: () => openEdit(row) }, { default: () => "编辑" }),
      h(NButton, { size: "tiny", text: true, onClick: () => openPwd(row) }, { default: () => "重置密码" }),
      h(
        NPopconfirm,
        { onPositiveClick: () => toggleActive(row) },
        {
          trigger: () => h(NButton, { size: "tiny", text: true }, { default: () => (row.is_active ? "禁用" : "启用") }),
          default: () => (row.is_active ? "确定禁用该用户？" : "确定启用该用户？"),
        },
      ),
      h(
        NPopconfirm,
        { onPositiveClick: () => removeUser(row) },
        {
          trigger: () => h(NButton, { size: "tiny", text: true, type: "error" }, { default: () => "删除" }),
          default: () => "确定删除该用户？",
        },
      ),
    ],
  );
}

const columns = [
  { title: "ID", key: "id", width: 60 },
  { title: "用户名", key: "username", width: 130 },
  { title: "显示名", key: "display_name", width: 140 },
  {
    title: "角色",
    key: "role",
    width: 130,
    render: (row: User) => h(NTag, { size: "small", type: row.role === "admin" ? "error" : "primary" }, { default: () => roleName(row.role) }),
  },
  {
    title: "状态",
    key: "is_active",
    width: 80,
    render: (row: User) =>
      h(NTag, { size: "small", type: row.is_active ? "success" : "default" }, { default: () => (row.is_active ? "启用" : "禁用") }),
  },
  { title: "最后登录", key: "last_login", width: 170 },
  { title: "操作", key: "actions", width: 230, render: (row: User) => renderActions(row) },
];

async function loadRoles() {
  try {
    roles.value = await roleApi.list();
  } catch (e) {
    message.error((e as Error).message);
  }
}

async function load() {
  loading.value = true;
  try {
    const data = await userApi.list({
      page: page.value,
      page_size: pageSize,
      search: search.value || undefined,
      role: roleFilter.value || undefined,
    });
    items.value = data.list;
    total.value = data.total;
  } catch (e) {
    message.error((e as Error).message);
  } finally {
    loading.value = false;
  }
}

function reload() {
  page.value = 1;
  load();
}

function openCreate() {
  editing.value = null;
  Object.assign(form.value, { username: "", display_name: "", password: "", role: "tech_query", is_active: true });
  formShow.value = true;
}

function openEdit(u: User) {
  editing.value = u;
  Object.assign(form.value, { username: u.username, display_name: u.display_name, password: "", role: u.role, is_active: u.is_active });
  formShow.value = true;
}

async function save() {
  if (!form.value.username.trim()) {
    message.warning("请输入用户名");
    return;
  }
  saving.value = true;
  try {
    if (editing.value) {
      const payload: Record<string, unknown> = {
        display_name: form.value.display_name,
        role: form.value.role,
        is_active: form.value.is_active,
      };
      if (form.value.password) payload.password = form.value.password;
      await userApi.update(editing.value.id, payload);
      message.success("更新成功");
    } else {
      await userApi.create({
        username: form.value.username,
        display_name: form.value.display_name,
        password: form.value.password || "123456",
        role: form.value.role,
        is_active: form.value.is_active,
      });
      message.success("创建成功");
    }
    formShow.value = false;
    await load();
  } catch (e) {
    message.error((e as Error).message);
  } finally {
    saving.value = false;
  }
}

async function toggleActive(u: User) {
  try {
    await userApi.update(u.id, { is_active: !u.is_active });
    message.success(u.is_active ? "已禁用" : "已启用");
    await load();
  } catch (e) {
    message.error((e as Error).message);
  }
}

async function removeUser(u: User) {
  try {
    await userApi.remove(u.id);
    message.success("已删除");
    await load();
  } catch (e) {
    message.error((e as Error).message);
  }
}

function openPwd(u: User) {
  pwdTarget.value = u;
  pwdValue.value = "";
  pwdShow.value = true;
}

async function savePwd() {
  if (!pwdTarget.value) return;
  if (!pwdValue.value.trim() || pwdValue.value.length < 4) {
    message.warning("密码至少 4 位");
    return;
  }
  saving.value = true;
  try {
    await userApi.resetPassword(pwdTarget.value.id, pwdValue.value);
    message.success("密码已重置");
    pwdShow.value = false;
  } catch (e) {
    message.error((e as Error).message);
  } finally {
    saving.value = false;
  }
}

onMounted(async () => {
  await loadRoles();
  await load();
});
</script>

<style scoped>
.users-view {
  padding: 16px;
}
.toolbar {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
  align-items: center;
}
.pager {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 12px;
  margin-top: 16px;
}
.total {
  font-size: 12px;
  color: #888;
}
</style>
