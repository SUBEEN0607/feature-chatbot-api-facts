// Headless check that the v2 game works with no WebGL (never opens a window). A browser that cannot create a WebGL
// context used to blank the whole page: R3F's <Canvas> threw and React unmounted the root. Two ways to lose WebGL:
//   off:    Chromium launched with --disable-webgl --disable-gpu, so every getContext("webgl*") is null
//           (GLGuard's up-front probe sees it and three.js never loads)
//   throws: the probe's context is real, every later one is null, so the store canvas itself throws
//           "Error creating WebGL context" (GLGuard's error boundary catches it)
// Each run, as a first-time visitor: home shows the fallback note and the start buttons; 시연 모드 opens the welcome
// tour and its first card takes a guess and reveals; Esc lands on the narration; 자유 플레이 plays one month to its 정산.
// Usage: node tests/e2e/no_webgl.mjs [webUrl] [outDir]   (scripts/e2e.sh starts and stops the servers)
import { existsSync, mkdirSync, readdirSync } from "node:fs";
import { homedir } from "node:os";
import { join, resolve } from "node:path";
import { pathToFileURL } from "node:url";

const repo = resolve(new URL("../..", import.meta.url).pathname);
const { chromium } = await import(pathToFileURL(join(repo, "web/node_modules/playwright-core/index.mjs")).href);
const base = process.argv[2] ?? "http://127.0.0.1:5173/";
const out = process.argv[3] || undefined;
if (out) mkdirSync(out, { recursive: true });
const NOTE = "이 브라우저에서 3D 화면을 켤 수 없습니다";

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
let step = "start";
const at = (s) => { step = s; };
const snap = async (page, name) => out && page.screenshot({ path: join(out, `nogl-${name}.png`) });

// the first getContext("webgl*") on the page (GLGuard's probe) is real, every later one fails like a dead GPU
function failAfterProbe() {
  const orig = HTMLCanvasElement.prototype.getContext;
  let probed = false;
  HTMLCanvasElement.prototype.getContext = function (type, ...rest) {
    if (/webgl/.test(String(type))) {
      if (probed) return null;
      probed = true;
    }
    return orig.call(this, type, ...rest);
  };
}

const GUESSES = ["mid", "low", "high", "loss"];
async function driveNight(page) {
  for (let i = 0; i < 40; i++) {
    if (await page.locator("[data-testid=settlement]").count()) return;
    const card = page.locator("[data-testid=night-choice]");
    if (await card.count()) {
      if (await card.locator("[aria-disabled=true]").count()) { await page.waitForTimeout(500); continue; }
      const id = await card.getAttribute("data-dp");
      await card.locator("[data-night-option] >> nth=0").click({ timeout: 5000 }).catch(() => {});
      await page.waitForFunction((dp) => document.querySelector("[data-testid=night-choice]")?.getAttribute("data-dp") !== dp
        || document.querySelector("[data-testid=night-choice] [aria-disabled=true]"), id, { timeout: 15000 }).catch(() => {});
      continue;
    }
    const skip = page.locator("[data-testid=skip]");
    if (await skip.count()) await skip.click().catch(() => {});
    await page.waitForTimeout(400);
  }
  throw new Error("night never reached the 정산");
}

async function run(label, launchArgs, init) {
  const browser = await chromium.launch({ headless: true, executablePath: chromiumPath(), args: launchArgs });
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 900 } }); // fresh context: the tour has not been seen
    const errors = [];
    page.on("pageerror", (e) => errors.push(e.message));
    if (init) await page.addInitScript(init);

    at(`${label}: home`);
    await page.goto(base + "#/?seed=7", { waitUntil: "load" });
    await page.waitForSelector("[data-testid=mode-guided]", { timeout: 30000 });
    if (label === "off") check(await page.evaluate(() => { const c = document.createElement("canvas"); return !c.getContext("webgl2") && !c.getContext("webgl"); }),
      "off: this Chromium still creates WebGL contexts, the run proves nothing");
    await page.waitForSelector("[data-testid=gl-fallback]", { timeout: 30000 });
    check((await page.innerText("[data-testid=gl-fallback]")).includes(NOTE), `${label}: fallback note text`);
    check(await page.locator("[data-testid=gl-fallback]").isVisible(), `${label}: fallback note not visible`);
    check(await page.locator("canvas").count() === 0, `${label}: a canvas is still on the home page`);
    for (const m of ["mode-guided", "mode-free", "mode-trial", "mode-compare"])
      check(await page.locator(`[data-testid=${m}]`).isVisible(), `${label}: ${m} button not visible`);
    await page.waitForTimeout(500);
    await snap(page, `${label}-home`);

    at(`${label}: 시연 모드 opens the welcome tour`);
    await page.click("[data-testid=mode-guided]");
    await page.waitForSelector("[data-testid=tour][data-phase=guess]", { timeout: 30000 });
    check(await page.locator(".v2-tour-card").isVisible(), `${label}: tour card not visible`);
    check(await page.locator(".v2-tour-opt").count() === 4, `${label}: tour card does not show four buckets`);
    check(await page.locator("[data-testid=gl-fallback]").count() === 1, `${label}: no fallback under the tour`);
    await snap(page, `${label}-tour`);
    await page.keyboard.press("1");
    await page.waitForSelector("[data-testid=tour][data-phase=reveal]", { timeout: 10000 });
    check((await page.innerText(".v2-tour-val .display")).trim().length > 0, `${label}: tour reveal shows no value`);
    at(`${label}: Esc ends the tour on the narration`);
    await page.keyboard.press("Escape");
    await page.waitForSelector("[data-testid=narration]", { timeout: 30000 });

    at(`${label}: 자유 플레이, one month to the 정산`);
    await page.click("text=처음으로");
    await page.click("[data-testid=mode-free]");
    await page.waitForSelector("[data-testid=plan-board]", { timeout: 90000 });
    check(await page.locator("[data-testid=tour]").count() === 0, `${label}: the tour came back after it was seen`);
    await page.click("[data-testid=play]");
    await page.waitForSelector("[data-testid=guess]");
    await page.click(`[data-testid=guess] [data-guess=${GUESSES[1]}]`);
    await page.waitForSelector("[data-testid=transport]", { timeout: 60000 });
    await driveNight(page);
    const op = await page.getAttribute("[data-testid=settle-op]", "data-value");
    check(op !== null && Number.isFinite(Number(op)), `${label}: 정산 has no operating profit (${op})`);
    check(await page.locator("[data-testid=gl-fallback]").count() === 1, `${label}: no fallback behind the 정산`);
    await snap(page, `${label}-settle`);
    check(errors.length === 0, `${label}: page errors ${[...new Set(errors)].join(" | ")}`);
  } catch (e) {
    failures.push(`${step}: ${e.message.split("\n")[0]}`);
  } finally {
    await browser.close();
  }
}

await run("off", ["--disable-webgl", "--disable-gpu"]);
await run("throws", ["--use-angle=swiftshader", "--enable-unsafe-swiftshader"], failAfterProbe);
if (failures.length) {
  console.log(`no-WebGL e2e FAILED (${failures.length})`);
  for (const f of failures) console.log(" -", f);
  process.exit(1);
}
console.log("no-WebGL e2e ok: WebGL off and canvas throws; home note, tour card, 시연 narration, a free month to its 정산");
