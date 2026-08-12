<template>
  <div class="settings-view">
    <n-tabs v-model:value="activeTab" type="line">
      <n-tab-pane name="ai" tab="AI 配置">
        <div class="toolbar">
          <n-button type="primary" size="small" @click="openAiCreate">＋ 新增 AI 配置</n-button>
        </div>
        <n-grid :cols="2" :x-gap="16" :y-gap="16" responsive="screen" item-responsive>
          <n-grid-item v-for="c in aiConfigs" :key="c.id" span="12 m:12 l:12">
            <n-card size="small" :title="`${providerLabel(c.provider)} · ${c.model_name || '未设置模型'}`">
              <template #header-extra>
                <div class="card-actions">
                  <n-tag v-if="c.is_default" size="tiny" type="primary">默认</n-tag>
                  <n-tag v-if="!c.is_active" size="tiny">停用</n-tag>
                  <n-button size="tiny" text :loading="testingAiId === c.id" @click="testAi(c.id)">测试</n-button>
                  <n-button size="tiny" text @click="openAiEdit(c)">编辑</n-button>
                  <n-button v-if="!c.is_default" size="tiny" text @click="setDefault(c.id)">设为默认</n-button>
                  <n-popconfirm @positive-click="removeAi(c.id)">
                    <template #trigger><n-button size="tiny" text type="error">删除</n-button></template>
                    确定删除该配置？
                  </n-popconfirm>
                </div>
              </template>
              <div class="ai-meta">
                <div>API Base：{{ c.api_base || "（默认地址）" }}</div>
                <div>模型：{{ c.model_name || "—" }}</div>
                <div>API Key：{{ c.has_key ? "已配置 🔒" : "未配置" }}</div>
                <div>参数：max_tokens = {{ c.max_tokens }} · temperature = {{ c.temperature }}</div>
              </div>
            </n-card>
          </n-grid-item>
        </n-grid>
        <n-empty v-if="!aiConfigs.length" description="暂无 AI 配置，添加后即可使用 Agent" style="padding: 60px 0" />
      </n-tab-pane>

      <n-tab-pane name="driver" tab="JDBC 驱动">
        <div class="toolbar">
          <n-button size="small" type="primary" @click="driverModal = true">＋ 上传驱动</n-button>
        </div>
        <n-data-table :columns="driverColumns" :data="drivers" size="small" :bordered="false" :loading="driverLoading" />
      </n-tab-pane>

      <n-tab-pane name="prefs" tab="偏好设置">
        <n-card size="small" style="max-width: 560px">
          <n-form label-placement="left" label-width="120px">
            <n-form-item label="界面主题">
              <n-radio-group v-model:value="settings.theme" @update:value="settings.setTheme">
                <n-radio value="light">亮色</n-radio>
                <n-radio value="dark">暗色</n-radio>
              </n-radio-group>
            </n-form-item>
            <n-form-item label="语言">
              <n-select v-model:value="settings.language" :options="[{ label: '简体中文', value: 'zh' }, { label: 'English', value: 'en' }]" style="width: 200px" />
            </n-form-item>
            <n-form-item label="编辑器字号">
              <n-input-number v-model:value="fontSize" :min="10" :max="28" style="width: 160px" />
            </n-form-item>
            <n-form-item label="Tab 宽度">
              <n-input-number v-model:value="tabSize" :min="2" :max="8" style="width: 160px" />
            </n-form-item>
            <n-form-item label="自动补全">
              <n-switch v-model:value="autocomplete" />
            </n-form-item>
            <n-form-item label="">
              <n-button type="primary" :loading="savingPrefs" @click="savePrefs">保存设置</n-button>
            </n-form-item>
          </n-form>
        </n-card>
      </n-tab-pane>
    </n-tabs>

    <!-- AI 配置编辑 -->
    <n-modal v-model:show="aiModal" preset="card" :title="editingAi ? '编辑 AI 配置' : '新增 AI 配置'" style="width: 560px">
      <n-form label-placement="left" label-width="110px">
        <n-form-item label="提供商">
          <n-select v-model:value="aiForm.provider" :options="providerOptions" />
        </n-form-item>
        <n-form-item label="API Base">
          <n-input v-model:value="aiForm.api_base" placeholder="留空使用默认；Ollama 填 http://localhost:11434/v1" />
        </n-form-item>
        <n-form-item label="模型名称">
          <n-input v-model:value="aiForm.model_name" placeholder="如 gpt-4o-mini / claude-3-5-sonnet / qwen2.5" />
        </n-form-item>
        <n-form-item label="API Key">
          <n-input v-model:value="aiForm.api_key" type="password" show-password-on="click" :placeholder="editingAi ? '留空则保持不变' : ''" />
        </n-form-item>
        <n-grid :cols="2" :x-gap="12">
          <n-form-item-gi label="Max Tokens"><n-input-number v-model:value="aiForm.max_tokens" :min="1" :max="128000" style="width: 100%" /></n-form-item-gi>
          <n-form-item-gi label="Temperature"><n-input-number v-model:value="aiForm.temperature" :min="0" :max="2" :step="0.1" style="width: 100%" /></n-form-item-gi>
        </n-grid>
        <n-form-item label="启用">
          <n-switch v-model:value="aiForm.is_active" />
        </n-form-item>
        <n-form-item label="设为默认">
          <n-switch v-model:value="aiForm.is_default" />
        </n-form-item>
      </n-form>
      <n-alert v-if="aiTestResult" :type="aiTestResult.ok ? 'success' : 'error'" style="margin-top: 12px">
        {{ aiTestResult.text }}
      </n-alert>
      <template #footer>
        <div style="display: flex; justify-content: flex-end; gap: 8px">
          <n-button :loading="testingForm" @click="testAiForm">测试连通性</n-button>
          <n-button type="primary" :loading="aiSaving" @click="saveAi">保存</n-button>
        </div>
      </template>
    </n-modal>

    <!-- 驱动上传 -->
    <n-modal v-model:show="driverModal" preset="card" title="上传 JDBC 驱动" style="width: 480px">
      <n-form label-placement="left" label-width="100px">
        <n-form-item label="数据库类型"><n-input v-model:value="driverForm.db_type" placeholder="如 oracle / mysql" /></n-form-item>
        <n-form-item label="驱动类"><n-input v-model:value="driverForm.driver_class" placeholder="如 oracle.jdbc.OracleDriver" /></n-form-item>
        <n-form-item label="版本"><n-input v-model:value="driverForm.version" placeholder="如 21.5.0.0" /></n-form-item>
        <n-form-item label="JAR 文件">
          <n-upload :default-upload="false" :custom-request="uploadDriver" accept=".jar">
            <n-button>选择文件</n-button>
          </n-upload>
        </n-form-item>
      </n-form>
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, h, onMounted, reactive, ref } from "vue";
import { NButton, NPopconfirm, useMessage } from "naive-ui";
import type { UploadCustomRequestOptions } from "naive-ui";
import { configApi } from "../api";
import type { AIConfig } from "../api";
import { useSettingsStore } from "../stores/settings";

