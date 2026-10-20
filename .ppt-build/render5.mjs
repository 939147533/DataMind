import fs from "node:fs/promises";
import { PresentationFile, FileBlob } from "@oai/artifact-tool";
const OUT = "/Users/ly/Code/DataMind/.ppt-build/final-v12-render";
await fs.mkdir(OUT, { recursive: true });
const p = await PresentationFile.importPptx(await FileBlob.load("/Users/ly/Code/DataMind/docs/DataMind数据库Agent项目介绍V1.2.pptx"));
const info = await p.inspect({ select: "$.slides[*]", include: ["id","index"] });
const rows = info.records.slice().sort((a,b)=>a.index-b.index);
for (const r of rows) {
  const png = await p.export({ slide: p.resolve(r.id), format: "png", scale: 1 });
  await fs.writeFile(`${OUT}/slide-${String(r.index+1).padStart(2,"0")}.png`, Buffer.from(await png.arrayBuffer()));
}
const m = await p.export({ format: "webp", montage: true });
await fs.writeFile(`${OUT}/montage.webp`, Buffer.from(await m.arrayBuffer()));
console.log("rendered", rows.length, "->", OUT);
