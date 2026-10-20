import fs from "node:fs/promises";
import { PresentationFile, FileBlob } from "@oai/artifact-tool";

const SRC = "/Users/ly/Code/DataMind/docs/DataMind数据库Agent项目介绍V1.0.pptx";
const DRAFT = "/Users/ly/Code/DataMind/.ppt-build/draft-v11.pptx";
const OUT = "/Users/ly/Code/DataMind/.ppt-build/after3";
await fs.mkdir(OUT, { recursive: true });

const p = await PresentationFile.importPptx(await FileBlob.load(SRC));
const info0 = await p.inspect({ select: "$.slides[*]", include: ["id","index","elements.text"] });
const s0 = info0.records.slice().sort((a,b)=>a.index-b.index);
const idAt = s0.map(r => r.id);
const textsOf = (r) => (r.elements||[]).map(e=>e.text||"").join("\n");

const messyIdx = s0.findIndex(r => textsOf(r).includes("在银行、运维、业务分析等场景中"));
const srcIdx = s0.findIndex(r => textsOf(r).includes("技术亮点 ③"));
if (messyIdx < 0 || srcIdx < 0) throw new Error(`locate failed messy=${messyIdx} src=${srcIdx}`);
console.log("messy slide index:", messyIdx, "| 3-card source index:", srcIdx);

const dup = p.resolve(idAt[srcIdx]).duplicate();
p.delete(idAt[messyIdx]);
const order = idAt.filter((_, i) => i !== messyIdx);
order.splice(messyIdx, 0, "sl/" + dup.id);
p.slides.reorder(order);

const info = await p.inspect({ select: "$.slides[*]", include: ["id","index","elements.id","elements.kind","elements.text","elements.position"] });
const slides = info.records.slice().sort((a,b)=>a.index-b.index);
const byId = {}; for (const r of slides) for (const e of (r.elements||[])) byId[e.id]=e;
const set = (id, v) => { if (!byId[id]) throw new Error("missing "+id); p.resolve(id).text = v; };
const slideAt = (i) => slides.find(r => r.index === i);
const elOf = (i, pred) => (slideAt(i).elements||[]).find(pred);

// ---- 1) page numbers: numeric footer textbox, renumber by position ----
let renumbered = 0;
for (const r of slides) {
  for (const e of (r.elements||[])) {
    const q = e.position || {};
    const numeric = /^\d{1,2}$/.test((e.text||"").trim());
    if (numeric && (q.left ?? 0) >= 1000 && (q.top ?? 0) >= 640 && (q.width ?? 0) <= 120) {
      set(e.id, String(r.index + 1));
      renumbered++;
    }
  }
}
console.log("renumbered:", renumbered);

// ---- 2) rebuild the role-pain slide at index 3 ----
const T = "三类角色的取数痛点";
set(elOf(3, e => e.text === "技术亮点 ③：安全、审计与可观测").id, T);
set(elOf(3, e => (e.text||"").startsWith("密钥加密、分级授权")).id,
  "同一个数据库，三类使用者卡在完全不同的环节：业务要等、开发要配、运维要管。");
set(elOf(3, e => e.text === "加密与认证").id, "业务人员 · 拿不到");
set(elOf(3, e => e.text === "权限与审计").id, "开发人员 · 拿得慢");
set(elOf(3, e => e.text === "可观测与部署").id, "运维 / DBA · 管不住");
set(elOf(3, e => (e.text||"").startsWith("数据库密码、SSH 私钥")).id,
  "· 取数靠排队，等排期\n· 不懂 SQL，没有自助入口\n· 口径不一致，数据对不上\n· 只能拿到数字，拿不到图\n· 结果不可复用，反复重问");
set(elOf(3, e => (e.text||"").startsWith("按角色控制权限")).id,
  "· 多数据库客户端来回切换\n· 查线上数据先搭隧道环境\n· 简单 SQL 也要重复手写\n· 误操作没有二次确认\n· 查完只能截图贴群，难复现");
set(elOf(3, e => (e.text||"").startsWith("/metrics 暴露请求数")).id,
  "· 多环境连接靠文档维护\n· 变更前靠人眼比对结构\n· 慢查询只能逐台登录排查\n· 权限靠人肉维护，粒度粗\n· 审计留痕与导出都很困难");

p.resolve(slideAt(3).id).speakerNotes.text =
  "痛点来源：docs/需求说明书V2.0.md 1.2 目标用户、1.3 核心价值；对应解法见 README「功能特性」与本稿功能演示页。三类成本：业务等、开发慢、运维难管。";

await (await PresentationFile.exportPptx(p)).save(DRAFT);
console.log("slides", slides.length);
for (const r of slides) {
  const png = await p.export({ slide: p.resolve(r.id), format: "png", scale: 1 });
  await fs.writeFile(`${OUT}/slide-${String(r.index+1).padStart(2,"0")}.png`, Buffer.from(await png.arrayBuffer()));
}
const m = await p.export({ format: "webp", montage: true });
await fs.writeFile(`${OUT}/montage.webp`, Buffer.from(await m.arrayBuffer()));
console.log("DRAFT", DRAFT);
