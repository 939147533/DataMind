import fs from "node:fs/promises";
import { PresentationFile, FileBlob } from "@oai/artifact-tool";

const SRC = "/Users/ly/Code/DataMind/docs/DataMind数据库Agent项目介绍V1.0.pptx";
const DRAFT = "/Users/ly/Code/DataMind/.ppt-build/draft.pptx";
const OUT = "/Users/ly/Code/DataMind/.ppt-build/after";
await fs.mkdir(OUT, { recursive: true });

const p = await PresentationFile.importPptx(await FileBlob.load(SRC));
const items = () => p.slides.items;
const origIds = items().map((s) => "sl/" + s.id);

// ---- duplicate sources (capture before any mutation) ----
const srcDivider01 = items()[2];
const srcCards3 = items()[19];   // 技术亮点③ : title/subtitle + 3 cards
const srcTable = items()[15];    // AI Agent : eyebrow/title/subtitle + 3-col table

const landing = srcCards3.duplicate();
const quality = srcCards3.duplicate();
const qa = srcTable.duplicate();
const divider04 = srcDivider01.duplicate();

const L = "sl/" + landing.id, Q = "sl/" + quality.id, A = "sl/" + qa.id, D4 = "sl/" + divider04.id;

// ---- final order ----
const order = [
  origIds[0], origIds[1], origIds[2], origIds[3], origIds[4],   // cover / toc / 01 / why / positioning
  L,                                                            // NEW 落地与推广
  origIds[5], origIds[6], origIds[7], origIds[8], origIds[9], origIds[10], origIds[11], origIds[12], origIds[13],
  origIds[14], origIds[15], origIds[16], origIds[17],           // 03 divider + agent/chain/security
  D4, Q,                                                        // NEW 04 divider + 工程质量
  origIds[18], origIds[19], origIds[20],                        // audit-monitor / tech-highlight3 / closing
  A,                                                            // NEW 问答附录
];
p.slides.reorder(order);

// ---- inspect every slide after reorder ----
const info = await p.inspect({ select: "$.slides[*]", include: ["id", "index", "elements.id", "elements.kind", "elements.text"] });
const slides = info.records;
const byId = {};
for (const r of slides) for (const e of (r.elements || [])) byId[e.id] = e;

const set = (id, v) => { if (!byId[id]) throw new Error("missing element " + id); p.resolve(id).text = v; };
const rep = (id, oldS, newS) => {
  const e = byId[id];
  if (!e) throw new Error("missing element " + id);
  if (!e.text.includes(oldS)) throw new Error(`pattern not found in ${id}: ${oldS}`);
  p.resolve(id).text = e.text.replace(oldS, newS);
};
const slideById = (id) => slides.find((r) => r.id === id);
const elOf = (slideId, pred) => (slideById(slideId).elements || []).find(pred);

// ---- 1) renumber pages (original slides keep their ids) ----
const PAGE = {
  "sh/x4r21kru": "2", "sh/doj29oba": "4", "sh/dgbulwnm": "5",
  "sh/cb2tkvap": "8", "sh/18byd4zy": "9", "sh/1cfmhgne": "10",
  "sh/xc3mho32": "11", "sh/xcryxg7y": "12", "sh/1gbm9s3a": "13",
  "sh/q50nydsj": "14", "sh/xc7eds76": "15", "sh/kv2h4rqp": "17",
  "sh/t8ne10n6": "18", "sh/4felwzu5": "19", "sh/xkbq10be": "22",
  "sh/qpwjmh8n": "23", "sh/sb2lk36t": "24",
};
for (const [id, v] of Object.entries(PAGE)) set(id, v);
set(elOf(L, (e) => e.text === "16").id, "6");
set(elOf(Q, (e) => e.text === "16").id, "21");
set(elOf(A, (e) => e.text === "6").id, "25");

// ---- 2) fixes on existing slides ----
rep("sh/s72xofmh", "RBAC、审计、监控", "架构分层、工程质量、审计监控");
rep("sh/ih8ju9sn", "不通数据库", "不同数据库");
rep("sh/kzmdova1", "8 类数据源", "7 类数据源");
rep("sh/hcfy9k3u", "覆盖 SQLite / Oracle / MySQL / OceanBase",
  "覆盖 7 类数据源（MySQL、Oracle）");
