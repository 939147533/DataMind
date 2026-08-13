import { chromium } from "playwright";

const BASE = "http://127.0.0.1:8000";
const SHOT_DIR = "C:\\Users\\93914\\AppData\\Local\\Temp";
let step = 0;
let failures = 0;
const errors = [];

async function shot(page, name) {
  step += 1;
  const p = SHOT_DIR + "\\e2e_ai_" + String(step).padStart(2, "0") + "_" + name + ".png";
  try { await page.screenshot({ path: p }); } catch (e) { console.log("shot fail:", name, e.message); }
  console.log("shot:", p);
}

function check(name, cond, extra) {
  if (cond) console.log("PASS:", name);
  else { console.log("FAIL:", name, extra || ""); failures += 1; }
}

async function waitMsg(page, text, timeoutMs) {
  await page.waitForFunction((t) => Array.from(document.querySelectorAll(".n-message")).some((el) => el.textContent.includes(t)), text, { timeout: timeoutMs });
}

async function waitAlert(page, text, timeoutMs) {
  await page.waitForFunction((t) => Array.from(document.querySelectorAll(".n-modal .n-alert")).some((el) => el.textContent.includes(t)), text, { timeout: timeoutMs });
}

async function closeModal(page) {
  await page.keyboard.press("Escape");
  await page.waitForTimeout(500);
  let vis = false;
  try { vis = await page.locator(".n-modal").first().isVisible(); } catch (e) { vis = false; }
  if (vis) {
    const closeBtn = page.locator(".n-modal .n-base-close").first();
    if (await closeBtn.count()) { await closeBtn.click(); await page.waitForTimeout(500); }
  }
  await page.waitForSelector(".n-modal", { state: "hidden", timeout: 10000 }).catch(() => {});
}

const browser = await chromium.launch({ channel: "chrome", headless: true });
const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const page = await context.newPage();
page.on("pageerror", (e) => errors.push("pageerror: " + e.message));

