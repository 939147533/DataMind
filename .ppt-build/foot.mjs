import { PresentationFile, FileBlob } from "@oai/artifact-tool";
for (const [name,path] of [["V1.0","/Users/ly/Code/DataMind/docs/DataMind数据库Agent项目介绍V1.0.pptx"],["draft","/Users/ly/Code/DataMind/.ppt-build/draft-v11.pptx"]]) {
  const p = await PresentationFile.importPptx(await FileBlob.load(path));
  const info = await p.inspect({ select: "$.slides[*]", include: ["index","elements.text"] });
  const rows = info.records.slice().sort((a,b)=>a.index-b.index);
  console.log("=====", name);
  for (const r of rows) {
    const ts = (r.elements||[]).map(e=>e.text||"");
    const foot = ts.some(t=>t.includes("DataMind · 数据库 Agent"));
    const num = ts.filter(t=>/^\d{1,2}$/.test(t.trim())).join(",");
    console.log(String(r.index+1).padStart(2,"0"), "footer:", foot?"Y":"-", " num:", num);
  }
}
