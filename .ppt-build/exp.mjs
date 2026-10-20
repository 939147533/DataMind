import fs from "node:fs/promises";
import { PresentationFile, FileBlob } from "@oai/artifact-tool";
const p = await PresentationFile.importPptx(await FileBlob.load("/Users/ly/Code/DataMind/.ppt-build/draft.pptx"));
const info0 = await p.inspect({ select: "$.slides[*]", include: ["id","elements.id","elements.text"] });
const landingId = info0.records.find(r => (r.elements||[]).some(e => (e.text||"").startsWith("Docker 多阶段"))).id;
const S = p.resolve(landingId);
const GEO = { left: 63.33, top: 379.33, width: 330.67, height: 230 };
const TXT = "Docker 多阶段构建，单端口一键启动；数据卷持久化应用库、演示库、驱动与导出文件，不侵入现有业务库。";
const TXT2 = "以 Docker 多阶段构建交付单镜像，单端口一键启动；数据卷持久化应用库、演示库、驱动与导出文件，不侵入现有业务库。";

const a = S.duplicate(), b = S.duplicate(), c = S.duplicate();
const info = await p.inspect({ select: "$.slides[*]", include: ["id","elements.id","elements.text"] });
const byId = Object.fromEntries(info.records.map(r => [r.id, r]));
function bodyOf(sl) {
  const rec = byId["sl/" + sl.id];
  const el = (rec.elements||[]).find(e => (e.text||"").startsWith("Docker 多阶段"));
  return el && el.id;
}
for (const [sl, txt] of [[b, TXT], [c, TXT2]]) {
  const bid = bodyOf(sl);
  if (!bid) { console.log("NO BODY for", sl.id); continue; }
  p.delete(bid);
  sl.shapes.add({ geometry: "textbox", position: GEO, text: { text: txt, style: { fontSize: 21.33, typeface: "Helvetica Neue", color: "#000000", alignment: "left" } } });
}
for (const [n, sl] of [["A", a], ["B", b], ["C", c]]) {
  const png = await p.export({ slide: sl, format: "png", scale: 2 });
  await fs.writeFile(`/Users/ly/Code/DataMind/.ppt-build/exp-${n}.png`, Buffer.from(await png.arrayBuffer()));
}
console.log("done");