let tempCfgId = null;
try {
  // 0. 通过 API 创建无 Key 临时 AI 配置（gpt-4o-mini），供无 Key 分支测试
  {
    const adminLogin = await context.request.post(BASE + "/api/auth/login", { data: { username: "admin", password: "admin123" } });
    const adminCookie = (adminLogin.headers()["set-cookie"] || "").split(";")[0];
    const created = await context.request.post(BASE + "/api/config/ai", {
      data: { provider: "openai", api_key: "", api_base: "", model_name: "gpt-4o-mini", max_tokens: 4096, temperature: 0.7, is_active: true, is_default: false },
      headers: { Cookie: adminCookie },
    });
    const createdBody = await created.json();
    tempCfgId = createdBody.data && createdBody.data.id;
    check("创建无 Key 临时 AI 配置", created.status() === 200 && !!tempCfgId, String(created.status()));
    await context.clearCookies();
  }

  // 1. 管理员登录并进入系统设置
  await page.goto(BASE, { waitUntil: "domcontentloaded", timeout: 30000 });
  await page.waitForSelector(".login-card", { timeout: 20000 });
  await page.getByPlaceholder("admin", { exact: true }).fill("admin");
  await page.getByPlaceholder("admin123", { exact: true }).fill("admin123");
  await page.getByRole("button", { name: "登 录" }).click();
  await page.waitForFunction(() => !location.pathname.includes("/login"), null, { timeout: 20000 });
  await page.goto(BASE + "/settings", { waitUntil: "domcontentloaded", timeout: 20000 });
  await page.waitForSelector('.n-tab-pane:has-text("AI 配置")', { timeout: 20000 });
  check("系统设置 AI 配置页渲染", true);

  // 2. AI 配置卡片与“测试”按钮
  await page.waitForSelector(".settings-view .n-grid .n-card", { timeout: 20000 });
  const cardCount = await page.locator(".settings-view .n-grid .n-card").count();
  check("AI 配置卡片存在", cardCount >= 1, "count=" + cardCount);
  const testBtnCount = await page.locator(".settings-view .n-grid .n-card .card-actions .n-button", { hasText: "测试" }).count();
  check("卡片含测试按钮", testBtnCount >= 1, "count=" + testBtnCount);
  await shot(page, "ai-config-list");

  // 3. 卡片测试：无 Key 配置（gpt-4o-mini）→ 失败提示（未配置 API Key）
  const noKeyCard = page.locator('.settings-view .n-grid .n-card:has-text("gpt-4o-mini")');
  check("无 Key 配置卡片存在", (await noKeyCard.count()) === 1);
  await noKeyCard.locator(".card-actions .n-button", { hasText: "测试" }).click();
  await waitMsg(page, "API Key", 20000);
  check("卡片测试失败提示（未配置 API Key）", true);
  await shot(page, "card-test-nokey");

  // 4. 卡片测试：有 Key 配置（第一张卡，id 倒序 = DeepSeek）→ 连接成功
  const firstCard = page.locator('.settings-view .n-grid .n-card:has-text("deepseek")').first();
  await firstCard.locator(".card-actions .n-button", { hasText: "测试" }).click();
  await waitMsg(page, "连接成功", 45000);
  check("卡片测试有 Key 配置连接成功", true);
  await shot(page, "card-test-ok");

  // 5. 编辑弹窗内“测试连通性”（无 Key 配置）→ 弹窗内错误 alert + 耗时
  await noKeyCard.locator(".card-actions .n-button", { hasText: "编辑" }).click();
  await page.waitForSelector('.n-modal:has-text("编辑 AI 配置")', { timeout: 15000 });
  await page.locator('.n-modal .n-button:has-text("测试连通性")').click();
  await waitAlert(page, "API Key", 20000);
  check("弹窗内测试失败提示（未配置 API Key）", true);
  const alertText = await page.locator(".n-modal .n-alert").first().innerText();
  check("弹窗内测试展示耗时", alertText.includes("ms"), alertText);
  await shot(page, "modal-test-nokey");

  // 6. 新增配置弹窗：未保存即可测试（填模型名后点“测试连通性”）→ 失败 alert
  await closeModal(page);
  await page.locator(".toolbar .n-button", { hasText: "新增 AI 配置" }).click();
  await page.waitForSelector('.n-modal:has-text("新增 AI 配置")', { timeout: 15000 });
  await page.locator('.n-modal .n-form-item:has-text("模型名称") input').fill("e2e-ping-model");
  await page.locator('.n-modal .n-button:has-text("测试连通性")').click();
  await waitAlert(page, "API Key", 20000);
  check("新增弹窗内测试失败提示（未配置 API Key）", true);
  await shot(page, "modal-create-test");

  // 7. 编辑有 Key 配置（DeepSeek）→ 弹窗内成功 alert
  await closeModal(page);
  const okCard = page.locator('.settings-view .n-grid .n-card:has-text("deepseek")');
  check("有 Key 配置卡片存在", (await okCard.count()) >= 1);
  await okCard.first().locator(".card-actions .n-button", { hasText: "编辑" }).click();
  await page.waitForSelector('.n-modal:has-text("编辑 AI 配置")', { timeout: 15000 });
  await page.locator('.n-modal .n-button:has-text("测试连通性")').click();
  await waitAlert(page, "连接成功", 45000);
  check("弹窗内测试有 Key 配置连接成功", true);
  await shot(page, "modal-test-ok");
} catch (e) {
  console.log("E2E ERROR:", e.message);
  failures += 1;
} finally {
  if (tempCfgId) {
    try {
      const adminLogin = await context.request.post(BASE + "/api/auth/login", { data: { username: "admin", password: "admin123" } });
      const adminCookie = (adminLogin.headers()["set-cookie"] || "").split(";")[0];
      await context.request.delete(BASE + "/api/config/ai/" + tempCfgId, { headers: { Cookie: adminCookie } });
      console.log("temp ai config cleaned");
    } catch (e) {
      console.log("temp ai config cleanup failed:", e.message);
    }
  }
  if (errors.length) console.log("PAGE ERRORS:", errors.join(" | "));
  await browser.close();
}

console.log(failures === 0 ? "ALL PASS" : failures + " FAILURES");
process.exit(failures === 0 ? 0 : 1);