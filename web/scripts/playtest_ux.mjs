// First-time-player UX numbers for free play (headless, API needed). Plays N months at default speed without
// skipping, as a newcomer: answers the first question, guesses, answers every night card, reads the 정산.
// Reports clicks per month, seconds from landing to the first decision, the longest stretch of replay with no
// prompt (seconds), and how many decisions each month asked for.
// Usage: node scripts/playtest_ux.mjs <webUrl> [months]
import { chromium } from "playwright-core";
import { chromiumPath } from "./shoot3d-lib.mjs";

const [base, monthsArg] = process.argv.slice(2);
const MONTHS = Number(monthsArg ?? 2);
const browser = await chromium.launch({ headless: true, executablePath: chromiumPath(), args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader"] });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
let clicks = 0;
const click = async (sel) => { await page.click(sel); clicks++; };
const t0 = Date.now();
await page.goto(base + "#/?seed=11");
await page.waitForSelector("[data-testid=mode-free]");
await click("[data-testid=mode-free]");
await page.waitForSelector("[data-testid=first-question]", { timeout: 60000 });
const firstDecision = (Date.now() - t0) / 1000;
const rows = [];
for (let m = 1; m <= MONTHS; m++) {
  const c0 = clicks;
  let decisions = 0;
  await page.waitForSelector("[data-testid=plan-board]");
  if (m === 1) { await click("[data-answer] >> nth=0"); decisions++; }
  else { await click("[data-lever=staff_per_shift] button[aria-label$='늘리기']"); decisions++; }
  await page.waitForTimeout(800);
  await click("[data-testid=play]");
  await page.waitForSelector("[data-testid=guess]");
  await click("[data-guess=mid]"); decisions++;
  await page.waitForSelector("[data-testid=transport]", { timeout: 60000 });
  // watch the night at default speed; time the stretches with no prompt on screen
  let longest = 0, stretch = Date.now();
  for (;;) {
    if (await page.locator("[data-testid=settlement]").count()) { longest = Math.max(longest, (Date.now() - stretch) / 1000); break; }
    const card = page.locator("[data-testid=night-choice]");
    if (await card.count() && !(await card.locator("[aria-disabled=true]").count())) {
      longest = Math.max(longest, (Date.now() - stretch) / 1000);
      const id = await card.getAttribute("data-dp");
      await card.locator("[data-night-option] >> nth=0").click(); clicks++; decisions++;
      await page.waitForFunction((dp) => document.querySelector("[data-testid=night-choice]")?.getAttribute("data-dp") !== dp, id, { timeout: 60000 }).catch(() => {});
      stretch = Date.now();
      continue;
    }
    await page.waitForTimeout(200);
  }
  await page.waitForTimeout(2500); // read the 정산
  await click("[data-testid=next]");
  rows.push({ month: m, clicks: clicks - c0, decisions, longestPassiveReplay_s: Math.round(longest * 10) / 10 });
}
console.log(JSON.stringify({ secondsToFirstDecision: Math.round(firstDecision * 10) / 10, months: rows }, null, 1));
await browser.close();
