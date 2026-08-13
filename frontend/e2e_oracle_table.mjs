import { chromium } from "playwright";

const BASE = "http://127.0.0.1:8000";
const SHOT_DIR = "C:\\Users\\93914\\AppData\\Local\\Temp";
let step = 0;
let failures = 0;
const errors = [];

async function shot(page, name) {
  step += 1;
  const p = SHOT_DIR + "\\e2e_oracle_" + String(step).padStart(2, "0") + "_" + name + ".png";
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

try {
  // 1. 管理员登录进入工作台
  await page.goto(BASE, { waitUntil: "domcontentloaded", timeout: 30000 });
  await page.waitForSelector(".login-card", { timeout: 20000 });
  await page.getByPlaceholder("admin", { exact: true }).fill("admin");
  await page.getByPlaceholder("admin123", { exact: true }).fill("admin123");
  await page.getByRole("button", { name: "登 录" }).click();
  await page.waitForFunction(() => !location.pathname.includes("/login"), null, { timeout: 20000 });
  await page.goto(BASE + "/workspace", { waitUntil: "domcontentloaded", timeout: 20000 });
  await page.waitForSelector(".workspace-view", { timeout: 20000 });
  check("工作台渲染", true);

  // 2. 选择 oracle-free 数据源
  await page.locator(".ds-row .n-select").click();
  await page.waitForSelector(".n-base-select-option", { timeout: 15000 });
  await page.locator(".n-base-select-option", { hasText: "oracle-free" }).first().click();
  await page.waitForSelector(".object-tree .n-tree", { timeout: 20000 });
  await page.waitForTimeout(800);
  await shot(page, "ds-selected");

  // 3. 展开“表”并等待 T_ACCOUNT
  const tablesNode = page.locator('.object-tree .n-tree-node-content:has-text("表")').first();
  await tablesNode.locator("xpath=ancestor::div[contains(@class, 'n-tree-node')][1]").locator(".n-tree-node-switcher").click();
  await page.waitForSelector('.object-tree .n-tree-node-content:has-text("T_ACCOUNT")', { timeout: 40000 });
  check("对象树加载出 T_ACCOUNT", true);
  await shot(page, "tree-loaded");

  // 4. 点击 T_ACCOUNT：生成查询并自动执行
  await page.locator('.object-tree .n-tree-node-content:has-text("T_ACCOUNT")').first().click();
  await page.waitForFunction(() => {
    const el = document.querySelector(".cm-content");
    return el !== null && el.textContent.indexOf("T_ACCOUNT") >= 0;
  }, null, { timeout: 20000 });
  const sql = await page.locator(".cm-content").innerText();
  check("编辑器生成 Oracle 语法（FETCH FIRST）", sql.indexOf("FETCH FIRST 100 ROWS ONLY") >= 0, sql);
  check("编辑器生成语句不含 LIMIT", sql.indexOf("LIMIT") < 0, sql);
  await shot(page, "editor-sql");

  // 5. 执行结果：成功显示行数，且无 ORA-03047
  await page.waitForFunction(() => {
    const meta = document.querySelector(".result-table .result-meta");
    return meta !== null;
  }, null, { timeout: 40000 });
  const metaText = await page.locator(".result-table .result-meta").innerText();
  check("Oracle 查询执行成功并返回行数", metaText.indexOf("行") >= 0, metaText);
  const pageText = await page.locator(".result-table").innerText();
  check("无 ORA-03047 错误", pageText.indexOf("ORA-03047") < 0, pageText.slice(0, 200));
  await shot(page, "result-ok");
} catch (e) {
  console.log("E2E ERROR:", e.message);
  failures += 1;
} finally {
  if (errors.length) console.log("PAGE ERRORS:", errors.join(" | "));
  await browser.close();
}

console.log(failures === 0 ? "ALL PASS" : failures + " FAILURES");
process.exit(failures === 0 ? 0 : 1);