rep("sh/e98nydwb", "重试（默认最多重试3次，可设置）", "重试，默认最多尝试 3 次（可配置）");
rep("sh/1cj69sv2", "（少量示例） 注入", "（少量示例）注入");
rep("sh/qpgjex8f", "不通环境表结构对比）", "不同环境表结构对比");
rep("sh/rid4nuhs", "117 项后端测试", "167 项后端测试");

// ---- 3) NEW: 04 divider ----
set(elOf(D4, (e) => e.text === "01").id, "04");
set(elOf(D4, (e) => e.text === "为什么做").id, "工程与治理");
set(elOf(D4, (e) => e.text === "痛点、定位、目标用户").id, "架构分层、工程质量、审计与监控");

// ---- 4) NEW: 落地与推广 ----
set(elOf(L, (e) => e.text === "技术亮点 ③：安全、审计与可观测").id, "落地与推广：低成本、可复制");
set(elOf(L, (e) => e.text === "密钥加密、分级授权、全量审计、指标暴露与测试覆盖，构成可交付的企业级完整性。").id,
  "不改动业务系统，单机即可部署；连接、权限与报表配置化，换一套数据库即可复用。");
set(elOf(L, (e) => e.text === "加密与认证").id, "部署与运维");
set(elOf(L, (e) => e.text === "权限与审计").id, "兼容与迁移");
set(elOf(L, (e) => e.text === "可观测与部署").id, "复用与推广");
set(elOf(L, (e) => (e.text || "").startsWith("数据库密码、SSH 私钥")).id,
  "Docker多阶段构建、单端口一键启动；数据卷持久化应用库、演示库、驱动与导出文件，不侵入现有业务库。");
set(elOf(L, (e) => (e.text || "").startsWith("按角色控制权限")).id,
  "7类数据源开箱可用；只读连接池与SSH隧道适配内网与云上环境；结构变更走Alembic迁移，老库启动自动补建缺失索引。");
set(elOf(L, (e) => (e.text || "").startsWith("/metrics 暴露请求数")).id,
  "内置5个角色模板覆盖技术与业务岗位；AI模型可在OpenAI / Claude / Ollama间切换，适配不同合规环境。");

// ---- 5) NEW: 工程质量 ----
set(elOf(Q, (e) => e.text === "技术亮点 ③：安全、审计与可观测").id, "工程质量：架构、测试与交付");
set(elOf(Q, (e) => e.text === "密钥加密、分级授权、全量审计、指标暴露与测试覆盖，构成可交付的企业级完整性。").id,
  "分层解耦、自动化测试与静态检查，保证系统长期可维护、可扩展。");
set(elOf(Q, (e) => e.text === "加密与认证").id, "架构与扩展性");
set(elOf(Q, (e) => e.text === "权限与审计").id, "代码质量保障");
set(elOf(Q, (e) => e.text === "可观测与部署").id, "一致性与交付");
set(elOf(Q, (e) => (e.text || "").startsWith("数据库密码、SSH 私钥")).id,
  "routers → services → adapters三层解耦；新增数据库只需实现适配器并注册；LLM统一抽象OpenAI / Claude / Ollama。");
set(elOf(Q, (e) => (e.text || "").startsWith("按角色控制权限")).id,
  "167项后端测试覆盖SQL分级、连接池、权限、审计与分页等关键路径；并通过ruff静态检查与前端vue-tsc类型检查。");
set(elOf(Q, (e) => (e.text || "").startsWith("/metrics 暴露请求数")).id,
  "统一响应{code, message, data}格式与全局异常处理；结构变更走Alembic迁移；Docker多阶段构建交付单镜像。");

// ---- 6) NEW: 问答附录 (table) ----
set(elOf(A, (e) => e.text === "核心亮点 · AI Agent").id, "附录 · 问答准备");
set(elOf(A, (e) => e.text === "把自然语言变成可信、可解释、可执行的 SQL").id, "常见提问与应答要点");
set(elOf(A, (e) => (e.text || "").startsWith("Agent 不是简单调用大模型")).id,
  "把评委最可能追问的问题，先给出可验证的答案。");
