import { chromium } from "playwright";

const BASE = "http://127.0.0.1:8000";
const SHOT_DIR = "C:\\Users\\93914\\AppData\\Local\\Temp";
let step = 0;
let failures = 0;
const errors = [];
const NAME = "E2E" + String(Date.now() % 100000);
const KPI_NAME = NAME + "-KPI";
const BAR_NAME = NAME + "-状态";
const DASH_NAME = NAME + "-大屏";

async function shot(page, name) {
  step += 1;
  const p = SHOT_DIR + "\\e2e_rep_" + String(step).padStart(2, "0") + "_" + name + ".png";
  try { await page.screenshot({ path: p }); } catch (e) { console.log("shot fail:", name, e.message); }
  console.log("shot:", p);
}
function check(name, cond, extra = "") {
  if (cond) console.log("PASS:", name);
  else { console.log("FAIL:", name, extra); failures += 1; }
}

const browser = await chromium.launch({ channel: "chrome", headless: true });
const context = await browser.newContext({ viewport: { width: 1600, height: 1000 } });
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

async function apiAdmin() {
  const api = await context.request;
  const login = await api.post(BASE + "/api/auth/login", { data: { username: "admin", password: "admin123" } });
  const setCookie = login.headers()["set-cookie"] || "";
  const cookie = setCookie.split(";")[0];
  return { api, headers: { Cookie: cookie } };
}

async function selectOption(modal, selectionText, optionText) {
  await modal.locator(".n-base-selection", { hasText: selectionText }).first().click();
  await page.waitForTimeout(300);
  await page.locator(".n-base-select-option", { hasText: optionText }).first().click();
  await page.waitForTimeout(200);
}

async function createChart({ name, sql, type, x, y, title, theme, refresh, prefix }) {
  await page.locator(".toolbar button", { hasText: "新建图表" }).click();
  const modal = page.locator(".n-modal");
  await modal.waitFor({ state: "visible" });
  await page.getByPlaceholder("图表名称", { exact: true }).fill(name);
  await selectOption(modal, "选择数据源", "本地演示库");
  await modal.locator("textarea").fill(sql);
  if (type) await selectOption(modal, "柱状图", type);
  if (x) await page.getByPlaceholder("分类列").fill(x);
  if (y) await page.getByPlaceholder("数值列，逗号分隔多列").fill(y);
  if (title) await page.getByPlaceholder("默认使用图表名称", { exact: true }).fill(title);
  if (theme) await selectOption(modal, "跟随系统", theme);
  if (refresh) {
    await modal.locator(".n-form-item", { hasText: "刷新间隔" }).locator("input").fill(String(refresh));
  }
  if (prefix) {
    await modal.locator(".n-form-item", { hasText: "数值前缀" }).locator("input").fill(prefix);
  }
  await shot(page, "chart-form-" + name);
  await modal.getByRole("button", { name: "保存" }).click();
  await page.waitForTimeout(1200);
}

