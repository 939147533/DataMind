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
