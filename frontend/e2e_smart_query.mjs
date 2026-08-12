import { chromium } from "playwright";

const BASE = "http://127.0.0.1:8000";
const SHOT_DIR = "C:\\Users\\93914\\AppData\\Local\\Temp";
let step = 0;
let failures = 0;
const errors = [];
const BIZ_USER = "sq_biz_" + String(Date.now() % 100000);
const BIZ_PWD = "e2e123456";

async function shot(page, name) {
  step += 1;
  const p = SHOT_DIR + "\\e2e_sq_" + String(step).padStart(2, "0") + "_" + name + ".png";
  try { await page.screenshot({ path: p }); } catch (e) { console.log("shot fail:", name, e.message); }
  console.log("shot:", p);
}

function check(name, cond, extra = "") {
  if (cond) console.log("PASS:", name);
  else { console.log("FAIL:", name, extra); failures += 1; }
}

const browser = await chromium.launch({ channel: "chrome", headless: true });
const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const page = await context.newPage();
page.on("pageerror", (e) => errors.push("pageerror: " + e.message));

async function login(u, pwd) {
  await context.clearCookies();
  await page.goto(BASE, { waitUntil: "domcontentloaded", timeout: 30000 });
  await page.waitForSelector(".login-card", { timeout: 20000 });
  await page.getByPlaceholder("admin", { exact: true }).fill(u);
  await page.getByPlaceholder("admin123", { exact: true }).fill(pwd);
  await page.getByRole("button", { name: "登 录" }).click();
}

async function logout() {
  await page.locator(".topbar-actions .n-button").last().click();
  await page.waitForTimeout(400);
  await page.locator(".n-dropdown-option", { hasText: "退出登录" }).first().click();
  await page.waitForSelector(".login-card", { timeout: 15000 });
}

async function menuClick(label) {
  await page.locator(".n-menu-item-content", { hasText: label }).first().click();
}

async function apiAdmin() {
  const api = await context.request;
  const login = await api.post(BASE + "/api/auth/login", { data: { username: "admin", password: "admin123" } });
  const setCookie = login.headers()["set-cookie"] || "";
  const cookie = setCookie.split(";")[0];
  return { api, headers: { Cookie: cookie } };
}

try {
  // 0. 管理员 API：确认权限含 ai_query
  {
    const { api, headers } = await apiAdmin();
    const me = await (await api.get(BASE + "/api/auth/me", { headers })).json();
    const perms = me.data.permissions || [];
    check("admin 权限含 ai_query", perms.includes("*") || perms.includes("ai_query"), JSON.stringify(perms));

    // 创建业务查询用户
    const users = await (await api.get(BASE + "/api/users?search=" + BIZ_USER + "&page_size=50", { headers })).json();
    for (const u of users.data.list) {
      if (u.username === BIZ_USER) await api.delete(BASE + "/api/users/" + u.id, { headers });
    }
    const created = await api.post(BASE + "/api/users", {
      data: { username: BIZ_USER, password: BIZ_PWD, display_name: "业务测试", role: "biz_query", is_active: true },
      headers,
    });
    check("创建业务查询用户", created.status() === 200, String(created.status()));
  }

  // 1. 管理员登录默认进入智能查询
  await login("admin", "admin123");
  await page.waitForURL("**/smart-query", { timeout: 20000 });
  await page.waitForSelector(".smart-query-view", { timeout: 20000 });
  check("管理员登录默认进入智能查询", true);
  await shot(page, "admin-smart-query");

  // 2. 菜单含 智能查询
  await page.waitForSelector('.n-menu-item-content:has-text("智能查询")', { timeout: 10000 });
  check("菜单显示智能查询", true);

  // 3. 页面渲染：欢迎语 / 示例 / 数据源
  await page.waitForSelector('.sq-empty-title:has-text("你好")', { timeout: 10000 });
  check("智能查询欢迎语渲染", true);
  const exampleCount = await page.locator(".sq-examples .n-tag").count();
  check("示例问题渲染", exampleCount >= 3, "count=" + exampleCount);
  await page.waitForSelector('.sq-toolbar :text("本地演示库")', { timeout: 15000 });
  check("数据源下拉已加载并默认选中演示库", true);

  // 4. 点击示例自动发送自然语言（未配置 AI Key 时走错误分支，验证 SSE 管道）
  await page.locator(".sq-examples .n-tag").first().click();
  await page.waitForSelector(".sq-messages .msg.user", { timeout: 15000 });
  check("示例点击后发送用户消息", true);
  await page.waitForSelector(".sq-messages .msg.assistant", { timeout: 30000 });
  check("发送后出现助手消息（SSE 管道正常）", true);
  await shot(page, "admin-chat-response");

  // 5. SQL 工作台仍然可用
  await menuClick("SQL 工作台");
  await page.waitForSelector(".workspace-view", { timeout: 20000 });
  check("SQL 工作台可访问", true);

  // 6. 业务查询用户：默认进入智能查询；菜单有智能查询和 SQL 工作台，无用户/角色管理
  await logout();
  await login(BIZ_USER, BIZ_PWD);
  await page.waitForURL("**/smart-query", { timeout: 20000 });
  await page.waitForSelector(".smart-query-view", { timeout: 20000 });
  check("业务用户默认进入智能查询", true);
  await page.waitForSelector('.n-menu-item-content:has-text("SQL 工作台")', { timeout: 10000 });
  check("业务用户菜单含 SQL 工作台（未写死移除 workspace）", true);
  const hasUsers = await page.locator('.n-menu-item-content:has-text("用户管理")').count();
  const hasRoles = await page.locator('.n-menu-item-content:has-text("角色管理")').count();
  check("业务用户看不到用户管理/角色管理", hasUsers === 0 && hasRoles === 0, "users=" + hasUsers + " roles=" + hasRoles);
  await shot(page, "biz-smart-query");

  // 7. 业务用户也可进入 SQL 工作台
  await menuClick("SQL 工作台");
  await page.waitForSelector(".workspace-view", { timeout: 20000 });
  check("业务用户可访问 SQL 工作台", true);

  // 8. 直接访问 /users 被守卫拦截
  await page.goto(BASE + "/users", { waitUntil: "domcontentloaded" });
  await page.waitForURL("**/smart-query", { timeout: 20000 });
  check("业务用户访问用户管理被拦截回退首页", true);
} catch (e) {
  console.log("E2E ERROR:", e.message);
  failures += 1;
} finally {
  // 清理测试用户
  try {
    const { api, headers } = await apiAdmin();
    const users = await (await api.get(BASE + "/api/users?search=" + BIZ_USER + "&page_size=50", { headers })).json();
    for (const u of users.data.list) {
      if (u.username === BIZ_USER) await api.delete(BASE + "/api/users/" + u.id, { headers });
    }
    console.log("cleanup done");
  } catch (e) {
    console.log("cleanup failed:", e.message);
  }
  if (errors.length) console.log("PAGE ERRORS:", errors.join(" | "));
  await browser.close();
}

console.log(failures === 0 ? "ALL PASS" : failures + " FAILURES");
process.exit(failures === 0 ? 0 : 1);
