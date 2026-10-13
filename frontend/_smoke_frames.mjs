import { chromium } from "playwright";
import fs from "node:fs";
import path from "node:path";
const dir = "E:\\视频及材料\\recording\\smoke_frames";
fs.mkdirSync(dir, { recursive: true });
for (const f of fs.readdirSync(dir)) fs.rmSync(path.join(dir, f), { force: true });
const browser = await chromium.launch({ channel: "chrome", headless: true });
const context = await browser.newContext({ viewport: { width: 1920, height: 1080 }, acceptDownloads: true });
const page = await context.newPage();
await page.goto("http://127.0.0.1:5174", { waitUntil: "domcontentloaded", timeout: 60000 });
await page.waitForSelector(".login-card", { timeout: 30000 });
const t0 = Date.now();
let frames = 0;
for (let i = 0; i < 30; i++) {
  const s = Date.now();
  await page.screenshot({ path: path.join(dir, `${String(i).padStart(3, "0")}.jpg`), type: "jpeg", quality: 92 });
  const dt = Date.now() - s;
  frames++;
  console.log(`frame ${i} screenshot_ms=${dt}`);
  await new Promise((r) => setTimeout(r, Math.max(0, 100 - dt)));
}
console.log(`TOTAL_MS=${Date.now()-t0} FRAMES=${frames} AVG_MS=${((Date.now()-t0)/frames).toFixed(1)}`);
await browser.close();

