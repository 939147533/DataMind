import fs from "node:fs/promises";
import path from "node:path";
import { Presentation, PresentationFile } from "@oai/artifact-tool";

const FONT = "Microsoft YaHei";
const ACCENT = "#0B5FFF";
const DARK = "#0B1830";
const INK = "#0F172A";
const MUTED = "#475569";
const LIGHT_LINE = "#E2E8F0";
const LIGHT_BG = "#F8FAFC";

const deck = Presentation.create({ slideSize: { width: 1280, height: 720 } });

function addSlide(bg = "#FFFFFF") {
  const slide = deck.slides.add();
  slide.background.fill = bg;
  return slide;
}

function addText(slide, name, text, pos, opts = {}) {
  const shape = slide.shapes.add({
    geometry: "textbox",
    name,
    position: pos,
    fill: "none",
    line: { style: "solid", fill: "none", width: 0 },
  });
  shape.text = text;
  shape.text.style = {
    typeface: FONT,
    fontSize: opts.fontSize ?? 16,
    bold: opts.bold ?? false,
    color: opts.color ?? INK,
    alignment: opts.alignment ?? "left",
    verticalAlignment: opts.verticalAlignment ?? "top",
    wrap: opts.wrap ?? "square",
    lineSpacing: opts.lineSpacing ?? 1.25,
  };
  return shape;
}

function addRect(slide, name, pos, opts = {}) {
  return slide.shapes.add({
    geometry: opts.round ? "roundRect" : "rect",
    name,
    position: pos,
    fill: opts.fill ?? LIGHT_BG,
    line: opts.line ?? { style: "solid", fill: LIGHT_LINE, width: 1 },
    borderRadius: opts.round ? (opts.borderRadius ?? "rounded-2xl") : undefined,
    shadow: opts.shadow ?? "shadow-none",
  });
}

function addHeader(slide, kicker, title, opts = {}) {
  addText(slide, "kicker", kicker, { left: 72, top: 40, width: 500, height: 24 }, {
    fontSize: 14, bold: true, color: ACCENT, wrap: "none",
  });
  addText(slide, "title", title, { left: 72, top: 66, width: 1100, height: 58 }, {
    fontSize: 35, bold: true, color: INK, wrap: "none",
  });
  addRect(slide, "title-accent", { left: 72, top: 130, width: 56, height: 5 }, {
    fill: ACCENT, line: { style: "solid", fill: "none", width: 0 },
  });
  if (opts.footer !== false) addFooter(slide);
}

function addFooter(slide) {
  addRect(slide, "footer-line", { left: 72, top: 676, width: 1136, height: 1 }, {
    fill: LIGHT_LINE, line: { style: "solid", fill: "none", width: 0 },
  });
  addText(slide, "footer-left", "DataMind · 数据库 Agent Web 应用", { left: 72, top: 686, width: 500, height: 18 }, {
    fontSize: 12, color: "#94A3B8", wrap: "none",
  });
  addText(slide, "footer-page", String(deck.slides.items.length), { left: 1108, top: 686, width: 100, height: 18 }, {
    fontSize: 12, color: "#94A3B8", alignment: "right", wrap: "none",
  });
}

function addBullets(slide, name, items, pos, opts = {}) {
  const shape = addText(slide, name, "", pos, opts);
  const paragraphs = items.map((item) => {
    if (typeof item === "string") {
      return {
        bulletCharacter: "•",
        marginLeft: 22,
        indent: -12,
        spaceBefore: opts.spaceBefore ?? 8,
        runs: [item],
      };
    }
    return {
      bulletCharacter: "•",
      marginLeft: 22,
      indent: -12,
      spaceBefore: opts.spaceBefore ?? 8,
      runs: [
        { run: item.lead, textStyle: { bold: true, color: opts.leadColor ?? INK } },
        { run: item.text, textStyle: { color: opts.textColor ?? MUTED } },
      ],
    };
  });
  shape.text.set(paragraphs);
  return shape;
}

function addTable(slide, name, values, pos, opts = {}) {
  const rows = values.length;
  const cols = values[0].length;
  const table = slide.tables.add({
    rows,
    columns: cols,
    left: pos.left,
    top: pos.top,
    width: pos.width,
    height: pos.height,
    values,
  });
  table.styleOptions = { headerRow: true, bandedRows: true, firstColumn: false };
  table.borders.assign({ style: "solid", fill: "#D7E2F0", width: 1 });
  for (let c = 0; c < cols; c++) {
    const cell = table.getCell(0, c);
    cell.fill = opts.headerFill ?? DARK;
    cell.text.style = {
      typeface: FONT,
      fontSize: opts.headerSize ?? 16,
      bold: true,
      color: "#FFFFFF",
      alignment: "left",
      verticalAlignment: "middle",
      insets: { top: 7, bottom: 7, left: 14, right: 14 },
    };
  }
  for (let r = 1; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const cell = table.getCell(r, c);
      cell.text.style = {
        typeface: FONT,
        fontSize: opts.bodySize ?? 16,
        color: INK,
        alignment: "left",
        verticalAlignment: "middle",
        insets: { top: 6, bottom: 6, left: 14, right: 14 },
      };
    }
  }
  return table;
}

function setNotes(slide, lines) {
  slide.speakerNotes.textFrame.setText(lines);
  slide.speakerNotes.setVisible(true);
}

function arrow(slide, name, pos, color = ACCENT) {
  return slide.shapes.add({
    geometry: "rightArrow",
    name,
    position: pos,
    fill: color,
    line: { style: "solid", fill: "none", width: 0 },
    shadow: "shadow-none",
  });
}

