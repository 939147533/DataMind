import fs from "node:fs/promises";
import { PresentationFile, FileBlob } from "@oai/artifact-tool";

const SRC = "/Users/ly/Code/DataMind/.ppt-build/draft-v11.pptx";
const DRAFT = "/Users/ly/Code/DataMind/.ppt-build/draft-v12.pptx";
const OUT = "/Users/ly/Code/DataMind/.ppt-build/after5";
await fs.mkdir(OUT, { recursive: true });

const p = await PresentationFile.importPptx(await FileBlob.load(SRC));

const refresh = async () => {
  const info = await p.inspect({
    select: "$.slides[*]",
    include: ["id", "index", "elements.id", "elements.kind", "elements.text", "elements.position"],
  });
  const byId = {};
  const order = info.records.slice().sort((a, b) => a.index - b.index);
  for (const r of order) byId[r.id] = r;
  return { byId, order };
};
const textsOf = (r) => (r.elements || []).map((e) => e.text || "").join("\n");
const locate = (order, needle) => {
  const r = order.find((row) => textsOf(row).includes(needle));
  if (!r) throw new Error("locate failed: " + needle);
  return r.id;
};
const pick = (rec, pred) => {
  const e = (rec.elements || []).find(pred);
  if (!e) throw new Error("element not found: " + pred);
  return e;
};
const byText = (t) => (e) => e.text === t;
const byPrefix = (t) => (e) => (e.text || "").startsWith(t);

let S = await refresh();
const BASE = S.order.map((r) => r.id);            // original 22 slides, captured before any duplication
const card3Src = locate(S.order, "Agent 执行链路");
const tableSrc = locate(S.order, "核心亮点 · AI Agent");
const divSrc = locate(S.order, "AI Agent 工具调用、安全执行、跨库适配");
const oldPain = locate(S.order, "三类角色的取数痛点");
const secPageOld = locate(S.order, "技术亮点 ③：安全、审计与可观测");
const closing = locate(S.order, "让每个人都能安全、高效地与数据对话");
console.log("templates ->", { card3Src, tableSrc, divSrc, oldPain, secPageOld, closing });

const mk = (src) => "sl/" + p.resolve(src).duplicate().id;
const newPain = mk(card3Src);
const newDiv4 = mk(divSrc);
const newQuality = mk(card3Src);
const newLanding = mk(card3Src);
const newAppendix = mk(tableSrc);

const setOn = async (sid, pred, value) => {
  const s = await refresh();
  p.resolve(pick(s.byId[sid], pred).id).text = value;
};

const buildThreeCard = async (sid, { eyebrow, title, cards }) => {
  let s = await refresh();
  let rec = s.byId[sid];
  const dels = [];
  for (const e of rec.elements || []) {
    const q = e.position || {};
    const top = q.top ?? 0;
    if (top >= 160 && top <= 250) dels.push(e.id);
    else if (e.kind === "textbox" && top >= 600 && (q.height ?? 0) >= 50) dels.push(e.id);
  }
  console.log("  drop on new slide:", dels.length, "elements");
  p.delete(dels);

  s = await refresh();
  rec = s.byId[sid];
  const DELTA = 108;
  for (const e of rec.elements || []) {
    const q = e.position || {};
    const top = q.top ?? 0;
    if (top >= 270 && top <= 620) {
      p.resolve(e.id).position = { left: q.left, top: top - DELTA, width: q.width, height: q.height };
    }
  }

  await setOn(sid, byText("Agent 执行链路"), eyebrow);
  await setOn(sid, byText("工具调用 + 失败重试 + few-shot，让结果更可靠"), title);
  const heads = ["工具调用", "失败重试", "经验复用"];
  const bodyPrefix = ["list_tables", "READ ", "历史成功 SQL"];
  for (let i = 0; i < 3; i++) {
    await setOn(sid, byText(heads[i]), cards[i][0]);
    await setOn(sid, byPrefix(bodyPrefix[i]), cards[i][1]);
  }
};

