import fs from "node:fs/promises";
import { PresentationFile, FileBlob } from "@oai/artifact-tool";

const SRC = "/Users/ly/Code/DataMind/.ppt-build/draft-v12.pptx";
const DRAFT = "/Users/ly/Code/DataMind/.ppt-build/draft-v13.pptx";
const OUT = "/Users/ly/Code/DataMind/.ppt-build/after6";
await fs.mkdir(OUT, { recursive: true });

const FONT = "微软雅黑";
const ACCENT = "#0B5FFF";
const INK = "#0F172A";
const BODY = "#334155";
const MUTED = "#64748B";
const BAND_FILL = "#F2F5FB";
const BAND_LINE = "#DDE4EF";
const RAIL_FILL = "#EAF0FF";

const p = await PresentationFile.importPptx(await FileBlob.load(SRC));
const refresh = async () => {
  const info = await p.inspect({
    select: "$.slides[*]",
    include: ["id", "index", "elements.id", "elements.kind", "elements.text", "elements.position"],
  });
  const order = info.records.slice().sort((a, b) => a.index - b.index);
  const byId = {};
  for (const r of order) byId[r.id] = r;
  return { order, byId };
};
const textsOf = (r) => (r.elements || []).map((e) => e.text || "").join("\n");
const locate = (order, needle) => {
  const r = order.find((row) => textsOf(row).includes(needle));
  if (!r) throw new Error("locate failed: " + needle);
  return r.id;
};

let S = await refresh();
const BASE = S.order.map((r) => r.id);
if (BASE.length !== 26) throw new Error("unexpected base count " + BASE.length);
const card3Src = locate(S.order, "Agent 执行链路");
const divIdx = BASE.findIndex((id) => textsOf(S.byId[id]).includes("架构与质量、安全合规、落地与推广"));
const qualityPage = locate(S.order, "分层解耦 + 测试覆盖，交付可维护的系统");
console.log("divider page index:", divIdx, "| quality page:", qualityPage);

const arch = "sl/" + p.resolve(card3Src).duplicate().id;

// ---- chrome only: drop the flow band, the 3 cards and the bottom summary ----
S = await refresh();
let rec = S.byId[arch];
const dels = [];
for (const e of rec.elements || []) {
  const top = (e.position || {}).top ?? 0;
  if (top > 150 && top < 670) dels.push(e.id);
}
console.log("dropped from the new page:", dels.length);
p.delete(dels);

// ---- header text ----
const setOn = async (sid, pred, value) => {
  const s = await refresh();
  const e = (s.byId[sid].elements || []).find(pred);
  if (!e) throw new Error("element not found");
  p.resolve(e.id).text = value;
};
await setOn(arch, (e) => e.text === "Agent 执行链路", "系统技术分层结构");
await setOn(arch, (e) => e.text === "工具调用 + 失败重试 + few-shot，让结果更可靠",
  "五层调用链：从界面直达数据库，治理能力横向贯穿");

// ---- draw the diagram ----
const slide = p.resolve(arch);
const addBand = (y, name, body) => {
  slide.shapes.add({
    geometry: "roundRect",
    position: { left: 72, top: y, width: 812, height: 78 },
    fill: BAND_FILL,
    line: { style: "solid", fill: BAND_LINE, width: 1 },
    borderRadius: 8,
  });
  const n = slide.shapes.add({ geometry: "textbox", position: { left: 86, top: y + 7, width: 786, height: 20 } });
  n.text = name;
  n.text.fontSize = 13;
  n.text.bold = true;
  n.text.typeface = FONT;
  n.text.color = INK;
  n.text.wrap = "none";
  n.text.insets = 0;
  const b = slide.shapes.add({ geometry: "textbox", position: { left: 86, top: y + 30, width: 786, height: 42 } });
  b.text = body;
  b.text.fontSize = 11.5;
  b.text.typeface = FONT;
  b.text.color = BODY;
  b.text.insets = 0;
};
const addGap = (y, label) => {
  const t = slide.shapes.add({ geometry: "textbox", position: { left: 90, top: y, width: 600, height: 18 } });
  t.text = label;
  t.text.fontSize = 10.5;
  t.text.typeface = FONT;
  t.text.color = MUTED;
  t.text.wrap = "none";
  t.text.insets = 0;
};
const addRailText = (x, y, w, h, value, size, color, bold) => {
  const t = slide.shapes.add({ geometry: "textbox", position: { left: x, top: y, width: w, height: h } });
  t.text = value;
  t.text.fontSize = size;
  t.text.typeface = FONT;
  t.text.color = color;
  if (bold) t.text.bold = true;
  t.text.insets = 0;
  return t;
};

