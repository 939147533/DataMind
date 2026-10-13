import { chromium } from "playwright";
import fs from "node:fs";

const BASE = "http://127.0.0.1:5174";
const OUT_DIR = "E:/视频及材料/recording/scene11_rec";
fs.mkdirSync(OUT_DIR, { recursive: true });

const browser = await chromium.launch({ channel: 'chrome', headless: true });
const context = await browser.newContext({
  viewport: { width: 1920, height: 1080 },
  recordVideo: {
    dir: OUT_DIR,
    size: { width: 1920, height: 1080 },
  },
  acceptDownloads: true,
});
const page = await context.newPage();
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

try {
  await page.goto(BASE + "/login", { waitUntil: "domcontentloaded", timeout: 30000 });
  await page.waitForSelector(".login-card", { timeout: 20000 });
  await sleep(1200);

  await page.getByPlaceholder("请输入用户名").fill("tec_que_01");
  await sleep(500);
  await page.getByPlaceholder("请输入密码").fill("123456");
  await sleep(600);
  await page.getByRole("button", { name: "登 录" }).click();
  await page.waitForFunction(() => document.body.innerText.includes("登录成功") || location.pathname === "/workspace", null, { timeout: 20000 });
  await sleep(1800);

  if (!page.url().includes("/workspace")) {
    await page.goto(BASE + "/workspace", { waitUntil: "domcontentloaded", timeout: 20000 });
  }
  await page.waitForSelector(".workspace-view", { timeout: 20000 });
  await sleep(1000);

  // 选择本地演示库
  await page.locator(".n-base-selection").filter({ hasText: "选择数据源" }).first().click();
  await sleep(500);
  await page.locator(".n-base-select-option").filter({ hasText: "本地演示库" }).first().click();
  await sleep(1800);

  // 只读查询
  const readSql = "SELECT id, name, stock FROM products LIMIT 10;";
  await page.locator(".cm-content").click();
  await page.keyboard.press("ControlOrMeta+a");
  await page.keyboard.type(readSql, { delay: 35 });
  await sleep(900);
  await page.getByRole("button", { name: "▶ 执行" }).click();
  await page.waitForFunction(() => document.body.innerText.includes("共10行") || document.body.innerText.includes("共 10 行"), null, { timeout: 20000 });
  await sleep(3500);

  // UPDATE 拦截
  const updateSql = "UPDATE products SET stock = stock + 1 WHERE id = 1;";
  await page.locator(".cm-content").click();
  await page.keyboard.press("ControlOrMeta+a");
  await page.keyboard.type(updateSql, { delay: 30 });
  await sleep(700);
  await page.getByRole("button", { name: "▶ 执行" }).click();
  await page.waitForFunction(() => document.body.innerText.includes("无权限执行该操作"), null, { timeout: 20000 });
  await sleep(4500);

  // CREATE TABLE 拦截
  const createSql = "CREATE TABLE demo_test (id INTEGER);";
  await page.locator(".cm-content").click();
  await page.keyboard.press("ControlOrMeta+a");
  await page.keyboard.type(createSql, { delay: 30 });
  await sleep(700);
  await page.getByRole("button", { name: "▶ 执行" }).click();
  await page.waitForFunction(() => document.body.innerText.includes("无权限执行该操作"), null, { timeout: 20000 });
  await sleep(4500);

  console.log("SCENE11_RECORD_OK", page.url());
} catch (e) {
  console.error("SCENE11_RECORD_FAIL", e);
  await page.screenshot({ path: "E:/视频及材料/recording/scene11_rec/error.png", fullPage: false });
  throw e;
} finally {
  await context.close();
  await browser.close();
}

