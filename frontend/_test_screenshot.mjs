import { chromium } from "playwright";
const browser = await chromium.launch({ channel: "chrome", headless: true });
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
await page.goto("http://127.0.0.1:5174", { waitUntil: "domcontentloaded" });
await page.waitForSelector(".login-card");
await page.screenshot({ path: "E:\\视频及材料\\recording\\pw_screenshot_test.png", type: "png" });
await browser.close();
console.log("done");
