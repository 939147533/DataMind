# AGENTS.md

> 面向在本仓库中工作的 AI 编码代理：说明项目背景、代码结构、架构与开发约定。

## 项目概述

**DataMind（数据库 Agent Web 应用，DB Agent）**：一个前后端分离的数据库查询 AI Agent 工作台，基于《需求说明书 V2.0/V3.0》实现。支持连接管理、SQL 工作台（含结果集直接编辑与 SQL 收藏）、元数据管理、AI 自然语言查询（SSE 流式 + 工具调用）、报表可视化、系统管理（AI 配置/JDBC 驱动/偏好）、用户与角色权限、审计日志（可导出并按保留期自动清理）、运维监控（慢查询/连接概览/表结构对比/Prometheus 指标）、定时导出。

- 需求文档：`需求说明书V2.0.md`（基线）、`需求说明书V3.0.md`（在 V2 基础上补充了角色权限页面控制，2026-08-12 更新）
- 版本：v2.0.0（FastAPI title、package.json、Docker 镜像 tag 均为 2.0.0）
- 默认账户：`admin / admin123`（首次登录后建议修改）

## 技术栈

- 后端：Python 3.12 + FastAPI + SQLAlchemy 2.0（async）+ aiosqlite（应用库）+ sqlglot（SQL 格式化/解析）+ openai/anthropic SDK + sshtunnel/paramiko（SSH 隧道）
- 前端：Vue 3 + TypeScript + Vite + Pinia + Naive UI + CodeMirror 6 + ECharts + gridstack
- 测试：pytest（后端）；playwright E2E 脚本 `scripts/e2e_final.mjs`（前端）
- 部署：Docker 多阶段构建（单端口 8000，FastAPI 托管 `frontend/dist`）；本地开发模式前后端分离（8000 + Vite 5174）

## 目录结构

```
backend/
  app/
    main.py             FastAPI 入口：CORS、异常处理、路由注册、SPA 托管、lifespan 种子数据
    config.py           路径/常量配置（数据目录、超时、端口、默认账号）；DBAGENT_DATA_DIR 可覆盖数据目录
    database.py         SQLAlchemy 异步引擎与会话
    models.py           SQLAlchemy 模型（16 张表）
    schemas.py          Pydantic 请求/响应模型
    security.py         Fernet 加密、pbkdf2 密码哈希、token 生成
    deps.py             依赖：get_current_user（Cookie 会话）、get_client_ip
    response.py         统一响应 {code, message, data}
    permissions.py      权限码、5 个内置角色、权限校验依赖
    seed.py             启动种子：默认管理员、演示 SQLite 库、演示连接、默认 AI 配置、默认设置
    adapters/           数据库适配层（SQLite/MySQL/PostgreSQL/Oracle/MongoDB）
    routers/            API 路由（auth/connections/sql/metadata/agent/export/charts/system/audit/users/roles/monitor/saved/schedule）
    services/           业务服务层（sql/agent/connection/metadata/export/llm/ssh_tunnel/audit_service/schedule_service）
  tests/                pytest 测试（每个模块对应测试文件）
  data/                 运行数据（app.db、demo.db、drivers/、exports/、secret.key），已被 .gitignore 忽略
frontend/
  src/
    api/client.ts       fetch 封装（统一响应、401 跳转、SSE、文件下载）
    api/index.ts        按模块组织的类型化 API
    stores/             Pinia（auth/connections/settings/workspace/agent）
    router/index.ts     路由 + 权限守卫（meta.permission）
    views/              页面（Login/SmartQuery/Workspace/Connections/Reports/DashboardDetail/Share/Users/Roles/Settings/Audit/Monitor）
    components/         组件（SqlEditor/ObjectTree/ResultTable/ChartCard/DashboardGrid/BigScreenDashboard/AgentPanel 等）
scripts/                启动脚本（start_dev.ps1 / start_prod.ps1 / start_dev.cmd）、init_demo.py、seed_oracle_bank.py、e2e_final.mjs
docs/                   ai_agent_test_cases.md（AI Agent 测试用例）
Dockerfile / docker-compose.yml   多阶段构建 + 一键启动（数据卷 dbagent-data）
```

## 功能模块

