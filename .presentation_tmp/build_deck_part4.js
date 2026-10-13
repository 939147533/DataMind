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
