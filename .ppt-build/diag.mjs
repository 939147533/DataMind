import { PresentationFile, FileBlob } from "@oai/artifact-tool";
const p = await PresentationFile.importPptx(await FileBlob.load("/Users/ly/Code/DataMind/.ppt-build/draft.pptx"));
const info = await p.inspect({
  select: "$.slides[5,20].elements[*]",
  include: ["id","kind","text","paragraphs","position","style"],
});
for (const r of info.records) {
  if (r.kind !== "textbox") continue;
  if (!/Docker|routers|部署与运维|架构与扩展/.test(r.text||"")) continue;
  console.log("----", r.id, JSON.stringify(r.text));
  console.log("  pos", JSON.stringify(r.position), "style", JSON.stringify(r.style));
  console.log("  paras", JSON.stringify(r.paragraphs));
}
