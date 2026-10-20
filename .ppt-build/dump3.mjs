import { PresentationFile, FileBlob } from "@oai/artifact-tool";
const p = await PresentationFile.importPptx(await FileBlob.load("/Users/ly/Code/DataMind/docs/DataMind数据库Agent项目介绍V1.0.pptx"));
const info = await p.inspect({ select: "$.slides[*]", include: ["id","index","elements.id","elements.kind","elements.text","elements.position"] });
const rows = info.records.slice().sort((a,b)=>a.index-b.index);
for (const r of rows) {
  if (![3,4,5,20,21].includes(r.index)) continue;
  console.log("======== slide index", r.index, "(page", r.index+1, ") id", r.id);
  for (const e of (r.elements||[])) {
    const q = e.position||{};
    console.log(`  [${e.kind}] ${e.id} @(${q.left},${q.top} ${q.width}x${q.height}) :: ${JSON.stringify((e.text||"").slice(0,200))}`);
  }
}
