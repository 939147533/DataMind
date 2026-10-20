import { PresentationFile, FileBlob } from "@oai/artifact-tool";
const files = {
  "V1.0": "/Users/ly/Code/DataMind/docs/DataMind数据库Agent项目介绍V1.0.pptx",
  "draft-v11": "/Users/ly/Code/DataMind/.ppt-build/draft-v11.pptx",
};
for (const [name, path] of Object.entries(files)) {
  const p = await PresentationFile.importPptx(await FileBlob.load(path));
  const info = await p.inspect({ select: "$.slides[*]", include: ["id","index","elements.text"] });
  const rows = info.records.slice().sort((a,b)=>a.index-b.index);
  console.log("=====", name, "slides:", rows.length, "=====");
  for (const r of rows) {
    const ts = (r.elements||[]).map(e=>e.text||"").filter(t=>t.trim());
    console.log(String(r.index+1).padStart(2,"0"), "|", ts.slice(0,2).join(" // ").slice(0,110));
  }
}