// 1) page 4 rebuilt in the footer family
await buildThreeCard(newPain, {
  eyebrow: "项目背景 · 取数痛点",
  title: "三类角色的取数痛点",
  cards: [
    ["业务人员 · 拿不到",
      "· 取数靠排队，等排期\n· 不懂 SQL，没有自助入口\n· 口径不一致，数据对不上\n· 只能拿到数字，拿不到图\n· 结果不可复用，反复重问"],
    ["开发人员 · 拿得慢",
      "· 多数据库客户端来回切换\n· 查线上数据先搭隧道环境\n· 简单 SQL 也要重复手写\n· 误操作没有二次确认\n· 查完只能截图贴群，难复现"],
    ["运维 / DBA · 管不住",
      "· 多环境连接靠文档维护\n· 变更前靠人眼比对结构\n· 慢查询只能逐台登录排查\n· 权限靠人肉维护，粒度粗\n· 审计留痕与导出都很困难"],
  ],
});

// 2) 04 divider
await setOn(newDiv4, byText("03"), "04");
await setOn(newDiv4, byText("技术亮点"), "工程与治理");
await setOn(newDiv4, byText("AI Agent 工具调用、安全执行、跨库适配"), "架构与质量、安全合规、落地与推广");

// 3) 工程质量与架构
await buildThreeCard(newQuality, {
  eyebrow: "工程质量与架构",
  title: "分层解耦 + 测试覆盖，交付可维护的系统",
  cards: [
    ["架构与扩展性",
      "routers → services → adapters 三层解耦，新增数据库只需实现适配器并注册；\nLLM 统一抽象 OpenAI / Claude / Ollama。"],
    ["代码质量保障",
      "167 项后端测试覆盖 SQL 分级、连接池、权限、审计、分页等关键路径；\nruff 静态检查 + 前端 vue-tsc 类型校验。"],
    ["工程复杂度",
      "统一 {code, message, data} 响应与全局异常处理；\n结构变更走 Alembic 迁移，Docker 多阶段构建交付单镜像。"],
  ],
});

// 4) 落地与推广
await buildThreeCard(newLanding, {
  eyebrow: "落地与推广",
  title: "不改业务系统，单机即可部署、按需复用",
  cards: [
    ["部署成本",
      "不动业务系统，单机 Docker 一键启动、单端口对外；\n不需要消息队列、缓存等额外中间件。"],
    ["运维与兼容",
      "统一适配层屏蔽方言差异，已支持 7 类数据源；\n权限、审计、监控沿用企业现有体系。"],
    ["复用与推广",
      "连接、权限、报表全部配置化：\n换一套数据库、换一个团队即可复用，推广成本低。"],
  ],
});

// 5) appendix
await setOn(newAppendix, byText("核心亮点 · AI Agent"), "附录 · 答辩准备");
await setOn(newAppendix, byText("把自然语言变成可信、可解释、可执行的 SQL"), "评委常问的问题，先给出可验证的答案");
await setOn(newAppendix, byPrefix("Agent 不是简单调用大模型"), "以下问题覆盖安全、扩展性、性能与落地成本，答案都对应产品里已经实现的能力。");
{
  const s = await refresh();
  const t = pick(s.byId[newAppendix], (e) => e.kind === "table");
  const tb = p.resolve(t.id);
  const rows = [
    ["评委追问", "应答要点", "对应能力"],
    ["AI 会误删数据吗？", "写操作一律二次确认，DDL 额外高危提示；确认记录 5 分钟过期、只能消费一次", "分级授权 + 确认机制"],
    ["数据库密码怎么保护？", "密码、SSH 私钥、AI Key 均为 Fernet 加密入库，接口只返回 has_key", "密钥可环境变量注入"],
    ["支持哪些数据库？", "7 类数据源；OceanBase、GoldenDB 复用 MySQL 协议", "适配器层可直接扩展"],
    ["大结果集会不会卡住？", "分页 + 最大行数限制，Agent 结果超限时截断提示，前端虚拟滚动", "端到端限流"],
    ["部署与运维成本高吗？", "单机 Docker 一键启动、单端口，/metrics 可接入现有监控", "无外部中间件依赖"],
  ];
  for (let r = 0; r < rows.length; r++) for (let c = 0; c < rows[r].length; c++) tb.cells.set(r, c, rows[r][c]);
}

// 6) text corrections
const fix = async (from, to) => {
  const s = await refresh();
  for (const r of s.order) for (const e of r.elements || []) {
    if ((e.text || "").includes(from)) {
      p.resolve(e.id).text = e.text.split(from).join(to);
      console.log("  fixed:", from, "->", to);
      return;
    }
  }
  throw new Error("text to fix not found: " + from);
};
await fix("8 类数据源、SSH 隧道、多环境标签", "7 类数据源、SSH 隧道、多环境标签");
await fix("不通环境表结构对比）", "不同环境表结构对比");
await fix("117 项后端测试 + Playwright E2E", "167 项后端测试 + Playwright E2E");

