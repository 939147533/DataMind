<template>
  <div ref="host" class="chart-card"></div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from "vue";
import * as echarts from "echarts";
import type { Chart } from "../api";

const props = defineProps<{ chart: Chart; data: { columns: string[]; rows: unknown[][] } | null }>();
const host = ref<HTMLElement>();
let chart: echarts.ECharts | null = null;

function buildOption() {
  const cols = props.data?.columns || [];
  const rows = props.data?.rows || [];
  const xi = cols.indexOf(props.chart.x_column);
  const yi = cols.indexOf(props.chart.y_column);
  const names = rows.map((r) => String(r[xi] ?? ""));
  const values = rows.map((r) => Number(r[yi] ?? 0));
  if (props.chart.chart_type === "pie") {
    return {
      tooltip: { trigger: "item" },
      legend: { bottom: 0, type: "scroll" },
      series: [{ type: "pie", radius: ["30%", "65%"], data: names.map((n, i) => ({ name: n, value: values[i] })) }],
    };
  }
  return {
    tooltip: { trigger: "axis" },
    legend: { top: 0 },
    grid: { left: 48, right: 24, top: 36, bottom: 40 },
    xAxis: { type: "category", data: names, axisLabel: { interval: 0, rotate: names.length > 8 ? 30 : 0 } },
    yAxis: { type: "value" },
    series: [{ type: props.chart.chart_type === "line" ? "line" : "bar", data: values, smooth: true, itemStyle: { borderRadius: [4, 4, 0, 0] } }],
  };
}

function render() {
  if (!host.value) return;
  if (!chart) chart = echarts.init(host.value);
  chart.setOption(buildOption(), true);
}

function onResize() {
  chart?.resize();
}

onMounted(() => {
  render();
  window.addEventListener("resize", onResize);
});

watch(() => [props.chart, props.data] as const, render, { deep: true });

onBeforeUnmount(() => {
  window.removeEventListener("resize", onResize);
  chart?.dispose();
  chart = null;
});
</script>

<style scoped>
.chart-card {
  width: 100%;
  height: 100%;
  min-height: 220px;
}
</style>

