import fs from "node:fs/promises";
import { PresentationFile, FileBlob } from "@oai/artifact-tool";
const p = await PresentationFile.importPptx(await FileBlob.load("/Users/ly/Code/DataMind/.ppt-build/draft-v12.pptx"));
const s = p.slides.add();
const box = s.shapes.add({
  geometry: "roundRect",
  position: { left: 80, top: 80, width: 400, height: 70 },
  fill: "#F5F7FB",
  line: { style: "solid", fill: "#DDE4EF", width: 1 },
  borderRadius: 8,
});
console.log("box ok", box.id);
const tb = s.shapes.add({ geometry: "textbox", position: { left: 92, top: 88, width: 380, height: 22 } });
tb.text = "① 前端层  Vue 3 · TypeScript · Vite · Pinia";
const tries = {
  fontSize: () => { tb.text.fontSize = 13; },
  typeface: () => { tb.text.typeface = "微软雅黑"; },
  color: () => { tb.text.color = "#0B5FFF"; },
  bold: () => { tb.text.bold = true; },
  wrap: () => { tb.text.wrap = "none"; },
  align: () => { tb.text.alignment = "left"; },
  insets: () => { tb.text.insets = 0; },
  vAlign: () => { tb.text.verticalAlignment = "middle"; },
};
for (const [k, fn] of Object.entries(tries)) {
  try { fn(); console.log("OK   ", k); } catch (e) { console.log("FAIL ", k, "->", String(e.message).slice(0, 120)); }
}
const tb2 = s.shapes.add({ geometry: "textbox", position: { left: 92, top: 112, width: 380, height: 40 } });
tb2.text = "智能查询 · SQL 工作台 · 可视化报表 / 大屏 · 连接管理";
try { tb2.text.style = { fontSize: 11.5, color: "#334155" }; console.log("OK    text.style object"); } catch (e) { console.log("FAIL  text.style ->", String(e.message).slice(0,120)); }
const out = "/Users/ly/Code/DataMind/.ppt-build/probe8.pptx";
await (await PresentationFile.exportPptx(p)).save(out);
const back = await PresentationFile.importPptx(await FileBlob.load(out));
const idx = (await back.inspect({ select: "$.slides[*]", include: ["index"] })).records.length - 1;
const r = await back.inspect({ select: `$.slides[?(@.index==${idx})].elements[*]`, include: ["id","kind","text","position","style"] });
for (const e of (r.records||[])) console.log("  ->", e.kind, JSON.stringify(e.position), JSON.stringify(e.style), JSON.stringify((e.text||"").slice(0,40)));
const png = await back.export({ slide: back.resolve((r.records[0]||{}).id || r.records[0].id), format: "png", scale: 1 }).catch(()=>null);
console.log("probe written");
