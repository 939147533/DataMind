import { PresentationFile, FileBlob } from "@oai/artifact-tool";
const p = await PresentationFile.importPptx(await FileBlob.load("/Users/ly/Code/DataMind/.ppt-build/draft-v11.pptx"));
for (const i of [19,20]) {
  const r = await p.inspect({ select: `$.slides[?(@.index==${i})].elements[*]`, include: ["id","kind","text","position","style"] });
  console.log("=== slide page", i+1);
  for (const e of (r.records||[])) {
    const q=e.position||{};
    console.log("   ", e.kind, String(e.id).padEnd(14), `@(${Math.round(q.left)},${Math.round(q.top)} ${Math.round(q.width)}x${Math.round(q.height)})`, (e.style?JSON.stringify(e.style):"").slice(0,60), JSON.stringify((e.text||"").slice(0,70)));
  }
}
