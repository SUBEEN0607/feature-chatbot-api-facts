// Headless check of the welcome tour (가게 둘러보기, web/src/v2/Tour.tsx) as a first-time visitor (never opens a window).
//   free skip:      자유 플레이 opens the tour first; Esc at stop 1 lands on the planning board, seen is remembered,
//                   a second start shows no tour, the HUD's 가게 둘러보기 replays it, 건너뛰기 ends the replay
//   free complete:  all seven stops (TOUR-SPEC.md), one guess each; buckets, question, headline, reveal, formula,
//                   parameter rows, sensitivity rows and the stop-7 waterfall equal web/public/data/tour.json, and the
//                   정답 tile is its answer_bucket;
//                   the last 계획 시작 lands on the planning board with the camera back on the diorama
//   guided complete: 시연 모드 the same way with NO API request
// Usage: node tests/e2e/tour.mjs [webUrl] [outDir]   (scripts/e2e.sh starts and stops the servers)
import { existsSync, mkdirSync, readFileSync, readdirSync } from "node:fs";
import { homedir } from "node:os";
import { join, resolve } from "node:path";
import { pathToFileURL } from "node:url";

const repo = resolve(new URL("../..", import.meta.url).pathname);
const { chromium } = await import(pathToFileURL(join(repo, "web/node_modules/playwright-core/index.mjs")).href);
const base = process.argv[2] ?? "http://127.0.0.1:5173/";
const out = process.argv[3] || undefined;
if (out) mkdirSync(out, { recursive: true });
const pub = (f) => JSON.parse(readFileSync(join(repo, "web/public", f), "utf8"));

function chromiumPath() {
  if (process.env.PLAYWRIGHT_CHROMIUM) return process.env.PLAYWRIGHT_CHROMIUM;
  const caches = [join(homedir(), "Library/Caches/ms-playwright"), join(homedir(), ".cache/ms-playwright"), join(process.env.LOCALAPPDATA ?? "", "ms-playwright")];
  for (const cache of caches.filter(existsSync))
    for (const d of readdirSync(cache).filter((x) => x.startsWith("chromium_headless_shell-")).sort().reverse())
      for (const sub of readdirSync(join(cache, d)))
        for (const exe of ["chrome-headless-shell", "chrome-headless-shell.exe"]) {
          const p = join(cache, d, sub, exe);
          if (existsSync(p)) return p;
        }
  return undefined;
}

const failures = [];
const check = (cond, msg) => { if (!cond) failures.push(msg); };
const near = (a, b) => Math.abs(Number(a) - Number(b)) < 1;
const browser = await chromium.launch({ headless: true, executablePath: chromiumPath(), args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader"] });
let step = "start";
const at = (s) => { step = s; };
let shotN = 0;
const snap = async (page, name) => out && page.screenshot({ path: join(out, `tour-${String(++shotN).padStart(2, "0")}-${name}.png`) });
async function newPage() {
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } }); // a fresh context: nothing in localStorage
  page.errors = [];
  page.on("pageerror", (e) => page.errors.push(e.message));
  return page;
}

// every card number comes from web/public/data/tour.json (make tour), so the run checks the screen against it
const tour = pub("data/tour.json");

