// Headless end-to-end check against the LIVE API + web dev server (never opens a window):
// map, store, 사건 SH03, 사장님의 선택 reprice, 정산 (one full month), 다음 달 SH03 reprice, 사장님에게 묻기.
// Asserts the chat answer on screen is the API's /chat response (mock backend), not the offline fallback.
// Usage: node tests/e2e/game_chat.mjs [webUrl] [outDir]   (scripts/e2e.sh starts and stops the servers)
import { existsSync, mkdirSync, readdirSync } from "node:fs";
import { homedir } from "node:os";
import { join, resolve } from "node:path";
import { pathToFileURL } from "node:url";

const repo = resolve(new URL("../..", import.meta.url).pathname);
const { chromium } = await import(pathToFileURL(join(repo, "web/node_modules/playwright-core/index.mjs")).href);
const base = process.argv[2] ?? "http://127.0.0.1:5173/";
const out = process.argv[3];
if (out) mkdirSync(out, { recursive: true });

// Headless shell from the Playwright cache (macOS, Linux, Windows), or PLAYWRIGHT_CHROMIUM. Install once with
// `cd web && npx playwright-core install chromium --only-shell`. Undefined = Playwright's own default.
function chromiumPath() {
  if (process.env.PLAYWRIGHT_CHROMIUM) return process.env.PLAYWRIGHT_CHROMIUM;
  const caches = [join(homedir(), "Library/Caches/ms-playwright"), join(homedir(), ".cache/ms-playwright"),
    join(process.env.LOCALAPPDATA ?? "", "ms-playwright")];
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
const browser = await chromium.launch({ headless: true, executablePath: chromiumPath(),
  args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader"] });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
const snap = async (name) => out && page.screenshot({ path: join(out, `${name}.png`) });
let step = "start";
const at = (name) => { step = name; };

try {
  at("open map"); await page.goto(base + "#/v1", { waitUntil: "networkidle" });   // v1 game; #/ is v2 now
  at("enter store"); await page.getByRole("button", { name: "가게로 들어가기" }).click();
  await page.waitForSelector(".g-stage canvas", { timeout: 30000 });
  at("draw event"); await page.getByRole("button", { name: "이번 달 사건 뽑기" }).click();
  at("pick SH03"); await page.click("[data-shock=SH03]");
  at("to choices"); await page.getByRole("button", { name: "사장님의 선택" }).click();
  at("choose reprice"); await page.click("[data-action=reprice]");
  at("skip to settlement"); await page.getByRole("button", { name: "정산으로 건너뛰기" }).click();
  await page.waitForSelector("[data-testid=settlement]");
  await snap("e2e-01-settlement");

  // month 2 (season mode: the reprice card is already applied and keeps the lever), then ask the owner
  at("next month"); await page.getByRole("button", { name: "다음 달" }).click();
  at("month 2 pick SH03"); await page.click("[data-shock=SH03]");
  at("month 2 choices"); await page.getByRole("button", { name: "사장님의 선택" }).click();
  at("month 2 reprice"); await page.click("[data-action=reprice]");
  at("open chat"); await page.getByRole("button", { name: "사장님에게 묻기" }).click();
  // preset chip (text identical to agents.prewarm); free typing is hidden while the API backend is mock
  const question = "돼지고기 값이 오르면 어떻게 하실 건가요?";
  await page.waitForSelector(".g-chat .g-chip");
  await page.waitForFunction(() => document.querySelector("[data-testid=chat-mode]")?.dataset.mode !== "checking"
    || document.querySelector(".g-chat input"));
  const [resp] = await Promise.all([
    page.waitForResponse((r) => r.url().endsWith("/chat") && r.request().method() === "POST", { timeout: 20000 }),
    page.locator(".g-chip", { hasText: question }).click(),
  ]);
  const apiBase = process.env.E2E_API_BASE ?? base.replace(/:\d+\/?$/, ":8000");
  const health = await (await fetch(apiBase + "/health")).json().catch(() => ({}));
  if (health.backend === "mock") check((await page.locator(".g-chat input").count()) === 0, "free-text input shown in mock mode");
  const body = await resp.json();
  const sent = JSON.parse(resp.request().postData());
  await page.waitForSelector(".g-msg-owner:not(.g-typing)", { timeout: 20000 });
  await page.waitForTimeout(300);
  await snap("e2e-02-owner-chat");

  check(resp.status() === 200, `/chat status ${resp.status()}`);
  check(body.backend === "mock", `backend ${body.backend}`);
  check(sent.persona === "owner" && sent.message === question, "request persona/message");
  check(sent.context?.shock === "SH03" && sent.context?.action === "reprice", `context ${JSON.stringify(sent.context)}`);
  check((await page.locator(".g-offline").count()) === 0, "offline fallback was shown");
  const shown = await page.locator(".g-msg-owner p").last().innerText();
  check(shown === body.answer, "on-screen answer differs from the API answer");
  check(!/mock|가상 매장/.test(body.answer), "answer leaks mock/demo wording");
  check(body.numbers_from.some((x) => x.startsWith("sim SH03/reprice")), `numbers_from ${body.numbers_from}`);
  const src = await page.locator(".g-msg-src").last().innerText().catch(() => "");
  check(src.startsWith("출처"), "sources line missing under the answer");
  console.log("chat answer:", body.answer.slice(0, 160));
} catch (e) {
  failures.push(`flow error at "${step}": ${e.message.split("\n")[0]}`);
  await snap("e2e-error").catch(() => {});
} finally {
  await browser.close();
}
if (errors.length) console.log("PAGE ERRORS:\n" + errors.join("\n"));
console.log(failures.length ? "E2E FAIL:\n" + failures.join("\n") : "E2E PASS: one month played, owner chat answered by the API (mock)");
process.exitCode = failures.length ? 1 : 0;