// 1. Cover
{
  const s = addSlide("linear(135deg, #061224 0%, #0A2A5E 56%, #0B5FFF 100%)");
  addRect(s, "cover-glow", { left: 780, top: 60, width: 430, height: 430 }, {
    round: true, borderRadius: "rounded-full", fill: "#22C55E/8",
    line: { style: "solid", fill: "none", width: 0 }, shadow: "shadow-none",
  });
  addText(s, "cover-eyebrow", "AI PROGRAMMING COMPETITION · PROJECT SHOWCASE", { left: 96, top: 128, width: 800, height: 24 }, {
    fontSize: 14, bold: true, color: "#7DD3FC", wrap: "none",
  });
  addText(s, "cover-title", "DataMind", { left: 90, top: 178, width: 720, height: 110 }, {
    fontSize: 64, bold: true, color: "#FFFFFF", wrap: "none", lineSpacing: 1,
  });
  addText(s, "cover-subtitle", "数据库 Agent Web 应用", { left: 96, top: 292, width: 720, height: 48 }, {
    fontSize: 30, bold: true, color: "#FFFFFF", wrap: "none",
  });
  addText(s, "cover-claim", "让每个人安全、高效地与数据对话", { left: 96, top: 352, width: 760, height: 40 }, {
    fontSize: 20, color: "#DBEAFE", wrap: "none",
  });
  const tags = ["AI Agent", "Multi-Database", "Security First"];
  tags.forEach((tag, i) => {
    const x = 96 + i * 232;
    addText(s, `cover-tag-${i}`, tag, { left: x, top: 436, width: 210, height: 28 }, {
      fontSize: 16, bold: true, color: "#93C5FD", wrap: "none",
    });
    addRect(s, `cover-tag-line-${i}`, { left: x, top: 470, width: 40, height: 3 }, {
      fill: i === 2 ? "#22C55E" : ACCENT, line: { style: "solid", fill: "none", width: 0 },
    });
  });
  addText(s, "cover-version", "v2.0.0 · 可运行 · 可测试 · 可部署", { left: 96, top: 596, width: 600, height: 28 }, {
    fontSize: 16, color: "#BFDBFE", wrap: "none",
  });
  setNotes(s, [
    "开场控制在 15 秒内：这是一个前后端分离、AI Agent 驱动的数据库查询与运维工作台。",
    "一句话说清用户价值：不会 SQL 的人也能查询，会 SQL 的人更快。",
  ]);
}

// 2. Agenda
{
  const s = addSlide("#FFFFFF");
  addHeader(s, "展示路线", "20 页讲清产品价值、技术亮点与工程完整度");
  const items = [
    ["01", "为什么做", "定位、目标用户与真实痛点"],
    ["02", "产品能力", "AI 查询、SQL 工作台、报表、元数据"],
    ["03", "技术亮点", "Agent 工具调用、安全执行、跨库适配"],
    ["04", "工程与治理", "RBAC、审计、监控、测试、部署"],
  ];
  items.forEach((item, i) => {
    const y = 178 + i * 112;
    addText(s, `agenda-num-${i}`, item[0], { left: 96, top: y, width: 110, height: 70 }, {
      fontSize: 46, bold: true, color: ACCENT, wrap: "none",
    });
    addText(s, `agenda-title-${i}`, item[1], { left: 230, top: y + 6, width: 300, height: 36 }, {
      fontSize: 26, bold: true, color: DARK, wrap: "none",
    });
    addText(s, `agenda-desc-${i}`, item[2], { left: 230, top: y + 46, width: 800, height: 28 }, {
      fontSize: 17, color: MUTED, wrap: "none",
    });
    if (i < items.length - 1) {
      addRect(s, `agenda-line-${i}`, { left: 96, top: y + 90, width: 980, height: 1 }, {
        fill: LIGHT_LINE, line: { style: "solid", fill: "none", width: 0 },
      });
    }
  });
  setNotes(s, [
    "先给观众一个清晰的路线图：从为什么做，到产品能力、技术亮点，再到工程治理。",
    "说明后续每一部分都服务于同一个判断：这是一个可运行、可测试、可部署的完整产品。",
  ]);
}

// 3. Product positioning
{
  const s = addSlide("#FFFFFF");
  addHeader(s, "项目定位", "一个工具，覆盖从查询到报表的完整数据链路");
  addText(s, "positioning-intro", "DataMind 是一款开源、智能、跨数据库的 Agent Web 应用。用户可以用自然语言提问，也可以使用传统 SQL 编辑器完成查询、表结构管理、性能分析和报表导出。", { left: 72, top: 158, width: 500, height: 130 }, {
    fontSize: 18, color: MUTED, lineSpacing: 1.5,
  });
  addBullets(s, "positioning-values", [
    { lead: "AI 驱动：", text: "自然语言生成 SQL、解释与优化建议" },
    { lead: "多数据库统一：", text: "一套工具管理主流关系型数据库与 MongoDB" },
    { lead: "高效工作台：", text: "编辑器、元数据、导出、报表面板一体化" },
    { lead: "轻量可扩展：", text: "Python 后端与插件化适配器，便于二次开发" },
  ], { left: 72, top: 296, width: 500, height: 260 }, {
    fontSize: 17, leadColor: DARK, textColor: MUTED, spaceBefore: 14,
  });
  addTable(s, "positioning-table", [
    ["用户", "核心需求", "典型场景"],
    ["后端开发者", "快速查数、编写与优化 SQL", "日常开发、数据排障"],
    ["DBA / 管理员", "多实例管理与变更监控", "运维、变更审计"],
    ["数据分析师", "自然语言取数、可视化", "数据探索、报表制作"],
    ["产品经理", "不熟悉 SQL 也要看数据", "辅助决策、简单分析"],
  ], { left: 620, top: 158, width: 588, height: 330 }, { headerFill: ACCENT, bodySize: 15 });
  setNotes(s, [
    "强调 DataMind 不只是 SQL 编辑器，而是从连接到查询、分析、报表、审计的完整闭环。",
    "与常见客户端工具的核心差异：内置 AI Agent、Web 化协作、权限与审计。",
  ]);
}