// one full tour, guessing bucket (i % 4)
async function playThrough(page, label) {
  check(tour.events.length === 0 && (await page.innerText("[data-testid=tour-baseline]")).includes(tour.baseline_ko), `${label}: baseline label not the event-free month`);
  const n = await page.locator(".v2-tour-stops li").count();
  check(n === tour.stops.length, `${label}: ${n} stops on screen, tour.json has ${tour.stops.length}`);
  for (let i = 0; i < n; i++) {
    const want = tour.stops[i];
    at(`${label}: stop ${i + 1} guess`);
    await page.waitForSelector(`[data-testid=tour][data-anchor=${want.anchor}][data-phase=guess]`, { timeout: 20000 });
    const opts = await page.$$eval(".v2-tour-opt span:first-child", (els) => els.map((e) => e.textContent.trim()));
    check(JSON.stringify(opts) === JSON.stringify(want.buckets.map((b) => b.label_ko)), `${label} ${want.anchor}: buckets ${JSON.stringify(opts)}`);
    check((await page.innerText(".v2-tour-owner")).includes(want.question_ko), `${label} ${want.anchor}: question not tour.json's`);
    check(await page.locator("[data-testid=tour-prelim]").count() === (want.preliminary ? 1 : 0), `${label} ${want.anchor}: PRELIMINARY badge != preliminary`);
    if (want.anchor !== "room") check(await page.locator("[data-testid=tour-callout]").count() === 1, `${label} ${want.anchor}: no world callout`);
    if (i === 0) await snap(page, `${label}-guess`);
    await page.keyboard.press(String((i % 4) + 1));
    at(`${label}: stop ${i + 1} (${want.anchor}) reveal`);
    await page.waitForSelector("[data-testid=tour][data-phase=reveal]");
    const right = await page.$eval(".v2-tour-opt.right", (el) => Number(el.dataset.option));
    check(right === want.answer_bucket, `${label} ${want.anchor}: 정답 tile ${right} != answer_bucket ${want.answer_bucket}`);
    check((await page.innerText(".v2-tour-val .display")).trim() === want.display_ko, `${label} ${want.anchor}: headline != display_ko`);
    check((await page.innerText("[data-testid=tour-reveal]")).trim() === want.reveal_ko, `${label} ${want.anchor}: reveal != reveal_ko`);
    if (want.formula_ko) check((await page.innerText("[data-testid=tour-formula]")).includes(want.formula_ko), `${label} ${want.anchor}: formula`);
    if (want.side !== "result") {
      const rows = await page.$$eval("[data-testid=tour-params] [data-param]", (els) => els.map((e) => [e.dataset.param, e.querySelector(".v").textContent.trim()]));
      check(JSON.stringify(rows) === JSON.stringify(want.params.map((p) => [p.criterion_id, p.display_ko])), `${label} ${want.anchor}: parameter rows ${JSON.stringify(rows)}`);
      check(await page.locator("[data-testid=tour-sens] [data-lever]").count() === want.sensitivity.length, `${label} ${want.anchor}: sensitivity rows`);
    } else {
      const lines = await page.$$eval("[data-testid=tour-waterfall] [data-line]", (els) => els.map((e) => [e.dataset.line, Number(e.dataset.v)]));
      const p = tour.pnl;
      const exp = [["revenue", p.revenue], ...["cogs", "labor", "rent", "mgmt", "fees"].map((k) => [k, -p.lines[k]]), ["op", p.op]];
      check(lines.length === 7 && lines.every(([k, v], j) => k === exp[j][0] && Math.abs(v - exp[j][1]) <= 1), `${label}: waterfall ${JSON.stringify(lines)}`);
      await snap(page, `${label}-pnl`);
    }
    if (i === 1) await snap(page, `${label}-reveal`);
    await page.click("[data-testid=tour-next]");
  }
}

async function landsOnPlan(page, label, selector) {
  at(`${label}: back to the planning view`);
  await page.waitForSelector("[data-testid=tour]", { state: "detached", timeout: 10000 });
  await page.waitForSelector(selector, { timeout: 30000 });
  check(await page.evaluate(() => window.__v2?.tour === false && window.__v2?.phase === "plan"), `${label}: __v2 not in plan without the tour`);
  check(await page.evaluate(() => localStorage.getItem("v2-tour-done")) === "1", `${label}: seen not stored`);
  check(await page.locator("[data-testid=hud-prelim]").count() === 1, `${label}: HUD has no PRELIMINARY badge`);
}

