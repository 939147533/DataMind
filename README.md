# DataMind —— 通用数据库 Agent Web 应用

一个前后端分离、**AI Agent 驱动的数据库查询与运维工作台**。支持连接管理、SQL 工作台、元数据管理、AI 自然语言查询（SSE 流式 + 工具调用）、可视化报表、用户与角色权限、审计日志、运维监控与定时导出。

**核心价值**：不会 SQL 的业务人员也能安全地查数据，会 SQL 的技术人员效率更高。

---

## 功能特性

- **连接管理**：SQLite / MySQL / PostgreSQL / Oracle / MongoDB / OceanBase / GoldenDB；连接测试、克隆、编辑、多环境标签、SSH 隧道；密码 Fernet 加密存储。入口位于「系统设置 → 数据库连接配置」
- **SQL 工作台**：多 Tab CodeMirror 6 编辑器、对象树（表/视图/索引/触发器/函数/存储过程/序列）、结果集分页/排序/列宽/导出、**结果集直接编辑**（双击单元格改值、新增/删除行）、大结果集虚拟滚动、SQL 收藏与模板、执行历史
- **SQL 安全执行**：执行前把语句分为 READ / DML / DDL 三档并据此鉴权放行——READ 免确认直达执行，DML 生成 `execution_id` 待确认（5 分钟有效），DDL 高危二次确认；分类已加固 CTE 写操作（`WITH … DELETE`）、`EXPLAIN ANALYZE`、`SELECT … INTO`、`FOR UPDATE` 等易绕过写法，识别不确定时按 DML 兜底；全部操作（含鉴权被拒）记录审计日志
- **AI Agent**：自然语言→SQL，SSE 流式返回思考过程/SQL/结果；**工具调用**（查表结构/采样数据/EXPLAIN）避免模型编造表名列名；查询失败自动修正重试；历史成功 SQL 作为 few-shot 示例；写操作授权弹窗；SQL 解释与优化
- **元数据管理**：Schema/表/列/索引/DDL/视图/函数/存储过程/触发器/序列；表收藏；两库**表结构对比（schema diff）**
- **可视化报表**：柱状/折线/饼图 + 仪表盘（gridstack 拖拽）、分享链接、大屏展示模式
- **用户与角色**：RBAC 权限体系，5 个内置角色 + 自定义角色，14 个细粒度权限码，前端路由守卫 + 后端鉴权双重控制
- **审计日志**：登录/SQL 执行/Agent 动作/结果与库文档导出全量审计（成功与失败都记录），CSV/Excel 导出，按保留期自动清理（默认 180 天）。入口位于「运维监控 → 审计日志」
- **运维监控**：连接概览、慢查询统计、表结构对比、审计日志、定时任务；`/metrics` 暴露 Prometheus 指标（配 `DBAGENT_METRICS_TOKEN` 后需 Bearer 令牌，未配置仅限本机/内网）
- **定时导出**：定时任务按周期导出报表/订阅推送，后台调度循环用条件 UPDATE 认领到期任务（多副本不重复执行），复用导出服务

---

## 技术栈

| 层 | 技术 |
|---|---|
| 前端 | Vue 3 + TypeScript + Vite + Pinia + Naive UI + CodeMirror 6 + ECharts + gridstack |
| 后端 | Python 3.12 + FastAPI + SQLAlchemy 2.0（async）+ aiosqlite + Alembic + sqlglot |
| AI | openai / anthropic SDK（OpenAI 兼容网关、Claude、Ollama 统一抽象） |
| 数据库 | pymysql / psycopg2 / oracledb / pymongo / aiosqlite（只读查询走进程级连接池）；sshtunnel + paramiko（SSH 隧道） |
| 测试/部署 | pytest（167 项）、ruff 静态检查、Playwright E2E；Docker 多阶段构建、docker-compose |

---

## 系统架构

分层设计：`routers → services → adapters → 目标数据库`，应用自身状态存 SQLite（`data/app.db`）。

