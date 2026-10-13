// Headless playthrough of a full 6-month season (never opens a window). Asserts every on-screen number against
// web/public/runs (season grid + single-month files) and saves screenshots.
// Usage: (vite preview running on 4173) node scripts/playthrough.mjs <outDir> [baseUrl]
import { chromium } from "playwright-core";
import { existsSync, mkdirSync, readFileSync, readdirSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

const out = process.argv[2] ?? "shots-game";
const base = process.argv[3] ?? "http://127.0.0.1:4173/";
mkdirSync(out, { recursive: true });
const runs = (p) => JSON.parse(readFileSync(new URL(`../public/runs/${p}`, import.meta.url), "utf8"));
const index = runs("index.json");
const season = runs("season/index.json");
const baseFile = runs("base.json");
const grid = (state, shock) => runs(`season/${state}.json`).shocks[shock];

const man = (x) => `${(x / 10000).toLocaleString("ko-KR", { maximumFractionDigits: 0 })}만원`;
const failures = [];
const check = (cond, msg) => { if (!cond) failures.push(msg); };
const near = (a, b) => Math.abs(a - b) <= 1e-6 * Math.max(1, Math.abs(b));

function chromiumPath() {
  const cache = join(homedir(), "Library/Caches/ms-playwright");
  for (const d of readdirSync(cache).filter((x) => x.startsWith("chromium_headless_shell-")).sort().reverse())
    for (const sub of readdirSync(join(cache, d))) {
      const p = join(cache, d, sub, "chrome-headless-shell");
      if (existsSync(p)) return p;
    }
}
const browser = await chromium.launch({ headless: true, executablePath: chromiumPath(), args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader"] });
const errors = [];
async function newPage(w, h) {
  const page = await browser.newPage({ viewport: { width: w, height: h } });
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("console", (m) => m.type() === "error" && !/localhost:8000|ERR_CONNECTION_REFUSED/.test(m.text()) && errors.push(m.text()));
  return page;
}
const snap = (page, name, full = false) => page.screenshot({ path: join(out, `${name}.png`), fullPage: full });
const stage = async (page) => { await page.waitForSelector(".g-stage canvas", { timeout: 30000 }); await page.waitForTimeout(2500); };

async function assertSettle(page, rec) {
  for (const row of await page.$$("[data-testid=settlement] tbody tr")) {
    const kpi = await row.getAttribute("data-kpi");
    const want = { base: baseFile.kpis[kpi].p50, shocked: rec.shocked[kpi].p50, reacted: rec.reacted[kpi].p50 };
    for (const col of ["base", "shocked", "reacted"]) {
      const v = Number(await (await row.$(`td[data-col=${col}]`)).getAttribute("data-value"));
      check(near(v, want[col]), `month ${rec.m} ${kpi} ${col}: screen ${v} vs json ${want[col]}`);
    }
  }
  const op = await page.locator("[data-testid=settlement] tr[data-kpi=op] td[data-col=reacted]").innerText();
  check(op === man(rec.reacted.op.p50), `month ${rec.m} OP text ${op}`);
}

// plays one month: pick shock, check choice cards, choose, skip to settlement, assert
let state = season.base_state;
let cumulative = 0;
const months = [];
async function month(page, m, shock, action, shots = {}) {
  await page.waitForSelector("[data-shock]");
  if (shots.events) await snap(page, shots.events);
  await page.click(`[data-shock=${shock}]`);
  await page.waitForSelector(".g-impact");
  await page.waitForTimeout(900);
  const before = grid(state, shock);
  if (state === season.base_state) {
    const h = await page.locator("[data-testid=shock-headline]").innerText();
    check(h === runs(`${shock}/absorb.json`).shock_headline, `month ${m} shock headline differs from runs/${shock}/absorb.json`);
  }
  if (shots.impact) await snap(page, shots.impact);
  await page.getByRole("button", { name: "사장님의 선택" }).click();
  await page.waitForSelector(".g-choices");
  await page.waitForTimeout(300);
  for (const card of await page.$$(".g-choice-card")) {
    const a = await card.getAttribute("data-action");
    const next = season.transitions[state][a];
    const want = grid(next, shock).kpis.op.p50;
    check(near(Number(await card.getAttribute("data-op")), want), `month ${m} choice ${a} op vs grid ${next}`);
    check((await card.getAttribute("data-applied")) === String(a !== "absorb" && next === state), `month ${m} choice ${a} applied state`);
    const badge = await page.$(`.g-card-wrap:has([data-action=${a}]) .g-badge`);
    check(Boolean(badge) === Boolean(index.actions[a].evidence.needs_interview), `month ${m} badge on ${a}`);
  }
  for (const x of index.excluded ?? []) check(!(await page.$(`[data-action=${x}]`)), `excluded action ${x} is shown`);
  if (shots.choices) await snap(page, shots.choices);
  await page.click(`[data-action=${action}]`);
  await page.waitForSelector(".g-banner");
  if (shots.playing) { await page.waitForTimeout(3500); await snap(page, shots.playing); }
  await page.getByRole("button", { name: "정산으로 건너뛰기" }).click();
  await page.waitForSelector("[data-testid=settlement]");
  await page.waitForTimeout(1100);
  const next = season.transitions[state][action];
  const rec = { m, shocked: before.kpis, reacted: grid(next, shock).kpis };
  await assertSettle(page, rec);
  if (state === season.base_state) {  // month 1: the season grid must equal the single-month file
    const single = runs(`${shock}/${action}.json`);
    check(near(rec.reacted.op.p50, single.reacted.op.p50), `month ${m} grid vs single-month file OP`);
    check((await page.locator("[data-testid=settle-headline]").innerText()) === single.headline, `month ${m} headline vs single-month file`);
  }
  const flagged = index.shocks[shock].evidence.needs_interview || index.actions[action].evidence.needs_interview;
  check(Boolean(await page.$("[data-testid=settle-interview]")) === flagged, `month ${m} 정산 interview flag`);
  cumulative += rec.reacted.op.p50;
  months.push(rec.reacted.op.p50);
  check(near(Number(await page.getAttribute("[data-testid=cumulative]", "data-value")), cumulative), `month ${m} cumulative`);
  for (const k of ["revenue", "op", "covers", "walkaways", "ticket", "table_utilization"])
    check(near(Number(await page.getAttribute(`.g-hud [data-kpi=${k}]`, "data-value")), rec.reacted[k].p50), `month ${m} HUD ${k}`);
  if (shots.settle) await snap(page, shots.settle);
  state = next;
}

// ---- desktop season --------------------------------------------------------------------------------
const page = await newPage(1440, 900);
await page.goto(base + "#/", { waitUntil: "networkidle" });
await page.evaluate(() => document.fonts.ready);
await page.waitForTimeout(500);
await snap(page, "01-opening-map-1440");
await page.getByRole("button", { name: "가게로 들어가기" }).click();
await stage(page);
await page.evaluate(() => window.__game.setTime(210)); // 20:30
await page.getByRole("button", { name: "일시정지" }).click();
await page.waitForTimeout(800);
await snap(page, "02-main-stage-2030-1440");
check((await page.innerText(".g-hud [data-kpi=op] .g-kpi-note")) === "사장님 인건비 300만원 차감 후", "OP footnote");
await page.getByRole("button", { name: "재생" }).click();
await page.getByRole("button", { name: "이번 달 사건 뽑기" }).click();
for (const sid of Object.keys(index.shocks))
  check(Boolean(await page.$(`.g-card-wrap:has([data-shock=${sid}]) .g-badge`)) === index.shocks[sid].evidence.needs_interview, `event badge ${sid}`);
for (const x of index.excluded ?? []) check(!(await page.$(`[data-shock=${x}]`)), `excluded event ${x} is shown`);
check(await page.isVisible("[data-testid=limit-events]") === (index.excluded ?? []).includes("SH07"), "staff limit line on events");
check((await page.innerText("[data-testid=review-status]")).startsWith("검토 "), "review status chip");
await page.click(".g-card-wrap:has([data-shock=SH04]) .g-badge");
await page.waitForTimeout(200);
check(await page.isVisible(".g-badge-reason"), "badge reason on tap");
await snap(page, "03-event-cards-badges-1440");
await page.click(".g-card-wrap:has([data-shock=SH04]) .g-badge");

await month(page, 1, "SH03", "reprice", { impact: "04-impact-SH03-1440", choices: "05-choices-SH03-1440", playing: "06-month-playing-1440", settle: "07-settle-m1-SH03-reprice-1440" });
// owner chat from the receipt, with a preset question (must equal agents.prewarm text byte for byte)
const presets = JSON.parse(readFileSync(new URL("../public/data/chat_presets.json", import.meta.url), "utf8"));
const chatReq = [];
page.on("request", (r) => r.url().endsWith("/chat") && r.method() === "POST" && chatReq.push(JSON.parse(r.postData())));
await page.locator("[data-testid=settlement]").getByRole("button", { name: "사장님에게 묻기" }).click();
await page.waitForSelector(".g-chat .g-chip");
await page.waitForSelector("[data-testid=chat-mode]:not([data-mode=checking])");
check((await page.locator(".g-chat input").count()) === 0, "free-text input shown while the API is unreachable");
const onTop = await page.evaluate(() => {
  const c = document.querySelector(".g-chat").getBoundingClientRect();
  return document.elementFromPoint(c.x + c.width / 2, c.y + 20)?.closest(".g-chat") !== null;
});
check(onTop, "chat panel is not on top of the receipt");
const preset = "돼지고기 값이 오르면 어떻게 하실 건가요?";
check(presets.some((p) => p.q === preset), "preset missing from chat_presets.json");
await page.locator(".g-chip", { hasText: preset }).click();
await page.waitForSelector(".g-msg-owner:not(.g-typing)", { timeout: 20000 });
// The API is not running here: /health fails, so the chat answers offline without POSTing /chat.
// (make e2e covers the live path: request text = preset, context {SH03, reprice}.)
check(chatReq.length === 0, `chat POSTed while offline: ${JSON.stringify(chatReq)}`);
check(await page.isVisible(".g-offline"), "offline answer label missing");
check((await page.locator(".g-msg-me p").last().innerText()) === preset, "asked text differs from the preset");
await page.waitForTimeout(300);
await snap(page, "08b-chat-from-receipt-1440");
await page.getByRole("button", { name: "대화 닫기" }).click();
await page.getByRole("button", { name: "가게 능력치 보기" }).click();
await page.evaluate(() => { document.querySelector(".g-veil").style.display = "none"; });
await page.click(".g-node-name:has-text('식재료비')").catch(() => {});
await page.waitForTimeout(300);
const affects = await page.innerText(".g-affects").catch(() => "");
check(affects.includes("영업이익") && !affects.includes("생존기간") && !affects.includes("24개월"), `affected list: ${affects}`);
await snap(page, "08-stats-panel-1440");
await page.evaluate(() => { document.querySelector(".g-veil").style.display = ""; });
await page.getByRole("button", { name: "능력치 닫기" }).click();
await page.getByRole("button", { name: "다음 달" }).click();
await month(page, 2, "SH09", "absorb", { settle: "09-settle-m2-SH09-absorb-1440" });
await page.getByRole("button", { name: "다음 달" }).click();
await month(page, 3, "SH06", "reprice_alcohol", { choices: "10-choices-m3-lasting-1440", settle: "11-settle-m3-SH06-interview-1440" });
await page.getByRole("button", { name: "다음 달" }).click();
await month(page, 4, "SH10", "discount");
await page.getByRole("button", { name: "다음 달" }).click();
await month(page, 5, "SH11", "reprice");
await page.getByRole("button", { name: "다음 달" }).click();
await month(page, 6, "SH04", "discount");
await page.getByRole("button", { name: "시즌 결산" }).click();
await page.waitForSelector("[data-testid=season-summary]");
const total = Number(await page.getAttribute("[data-testid=season-total]", "data-value"));
const totalBase = Number(await page.getAttribute("[data-testid=season-total]", "data-base"));
check(near(total, months.reduce((a, b) => a + b, 0)), `season total ${total}`);
check(near(totalBase, 6 * baseFile.kpis.op.p50), `season 평소 total ${totalBase}`);
check((await page.$$("[data-testid=season-summary] tbody tr")).length === 6, "season rows");
await page.waitForTimeout(300);
await snap(page, "12-season-summary-1440");
await page.getByRole("button", { name: "1월차 다시 보기" }).click();
await page.waitForSelector("[data-testid=settlement]");
check((await page.locator("[data-testid=settlement] tr[data-kpi=op] td[data-col=reacted]").innerText()) === man(months[0]), "review month 1");
await page.getByRole("button", { name: "시즌 결산으로" }).click();
await page.getByRole("button", { name: "새 시즌 시작" }).click();
await page.waitForSelector(".g-events");
check((await page.locator(".g-score .g-kpi-label").innerText()).startsWith("1월차"), "new season resets month");
await page.close();

// ---- first person ----------------------------------------------------------------------------------
const fp = await newPage(1440, 900);
await fp.goto(base + "#/?phase=idle&cam=fps&t=20:30&paused=1", { waitUntil: "networkidle" });
await stage(fp);
await snap(fp, "13-first-person-2030-1440");
await fp.close();

// ---- mobile ----------------------------------------------------------------------------------------
const mp = await newPage(390, 844);
state = season.base_state; cumulative = 0; months.length = 0;
await mp.goto(base + "#/", { waitUntil: "networkidle" });
await mp.waitForTimeout(600);
await snap(mp, "14-mobile-opening-390");
await mp.getByRole("button", { name: "가게로 들어가기" }).click();
await stage(mp);
await mp.evaluate(() => window.__game.setTime(210));
await mp.getByRole("button", { name: "일시정지" }).click();
await mp.waitForTimeout(600);
await snap(mp, "15-mobile-stage-2030-390");
await mp.getByRole("button", { name: "재생" }).click();
await mp.getByRole("button", { name: "이번 달 사건 뽑기" }).click();
await month(mp, 1, "SH03", "reprice", { events: "16-mobile-events-390", choices: "17-mobile-choices-390", settle: "18-mobile-settle-390" });
await mp.close();

await browser.close();
console.log(errors.length ? "PAGE ERRORS:\n" + errors.join("\n") : "no page errors");
console.log(failures.length ? "ASSERTION FAILURES:\n" + failures.join("\n") : "all on-screen numbers match runs/*.json (season of 6 months)");
process.exitCode = failures.length || errors.length ? 1 : 0;
