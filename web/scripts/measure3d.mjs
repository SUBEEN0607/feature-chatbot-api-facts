// How much of the 3D store changes when the player moves levers (headless). Free play on the API, planning view
// paused at 20:30, the 3D area between the side panels captured before and after each lever change.
// Usage: node scripts/measure3d.mjs <outDir> <webUrl>   then: python3 scripts/diff3d.py <outDir>
import { chromium } from "playwright-core";
import { mkdirSync } from "node:fs";
import { join } from "node:path";
import { chromiumPath } from "./shoot3d-lib.mjs";

const [out, base] = process.argv.slice(2);
mkdirSync(out, { recursive: true });
const browser = await chromium.launch({ headless: true, executablePath: chromiumPath(), args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader"] });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
await page.goto(base + "#/?tutorial=0&seed=11&unlock=1&t=20:30&paused=1" + (process.env.NOFOCUS ? "&nofocus=1" : ""));
await page.click("[data-testid=mode-free]");
await page.waitForSelector("[data-testid=plan-board]");
const clip = { x: 420, y: 110, width: 660, height: 620 };
const shot = async (name) => { await page.waitForTimeout(Number(process.env.SETTLE ?? 2500)); await page.screenshot({ path: join(out, `${name}.png`), clip }); };
const steps = [
  ["noise", async () => {}],
  ["meat_price", async () => page.$eval("input[data-lever=meat_price]", (el) => { Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set.call(el, "21000"); el.dispatchEvent(new Event("input", { bubbles: true })); })],
  ["staff", async () => page.click("[data-lever=staff_per_shift] button[aria-label$='늘리기']")],
  ["banchan", async () => { await page.click("[data-lever=banchan] button[aria-label$='늘리기']"); await page.click("[data-lever=banchan] button[aria-label$='늘리기']"); }],
  ["grade", async () => page.click("[data-lever=meat_grade] button:has-text('숙성')")],
  ["terrace", async () => page.click("button[data-lever=terrace]")],
];
await shot("00-base");
for (const [name, act] of steps) {
  await page.evaluate(() => window.__v2?.setTime(210));
  await shot(`${name}-a`);
  await act();
  await page.evaluate(() => window.__v2?.setTime(210));
  await shot(`${name}-b`);
}
await browser.close();
