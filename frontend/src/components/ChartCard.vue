<template>
  <div class="chart-card" :class="{ dark: isDark }">
    <div v-if="isKpi" class="kpi-box">
      <div class="kpi-title">{{ chartTitle }}</div>
      <div class="kpi-value-row">
        <span v-if="prefix" class="kpi-unit">{{ prefix }}</span>
        <span class="kpi-value">{{ kpiValue }}</span>
        <span v-if="suffix" class="kpi-unit">{{ suffix }}</span>
      </div>
      <div v-if="kpiSub" class="kpi-sub">{{ kpiSub }}</div>
    </div>
    <div v-else-if="isProgress" class="progress-box">
      <div class="progress-head">
        <span class="progress-title">{{ chartTitle }}</span>
        <span class="progress-num">{{ prefix }}{{ progressValue }}{{ suffix }}</span>
      </div>
      <div class="progress-track">
        <div class="progress-fill" :style="{ width: progressPct + '%' }"></div>
      </div>
    </div>
    <div v-else ref="host" class="chart-host"></div>
    <div v-if="error" class="chart-msg error">{{ error }}</div>
    <div v-else-if="!data && !isKpi && !isProgress" class="chart-msg">加载中...</div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import * as echarts from "echarts";
import type { Chart } from "../api";

const props = withDefaults(
  defineProps<{
    chart: Chart;
    data: { columns: string[]; rows: unknown[][] } | null;
    dark?: boolean;
    error?: string;
  }>(),
  { dark: false, error: "" }
);

const host = ref<HTMLElement>();
let chart: echarts.ECharts | null = null;
let ro: ResizeObserver | null = null;

const opts = computed<Record<string, any>>(() => {
  try {
    const o = JSON.parse(props.chart.options || "{}");
    return o && typeof o === "object" ? o : {};
  } catch {
    return {};
  }
});

const isDark = computed(() => props.dark || opts.value.theme === "dark");
const chartTitle = computed(() => opts.value.title || props.chart.name || "图表");
const prefix = computed(() => String(opts.value.number_prefix || ""));
const suffix = computed(() => String(opts.value.number_suffix || ""));
const yCols = computed(() => (props.chart.y_column || "").split(",").map((s) => s.trim()).filter(Boolean));

const isKpi = computed(() => props.chart.chart_type === "kpi");
const isProgress = computed(() => props.chart.chart_type === "progress");
const kpiSub = computed(() => String(opts.value.sub_label || ""));

function num(v: unknown): number {
  const n = Number(v);
  return isFinite(n) ? n : 0;
}

function fmt(n: number): string {
  if (!isFinite(n)) return "0";
  const abs = Math.abs(n);
  if (abs >= 1e8) return (n / 1e8).toFixed(2) + "亿";
  if (abs >= 1e4) return (n / 1e4).toFixed(2) + "万";
  return n.toLocaleString("zh-CN", { maximumFractionDigits: 2 });
}

const firstValue = computed(() => {
  const rows = props.data?.rows || [];
  const yi = colIdx(yCols.value[0] || props.chart.y_column);
  if (!rows.length || yi < 0) return 0;
  return num(rows[0][yi]);
});

const kpiValue = computed(() => fmt(firstValue.value));
const progressValue = computed(() => firstValue.value);
const progressPct = computed(() => {
  const min = num(opts.value.min ?? 0);
  const max = num(opts.value.max ?? 100);
  const span = max - min || 1;
  return Math.max(0, Math.min(100, ((firstValue.value - min) / span) * 100));
});

const PALETTE_LIGHT = ["#5470c6", "#91cc75", "#fac858", "#ee6666", "#73c0de", "#3ba272", "#fc8452", "#9a60b4", "#ea7ccc"];
const PALETTE_DARK = ["#4f8df9", "#36cfc9", "#b37feb", "#ff9f43", "#ff6b81", "#7bed9f", "#70a1ff", "#ffa502", "#2ed573"];
const palette = computed(() => (isDark.value ? PALETTE_DARK : PALETTE_LIGHT));

function categoryData(): string[] {
  const rows = props.data?.rows || [];
  const xi = colIdx(props.chart.x_column);
  return rows.map((r) => {
    const v = String(r[xi] ?? "");
    // 日期时间值精简显示：2026-07-14T00:00:00 -> 2026-07-14
    return v.replace(/T00:00:00(?:\.\d+)?(Z|$)/, "").slice(0, 16);
  });
}

