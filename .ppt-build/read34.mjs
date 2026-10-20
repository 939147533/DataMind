import { PresentationFile, FileBlob } from "@oai/artifact-tool";
const p = await PresentationFile.importPptx(await FileBlob.load("/Users/ly/Code/DataMind/docs/DataMind数据库Agent项目介绍V1.0.pptx"));
const info = await p.inspect({ select: "$.slides[3,4]", include: ["index","elements.id","elements.kind","elements.text","elements.position"] });
for (const r of info.records) {
  console.log("========== idx", r.index);
  for (const e of (r.elements||[])) {
    console.log("  --", e.kind, e.id, JSON.stringify(e.position));
    console.log("     ", JSON.stringify(e.text));
  }
}
