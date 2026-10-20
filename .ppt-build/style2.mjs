import { PresentationFile, FileBlob } from "@oai/artifact-tool";
const p = await PresentationFile.importPptx(await FileBlob.load("/Users/ly/Code/DataMind/.ppt-build/draft-v11.pptx"));
try {
  const t = await p.inspect({ select: "$.slides[?(@.index==4)].elements[*]", include: ["id","kind","text","position","style","fill","line","font"] });
  console.log(JSON.stringify(t, null, 1).slice(0, 3000));
} catch (e) { console.log("ERR:", String(e.message).slice(0,300)); }