| 模块 | 后端 | 前端 | 说明 |
|---|---|---|---|
| 认证 | routers/auth.py | LoginView、stores/auth.ts | Cookie 会话（httponly `session_token`，24h TTL） |
| 连接管理 | routers/connections.py + services/connection_service.py | SettingsView「数据库连接配置」页签（内嵌 ConnectionsView）、stores/connections.ts | 数据源 CRUD、测试、克隆、SSH 隧道、多环境标签；密码 Fernet 加密；入口已并入系统设置页 |
| SQL 工作台 | routers/sql.py + services/sql_service.py | WorkspaceView、SqlEditor、ResultTable、ObjectTree | 多 Tab CodeMirror 编辑器、对象树、执行历史、结果分页/排序/导出、结果集直接编辑（双击单元格/新增/删除行）、虚拟滚动 |
| SQL 安全执行 | services/sql_service.py | ConfirmExecModal | READ 自动执行；DML/DDL 生成 execution_id 待确认（5 分钟有效）；全部审计 |
| 元数据管理 | routers/metadata.py + services/metadata_service.py | ObjectTree | Schema/表/列/索引/DDL/视图/函数/存储过程/触发器/序列、收藏、表结构对比（schema diff） |
| AI Agent | routers/agent.py + services/agent_service.py + llm_providers.py | SmartQueryView、stores/agent.ts | NL→SQL（SSE）、SQL 解释/优化、多轮会话、写操作授权、生成图表、工具调用（查表结构/采样数据/EXPLAIN）、SQL 失败自动修正重试、历史 SQL few-shot |
| 文档导出 | routers/export.py + services/export_service.py | WorkspaceView/ReportsView | 结果导出（csv/json/excel）；库文档异步导出（word/markdown/html） |
| 可视化报表 | routers/charts.py | ReportsView、ChartCard、DashboardGrid、BigScreenDashboard、ShareView | 图表 CRUD、仪表盘（gridstack）、分享链接、大屏模式 |
| 系统管理 | routers/system.py | SettingsView | 大模型连接配置（原 AI 配置，OpenAI 兼容/Claude/Ollama，Key 加密）、偏好设置（JDBC 驱动上传已隐藏） |
| 用户/角色 | routers/users.py、roles.py | UsersView、RolesView | RBAC：5 个内置角色 + 自定义角色，权限码按功能分组 |
| 审计日志 | routers/audit.py + services/audit_service.py | MonitorView（审计日志 Tab，内嵌 AuditView） | 登录/SQL 执行/Agent 动作等全部审计；导出（csv/xlsx）；按 audit_retention_days 自动清理（默认 180 天） |
| SQL 收藏 | routers/saved.py | WorkspaceView（收藏 Tab） | 常用 SQL 收藏/模板 CRUD |
| 运维监控 | routers/monitor.py | MonitorView | 连接概览、慢查询统计、表结构对比（schema diff）、审计日志（Tab） |
| 定时导出 | routers/schedule.py + services/schedule_service.py | MonitorView（定时任务 Tab） | 定时导出报表/订阅推送，后台调度循环每分钟扫描执行，复用 export_service |

## 架构

分层：`routers → services → adapters → 目标数据库`，应用自身状态存 SQLite（`data/app.db`）。

