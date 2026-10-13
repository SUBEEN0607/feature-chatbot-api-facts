// Ad-hoc headless screenshots of the v2 game (dev aid). Usage: node scripts/peek.mjs <outDir> <base> <steps-json>
import { chromium } from "playwright-core";
import { mkdirSync } from "node:fs";
import { join } from "node:path";
import { chromiumPath } from "./shoot3d-lib.mjs";

const [out, base, stepsArg] = process.argv.slice(2);
mkdirSync(out, { recursive: true });
const steps = JSON.parse(stepsArg);
const vp = steps.viewport ?? { width: 1440, height: 900 };
const browser = await chromium.launch({ headless: true, executablePath: chromiumPath(), args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader"] });
const page = await browser.newPage({ viewport: vp });
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
await page.goto(base + (steps.hash ?? "#/"));
for (const s of steps.do) {
  if (s.click) await page.click(s.click, { timeout: 30000 });
  if (s.hover) await page.hover(s.hover, { timeout: 30000 });
  if (s.wait) await page.waitForSelector(s.wait, { timeout: 60000 });
  if (s.ms) await page.waitForTimeout(s.ms);
  if (s.eval) await page.evaluate(s.eval);
  if (s.shot) await page.screenshot({ path: join(out, s.shot + ".png"), fullPage: false });
}
await browser.close();
console.log(errors.length ? "ERRORS:\n" + errors.join("\n") : "no page errors");
