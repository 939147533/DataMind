import { PresentationFile, FileBlob } from "@oai/artifact-tool";
async function scan(file, label) {
  const p = await PresentationFile.importPptx(await FileBlob.load(file));
  const info = await p.inspect({ select: "$.slides[*]", include: ["index","elements.id","elements.kind","elements.position","elements.text"] });
  for (const r of info.records) {
    for (const e of (r.elements||[])) {
      const q = e.position; if (!q) continue;
      const bad = (q.left ?? 0) < -1 || (q.top ?? 0) < -1 || (q.left ?? 0) + (q.width ?? 0) > 1281 || (q.top ?? 0) + (q.height ?? 0) > 721;
      if (bad) console.log(label, "idx", r.index+1, e.kind, e.id, JSON.stringify(q), JSON.stringify((e.text||"").slice(0,20)));
    }
  }
}
await scan("/Users/ly/Code/DataMind/docs/DataMind数据库Agent项目介绍V1.0.pptx", "SRC ");
await scan("/Users/ly/Code/DataMind/docs/DataMind数据库Agent项目介绍V1.1.pptx", "FINAL");
console.log("scan done");