- **适配器模式**：`BaseDBAdapter` 统一接口（connect/test/metadata/execute/explain/schema_summary），`registry` 按 `db_type` 分发；OceanBase / GoldenDB 协议兼容复用 MySQL 适配器
- **连接池与事件循环**：目标库驱动都是同步实现，所有调用统一经 `build_adapter_async / call_adapter / asyncio.to_thread` 进入线程池，慢查询不会卡住事件循环；网络型驱动（MySQL/PostgreSQL/Oracle/MongoDB）的只读元数据查询复用 `adapters/pool.py` 的进程级连接池（借出前存活探测、归还前回滚、池容量与空闲 TTL 可配），SQLite 与写操作保持独占连接
- **数据层与迁移**：热点列（`query_history.datasource_id`、`audit_logs.created_at`、`agent_messages.session_id`、`dashboards.share_token` 等）已建索引，启动时自动给老库补建缺失索引；分页总数用 `COUNT(*)` 子查询；表结构变更用 Alembic 迁移（`backend/migrations`，基线 0001）
- **LLM Provider 抽象**：OpenAICompatProvider（OpenAI 官方 + 兼容网关 + Ollama /v1）与 ClaudeProvider 统一 `chat/stream/ping`；未配置 Key 时快速失败提示
- **统一响应**：所有接口返回 `{code, message, data}`，HTTP/校验异常统一处理
- **SSE 事件流**：Agent 对话 `text/event-stream`，事件类型 `session_title / thought / tool / retry / sql / result / text / chart / authorization_required / done / error`
- **语句风险分类**：`services/sql_service.classify_statement` 按首个关键字判定 READ / DML / DDL，并加固会被首个关键字绕过的写法——`WITH … DELETE/UPDATE/INSERT`（跳过 CTE 定义取主动词）、`EXPLAIN ANALYZE`（真会执行，按内层语句定级）、`SELECT … INTO`（Postgres 建表 / MySQL 写文件，升为 DDL）、`FOR UPDATE` / `LOCK IN SHARE MODE`（加锁读，升为 DML）；判定前遮蔽字符串字面量与注释，无法识别时按 DML 兜底。等级决定所需权限（`workspace` / `sql_write` / `sql_ddl`）与是否二次确认
- **写操作确认**：待确认执行落库 `pending_executions`（`execution_id` 主键，5 分钟过期，重启/多副本不丢），确认后二次鉴权、执行并审计
- **定时调度**：FastAPI lifespan 启动调度循环，每分钟扫描到期任务并用条件 UPDATE 认领（多副本只有一个进程执行），线程池执行导出
- **监控指标**：`/metrics` 暴露 Prometheus 指标（REQUEST_COUNT / REQUEST_LATENCY / SQL_EXECUTIONS），路径标签用路由模板避免标签爆炸，支持令牌鉴权与内网限制
- **安全基线**：加密密钥支持环境变量/独立挂载（`DBAGENT_SECRET_KEY`、`DBAGENT_SECRET_KEY_FILE`），默认密钥文件 600 权限且不入库；初始管理员口令可用 `DBAGENT_ADMIN_PASSWORD` 指定，未改默认口令时启动告警

---

## 项目结构

```
backend/
  app/
    main.py             FastAPI 入口（CORS、异常处理、路由注册、SPA 托管、种子数据）
    config.py           路径/常量配置；DBAGENT_DATA_DIR / DBAGENT_AGENT_MAX_TOOL_ROUNDS / DBAGENT_AGENT_SQL_MAX_ATTEMPTS / DBAGENT_DB_POOL_SIZE / DBAGENT_DB_POOL_IDLE_TTL 等环境变量可覆盖
    models.py           SQLAlchemy 模型（16 张表）
    security.py         Fernet 加密、pbkdf2 哈希、token 生成
    permissions.py      权限码、5 个内置角色、鉴权依赖
    adapters/           数据库适配层（SQLite/MySQL/PostgreSQL/Oracle/MongoDB）+ pool.py 只读连接池
    routers/            14 个 API 路由模块（auth/connections/sql/metadata/agent/...）
    services/           业务服务层（sql/agent/connection/export/llm/ssh/audit/schedule）
  tests/                pytest 测试（167 项）
  data/                 运行数据（app.db、demo.db、drivers/、exports/）
  alembic.ini / migrations/   Alembic 迁移配置与脚本（0001 为当前模型基线）
frontend/
  src/
    api/                fetch 封装 + 类型化 API
    stores/             Pinia（auth/connections/settings/workspace/agent）
    router/             路由 + 权限守卫
    views/              页面（Login/SmartQuery/Workspace/Reports/Users/Roles/Settings/Monitor/...）
    components/         组件（SqlEditor/ObjectTree/ResultTable/AgentPanel/ChartCard/...）
scripts/                启动脚本、演示数据初始化、E2E 脚本
docs/                   需求说明书、AI 测试用例、竞赛项目介绍
Dockerfile / docker-compose.yml   多阶段构建 + 一键启动（数据卷 dbagent-data）
```