// 4. Pain points and solutions
{
  const s = addSlide("#F8FAFC");
  addHeader(s, "为什么需要 DataMind", "把高门槛、高风险的数据工作，变成安全可控的对话");
  addRect(s, "pain-surface", { left: 72, top: 160, width: 548, height: 472 }, {
    round: true, fill: "#FFFFFF", line: { style: "solid", fill: "#E2E8F0", width: 1 }, shadow: "shadow-sm",
  });
  addText(s, "pain-title", "常见痛点", { left: 104, top: 190, width: 300, height: 36 }, {
    fontSize: 24, bold: true, color: "#B91C1C", wrap: "none",
  });
  addBullets(s, "pain-list", [
    "业务人员不会写 SQL，取数依赖技术同事",
    "数据库类型多，不同工具反复切换",
    "AI 生成 SQL 存在误操作与越权风险",
    "查询结果难以沉淀为报表与文档",
    "敏感数据与用户操作缺少权限和审计",
  ], { left: 104, top: 244, width: 484, height: 350 }, {
    fontSize: 17, color: "#334155", leadColor: "#B91C1C", textColor: "#334155", spaceBefore: 16,
  });
  addRect(s, "solution-surface", { left: 660, top: 160, width: 548, height: 472 }, {
    round: true, fill: "#FFFFFF", line: { style: "solid", fill: "#BFDBFE", width: 1 }, shadow: "shadow-sm",
  });
  addText(s, "solution-title", "DataMind 的解法", { left: 692, top: 190, width: 300, height: 36 }, {
    fontSize: 24, bold: true, color: ACCENT, wrap: "none",
  });
  addBullets(s, "solution-list", [
    { lead: "自然语言查询：", text: "输入问题，自动生成 SQL、执行并可视化" },
    { lead: "统一适配层：", text: "屏蔽多数据库方言差异" },
    { lead: "分级安全执行：", text: "只读自动、写操作确认、DDL 高危提示" },
    { lead: "报表与大屏：", text: "结果一键沉淀为图表、仪表盘、分享页" },
    { lead: "RBAC + 审计：", text: "细粒度权限、全量留痕、可导出" },
  ], { left: 692, top: 244, width: 484, height: 350 }, {
    fontSize: 17, leadColor: ACCENT, textColor: "#334155", spaceBefore: 16,
  });
  setNotes(s, [
    "用真实工作流举例：产品经理打开网页，输入“本月新增用户按日分组”，系统生成 SQL、返回结果，并可一键生成图表。",
    "不要逐条念，重点突出从“会写 SQL”到“会描述需求”的降低门槛。",
  ]);
}

// 5. Feature map
{
  const s = addSlide("#FFFFFF");
  addHeader(s, "功能全景", "围绕数据工作流组织，而不是功能堆砌");
  const left = [
    { lead: "连接管理：", text: "数据源 CRUD、连接测试、SSH 隧道、环境标签、密码加密" },
    { lead: "SQL 工作台：", text: "多 Tab 编辑器、对象树、执行历史、结果分页/导出/直接编辑" },
    { lead: "元数据管理：", text: "表/列/索引/DDL/视图/函数/存储过程/触发器/序列" },
    { lead: "AI Agent：", text: "NL→SQL、解释优化、多轮会话、工具调用、写操作授权、自动修正" },
  ];
  const right = [
    { lead: "文档导出：", text: "CSV/JSON/Excel；库文档 Word/Markdown/HTML 异步导出" },
    { lead: "可视化报表：", text: "图表 CRUD、仪表盘、分享链接、大屏模式" },
    { lead: "系统管理：", text: "大模型配置、偏好设置、用户角色、审计、定时导出" },
    { lead: "运维监控：", text: "连接概览、慢查询、表结构对比、Prometheus 指标" },
  ];
  addBullets(s, "features-left", left, { left: 72, top: 172, width: 548, height: 450 }, {
    fontSize: 17, leadColor: ACCENT, textColor: MUTED, spaceBefore: 20,
  });
  addBullets(s, "features-right", right, { left: 660, top: 172, width: 548, height: 450 }, {
    fontSize: 17, leadColor: ACCENT, textColor: MUTED, spaceBefore: 20,
  });
  setNotes(s, [
    "功能模块不是孤立存在，而是围绕“查询—分析—报表—管理”闭环组织。",
    "补充工程化细节：定时导出、审计保留期自动清理。",
  ]);
}

// 6. AI Agent overview
{
  const s = addSlide("#FFFFFF");
  addHeader(s, "核心亮点 · AI Agent", "把自然语言变成可信、可解释、可执行的 SQL");
  addText(s, "agent-overview-intro", "Agent 不是简单调用大模型，而是围绕 Schema、工具与安全策略构建的查询推理系统。", { left: 72, top: 158, width: 1136, height: 48 }, {
    fontSize: 18, color: MUTED, wrap: "none",
  });
  addTable(s, "agent-capability-table", [
    ["能力", "说明", "价值"],
    ["自然语言 → SQL", "输入问题，自动生成对应 SQL", "降低取数门槛"],
    ["Schema 感知", "自动获取表结构作为上下文", "提升生成准确率"],
    ["多轮对话", "保留上下文，可追问与调整", "更自然的交互"],
    ["SQL 解释与优化", "解释含义、分析执行计划", "帮助理解与调优"],
    ["流式输出", "SSE 实时返回思考过程与结果", "体验透明"],
  ], { left: 72, top: 220, width: 1136, height: 360 }, { headerFill: ACCENT, bodySize: 16 });
  setNotes(s, [
    "强调 Agent 能力的层次：不只是生成 SQL，还包括 Schema 感知、多轮对话、解释优化和流式输出。",
    "下一页会展开工程实现中的工具调用与失败重试。",
  ]);
}

