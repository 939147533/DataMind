import { PresentationFile, FileBlob } from "@oai/artifact-tool";
const SRC = "/Users/ly/Code/DataMind/docs/DataMind数据库Agent项目介绍V1.0.pptx";
const p = await PresentationFile.importPptx(await FileBlob.load(SRC));
const items = p.slides.items;
console.log("count", items.length);
const s2 = items[2];
console.log("slide keys", Object.keys(s2).slice(0, 40));
console.log("id prop", s2.id, "index?", s2.index);
const dup = s2.duplicate();
console.log("dup id", dup.id, "count now", p.slides.items.length);
try { dup.moveTo(5); console.log("moveTo ok, now index", p.slides.items.indexOf(dup)); } catch(e){ console.log("moveTo err", e.message); }
try { p.slides.reorder(p.slides.items.map(s=>s.id)); console.log("reorder ok"); } catch(e){ console.log("reorder err", e.message); }
