import fs from "node:fs/promises";
import { PresentationFile, FileBlob } from "@oai/artifact-tool";
const p = await PresentationFile.importPptx(await FileBlob.load("/Users/ly/Code/DataMind/.ppt-build/draft.pptx"));
const info = await p.inspect({ select: "$.slides[*]", include: ["id","elements.text"] });
const target = info.records.find(r => (r.elements||[]).some(e => (e.text||"").startsWith("Docker 多阶段")));
const png = await p.export({ slide: p.resolve(target.id), format: "png", scale: 2 });
await fs.writeFile("/Users/ly/Code/DataMind/.ppt-build/zoom-landing.png", Buffer.from(await png.arrayBuffer()));
console.log("ok", target.id);
