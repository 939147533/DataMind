import { PresentationFile, FileBlob } from "@oai/artifact-tool";
const SRC = "/Users/ly/Code/DataMind/docs/DataMind数据库Agent项目介绍V1.0.pptx";
const p = await PresentationFile.importPptx(await FileBlob.load(SRC));
const ids = p.slides.items.map(s => "sl/" + s.id);
console.log(ids.slice(0,4));
try { p.slides.reorder(ids); console.log("reorder with sl/ ok"); } catch(e){ console.log("err", e.message); }
// duplicate then inspect element ids on the dup
const dup = p.slides.items[2].duplicate();
console.log("dup id", dup.id);
const info = await p.inspect({ select: `$.slides[?(@.id == 'sl/${dup.id}')]`, include: ["id","elements.id","elements.kind","elements.text"] });
console.log(info.ndjson.slice(0, 1500));
