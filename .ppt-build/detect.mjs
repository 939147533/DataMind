import { PresentationFile, FileBlob } from "@oai/artifact-tool";
const p = await PresentationFile.importPptx(await FileBlob.load("/Users/ly/Code/DataMind/.ppt-build/draft-v11.pptx"));
const t = await p.inspect({ select: "$.slides[*]", include: ["id","index","elements.id","elements.kind","elements.text"] });
const rows = t.records.slice().sort((a,b)=>a.index-b.index);
const tables=[], charts=[], imgs=[];
for (const r of rows) for (const e of (r.elements||[])) {
  if (e.kind==="table") tables.push([r.index+1, e.id, (e.text||"").slice(0,40)]);
  if (e.kind==="chart") charts.push([r.index+1, e.id, (e.text||"").slice(0,40)]);
  if (e.kind==="image") imgs.push([r.index+1, e.id]);
}
console.log("TABLES:", JSON.stringify(tables));
console.log("CHARTS:", JSON.stringify(charts));
console.log("IMAGES count:", imgs.length, "slides:", JSON.stringify([...new Set(imgs.map(i=>i[0]))]));
