// Headless screenshots of the v2 store (never opens a window). Usage:
//   (vite running) node scripts/shoot3d.mjs <outDir> [baseUrl]
import { chromium } from "playwright-core";
import { existsSync, mkdirSync, readdirSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

const out = process.argv[2] ?? "shots-3d";
const base = process.argv[3] ?? "http://127.0.0.1:5191/";
mkdirSync(out, { recursive: true });

export function chromiumPath() {
  const cache = join(homedir(), "Library/Caches/ms-playwright");
  for (const d of readdirSync(cache).filter((x) => x.startsWith("chromium_headless_shell-")).sort().reverse())
    for (const sub of readdirSync(join(cache, d))) {
      const p = join(cache, d, sub, "chrome-headless-shell");
      if (existsSync(p)) return p;
    }
}

const SHOTS = (process.env.SHOTS ?? "").split(",").filter(Boolean);
const all = [
  ["orbit-2030-busy", "m=1&t=20:30&cam=orbit&paused=1"],
  ["fps-2030", "m=1&t=20:30&cam=fps&paused=1"],
  ["storefront-dusk", "m=1&t=18:05&cam=street&paused=1"],
  ["storefront-night", "m=1&t=20:40&cam=street&paused=1"],
  ["rain-competitor", "m=3&t=21:10&cam=orbit&weather=rain&competitor=1&paused=1"],
];
const browser = await chromium.launch({ headless: true, executablePath: chromiumPath(), args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader"] });
const errors = [];
for (const [name, q] of all.filter(([n]) => !SHOTS.length || SHOTS.includes(n))) {
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  page.on("pageerror", (e) => errors.push(`${name}: ${e.message}`));
  page.on("console", (m) => m.type() === "error" && errors.push(`${name}: ${m.text()}`));
  await page.goto(`${base}#/store?${q}`);
  await page.waitForSelector("#s3-canvas canvas", { timeout: 60000 });
  await page.waitForTimeout(Number(process.env.WAIT ?? 4000));
  await page.screenshot({ path: join(out, `${name}.png`) });
  await page.close();
  console.log("shot", name);
}
await browser.close();
if (errors.length) console.log("ERRORS\n" + errors.join("\n"));
