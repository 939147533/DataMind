import { chromium } from "playwright";

const BASE = "http://127.0.0.1:8000";
const SHOT_DIR = "C:\\Users\\93914\\AppData\\Local\\Temp";
let step = 0;
let failures = 0;
const errors = [];
const TEST_USER = "e2e_user_" + String(Date.now() % 100000);
const TEST_PWD = "e2e123456";

async function shot(page, name) {
  step += 1;
  const p = SHOT_DIR + "\\e2e_roles_" + String(step).padStart(2, "0") + "_" + name + ".png";
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
  await page.goto(BASE, { waitUntil: "domcontentloaded", timeout: 30000 });
  await page.waitForSelector(".login-card", { timeout: 20000 });
  await page.getByPlaceholder("admin", { exact: true }).fill(u);
  await page.getByPlaceholder("admin123", { exact: true }).fill(pwd);
  await page.getByRole("button", { name: "登 录" }).click();
  await page.waitForURL("**/workspace", { timeout: 20000 });
  await page.waitForSelector(".workspace-view", { timeout: 20000 });
}

async function menuClick(label) {
  await page.locator(".n-menu-item-content", { hasText: label }).first().click();
}

async function apiCleanup() {
  try {
    const api = await context.request;
    const login = await api.post(BASE + "/api/auth/login", { data: { username: "admin", password: "admin123" } });
    const setCookie = login.headers()["set-cookie"] || "";
    const cookie = setCookie.split(";")[0];
    if (!cookie) return;
    const headers = { Cookie: cookie };
    // 删除测试用户
    const users = await (await api.get(BASE + "/api/users?search=" + TEST_USER + "&page_size=50", { headers })).json();
    for (const u of users.data.list) {
      if (u.username === TEST_USER) await api.delete(BASE + "/api/users/" + u.id, { headers });
    }
    // 恢复 tech_query 默认权限
    const roles = await (await api.get(BASE + "/api/roles", { headers })).json();
    const tq = roles.data.find((r) => r.code === "tech_query");
    if (tq) {
      const perms = tq.permissions.filter((p) => p !== "settings");
      await api.put(BASE + "/api/roles/" + tq.id, { data: { permissions: perms }, headers });
    }
    console.log("cleanup done");
  } catch (e) {
    console.log("cleanup failed:", e.message);
  }
}