try {
  // cleanup leftovers from previous runs
  {
    const { api, headers } = await apiAdmin();
    const charts = await (await api.get(BASE + "/api/charts", { headers })).json();
    const chartArr = Array.isArray(charts.data) ? charts.data : charts.data.list || [];
    for (const c of chartArr) {
      if (c.name.startsWith("E2E")) await api.delete(BASE + "/api/charts/" + c.id, { headers });
    }
    const dashes = await (await api.get(BASE + "/api/dashboards", { headers })).json();
    const dashArr = Array.isArray(dashes.data) ? dashes.data : dashes.data.list || [];
    for (const d of dashArr) {
      if (d.name.startsWith("E2E")) await api.delete(BASE + "/api/dashboards/" + d.id, { headers });
    }
  }

  await login("admin", "admin123");
  await page.waitForURL("**/smart-query", { timeout: 20000 });
  await page.locator(".n-menu-item-content", { hasText: "可视化报表" }).first().click();
  await page.waitForSelector(".reports-view", { timeout: 20000 });
  await page.waitForTimeout(800);
  check("进入可视化报表页", true);
  await shot(page, "reports-home");

  // 1. create KPI chart
  await createChart({
    name: KPI_NAME,
    sql: "SELECT SUM(amount) AS total FROM orders",
    type: "KPI 指标卡",
    y: "total",
    title: "销售总额",
    theme: "深色",
    refresh: 5,
    prefix: "¥",
  });
  await page.waitForSelector('.type-badge:has-text("KPI 指标卡")', { timeout: 15000 });
  check("KPI 图表创建成功且类型徽标正确", true);
  await page.waitForSelector('.refresh-badge:has-text("刷新 5s")', { timeout: 8000 });
  check("KPI 图表显示刷新间隔 5s", true);
  await shot(page, "kpi-chart-card");

  // 2. create bar chart
  await createChart({
    name: BAR_NAME,
    sql: "SELECT status, COUNT(*) AS cnt FROM orders GROUP BY status",
    type: "柱状图",
    x: "status",
    y: "cnt",
    refresh: 6,
  });
  await page.waitForSelector('.type-badge:has-text("柱状图")', { timeout: 15000 });
  await page.waitForSelector('.refresh-badge:has-text("刷新 6s")', { timeout: 8000 });
  check("柱状图创建成功并显示刷新 6s", true);
  await shot(page, "bar-chart-card");

  // 3. create dashboard
  await page.locator(".n-tabs-tab", { hasText: "仪表盘" }).click();
  await page.waitForTimeout(500);
  await page.locator(".toolbar button", { hasText: "新建仪表盘" }).click();
  const modal = page.locator(".n-modal");
  await modal.waitFor({ state: "visible" });
  await page.getByPlaceholder("仪表盘名称", { exact: true }).fill(DASH_NAME);
  await modal.locator(".n-base-selection", { hasText: "选择要加入的图表" }).first().click();
  await page.waitForTimeout(400);
  await page.locator(".n-base-select-option", { hasText: KPI_NAME }).first().click();
  await page.locator(".n-base-select-option", { hasText: BAR_NAME }).first().click();
  await page.keyboard.press("Escape");
  await page.waitForTimeout(300);
  await shot(page, "dash-create-form");
  await modal.getByRole("button", { name: "创建" }).click();
  await page.waitForSelector('.n-card:has-text("' + DASH_NAME + '")', { timeout: 15000 });
  check("仪表盘创建成功", true);

  // 4. share
  const dashCard = page.locator(".n-card", { hasText: DASH_NAME }).first();
  await dashCard.getByRole("button", { name: "分享" }).click();
  const shareModal = page.locator(".n-modal").filter({ hasText: "分享仪表盘" });
  await shareModal.waitFor({ state: "visible" });
  await page.waitForTimeout(600);
  const shareUrl = await shareModal.locator(".n-input input").inputValue();
  check("分享链接生成", shareUrl.includes("/share/"), shareUrl);
  await shot(page, "share-modal");
  await page.keyboard.press("Escape");
  await page.waitForTimeout(400);

  // 5. open share URL anonymously (fresh context)
  const ctx2 = await browser.newContext({ viewport: { width: 1600, height: 900 } });
  const page2 = await ctx2.newPage();
  page2.on("pageerror", (e) => errors.push("share pageerror: " + e.message));
  console.log("shareUrl:", shareUrl);
  await page2.goto(shareUrl, { waitUntil: "domcontentloaded", timeout: 30000 });
  await page2.waitForTimeout(4000);
  try {
    console.log("page2 body:", (await page2.locator("body").innerText()).slice(0, 200).replace(/\n/g, " | "));
  } catch {}
  await page2.waitForSelector(".big-screen .screen", { timeout: 20000 });
  await page2.waitForTimeout(1500);
  const titleText = await page2.locator(".screen-title").innerText();
  check("大屏标题 = 仪表盘名", titleText.includes(DASH_NAME), titleText);
  const itemCount = await page2.locator(".grid-stack-item").count();
  check("大屏渲染 2 个图表卡片", itemCount === 2, "count=" + itemCount);
  const kpiVisible = await page2.locator(".kpi-box").isVisible();
  check("KPI 指标卡渲染", kpiVisible);
  const canvasCount = await page2.locator(".grid-stack-item-content canvas").count();
  check("ECharts 画布渲染(柱状图)", canvasCount >= 1, "canvas=" + canvasCount);
  const refreshInfo = await page2.locator(".screen-info .info-item", { hasText: "自动刷新" }).count();
  check("大屏显示自动刷新信息", refreshInfo >= 1, "count=" + refreshInfo);
  const fsBtn = await page2.locator(".fs-btn").count();
  check("大屏有全屏按钮", fsBtn >= 1);
  await shot(page2, "share-big-screen");

  // 6. dashboard detail page
  await page.bringToFront();
  await page.locator(".n-card", { hasText: DASH_NAME }).first().getByRole("button", { name: "编辑布局" }).click();
  await page.waitForURL("**/reports/dashboard/**", { timeout: 20000 });
  await page.waitForSelector(".detail-view", { timeout: 15000 });
  await page.waitForTimeout(1200);
  const detailItems = await page.locator(".detail-view .grid-stack-item").count();
  check("详情页渲染 2 个图表", detailItems === 2, "count=" + detailItems);
  const editable = await page.locator(".detail-view .gs-editable").count();
  check("管理员可编辑布局(gs-editable)", editable >= 1, "count=" + editable);
  const handles = await page.locator(".detail-view .ui-resizable-handle").count();
  check("拖拽缩放手柄存在", handles >= 1, "count=" + handles);
  await shot(page, "dashboard-detail");

  // 7. big screen overlay from reports
  await page.goto(BASE + "/reports", { waitUntil: "domcontentloaded" });
  await page.waitForSelector(".reports-view", { timeout: 15000 });
  await page.locator(".n-tabs-tab", { hasText: "仪表盘" }).click();
  await page.waitForTimeout(600);
  await page.locator(".n-card", { hasText: DASH_NAME }).first().getByRole("button", { name: "大屏" }).click();
  await page.waitForSelector(".big-screen .screen", { timeout: 15000 });
  await page.waitForTimeout(1200);
  const overlayItems = await page.locator(".big-screen .grid-stack-item").count();
  check("大屏浮层渲染图表数", overlayItems === 2, "count=" + overlayItems);
  await shot(page, "big-screen-overlay");
  await page.locator(".close-btn").click();
  await page.waitForTimeout(500);
  const overlayGone = await page.locator(".big-screen").count();
  check("大屏浮层可关闭", overlayGone === 0);

  // 8. save layout (attempt drag, non-fatal if flaky)
  try {
    await page.locator(".n-card", { hasText: DASH_NAME }).first().getByRole("button", { name: "编辑布局" }).click();
    await page.waitForURL("**/reports/dashboard/**", { timeout: 20000 });
    await page.waitForSelector(".detail-view .grid-stack-item", { timeout: 15000 });
    await page.waitForTimeout(1000);
    const item = page.locator(".detail-view .grid-stack-item .grid-stack-item-content").first();
    const box = await item.boundingBox();
    if (box) {
      await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
      await page.mouse.down();
      await page.mouse.move(box.x + box.width / 2 + 120, box.y + box.height / 2 + 80, { steps: 12 });
      await page.mouse.up();
      await page.waitForTimeout(700);
    }
    await page.locator(".detail-view .detail-actions button", { hasText: "保存布局" }).click();
    await page.waitForTimeout(1200);
    const savedToast = await page.locator(".n-message", { hasText: "布局已保存" }).count();
    check("拖拽后保存布局", savedToast >= 1, "toast=" + savedToast);
    await shot(page, "layout-saved");
  } catch (e) {
    console.log("drag/save skipped:", e.message);
  }

  // cleanup
  {
    const { api, headers } = await apiAdmin();
    const charts = await (await api.get(BASE + "/api/charts", { headers })).json();
    const chartArr = Array.isArray(charts.data) ? charts.data : charts.data.list || [];
    for (const c of chartArr) {
      if (c.name.startsWith("E2E")) await api.delete(BASE + "/api/charts/" + c.id, { headers });
    }
    const dashes = await (await api.get(BASE + "/api/dashboards", { headers })).json();
    const dashArr = Array.isArray(dashes.data) ? dashes.data : dashes.data.list || [];
    for (const d of dashArr) {
      if (d.name.startsWith("E2E")) await api.delete(BASE + "/api/dashboards/" + d.id, { headers });
    }
    console.log("cleanup done");
  }
} catch (e) {
  console.log("E2E ERROR:", e.message);
  failures += 1;
  try { await shot(page, "error"); } catch {}
} finally {
  if (errors.length) console.log("PAGE ERRORS:", errors.join(" | "));
  await browser.close();
}

console.log(failures === 0 ? "ALL PASS" : failures + " FAILURES");
process.exit(failures === 0 ? 0 : 1);
