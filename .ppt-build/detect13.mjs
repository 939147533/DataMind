import { PresentationFile, FileBlob } from "@oai/artifact-tool";
const p = await PresentationFile.importPptx(await FileBlob.load("/Users/ly/Code/DataMind/.ppt-build/draft-v13.pptx"));
const t = await p.inspect({ select: "$.slides[*]", include: ["index","elements.id","elements.kind","elements.text"] });
const rows = t.records.slice().sort((a,b)=>a.index-b.index);
const tb=[], ch=[];
for (const r of rows) for (const e of (r.elements||[])) {
  if (e.kind==="table") tb.push([r.index+1, e.id, (e.text||"").split("\n")[0].slice(0,30)]);
  if (e.kind==="chart") ch.push([r.index+1, e.id]);
}
console.log("TABLES:", JSON.stringify(tb));
console.log("CHARTS:", JSON.stringify(ch));
