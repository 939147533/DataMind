<template>
  <div ref="gridEl" class="grid-stack" :class="{ 'gs-editable': editable, dark }">
    <div
      v-for="item in gridItems"
      :key="item.chart_id"
      class="grid-stack-item"
      :gs-id="String(item.chart_id)"
      :gs-x="item.x"
      :gs-y="item.y"
      :gs-w="item.w"
      :gs-h="item.h"
    >
      <div class="grid-stack-item-content">
        <ChartCard
          v-if="chartById(item.chart_id)"
          :chart="chartById(item.chart_id)!"
          :data="dataById(item.chart_id)"
          :dark="dark"
          :error="errById(item.chart_id)"
        />
        <div v-else class="gs-missing">图表不存在或已删除</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { GridStack } from "gridstack";
import "gridstack/dist/gridstack.min.css";
import type { ChartWithData } from "../api";
import ChartCard from "./ChartCard.vue";

export interface DashboardLayoutItem {
  chart_id: number;
  x: number;
  y: number;
  w: number;
  h: number;
}
export interface DashboardLayout {
  columns?: number;
  rowHeight?: number;
  margin?: number;
  refresh_interval?: number;
  items?: DashboardLayoutItem[];
}

const props = withDefaults(
  defineProps<{
    charts: ChartWithData[];
    layout: string;
    editable?: boolean;
    dark?: boolean;
    dataMap?: Record<number, { columns: string[]; rows: unknown[][] } | null>;
    errorMap?: Record<number, string>;
  }>(),
  { editable: false, dark: false, dataMap: () => ({}), errorMap: () => ({}) }
);

const emit = defineEmits<{ (e: "layout-change", layout: string): void }>();

const gridEl = ref<HTMLElement>();
let grid: GridStack | null = null;
let lastEmitted = "";

function parseLayout(): DashboardLayout {
  try {
    const o = JSON.parse(props.layout || "{}");
    return o && typeof o === "object" ? o : {};
  } catch {
    return {};
  }
}

const layoutObj = computed(() => parseLayout());

const chartMap = computed(() => {
  const m: Record<number, ChartWithData> = {};
  props.charts.forEach((c) => (m[c.id] = c));
  return m;
});

const gridItems = computed<DashboardLayoutItem[]>(() => {
  const items = (layoutObj.value.items || []).filter((it) => chartMap.value[it.chart_id]);
  const inLayout = new Set(items.map((it) => it.chart_id));
  let autoY = 0;
  for (const c of props.charts) {
    if (!inLayout.has(c.id)) {
      items.push({ chart_id: c.id, x: 0, y: autoY, w: 6, h: 4 });
      autoY += 4;
    }
  }
  return items;
});

function chartById(id: number): ChartWithData | undefined {
  return chartMap.value[id];
}
function dataById(id: number): { columns: string[]; rows: unknown[][] } | null {
  if (props.dataMap[id] !== undefined) return props.dataMap[id];
  const c = chartMap.value[id];
  if (c && Array.isArray(c.columns) && Array.isArray(c.rows)) return { columns: c.columns, rows: c.rows };
  return null;
}
function errById(id: number): string {
  if (props.errorMap[id]) return props.errorMap[id];
  return chartMap.value[id]?.error || "";
}

function initGrid() {
  if (!gridEl.value) return;
  if (grid) {
    grid.destroy(false);
    grid = null;
  }
  const lo = layoutObj.value;
  const g = GridStack.init(
    {
      column: lo.columns || 12,
      cellHeight: lo.rowHeight || 44,
      margin: lo.margin ?? 8,
      float: true,
      animate: true,
      staticGrid: !props.editable,
      disableDrag: !props.editable,
      disableResize: !props.editable,
      minRow: 2,
      columnOpts: { breakpoints: [] },
    },
    gridEl.value
  );
  if (!g) return;
  grid = g;
  g.on("change", () => {
    const nodes = ((grid?.save(false) as { id?: string; x?: number; y?: number; w?: number; h?: number }[]) || []).filter((n) => n.id != null);
    const items: DashboardLayoutItem[] = nodes.map((n) => ({
      chart_id: Number(n.id),
      x: n.x ?? 0,
      y: n.y ?? 0,
      w: n.w ?? 6,
      h: n.h ?? 4,
    }));
    const out = JSON.stringify({ ...lo, items });
    lastEmitted = out;
    emit("layout-change", out);
  });
}

onMounted(() => {
  initGrid();
});

watch(
  () => props.layout,
  async (val) => {
    if (val !== lastEmitted) {
      await nextTick();
      initGrid();
    }
  }
);

watch(
  () => props.editable,
  (val) => {
    grid?.setStatic(!val);
  }
);

onBeforeUnmount(() => {
  grid?.destroy(false);
  grid = null;
});
</script>

<style scoped>
.grid-stack {
  width: 100%;
}
.grid-stack-item-content {
  overflow: hidden;
  border-radius: 10px;
  background: #fff;
  border: 1px solid #e6ebf5;
  box-shadow: 0 1px 4px rgba(30, 60, 120, 0.08);
}
.grid-stack.dark .grid-stack-item-content {
  background: linear-gradient(160deg, rgba(20, 32, 60, 0.92), rgba(12, 20, 42, 0.96));
  border: 1px solid rgba(79, 141, 249, 0.28);
  box-shadow: 0 4px 24px rgba(0, 10, 40, 0.55);
}
.gs-editable .grid-stack-item-content {
  cursor: move;
}
.gs-missing {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  font-size: 12px;
  color: #999;
}
</style>
