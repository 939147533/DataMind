import { PresentationFile, FileBlob } from "@oai/artifact-tool";
const p = await PresentationFile.importPptx(await FileBlob.load("/Users/ly/Code/DataMind/.ppt-build/draft.pptx"));
const info = await p.inspect({ select: "$.slides[*]", include: ["id","elements.id","elements.text"] });
const target = info.records.find(r => (r.elements||[]).some(e => (e.text||"").startsWith("Docker 多阶段")));
const j = JSON.parse(await (await p.resolve(target.id).export({ format: "layout" })).text());
const arr = Array.isArray(j.elements) ? j.elements : Object.values(j.elements);
for (const e of arr) {
  console.log(e.kind, JSON.stringify(e.position), "|", JSON.stringify((e.text||"").slice(0,34)), "| style", JSON.stringify(e.style));
}
