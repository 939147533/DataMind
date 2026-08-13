import { chromium } from "playwright";

const BASE = "http://127.0.0.1:8000";
const EXE = "C:/Users/93914/AppData/Local/ms-playwright/chromium-1228/chrome-win64/chrome.exe";
const browser = await chromium.launch({ executablePath: EXE, headless: true });
const context = await browser.newContext({ viewport: { width: 1500, height: 950 } });

const lr = await context.request.post(BASE + "/api/auth/login", { data: { username: "admin", password: "admin123" } });
console.log("login:", lr.status());
if (lr.status() !== 200) { await browser.close(); process.exit(1); }

const page = await context.newPage();
const errors = [];
page.on("pageerror", (e) => errors.push("PAGEERROR: " + e.message));
page.on("console", (m) => { if (m.type() === "error") errors.push("CONSOLE: " + m.text().slice(0, 200)); });

// ===== Scenario A: smart query dual-axis chart =====
await page.goto(BASE + "/smart-query", { waitUntil: "networkidle" });
await page.waitForSelector(".sq-toolbar .n-base-selection", { timeout: 20000 });
await page.locator(".sq-toolbar .n-base-selection").nth(0).click();
await page.waitForTimeout(400);
const dsOpt = page.locator(".n-base-select-option", { hasText: "oracle-free" }).first();
await dsOpt.waitFor({ timeout: 10000 });
await dsOpt.click();
await page.waitForTimeout(400);
await page.getByRole("button", { name: "新建对话" }).click();
await page.waitForTimeout(600);
const input = page.locator(".sq-input textarea, .sq-input input").first();
await input.fill("近30天每天的成功交易笔数和金额的趋势图");
await input.press("Enter");
let ok = false;
for (let i = 0; i < 90; i++) {
  await page.waitForTimeout(2000);
  if ((await page.locator(".chart-host canvas").count()) > 0) { ok = true; break; }
  if ((await page.locator(".chart-empty").count()) > 0) break;
}
console.log("A) smart-query chart rendered:", ok);
console.log("A) titles:", await page.locator(".chart-title").allTextContents());
await page.screenshot({ path: "C:/Users/93914/AppData/Local/Temp/e2e_dualaxis_sq.png" });

// ===== Scenario B: reports page loads saved chart =====
await page.goto(BASE + "/reports", { waitUntil: "networkidle" });
await page.waitForSelector(".chart-host", { timeout: 20000 });
await page.waitForTimeout(2500);
const loadingCount = await page.locator(".chart-msg", { hasText: "加载中" }).count();
const canvasCount = await page.locator(".chart-host canvas").count();
const chartNames = await page.locator(".chart-card").count();
console.log("B) reports chart cards:", chartNames, "canvases:", canvasCount, "loading-msgs:", loadingCount);
await page.screenshot({ path: "C:/Users/93914/AppData/Local/Temp/e2e_dualaxis_reports.png" });

if (errors.length) { console.log("--- errors ---"); errors.slice(0, 10).forEach((e) => console.log(e)); }
else console.log("no page errors");

await browser.close();
process.exit(ok && loadingCount === 0 ? 0 : 2);