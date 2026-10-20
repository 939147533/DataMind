import { PresentationFile, FileBlob } from "@oai/artifact-tool";
const p = await PresentationFile.importPptx(await FileBlob.load("/Users/ly/Code/DataMind/.ppt-build/draft-v11.pptx"));
const t = await p.inspect({ select: "$.slides[*]", include: ["index","elements.id","elements.kind","elements.text"] });
const rows = t.records.slice().sort((a,b)=>a.index-b.index);
const needles = ["8 类数据源","7 类数据源","不通数据库","不同数据库","覆盖 SQLite","117 项","167 项","不通环境","重试3次","少量示例"];
for (const n of needles) {
  const hits=[];
  for (const r of rows) for (const e of (r.elements||[])) if ((e.text||"").includes(n)) hits.push(`p${r.index+1}:${e.id}`);
  console.log(n, "->", hits.join(" ") || "-");
}
// table structure
const ti = await p.inspect({ kind: "table", include: ["id","text","position","style"] });
for (const e of (ti.records||[])) {
  if (e.id === "tb/tkvi1snm" || !e.id) continue;
}
const r17 = rows.find(r=>r.index===16);
const tbEl = (r17.elements||[]).find(e=>e.kind==="table");
console.log("table id:", tbEl.id);
const tb = p.resolve(tbEl.id);
console.log("rows:", tb.rows, "columns:", tb.columns);
console.log("FULLTEXT:", JSON.stringify(tbEl.text));