const BANDS = [
  [160, "① 前端层｜Vue 3 · TypeScript · Vite · Pinia",
    "模块：智能查询（NL→SQL）· SQL 工作台 · 可视化报表与大屏 · 连接管理 · 用户与角色 · 运维监控 · 审计日志\n组件：SqlEditor（CodeMirror 6）· ResultTable · ObjectTree · ChartCard（ECharts）· AgentPanel"],
  [258, "② 接口层｜FastAPI · 单端口 8000 · 14 个路由模块",
    "统一响应 {code, message, data} · httponly Cookie 会话 · 依赖注入 · RBAC 权限校验 · 静态托管前端产物\n路由：auth · sql · agent（SSE）· metadata · export · charts · monitor · audit · users · roles 等 14 个"],
  [356, "③ 服务层｜业务编排 · services/ 下 10 个服务模块",
    "sql_service（风险分级 / 写操作二次确认 / 审计落库）· agent_service（工具调用 / 失败重试 / few-shot）\nconnection · metadata · export · audit · schedule · llm_providers · ssh_tunnel · sql_examples"],
  [454, "④ 适配层｜BaseDBAdapter + registry · adapters/",
    "MySQL · OceanBase · GoldenDB · PostgreSQL · Oracle · SQLite · MongoDB（前二者复用 MySQL 协议）\n只读连接池：按连接参数分桶复用 · 借出前存活探测 · 归还前回滚 · 参数变更即作废"],
  [552, "⑤ 存储层｜两类数据落点",
    "应用库 SQLite（app.db）：账号、连接、审计、会话等自身状态，SQLAlchemy async + Alembic 迁移\n目标数据库：用户数据源，元数据只读查询走连接池，SQL 执行经统一分类与审计"],
];
for (const [y, name, body] of BANDS) addBand(y, name, body);

addGap(237, "↓  HTTP / SSE 流式");
addGap(335, "↓  异步业务调用（全链路 await）");
addGap(433, "↓  按 db_type 分发适配器");
addGap(531, "↓  同步驱动置于线程池");

// ---- right rail: cross-cutting capabilities ----
slide.shapes.add({
  geometry: "roundRect",
  position: { left: 904, top: 160, width: 304, height: 470 },
  fill: RAIL_FILL,
  line: { style: "solid", fill: ACCENT, width: 1 },
  borderRadius: 8,
});
addRailText(918, 172, 276, 20, "横向能力（贯穿 ②–⑤）", 12.5, ACCENT, true);
const RAIL = [
  [204, "安全", "Fernet 加密（库密码 / SSH 私钥 / AI Key）· pbkdf2 口令哈希 · httponly Cookie"],
  [310, "审计", "登录、SQL 执行、Agent 动作全量留痕 · 按保留期自动清理 · 可导出 CSV / XLSX"],
  [416, "可观测", "/metrics 暴露请求数、延迟与 SQL 执行次数 · 慢查询统计与连接概览"],
  [522, "交付", "Docker 多阶段构建 · 单镜像单端口 · 环境变量配置，密钥可独立挂载"],
];
for (const [y, label, desc] of RAIL) {
  addRailText(918, y, 276, 18, label, 11.5, INK, true);
  addRailText(918, y + 18, 276, 56, desc, 11, BODY, false);
}

addRailText(72, 636, 1136, 18, "外部依赖：大模型服务（OpenAI 兼容 / Claude / Ollama，经 llm_providers 抽象）· SSH 隧道（ssh_tunnel）", 10.5, MUTED, false);

// ---- order ----
const order = [...BASE.slice(0, divIdx + 1), arch, ...BASE.slice(divIdx + 1)];
if (order.length !== 27) throw new Error("order size " + order.length);
p.slides.reorder(order);

// ---- renumber ----
S = await refresh();
let n = 0;
for (const r of S.order) for (const e of r.elements || []) {
  const q = e.position || {};
  if (/^\d{1,2}$/.test((e.text || "").trim()) && (q.left ?? 0) >= 1000 && (q.top ?? 0) >= 640 && (q.width ?? 0) <= 120) {
    p.resolve(e.id).text = String(r.index + 1);
    n++;
  }
}
console.log("renumbered:", n, "slides:", S.order.length);

// de-duplicate the quality page against the new architecture page
await setOn(qualityPage, (e) => e.text === "架构与扩展性", "扩展方式");
await setOn(qualityPage, (e) => (e.text || "").startsWith("routers → services"),
  "新增数据库：实现适配器并注册；新增模型供应商：实现统一接口，业务层无需改动。");

p.resolve(arch).speakerNotes.text =
  "分层依据：backend/app/routers（14 个路由模块）、services（业务编排）、adapters（BaseDBAdapter + registry + pool）、database/models（SQLite app.db）；安全/审计/可观测/交付为横向能力，见 security.py、audit_service.py、main.py /metrics、Dockerfile。";

await (await PresentationFile.exportPptx(p)).save(DRAFT);
S = await refresh();
for (const r of S.order) {
  const png = await p.export({ slide: p.resolve(r.id), format: "png", scale: 1 });
  await fs.writeFile(`${OUT}/slide-${String(r.index + 1).padStart(2, "0")}.png`, Buffer.from(await png.arrayBuffer()));
}
const m = await p.export({ format: "webp", montage: true });
await fs.writeFile(`${OUT}/montage.webp`, Buffer.from(await m.arrayBuffer()));
console.log("DRAFT", DRAFT, "slides", S.order.length);
