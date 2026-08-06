export class ApiError extends Error {
  code: number;
  constructor(code: number, message: string) {
    super(message);
    this.code = code;
  }
}

export async function request<T>(url: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = { ...(options.headers as Record<string, string> | undefined) };
  if (!(options.body instanceof FormData) && options.body !== undefined) {
    headers["Content-Type"] = "application/json";
  }
  const resp = await fetch(url, { credentials: "include", ...options, headers });
  if (resp.status === 401 && !url.includes("/auth/login") && !url.includes("/auth/me") && !window.location.pathname.startsWith("/login")) {
    window.location.href = "/login";
    throw new ApiError(401, "未登录");
  }
  const ct = resp.headers.get("content-type") || "";
  if (ct.includes("application/json")) {
    const body = await resp.json();
    if (body.code !== 0) throw new ApiError(body.code ?? resp.status, body.message || "请求失败");
    return body.data as T;
  }
  if (!resp.ok) throw new ApiError(resp.status, `请求失败 (${resp.status})`);
  return resp as unknown as T;
}

export const http = {
  get: <T>(url: string) => request<T>(url),
  post: <T>(url: string, body?: unknown) => request<T>(url, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) }),
  put: <T>(url: string, body?: unknown) => request<T>(url, { method: "PUT", body: body === undefined ? undefined : JSON.stringify(body) }),
  del: <T>(url: string) => request<T>(url, { method: "DELETE" }),
};

export async function downloadFile(url: string, body: unknown, filename: string) {
  const resp = await fetch(url, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!resp.ok) {
    let message = `下载失败 (${resp.status})`;
    try {
      const j = await resp.json();
      if (j.message) message = j.message;
    } catch {
      /* ignore */
    }
    throw new ApiError(resp.status, message);
  }
  const blob = await resp.blob();
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  URL.revokeObjectURL(a.href);
}