const message = useMessage();
const settings = useSettingsStore();
const activeTab = ref("ai");
const aiConfigs = ref<AIConfig[]>([]);
const drivers = ref<Record<string, unknown>[]>([]);
const driverLoading = ref(false);
const aiModal = ref(false);
const aiSaving = ref(false);
const editingAi = ref<AIConfig | null>(null);
const testingAiId = ref<number | null>(null);
const testingForm = ref(false);
const aiTestResult = ref<{ ok: boolean; text: string } | null>(null);
const driverModal = ref(false);
const savingPrefs = ref(false);

const providerOptions = [
  { label: "OpenAI（或兼容网关）", value: "openai" },
  { label: "Anthropic Claude", value: "claude" },
  { label: "Ollama（本地）", value: "ollama" },
];

const aiForm = reactive({ provider: "openai", api_base: "", model_name: "", api_key: "", max_tokens: 4096, temperature: 0.7, is_active: true, is_default: false });
const driverForm = reactive({ db_type: "", driver_class: "", version: "" });

const fontSize = computed({
  get: () => Number(settings.editor_font_size || 14),
  set: (v) => (settings.editor_font_size = String(v)),
});
const tabSize = computed({
  get: () => Number(settings.editor_tab_size || 4),
  set: (v) => (settings.editor_tab_size = String(v)),
});
const autocomplete = computed({
  get: () => settings.autocomplete === "true",
  set: (v) => (settings.autocomplete = String(v)),
});

function providerLabel(p: string) {
  return providerOptions.find((o) => o.value === p)?.label || p;
}

async function loadAi() {
  try {
    aiConfigs.value = await configApi.listAi();
  } catch (e) {
    message.error((e as Error).message);
  }
}

async function loadDrivers() {
  driverLoading.value = true;
  try {
    drivers.value = await configApi.drivers();
  } catch {
    /* ignore */
  } finally {
    driverLoading.value = false;
  }
}

function openAiCreate() {
  editingAi.value = null;
  aiTestResult.value = null;
  Object.assign(aiForm, { provider: "openai", api_base: "", model_name: "", api_key: "", max_tokens: 4096, temperature: 0.7, is_active: true, is_default: false });
  aiModal.value = true;
}

function openAiEdit(c: AIConfig) {
  editingAi.value = c;
  aiTestResult.value = null;
  Object.assign(aiForm, {
    provider: c.provider,
    api_base: c.api_base,
    model_name: c.model_name,
    api_key: "",
    max_tokens: c.max_tokens,
    temperature: c.temperature,
    is_active: c.is_active,
    is_default: c.is_default,
  });
  aiModal.value = true;
}

