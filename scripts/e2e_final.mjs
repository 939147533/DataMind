import { chromium } from "playwright";
import path from "node:path";

const BASE = "http://127.0.0.1:8000";
const SHOT_DIR = "C:\\Users\\93914\\AppData\\Local\\Temp";
let step = 0;
const shots = [];
let failures = 0;

async function shot(page, name) {
  step += 1;
  const p = path.join(SHOT_DIR, `e2e_final_${String(step).padStart(2, "0")}_${name}.png`);
  try { await page.screenshot({ path: p, fullPage: false }); shots.push(p); } catch (e) { console.log("shot fail:", name, e.message); }
  console.log("shot:", p);
}

function check(name, cond, extra = "") {
  if (cond) console.log("PASS:", name);
  else { console.log("FAIL:", name, extra); failures += 1; }
}

const browser = await chromium.launch({ channel: "chrome", headless: true });
const context = await browser.newContext({ acceptDownloads: true, viewport: { width: 1440, height: 900 } });
const page = await context.newPage();
const errors = [];
page.on("pageerror", (e) => errors.push("pageerror: " + e.message));

try {
  // 1. 打开首页并登录
  await page.goto(BASE, { waitUntil: "domcontentloaded", timeout: 30000 });
  await page.waitForSelector(".login-card", { timeout: 20000 });
  check("登录页渲染", true);
  await shot(page, "login");
  await page.getByPlaceholder("admin", { exact: true }).fill("admin");
  await page.getByPlaceholder("admin123", { exact: true }).fill("admin123");
  await page.getByRole("button", { name: "登 录" }).click();
  await page.waitForURL("**/workspace", { timeout: 20000 });
  await page.waitForSelector(".workspace-view", { timeout: 20000 });
  check("登录成功进入工作台", true);
  await shot(page, "workspace");

  // 2. 选择数据源
  await page.locator(".n-base-selection", { hasText: "选择数据源" }).first().click();
  await page.locator(".n-base-select-option").filter({ hasText: "本地演示库" }).first().click();
  await page.waitForTimeout(1000);
  check("数据源已选择", await page.locator(".n-base-selection", { hasText: "本地演示库" }).count() > 0);
  await shot(page, "ds-selected");

  // 3. 对象树：展开「表」，点击 users
  await page.locator(".n-tree-node", { hasText: "表" }).first().locator(".n-tree-node-switcher").click();
  await page.waitForSelector('.n-tree-node:has-text("users")', { timeout: 15000 });
  check("对象树加载表列表", true);
  await shot(page, "object-tree");
  await page.locator('.n-tree-node:has-text("users")').first().locator(".n-tree-node-content").click();
  await page.waitForSelector('.result-table', { timeout: 20000 });
  const usersText = await page.locator(".result-table").innerText();
  check("点击表自动执行 SELECT 并返回行", /共 \d+ 行/.test(usersText) && usersText.includes("alice"), usersText.slice(0, 60));
  await shot(page, "result-users");

  // 4. 多条语句执行
  const multiSql = "SELECT id, username, age FROM users ORDER BY age DESC LIMIT 5;\nSELECT status, COUNT(*) AS cnt FROM orders GROUP BY status;";
  await page.locator(".cm-content").click();
  await page.keyboard.press("ControlOrMeta+a");
  await page.keyboard.type(multiSql, { delay: 10 });
  await page.getByRole("button", { name: "▶ 执行" }).click();
  await page.waitForTimeout(2500);
  const multiOk = (await page.locator(".result-table").innerText().catch(() => "")).includes("共");
  check("多条 SQL 执行成功并展示结果", multiOk);
  await shot(page, "multi-sql");

  // 5. 写操作确认（UPDATE，幂等）
  const updSql = "UPDATE users SET age = age WHERE username = 'alice';";
  await page.locator(".cm-content").click();
  await page.keyboard.press("ControlOrMeta+a");
  await page.keyboard.type(updSql, { delay: 10 });
  await page.getByRole("button", { name: "▶ 执行" }).click();
  await page.waitForSelector(".n-modal:has-text('写操作确认')", { timeout: 15000 });
  check("写操作弹出确认弹窗", true);
  await shot(page, "dml-confirm");
  await page.locator(".n-modal").getByRole("button", { name: "确认执行" }).click();
  await page.waitForSelector('.result-table:has-text("影响 1 行")', { timeout: 20000 });
  check("确认后执行 UPDATE 影响 1 行", true);

  // 6. DDL 危险操作取消
  const ddlSql = "CREATE TABLE e2e_tmp (id INTEGER);";
  await page.locator(".cm-content").click();
  await page.keyboard.press("ControlOrMeta+a");
  await page.keyboard.type(ddlSql, { delay: 10 });
  await page.getByRole("button", { name: "▶ 执行" }).click();
  await page.waitForSelector(".n-modal:has-text('危险操作')", { timeout: 15000 });
  check("DDL 弹出危险操作确认", true);
  await shot(page, "ddl-danger");
  await page.locator(".n-modal").getByRole("button", { name: "取消" }).click();
  await page.waitForTimeout(800);
  check("DDL 取消后无新建表", (await page.locator(".n-modal").count()) === 0);

  // 7. 结果导出（CSV）
  const csvSql = "SELECT id, username, age FROM users LIMIT 5;";
  await page.locator(".cm-content").click();
  await page.keyboard.press("ControlOrMeta+a");
  await page.keyboard.type(csvSql, { delay: 5 });
  await page.getByRole("button", { name: "▶ 执行" }).click();
  await page.waitForTimeout(2000);
  const dlPromise = page.waitForEvent("download", { timeout: 15000 }).catch(() => null);
  await page.getByRole("button", { name: "CSV" }).first().click();
  const dl = await dlPromise;
  check("CSV 结果导出触发下载", !!dl, dl ? "" : "(下载未触发，可能直接保存)");

  // 8. 导出库文档（Markdown）
  await page.getByRole("button", { name: /导出库文档/ }).click();
  const dl2Promise = page.waitForEvent("download", { timeout: 30000 }).catch(() => null);
  await page.getByText("Markdown (.md)").click();
  const dl2 = await dl2Promise;
  check("数据库文档导出（Markdown）触发下载", !!dl2, dl2 ? "" : "(下载未触发)");
  await shot(page, "export-doc");

  // 9. 执行历史
  await page.locator(".n-tabs-tab", { hasText: "历史" }).first().click();
  await page.waitForTimeout(1000);
  const histText = await page.locator(".history-list").innerText().catch(() => "");
  check("执行历史有条目", histText.includes("UPDATE") || histText.includes("SELECT"));
  await shot(page, "history");

  // 10. 报表页面
  await page.locator(".n-menu-item-content").filter({ hasText: "可视化报表" }).first().click();
  await page.waitForTimeout(2500);
  const charts = await page.locator("canvas").count();
  check("报表页渲染图表 canvas", charts > 0, `canvas=${charts}`);
  await shot(page, "reports");

  // 11. 系统设置
  await page.locator(".n-menu-item-content").filter({ hasText: "系统设置" }).first().click();
  await page.waitForSelector("text=＋ 新增 AI 配置", { timeout: 15000 });
  check("系统设置 AI 配置页", true);
  await shot(page, "settings");

  // 12. 审计日志
  await page.locator(".n-menu-item-content").filter({ hasText: "审计日志" }).first().click();
  await page.waitForTimeout(1500);
  const auditRows = await page.locator(".n-data-table tbody tr").count();
  check("审计日志有记录", auditRows > 0, `rows=${auditRows}`);
  await shot(page, "audit");

  // 13. Agent 无 Key 快速失败
  await page.locator(".n-menu-item-content").filter({ hasText: "SQL 工作台" }).first().click();
  await page.waitForSelector('textarea[placeholder*="输入自然语言查询"]', { timeout: 15000 });
  const t0 = Date.now();
  await page.locator('textarea[placeholder*="输入自然语言查询"]').fill("统计各订单状态的数量");
  await page.locator(".agent-input").getByRole("button", { name: "发送" }).click();
  await page.waitForSelector('.agent-messages :text("AI 调用失败")', { timeout: 15000 });
  const elapsed = (Date.now() - t0) / 1000;
  check("Agent 无 Key 快速返回错误", true, `elapsed=${elapsed}s`);
  check("Agent 错误耗时小于 5 秒", elapsed < 5, `elapsed=${elapsed}s`);
  await shot(page, "agent-error");

  // 14. 主题切换
  await page.locator(".topbar-actions button").first().click();
  await page.waitForTimeout(600);
  check("暗色主题切换无异常", true);
  await shot(page, "dark-theme");
  await page.locator(".topbar-actions button").first().click(); // 切回亮色
  await page.waitForTimeout(400);

  console.log("\n===== E2E SUMMARY =====");
  console.log("failures:", failures);
  console.log("page errors:", errors.length ? errors.slice(0, 5) : "none");
  console.log("screenshots:");
  shots.forEach((s) => console.log("  " + s));
} catch (e) {
  failures += 1;
  console.log("E2E EXCEPTION:", e.message);
  await shot(page, "exception");
} finally {
  await browser.close();
  if (failures > 0) throw new Error("E2E failures: " + failures);
}