try {
  // 1. 管理员登录
  await login("admin", "admin123");
  check("管理员登录进入工作台", true);
  await shot(page, "admin-workspace");

  // 2. 菜单含 用户管理/角色管理
  await page.waitForSelector('.n-menu-item-content:has-text("用户管理")', { timeout: 10000 });
  await page.waitForSelector('.n-menu-item-content:has-text("角色管理")', { timeout: 10000 });
  check("菜单显示用户管理/角色管理", true);

  // 3. 用户管理：新增用户
  await menuClick("用户管理");
  await page.waitForSelector('text=＋ 新增用户', { timeout: 15000 });
  check("用户管理页渲染", true);
  await shot(page, "users-page");
  await page.getByRole("button", { name: "＋ 新增用户" }).click();
  await page.locator(".n-modal").getByPlaceholder("登录账号").fill(TEST_USER);
  await page.locator(".n-modal").getByPlaceholder("显示名称（留空默认用户名）").fill("E2E测试用户");
  await page.locator(".n-modal").getByPlaceholder("至少 4 位（默认 123456）").fill(TEST_PWD);
  await page.locator(".n-modal").getByRole("button", { name: "保存" }).click();
  await page.waitForSelector(".n-data-table tr:has-text('" + TEST_USER + "')", { timeout: 15000 });
  check("创建用户出现在列表", true);
  await shot(page, "users-created");

  // 4. 角色管理：查看 技术查询 角色权限
  await menuClick("角色管理");
  await page.waitForSelector('text=＋ 新增角色', { timeout: 15000 });
  check("角色管理页渲染", true);
  await shot(page, "roles-page");
  await page.locator(".n-data-table tbody tr", { hasText: "技术查询" }).first().click();
  await page.waitForSelector(".perm-items", { timeout: 10000 });
  const permCount = await page.locator(".perm-items .n-checkbox").count();
  check("技术查询权限项渲染", permCount >= 6, "count=" + permCount);
  await shot(page, "roles-perms");

  // 5. 勾选 系统设置 权限并保存
  const settingsCb = page.locator(".perm-items .n-checkbox", { hasText: "系统设置" }).first();
  const settingsChecked = await settingsCb.locator("input").isChecked().catch(() => false);
  if (!settingsChecked) await settingsCb.click();
  await page.getByRole("button", { name: "保存权限" }).click();
  await page.getByText("权限已保存").first().waitFor({ timeout: 15000 });
  check("保存角色权限成功", true);

  // 6. 角色成员：确认新用户在成员列表中
  await page.waitForTimeout(1200);
  const memberItem = page.locator(".member-box .n-checkbox", { hasText: TEST_USER }).first();
  const memberExists = (await memberItem.count()) > 0;
  const memberChecked = memberExists ? await memberItem.locator("input").isChecked().catch(() => false) : false;
  check("新用户在角色成员列表", memberExists);
  if (memberExists && !memberChecked) await memberItem.click();
  if (memberExists) {
    await page.getByRole("button", { name: "保存成员" }).click();
    await page.getByText("成员已保存").first().waitFor({ timeout: 15000 });
    check("保存角色成员成功", true);
  }
  await shot(page, "roles-members");

  // 7. 登出，用新用户登录
  await page.locator(".topbar-actions .n-button", { hasText: "管理员" }).first().click();
  await page.waitForTimeout(400);
  await page.locator(".n-dropdown-option", { hasText: "退出登录" }).first().click();
  await page.waitForSelector(".login-card", { timeout: 15000 });
  await login(TEST_USER, TEST_PWD);
  check("新用户登录进入工作台", true);

  // 8. 菜单权限过滤
  const menuText = await page.locator(".n-menu").innerText();
  check("新用户可见系统设置（权限已生效）", menuText.includes("系统设置"), menuText.slice(0, 60));
  check("新用户不可见用户管理", !menuText.includes("用户管理"));
  check("新用户不可见角色管理", !menuText.includes("角色管理"));
  await shot(page, "limited-menu");

  // 9. 新用户可访问系统设置
  await menuClick("系统设置");
  await page.waitForSelector('text=＋ 新增 AI 配置', { timeout: 15000 });
  check("新用户可访问系统设置", true);

  // 10. 新用户只读查询
  await menuClick("SQL 工作台");
  await page.waitForSelector(".workspace-view", { timeout: 15000 });
  await page.locator(".n-base-selection").first().click();
  await page.locator(".n-base-select-option", { hasText: "本地演示库" }).first().click();
  await page.waitForTimeout(800);
  await page.locator(".cm-content").click();
  await page.keyboard.press("ControlOrMeta+a");
  await page.keyboard.type("SELECT COUNT(*) AS c FROM users;", { delay: 5 });
  await page.getByRole("button", { name: "▶ 执行" }).click();
  await page.waitForTimeout(2200);
  const resultText = await page.locator(".result-table").innerText().catch(() => "");
  check("新用户只读查询成功", resultText.includes("共"), resultText.slice(0, 60));
  await shot(page, "limited-sql");

  // 11. 新用户 DDL 被权限拦截
  await page.locator(".cm-content").click();
  await page.keyboard.press("ControlOrMeta+a");
  await page.keyboard.type("CREATE TABLE e2e_deny(id INTEGER);", { delay: 5 });
  await page.getByRole("button", { name: "▶ 执行" }).click();
  await page.waitForTimeout(2200);
  const alertText = await page.locator(".result-table .n-alert").innerText().catch(() => "");
  check("DDL 被权限拦截提示", alertText.includes("无权限"), alertText.slice(0, 60));
  await shot(page, "limited-ddl-denied");

  console.log("\n===== ROLES E2E SUMMARY =====");
  console.log("test user:", TEST_USER);
  console.log("failures:", failures);
  console.log("page errors:", errors.length ? errors.slice(0, 5) : "none");
} catch (e) {
  failures += 1;
  console.log("E2E EXCEPTION:", e.message);
  await shot(page, "exception");
} finally {
  await apiCleanup();
  await browser.close();
  if (failures > 0) throw new Error("E2E failures: " + failures);
  console.log("ALL PASS");
}