import { PresentationFile, FileBlob } from "@oai/artifact-tool";
const p = await PresentationFile.importPptx(await FileBlob.load("/Users/ly/Code/DataMind/.ppt-build/draft-v11.pptx"));
const t = await p.inspect({ select: "$.slides[*].elements[*]", include: ["id","kind","text","position","style"] });
const bySlide = {};
// fallback: per-slide
for (let i=16;i<=20;i++){
  const r = await p.inspect({ select: `$.slides[?(@.index==${i})].elements[*]`, include: ["id","kind","text","position","style"] });
  console.log("=== slide page", i+1);
  for (const e of (r.records||[])) {
    const q=e.position||{};
    if ((q.top||0) > 630 || /DataMind ·/.test(e.text||"")) console.log("   ", e.kind, e.id, JSON.stringify(e.position), JSON.stringify(e.text||"").slice(0,40), JSON.stringify(e.style||{}));
  }
}
// read fill/line of slide5 card + divider
const s5 = await p.inspect({ select: `$.slides[?(@.index==4)].elements[*]`, include: ["id","kind","position"] });
const card = (s5.records||[]).find(e=>e.id==="sh/032tgr6d");
const div  = (s5.records||[]).find(e=>e.id==="sh/z2tcnm5s");
for (const [lbl,el] of [["card",card],["div",div]]) {
  if(!el) { console.log(lbl,"not found"); continue; }
  const r = p.resolve(el.id);
  const dump = {};
  for (const k of ["fill","line","borderRadius","geometry","shadow"]) { try { dump[k]=JSON.stringify(r[k]); } catch(e){ dump[k]="ERR"; } }
  console.log(lbl, JSON.stringify(dump));
}
