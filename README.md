# 数据库 Agent Web 应用（DB Agent）

基于需求说明书 V2.0 的全量实现（P0 + P1 + P2）：一个前后端分离的数据库查询与 AI Agent 工作台。
支持连接管理、SQL 工作台、元数据管理、AI 自然语言查询（SSE 流式）、报表可视化、系统管理与审计日志。

## 功能特性

- **连接管理**：SQLite / MySQL / PostgreSQL / Oracle / OceanBase / GoldenDB / MongoDB，支持连接测试、克隆、编辑、环境标签。
- **SQL 工作台**：多 Tab CodeMirror 6 编辑器、对象树（表/视图/索引/触发器）、结果表格分页/排序/列宽/导出、执行历史。
- **SQL 安全执行协议**：SELECT/SHOW/DESC/EXPLAIN 自动执行；写操作（INSERT/UPDATE/DELETE）需确认并返回影响行数预估；DDL 标记高危需二次确认；全部操作记录审计日志。
- **AI Agent**：自然语言→SQL，SSE 流式返回思考过程/SQL/结果；写操作授权弹窗；会话多轮上下文；提供 SQL 解释与优化端点。
- **报表**：柱状/折线/饼图 + 仪表盘，支持分享令牌。
- **系统管理**：AI 模型配置（OpenAI 兼容 / Claude / Ollama，Key 加密存储）、JDBC 驱动上传、偏好设置、审计日志。
- **安全**：Fernet 加密敏感信息、pbkdf2 密码哈希、Session/Cookie 认证、统一 `{code,message,data}` 响应。

## 技术栈

- 后端：Python 3.12 + FastAPI + SQLAlchemy 2.0（async）+ SQLite（应用库）
- 前端：Vue 3 + TypeScript + Vite + Pinia + Naive UI + CodeMirror 6 + ECharts
- 部署：Docker 多阶段构建（单端口 8000）/ 本地开发模式（8000 + Vite）

## 目录结构

```
backend/            FastAPI 应用（app 包、适配器、服务、路由、测试）
frontend/           Vue 3 前端（src 源码、dist 构建产物）
scripts/            启动脚本与初始化脚本
Dockerfile          多阶段构建（前端构建 + 后端运行）
docker-compose.yml  一键启动（端口 8000）
需求说明书V2.0.md    需求文档
```

## 快速开始（开发模式）

前置要求：Python 3.11+、Node.js 18+、npm。

```powershell
# 一键启动（自动创建 venv、安装依赖、启动后端 8000 + 前端 5174）
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\start_dev.ps1
```

打开 http://127.0.0.1:5174 使用。

> 说明：默认使用 5174 端口，避免与本机 5173 上的其他应用（如 DataMind）冲突；
> 如需换端口：`-File scripts\start_dev.ps1 -Port 5175`。

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

## 生产模式（单端口 8000）

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\start_prod.ps1
# 或手动：
cd frontend; npm.cmd run build
cd ..\backend; .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

访问 http://127.0.0.1:8000（FastAPI 直接托管 `frontend/dist` 静态产物，SPA 路由回退到 index.html）。

## Docker 一键启动

```bash
docker compose up -d --build
# 或: docker build -t db-agent:2.0.0 . && docker run -d -p 8000:8000 -v dbagent-data:/app/data db-agent:2.0.0
```

访问 http://127.0.0.1:8000。数据持久化在 Docker 卷 `dbagent-data`（应用库、演示库、上传的驱动、导出文件）。

## 默认账户与演示数据

- 默认账户：`admin / admin123`（首次登录后建议在系统设置中修改密码）
- 内置演示数据源「本地演示库 (SQLite)」：`users / products / categories / orders / order_logs` 5 张表 + 视图 + 触发器 + 约 100 条订单数据
- 首次启动自动建表并种入：管理员、演示库、演示连接、默认 OpenAI 兼容 AI 配置（Key 留空）
- 手动重建演示数据：`python scripts/init_demo.py`

## AI Agent 配置

在「系统设置 → AI 配置」中新增模型（密钥仅加密存储，前端不回显明文）：

- **OpenAI 兼容**（默认 `gpt-4o-mini`）：填写 API Key，可选自定义 `api_base`（支持 OpenAI 官方与兼容网关）
- **Anthropic Claude**：填写 API Key 与模型名
- **Ollama**：填写服务地址（默认 `http://localhost:11434/v1`），本地无需 Key

未配置 Key 时，Agent 会立即返回错误提示，不会等待 SDK 超时。

## 测试

```powershell
# 后端单元测试（56 项，覆盖率约 62%）
cd backend
.\.venv\Scripts\python.exe -m pytest -q

# 前端类型检查与构建
cd frontend
npm.cmd run build   # 内置 vue-tsc 校验（package.json 可加 "type-check": "vue-tsc --noEmit"）
```

## 端口与常见问题

| 服务 | 地址 | 说明 |
| --- | --- | --- |
| 后端 API / 生产页面 | http://127.0.0.1:8000 | 健康检查 `/api/health` |
| 开发前端 | http://127.0.0.1:5174 | 代理 `/api` 到 8000 |

- **5173 被占用**：本机常见于 DataMind 等应用占用 5173，开发脚本默认改用 5174；Vite 代理不受端口影响。
- **PowerShell 执行策略**：本仓库脚本均需 `powershell -NoProfile -ExecutionPolicy Bypass -File ...` 方式运行。
- **控制台中文乱码**：Windows PowerShell 5.1 显示乱码是控制台代码页问题，文件均为 UTF-8，不影响功能。
- **AI 调用失败**：检查 Key 是否填写、网络是否可达；Ollama 需先 `ollama serve` 并已拉取模型。
- **Docker 构建慢**：首次构建需拉取 Node/Python 基础镜像与依赖；数据卷 `dbagent-data` 保留运行数据。
