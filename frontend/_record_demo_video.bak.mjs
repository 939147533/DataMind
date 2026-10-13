import { chromium } from "playwright";
import fs from "node:fs";
import path from "node:path";

const BASE = "http://127.0.0.1:5174";
const OUT_DIR = "E:\\视频及材料\\recording";
const VIDEO_DIR = path.join(OUT_DIR, "video");
const LOG_PATH = path.join(OUT_DIR, "scene_log.json");
fs.mkdirSync(VIDEO_DIR, { recursive: true });

const narration = JSON.parse(fs.readFileSync(path.join(OUT_DIR, "narration.json"), "utf8"));
const minByScene = Object.fromEntries(narration.map((s) => [s.id, (s.min || 30) * 1000]));

const sceneLog = [];
let currentScene = null;
function startScene(id, name) {
  currentScene = { id, name, start: Date.now(), end: null };
}
async function endScene() {
  if (!currentScene) return;
  const elapsed = Date.now() - currentScene.start;
  const min = minByScene[currentScene.id] || 30000;
  const remaining = Math.max(0, min - elapsed);
  if (remaining > 0) await page.waitForTimeout(remaining);
  currentScene.end = Date.now();
  sceneLog.push(currentScene);
  fs.writeFileSync(LOG_PATH, JSON.stringify(sceneLog, null, 2));
  currentScene = null;
}

const browser = await chromium.launch({ channel: "chrome", headless: true });
const context = await browser.newContext({
  viewport: { width: 1920, height: 1080 },
  acceptDownloads: true,
  recordVideo: { dir: VIDEO_DIR, size: { width: 1920, height: 1080 } },
});
const page = await context.newPage();
page.setDefaultTimeout(120000);
page.on("pageerror", (e) => console.log("PAGEERROR:", e.message));

