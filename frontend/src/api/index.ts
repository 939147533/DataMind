import { downloadFile, http, request } from "./client";
import type { ApiError } from "./client";

export interface PageResult<T> {
  list: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface Connection {
  id: number;
  name: string;
  db_type: string;
  host: string;
  port: number | null;
  username: string;
  has_password: boolean;
  database_name: string;
  ssh_enabled: boolean;
  environment: string;
  status: string;
  description: string;
  created_at?: string;
}

export interface User {
  id: number;
  username: string;
  display_name: string;
  role: string;
  is_active: boolean;
  permissions: string[];
  last_login?: string | null;
  created_at?: string | null;
}

export interface Role {
  id: number;
  code: string;
  name: string;
  description: string;
  permissions: string[];
  is_builtin: boolean;
  user_count: number;
}

export interface RoleMember {
  id: number;
  username: string;
  display_name: string;
  is_active: boolean;
  last_login?: string | null;
}

export const PERMISSION_GROUPS = [
  {
    group: "工作台",
    items: [
      { code: "workspace", name: "SQL 工作台", desc: "访问 SQL 工作台并执行只读查询" },
      { code: "ai_query", name: "智能查询", desc: "自然语言查询数据、导出结果、生成图表" },
      { code: "sql_write", name: "写操作 (DML)", desc: "执行 INSERT/UPDATE/DELETE 等写操作" },
      { code: "sql_ddl", name: "结构变更 (DDL)", desc: "执行 CREATE/ALTER/DROP 等结构变更" },
      { code: "agent", name: "AI Agent", desc: "使用 AI 智能助手" },
    ],
  },
  {
    group: "连接",
    items: [
      { code: "connections", name: "连接管理-查看", desc: "查看数据源连接、测试连接" },
      { code: "connections_manage", name: "连接管理-维护", desc: "新增/编辑/删除数据源连接" },
    ],
  },
  {
    group: "报表",
    items: [
      { code: "reports", name: "报表-查看", desc: "查看图表与仪表盘" },
      { code: "reports_manage", name: "报表-维护", desc: "新增/编辑/删除图表与仪表盘" },
    ],
  },
  {
    group: "系统",
    items: [
      { code: "settings", name: "系统设置", desc: "AI 配置、JDBC 驱动、偏好设置" },
      { code: "audit", name: "审计日志", desc: "查看操作审计日志" },
      { code: "users", name: "用户管理", desc: "管理用户账号" },
      { code: "roles", name: "角色管理", desc: "管理角色与功能权限" },
    ],
  },
];

export interface ColumnInfo {
  name: string;
  data_type: string;
  nullable: boolean;
  default: string | null;
  primary_key: boolean;
  auto_increment: boolean;
  comment: string;
}

export interface AIConfig {
  id: number;
  provider: string;
  has_key: boolean;
  api_base: string;
  model_name: string;
  max_tokens: number;
  temperature: number;
  is_active: boolean;
  is_default: boolean;
}

export interface AgentSession {
  id: number;
  title: string;
  datasource_id: number | null;
  model_config_id: number | null;
  message_count: number;
}

export interface AgentMessage {
  id: number;
  role: string;
  content: string;
  message_type: string;
  created_at?: string;
}

export interface Chart {
  id: number;
  name: string;
  datasource_id: number | null;
  sql_text: string;
  chart_type: string;
  x_column: string;
  y_column: string;
  aggregation: string;
  options: string;
}

export interface Dashboard {
  id: number;
  name: string;
  chart_ids: number[];
  layout: string;
  is_public: boolean;
  share_token: string;
}

export type { ApiError };

// 认证
export const authApi = {
  login: (username: string, password: string) => http.post<{ user: User }>("/api/auth/login", { username, password }),
  logout: () => http.post("/api/auth/logout"),
  me: () => http.get<User>("/api/auth/me"),
};

// 连接
export const connectionApi = {
  list: (params: { search?: string; environment?: string; page?: number; page_size?: number }) => {
    const q = new URLSearchParams();
    if (params.search) q.set("search", params.search);
    if (params.environment) q.set("environment", params.environment);
    q.set("page", String(params.page || 1));
    q.set("page_size", String(params.page_size || 20));
    return http.get<PageResult<Connection>>(`/api/connections?${q}`);
  },
  get: (id: number) => http.get<Connection>(`/api/connections/${id}`),
  create: (data: Record<string, unknown>) => http.post<Connection>("/api/connections", data),
  update: (id: number, data: Record<string, unknown>) => http.put<Connection>(`/api/connections/${id}`, data),
  remove: (id: number) => http.del(`/api/connections/${id}`),
  clone: (id: number) => http.post<Connection>(`/api/connections/${id}/clone`),
  test: (data: Record<string, unknown>) => http.post<{ success: boolean; message: string }>("/api/connections/test", data),
  connect: (id: number) => http.post<{ status: string; schemas: string[] }>(`/api/connections/${id}/connect`),
};

export interface SmartChartConfig {
  chart_type: string;
  title: string;
  x_column: string;
  y_column: string;
  aggregation: string;
}

// SQL
export interface SqlResult {
  need_confirm: boolean;
  operation_type: string;
  columns: string[];
  rows: unknown[][];
  total_rows: number;
  duration_ms: number;
  truncated: boolean;
  message: string;
  affected_rows?: number;
  sql_text?: string;
  preview?: string;
  risk_level?: string;
  execution_id?: string;
  session_id?: number | null;
  status?: string;
}

export const sqlApi = {
  execute: (datasource_id: number, sql: string) =>
    http.post<SqlResult>("/api/sql/execute", { datasource_id, sql, page: 1, page_size: 100, max_rows: 1000 }),
  confirm: (execution_id: string, confirmed: boolean) =>
    http.post<SqlResult>("/api/sql/execute/confirm", { execution_id, confirmed }),
  format: (sql: string) => http.post<{ sql: string }>("/api/sql/format", { sql }),
  history: (params: { datasource_id?: number; page?: number; page_size?: number }) => {
    const q = new URLSearchParams();
    if (params.datasource_id) q.set("datasource_id", String(params.datasource_id));
    q.set("page", String(params.page || 1));
    q.set("page_size", String(params.page_size || 20));
    return http.get<PageResult<SqlHistoryItem>>(`/api/sql/history?${q}`);
  },
};

export interface SqlHistoryItem {
  id: number;
  datasource_id: number | null;
  sql_text: string;
  status: string;
  row_count: number;
  duration_ms: number;
  error_message: string;
  created_at?: string;
}

// 元数据
export const metadataApi = {
  schemas: (dsId: number) => http.get<string[]>(`/api/metadata/${dsId}/schemas`),
  tables: (dsId: number, schema?: string) => http.get<string[]>(`/api/metadata/${dsId}/tables${schema ? `?schema=${encodeURIComponent(schema)}` : ""}`),
  columns: (dsId: number, table: string, schema?: string) =>
    http.get<ColumnInfo[]>(`/api/metadata/${dsId}/tables/${encodeURIComponent(table)}/columns${schema ? `?schema=${encodeURIComponent(schema)}` : ""}`),
  indexes: (dsId: number, table: string) => http.get<unknown[]>(`/api/metadata/${dsId}/tables/${encodeURIComponent(table)}/indexes`),
  ddl: (dsId: number, table: string) => http.get<{ ddl: string }>(`/api/metadata/${dsId}/tables/${encodeURIComponent(table)}/ddl`),
  data: (dsId: number, table: string, page = 1, size = 100) =>
    http.get<{ columns: string[]; rows: unknown[][]; total: number; page: number; page_size: number }>(
      `/api/metadata/${dsId}/tables/${encodeURIComponent(table)}/data?page=${page}&size=${size}`,
    ),
  alter: (dsId: number, table: string, body: { schema_name?: string; changes?: string; ddl?: string }) =>
    http.post<SqlResult>(`/api/metadata/${dsId}/tables/${encodeURIComponent(table)}/alter`, body),
  objects: (dsId: number, kind: string, schema?: string) =>
    http.get<unknown[]>(`/api/metadata/${dsId}/${kind}${schema ? `?schema=${encodeURIComponent(schema)}` : ""}`),
  objectDdl: (dsId: number, kind: string, name: string) => http.get<{ ddl: string }>(`/api/metadata/${dsId}/${kind}/${encodeURIComponent(name)}/ddl`),
  favorites: (dsId: number) => http.get<{ id: number; schema_name: string; table_name: string }[]>(`/api/metadata/${dsId}/favorites`),
  addFavorite: (dsId: number, schema_name: string, table_name: string) =>
    http.post(`/api/metadata/${dsId}/favorites`, { schema_name, table_name }),
  removeFavorite: (dsId: number, table_name: string) => http.del(`/api/metadata/${dsId}/favorites/${encodeURIComponent(table_name)}`),
};

// Agent
export const agentApi = {
  createSession: (data: { datasource_id?: number | null; model_config_id?: number | null; title?: string }) =>
    http.post<{ id: number; title: string }>("/api/agent/sessions", data),
  listSessions: () => http.get<AgentSession[]>("/api/agent/sessions"),
  deleteSession: (id: number) => http.del(`/api/agent/sessions/${id}`),
  messages: (id: number) => http.get<AgentMessage[]>(`/api/agent/sessions/${id}/messages`),
  confirm: (execution_id: string, confirmed: boolean) => http.post<SqlResult>("/api/agent/confirm", { execution_id, confirmed }),
  saveChart: (data: {
    name: string;
    datasource_id?: number | null;
    sql_text?: string;
    chart_type: string;
    x_column: string;
    y_column: string;
    aggregation?: string;
    options?: string;
  }) => http.post<Chart>("/api/agent/charts", data),
};

// AI 配置 / 设置 / 驱动
export const configApi = {
  listAi: () => http.get<AIConfig[]>("/api/config/ai"),
  createAi: (data: Record<string, unknown>) => http.post<AIConfig>("/api/config/ai", data),
  updateAi: (id: number, data: Record<string, unknown>) => http.put<AIConfig>(`/api/config/ai/${id}`, data),
  deleteAi: (id: number) => http.del(`/api/config/ai/${id}`),
  setDefaultAi: (id: number) => http.put(`/api/config/ai/${id}/default`),
  testAi: (data: {
    config_id?: number;
    provider?: string;
    api_key?: string;
    api_base?: string;
    model_name?: string;
    max_tokens?: number;
    temperature?: number;
  }) => http.post<{ success: boolean; message: string; latency_ms?: number; model?: string }>("/api/config/ai/test", data),
  settings: () => http.get<{ values: Record<string, string> }>("/api/config/settings"),
  saveSettings: (values: Record<string, string>) => http.put("/api/config/settings", { values }),
  drivers: () => http.get<Record<string, unknown>[]>("/api/config/drivers"),
  uploadDriver: (form: FormData) =>
    request<Record<string, unknown>>("/api/config/drivers", { method: "POST", body: form }),
  deleteDriver: (id: number) => http.del(`/api/config/drivers/${id}`),
};

// 报表
export const chartApi = {
  list: () => http.get<Chart[]>("/api/charts"),
  create: (data: Record<string, unknown>) => http.post<Chart>("/api/charts", data),
  update: (id: number, data: Record<string, unknown>) => http.put<Chart>(`/api/charts/${id}`, data),
  remove: (id: number) => http.del(`/api/charts/${id}`),
  data: (id: number) => http.get<{ columns: string[]; rows: unknown[][] }>(`/api/charts/${id}/data`),
  dashboards: () => http.get<Dashboard[]>("/api/dashboards"),
  createDashboard: (data: { name: string; chart_ids: number[] }) => http.post<Dashboard>("/api/dashboards", data),
  updateDashboard: (id: number, data: Record<string, unknown>) => http.put<Dashboard>(`/api/dashboards/${id}`, data),
  deleteDashboard: (id: number) => http.del(`/api/dashboards/${id}`),
  shareDashboard: (id: number) => http.post<{ share_token: string; share_url: string }>(`/api/dashboards/${id}/share`),
};

// 审计
export const auditApi = {
  logs: (params: { page?: number; page_size?: number; action_type?: string; status?: string }) => {
    const q = new URLSearchParams();
    q.set("page", String(params.page || 1));
    q.set("page_size", String(params.page_size || 20));
    if (params.action_type) q.set("action_type", params.action_type);
    if (params.status) q.set("status", params.status);
    return http.get<PageResult<AuditItem>>(`/api/audit/logs?${q}`);
  },
};

export interface AuditItem {
  id: number;
  user_id: number | null;
  action_type: string;
  sql_text: string;
  operation_type: string;
  datasource_id: number | null;
  status: string;
  client_ip: string;
  created_at?: string;
}

// 导出
export const exportApi = {
  result: (datasource_id: number, sql: string, format: string) => {
    const query = new URLSearchParams({ format });
    return downloadFile(`/api/export/result?${query}`, { datasource_id, sql }, `export.${format === "excel" ? "xlsx" : format}`);
  },
  database: async (datasource_id: number, format: string, tables?: string[]) => {
    const resp = await fetch(`/api/export/database?format=${format}`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ datasource_id, tables: tables || null, include_ddl: true }),
    });
    const body = await resp.json();
    return body.data as { task_id: string };
  },
  poll: async (taskId: string) => http.get<{ status: string; download_url?: string; file_name?: string; error?: string }>(`/api/export/database/status/${taskId}`),
};
// 用户管理
export const userApi = {
  list: (params: { search?: string; role?: string; page?: number; page_size?: number }) => {
    const q = new URLSearchParams();
    if (params.search) q.set("search", params.search);
    if (params.role) q.set("role", params.role);
    q.set("page", String(params.page || 1));
    q.set("page_size", String(params.page_size || 20));
    return http.get<PageResult<User>>(`/api/users?${q}`);
  },
  get: (id: number) => http.get<User>(`/api/users/${id}`),
  create: (data: Record<string, unknown>) => http.post<User>("/api/users", data),
  update: (id: number, data: Record<string, unknown>) => http.put<User>(`/api/users/${id}`, data),
  remove: (id: number) => http.del(`/api/users/${id}`),
  resetPassword: (id: number, password: string) => http.post(`/api/users/${id}/reset-password`, { password }),
};

// 角色管理
export const roleApi = {
  list: () => http.get<Role[]>("/api/roles"),
  get: (id: number) => http.get<Role>(`/api/roles/${id}`),
  create: (data: Record<string, unknown>) => http.post<Role>("/api/roles", data),
  update: (id: number, data: Record<string, unknown>) => http.put<Role>(`/api/roles/${id}`, data),
  remove: (id: number) => http.del(`/api/roles/${id}`),
  users: (id: number) => http.get<RoleMember[]>(`/api/roles/${id}/users`),
  setUsers: (id: number, user_ids: number[]) => http.put(`/api/roles/${id}/users`, { user_ids }),
};