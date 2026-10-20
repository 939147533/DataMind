import { PresentationFile, FileBlob } from "@oai/artifact-tool";
async function probe(file) {
  const p = await PresentationFile.importPptx(await FileBlob.load(file));
  const info = await p.inspect({ select: "$.slides[*]", include: ["index","elements.text"] });
  const rows = info.records.slice().sort((a,b)=>a.index-b.index);
  const all = rows.map(r => (r.elements||[]).map(e=>e.text||"").join("|")).join("\n");
  const marks = ["工程质量：架构、测试与交付","附录 · 问答准备","落地与推广：低成本、可复制","三类角色的取数痛点","技术亮点 ③"];
  console.log(file.split("/").pop(), "| slides:", rows.length, "|", marks.map(m=>`${m}:${all.includes(m)}`).join(" "));
}
await probe("/Users/ly/Code/DataMind/docs/DataMind数据库Agent项目介绍V1.0.pptx");
await probe("/Users/ly/Code/DataMind/DataMind数据库Agent项目介绍V1.0_副本.pptx");