async function login(u, pwd) {
  await context.clearCookies();
  await page.goto(BASE, { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.waitForSelector(".login-card", { timeout: 30000 });
  await page.getByPlaceholder("请输入用户名", { exact: true }).fill(u);
  await page.getByPlaceholder("请输入密码", { exact: true }).fill(pwd);
  await page.getByRole("button", { name: "登 录" }).click();
  await page.waitForFunction(() => !location.pathname.includes("/login"), null, { timeout: 30000 });
}
async function logout() {
  await page.locator(".topbar-actions .n-button").last().click();
  await page.waitForTimeout(500);
  await page.locator(".n-dropdown-option", { hasText: "退出登录" }).first().click();
  await page.waitForSelector(".login-card", { timeout: 30000 });
}
async function menuClick(label) {
  await page.locator(".n-menu-item-content", { hasText: label }).first().click();
  await page.waitForTimeout(500);
}
async function waitForStreamEnd(areaSel, timeout = 120000) {
  await page.waitForFunction((sel) => {
    const area = document.querySelector(sel);
    if (!area) return false;
    if (area.querySelector(".cursor")) return false;
    return Array.from(area.querySelectorAll(".n-button.is-loading")).length === 0;
  }, areaSel, { timeout });
}
async function scrollToBottom(selector, ms = 1200) {
  await page.locator(selector).evaluate(async (el, t) => {
    for (let i = 1; i <= 15; i++) {
      el.scrollTop = el.scrollHeight * i / 15;
      await new Promise((r) => setTimeout(r, t / 15));
    }
  }, ms);
}
async function selectByLabel(formItemText, optionText) {
  const item = page.locator(".n-modal").last().locator(".n-form-item, .n-form-item-gi").filter({ hasText: formItemText }).first();
  await item.locator(".n-base-selection").first().click();
  await page.waitForTimeout(300);
  await page.locator(".n-base-select-option", { hasText: optionText }).last().click();
  await page.waitForTimeout(200);
}
async function fillByLabel(formItemText, value) {
  const item = page.locator(".n-modal").last().locator(".n-form-item, .n-form-item-gi").filter({ hasText: formItemText }).first();
  await item.locator("input").first().fill(String(value));
}
async function selectSmartQueryModel() {
  const selects = page.locator(".sq-toolbar .n-base-selection");
  if (await selects.count() < 2) return;
  await selects.nth(1).click();
  await page.waitForTimeout(300);
  const option = page.locator(".n-base-select-option", { hasText: "openai · deepseek-v4-flash" }).first();
  if (await option.count()) {
    await option.click();
    await page.waitForTimeout(400);
  } else {
    await page.keyboard.press("Escape");
  }
}async function waitMessage(text, timeout = 30000) {
  await page.waitForFunction((t) => Array.from(document.querySelectorAll(".n-message")).some((el) => el.textContent.includes(t)), text, { timeout });
}

try {
  // 0 登录与总览
  startScene("00", "登录与系统总览");
  await login("admin", "admin123");
  await page.waitForURL("**/smart-query", { timeout: 30000 }).catch(() => {});
  await page.waitForSelector(".smart-query-view", { timeout: 30000 });
  await page.waitForTimeout(1200);
  await selectSmartQueryModel();
  await page.locator(".n-menu").first().evaluate((el) => (el.scrollTop = 0));
  await page.waitForTimeout(1800);
  await endScene();

  // 1 MySQL 智能查询
  startScene("01", "智能查询MySQL");
  await page.waitForSelector(".sq-toolbar .n-base-selection", { timeout: 30000 });
  await page.locator(".sq-toolbar .n-base-selection").first().click();
  await page.waitForTimeout(300);
  await page.locator(".n-base-select-option", { hasText: "mysql (mysql)" }).first().click();
  await page.waitForTimeout(500);
  await page.locator(".sq-toolbar .n-button", { hasText: "新建对话" }).click();
  await page.waitForTimeout(600);
  await page.locator(".sq-input textarea").fill("各机构客户数和账户数 TOP10");
  await page.locator(".sq-input .n-button", { hasText: "发送" }).click();
  await page.waitForSelector(".sq-messages .msg.assistant", { timeout: 120000 });
  await waitForStreamEnd(".sq-messages", 120000);
  await page.waitForSelector(".sq-messages .result-meta", { timeout: 120000 });
  await page.waitForTimeout(800);
  await scrollToBottom(".sq-messages", 1600);
  await page.waitForTimeout(800);
  await endScene();

  // 2 Oracle + Excel
  startScene("02", "智能查询Oracle导出Excel");
  await page.locator(".sq-toolbar .n-base-selection").first().click();
  await page.waitForTimeout(300);
  await page.locator(".n-base-select-option", { hasText: "oracle-free (oracle)" }).first().click();
  await page.waitForTimeout(500);
  await page.locator(".sq-toolbar .n-button", { hasText: "新建对话" }).click();
  await page.waitForTimeout(600);
  await page.locator(".sq-input textarea").fill("查询所有机构，列出机构号、机构名称、机构层级和所在地区，按机构号排序");
  await page.locator(".sq-input .n-button", { hasText: "发送" }).click();
  await page.waitForSelector(".sq-messages .msg.assistant", { timeout: 120000 });
  await waitForStreamEnd(".sq-messages", 120000);
  await page.waitForSelector(".sq-messages .result-meta", { timeout: 120000 });
  await page.waitForTimeout(800);
  await scrollToBottom(".sq-messages", 1600);
  await page.waitForTimeout(600);
  const [download] = await Promise.all([
    page.waitForEvent("download", { timeout: 60000 }),
    page.locator(".sq-messages .result-actions .n-button", { hasText: "Excel" }).first().click(),
  ]);
  console.log("download:", download.suggestedFilename());
  await waitMessage("导出成功", 30000).catch(() => console.log("export toast not seen"));
  await page.waitForTimeout(800);
  await endScene();

  // 3 报表一
  startScene("03", "智能查询报表一");
  await page.locator(".sq-toolbar .n-button", { hasText: "新建对话" }).click();
  await page.waitForTimeout(600);
  await page.locator(".sq-input textarea").fill("按分行层级统计近30天各个分行的交易笔数、交易总额，生成图表");
  await page.locator(".sq-input .n-button", { hasText: "发送" }).click();
  await page.waitForSelector(".sq-messages .msg.assistant", { timeout: 120000 });
  await waitForStreamEnd(".sq-messages", 120000);
  await page.waitForSelector(".sq-messages .chart-box", { timeout: 120000 });
  await page.waitForTimeout(800);
  await scrollToBottom(".sq-messages", 1200);
  await page.locator(".sq-messages .chart-actions .n-button", { hasText: "保存到可视化报表" }).first().click();
  await waitMessage("已保存到可视化报表", 30000);
  await page.waitForTimeout(800);
  await endScene();

  // 4 报表二
  startScene("04", "智能查询报表二");
  await page.locator(".sq-toolbar .n-button", { hasText: "新建对话" }).click();
  await page.waitForTimeout(600);
  await page.locator(".sq-input textarea").fill("近30天成功交易笔数和金额趋势，生成图表");
  await page.locator(".sq-input .n-button", { hasText: "发送" }).click();
  await page.waitForSelector(".sq-messages .msg.assistant", { timeout: 120000 });
  await waitForStreamEnd(".sq-messages", 120000);
  await page.waitForSelector(".sq-messages .chart-box", { timeout: 120000 });
  await page.waitForTimeout(800);
  await scrollToBottom(".sq-messages", 1200);
  await page.locator(".sq-messages .chart-actions .n-button", { hasText: "保存到可视化报表" }).first().click();
  await waitMessage("已保存到可视化报表", 30000);
  await page.waitForTimeout(800);
  await endScene();

  // 5 可视化报表
  startScene("05", "可视化报表仪表盘大屏分享");
  await menuClick("可视化报表");
  await page.waitForSelector(".reports-view", { timeout: 30000 });
  await page.waitForTimeout(1200);
  await page.locator(".n-tabs-tab", { hasText: "仪表盘" }).click();
  await page.waitForTimeout(800);
  await page.locator(".toolbar .n-button", { hasText: "新建仪表盘" }).click();
  await page.waitForSelector('.n-modal:has-text("新建仪表盘")', { timeout: 30000 });
  await page.locator(".n-modal").last().getByPlaceholder("仪表盘名称").fill("近30天交易统计");
  const dashModal = page.locator(".n-modal").last();
  await dashModal.locator(".n-base-selection").first().click();
  await page.waitForTimeout(400);
  const visibleOptions = page.locator(".n-base-select-option:visible");
  const chartCount = await visibleOptions.count();
  console.log("chart options count:", chartCount);
  for (let i = 0; i < Math.min(2, chartCount); i++) {
    await visibleOptions.nth(i).click();
    await page.waitForTimeout(250);
  }
  await page.keyboard.press("Escape");
  await page.waitForTimeout(400);
  await dashModal.getByRole("button", { name: "创建" }).click();
  await page.waitForTimeout(1500);

  const dashCard = page.locator(".n-card", { hasText: "近30天交易统计" }).first();
  await dashCard.getByRole("button", { name: "大屏" }).click();
  await page.waitForSelector(".big-screen .screen", { timeout: 30000 });
  await page.waitForTimeout(1800);
  await page.locator(".close-btn").click();
  await page.waitForTimeout(600);
  await dashCard.getByRole("button", { name: "分享" }).click();
  await page.waitForSelector('.n-modal:has-text("分享仪表盘")', { timeout: 30000 });
  await page.waitForTimeout(800);
  await page.locator(".n-modal").last().getByRole("button", { name: "复制链接" }).click();
  await page.waitForTimeout(700);
  await page.keyboard.press("Escape");
  await page.waitForTimeout(500);
  await endScene();

  // 6 SQL 工作台
  startScene("06", "SQL工作台AI辅助");
  await menuClick("SQL 工作台");
  await page.waitForSelector(".workspace-view", { timeout: 30000 });
  await page.locator(".ds-row .n-select").click();
  await page.waitForTimeout(300);
  await page.locator(".n-base-select-option", { hasText: "oracle-free" }).first().click();
  await page.waitForSelector(".object-tree .n-tree", { timeout: 40000 });
  await page.waitForTimeout(1000);
  const tablesNode = page.locator('.object-tree .n-tree-node-content:has-text("表")').first();
  if (await tablesNode.count()) {
    await tablesNode.locator("xpath=ancestor::div[contains(@class, 'n-tree-node')][1]").locator(".n-tree-node-switcher").click();
    await page.waitForSelector('.object-tree .n-tree-node-content:has-text("T_ACCOUNT")', { timeout: 40000 });
    await page.waitForTimeout(800);
  }
  await page.locator(".agent-rail").click();
  await page.waitForSelector(".agent-panel", { timeout: 30000 });
  await page.waitForTimeout(600);
  await page.locator(".agent-input textarea").fill("统计近90天各地区的成功交易笔数和交易金额，按金额从高到低");
  await page.locator(".agent-input .n-button", { hasText: "发送" }).click();
  await page.waitForSelector(".agent-messages .msg.assistant", { timeout: 120000 });
  await waitForStreamEnd(".agent-messages", 120000);
  await page.waitForSelector(".agent-messages .sql-block", { timeout: 120000 });
  await page.waitForTimeout(800);
  await page.locator(".agent-messages .sql-block .n-button", { hasText: "填入编辑器" }).first().click();
  await page.waitForTimeout(800);
  const agentSql = await page.locator(".agent-messages .sql-block code").last().innerText().catch(() => "");
  console.log("agent sql length:", agentSql.length);
  const editedSql = agentSql
    .replace(/(TRUNC\(SYSDATE\))\s*-\s*90/g, "$1 - 30")
    .replace(/(TRUNC\(SYSDATE\))\s*-\s*89/g, "$1 - 29");
  await page.locator(".cm-content").click();
  await page.keyboard.press("ControlOrMeta+a");
  await page.keyboard.type(editedSql, { delay: 3 });
  await page.waitForTimeout(500);
  await page.getByRole("button", { name: "▶ 执行" }).click();
  await page.waitForSelector(".result-table .result-meta", { timeout: 120000 });
  await page.waitForTimeout(800);
  await page.locator(".workspace-view .toolbar .n-button", { hasText: "收藏" }).first().click();
  await page.waitForSelector('.n-modal:has-text("收藏 SQL")', { timeout: 30000 });
  await page.locator(".n-modal").last().getByPlaceholder("给这条 SQL 起个名字").fill("近30天各地区成功交易统计");
  await page.locator(".n-modal").last().getByRole("button", { name: "保存" }).click();
  await waitMessage("已收藏", 30000);
  await page.waitForTimeout(800);

  await page.locator(".ds-row .n-select").click();
  await page.waitForTimeout(300);
  await page.locator(".n-base-select-option", { hasText: "本地演示库" }).first().click();
  await page.waitForTimeout(1000);
  await page.locator(".cm-content").click();
  await page.keyboard.press("ControlOrMeta+a");
  await page.keyboard.type("UPDATE products SET stock = stock + 1 WHERE id = 1;", { delay: 4 });
  await page.getByRole("button", { name: "▶ 执行" }).click();
  await page.waitForSelector('.n-modal:has-text("写操作确认")', { timeout: 30000 });
  await page.waitForTimeout(1000);
  await page.locator(".n-modal").last().getByRole("button", { name: "确认执行" }).click();
  await page.waitForTimeout(1500);
  await endScene();

  // 7 系统设置
  startScene("07", "系统设置连接与模型");
  await menuClick("系统设置");
  await page.waitForSelector(".settings-view", { timeout: 30000 });
  await page.locator(".n-tabs-tab", { hasText: "数据库连接配置" }).click();
  await page.waitForTimeout(800);
  await page.locator(".connections-view .toolbar .n-button", { hasText: "新建连接" }).click();
  await page.waitForSelector('.n-modal:has-text("新建连接")', { timeout: 30000 });
  await fillByLabel("连接名称", "Oracle（开发）");
  await selectByLabel("数据库类型", "Oracle");
  await fillByLabel("主机", "100.102.197.1");
  await fillByLabel("端口", "1521");
  await fillByLabel("用户名", "system");
  await fillByLabel("密码", "system");
  await fillByLabel("默认数据库", "FREE");
  await selectByLabel("环境", "开发");
  await page.locator(".n-modal").last().getByRole("button", { name: "测试连接" }).click();
  await page.waitForSelector('.n-modal:has-text("连接测试结果")', { timeout: 30000 });
  await page.waitForTimeout(1000);
  const testClose = page.locator('.n-modal:has-text("连接测试结果") .n-base-close').first();
  if (await testClose.count()) { await testClose.click(); } else { await page.keyboard.press("Escape"); }
  await page.waitForTimeout(500);
  await page.locator('.n-modal:has-text("新建连接")').getByRole("button", { name: "保存" }).click();
  await waitMessage("创建成功", 30000);
  await page.waitForTimeout(800);

  await page.locator(".n-tabs-tab", { hasText: "大模型连接配置" }).click();
  await page.waitForTimeout(800);
  await page.locator(".settings-view .toolbar .n-button", { hasText: "新增大模型配置" }).click();
  await page.waitForSelector('.n-modal:has-text("新增大模型配置")', { timeout: 30000 });
  await selectByLabel("提供商", "OpenAI（或兼容网关）");
  await fillByLabel("API Base", "https://apihub.agnes-ai.com/v1");
  await fillByLabel("模型名称", "agnes-2.5-flash");
  await fillByLabel("API Key", "sk-N9lFn1u7EdbIM27mDfBlyvy3lLZFvkOuK8hIeo62LToE7tNT");
  await page.locator(".n-modal").last().getByRole("button", { name: "测试连通性" }).click();
  await page.waitForSelector('.n-modal .n-alert:has-text("连接成功")', { timeout: 60000 });
  await page.waitForTimeout(1000);
  await page.locator(".n-modal").last().getByRole("button", { name: "保存" }).click();
  await waitMessage("创建成功", 30000);
  await page.waitForTimeout(800);
  await endScene();

  // 8 用户与角色
  startScene("08", "用户与角色管理");
  await menuClick("用户管理");
  await page.waitForSelector('text=＋ 新增用户', { timeout: 30000 });
  await page.waitForTimeout(1200);
  await menuClick("角色管理");
  await page.waitForSelector('text=＋ 新增角色', { timeout: 30000 });
  await page.waitForTimeout(1800);
  await endScene();

  // 9 运维监控
  startScene("09", "运维监控");
  await menuClick("运维监控");
  await page.waitForSelector(".monitor-view", { timeout: 30000 });
  await page.waitForTimeout(1000);
  await page.locator(".n-tabs-tab", { hasText: "慢查询" }).click();
  await page.waitForTimeout(600);
  const monitorInputs = page.locator(".monitor-view .n-tab-pane").last().locator("input");
  if (await monitorInputs.count()) { await monitorInputs.first().fill("200"); }
  await page.locator(".monitor-view .toolbar .n-button", { hasText: "查询" }).click();
  await page.waitForTimeout(800);
  await page.locator(".n-tabs-tab", { hasText: "表结构对比" }).click();
  await page.waitForTimeout(600);
  await page.locator(".n-tabs-tab", { hasText: "审计日志" }).click();
  await page.waitForSelector(".audit-view", { timeout: 30000 }).catch(() => {});
  await page.waitForTimeout(800);
  await page.locator(".n-tabs-tab", { hasText: "定时任务" }).click();
  await page.waitForTimeout(900);
  await endScene();

  // 10 业务管理账号
  startScene("10", "业务管理账号");
  await logout();
  await login("bus_man_01", "123456");
  await page.waitForTimeout(1500);
  const bizMenu = await page.locator(".n-menu").innerText().catch(() => "");
  console.log("biz menu:", bizMenu.replace(/\n/g, " | "));
  await menuClick("系统设置");
  await page.waitForSelector(".settings-view", { timeout: 30000 });
  await page.waitForTimeout(1200);
  await menuClick("运维监控");
  await page.waitForSelector(".monitor-view", { timeout: 30000 });
  await page.waitForTimeout(1200);
  await endScene();

  // 11 技术查询账号
  startScene("11", "技术查询账号");
  await logout();
  await login("tec_que_01", "123456");
  await menuClick("SQL 工作台");
  await page.waitForSelector(".workspace-view", { timeout: 30000 });
  await page.locator(".ds-row .n-select").click();
  await page.waitForTimeout(300);
  await page.locator(".n-base-select-option", { hasText: "本地演示库" }).first().click();
  await page.waitForTimeout(1000);
  await page.locator(".cm-content").click();
  await page.keyboard.press("ControlOrMeta+a");
  await page.keyboard.type("SELECT id, name, stock FROM products LIMIT 10;", { delay: 4 });
  await page.getByRole("button", { name: "▶ 执行" }).click();
  await page.waitForSelector(".result-table .result-meta", { timeout: 120000 });
  await page.waitForTimeout(1000);
  await page.locator(".cm-content").click();
  await page.keyboard.press("ControlOrMeta+a");
  await page.keyboard.type("UPDATE products SET stock = stock + 1 WHERE id = 1;", { delay: 4 });
  await page.getByRole("button", { name: "▶ 执行" }).click();
  await page.waitForSelector('.result-table .n-alert:has-text("无权限")', { timeout: 30000 });
  await page.waitForTimeout(1200);
  await page.locator(".cm-content").click();
  await page.keyboard.press("ControlOrMeta+a");
  await page.keyboard.type("CREATE TABLE demo_test (id INTEGER);", { delay: 4 });
  await page.getByRole("button", { name: "▶ 执行" }).click();
  await page.waitForSelector('.result-table .n-alert:has-text("无权限")', { timeout: 30000 });
  await page.waitForTimeout(1500);
  await endScene();

  console.log("RECORDING DONE");
} catch (e) {
  console.log("RECORD ERROR:", e.message);
  console.log(e.stack);
  if (currentScene) {
    currentScene.end = Date.now();
    sceneLog.push(currentScene);
    fs.writeFileSync(LOG_PATH, JSON.stringify(sceneLog, null, 2));
  }
} finally {
  await context.close();
  await browser.close();
}