try {
  // 1. 자유 플레이: Esc at the first stop, then the replay and 건너뛰기
  {
    const page = await newPage();
    at("free skip: home"); await page.goto(base + "#/?seed=7", { waitUntil: "load" });
    await page.click("[data-testid=mode-free]");
    await page.waitForSelector("[data-testid=tour] .v2-tour-stops li.now", { timeout: 90000 });
    check(await page.locator("[data-testid=plan-board]").count() === 0, "free skip: the planning board shows under the tour");
    await page.waitForSelector("[data-testid=tour][data-phase=guess]", { timeout: 10000 });
    await page.keyboard.press("Escape");
    await landsOnPlan(page, "free skip", "[data-testid=plan-board]");
    await snap(page, "free-after-skip");
    at("free skip: second start shows no tour");
    await page.click("text=처음으로");
    await page.click("[data-testid=mode-free]");
    await page.waitForSelector("[data-testid=plan-board]", { timeout: 90000 });
    await page.waitForTimeout(1500);
    check(await page.locator("[data-testid=tour]").count() === 0, "free skip: the tour came back after it was seen");
    at("free skip: replay from the HUD");
    await page.click("[data-testid=tour-replay]");
    await page.waitForSelector("[data-testid=tour] .v2-tour-stops li.now");
    await page.click("[data-testid=tour-skip]");
    await page.waitForSelector("[data-testid=tour]", { state: "detached" });
    await page.waitForSelector("[data-testid=plan-board]");
    check(page.errors.length === 0, `free skip: page errors ${page.errors.join(" | ")}`);
    await page.close();
  }
  // 2. 자유 플레이: complete, numbers from the live season
  {
    const page = await newPage();
    at("free complete: home"); await page.goto(base + "#/?seed=7", { waitUntil: "load" });
    await page.click("[data-testid=mode-free]");
    await page.waitForSelector("[data-testid=tour]", { timeout: 90000 });
    await playThrough(page, "free");
    await landsOnPlan(page, "free complete", "[data-testid=plan-board]");
    at("free complete: the board explains the jump from the tour's 영업이익");
    await page.waitForSelector("[data-testid=vs-baseline-month]", { timeout: 90000 });
    const vb = await page.$eval("[data-testid=vs-baseline-month]", (el) => ({ ...el.dataset, text: el.textContent }));
    check(Math.abs(Number(vb.baseOp) - tour.pnl.op) <= 1 && vb.text.includes(tour.baseline_ko), `free complete: 평소 달 line ${JSON.stringify(vb)} != tour op ${tour.pnl.op}`);
    await page.waitForTimeout(1600); // camera flight home
    await snap(page, "free-after-complete");
    check(page.errors.length === 0, `free complete: page errors ${page.errors.join(" | ")}`);
    await page.close();
  }
  // 3. 시연 모드: complete with the API never called
  {
    const page = await newPage();
    const apiCalls = [];
    page.on("request", (r) => { if (/:(8\d{3})\//.test(r.url())) apiCalls.push(r.url()); });
    at("guided complete: home"); await page.goto(base + "#/", { waitUntil: "load" });
    await page.click("[data-testid=mode-guided]");
    await page.waitForSelector("[data-testid=tour]", { timeout: 30000 });
    await playThrough(page, "guided");
    await landsOnPlan(page, "guided complete", "[data-testid=narration]");
    check(apiCalls.length === 0, `guided: the tour called the API: ${apiCalls.slice(0, 3).join(", ")}`);
    check(page.errors.length === 0, `guided complete: page errors ${page.errors.join(" | ")}`);
    await page.close();
  }
} catch (e) {
  failures.push(`${step}: ${e.message.split("\n")[0]}`);
} finally {
  await browser.close();
}
if (failures.length) {
  console.log(`tour e2e FAILED (${failures.length})`);
  for (const f of failures) console.log(" -", f);
  process.exit(1);
}
console.log("tour e2e ok: free skip + replay, free complete (tour.json), guided complete (offline)");
