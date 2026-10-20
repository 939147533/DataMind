import { PresentationFile, FileBlob } from "@oai/artifact-tool";
const p = await PresentationFile.importPptx(await FileBlob.load("/Users/ly/Code/DataMind/docs/DataMind数据库Agent项目介绍V1.0.pptx"));
const info = await p.inspect({ select: "$.slides[*]", include: ["index","layout.name","elements.id","elements.kind","elements.text"] });
const rows = info.records.slice().sort((a,b)=>a.index-b.index);
for (const r of rows) {
  console.log("=== idx", r.index, "| layout:", (r.layout||{}).name);
  for (const e of (r.elements||[])) {
    const t = (e.text||"").replace(/\n/g," ⏎ ");
    console.log("   ", e.kind, e.id, t.length>70 ? t.slice(0,70)+"…" : t);
  }
}
