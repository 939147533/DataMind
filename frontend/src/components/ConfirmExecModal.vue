<template>
  <n-modal v-model:show="show" preset="card" :title="title" style="width: 560px">
    <n-alert v-if="info" :type="danger ? 'error' : 'warning'" :title="danger ? '危险操作' : '写操作确认'">
      <p style="margin: 0 0 8px">{{ info.preview || "该操作将修改数据，请仔细核对。" }}</p>
      <n-tag :type="danger ? 'error' : 'warning'" size="small">{{ info.operation_type }} · {{ info.risk_level }}</n-tag>
    </n-alert>
    <n-input v-if="info" v-model:value="displaySql" type="textarea" :rows="8" readonly style="margin-top: 12px" />
    <template #footer>
      <div style="display: flex; justify-content: flex-end; gap: 8px">
        <n-button @click="cancel">取消</n-button>
        <n-button type="primary" :loading="loading" @click="ok">确认执行</n-button>
      </div>
    </template>
  </n-modal>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";

const props = defineProps<{ show: boolean; info: { sql_text: string; operation_type: string; risk_level: string; preview?: string; execution_id: string } | null; loading?: boolean }>();
const emit = defineEmits<{ (e: "update:show", v: boolean): void; (e: "confirm", confirmed: boolean): void }>();
const show = computed({
  get: () => props.show,
  set: (v) => emit("update:show", v),
});
const displaySql = ref("");
watch(
  () => props.info?.sql_text,
  (v) => (displaySql.value = v || ""),
  { immediate: true },
);
const danger = computed(() => props.info?.risk_level === "danger");
const title = computed(() => (danger.value ? "⚠️ 危险操作确认" : "写操作确认"));

function ok() {
  emit("confirm", true);
}
function cancel() {
  emit("confirm", false);
}
</script>
