import { PresentationFile, FileBlob } from "@oai/artifact-tool";
const p = await PresentationFile.importPptx(await FileBlob.load("/Users/ly/Code/DataMind/docs/DataMind数据库Agent项目介绍V1.1.pptx"));
const info = await p.inspect({ select: "$.slides[*]", include: ["index","elements.text"] });
const rows = info.records.slice().sort((a,b)=>a.index-b.index);
console.log("slide count:", rows.length);
for (const r of rows) {
  const ts=(r.elements||[]).map(e=>e.text||"");
  const num=ts.filter(t=>/^\d{1,2}$/.test(t.trim())).map(t=>t.trim()).join(",");
  const title=ts.find(t=>t.trim().length>3)||"";
  console.log(String(r.index+1).padStart(2,"0"), "| num:", String(num).padEnd(12), "|", title.slice(0,52));
}
