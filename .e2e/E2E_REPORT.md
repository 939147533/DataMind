# DataMind 新增功能 E2E 测试报告

- 日期: 2026-08-13
- 环境: 后端 http://127.0.0.1:8000 / 前端 http://localhost:5174
- 浏览器: Codex In-App Browser（默认 1280x720，必要时临时 1920x1080）
- 账号: admin / admin123
- 数据源: 本地演示库 (SQLite, demo.db)，表 users

## 测试结果总览

| # | 功能 | 结果 | 说明 |
|---|------|------|------|
| 1 | 登录 | ✅ | admin 登录成功跳转 /smart-query |
| 2 | 运维监控总览 | ✅ | /monitor 加载正常 |
| 3 | 慢查询统计页 | ✅ | 阈值筛选/列表正常 |
| 4 | 定时任务 | ✅ | 创建→运行→删除全流程通过；导出请求已发出（沙箱内无法直接校验文件落盘） |
| 5 | 表结构对比 schema diff | ✅ | 选择源/目标数据源后输出差异 |
| 6 | SQL 工作台执行 | ✅ | SELECT 执行并渲染结果表 |
| 7 | 结果集单元格编辑 | ✅ | 双击编辑→写操作二次确认→保存生效，已还原原值 |
| 8 | 结果集新增行 | ✅ | 新增弹窗→二次确认→插入成功（共 9 行） |
| 9 | 结果集删除行 | ✅ | 删除→确认弹窗（预览 DELETE SQL）→确认执行→UI 与 DB 均删除 |
| 10 | Agent 面板布局修复回归 | ✅ | 面板改右侧停靠栏；1280x720 下删除按钮可点击、弹窗正常、收起态不遮挡（详见下节） |

## 删除行详细验证（本次补充完成）

1. 打开 SQL 工作台，执行 `SELECT * FROM users LIMIT 50;`，确认共 9 行、`e2e_test_user` 存在。
2. 点击该行「删除」→ 弹出「写操作确认」：将影响 1 行数据，SQL 预览 `DELETE FROM "users" WHERE "id" = 9`。
3. 点击「确认执行」→ 状态显示「影响 1 行」，表格刷新为共 8 行，`e2e_test_user` 消失。
4. DB 校验：`backend/data/demo.db` 中 users 表恢复为 8 条原始数据，id=9 已删除。

## 发现的问题（布局 Bug）

- 在 1280x720 视口下，AI Agent 面板（position: fixed, z-index: 50, x≈882–1264）会覆盖结果表最右侧「操作」列，
  导致「删除」按钮无法点击；收起面板后，右下角 FAB（48x48）又会盖住最后一行（如第 9 行）的删除按钮。
- 在 1920x1080 视口下无遮挡，删除流程完全正常 → 属窄屏/面板布局问题。
- 建议：面板改为不遮挡表格的布局（如 flex 流式排布或为表格预留空间），或将操作列/表格容器与面板避让。
- **状态：已修复并验证（见下节「布局修复回归验证」）**。


## 布局修复回归验证

- 修复内容：`frontend/src/components/AgentPanel.vue` 由 fixed 悬浮面板改为 `frontend/src/views/WorkspaceView.vue` 内的右侧停靠栏（`n-layout-sider`，展开 396px / 收起 48px 竖条 rail），不再覆盖结果表；`npm run build` 通过。
- 展开态删除按钮可点击：1280x720 下删除按钮位于 x≈861（面板起点 x≈884 左侧），`elementFromPoint` 命中链为表格行（`TD.n-data-table-td → TR.n-data-table-tr`，非面板）；点击弹出「写操作确认将影响 1 行数据」+ DELETE SQL 预览，点「取消」后表格仍为 8 行、无残留弹窗。
- 收起态不遮挡：点「收起」后右侧栏收为 48px rail（x≈1232–1280），删除按钮位于 x≈1137，rail 与操作列不相交；点 rail（title=“展开 Agent”）恢复 396px 面板。
- 横向滚动后可再次点击：重新滚动结果表使操作列进入可视区后，删除按钮回到 x≈789，再次执行 点击→弹窗→取消 正常。
- 证据截图：`.e2e/screens/fix-03-delete-modal.png`（展开态弹窗）、`fix-04-expanded.png`（展开态）、`fix-05-collapsed.png`（收起态 rail）、`fix-06-delete-modal2.png`（重滚动后弹窗）。
- 命中/坐标数据：`.e2e/reg-06-del-info.json`、`reg-11-collapsed.json`、`reg-15-hittest.json`、`reg-17-final.json`。

## 备注

- 测试过程截图与 DOM 快照见 .e2e/screens 与 .e2e/dom。
- 测试数据已还原：演示库 users 表保持原始 8 行（id 1-8, alice..heidi），无残留脏数据。
- 布局回归全程仅点击「取消」，未对原始数据执行写操作。