// 7. AI Agent workflow
{
  const s = addSlide("#FFFFFF");
  addHeader(s, "Agent 执行链路", "工具调用 + 失败重试 + few-shot，让结果更可靠");
  const nodeW = 190;
  const nodeH = 74;
  const gap = 30;
  const startX = 72;
  const y = 300;
  const nodes = [
    ["用户提问", "自然语言描述需求"],
    ["Agent 推理", "Schema 感知 + 历史 few-shot"],
    ["工具调用", "表结构 / 采样 / EXPLAIN"],
    ["生成 SQL", "只读查询或写操作"],
    ["安全执行", "结果 / 图表 / 解释"],
  ];
  nodes.forEach((node, i) => {
    const x = startX + i * (nodeW + gap);
    addRect(s, `agent-node-${i}`, { left: x, top: y, width: nodeW, height: nodeH }, {
      round: true, fill: i === 0 || i === 4 ? "#EFF6FF" : "#0B5FFF",
      line: { style: "solid", fill: i === 0 || i === 4 ? "#BFDBFE" : "none", width: 1 },
      borderRadius: "rounded-xl", shadow: "shadow-sm",
    });
    addText(s, `agent-node-title-${i}`, node[0], { left: x + 12, top: y + 14, width: nodeW - 24, height: 28 }, {
      fontSize: 20, bold: true, color: i === 0 || i === 4 ? DARK : "#FFFFFF", alignment: "center", wrap: "none",
    });
    addText(s, `agent-node-desc-${i}`, node[1], { left: x + 10, top: y + 46, width: nodeW - 20, height: 24 }, {
      fontSize: 13, color: i === 0 || i === 4 ? MUTED : "#DBEAFE", alignment: "center", wrap: "none",
    });
    if (i < nodes.length - 1) {
      arrow(s, `agent-arrow-${i}`, { left: x + nodeW + 4, top: y + 24, width: gap - 8, height: 26 }, ACCENT);
    }
  });
  addText(s, "agent-loop", "失败自动修正：READ 查询错误后，由 LLM 重新生成 SQL，最多重试 3 次", { left: 72, top: 416, width: 1136, height: 30 }, {
    fontSize: 16, bold: true, color: "#065F46", wrap: "none",
  });
  addText(s, "agent-tools", "内置工具：list_tables · get_columns · sample_data · explain　｜　工具调用最多 3 轮　｜　SSE 流式输出", { left: 72, top: 460, width: 1136, height: 30 }, {
    fontSize: 15, color: MUTED, wrap: "none",
  });
  setNotes(s, [
    "重点讲“工具调用 + 失败重试 + few-shot”，这是 AI 编程竞赛最看重的工程深度。",
    "现场演示：输入“查询本月新增用户数并按日分组”，展示思考过程、SQL、结果和图表生成。",
  ]);
}

// 8. SQL security
{
  const s = addSlide("#FFFFFF");
  addHeader(s, "核心亮点 · 安全执行", "AI 可以生成 SQL，但不会拥有不受控的写权限");
  addTable(s, "security-table", [
    ["操作类型", "授权方式", "执行说明"],
    ["SELECT / SHOW / DESC / EXPLAIN", "自动执行", "只读查询直接返回结果"],
    ["INSERT / UPDATE / DELETE", "手动确认", "返回影响预览与 execution_id"],
    ["CREATE / ALTER / DROP / TRUNCATE", "高危确认", "红色警告并展示完整 DDL"],
    ["多条混合 SQL", "逐条确认", "按 SQL 类型分别处理"],
  ], { left: 72, top: 172, width: 1136, height: 300 }, { headerFill: "#0B1830", bodySize: 17 });
  addText(s, "security-callout", "execution_id 暂存待确认执行，5 分钟过期；用户确认后再次鉴权，全程审计。", { left: 72, top: 502, width: 1136, height: 30 }, {
    fontSize: 16, bold: true, color: "#B45309", wrap: "none",
  });
  setNotes(s, [
    "这是项目的信任基础：让 AI 能生成 SQL，但不让 AI 拥有不受控的写权限。",
    "可对比“直接给 AI 数据库权限”的传统做法，突出安全设计。",
  ]);
}

// 9. SQL workbench
{
  const s = addSlide("#F8FAFC");
  addHeader(s, "SQL 工作台", "面向开发者的高频查询环境");
  addRect(s, "sql-editor-surface", { left: 72, top: 160, width: 548, height: 472 }, {
    round: true, fill: "#FFFFFF", line: { style: "solid", fill: "#E2E8F0", width: 1 }, shadow: "shadow-sm",
  });
  addText(s, "sql-editor-title", "编辑器与对象树", { left: 104, top: 190, width: 300, height: 36 }, {
    fontSize: 24, bold: true, color: ACCENT, wrap: "none",
  });
  addBullets(s, "sql-editor-list", [
    { lead: "CodeMirror 6：", text: "语法高亮、自动补全、SQL 格式化" },
    { lead: "多 Tab：", text: "并行处理多个查询任务" },
    { lead: "对象树：", text: "表、视图、索引、触发器等快速浏览" },
    { lead: "执行历史：", text: "重复查询一键复用" },
  ], { left: 104, top: 244, width: 484, height: 340 }, {
    fontSize: 17, leadColor: ACCENT, textColor: "#334155", spaceBefore: 18,
  });
  addRect(s, "sql-result-surface", { left: 660, top: 160, width: 548, height: 472 }, {
    round: true, fill: "#FFFFFF", line: { style: "solid", fill: "#E2E8F0", width: 1 }, shadow: "shadow-sm",
  });
  addText(s, "sql-result-title", "结果集与直接编辑", { left: 692, top: 190, width: 300, height: 36 }, {
    fontSize: 24, bold: true, color: ACCENT, wrap: "none",
  });
  addBullets(s, "sql-result-list", [
    { lead: "虚拟滚动：", text: "大数据量下保持流畅" },
    { lead: "分页与排序：", text: "按需加载，快速定位" },
    { lead: "导出：", text: "CSV / JSON / Excel" },
    { lead: "直接编辑：", text: "双击单元格、新增/删除行，写操作走确认链路" },
  ], { left: 692, top: 244, width: 484, height: 340 }, {
    fontSize: 17, leadColor: ACCENT, textColor: "#334155", spaceBefore: 18,
  });
  setNotes(s, [
    "SQL 工作台解决“效率”问题：多 Tab、对象树、执行历史和结果集编辑减少重复操作。",
    "结果集直接编辑仍然复用 execute_sql，自动完成分类、鉴权与审计。",
  ]);
}

