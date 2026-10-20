import { PresentationFile, FileBlob } from "@oai/artifact-tool";
const p = await PresentationFile.importPptx(await FileBlob.load("/Users/ly/Code/DataMind/docs/DataMind数据库Agent项目介绍V1.0.pptx"));
const info = await p.inspect({ select: "$.slides[*]", include: ["index","elements.text"] });
const rows = info.records.slice().sort((a,b)=>a.index-b.index);
const all = rows.map(r => (r.elements||[]).map(e=>e.text||"").join("|")).join("\n");
for (const m of ["117 项","167 项","不通数据库","不同数据库","8 类数据源","7 类数据源","覆盖 SQLite"]) {
  console.log(m, "->", all.includes(m));
}
console.log("--- page-number-ish per slide ---");
for (const r of rows) {
  const nums = (r.elements||[]).filter(e=>/^\d{1,2}$/.test((e.text||"").trim())).map(e=>e.text.trim());
  console.log(String(r.index+1).padStart(2,"0"), JSON.stringify(nums));
}