async function testAi(id: number) {
  testingAiId.value = id;
  try {
    const r = await configApi.testAi({ config_id: id });
    const text = r.message + (r.latency_ms != null ? `（${r.latency_ms} ms）` : "");
    if (r.success) message.success(text);
    else message.error(text);
  } catch (e) {
    message.error((e as Error).message);
  } finally {
    testingAiId.value = null;
  }
}

async function testAiForm() {
  if (!aiForm.model_name.trim()) {
    message.warning("请输入模型名称");
    return;
  }
  testingForm.value = true;
  aiTestResult.value = null;
  try {
    const r = await configApi.testAi({
      ...(editingAi.value ? { config_id: editingAi.value.id } : {}),
      provider: aiForm.provider,
      api_key: aiForm.api_key || undefined,
      api_base: aiForm.api_base,
      model_name: aiForm.model_name,
      max_tokens: aiForm.max_tokens,
      temperature: aiForm.temperature,
    });
    aiTestResult.value = { ok: r.success, text: r.message + (r.latency_ms != null ? `（${r.latency_ms} ms）` : "") };
    if (r.success) message.success(aiTestResult.value.text);
  } catch (e) {
    aiTestResult.value = { ok: false, text: (e as Error).message };
  } finally {
    testingForm.value = false;
  }
}

async function saveAi() {
  if (!aiForm.model_name.trim()) {
    message.warning("请输入模型名称");
    return;
  }
  aiSaving.value = true;
  try {
    const payload: Record<string, unknown> = { ...aiForm };
    if (editingAi.value) {
      if (!payload.api_key) delete payload.api_key;
      await configApi.updateAi(editingAi.value.id, payload);
      message.success("更新成功");
    } else {
      await configApi.createAi(payload);
      message.success("创建成功");
    }
    aiModal.value = false;
    await loadAi();
  } catch (e) {
    message.error((e as Error).message);
  } finally {
    aiSaving.value = false;
  }
}

async function setDefault(id: number) {
  try {
    await configApi.setDefaultAi(id);
    message.success("已设为默认模型");
    await loadAi();
  } catch (e) {
    message.error((e as Error).message);
  }
}

async function removeAi(id: number) {
  try {
    await configApi.deleteAi(id);
    message.success("已删除");
    await loadAi();
  } catch (e) {
    message.error((e as Error).message);
  }
}

async function uploadDriver(options: UploadCustomRequestOptions) {
  const file = options.file.file;
  if (!file) return;
  const form = new FormData();
  form.append("file", file);
  form.append("db_type", driverForm.db_type);
  form.append("driver_class", driverForm.driver_class);
  form.append("version", driverForm.version);
  try {
    await configApi.uploadDriver(form);
    options.onFinish();
    message.success("上传成功");
    driverModal.value = false;
    await loadDrivers();
  } catch (e) {
    options.onError();
    message.error((e as Error).message);
  }
}

async function removeDriver(id: number) {
  try {
    await configApi.deleteDriver(id);
    message.success("已删除");
    await loadDrivers();
  } catch (e) {
    message.error((e as Error).message);
  }
}

const driverColumns = [
  { title: "ID", key: "id", width: 60 },
  { title: "数据库类型", key: "db_type", width: 110 },
  { title: "驱动类", key: "driver_class", ellipsis: { tooltip: true } },
  { title: "版本", key: "version", width: 110 },
  { title: "文件", key: "file_name", ellipsis: { tooltip: true } },
  { title: "大小 (KB)", key: "file_size", width: 90, render: (row: any) => Math.round((row.file_size || 0) / 1024) },
  { title: "上传时间", key: "upload_time", width: 170 },
  {
    title: "操作",
    key: "actions",
    width: 80,
    render: (row: any) =>
      h(
        NPopconfirm,
        { onPositiveClick: () => removeDriver(row.id) },
        {
          trigger: () => h(NButton, { size: "tiny", text: true, type: "error" }, { default: () => "删除" }),
          default: () => "确定删除该驱动？",
        },
      ),
  },
];

async function savePrefs() {
  savingPrefs.value = true;
  try {
    await settings.save();
    message.success("设置已保存");
  } finally {
    savingPrefs.value = false;
  }
}

onMounted(async () => {
  await settings.load();
  await loadAi();
  await loadDrivers();
});
</script>

<style scoped>
.settings-view {
  padding: 16px;
  height: 100%;
  overflow: auto;
}
.toolbar {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 16px;
}
.card-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}
.ai-meta {
  font-size: 13px;
  color: #666;
  line-height: 1.9;
}
</style>
