<template>
  <div class="object-tree">
    <div v-if="!dsId" class="empty-tip">请先选择一个数据源</div>
    <n-tree
      v-else
      block-line
      :data="treeData"
      remote
      :on-load="handleLoad"
      :render-suffix="renderSuffix"
      @update:selected-keys="onSelect"
      :selected-keys="selectedKeys"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, h, ref, watch } from "vue";
import { NButton, NIcon } from "naive-ui";
import { metadataApi } from "../api";

const props = defineProps<{ dsId: number | null; dsName: string }>();
const emit = defineEmits<{ (e: "open-table", name: string, schema?: string): void; (e: "show-ddl", kind: string, name: string): void; (e: "show-sequence", name: string, detail: unknown): void }>();

interface TreeNode {
  key: string;
  label: string;
  isLeaf?: boolean;
  children?: TreeNode[];
  type?: string;
  name?: string;
  schema?: string;
  detail?: unknown;
  loaded?: boolean;
}

const treeData = ref<TreeNode[]>([]);
const selectedKeys = ref<string[]>([]);

const rootNodes = (): TreeNode[] => [
  { key: "fav", label: "📌 收藏", loaded: false, isLeaf: false },
  { key: "tables", label: "📁 表", loaded: false, isLeaf: false },
  { key: "views", label: "👁️ 视图", loaded: false, isLeaf: false },
  { key: "functions", label: "ƒ 函数", loaded: false, isLeaf: false },
  { key: "procedures", label: "⚙️ 存储过程", loaded: false, isLeaf: false },
  { key: "triggers", label: "🔔 触发器", loaded: false, isLeaf: false },
  { key: "sequences", label: "🔢 序列", loaded: false, isLeaf: false },
];

watch(
  () => props.dsId,
  async (id) => {
    selectedKeys.value = [];
    treeData.value = rootNodes();
    if (!id) return;
    try {
      const favs = await metadataApi.favorites(id);
      const favNode = treeData.value.find((n) => n.key === "fav");
      if (favNode) {
        favNode.children = favs.map((f) => ({ key: `fav:${f.table_name}`, label: `⭐ ${f.table_name}`, isLeaf: true, type: "table", name: f.table_name, schema: f.schema_name }));
        favNode.loaded = true;
      }
    } catch {
      /* ignore */
    }
  },
  { immediate: true },
);

async function handleLoad(node: TreeNode): Promise<void> {
  if (!props.dsId) return;
  const kind = node.key;
  if (node.loaded) return;
  try {
    if (kind === "tables") {
      const tables = await metadataApi.tables(props.dsId);
      node.children = tables.map((t) => ({ key: `table:${t}`, label: `📄 ${t}`, isLeaf: true, type: "table", name: t }));
    } else if (kind === "views") {
      const views = await metadataApi.objects(props.dsId, "views");
      node.children = views.map((v) => ({ key: `view:${v}`, label: `👁️ ${v}`, isLeaf: true, type: "view", name: v as string }));
    } else if (kind === "functions") {
      const items = await metadataApi.objects(props.dsId, "functions");
      node.children = items.map((v) => ({ key: `fn:${v}`, label: `ƒ ${v}`, isLeaf: true, type: "function", name: v as string }));
    } else if (kind === "procedures") {
      const items = await metadataApi.objects(props.dsId, "procedures");
      node.children = items.map((v) => ({ key: `proc:${v}`, label: `⚙️ ${v}`, isLeaf: true, type: "procedure", name: v as string }));
    } else if (kind === "triggers") {
      const items = await metadataApi.objects(props.dsId, "triggers");
      node.children = items.map((v) => ({ key: `trg:${v}`, label: `🔔 ${v}`, isLeaf: true, type: "trigger", name: (v as { name: string }).name }));
    } else if (kind === "sequences") {
      const items = await metadataApi.objects(props.dsId, "sequences");
      node.children = items.map((v) => ({ key: `seq:${v}`, label: `🔢 ${(v as { name: string }).name}`, isLeaf: true, type: "sequence", name: (v as { name: string }).name, detail: v }));
    }
    node.loaded = true;
  } catch (e) {
    node.children = [{ key: `err:${kind}`, label: `加载失败：${(e as Error).message}`, isLeaf: true }];
    node.loaded = true;
  }
}

function onSelect(keys: string[]) {
  if (!keys.length) return;
  const key = keys[0];
  const node = findNode(treeData.value, key);
  if (!node || !node.isLeaf || !node.type) return;
  if (node.type === "table" || node.type === "view") {
    emit("open-table", node.name as string, node.schema);
  } else if (node.type === "trigger") {
    emit("show-ddl", "triggers", node.name as string);
  } else if (node.type === "sequence") {
    emit("show-sequence", node.name as string, node.detail);
  } else if (node.type === "function" || node.type === "procedure") {
    emit("show-ddl", node.type === "function" ? "functions" : "procedures", node.name as string);
  }
}

function findNode(nodes: TreeNode[], key: string): TreeNode | null {
  for (const n of nodes) {
    if (n.key === key) return n;
    if (n.children) {
      const found = findNode(n.children, key);
      if (found) return found;
    }
  }
  return null;
}

function renderSuffix({ option }: { option: TreeNode }) {
  if (option.type === "table") {
    return h(
      NButton,
      {
        size: "tiny",
        text: true,
        onClick: (e: MouseEvent) => {
          e.stopPropagation();
          if (props.dsId) {
            metadataApi.addFavorite(props.dsId, "", option.name as string).then(() => {
              const fav = treeData.value.find((n) => n.key === "fav");
              if (fav) {
                fav.children = [...(fav.children || []), { key: `fav:${option.name}`, label: `⭐ ${option.name}`, isLeaf: true, type: "table", name: option.name }];
                fav.loaded = true;
              }
            });
          }
        },
      },
      { default: () => "⭐" },
    );
  }
  return null;
}
</script>

<style scoped>
.object-tree {
  height: 100%;
  overflow: auto;
  padding: 8px 4px;
}
.empty-tip {
  color: #999;
  text-align: center;
  padding: 24px 8px;
  font-size: 13px;
}
</style>
