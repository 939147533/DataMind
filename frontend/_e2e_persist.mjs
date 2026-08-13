
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

async function dsValue() {
  const sel = page.locator(".sq-toolbar .n-base-selection").nth(0);
  await sel.waitFor({ timeout: 15000 });
  return (await sel.innerText()).replace(/\s+/g, " ").trim();
}

// ===== go to smart query =====
await page.goto(BASE + "/smart-query", { waitUntil: "networkidle" });
await page.waitForSelector(".sq-toolbar .n-base-selection", { timeout: 20000 });
const before = await dsValue();
console.log("0) default ds:", JSON.stringify(before));

// pick a different datasource (prefer oracle-free, else first non-current option)
await page.locator(".sq-toolbar .n-base-selection").nth(0).click();
await page.waitForTimeout(400);
let opts = page.locator(".n-base-select-option");
let target = opts.filter({ hasText: "oracle-free" }).first();
let chosen = "";
if (await target.count()) {
  chosen = (await target.innerText()).replace(/\s+/g, " ").trim();
  await target.click();
} else {
  const all = await opts.allTextContents();
  const other = all.find((t) => t.replace(/\s+/g, " ").trim() !== before);
  if (!other) { console.log("SKIP: only one datasource"); await browser.close(); process.exit(3); }
  chosen = other.replace(/\s+/g, " ").trim();
  await opts.filter({ hasText: chosen }).first().click();
}
await page.waitForTimeout(500);
const after = await dsValue();
console.log("1) selected ds:", JSON.stringify(after), "picked:", JSON.stringify(chosen));

// ===== switch to another menu via SPA (menu index 2 = connections) =====
await page.locator(".n-menu .n-menu-item-content").nth(2).click();
await page.waitForURL("**/connections", { timeout: 10000 });
await page.waitForTimeout(500);
console.log("2) at:", page.url());

// back to smart query (menu index 0)
await page.locator(".n-menu .n-menu-item-content").nth(0).click();
await page.waitForURL("**/smart-query", { timeout: 10000 });
await page.waitForSelector(".sq-toolbar .n-base-selection", { timeout: 20000 });
await page.waitForTimeout(800);
const backAfter = await dsValue();
console.log("3) ds after menu switch:", JSON.stringify(backAfter), "preserved:", backAfter === after);

// ===== full page reload (localStorage) =====
await page.reload({ waitUntil: "networkidle" });
await page.waitForSelector(".sq-toolbar .n-base-selection", { timeout: 20000 });
await page.waitForTimeout(800);
const afterReload = await dsValue();
console.log("4) ds after reload:", JSON.stringify(afterReload), "preserved:", afterReload === after);

if (errors.length) { console.log("--- errors ---"); errors.slice(0, 10).forEach((e) => console.log(e)); }
else console.log("no page errors");

const pass = backAfter === after && afterReload === after;
await browser.close();
process.exit(pass ? 0 : 2);
