# AI 查询时序说明

> 配套图：`docs/AI查询时序图.svg`
> 入口：`POST /api/agent/chat`（需 `agent` 或 `ai_query` 权限，返回 `text/event-stream`）
> 主要代码：`backend/app/services/agent_service.py:308-533`、`backend/app/routers/agent.py:53-70`

---

## 一、参与者与职责

| 角色 | 职责 |
|---|---|
| **前端 Vue** | `SmartQueryView` + `stores/agent.ts`：发请求、逐行解析 SSE、渲染气泡、写操作弹确认框 |
| **Agent 服务** | `agent_service.agent_chat`：编排上下文装配 → LLM 调用 → 工具循环 → SQL 执行 → 落库 |
| **LLM Provider** | `services/llm_providers.py`：OpenAI 兼容 / Claude，提供 `chat(json_mode)` 与 `stream` |
| **SQL 服务** | `sql_service.execute_sql`：**唯一执行入口**，负责分类 → 鉴权 → 审计 → 执行 |
| **适配器 / 目标库** | `BaseDBAdapter` 子类；驱动全是同步实现，一律经 `asyncio.to_thread` 离开事件循环 |

---

## 二、主链路：一次只读查询

### 1. 请求进入与落库

前端把**当前数据源**随每次请求一起发出（`datasource_id` 不是建会话时定死的）：

```
POST /api/agent/chat
body: { session_id, datasource_id, model_config_id, message }
```

后端顺序做三件事：

1. **解析数据源** —— 优先用请求里的 `datasource_id`，缺省才回退 `session.datasource_id`（`agent_service.py:318-322`）；
2. **解析模型配置** —— 请求的 `model_config_id` → 会话绑定的 → 默认配置 → 任一启用中的配置，逐级回退（`resolve_model_config`）。全都取不到则直接返回 `error` + `done`；
3. **落库用户消息** —— 写入 `agent_messages`，`message_count` 加一；**若是本会话第一条消息**，用问题前 20 字生成会话标题，并向前端推一个 `session_title` 事件。

### 2. 上下文装配

这一步决定了模型「看到什么」，是整条链路最关键的环节（`agent_service.py:348-356`）：

| 片段 | 来源 | 说明 |
|---|---|---|
| `db_type` + `dialect_hint` | 适配器的**类属性** | 每个库一份方言提示，如 Oracle 会明确写「不支持 LIMIT，用 FETCH FIRST N ROWS ONLY」 |
| `schema` | `adapter.schema_summary()`，截断 8000 字 | 表结构摘要，与数据源同源 |
| `few_shots` | `sql_examples.build_few_shot_block`，取 top 3 | **按数据源分桶**的历史成功 SQL，按提问相似度、表名重合度、执行频次加权排序 |
| 历史消息 | `_load_history`，最近 10 条 | 只取 `message_type` 为 `text` / `sql` 的消息，每条截断 2000 字 |

四者填进 `SYSTEM_TEMPLATE`，再与历史、当前问题一起交给 `build_messages` 组装成消息数组。

> **注意**：`schema_summary()` 是阻塞的目标库调用，通过 `asyncio.to_thread` 执行；失败时**静默降级**为「（Schema 获取失败）」且 `dialect_hint` 置空（详见优化清单 A2）。

### 3. 首轮 LLM 推理（第 ① 次调用）

`_chat_json_with_retry` 以 `json_mode=True` 调用模型，要求返回严格 JSON：

```json
{ "thought": "推理过程", "sql": "要执行的 SQL", "answer": "无需 SQL 时的直接回答", "chart": { ... } }
```

**重试策略**：空响应、非 JSON、`LLMError` 等瞬时失败会自动重试，最多 3 次，每次间隔 1 秒。

### 4. 工具调用循环（≤ 3 轮）

如果模型返回的 JSON 里带 `tool` 字段且取值属于 `list_tables / get_columns / sample_data / explain`，就进入工具循环：

```
模型请求工具 → Agent 执行工具 → 把结果追加进消息 → 模型继续推理
```

- 工具执行走 `asyncio.to_thread(_run_tool)`，**直接 `build_adapter` 调适配器，不经过 SQL 服务层** —— 因为工具只做只读元数据查询，没有 DML/DDL 风险，无需分类鉴权；
- 每轮都向前端推一个 `tool` 事件，界面显示「🔧 工具名：结果」；
- 轮数上限 `AGENT_MAX_TOOL_ROUNDS`（默认 3）。**跑满仍未收敛**则推 `error`「工具调用轮次过多」并结束。

### 5. 输出判定与 SQL 分类

模型最终给出 `thought` / `sql` / `answer` 后：

- **无 SQL** → 直接把 `answer` 作为 `text` 事件返回，落库助手消息、写审计（`success`），结束；
- **有 SQL** → `split_statements` 拆分后用 `classify_statement` 逐条定级，取最高等级：

| 等级 | 权限要求 | 是否需确认 |
|---|---|---|
| `READ` | `workspace` 或 `ai_query` | 免确认，直接执行 |
| `DML` | `sql_write` | 需确认 |
| `DDL` | `sql_ddl` | 需确认 |

随即推 `sql` 事件（带 `operation_type` 与 `need_confirm`）。

### 6. 执行（READ 路径）

调用 `sql_service.execute_sql(db, ds, sql, user_id, client_ip, session_id)` —— 这是**全系统唯一允许执行用户 SQL 的入口**，内部完成分类、鉴权、审计与执行。

