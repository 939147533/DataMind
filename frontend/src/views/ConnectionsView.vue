<template>
  <div class="connections-view">
    <div class="toolbar">
      <n-input v-model:value="store.search" placeholder="搜索名称 / 主机" clearable style="width: 240px" @update:value="onFilter" />
      <n-select v-model:value="store.environment" :options="envOptions" placeholder="全部环境" clearable style="width: 140px" @update:value="onFilter" />
      <div style="flex: 1"></div>
      <n-button type="primary" @click="openCreate">＋ 新建连接</n-button>
    </div>

    <n-data-table
      :columns="columns"
      :data="store.list"
      :loading="store.loading"
      :pagination="pagination"
      :row-key="(row: any) => row.id"
      :bordered="false"
    />

    <n-modal v-model:show="showModal" preset="card" :title="editingId ? '编辑连接' : '新建连接'" style="width: 640px">
      <n-form label-placement="left" label-width="110px">
        <n-grid :cols="2" :x-gap="12">
          <n-form-item-gi label="连接名称"><n-input v-model:value="form.name" placeholder="如：本地演示库" /></n-form-item-gi>
          <n-form-item-gi label="数据库类型">
            <n-select v-model:value="form.db_type" :options="dbTypeOptions" @update:value="onDbTypeChange" />
          </n-form-item-gi>
          <n-form-item-gi label="主机"><n-input v-model:value="form.host" placeholder="localhost" :disabled="form.db_type === 'sqlite'" /></n-form-item-gi>
          <n-form-item-gi label="端口"><n-input-number v-model:value="form.port" :disabled="form.db_type === 'sqlite'" style="width: 100%" /></n-form-item-gi>
          <n-form-item-gi label="用户名"><n-input v-model:value="form.username" :disabled="form.db_type === 'sqlite'" /></n-form-item-gi>
          <n-form-item-gi label="密码"><n-input v-model:value="form.password" type="password" show-password-on="click" :placeholder="editingId ? '留空则不修改' : ''" /></n-form-item-gi>
          <n-form-item-gi :label="form.db_type === 'sqlite' ? '数据库文件' : '默认数据库'">
            <n-input v-model:value="form.database_name" :placeholder="form.db_type === 'sqlite' ? '留空使用内置演示库 demo.db' : '数据库名 / 服务名'" />
          </n-form-item-gi>
          <n-form-item-gi label="环境">
            <n-select v-model:value="form.environment" :options="envOptions" />
          </n-form-item-gi>
        </n-grid>
        <n-collapse>
          <n-collapse-item title="SSH 隧道（可选）" name="ssh">
            <n-form-item label="启用 SSH"><n-switch v-model:value="form.ssh_enabled" /></n-form-item>
            <n-grid :cols="2" :x-gap="12">
              <n-form-item-gi label="跳板机"><n-input v-model:value="form.ssh_host" /></n-form-item-gi>
              <n-form-item-gi label="SSH 端口"><n-input-number v-model:value="form.ssh_port" style="width: 100%" /></n-form-item-gi>
              <n-form-item-gi label="SSH 用户"><n-input v-model:value="form.ssh_user" /></n-form-item-gi>
              <n-form-item-gi label="认证方式">
                <n-select v-model:value="form.ssh_auth_type" :options="[{ label: '密码', value: 'password' }, { label: '密钥', value: 'key' }]" />
              </n-form-item-gi>
            </n-grid>
          </n-collapse-item>
        </n-collapse>
        <n-form-item label="描述" style="margin-top: 8px">
          <n-input v-model:value="form.description" type="textarea" :rows="2" />
        </n-form-item>
      </n-form>
      <template #footer>
        <div style="display: flex; justify-content: flex-end; gap: 8px">
          <n-button @click="testForm">测试连接</n-button>
          <n-button type="primary" :loading="saving" @click="save">保存</n-button>
        </div>
      </template>
    </n-modal>

    <n-modal v-model:show="showTest" preset="card" title="连接测试结果" style="width: 420px">
      <n-result v-if="testResult" :status="testResult.success ? 'success' : 'error'" :title="testResult.success ? '连接成功' : '连接失败'" :description="testResult.message" />
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, h, onMounted, reactive, ref } from "vue";
import { NButton, NPopconfirm, NTag, useMessage } from "naive-ui";
import { useRouter } from "vue-router";
import { connectionApi } from "../api";
import { useConnectionsStore } from "../stores/connections";

const store = useConnectionsStore();
const router = useRouter();
const message = useMessage();
const showModal = ref(false);
const showTest = ref(false);
const saving = ref(false);
const editingId = ref<number | null>(null);
const testResult = ref<{ success: boolean; message: string } | null>(null);

const envOptions = [
  { label: "开发", value: "dev" },
  { label: "测试", value: "test" },
  { label: "生产", value: "prod" },
];
const dbTypeOptions = [
  { label: "SQLite", value: "sqlite" },
  { label: "MySQL", value: "mysql" },
  { label: "PostgreSQL", value: "postgresql" },
  { label: "Oracle", value: "oracle" },
  { label: "OceanBase", value: "oceanbase" },
  { label: "GoldenDB", value: "goldendb" },
  { label: "MongoDB", value: "mongodb" },
];

