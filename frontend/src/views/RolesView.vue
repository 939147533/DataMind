<template>
  <div class="roles-view">
    <n-grid :cols="2" :x-gap="16" responsive="screen" item-responsive>
      <n-grid-item span="24 m:9 l:9">
        <n-card size="small" title="角色列表" class="role-card">
          <template #header-extra>
            <n-button size="tiny" type="primary" @click="openCreate">＋ 新增角色</n-button>
          </template>
          <n-data-table :columns="roleColumns" :data="roles" :loading="loading" :bordered="false" size="small" :row-class-name="rowClassName" :row-props="rowProps" />
        </n-card>
      </n-grid-item>
      <n-grid-item span="24 m:15 l:15">
        <n-card size="small" :title="selected ? selected.name + '（' + selected.code + '）' : '角色详情'" class="detail-card">
          <template #header-extra>
            <n-button v-if="selected" size="tiny" type="error" :disabled="selected.is_builtin" @click="removeRole">删除角色</n-button>
          </template>
          <n-empty v-if="!selected" description="请选择左侧角色进行配置" style="padding: 60px 0" />
          <div v-else>
            <div class="detail-grid">
              <div class="field">
                <span class="label">名称</span>
                <n-input v-model:value="detail.name" :disabled="selected.is_builtin" size="small" />
              </div>
              <div class="field">
                <span class="label">编码</span>
                <n-input v-model:value="detail.code" :disabled="selected.is_builtin" size="small" />
              </div>
              <div class="field field-wide">
                <span class="label">说明</span>
                <n-input v-model:value="detail.description" type="textarea" :rows="2" size="small" />
              </div>
            </div>

            <n-divider title-placement="left" style="margin: 12px 0">功能权限</n-divider>
            <div v-for="group in permissionGroups" :key="group.group" class="perm-group">
              <div class="perm-group-title">{{ group.group }}</div>
              <div class="perm-items">
                <n-checkbox
                  v-for="item in group.items"
                  :key="item.code"
                  :checked="detail.permissions.includes(item.code)"
                  @update:checked="(v) => togglePerm(item.code, v)"
                >
                  {{ item.name }}
                  <span class="perm-desc">{{ item.desc }}</span>
                </n-checkbox>
              </div>
            </div>
            <div class="save-row">
              <n-button size="small" type="primary" :loading="savingPerm" @click="savePermissions">保存权限</n-button>
            </div>

            <n-divider title-placement="left" style="margin: 16px 0 12px">角色成员（{{ memberIds.length }} 人）</n-divider>
            <div class="member-box">
              <n-checkbox-group v-model:value="memberIds">
                <n-checkbox v-for="u in allUsers" :key="u.id" :value="u.id" :label="u.display_name + '（' + u.username + '）'" class="member-item" />
              </n-checkbox-group>
            </div>
            <div class="save-row">
              <n-button size="small" type="primary" :loading="savingMember" @click="saveMembers">保存成员</n-button>
            </div>
          </div>
        </n-card>
      </n-grid-item>
    </n-grid>

    <n-modal v-model:show="createShow" preset="card" title="新增角色" style="width: 520px">
      <n-form label-placement="left" label-width="80">
        <n-form-item label="编码">
          <n-input v-model:value="createForm.code" placeholder="唯一编码，如 analyst" />
        </n-form-item>
        <n-form-item label="名称">
          <n-input v-model:value="createForm.name" placeholder="角色名称" />
        </n-form-item>
        <n-form-item label="说明">
          <n-input v-model:value="createForm.description" type="textarea" :rows="2" placeholder="角色说明" />
        </n-form-item>
        <n-form-item label="权限">
          <div class="create-perms">
            <n-checkbox v-for="item in allPermItems" :key="item.code" :checked="createForm.permissions.includes(item.code)" @update:checked="(v) => toggleCreatePerm(item.code, v)">
              {{ item.name }}
            </n-checkbox>
          </div>
        </n-form-item>
      </n-form>
      <template #footer>
        <div style="display: flex; justify-content: flex-end; gap: 8px">
          <n-button size="small" @click="createShow = false">取消</n-button>
          <n-button size="small" type="primary" :loading="savingPerm" @click="saveCreate">创建</n-button>
        </div>
      </template>
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, h, onMounted, ref } from "vue";
import { NButton, NPopconfirm, NTag, useMessage } from "naive-ui";
import { PERMISSION_GROUPS, roleApi, userApi } from "../api";
import type { Role, User } from "../api";

const message = useMessage();
const roles = ref<Role[]>([]);
const allUsers = ref<User[]>([]);
const loading = ref(false);
const savingPerm = ref(false);
const savingMember = ref(false);
const selected = ref<Role | null>(null);
const detail = ref({ name: "", code: "", description: "", permissions: [] as string[] });
const memberIds = ref<number[]>([]);
const createShow = ref(false);
const createForm = ref({ code: "", name: "", description: "", permissions: [] as string[] });

const permissionGroups = PERMISSION_GROUPS;
const allPermItems = computed(() => permissionGroups.flatMap((g) => g.items));

function rowClassName(row: Role) {
  return selected.value && selected.value.id === row.id ? "role-row-active" : "";
}

function rowProps(row: Role) {
  return { style: "cursor:pointer", onClick: () => selectRole(row) };
}