**SQL 自动修正**：执行失败时最多尝试 `AGENT_SQL_MAX_ATTEMPTS`（默认 3）次，但**只有 HTTP 400（SQL 自身语法/对象错误）才值得让模型修正**；鉴权失败、连接失败等一律 break，不做无意义重试。修正时推 `retry` 事件，模型给出新 SQL 后再推一次 `sql`。

成功后依次产出：

1. `result` 事件 —— 列、行、总行数、耗时、SQL 文本（**结果集截断**：最多 100 行、50 列）；
2. `chart` 事件 —— 若模型输出了合法图表配置（`_parse_chart` 校验 type/x_column/y_columns/aggregation）；
3. `text` 事件 —— **第 ③ 次 LLM 调用**，用 `SUMMARY_TEMPLATE` 把结果交给模型做流式总结，逐 token 推送。

最后落库：`sql` 消息 + `text` 消息（有图表再加一条 `chart` 消息），写审计，推 `done`。

---

## 三、写操作分支（DML / DDL）

与 READ 的分岔点在「需不需要用户确认」：

1. `execute_sql` 不直接执行，而是落一条 `pending_executions` 记录（5 分钟有效），返回 `need_confirm` + `execution_id`；
2. Agent 推 `authorization_required` 事件，带 `execution_id`、`sql_text`、`operation_type`、`risk_level`、`preview`；
3. 前端弹确认框（`ConfirmExecModal`），用户确认后调 `POST /api/agent/confirm`（需 `agent` 权限）；
4. 后端 `confirm_execution` **再查一次权限**（防 TOCTOU：防止「生成待确认 → 权限被降级 → 仍能执行」），然后执行、写审计、记录一次性消费。

> 记录落库而非放内存，所以**重启、多副本下确认都不丢**。

---

## 四、异常与边界

| 场景 | 行为 |
|---|---|
| 未配置可用模型 | 推 `error` + `done`，不进入后续流程 |
| LLM 缺少 Key | `provider.validate()` 快速失败，**不等待 SDK 超时** |
| LLM 调用/解析失败 | 写审计（`failed`），推 `error` + `done` |
| 工具轮次超限 | 推 `error`「工具调用轮次过多」+ `done` |
| Schema 拉取失败 | **静默降级**为无表结构 + 无方言约束，仍继续生成 SQL（见优化清单 A2） |
| SQL 执行失败（400） | 最多修正 3 次；非 400 不重试 |
| SQL 执行失败（重试耗尽） | 推 `error` + `done` |
| 鉴权被拒 | 写审计（`denied`）后抛错，不重试 |
| 结果总结失败 | 结果照常返回，`text` 降级为「（结果已返回，但总结失败：…）」 |

---

## 五、SSE 事件清单

| 事件 | 时机 |
|---|---|
| `session_title` | 会话首条消息，标题生成后 |
| `thought` | 模型的推理过程 |
| `tool` | 每次工具调用返回结果 |
| `retry` | SQL 执行失败、即将让模型修正 |
| `sql` | 生成/修正后的 SQL（含 `operation_type`、`need_confirm`） |
| `result` | 查询结果集（含 `truncated` 标记） |
| `chart` | 图表配置 |
| `text` | 流式文本（直接回答或结果总结），逐 chunk 推送 |
| `authorization_required` | 写操作待确认 |
| `done` | 本次问答结束 |
| `error` | 各类错误 |

> 前端 `stores/agent.ts` 还保留了一个 `execution_result` 分支，但后端 `agent_chat` **从不发出该事件** —— 确认后的结果是通过 `/api/agent/confirm` 的 JSON 响应回填的，该分支目前是死代码。

---

## 六、关键常量与截断策略

| 常量 | 默认值 | 作用 |
|---|---|---|
| `AGENT_MAX_TOOL_ROUNDS` | 3 | 工具调用轮数上限 |
| `AGENT_SQL_MAX_ATTEMPTS` | 3 | READ 查询最大执行次数（含首次，即最多修正 2 次） |
| Schema 摘要截断 | 8000 字 | `_schema_info` |
| 历史消息 | 最近 10 条 / 每条 2000 字 | `_load_history` |
| few-shot 示例 | 3 条 | `build_few_shot_block` |
| 结果集截断 | 100 行 / 50 列 | `_truncate_result` |
| 待确认有效期 | 5 分钟 | `EXECUTION_CONFIRM_TIMEOUT` |
| 会话 TTL | 24 小时 | `SESSION_TTL_SECONDS` |

---

## 七、一段话讲清（汇报口径）

> 用于向领导口头讲解，一段读完即可。

用户在智能查询页输入一句中文问题，系统会把当前选中的数据源、数据库方言、表结构摘要和历史查询样例一起装配给大模型；模型如果觉得信息不够，可以主动调用工具去查表清单、看表结构或采样数据，最多往返三轮，最终生成 SQL。SQL 生成后并不直接执行——服务层先按语句类型判定风险：只读查询免确认直接执行，改数据或改结构的语句则必须先落一条待确认记录，由用户确认并再次校验权限后才执行，且全程留痕审计。执行结果返回后，系统再让模型做一次流式总结，连同数据表格与图表一并呈现给用户。整条链路可以概括为「模型负责理解与生成、系统负责把关与执行」：既让不会写 SQL 的业务人员用自然语言就能查数，也保证任何写操作都处在权限与确认的双重约束之下。

---

*创建：2026-10-16 · 依据代码核实，非文档转述*
