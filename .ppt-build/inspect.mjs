import fs from "node:fs/promises";
import { Presentation, PresentationFile, FileBlob } from "@oai/artifact-tool";

const SRC = "/Users/ly/Code/DataMind/docs/DataMind数据库Agent项目介绍V1.0.pptx";
const OUT = "/Users/ly/Code/DataMind/.ppt-build/src";
await fs.mkdir(OUT, { recursive: true });

const presentation = await PresentationFile.importPptx(await FileBlob.load(SRC));
const size = presentation.slideSize;
console.log("SLIDE_SIZE", JSON.stringify(size));
console.log("SLIDE_COUNT", presentation.slides.items.length);

const info = await presentation.inspect({
  select: "$.slides[*]",
  include: ["id", "index", "layout.id", "layout.name", "elements.id", "elements.kind", "elements.text", "elements.alt"],
  fileName: `${OUT}/content.ndjson`,
});
console.log("RECORDS", info.recordCount);
await fs.writeFile(`${OUT}/content.ndjson`, info.ndjson);

const montage = await presentation.export({ format: "webp", montage: true });
await fs.writeFile(`${OUT}/montage.webp`, Buffer.from(await montage.arrayBuffer()));

for (const [i, slide] of presentation.slides.items.entries()) {
  const png = await presentation.export({ slide, format: "png", scale: 1 });
  await fs.writeFile(`${OUT}/slide-${String(i + 1).padStart(2, "0")}.png`, Buffer.from(await png.arrayBuffer()));
}
console.log("DONE");