// 10. Metadata management
{
  const s = addSlide("#FFFFFF");
  addHeader(s, "元数据管理", "从对象浏览到结构对比，一次看清数据资产");
  addText(s, "metadata-intro", "对象树支持常见数据库对象与收藏，并提供表结构对比（schema diff），帮助团队识别变更风险。", { left: 72, top: 158, width: 1136, height: 48 }, {
    fontSize: 18, color: MUTED, wrap: "none",
  });
  addTable(s, "metadata-table", [
    ["能力", "支持内容"],
    ["对象浏览", "Schema / 表 / 列 / 索引 / 约束 / DDL"],
    ["高级对象", "视图 / 函数 / 存储过程 / 触发器 / 序列"],
    ["收藏", "常用表快速访问"],
    ["结构对比", "两库表结构差异与变更识别"],
  ], { left: 72, top: 220, width: 1136, height: 320 }, { headerFill: ACCENT, bodySize: 16 });
  setNotes(s, [
    "强调 DDL 提取已经按数据库方言实现：MySQL SHOW CREATE、PostgreSQL pg_get_functiondef、Oracle dbms_metadata。",
    "表结构对比用于变更审计，也是运维监控的一部分。",
  ]);
}

// 11. Cross-database adapters
{
  const s = addSlide("#FFFFFF");
  addHeader(s, "跨数据库适配", "上层服务无感知，底层方言被统一封装");
  addText(s, "adapter-intro", "BaseDBAdapter 定义统一接口：connect / test / metadata / execute / explain / schema_summary。ConnectionInfo 统一承载连接参数与 SSH 隧道。", { left: 72, top: 160, width: 1136, height: 68 }, {
    fontSize: 18, color: MUTED, lineSpacing: 1.5,
  });
  addTable(s, "adapter-table", [
    ["数据库", "适配方式", "关键能力"],
    ["SQLite", "SQLiteAdapter", "应用库与演示库、零配置"],
    ["MySQL", "MySQLAdapter", "元数据、DDL、序列、慢查询"],
    ["PostgreSQL", "PostgreSQLAdapter", "pg_get_functiondef / triggerdef"],
    ["Oracle", "OracleAdapter", "dbms_metadata、序列与存储过程"],
    ["MongoDB", "MongoDBAdapter", "非关系型数据探索"],
    ["OceanBase / GoldenDB", "复用 MySQLAdapter", "低新增成本接入"],
  ], { left: 72, top: 246, width: 1136, height: 356 }, { headerFill: ACCENT, bodySize: 16 });
  setNotes(s, [
    "重点讲“同一套 Agent 工具如何屏蔽数据库方言差异”。",
    "例如获取表结构在不同数据库里调用不同 SQL，但上层服务无感知。",
  ]);
}

// 12. Visualization and reports
{
  const s = addSlide("#FFFFFF");
  addHeader(s, "可视化报表", "查询结果直接变成可分享、可展示的看板");
  const cols = [
    ["图表", "柱状图 / 折线图 / 饼图", "自定义 SQL → 图表"],
    ["仪表盘", "gridstack 拖拽布局", "多图表组合展示"],
    ["分享与大屏", "分享链接 + 大屏模式", "跨团队、跨设备查看"],
  ];
  const colW = 348;
  const colH = 330;
  const startX = 72;
  const y = 178;
  cols.forEach((col, i) => {
    const x = startX + i * (colW + 46);
    addRect(s, `report-col-${i}`, { left: x, top: y, width: colW, height: colH }, {
      round: true, fill: "#F8FAFC", line: { style: "solid", fill: "#E2E8F0", width: 1 }, shadow: "shadow-sm",
    });
    addText(s, `report-title-${i}`, col[0], { left: x + 28, top: y + 32, width: colW - 56, height: 38 }, {
      fontSize: 26, bold: true, color: DARK, wrap: "none",
    });
    addText(s, `report-sub-${i}`, col[1], { left: x + 28, top: y + 86, width: colW - 56, height: 60 }, {
      fontSize: 18, bold: true, color: ACCENT, lineSpacing: 1.3,
    });
    addText(s, `report-desc-${i}`, col[2], { left: x + 28, top: y + 156, width: colW - 56, height: 130 }, {
      fontSize: 16, color: MUTED, lineSpacing: 1.45,
    });
  });
  setNotes(s, [
    "报表模块让查询结果不止停留在表格里，而是可以直接形成可复用的看板。",
    "大屏模式适合项目路演和监控展示场景。",
  ]);
}