const tableEl = elOf(A, (e) => e.kind === "table");
const tb = p.resolve(tableEl.id);
const T = [
  ["评委追问", "应答要点", "对应能力"],
  ["AI 会不会误删数据？", "写操作一律二次确认，DDL 高危提示；确认记录一次性消费、5 分钟过期", "分级授权 + 确认机制"],
  ["数据库密码如何保护？", "密码、SSH 私钥、AI Key 均为 Fernet 加密，接口只返回 has_key", "密钥可环境变量注入"],
  ["支持哪些数据库？", "7 类数据源，OceanBase / GoldenDB 复用 MySQL 协议", "适配器层可扩展"],
  ["大结果集会不会卡死？", "分页 + 最大行数限制，Agent 结果截断提示，前端虚拟滚动", "端到端限流"],
  ["部署与运维成本？", "单机 Docker 一键启动、单端口，/metrics 可接入现有监控", "无外部依赖"],
];
for (let r = 0; r < T.length; r++) for (let c = 0; c < T[r].length; c++) tb.cells.set(r, c, T[r][c]);

// ---- speaker notes for new slides ----
const notes = {
  [L]: "数据来源：README.md（部署方式）、backend/app/config.py（DEFAULT_DB_TYPES）、backend/app/services/connection_service.py、backend/app/database.py、backend/app/permissions.py。",
  [Q]: "数据来源：backend/app/services/（分层）、backend/tests（167 项测试，pytest 用例计数）、backend/pyproject.toml（ruff）、backend/migrations、Dockerfile。",
  [A]: "数据来源：backend/app/services/sql_service.py（确认机制）、backend/app/security.py（Fernet）、backend/app/adapters/registry.py（数据源类型）、backend/app/services/agent_service.py（结果截断）。",
};
for (const [sid, text] of Object.entries(notes)) p.resolve(sid).speakerNotes.text = text;


// ---------- finalize ----------
import path from "node:path";
import { pathToFileURL } from "node:url";

const SKILL_DIR = "/Users/ly/.codex/plugins/cache/openai-primary-runtime/presentations/26.1013.11914/skills/presentations";
const workspaceDir = "/Users/ly/Code/DataMind";
const RUNTIME_PYTHON = "/Users/ly/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3";
const FINAL_PPTX = "/Users/ly/Code/DataMind/docs/DataMind数据库Agent项目介绍V1.1.pptx";
const SOURCE_SHA = "15848670fedfc2466d5f33bc299dcb2a1055c355cde3e25a26689da2b3393ddd";

const { finalizePresentation } = await import(pathToFileURL(path.join(SKILL_DIR, "container_tools/artifact_tool_utils.mjs")).href);
const stagingDir = path.join(workspaceDir, ".ppt-build/finalizer");
await fs.mkdir(stagingDir, { recursive: true });
await fs.mkdir(path.dirname(FINAL_PPTX), { recursive: true });
const candidatePath = path.join(stagingDir, "candidate.pptx");
await (await PresentationFile.exportPptx(p)).save(candidatePath);

const requirements = {
  explicitTotalSlideCount: 25,
  requiredNativeTableOwnerSlides: [17, 19, 25],
  requiredNativeChartOwnerSlides: [],
};
const tableOwners = requirements.requiredNativeTableOwnerSlides;
const result = await finalizePresentation({
  ...requirements,
  workspaceDir,
  candidatePath,
  finalPath: FINAL_PPTX,
  pythonExecutable: RUNTIME_PYTHON,
  integrityValidatorPath: path.join(SKILL_DIR, "container_tools/inspect_presentation_package_integrity.py"),
  layoutValidatorPath: path.join(SKILL_DIR, "container_tools/inspect_presentation_layout_geometry.py"),
  layoutArgs: [
    "--expected-slide-size-emu", "12192000,6858000",
    "--validate-bullet-geometry",
    "--validate-heading-fit",
    ...tableOwners.flatMap((number) => ["--require-native-table-slide", String(number)]),
  ],
  requiredNativeTableOwnerSlides: tableOwners,
  fontPolicy: { basis: "reference", families: ["Helvetica Neue", "微软雅黑"], referencePath: SRC, referenceSha256: SOURCE_SHA },
  verifyArtifactToolImport: true,
  receiptPath: path.join(stagingDir, "final.validation.json"),
});
console.log("FINAL", FINAL_PPTX);
console.log(JSON.stringify(result, null, 1).slice(0, 4000));
