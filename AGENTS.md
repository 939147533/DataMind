# AGENTS.md

> 面向在本仓库中工作的 AI 编码代理：说明项目背景、代码结构、架构与开发约定。

## 项目概述

**DataMind（数据库 Agent Web 应用，DB Agent）**：一个前后端分离的数据库查询 AI Agent 工作台，基于《需求说明书 V2.0/V3.0》实现。支持连接管理、SQL 工作台（含结果集直接编辑与 SQL 收藏）、元数据管理、AI 自然语言查询（SSE 流式 + 工具调用）、报表可视化、系统管理（AI 配置/JDBC 驱动/偏好）、用户与角色权限、审计日志（可导出并按保留期自动清理）、运维监控（慢查询/连接概览/表结构对比/Prometheus 指标）、定时导出。

- 需求文档：`需求说明书V2.0.md`（基线）、`需求说明书V3.0.md`（在 V2 基础上补充了角色权限页面控制，2026-08-12 更新）
- 版本：v2.0.0（FastAPI title、package.json、Docker 镜像 tag 均为 2.0.0）
- 默认账户：`admin / admin123`（首次登录后建议修改）

## 技术栈

- 后端：Python 3.12 + FastAPI + SQLAlchemy 2.0（async）+ aiosqlite（应用库）+ Alembic（结构迁移）+ sqlglot（SQL 格式化/解析）+ openai/anthropic SDK + sshtunnel/paramiko（SSH 隧道）
- 前端：Vue 3 + TypeScript + Vite + Pinia + Naive UI + CodeMirror 6 + ECharts + gridstack
- 测试：pytest（后端）；playwright E2E 脚本 `scripts/e2e_final.mjs`（前端）
- 质量：ruff 静态检查（`backend/pyproject.toml`）；前端 `npm run typecheck`（vue-tsc）
- 部署：Docker 多阶段构建（单端口 8000，FastAPI 托管 `frontend/dist`）；本地开发模式前后端分离（8000 + Vite 5174）

## 目录结构