function colIdx(colName: string): number {
  const cols = props.data?.columns || [];
  const name = String(colName || "").toUpperCase();
  return cols.findIndex((c) => String(c).toUpperCase() === name);
}

function seriesValues(colName: string): number[] {
  const cols = props.data?.columns || [];
  const rows = props.data?.rows || [];
  const yi = colIdx(colName);
  return rows.map((r) => num(r[yi]));
}

function zoomIfNeeded() {
  if (categoryData().length <= 12) return [];
  return [
    { type: "inside" as const },
    { type: "slider" as const, height: 14, bottom: 4, borderColor: "transparent", backgroundColor: "rgba(128,128,128,0.15)" },
  ];
}

function tooltipFmt(params: any): string {
  const list = Array.isArray(params) ? params : [params];
  return list
    .map((p) => {
      const label = p.seriesName ? p.seriesName + "<br/>" : "";
      const val = Array.isArray(p.value) ? p.value[p.value.length - 1] : p.value;
      return label + p.name + ": " + prefix.value + fmt(Number(val)) + suffix.value;
    })
    .join("<br/>");
}

function buildOption(): any {
  const type = props.chart.chart_type;
  const names = categoryData();
  const seriesCols = yCols.value.length ? yCols.value : [props.chart.y_column];
  const dark = isDark.value;
  const textColor = dark ? "#d6e4ff" : "#333";
  const labelColor = dark ? "#9fb6d9" : "#666";
  const lineColor = dark ? "rgba(255,255,255,0.25)" : "#ddd";
  const splitColor = dark ? "rgba(255,255,255,0.08)" : "#eee";
  const c = palette.value;

  const base = {
    animationDuration: 800,
    animationEasing: "cubicOut" as const,
    backgroundColor: "transparent",
    color: c,
    textStyle: { color: textColor },
    tooltip: { trigger: "axis" as const, backgroundColor: dark ? "rgba(20,30,52,0.92)" : "#fff", borderColor: dark ? "#2b3c5e" : "#ddd", textStyle: { color: textColor }, formatter: tooltipFmt },
    legend: { top: 0, textStyle: { color: labelColor }, type: "scroll" as const },
  };

  if (type === "pie" || type === "funnel") {
    const values = seriesValues(seriesCols[0]);
    const data = names.map((n, i) => ({ name: n, value: values[i] }));
    if (type === "pie") {
      return {
        ...base,
        tooltip: { ...base.tooltip, trigger: "item" as const, formatter: (p: any) => p.name + ": " + prefix.value + fmt(Number(p.value)) + suffix.value + " (" + p.percent + "%)" },
        legend: { ...base.legend, bottom: 0, top: "auto" },
        series: [{ type: "pie", radius: ["28%", "62%"], center: ["50%", "48%"], itemStyle: { borderRadius: 6, borderColor: dark ? "#0d1526" : "#fff", borderWidth: 2 }, label: { color: textColor }, data }],
      };
    }
    return {
      ...base,
      tooltip: { ...base.tooltip, trigger: "item" as const, formatter: (p: any) => p.name + ": " + prefix.value + fmt(Number(p.value)) + suffix.value },
      series: [{ type: "funnel", left: "12%", width: "76%", top: 36, bottom: 24, minSize: "18%", label: { color: textColor, formatter: (p: any) => p.name + " " + prefix.value + fmt(Number(p.value)) + suffix.value }, data }],
    };
  }

  if (type === "radar") {
    const rawAbs = seriesValues(seriesCols[0]).map((v) => Math.abs(v));
    const maxVal = Math.max(1, ...rawAbs) * 1.15;
    return {
      ...base,
      tooltip: { ...base.tooltip, trigger: "item" as const, formatter: (p: any) => p.name + "<br/>" + p.marker + " " + prefix.value + fmt(Number(p.value)) + suffix.value },
      radar: {
        indicator: names.map((n) => ({ name: n, max: maxVal })),
        axisName: { color: labelColor },
        splitLine: { lineStyle: { color: splitColor } },
        splitArea: { areaStyle: { color: dark ? ["rgba(79,141,249,0.04)", "rgba(79,141,249,0.09)"] : ["rgba(84,112,198,0.03)", "rgba(84,112,198,0.08)"] } },
        axisLine: { lineStyle: { color: lineColor } },
      },
      series: seriesCols.map((col, i) => ({ name: col, type: "radar" as const, symbolSize: 4, lineStyle: { width: 2 }, areaStyle: { opacity: 0.15 }, data: [{ value: seriesValues(col) }] })),
    };
  }

  if (type === "gauge") {
    const maxVal = num(opts.value.max ?? 100);
    const minVal = num(opts.value.min ?? 0);
    return {
      ...base,
      series: [
        {
          type: "gauge",
          min: minVal,
          max: maxVal,
          radius: "92%",
          startAngle: 210,
          endAngle: -30,
          progress: { show: true, width: 14, itemStyle: { color: dark ? "#36cfc9" : "#5470c6" } },
          axisLine: { lineStyle: { width: 14, color: [[1, dark ? "rgba(255,255,255,0.12)" : "#e8ecf5"]] } },
          axisTick: { show: false },
          splitLine: { length: 8, lineStyle: { color: dark ? "#2b3c5e" : "#ddd" } },
          axisLabel: { distance: 16, color: labelColor },
          pointer: { itemStyle: { color: dark ? "#ff9f43" : "#fc8452" } },
          detail: { valueAnimation: true, formatter: (v: number) => prefix.value + fmt(v) + suffix.value, color: textColor, fontSize: 22, offsetCenter: [0, "68%"] },
          data: [{ value: firstValue.value, name: chartTitle.value }],
          title: { color: labelColor, fontSize: 12, offsetCenter: [0, "92%"] },
        },
      ],
    };
  }

  const xAxis: any = {
    type: "category",
    data: names,
    axisLabel: { color: labelColor, interval: 0, rotate: names.length > 8 ? 28 : 0 },
    axisLine: { lineStyle: { color: lineColor } },
  };
  const yAxis: any = {
    type: "value",
    axisLabel: { color: labelColor, formatter: (v: number) => fmt(v) },
    splitLine: { lineStyle: { color: splitColor } },
  };
  const grid: any = { left: 8, right: 16, top: 40, bottom: names.length > 12 ? 40 : 24, containLabel: true };

  if (type === "rank") {
    const ordered = names
      .map((n, i) => ({ n, v: seriesValues(seriesCols[0])[i] }))
      .sort((a, b) => b.v - a.v)
      .slice(0, 15);
    return {
      ...base,
      grid,
      xAxis: { type: "value", axisLabel: { color: labelColor, formatter: (v: number) => fmt(v) }, splitLine: { lineStyle: { color: splitColor } } },
      yAxis: { type: "category", data: ordered.map((o) => o.n), axisLabel: { color: labelColor }, axisLine: { lineStyle: { color: lineColor } } },
      series: seriesCols.map((col, i) => ({
        name: col,
        type: "bar" as const,
        data: ordered.map((o) => o.v),
        barWidth: "52%",
        itemStyle: { borderRadius: [0, 6, 6, 0], color: c[i % c.length] },
        label: { show: true, position: "right" as const, color: labelColor, formatter: (p: any) => prefix.value + fmt(Number(p.value)) + suffix.value },
      })),
    };
  }

  if (type === "scatter") {
    return {
      ...base,
      grid,
      xAxis: { ...xAxis, type: "value" as const, name: props.chart.x_column || "", axisLabel: { color: labelColor, formatter: (v: number) => fmt(v) } },
      yAxis,
      series: seriesCols.map((col, i) => ({
        name: col,
        type: "scatter" as const,
        symbolSize: 10,
        itemStyle: { color: c[i % c.length], opacity: 0.75 },
        data: names.map((n, j) => [num(n), seriesValues(col)[j]]),
      })),
    };
  }

  const isArea = type === "area";
  const isLine = type === "line" || isArea;
  const series = seriesCols.map((col, i) => {
    const s: any = {
      name: col,
      type: "line",
      data: seriesValues(col),
      smooth: true,
      symbolSize: 5,
      lineStyle: { width: 2.5, color: c[i % c.length] },
      itemStyle: { color: c[i % c.length] },
    };
    if (isArea) {
      s.areaStyle = {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: c[i % c.length] + "55" },
          { offset: 1, color: c[i % c.length] + "05" },
        ]),
      };
    }
    if (type === "bar") {
      s.type = "bar";
      s.barWidth = "52%";
      s.itemStyle = {
        borderRadius: [4, 4, 0, 0],
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: c[i % c.length] },
          { offset: 1, color: c[i % c.length] + "88" },
        ]),
      };
    }
    return s;
  });

  // 多系列量级差异大时（如笔数 vs 金额）自动拆分双 Y 轴，避免小量级系列被压成 0
  const maxs = seriesCols.map((col) => Math.max(0, ...seriesValues(col)));
  const positive = maxs.filter((m) => m > 0);
  const mx = Math.max(1, ...maxs);
  const mn = positive.length ? Math.min(...positive) : mx;
  let yAxes: any[] = [];
  let axisOf: number[] = maxs.map(() => 0);
  if (maxs.length >= 2 && mx / Math.max(mn, 1) >= 50) {
    const order = maxs.map((m, i) => ({ i, m })).sort((a, b) => b.m - a.m);
    const groups: number[][] = [[], []];
    const groupMax: number[] = [0, 0];
    for (const { i, m } of order) {
      let g: number;
      if (groupMax[1] === 0) {
        g = groupMax[0] === 0 || groupMax[0] / Math.max(m, 1) < 50 ? 0 : 1;
      } else {
        const r0 = groupMax[0] / Math.max(m, 1);
        const r1 = groupMax[1] / Math.max(m, 1);
        g = r1 < r0 ? 1 : 0;
      }
      groups[g].push(i);
      groupMax[g] = Math.max(groupMax[g], m);
    }
    axisOf = new Array(maxs.length).fill(0);
    groups[1].forEach((i) => (axisOf[i] = 1));
    yAxes = groups.map((g, gi) => ({
      type: "value",
      axisLabel: { color: labelColor, formatter: (v: number) => fmt(v) },
      splitLine: gi === 0 ? { lineStyle: { color: splitColor } } : { show: false },
    }));
  }

  return {
    ...base,
    grid,
    xAxis,
    yAxis: yAxes.length ? yAxes : yAxis,
    dataZoom: zoomIfNeeded(),
    series: yAxes.length ? series.map((s, i) => ({ ...s, yAxisIndex: axisOf[i] })) : series,
  };
}

