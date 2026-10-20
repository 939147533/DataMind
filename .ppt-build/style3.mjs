import { PresentationFile, FileBlob } from "@oai/artifact-tool";
const p = await PresentationFile.importPptx(await FileBlob.load("/Users/ly/Code/DataMind/.ppt-build/draft-v11.pptx"));
const t = await p.inspect({ select: "$.slides[?(@.index==4)].elements[*]", include: ["id","kind","text","position","style","fill","line"] });
console.log(Object.keys(t));
for (const e of (t.records||[])) console.log(JSON.stringify(e).slice(0,500));
