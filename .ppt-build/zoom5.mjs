import fs from "node:fs/promises";
import { PresentationFile, FileBlob } from "@oai/artifact-tool";
const p = await PresentationFile.importPptx(await FileBlob.load("/Users/ly/Code/DataMind/docs/DataMind数据库Agent项目介绍V1.1.pptx"));
const info = await p.inspect({ select: "$.slides[*]", include: ["id","index"] });
const rows = info.records.slice().sort((a,b)=>a.index-b.index);
for (const i of [3]) {
  const png = await p.export({ slide: p.resolve(rows[i].id), format: "png", scale: 2 });
  await fs.writeFile(`/Users/ly/Code/DataMind/.ppt-build/final-s4.png`, Buffer.from(await png.arrayBuffer()));
}
console.log("ok");
