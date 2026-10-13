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