const emptyForm = () => ({
  name: "",
  db_type: "sqlite" as string,
  host: "localhost",
  port: null as number | null,
  username: "",
  password: "",
  database_name: "",
  ssh_enabled: false,
  ssh_host: "",
  ssh_port: 22,
  ssh_user: "",
  ssh_auth_type: "password",
  ssh_private_key: "",
  environment: "dev",
  description: "",
});
const form = reactive(emptyForm());

const pagination = computed(() => ({
  pageSize: 20,
  itemCount: store.total,
  showSizePicker: false,
}));

function envTag(env: string) {
  const map: Record<string, { type: "success" | "info" | "warning" | "error"; label: string }> = {
    dev: { type: "info", label: "开发" },
    test: { type: "warning", label: "测试" },
    prod: { type: "error", label: "生产" },
  };
  const item = map[env] || { type: "default" as const, label: env };
  return h(NTag, { type: item.type, size: "small" }, { default: () => item.label });
}

const columns = [
  { title: "名称", key: "name" },
  {
    title: "类型",
    key: "db_type",
    render: (row: any) => row.db_type.toUpperCase(),
  },
  { title: "主机", key: "host", render: (row: any) => (row.db_type === "sqlite" ? (row.database_name || "demo.db") : `${row.host}:${row.port || ""}`) },
  { title: "环境", key: "environment", render: (row: any) => envTag(row.environment) },
  {
    title: "状态",
    key: "status",
    render: (row: any) =>
      h(NTag, { type: row.status === "active" ? "success" : row.status === "error" ? "error" : "default", size: "small" }, { default: () => (row.status === "active" ? "正常" : row.status === "error" ? "异常" : "未知") }),
  },
  {
    title: "操作",
    key: "actions",
    width: 260,
    render: (row: any) =>
      h("div", { style: "display:flex;gap:6px" }, [
        h(NButton, { size: "small", onClick: () => goWorkspace(row.id) }, { default: () => "打开" }),
        h(NButton, { size: "small", onClick: () => testRow(row.id) }, { default: () => "测试" }),
        h(NButton, { size: "small", onClick: () => openEdit(row) }, { default: () => "编辑" }),
        h(NButton, { size: "small", onClick: () => doClone(row.id) }, { default: () => "克隆" }),
        h(
          NPopconfirm,
          { onPositiveClick: () => doDelete(row.id) },
          { trigger: () => h(NButton, { size: "small", type: "error", secondary: true }, { default: () => "删除" }), default: () => "确认删除该连接？" },
        ),
      ]),
  },
];

function onFilter() {
  store.load();
}

function onDbTypeChange() {
  form.port = form.db_type === "mysql" || form.db_type === "goldendb" ? 3306 : form.db_type === "postgresql" ? 5432 : form.db_type === "oracle" ? 1521 : form.db_type === "oceanbase" ? 2881 : form.db_type === "mongodb" ? 27017 : (null as number | null);
}

function openCreate() {
  editingId.value = null;
  Object.assign(form, emptyForm());
  showModal.value = true;
}

function openEdit(row: any) {
  editingId.value = row.id;
  Object.assign(form, emptyForm(), {
    name: row.name,
    db_type: row.db_type,
    host: row.host,
    port: row.port,
    username: row.username,
    database_name: row.database_name,
    ssh_enabled: row.ssh_enabled,
    ssh_host: row.ssh_host,
    ssh_port: row.ssh_port,
    ssh_user: row.ssh_user,
    ssh_auth_type: row.ssh_auth_type,
    environment: row.environment,
    description: row.description,
  });
  showModal.value = true;
}

async function testForm() {
  if (editingId.value && !form.password) {
    try {
      const result = await connectionApi.connect(editingId.value);
      testResult.value = { success: true, message: result.status === "active" ? "连接成功" : result.status };
    } catch (e) {
      const msg = (e as { message?: string; detail?: string }).message || (e as { detail?: string }).detail || "连接失败";
      testResult.value = { success: false, message: msg };
    }
    showTest.value = true;
    return;
  }
  const result = await store.test({ ...form });
  testResult.value = result;
  showTest.value = true;
}

async function testRow(id: number) {
  try {
    const result = await connectionApi.connect(id);
    testResult.value = { success: true, message: result.status === "active" ? "连接成功" : result.status };
  } catch (e) {
    const msg = (e as { message?: string; detail?: string }).message || (e as { detail?: string }).detail || "连接失败";
    testResult.value = { success: false, message: msg };
  }
  showTest.value = true;
}

async function save() {
  if (!form.name) {
    message.warning("请输入连接名称");
    return;
  }
  saving.value = true;
  try {
    if (editingId.value) {
      await connectionApi.update(editingId.value, { ...form });
      message.success("更新成功");
    } else {
      await connectionApi.create({ ...form });
      message.success("创建成功");
    }
    showModal.value = false;
    await store.load();
  } catch (e) {
    message.error((e as Error).message);
  } finally {
    saving.value = false;
  }
}

async function doClone(id: number) {
  await store.clone(id);
  message.success("克隆成功");
}

async function doDelete(id: number) {
  await store.remove(id);
  message.success("删除成功");
}

function goWorkspace(id: number) {
  store.setCurrent(id);
  router.push("/workspace");
}

onMounted(() => store.load());
</script>

<style scoped>
.connections-view {
  padding: 16px;
}
.toolbar {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
  align-items: center;
}
</style>