function render() {
  if (isKpi.value || isProgress.value) return;
  if (!host.value) return;
  if (!chart) {
    chart = echarts.init(host.value);
    ro = new ResizeObserver(() => chart?.resize());
    ro.observe(host.value);
  }
  chart.setOption(buildOption(), true);
}

onMounted(render);
watch(() => [props.chart, props.data, isDark.value] as const, render, { deep: true });

onBeforeUnmount(() => {
  ro?.disconnect();
  ro = null;
  chart?.dispose();
  chart = null;
});
</script>

<style scoped>
.chart-card {
  position: relative;
  width: 100%;
  height: 100%;
  min-height: 180px;
}
.chart-host {
  width: 100%;
  height: 100%;
}
.chart-msg {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  color: #999;
  pointer-events: none;
}
.chart-msg.error {
  color: #e88080;
}
.kpi-box,
.progress-box {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 8px;
  padding: 12px 16px;
  box-sizing: border-box;
}
.kpi-title {
  font-size: 13px;
  color: #8fa3c8;
}
.kpi-value-row {
  display: flex;
  align-items: baseline;
  gap: 4px;
}
.kpi-value {
  font-size: 34px;
  font-weight: 700;
  line-height: 1.1;
  background: linear-gradient(120deg, #4f8df9, #36cfc9);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
  color: #4f8df9;
}
.kpi-unit {
  font-size: 14px;
  color: #8fa3c8;
}
.kpi-sub {
  font-size: 12px;
  color: #8fa3c8;
}
.progress-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  font-size: 13px;
}
.progress-title {
  color: #8fa3c8;
}
.progress-num {
  font-weight: 600;
  color: #36cfc9;
}
.progress-track {
  height: 12px;
  border-radius: 6px;
  background: rgba(128, 128, 160, 0.18);
  overflow: hidden;
}
.progress-fill {
  height: 100%;
  border-radius: 6px;
  background: linear-gradient(90deg, #4f8df9, #36cfc9);
  transition: width 0.6s ease;
}
</style>