```
backend/
  app/
    main.py             FastAPI 入口：CORS、异常处理、路由注册、SPA 托管、lifespan 种子数据
    config.py           路径/常量配置（数据目录、超时、端口、默认账号、Agent 循环上限、连接池、监控令牌、密钥路径）；DBAGENT_DATA_DIR / DBAGENT_AGENT_MAX_TOOL_ROUNDS / DBAGENT_AGENT_SQL_MAX_ATTEMPTS / DBAGENT_DB_POOL_SIZE / DBAGENT_DB_POOL_IDLE_TTL / DBAGENT_METRICS_TOKEN / DBAGENT_SECRET_KEY / DBAGENT_SECRET_KEY_FILE / DBAGENT_ADMIN_PASSWORD 等环境变量可覆盖
    database.py         SQLAlchemy 异步引擎与会话
    models.py           SQLAlchemy 模型（17 张表）
    schemas.py          Pydantic 请求/响应模型
    security.py         Fernet 加密、pbkdf2 密码哈希、token 生成
    deps.py             依赖：get_current_user（Cookie 会话）、get_client_ip
    response.py         统一响应 {code, message, data}
    permissions.py      权限码、5 个内置角色、权限校验依赖
    seed.py             启动种子：默认管理员、演示 SQLite 库、演示连接、默认 AI 配置、默认设置
    adapters/           数据库适配层（SQLite/MySQL/PostgreSQL/Oracle/MongoDB）+ pool.py 只读连接池
    routers/            API 路由（auth/connections/sql/metadata/agent/export/charts/system/audit/users/roles/monitor/saved/schedule）
    services/           业务服务层（sql/agent/connection/metadata/export/llm/ssh_tunnel/audit_service/schedule_service/sql_examples）
  tests/                pytest 测试（每个模块对应测试文件）
  data/                 运行数据（app.db、demo.db、drivers/、exports/、secret.key），已被 .gitignore 忽略
  alembic.ini          Alembic 迁移配置（连接串由 migrations/env.py 从 app.config 推导）
  migrations/          Alembic 迁移脚本；0001 为当前模型基线
  pyproject.toml       ruff 静态检查配置
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
| 连接管理 | routers/connections.py + services/connection_service.py | SettingsView「数据库连接配置」页签（内嵌 ConnectionsView）、stores/connections.ts | 数据源 CRUD、测试、克隆、SSH 隧道、多环境标签；密码 Fernet 加密；侧边栏入口名为「连接管理」（原系统设置页），并内含「数据库连接配置」页签 |
| SQL 工作台 | routers/sql.py + services/sql_service.py | WorkspaceView、SqlEditor、ResultTable、ObjectTree | 多 Tab CodeMirror 编辑器、对象树、执行历史、结果分页/排序/导出、结果集直接编辑（双击单元格/新增/删除行）、虚拟滚动 |
| SQL 安全执行 | services/sql_service.py | ConfirmExecModal | READ 自动执行；DML/DDL 生成 execution_id 待确认并落库 `pending_executions`（5 分钟有效，重启不丢）；全部审计（含鉴权被拒的 denied 记录） |
| 元数据管理 | routers/metadata.py + services/metadata_service.py | ObjectTree | Schema/表/列/索引/DDL/视图/函数/存储过程/触发器/序列、收藏、表结构对比（schema diff，比较类型与长度/精度） |
| AI Agent | routers/agent.py + services/agent_service.py + llm_providers.py | SmartQueryView、stores/agent.ts | NL→SQL（SSE）、SQL 解释/优化、多轮会话、写操作授权、生成图表、工具调用（查表结构/采样数据/EXPLAIN）、SQL 失败自动修正重试、历史 SQL few-shot |
| 文档导出 | routers/export.py + services/export_service.py | WorkspaceView/ReportsView | 结果导出（csv/json/excel，仅 READ，成功与失败都写 `export_result` 审计）；库文档异步导出（word/markdown/html，写 `export_database` 审计） |
| 可视化报表 | routers/charts.py | ReportsView、ChartCard、DashboardGrid、BigScreenDashboard、ShareView | 图表 CRUD、仪表盘（gridstack）、分享链接、大屏模式 |
| 系统管理 | routers/system.py | SettingsView | 大模型连接配置（原 AI 配置，OpenAI 兼容/Claude/Ollama，Key 加密）；偏好设置与 JDBC 驱动上传已隐藏 |
| 用户/角色 | routers/users.py、roles.py | UsersView、RolesView | RBAC：5 个内置角色 + 自定义角色，权限码按功能分组 |
| 审计日志 | routers/audit.py + services/audit_service.py | MonitorView（审计日志 Tab，内嵌 AuditView） | 登录/SQL 执行/Agent 动作等全部审计；导出（csv/xlsx）；按 audit_retention_days 自动清理（默认 180 天） |
| SQL 收藏 | routers/saved.py | WorkspaceView（收藏 Tab） | 常用 SQL 收藏/模板 CRUD |
| 运维监控 | routers/monitor.py | MonitorView | 连接概览、慢查询统计、表结构对比（schema diff，比较类型与长度/精度）、审计日志（Tab）；定时任务已从前端隐藏；`/metrics` 需令牌或内网访问 |
| 定时导出 | routers/schedule.py + services/schedule_service.py | MonitorView（定时任务 Tab，已隐藏） | 定时导出报表/订阅推送，后台调度循环每分钟扫描并用条件 UPDATE 认领到期任务（多副本不会重复执行），复用 export_service |

## 架构

分层：`routers → services → adapters → 目标数据库`，应用自身状态存 SQLite（`data/app.db`）。

- **适配器模式**（`app/adapters/`）：`BaseDBAdapter` 定义统一接口（connect/test/metadata/execute/explain/schema_summary），`registry.py` 按 db_type 分发；oceanbase/goldendb 复用 MySQLAdapter；`ConnectionInfo` 承载连接参数（含 SSH）。函数/存储过程 DDL 已实现：MySQL（SHOW CREATE）、PostgreSQL（pg_get_functiondef/pg_get_triggerdef）、Oracle（dbms_metadata）；序列支持：SQLite/MySQL/Oracle/PostgreSQL 已实现，MongoDB 不适用（后续可继续补齐）。
- **连接池与事件循环**：目标库驱动（pymysql/psycopg2/oracledb/pymongo）全是同步实现，因此所有目标库调用都必须离开事件循环——`sql_service.build_adapter_async` / `call_adapter` / `asyncio.to_thread` 是唯一入口（SSH 建隧道同样阻塞）。网络型驱动的只读元数据查询走 `adapters/pool.py` 的进程级连接池（按连接参数分桶、跨请求复用、借出前存活探测、归还前回滚，`DBAGENT_DB_POOL_SIZE`/`DBAGENT_DB_POOL_IDLE_TTL` 可调）；SQLite 是本地文件、建连近乎免费且连接有线程亲和性，保持每次新建；写操作（`execute()`）一律独占连接，保证事务语义清晰。
- **数据层与迁移**：`query_history`/`audit_logs`/`agent_messages`/`dashboards.share_token` 等热点列已加索引；`init_db()` 建表后用 `database._create_missing_indexes` 给老库补建缺失索引（`create_all` 不会改动已有表）。列表分页总数统一用 `COUNT(*)` 子查询（`select(func.count()).select_from(query.order_by(None).subquery())`），不把全量行拉进内存。结构变更走 Alembic（`backend/migrations`）；已上线的老库首次接入先 `alembic stamp head` 打基线，避免与 `create_all` 重复建表。
- **LLM Provider 抽象**（`services/llm_providers.py`）：OpenAICompatProvider（OpenAI 官方 + 兼容网关 + Ollama /v1）与 ClaudeProvider 统一 chat/stream/ping；缺失 Key 时 `validate()` 快速失败。
- **统一响应**：所有接口返回 `{code, message, data}`，用 `ok()`/`page_data()` 构造；HTTP 异常与校验异常统一处理。
- **权限模型**：用户 → role → permissions（JSON）。`admin` 角色为 `[*]`；SQL 操作按 READ/DML/DDL 分别要求 `workspace` / `sql_write` / `sql_ddl`；运维监控路由允许 `monitor` 或 `audit` 任一权限进入，页内各 Tab 按权限显示（概览/慢查询/表结构对比需 `monitor`，审计日志需 `audit`；定时任务 Tab 已隐藏）；前端路由用 `meta.permission`/`meta.permissionAny` + 守卫控制（`settings` 路由即侧边栏「连接管理」，允许 `settings` 或 `connections` 任一权限进入）。
- **SSE 事件流**（Agent）：`/api/agent/chat` 返回 `text/event-stream`，事件类型：`session_title / thought / tool / retry / sql / result / text / chart / authorization_required / done / error`。写操作由前端弹确认框，调 `/api/agent/confirm` 执行。
- **Agent 工具调用**：`agent_service` 提供 `list_tables / get_columns / sample_data / explain` 四个工具（`TOOL_NAMES`），LLM 按需调用（轮数上限 `config.AGENT_MAX_TOOL_ROUNDS`，默认 3）；READ 查询失败自动让 LLM 修正重试（最大执行次数 `config.AGENT_SQL_MAX_ATTEMPTS`，默认 3，即最多 2 次修正；仅限 SQL 自身报错即 HTTP 400，鉴权失败等不重试）；每轮对话注入历史成功 SQL 作为 few-shot 示例（`_load_few_shots` → `services/sql_examples.py`），候选池按 datasource 缓存（写入侧 `record()` 增量合并、TTL 300s 兜底），并按提问相似度、表名重合度、执行频次加权排序后取前 3 条。
- **SQL 语句风险分类**（`sql_service.classify_statement`）：执行前按首个关键字把语句判为 READ（只读）/ DML（改数据）/ DDL（改结构）三档，并加固会被首个关键字绕过的写法——`WITH` 语句跳过括号内的 CTE 定义取主动词（`WITH ... DELETE/UPDATE/INSERT` 判为 DML/DDL）、`EXPLAIN ANALYZE` 会真正执行被解释语句故按内层语句定级（普通 `EXPLAIN` / Oracle `EXPLAIN PLAN` 仍是 READ）、`SELECT ... INTO`（Postgres 建表 / MySQL `INTO OUTFILE`、`INTO @var`）升为 DDL、`FOR UPDATE` / `FOR SHARE` / `LOCK IN SHARE MODE` 加锁读升为 DML；判定前先遮蔽字符串字面量与注释，其中的关键字不参与分类；多语句取最高等级，无法识别时一律按 DML 兜底。分级结果决定所需权限（`workspace` / `sql_write` / `sql_ddl`）与是否二次确认（仅 READ 免确认直达），并全程留审计。
- **写操作确认机制**：待确认执行落库到 `pending_executions`（`execution_id` 主键，5 分钟有效，启动时 `cleanup_expired_executions` 清理过期记录）；确认后再次鉴权并执行、记录审计，记录一次性消费（重启、多副本下都能确认）。
- **定时调度**：`schedule_service.scheduler_loop` 在 FastAPI lifespan 启动，每分钟扫描到期的 `scheduled_exports`，用 `claim_schedule` 的条件 UPDATE（`next_run_at <= now` 且改到行才认领）抢占任务，多副本下同一任务只执行一次；执行用 `run_in_executor` 调 `export_result_file` 并记录 last_status/last_file。
- **连接池生命周期**：只读连接按数据源分桶复用，借出前存活探测、归还前回滚；数据源参数变更/删除时 `connection_service` 用 `adapter_pool_key` + `DB_POOL.drop` 作废旧连接；`pool_sweeper` 后台任务（60s）回收空闲超时连接，进程退出时清池。
- **监控指标**：`/metrics` 暴露 Prometheus 指标（REQUEST_COUNT/REQUEST_LATENCY、SQL_EXECUTIONS），路径标签取**路由模板**（`/api/connections/{connection_id}`）避免基数爆炸；配置 `DBAGENT_METRICS_TOKEN` 后必须带 `Authorization: Bearer <token>`，未配置时只允许本机/内网访问。审计日志按 `audit_retention_days` 设置（默认 180）在启动时清理过期记录。
- **安全基线**：加密密钥优先取 `DBAGENT_SECRET_KEY`（环境变量）或 `DBAGENT_SECRET_KEY_FILE`（独立挂载），默认文件 `data/secret.key` 创建时 chmod 600，启动 `security.warm_up()` 检查；首次管理员口令可用 `DBAGENT_ADMIN_PASSWORD` 指定，仍是默认口令时启动告警；密钥文件与导出文件不再入库（见 `.gitignore`）。
- **路径规范化**：SQLite 库文件与驱动文件统一存相对 `data/` 的路径；启动时 `repair_stored_paths` 自动修复历史绝对路径（项目改名后可迁移）。

## 数据模型（app.db 表）

`datasources`、`users`、`ai_configs`、`jdbc_drivers`、`query_history`、`agent_sessions`、`agent_messages`、`audit_logs`、`favorited_tables`、`charts`、`dashboards`、`sessions`、`settings`、`roles`、`saved_queries`、`scheduled_exports`。

`pending_executions`（待确认写操作，见「写操作确认机制」）。

## 关键约定与注意事项

- 新接口返回 `ok(...)`；分页用 `page_data`；错误抛 `HTTPException`。
- 密钥类字段（数据库密码、SSH 私钥、AI Key）一律经 `security.encrypt_text` 入库、`decrypt_text` 解密；对外响应只暴露 `has_password`/`has_key` 布尔值。
- 鉴权依赖优先使用 `permissions.require_permission(...)` / `require_any_permission(...)`；新增接口需同步前端 `PERMISSION_GROUPS` 与内置角色权限（`permissions.py`）。
- 结果集编辑（更新/插入/删除行）复用 `sql_service.execute_sql`，自动完成 SQL 分类/鉴权/审计；写操作返回 `need_confirm + execution_id`，前端 `ResultTable` 通过 `edit-confirm` 事件复用 ConfirmExecModal 确认。
- 用户 SQL 必须走 `sql_service.execute_sql`（拆分/分类/鉴权/审计），不要绕过服务层直接调用 adapter 执行。
- SQL 风险等级统一由 `sql_service.classify_statement` 判定（READ/DML/DDL，细则见「架构」章节）；新增数据库方言或新的写语法时，需同步加固分类，避免被首个关键字绕过。
- 新增数据库类型：在 `adapters/` 实现 `BaseDBAdapter` 子类并注册到 `registry.ADAPTERS`，同时更新 `config.DEFAULT_DB_TYPES/DEFAULT_PORTS` 与前端 db_type 选项。
- 新增/修改适配器时：只读查询（`_query` 等元数据方法）必须走 `_acquire_conn()`/`_release_conn(conn, broken=not ok)` 复用连接池，异常连接要 `broken=True` 丢弃；写路径（`execute`）保持自建连接。所有目标库调用都必须 `await`（或丢进线程池），禁止在协程里直接调用同步驱动。
- 列表接口统计总数用 `func.count()` 子查询（参照 `routers/audit.py`），不要 `len(query.scalars().all())`。
- 数据源参数变更/删除必须调用 `DB_POOL.drop(adapter_pool_key(ds))`（新增/删除前先取旧 key），别让旧连接继续被复用。
- 改表结构（新增表/列/索引）时同步写 Alembic 迁移：`alembic revision --autogenerate -m "..."`，并保持 `alembic check` 无输出。
- 提交前先跑 `ruff check .`（backend 目录）并通过；不要把 `__pycache__/`、`data/secret.key`、`data/exports/*` 提交进仓库（已在根 `.gitignore`）。
- 种子数据在 `seed.py`；手动重建演示数据：`python scripts/init_demo.py`。
- 根目录 `_patch_charts.py`、`_patch_dualaxis.py` 是一次性历史补丁脚本，可忽略；`scripts/bank_oracle_*.sql`、`seed_oracle_bank.py` 为 Oracle 演示数据脚本（大文件，勿直接打开）。

## 开发与测试

```bash
# macOS / Linux 一键启动与停止（后台运行，日志在 scripts/.run/；自动建 venv/装依赖）
./scripts/start_dev.sh     # 可用 --port 5175 / --backend-only / --frontend-only / --reload / --no-install
./scripts/stop_dev.sh      # 停止服务；--status 查看状态，--backend / --frontend 只操作其一
```

```powershell
# Windows：一键启动开发模式（自动建 venv/装依赖，前端 5174）
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\start_dev.ps1

# 手动后端（backend 目录）
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# 手动前端（frontend 目录，5174 避免与 5173 冲突）
npm.cmd run dev -- --port 5174

# 后端测试
cd backend; .\.venv\Scripts\python.exe -m pytest -q

# 前端类型检查与构建
cd frontend; npm.cmd run build

# 后端静态检查（backend 目录；配置见 pyproject.toml）
cd backend; ruff check .

# 数据库结构迁移（backend 目录；老库首次接入先 stamp 打基线）
cd backend; .\.venv\Scripts\python.exe -m alembic upgrade head
cd backend; .\.venv\Scripts\python.exe -m alembic revision --autogenerate -m "变更说明"

# Docker 一键启动（单端口 8000）
docker compose up -d --build
```

- 健康检查：`GET /api/health`
- PowerShell 执行策略：仓库脚本需 `powershell -NoProfile -ExecutionPolicy Bypass -File ...` 方式运行。
- 控制台中文乱码是 Windows PowerShell 5.1 显示问题，文件均为 UTF-8。
- 未配置 API Key 时 Agent 会立即返回错误提示（validate 快速失败），不会等待 SDK 超时。
- 全新安装由 `init_db()` 的 `create_all` 建表（含索引），无需跑迁移；只有当表结构变更、需要改已上线的库时才用 Alembic。
