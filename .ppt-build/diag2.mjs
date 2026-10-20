import { PresentationFile, FileBlob } from "@oai/artifact-tool";
const p = await PresentationFile.importPptx(await FileBlob.load("/Users/ly/Code/DataMind/.ppt-build/draft.pptx"));
const slide = p.slides.getItem(5);
const lay = await slide.export({ format: "layout" });
const txt = await lay.text();
const j = JSON.parse(txt);
const els = j.slide ? j.slide.elements : j.elements;
for (const e of els) {
  if (e.kind !== "textbox" && e.kind !== "shape") continue;
  const t = e.text || "";
  if (!/Docker|内置 5/.test(t)) continue;
  console.log(JSON.stringify(e, null, 1).slice(0, 2500));
  console.log("=======");
}