// 13. AI model configuration
{
  const s = addSlide("#FFFFFF");
  addHeader(s, "系统管理 · AI 配置", "模型可插拔，Key 只加密存储，前端不回显明文");
  addTable(s, "ai-config-table", [
    ["Provider", "接入方式", "配置说明"],
    ["OpenAI 兼容", "OpenAI 官方 / 兼容网关 / Ollama v1", "API Key + 可选 api_base + 模型名"],
    ["Claude", "Anthropic SDK", "API Key + 模型名"],
    ["Ollama", "本地 /v1", "服务地址 + 模型名，本地可无 Key"],
  ], { left: 72, top: 168, width: 1136, height: 280 }, { headerFill: ACCENT, bodySize: 16 });
  addText(s, "ai-config-note", "默认模型在系统设置中选择；对话创建时选择该会话使用的模型，创建后不可切换以保证上下文一致。", { left: 72, top: 486, width: 1136, height: 48 }, {
    fontSize: 17, bold: true, color: "#334155", lineSpacing: 1.4,
  });
  setNotes(s, [
    "重点讲 Provider 抽象：OpenAICompatProvider 与 ClaudeProvider 统一 chat / stream / ping。",
    "未配置 Key 时 validate 快速失败，不会等待 SDK 超时。",
  ]);
}

// 14. Users and roles
{
  const s = addSlide("#FFFFFF");
  addHeader(s, "用户与角色", "RBAC 权限从页面控制到 SQL 操作级别");
  addBullets(s, "rbac-left", [
    { lead: "5 个内置角色：", text: "admin、运维、分析师、只读用户等预设能力" },
    { lead: "自定义角色：", text: "权限码按功能分组，灵活组合" },
    { lead: "页面控制：", text: "路由守卫按 permission / permissionAny 控制" },
  ], { left: 72, top: 172, width: 548, height: 380 }, {
    fontSize: 18, leadColor: ACCENT, textColor: MUTED, spaceBefore: 22,
  });
  addText(s, "rbac-right-title", "SQL 权限三层拆分", { left: 660, top: 172, width: 400, height: 36 }, {
    fontSize: 24, bold: true, color: DARK, wrap: "none",
  });
  addTable(s, "rbac-table", [
    ["操作", "权限码", "说明"],
    ["只读查询", "workspace", "SELECT / SHOW / DESC / EXPLAIN"],
    ["写操作", "sql_write", "INSERT / UPDATE / DELETE"],
    ["结构变更", "sql_ddl", "CREATE / ALTER / DROP / TRUNCATE"],
  ], { left: 660, top: 220, width: 548, height: 250 }, { headerFill: "#0B1830", bodySize: 16 });
  addText(s, "rbac-note", "运维监控路由允许 monitor 或 audit 任一权限进入，页内各 Tab 再按权限显示。", { left: 660, top: 492, width: 548, height: 64 }, {
    fontSize: 16, color: MUTED, lineSpacing: 1.4,
  });
  setNotes(s, [
    "权限模型是用户 → 角色 → permissions（JSON），admin 角色为 [*]。",
    "重点说明 SQL 操作不是粗粒度开关，而是 READ / DML / DDL 分别授权。",
  ]);
}

// 15. Audit and monitoring
{
  const s = addSlide("#F8FAFC");
  addHeader(s, "审计与监控", "让每一次操作都可追溯、可观察");
  addRect(s, "audit-surface", { left: 72, top: 160, width: 548, height: 472 }, {
    round: true, fill: "#FFFFFF", line: { style: "solid", fill: "#E2E8F0", width: 1 }, shadow: "shadow-sm",
  });
  addText(s, "audit-title", "审计日志", { left: 104, top: 190, width: 300, height: 36 }, {
    fontSize: 24, bold: true, color: "#B45309", wrap: "none",
  });
  addBullets(s, "audit-list", [
    "登录、SQL 执行、Agent 动作全量留痕",
    "操作类型、SQL 文本、状态可追溯",
    "导出 CSV / XLSX",
    "audit_retention_days 默认 180 天自动清理",
  ], { left: 104, top: 244, width: 484, height: 350 }, {
    fontSize: 17, color: "#334155", spaceBefore: 18,
  });
  addRect(s, "monitor-surface", { left: 660, top: 160, width: 548, height: 472 }, {
    round: true, fill: "#FFFFFF", line: { style: "solid", fill: "#E2E8F0", width: 1 }, shadow: "shadow-sm",
  });
  addText(s, "monitor-title", "运维监控", { left: 692, top: 190, width: 300, height: 36 }, {
    fontSize: 24, bold: true, color: ACCENT, wrap: "none",
  });
  addBullets(s, "monitor-list", [
    "连接概览与慢查询统计",
    "表结构对比（schema diff）",
    "定时导出任务状态",
    "/metrics 暴露 Prometheus 指标",
  ], { left: 692, top: 244, width: 484, height: 350 }, {
    fontSize: 17, color: "#334155", spaceBefore: 18,
  });
  setNotes(s, [
    "审计与监控是系统可治理的体现，也是企业级部署的关键。",
    "强调审计导出与自动清理，以及 Prometheus 指标对运维友好。",
  ]);
}

