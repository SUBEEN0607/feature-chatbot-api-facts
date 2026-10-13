// Headless screenshots of the built app (never opens a visible window).
// Usage: npm run build && npx vite preview (port 4173) in another shell, then
//   node scripts/shoot.mjs <outDir> [baseUrl]
// Uses playwright-core with the locally cached headless Chromium (PW_CHROMIUM overrides the path).
import { chromium } from "playwright-core";
import { existsSync, mkdirSync, readdirSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

const out = process.argv[2] ?? "shots";
const base = process.argv[3] ?? "http://127.0.0.1:4173/";
mkdirSync(out, { recursive: true });

function findChromium() {
  if (process.env.PW_CHROMIUM) return process.env.PW_CHROMIUM;
  const cache = join(homedir(), "Library/Caches/ms-playwright");
  const dirs = existsSync(cache) ? readdirSync(cache).filter((d) => d.startsWith("chromium_headless_shell-")).sort().reverse() : [];
  for (const d of dirs) {
    for (const sub of readdirSync(join(cache, d))) {
      const p = join(cache, d, sub, "chrome-headless-shell");
      if (existsSync(p)) return p;
    }
  }
  return undefined;
}

const browser = await chromium.launch({
  headless: true,
  executablePath: findChromium(),
  args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"],
});

const errors = [];
async function shot(name, hash, { w = 1440, h = 900, full = false, replay = false } = {}) {
  const page = await browser.newPage({ viewport: { width: w, height: h }, deviceScaleFactor: 1 });
  page.on("pageerror", (e) => errors.push(`${name}: ${e.message}`));
  page.on("console", (m) => m.type() === "error" && errors.push(`${name}: ${m.text()}`));
  await page.goto(base + hash, { waitUntil: "networkidle" });
  await page.evaluate(() => document.fonts.ready);
  if (replay) {
    await page.waitForFunction(() => window.__replay?.ready === true, null, { timeout: 30000 });
    await page.waitForTimeout(2500);
  } else {
    await page.waitForTimeout(600);
  }
  await page.screenshot({ path: join(out, `${name}.png`), fullPage: full });
  await page.close();
  console.log("shot", name);
}

const only = process.env.ONLY;
const jobs = [
  ["replay-orbit-base-SH09-2030", "#/replay?scenario=SH09&variant=base&t=20:30&paused=1", { replay: true }],
  ["replay-orbit-shock-SH09-2030", "#/replay?scenario=SH09&variant=shock&t=20:30&paused=1", { replay: true }],
  ["replay-orbit-base-SH03-2030", "#/replay?scenario=SH03&variant=base&t=20:30&paused=1", { replay: true }],
  ["replay-fps-base-SH09-2030", "#/replay?scenario=SH09&variant=base&t=20:30&paused=1&cam=fps", { replay: true }],
  ["replay-orbit-base-390", "#/replay?scenario=SH09&variant=base&t=20:30&paused=1", { replay: true, w: 390, h: 844 }],
  ["home-1440", "#/", {}],
  ["A-1440", "#/a?shock=SH03", {}],
  ["A-1440-full", "#/a?shock=SH03", { full: true }],
  ["A-390-full", "#/a?shock=SH03", { w: 390, h: 844, full: true }],
  ["B-1440", "#/b?shock=SH09", {}],
  ["B-390-full", "#/b?shock=SH09", { w: 390, h: 844, full: true }],
  ["C-1440", "#/c?shock=SH11", {}],
  ["C-1440-full", "#/c?shock=SH11", { full: true }],
  ["C-390-full", "#/c?shock=SH11", { w: 390, h: 844, full: true }],
];
for (const [name, hash, opts] of jobs) {
  if (only && !name.includes(only)) continue;
  await shot(name, hash, opts);
}
await browser.close();
if (errors.length) {
  console.log("PAGE ERRORS:\n" + errors.join("\n"));
  process.exitCode = 1;
}
