import { PresentationFile, FileBlob } from "@oai/artifact-tool";
const p = await PresentationFile.importPptx(await FileBlob.load("/Users/ly/Code/DataMind/.ppt-build/draft-v11.pptx"));
const info = await p.inspect({ kind: "slide,textbox,shape", include: ["id","kind","text","position","style","fill","line","font","size","color"], maxChars: 12000 });
console.log(JSON.stringify(info.records?.slice(0,3), null, 1).slice(0,600));
// targeted
const t = await p.inspect({ select: "$.slides[?(@.index==4)].elements[*]", include: ["id","kind","text","position","style","fill","line","font"] });
console.log("--- slide idx4 elements (slide 5) ---");
for (const e of (t.records?.[0]?.elements||t.records||[])) console.log(JSON.stringify(e).slice(0,400));