// 16. Engineering
{
  const s = addSlide("#FFFFFF");
  addHeader(s, "工程化与可观测性", "不只做功能，也关注可测试、可监控、可部署");
  const metrics = [
    ["21", "后端测试文件", "约 115 个 pytest 用例"],
    ["95+", "API 端点", "15 个路由模块"],
    ["1", "命令部署", "Docker Compose 一键启动"],
    ["3", "监控信号", "请求量 / 延迟 / SQL 执行"],
  ];
  const mw = 266;
  const mx = 72;
  const my = 170;
  metrics.forEach((m, i) => {
    const x = mx + i * (mw + 24);
    addRect(s, `eng-surface-${i}`, { left: x, top: my, width: mw, height: 150 }, {
      round: true, fill: "#F8FAFC", line: { style: "solid", fill: "#E2E8F0", width: 1 }, shadow: "shadow-sm",
    });
    addText(s, `eng-number-${i}`, m[0], { left: x + 18, top: my + 24, width: mw - 36, height: 54 }, {
      fontSize: 44, bold: true, color: ACCENT, wrap: "none",
    });
    addText(s, `eng-label-${i}`, m[1], { left: x + 18, top: my + 84, width: mw - 36, height: 30 }, {
      fontSize: 18, bold: true, color: DARK, wrap: "none",
    });
    addText(s, `eng-desc-${i}`, m[2], { left: x + 18, top: my + 112, width: mw - 36, height: 28 }, {
      fontSize: 14, color: MUTED, wrap: "none",
    });
  });
  addBullets(s, "eng-details", [
    { lead: "测试：", text: "后端 pytest、前端构建校验、Playwright E2E 脚本" },
    { lead: "调度：", text: "每分钟扫描定时导出任务，复用 export_service" },
    { lead: "监控：", text: "慢查询、连接概览、表结构对比、Prometheus 指标" },
    { lead: "部署：", text: "Docker 多阶段构建，数据卷 dbagent-data 持久化" },
  ], { left: 72, top: 356, width: 1136, height: 230 }, {
    fontSize: 17, leadColor: ACCENT, textColor: MUTED, spaceBefore: 14,
  });
  setNotes(s, [
    "工程化能力是竞赛加分项，但不要展开太深，用数据和截图快速证明。",
    "可补充：后端约 43 个 Python 文件、前端约 32 个源文件。",
  ]);
}

// 17. Architecture
{
  const s = addSlide("#0B1830");
  addText(s, "arch-kicker", "系统架构", { left: 72, top: 42, width: 500, height: 24 }, {
    fontSize: 14, bold: true, color: "#7DD3FC", wrap: "none",
  });
  addText(s, "arch-title", "分层清晰，扩展点明确", { left: 72, top: 70, width: 1100, height: 58 }, {
    fontSize: 35, bold: true, color: "#FFFFFF", wrap: "none",
  });
  addRect(s, "arch-accent", { left: 72, top: 134, width: 56, height: 5 }, {
    fill: "#22C55E", line: { style: "solid", fill: "none", width: 0 },
  });
  const layers = [
    ["前端 · Vue 3", "Vite · TypeScript · Pinia · Naive UI · CodeMirror 6 · ECharts · gridstack", "FE"],
    ["后端 API · FastAPI", "15 个路由模块 · 业务服务层 · 统一响应与异常处理", "BE"],
    ["数据库适配层", "BaseDBAdapter → SQLite / MySQL / PostgreSQL / Oracle / MongoDB", "AD"],
    ["目标数据库", "应用状态存 SQLite，数据源按类型分发执行", "DB"],
  ];
  const lw = 980;
  const lh = 82;
  const lx = 150;
  const ly = 186;
  layers.forEach((layer, i) => {
    const y = ly + i * (lh + 28);
    addRect(s, `arch-layer-${i}`, { left: lx, top: y, width: lw, height: lh }, {
      round: true, fill: i === 0 ? "#0B5FFF" : "#123B78",
      line: { style: "solid", fill: "#3B82F6", width: 1 }, borderRadius: "rounded-xl", shadow: "shadow-md",
    });
    addText(s, `arch-layer-title-${i}`, layer[0], { left: lx + 22, top: y + 12, width: 250, height: 30 }, {
      fontSize: 22, bold: true, color: "#FFFFFF", wrap: "none",
    });
    addText(s, `arch-layer-desc-${i}`, layer[1], { left: lx + 22, top: y + 46, width: lw - 44, height: 26 }, {
      fontSize: 15, color: "#DBEAFE", wrap: "none",
    });
    if (i < layers.length - 1) {
      arrow(s, `arch-arrow-${i}`, { left: lx + 60, top: y + lh - 2, width: 26, height: 30 }, "#22C55E");
    }
  });
  setNotes(s, [
    "强调两个可扩展点：数据库适配器和 LLM Provider 抽象。",
    "补充：OceanBase、GoldenDB 复用 MySQLAdapter，后续新增数据库成本低。",
  ]);
}

// 18. Product interface
{
  const s = addSlide("#FFFFFF");
  addHeader(s, "产品界面", "每个高频场景都有对应的工作台视图");
  addTable(s, "interface-table", [
    ["场景", "核心视图", "关键能力"],
    ["AI 智能查询", "SmartQueryView / AgentPanel", "SSE 流式问答、工具调用、图表生成"],
    ["SQL 工作台", "WorkspaceView / SqlEditor", "多 Tab 编辑、对象树、结果集编辑"],
    ["可视化报表", "ReportsView / DashboardGrid", "图表、仪表盘、分享、大屏模式"],
    ["系统与监控", "SettingsView / MonitorView", "用户角色、审计、慢查询、定时任务"],
  ], { left: 72, top: 168, width: 1136, height: 330 }, { headerFill: "#0B1830", bodySize: 16 });
  addText(s, "interface-note", "登录入口：http://127.0.0.1:5174　·　演示账号：admin / admin123", { left: 72, top: 534, width: 1136, height: 30 }, {
    fontSize: 16, bold: true, color: ACCENT, wrap: "none",
  });
  setNotes(s, [
    "现场按“智能查询 → 结果转图表 → 保存报表 → 审计日志”顺序演示。",
    "如果时间有限，优先演示 AI Agent 和写操作确认弹窗。",
  ]);
}