// 7) 安全与合规 page (former 技术亮点 ③)
await setOn(secPageOld, byText("技术亮点 ③：安全、审计与可观测"), "安全与合规");
await setOn(secPageOld, byText("密钥加密、分级授权、全量审计、指标暴露与测试覆盖，构成可交付的企业级完整性。"),
  "数据不落盘、密钥可托管、操作可追溯：让这套 Agent 能通过企业安全评审。");
await setOn(secPageOld, byText("可观测与部署"), "合规与交付");
await setOn(secPageOld, byPrefix("数据库密码、SSH 私钥"),
  "数据库密码、SSH 私钥、AI Key 经 Fernet 加密入库，接口只返回 has_password / has_key；\n登录密码 pbkdf2 哈希，会话使用 httponly Cookie。");
await setOn(secPageOld, byPrefix("按角色控制权限"),
  "按角色控制权限，READ / DML / DDL 分级授权；\n登录、SQL、Agent 动作全量留痕，操作类型、SQL 文本与状态都可追溯。");
await setOn(secPageOld, byPrefix("/metrics 暴露请求数"),
  "密钥支持环境变量或独立密钥文件注入，密钥文件不入库；\n审计日志按保留期（默认 180 天）自动清理；导出文件统一落盘管理。");

// 8) reorder + drop the superseded page 4
if (BASE.length !== 22) throw new Error("unexpected base slide count: " + BASE.length);
const order = [
  BASE[0], BASE[1], BASE[2], newPain, BASE[4], BASE[5], BASE[6], BASE[7],
  BASE[8], BASE[9], BASE[10], BASE[11], BASE[12], BASE[13], BASE[14],
  BASE[15], BASE[16], BASE[17], BASE[18],
  newDiv4, BASE[19], secPageOld,
  newQuality, newLanding,
  BASE[21], newAppendix,
];
p.delete(oldPain);
p.slides.reorder(order);

// 9) renumber
let S2 = await refresh();
let renumbered = 0;
for (const r of S2.order) for (const e of r.elements || []) {
  const q = e.position || {};
  if (/^\d{1,2}$/.test((e.text || "").trim()) && (q.left ?? 0) >= 1000 && (q.top ?? 0) >= 640 && (q.width ?? 0) <= 120) {
    p.resolve(e.id).text = String(r.index + 1);
    renumbered++;
  }
}
console.log("renumbered:", renumbered, "total slides:", S2.order.length);

// 10) speaker notes
const notes = {
  [newPain]: "痛点来源：docs/需求说明书V2.0.md（1.2 目标用户、1.3 核心价值）与功能缺口；对应解法见功能演示页与「工程与治理」章节。",
  [newDiv4]: "章节 04 对应目录里的「工程与治理」：工程质量、安全合规、审计监控、落地推广。",
  [newQuality]: "数据来源：backend/app/services（三层分层）、backend/tests（167 项 pytest 用例）、backend/pyproject.toml（ruff）、backend/migrations、Dockerfile。",
  [newLanding]: "数据来源：Dockerfile/docker-compose（单机单端口）、backend/app/config.py（DEFAULT_DB_TYPES 共 7 类）、backend/app/adapters（统一适配层）。",
  [newAppendix]: "应答要点均可回溯到实现：backend/app/services/sql_service.py（确认机制）、backend/app/security.py（Fernet/pbkdf2）、backend/app/adapters/registry.py、backend/app/services/agent_service.py（结果截断）。",
  [secPageOld]: "原「技术亮点 ③」与「审计与监控」内容重叠，现改为安全合规视角：密钥托管、分级授权、审计保留期与交付方式。",
};
for (const [sid, text] of Object.entries(notes)) p.resolve(sid).speakerNotes.text = text;

await (await PresentationFile.exportPptx(p)).save(DRAFT);
S2 = await refresh();
for (const r of S2.order) {
  const png = await p.export({ slide: p.resolve(r.id), format: "png", scale: 1 });
  await fs.writeFile(`${OUT}/slide-${String(r.index + 1).padStart(2, "0")}.png`, Buffer.from(await png.arrayBuffer()));
}
const m = await p.export({ format: "webp", montage: true });
await fs.writeFile(`${OUT}/montage.webp`, Buffer.from(await m.arrayBuffer()));
console.log("DRAFT", DRAFT, "slides", S2.order.length);
