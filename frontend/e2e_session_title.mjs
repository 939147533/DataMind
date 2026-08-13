import { chromium } from "playwright";

const BASE = "http://127.0.0.1:8000";
const SHOT_DIR = "C:\\Users\\93914\\AppData\\Local\\Temp";
let step = 0;
let failures = 0;
const errors = [];

async function shot(page, name) {
  step += 1;
  const p = SHOT_DIR + "\\e2e_title_" + String(step).padStart(2, "0") + "_" + name + ".png";
  try { await page.screenshot({ path: p }); } catch (e) { console.log("shot fail:", name, e.message); }
  console.log("shot:", p);
}

function check(name, cond, extra) {
  if (cond) console.log("PASS:", name);
  else { console.log("FAIL:", name, extra || ""); failures += 1; }
}

const browser = await chromium.launch({ channel: "chrome", headless: true });
const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const page = await context.newPage();
page.on("pageerror", (e) => errors.push("pageerror: " + e.message));

let createdSessionId = null;

async function apiLogin() {
  const api = await context.request;
  const resp = await api.post(BASE + "/api/auth/login", { data: { username: "admin", password: "admin123" } });
  const cookie = (resp.headers()["set-cookie"] || "").split(";")[0];
  return { api, cookie };
}

try {
  // 1. 登录进入智能查询
  await page.goto(BASE, { waitUntil: "domcontentloaded", timeout: 30000 });
  await page.waitForSelector(".login-card", { timeout: 20000 });
  await page.getByPlaceholder("admin", { exact: true }).fill("admin");
  await page.getByPlaceholder("admin123", { exact: true }).fill("admin123");
  await page.getByRole("button", { name: "登 录" }).click();
  await page.waitForFunction(() => !location.pathname.includes("/login"), null, { timeout: 20000 });
  await page.waitForSelector(".smart-query-view", { timeout: 20000 });
  check("智能查询页渲染", true);

  // 2. 会话下拉显示问题概括标题（回填生效，不再全是新对话）
  const sessionSelect = page.locator(".sq-toolbar .n-select").nth(2);
  await sessionSelect.click();
  await page.waitForSelector(".n-base-select-option", { timeout: 15000 });
  const optionTexts = await page.locator(".n-base-select-option").allInnerTexts();
  const hasBackfilled = optionTexts.some((t) => t.indexOf("新对话") < 0 && t.trim().length > 0);
  check("会话列表包含问题概括标题", hasBackfilled, optionTexts.slice(0, 5).join(" / "));
  await page.keyboard.press("Escape");
  await page.waitForTimeout(400);
  await shot(page, "sessions-loaded");

  // 3. 新建对话 → 占位标题为新对话
  await page.getByRole("button", { name: "新建对话" }).click();
  await page.waitForFunction(() => {
    const sel = document.querySelectorAll(".sq-toolbar .n-select")[2];
    const el = sel ? sel.querySelector(".n-base-selection") : null;
    return el !== null && el.textContent.indexOf("新对话") >= 0;
  }, null, { timeout: 15000 });
  check("新建对话默认标题为新对话", true);
  await shot(page, "new-session");

  // 4. 发送问题 → 标题更新为问题概括
  await page.locator(".sq-input textarea").fill("列出所有表名");
  await page.getByRole("button", { name: "发送" }).click();
  await page.waitForFunction(() => {
    const ta = document.querySelector(".sq-input textarea");
    return ta !== null && ta.disabled === true;
  }, null, { timeout: 20000 });
  await page.waitForFunction(() => {
    const ta = document.querySelector(".sq-input textarea");
    return ta !== null && ta.disabled === false;
  }, null, { timeout: 120000 });
  await page.waitForFunction(() => {
    const sel = document.querySelectorAll(".sq-toolbar .n-select")[2];
    const el = sel ? sel.querySelector(".n-base-selection") : null;
    return el !== null && el.textContent.indexOf("列出所有表名") >= 0;
  }, null, { timeout: 20000 });
  check("对话名称更新为问题概括", true);
  await shot(page, "title-updated");

  // 5. API 校验最新会话标题
  const { api, cookie } = await apiLogin();
  const listResp = await api.get(BASE + "/api/agent/sessions", { headers: { Cookie: cookie } });
  const sessions = (await listResp.json()).data;
  const latest = sessions.reduce((a, b) => (a.id > b.id ? a : b), sessions[0]);
  check("API 最新会话标题为问题概括", latest.title === "列出所有表名" && latest.message_count >= 1, JSON.stringify(latest));
  createdSessionId = latest.id;
} catch (e) {
  console.log("E2E ERROR:", e.message);
  failures += 1;
} finally {
  if (createdSessionId) {
    try {
      const { api, cookie } = await apiLogin();
      await api.delete(BASE + "/api/agent/sessions/" + createdSessionId, { headers: { Cookie: cookie } });
      console.log("cleanup: deleted test session", createdSessionId);
    } catch (e) {
      console.log("cleanup fail:", e.message);
    }
  }
  if (errors.length) console.log("PAGE ERRORS:", errors.join(" | "));
  await browser.close();
}

console.log(failures === 0 ? "ALL PASS" : failures + " FAILURES");
process.exit(failures === 0 ? 0 : 1);