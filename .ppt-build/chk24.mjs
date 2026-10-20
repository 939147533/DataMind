import { PresentationFile, FileBlob } from "@oai/artifact-tool";
const p = await PresentationFile.importPptx(await FileBlob.load("/Users/ly/Code/DataMind/.ppt-build/draft-v13.pptx"));
const r = await p.inspect({ select: "$.slides[?(@.index==23)].elements[*]", include: ["id","kind","text","position"] });
for (const e of (r.records||[])) console.log(e.id, JSON.stringify(e.text), JSON.stringify(e.position));
