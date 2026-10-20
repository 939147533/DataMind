import { PresentationFile, FileBlob } from "@oai/artifact-tool";
const p = await PresentationFile.importPptx(await FileBlob.load("/Users/ly/Code/DataMind/.ppt-build/draft.pptx"));
const info = await p.inspect({ select: "$.slides[*]", include: ["index","elements.id","elements.text","notes.text"] });
const rows = info.records.slice().sort((a,b)=>a.index-b.index);
for (const r of rows) {
  const nums = (r.elements||[]).filter(e => /^\d{1,2}$/.test((e.text||"").trim())).map(e=>e.text.trim());
  const title = ((r.elements||[])[0]||{}).text || "";
  console.log(String(r.index+1).padStart(2,"0"), "numeric:", JSON.stringify(nums), "|", (title.replace(/\n/g," ").slice(0,42)));
}
const all = rows.flatMap(r => (r.elements||[]).map(e=>e.text||"")).join("\n");
for (const bad of ["117 项","不通","8 类数据源","GoldenDB"]) {
  console.log("contains", JSON.stringify(bad), ":", all.includes(bad));
}
console.log("notes count:", rows.filter(r=>r.notes && r.notes.text).length);
