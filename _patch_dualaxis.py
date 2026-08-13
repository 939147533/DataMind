# -*- coding: utf-8 -*-
path = r"E:\Code\DataMind\frontend\src\components\ChartCard.vue"
src = open(path, encoding="utf-8").read()

old = '''  return {
    ...base,
    grid,
    xAxis,
    yAxis,
    dataZoom: zoomIfNeeded(),
    series,
  };
}'''

new = '''  // 多系列量级差异大时（如笔数 vs 金额）自动拆分双 Y 轴，避免小量级系列被压成 0
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
}'''

assert old in src, "line/bar return block not found"
src = src.replace(old, new, 1)
open(path, "w", encoding="utf-8").write(src)
print("ChartCard.vue dual-axis patched OK")