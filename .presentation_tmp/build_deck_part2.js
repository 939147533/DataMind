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