---

## 快速开始（开发模式）

前置要求：Python 3.12+、Node.js 18+、npm。

```powershell
# 一键启动（自动创建 venv、安装依赖、启动后端 8000 + 前端 5174）
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\start_dev.ps1
```

macOS / Linux（同样适用于 Windows Git Bash）：

```bash
./scripts/start_dev.sh     # 后台启动后端 8000 + 前端 5174，日志见 scripts/.run/
./scripts/stop_dev.sh      # 停止服务；--status 查看状态
```

打开 http://127.0.0.1:5174 使用（如端口被占用：PowerShell 加 `-Port 5175`，shell 脚本加 `--port 5175`）。

### 手动启动

```powershell
# 后端（首次先创建 venv 并安装 backend\requirements.txt）
cd backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# 前端（另开终端）
cd frontend
npm.cmd install
npm.cmd run dev -- --port 5174
```

---

## 生产模式（单端口 8000）

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\start_prod.ps1
```

或手动：`cd frontend; npm.cmd run build` 后，`cd ..\backend; .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000`。

访问 http://127.0.0.1:8000（FastAPI 托管 `frontend/dist` 静态产物，SPA 路由回退 index.html）。

---

## Docker 一键启动

```bash
docker compose up -d --build
# 或：docker build -t db-agent:2.0.0 . && docker run -d -p 8000:8000 -v dbagent-data:/app/data db-agent:2.0.0
```

访问 http://127.0.0.1:8000。数据持久化在 Docker 卷 `dbagent-data`（应用库、演示库、上传驱动、导出文件）。

---

## 默认账户与演示数据

- 默认账户：`admin / admin123`（首次登录后建议修改）
- 内置 5 个角色：管理员 / 技术管理 / 技术查询 / 业务管理 / 业务查询（可在「用户与角色」中自定义）
- 内置演示数据源「本地演示库 (SQLite)」：`users / products / categories / orders / order_logs` 5 张表 + 视图 + 触发器 + 约 100 条订单数据
- 首次启动自动建表并种入：管理员、演示库、演示连接、默认大模型配置（Key 留空）
- 手动重建演示数据：`python scripts/init_demo.py`
- Oracle 演示数据：`python scripts/seed_oracle_bank.py`（可生成银行交易模拟数据）

---

## AI 大模型配置

在「系统设置 → 大模型连接配置」中新增模型（密钥仅加密存储，前端不回显明文）：

- **OpenAI 兼容**（默认 `gpt-4o-mini`）：填写 API Key，可选自定义 `api_base`（支持 OpenAI 官方与兼容网关）
- **Anthropic Claude**：填写 API Key 与模型名
- **Ollama**：填写服务地址（默认 `http://localhost:11434/v1`），本地无需 Key

未配置 Key 时，Agent 会立即返回错误提示，不会等待 SDK 超时。

---

## 测试

```powershell
# 后端单元测试（167 项）
cd backend
.\.venv\Scripts\python.exe -m pytest -q

# 前端类型检查与构建
cd frontend
npm.cmd run build   # 内置 vue-tsc 校验
```

---

## 端口与常见问题

| 服务 | 地址 | 说明 |
|---|---|---|
| 后端 API / 生产页面 | http://127.0.0.1:8000 | 健康检查 `GET /api/health` |
| 开发前端 | http://127.0.0.1:5174 | 代理 `/api` 到 8000 |

- **5173 被占用**：本机常见于其他应用占用 5173，开发脚本默认使用 5174；Vite 代理不受端口影响
- **PowerShell 执行策略**：仓库脚本需 `powershell -NoProfile -ExecutionPolicy Bypass -File ...` 方式运行
- **控制台中文乱码**：Windows PowerShell 5.1 显示乱码是控制台代码页问题，文件均为 UTF-8，不影响功能
- **AI 调用失败**：检查 Key 是否填写、网络是否可达；Ollama 需先 `ollama serve` 并已拉取模型
- **Docker 构建慢**：首次构建需拉取 Node/Python 基础镜像与依赖；数据卷 `dbagent-data` 保留运行数据