function selectRole(row: Role) {
  selected.value = row;
  Object.assign(detail.value, {
    name: row.name,
    code: row.code,
    description: row.description,
    permissions: [...(row.permissions || [])],
  });
  loadMembers();
}

async function loadRoles() {
  loading.value = true;
  try {
    roles.value = await roleApi.list();
    if (!selected.value && roles.value.length) {
      selectRole(roles.value[0]);
    }
  } catch (e) {
    message.error((e as Error).message);
  } finally {
    loading.value = false;
  }
}

async function loadMembers() {
  if (!selected.value) return;
  try {
    const [users, members] = await Promise.all([userApi.list({ page: 1, page_size: 100 }), roleApi.users(selected.value.id)]);
    allUsers.value = users.list;
    memberIds.value = members.map((m) => m.id);
  } catch (e) {
    message.error((e as Error).message);
  }
}

function togglePerm(code: string, checked: boolean) {
  if (checked) {
    if (!detail.value.permissions.includes(code)) detail.value.permissions.push(code);
  } else {
    detail.value.permissions = detail.value.permissions.filter((p) => p !== code);
  }
}

function toggleCreatePerm(code: string, checked: boolean) {
  if (checked) {
    if (!createForm.value.permissions.includes(code)) createForm.value.permissions.push(code);
  } else {
    createForm.value.permissions = createForm.value.permissions.filter((p) => p !== code);
  }
}

async function savePermissions() {
  if (!selected.value) return;
  savingPerm.value = true;
  try {
    await roleApi.update(selected.value.id, { permissions: detail.value.permissions });
    message.success("权限已保存");
    await loadRoles();
    if (selected.value) selectRole(selected.value);
  } catch (e) {
    message.error((e as Error).message);
  } finally {
    savingPerm.value = false;
  }
}

async function saveMembers() {
  if (!selected.value) return;
  savingMember.value = true;
  try {
    await roleApi.setUsers(selected.value.id, memberIds.value);
    message.success("成员已保存");
    await loadRoles();
  } catch (e) {
    message.error((e as Error).message);
  } finally {
    savingMember.value = false;
  }
}

async function removeRole() {
  if (!selected.value) return;
  try {
    await roleApi.remove(selected.value.id);
    message.success("已删除");
    selected.value = null;
    await loadRoles();
  } catch (e) {
    message.error((e as Error).message);
  }
}

function openCreate() {
  Object.assign(createForm.value, { code: "", name: "", description: "", permissions: [] });
  createShow.value = true;
}

async function saveCreate() {
  if (!createForm.value.code.trim()) {
    message.warning("请输入角色编码");
    return;
  }
  if (!createForm.value.name.trim()) {
    message.warning("请输入角色名称");
    return;
  }
  savingPerm.value = true;
  try {
    const role = await roleApi.create({
      code: createForm.value.code,
      name: createForm.value.name,
      description: createForm.value.description,
      permissions: createForm.value.permissions,
    });
    message.success("创建成功");
    createShow.value = false;
    selected.value = role;
    selectRole(role);
    await loadRoles();
  } catch (e) {
    message.error((e as Error).message);
  } finally {
    savingPerm.value = false;
  }
}

const roleColumns = [
  { title: "名称", key: "name", width: 110, render: (row: Role) => h(NTag, { size: "small", type: row.code === "admin" ? "error" : row.is_builtin ? "primary" : "default" }, { default: () => row.name }) },
  { title: "编码", key: "code", width: 120 },
  { title: "用户数", key: "user_count", width: 70 },
  { title: "类型", key: "is_builtin", width: 70, render: (row: Role) => (row.is_builtin ? "内置" : "自定义") },
  {
    title: "操作",
    key: "actions",
    width: 80,
    render: (row: Role) =>
      h(
        NPopconfirm,
        { onPositiveClick: () => removeRole() },
        {
          trigger: () => h(NButton, { size: "tiny", text: true, type: "error", disabled: row.is_builtin }, { default: () => "删除" }),
          default: () => "确定删除该角色？",
        },
      ),
  },
];

onMounted(async () => {
  await loadRoles();
  await loadMembers();
});
</script>

<style scoped>
.roles-view {
  padding: 16px;
}
.role-card {
  height: 100%;
}
.detail-card {
  min-height: 560px;
}
.detail-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}
.field {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 200px;
}
.field-wide {
  width: 100%;
}
.label {
  font-size: 13px;
  color: #666;
  white-space: nowrap;
}
.perm-group {
  margin-bottom: 10px;
}
.perm-group-title {
  font-size: 13px;
  font-weight: 600;
  color: #555;
  margin-bottom: 6px;
}
.perm-items {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 18px;
  padding: 8px;
  background: rgba(127, 127, 127, 0.06);
  border-radius: 6px;
}
.perm-desc {
  font-size: 12px;
  color: #999;
  margin-left: 4px;
}
.save-row {
  display: flex;
  justify-content: flex-end;
  margin-top: 10px;
}
.member-box {
  max-height: 260px;
  overflow: auto;
  padding: 8px;
  background: rgba(127, 127, 127, 0.06);
  border-radius: 6px;
}
.member-item {
  display: block;
  margin-bottom: 4px;
}
.create-perms {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 16px;
}
:deep(.role-row-active) {
  background: rgba(24, 160, 88, 0.12) !important;
}
</style>