// 19. Innovation and difficulties
{
  const s = addSlide("#FFFFFF");
  addHeader(s, "创新点与技术难点", "工程封装让大模型能力变得稳定、安全、可用");
  addText(s, "innov-title", "创新点", { left: 72, top: 172, width: 300, height: 34 }, {
    fontSize: 24, bold: true, color: ACCENT, wrap: "none",
  });
  addBullets(s, "innov-list", [
    "自然语言到 SQL 的 Agent 闭环：工具调用、失败重试、few-shot 增强",
    "写操作分级确认，让 AI 可用且可控",
    "跨数据库适配层，统一多源元数据与查询体验",
    "查询结果一键转图表、仪表盘、分享大屏",
    "RBAC + 全量审计 + Prometheus 指标，具备企业级完整性",
  ], { left: 72, top: 222, width: 548, height: 400 }, {
    fontSize: 17, color: MUTED, spaceBefore: 16,
  });
  addText(s, "difficulty-title", "技术难点", { left: 660, top: 172, width: 300, height: 34 }, {
    fontSize: 24, bold: true, color: "#B45309", wrap: "none",
  });
  addBullets(s, "difficulty-list", [
    "多数据库方言抽象与 DDL / 序列元数据提取",
    "控制 Agent 工具调用轮次与 token 成本",
    "SSE 流式事件在前端的逐步渲染",
    "结果集直接编辑与写操作确认链路",
    "SSH 隧道连接与敏感信息加密",
  ], { left: 660, top: 222, width: 548, height: 400 }, {
    fontSize: 17, color: MUTED, spaceBefore: 16,
  });
  setNotes(s, [
    "挑 2–3 个最有差异化的点展开，例如“失败自动修正重试”和“写操作确认协议”。",
    "表明团队不是简单调用大模型，而是做了可靠的工程封装。",
  ]);
}

// 20. Summary and outlook
{
  const s = addSlide("linear(135deg, #061224 0%, #0A2A5E 56%, #0B5FFF 100%)");
  addText(s, "close-kicker", "总结与展望", { left: 72, top: 44, width: 500, height: 24 }, {
    fontSize: 14, bold: true, color: "#7DD3FC", wrap: "none",
  });
  addText(s, "close-title", "用 AI Agent 重新定义数据库查询与数据协作", { left: 72, top: 76, width: 1100, height: 62 }, {
    fontSize: 40, bold: true, color: "#FFFFFF", wrap: "none",
  });
  addText(s, "close-summary", "DataMind 已完成自然语言查询、安全执行、跨库适配、报表、权限审计、监控、定时导出与 Docker 部署。", { left: 72, top: 156, width: 1080, height: 48 }, {
    fontSize: 20, color: "#DBEAFE", lineSpacing: 1.4,
  });
  const metrics = [
    ["7", "数据库类型", "跨库适配"],
    ["115+", "测试用例", "可测试"],
    ["1", "命令部署", "可部署"],
    ["v2.0.0", "产品版本", "可运行"],
  ];
  const mw = 250;
  metrics.forEach((m, i) => {
    const x = 72 + i * (mw + 30);
    addText(s, `close-num-${i}`, m[0], { left: x, top: 226, width: mw, height: 48 }, {
      fontSize: 38, bold: true, color: "#22C55E", wrap: "none",
    });
    addText(s, `close-label-${i}`, m[1], { left: x, top: 276, width: mw, height: 26 }, {
      fontSize: 17, bold: true, color: "#FFFFFF", wrap: "none",
    });
    addText(s, `close-desc-${i}`, m[2], { left: x, top: 304, width: mw, height: 22 }, {
      fontSize: 14, color: "#DBEAFE", wrap: "none",
    });
  });
  addText(s, "close-plan-title", "下一步路线", { left: 72, top: 368, width: 300, height: 34 }, {
    fontSize: 24, bold: true, color: "#FFFFFF", wrap: "none",
  });
  const roadmap = [
    "补齐更多数据库适配器与 DDL / 序列能力",
    "扩展 Agent 工具：索引建议、慢查询根因分析",
    "增强图表高级能力与协作工作区",
    "建设会话级 Prompt 模板与模型评测体系",
  ];
  addBullets(s, "close-roadmap", roadmap, { left: 72, top: 416, width: 700, height: 220 }, {
    fontSize: 17, color: "#DBEAFE", spaceBefore: 13,
  });
  addText(s, "close-ask", "演示入口：http://127.0.0.1:5174 · admin / admin123", { left: 72, top: 648, width: 800, height: 30 }, {
    fontSize: 16, bold: true, color: "#BFDBFE", wrap: "none",
  });
  setNotes(s, [
    "最后回到用户价值：让每个人都能安全、高效地与数据对话。",
    "预留 Q&A：准备数据安全、AI 准确率、与现有数据库工具差异三个常见问题。",
  ]);
}

// Export PPTX and previews
const tmpDir = "E:/Code/DataMind/.presentation_tmp";
const renderDir = path.join(tmpDir, "render");
await fs.mkdir(renderDir, { recursive: true });

for (let i = 0; i < deck.slides.items.length; i++) {
  const slide = deck.slides.items[i];
  const stem = `slide-${String(i + 1).padStart(2, "0")}`;
  const png = await deck.export({ slide, format: "png", scale: 1 });
  await fs.writeFile(path.join(renderDir, `${stem}.png`), new Uint8Array(await png.arrayBuffer()));
}

const montage = await deck.export({ format: "png", montage: true, scale: 1 });
await fs.writeFile(path.join(renderDir, "montage.png"), new Uint8Array(await montage.arrayBuffer()));

const finalPptx = "E:/Code/DataMind/DataMind_竞赛展示.pptx";
const pptx = await PresentationFile.exportPptx(deck);
await pptx.save(finalPptx);

const notes = [
  "Source: E:/Code/DataMind/docs/competition_ppt_outline.md",
  "Source repo: E:/Code/DataMind",
  "No external images or third-party assets were used.",
  "Deck statistics are derived from local repository files (backend/app, frontend/src, backend/tests).",
];
await fs.writeFile(path.join(tmpDir, "source-notes.txt"), notes.join("\n"), "utf8");

console.log(`Wrote ${deck.slides.items.length} slides to ${finalPptx}`);
console.log(`Previews: ${renderDir}`);


