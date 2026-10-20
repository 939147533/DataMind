import { PresentationFile, FileBlob } from "@oai/artifact-tool";
const p = await PresentationFile.importPptx(await FileBlob.load("/Users/ly/Code/DataMind/.ppt-build/draft-v11.pptx"));
const r = await p.inspect({ select: `$.slides[?(@.index==1)].elements[*]`, include: ["id","kind","text","position","style"] });
for (const e of (r.records||[])) { const q=e.position||{}; console.log(e.kind, e.id, `@(${Math.round(q.left)},${Math.round(q.top)})`, JSON.stringify(e.text||"")); }