- **适配器模式**（`app/adapters/`）：`BaseDBAdapter` 定义统一接口（connect/test/metadata/execute/explain/schema_summary），`registry.py` 按 db_type 分发；oceanbase/goldendb 复用 MySQLAdapter；`ConnectionInfo` 承载连接参数（含 SSH）。函数/存储过程 DDL 已实现：MySQL（SHOW CREATE）、PostgreSQL（pg_get_functiondef/pg_get_triggerdef）、Oracle（dbms_metadata）；序列支持：SQLite/MySQL/Oracle/PostgreSQL 已实现，MongoDB 不适用（后续可继续补齐）。
- **LLM Provider 抽象**（`services/llm_providers.py`）：OpenAICompatProvider（OpenAI 官方 + 兼容网关 + Ollama /v1）与 ClaudeProvider 统一 chat/stream/ping；缺失 Key 时 `validate()` 快速失败。
- **统一响应**：所有接口返回 `{code, message, data}`，用 `ok()`/`page_data()` 构造；HTTP 异常与校验异常统一处理。
- **权限模型**：用户 → role → permissions（JSON）。`admin` 角色为 `[*]`；SQL 操作按 READ/DML/DDL 分别要求 `workspace` / `sql_write` / `sql_ddl`；运维监控路由允许 `monitor` 或 `audit` 任一权限进入，页内各 Tab 按权限显示（概览/慢查询/表结构对比需 `monitor`，审计日志需 `audit`，定时任务需 `reports_manage`）；前端路由用 `meta.permission`/`meta.permissionAny` + 守卫控制（系统设置路由允许 `settings` 或 `connections` 任一权限进入，连接管理已并入设置页）。
- **SSE 事件流**（Agent）：`/api/agent/chat` 返回 `text/event-stream`，事件类型：`session_title / thought / tool / retry / sql / result / text / chart / authorization_required / done / error`。写操作由前端弹确认框，调 `/api/agent/confirm` 执行。
- **Agent 工具调用**：`agent_service` 提供 `list_tables / get_columns / sample_data / explain` 四个工具（`TOOL_NAMES`），LLM 按需调用（`MAX_TOOL_ROUNDS=3`）；READ 查询失败自动让 LLM 修正重试（最多 3 次）；每次会话注入历史成功 SQL 作为 few-shot 示例（`_load_few_shots`）。
- **写操作确认机制**：`sql_service._executions`（进程内存字典）暂存待确认执行，`execution_id` 为 key，5 分钟过期；确认后再次鉴权并执行、记录审计。
- **定时调度**：`schedule_service.scheduler_loop` 在 FastAPI lifespan 启动，每分钟扫描到期的 `scheduled_exports`，`run_in_executor` 同步调用 `export_result_file` 导出并记录 last_status/last_file。
- **监控指标**：`/metrics` 暴露 Prometheus 指标（REQUEST_COUNT/REQUEST_LATENCY、SQL_EXECUTIONS）；审计日志按 `audit_retention_days` 设置（默认 180）在启动时清理过期记录。
- **路径规范化**：SQLite 库文件与驱动文件统一存相对 `data/` 的路径；启动时 `repair_stored_paths` 自动修复历史绝对路径（项目改名后可迁移）。

## 数据模型（app.db 表）

`datasources`、`users`、`ai_configs`、`jdbc_drivers`、`query_history`、`agent_sessions`、`agent_messages`、`audit_logs`、`favorited_tables`、`charts`、`dashboards`、`sessions`、`settings`、`roles`、`saved_queries`、`scheduled_exports`。

## 关键约定与注意事项

- 新接口返回 `ok(...)`；分页用 `page_data`；错误抛 `HTTPException`。
- 密钥类字段（数据库密码、SSH 私钥、AI Key）一律经 `security.encrypt_text` 入库、`decrypt_text` 解密；对外响应只暴露 `has_password`/`has_key` 布尔值。
- 鉴权依赖优先使用 `permissions.require_permission(...)` / `require_any_permission(...)`；新增接口需同步前端 `PERMISSION_GROUPS` 与内置角色权限（`permissions.py`）。
- 结果集编辑（更新/插入/删除行）复用 `sql_service.execute_sql`，自动完成 SQL 分类/鉴权/审计；写操作返回 `need_confirm + execution_id`，前端 `ResultTable` 通过 `edit-confirm` 事件复用 ConfirmExecModal 确认。
- 用户 SQL 必须走 `sql_service.execute_sql`（拆分/分类/鉴权/审计），不要绕过服务层直接调用 adapter 执行。
- 新增数据库类型：在 `adapters/` 实现 `BaseDBAdapter` 子类并注册到 `registry.ADAPTERS`，同时更新 `config.DEFAULT_DB_TYPES/DEFAULT_PORTS` 与前端 db_type 选项。
- 种子数据在 `seed.py`；手动重建演示数据：`python scripts/init_demo.py`。
- 根目录 `_patch_charts.py`、`_patch_dualaxis.py` 是一次性历史补丁脚本，可忽略；`scripts/bank_oracle_*.sql`、`seed_oracle_bank.py` 为 Oracle 演示数据脚本（大文件，勿直接打开）。

## 开发与测试

```powershell
# 一键启动开发模式（自动建 venv/装依赖，前端 5174）
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\start_dev.ps1

# 手动后端（backend 目录）
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# 手动前端（frontend 目录，5174 避免与 5173 冲突）
npm.cmd run dev -- --port 5174

# 后端测试
cd backend; .\.venv\Scripts\python.exe -m pytest -q

# 前端类型检查与构建
cd frontend; npm.cmd run build

# Docker 一键启动（单端口 8000）
docker compose up -d --build
```

- 健康检查：`GET /api/health`
- PowerShell 执行策略：仓库脚本需 `powershell -NoProfile -ExecutionPolicy Bypass -File ...` 方式运行。
- 控制台中文乱码是 Windows PowerShell 5.1 显示问题，文件均为 UTF-8。
- 未配置 API Key 时 Agent 会立即返回错误提示（validate 快速失败），不会等待 SDK 超时。
