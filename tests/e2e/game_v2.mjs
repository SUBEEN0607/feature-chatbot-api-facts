// Headless end-to-end check of the v2 game (never opens a window).
//   guided: 시연 모드 start to finish with NO API request (offline), every 정산 number equal to web/public/guided
//   free:   자유 플레이 against the LIVE API: a lose path (폐업) and a win path (6 months, beats the 평소 plan),
//           every 정산 operating profit equal to the API's /play response, the live preview equal to /preview,
//           a reviewer question answered by /persona, 트윈 인터뷰 from /survey, then 비교 mode
// Usage: node tests/e2e/game_v2.mjs [webUrl] [outDir] [guided|free|all]
//   (scripts/e2e.sh starts and stops the servers; the web must be built/served with VITE_API_BASE pointing at the API)
import { existsSync, mkdirSync, readFileSync, readdirSync } from "node:fs";
import { homedir } from "node:os";
import { join, resolve } from "node:path";
import { pathToFileURL } from "node:url";

const repo = resolve(new URL("../..", import.meta.url).pathname);
const { chromium } = await import(pathToFileURL(join(repo, "web/node_modules/playwright-core/index.mjs")).href);
const base = process.argv[2] ?? "http://127.0.0.1:5173/";
const out = process.argv[3] || undefined;
const which = process.argv[4] ?? "all";
if (out) mkdirSync(out, { recursive: true });
const guidedFile = (f) => JSON.parse(readFileSync(join(repo, "web/public/guided", f), "utf8"));

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

let currentPage = null;
async function newPage() {
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  await page.addInitScript(() => { try { localStorage.setItem("v2-tour-done", "1"); } catch { /* */ } }); // the welcome tour has its own run (tour.mjs)
  currentPage = page;
  page.errors = [];
  page.on("pageerror", (e) => page.errors.push(e.message));
  return page;
}
const snap = async (page, name) => out && page.screenshot({ path: join(out, `${String(++shotN).padStart(2, "0")}-${name}.png`) });

// ---------------------------------------------------------------------------------------------------------
async function guidedRun() {
  const page = await newPage();
  const apiCalls = [];
  page.on("request", (r) => { if (/:(8\d{3})\//.test(r.url())) apiCalls.push(r.url()); });
  const index = guidedFile("index.json");
  at("guided: home"); await page.goto(base + "#/", { waitUntil: "load" });
  await page.click("[data-testid=mode-guided]");
  for (const st of index.story) {
    at(`guided ${st.label}: narration`);
    await page.waitForSelector("[data-testid=narration]");
    const title = await page.locator("[data-testid=narration] h2").innerText();
    check(title.includes(st.title), `guided ${st.label}: title "${title}"`);
    check(await page.locator("[data-option]").count() === st.decision.options.length, `guided ${st.label}: option count`);
    for (const e of st.events) check(await page.locator(`[data-event=${e}]`).count() === 1, `guided ${st.label}: event ${e} not on the month card`);
    await page.hover(`[data-option=${st.story_choice}]`);
    if (st.n === 2) { await page.waitForTimeout(800); await snap(page, "guided-decision"); }
    at(`guided ${st.label}: play`);
    if (st.n === 2 && st.decision.options.length > 1) {
      // 방에 물어보기: the same decision shown large for the room
      await page.click("[data-testid=room-open]");
      await page.waitForSelector("[data-testid=room]");
      check(await page.locator("[data-room-option]").count() === st.decision.options.length, "room card: option count");
      await snap(page, "guided-room");
      await page.click(`[data-room-option=${st.story_choice}]`);
    } else await page.click(`[data-option=${st.story_choice}]`);
    await guess(page, st.n);
    await page.waitForSelector("[data-testid=transport]");
    const nightPrefer = st.night_decision?.story_option;
    await driveNight(page, nightPrefer, st.n === 1 ? hoverTest : null);
    const file = guidedFile(st.decision.options.find((o) => o.id === st.story_choice).file);
    const op = await page.getAttribute("[data-testid=settle-op]", "data-value");
    check(near(op, file.draw.kpis.op), `guided ${st.label}: 정산 op ${op} vs file ${file.draw.kpis.op}`);
    const cash = await page.getAttribute("[data-testid=hud-cash]", "data-value");
    check(near(cash, file.state_after.cash), `guided ${st.label}: HUD cash ${cash} vs file ${file.state_after.cash}`);
    check(await page.locator("[data-testid=guess-result]").count() === 1, `guided ${st.label}: guess vs actual missing on the receipt`);
    const flat = file.waterfall.filter((w) => w.kind === "step").every((w) => Math.abs(w.delta) < 10000);
    if (!flat) check(await page.locator("[data-testid=waterfall] .v2-wf-row").count() === file.waterfall.length, `guided ${st.label}: waterfall rows`);
    check(near(await page.getAttribute("[data-testid=waterfall] .v2-wf-row[data-key=end]", "data-value"), file.draw.kpis.op), `guided ${st.label}: waterfall end != op`);
    if (file.shadow) check(near(await page.getAttribute("[data-testid=shadow]", "data-value"), file.shadow.kpis.op), `guided ${st.label}: 평소 headline != shadow`);
    check(await page.locator("[data-testid=reviews] [data-review]").count() === file.reviews.length, `guided ${st.label}: review cards`);
    if (st.n === 2) await snap(page, "guided-settle");
    if (st.n === 4) {
      at("guided: ask a reviewer offline");
      await page.click("[data-testid=reviews] [data-review] >> nth=0");
      await page.click("[data-testid=ask-panel] .v2-chips button >> nth=1");
      await page.waitForSelector("[data-testid=ask-panel] [data-role=answer]");
      check((await page.locator("[data-testid=ask-panel] .src").last().innerText()).includes("오프라인"), "guided: reviewer answer not marked offline");
      await page.click("[data-testid=ask-panel] .v2-close");
      at("guided: district + tree");
      await page.click("[data-testid=minimap]");
      await page.waitForSelector("[data-testid=district] svg");
      await snap(page, "guided-district");
      await page.click("[data-testid=district] .v2-close");
      await page.click("[data-testid=open-tree]");
      await page.waitForSelector("[data-testid=tree] [data-node=op]");
      await page.click("[data-testid=tree] .v2-close");
    }
    await page.click("[data-testid=next]");
  }
  at("guided: end");
  await page.waitForSelector("[data-testid=end-survived]");
  if (index.summary) {
    check(await page.locator("[data-testid=guided-summary] [data-branch]").count() === index.summary.branches.length, "guided summary: branch rows");
    check(await page.locator("[data-testid=guided-summary] .gs-take li").count() === index.summary.takeaways.length, "guided summary: takeaways");
  }
  await snap(page, "guided-end");
  if (existsSync(join(repo, "web/public/guided/report.json"))) {
    at("guided: offline 개선 리포트");
    const rep = guidedFile("report.json");
    await page.waitForSelector("[data-testid=report] [data-testid=report-table] tbody tr");
    check(await page.locator("[data-testid=report-table] tbody tr").count() === rep.table.length, "guided report: table rows");
    check(await page.locator("[data-testid=improvements] li").count() === Math.min(5, rep.improvements.length), "guided report: improvements");
    if (rep.cash_only?.length) check(await page.locator("[data-testid=cash-only] li").count() === rep.cash_only.length, "guided report: 현금만 늘리는 선택 section");
    check((await page.getAttribute("[data-testid=csv]", "href")).startsWith("blob:"), "guided report: CSV is not a local download");
    await page.click("[data-testid=report-ask] .v2-chips button >> nth=0");
    await page.waitForSelector("[data-testid=report-answer]");
    check((await page.locator("[data-testid=report-answer]").first().innerText()).startsWith(rep.asks[0].a.slice(0, 20)), "guided report: preset answer differs from report.json");
    await page.locator("[data-testid=report]").scrollIntoViewIfNeeded();
    await snap(page, "guided-report");
  }
  check(apiCalls.length === 0, `guided mode called the API: ${apiCalls.slice(0, 3).join(", ")}`);
  if (page.errors.length) failures.push(`guided page errors: ${[...new Set(page.errors)].join(" | ")}`);
  await page.close();
}

// ---------------------------------------------------------------------------------------------------------
async function setRange(page, key, v) {
  await page.$eval(`input[data-lever=${key}]`, (el, val) => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set.call(el, String(val));
    el.dispatchEvent(new Event("input", { bubbles: true }));
  }, v);
}
async function previewSettled(page) {
  const resp = await page.waitForResponse((r) => r.url().includes("/preview") && r.request().method() === "POST", { timeout: 90000 });
  const body = await resp.json();
  await page.waitForFunction((op) => Number(document.querySelector("[data-testid=preview]")?.dataset.op) === op, body.expected.op, { timeout: 10000 })
    .catch(() => failures.push(`preview on screen != /preview ${body.expected.op}`));
  return body;
}
// predict, then reveal: every month starts through the guess sheet (a guess per month, cycling buckets)
const GUESSES = ["mid", "low", "high", "loss"];
async function guess(page, n) {
  await page.waitForSelector("[data-testid=guess]");
  await page.click(`[data-testid=guess] [data-guess=${GUESSES[n % GUESSES.length]}]`);
}
async function hoverTest(page) {
  at("guided: 3D responds (overlay + table card)");
  await page.waitForTimeout(1200);
  await page.evaluate(() => window.__v2.setTime(200));
  await page.click("[aria-label=일시정지]");
  await page.click("[data-testid=overlay]");
  const box = await page.locator("#s3-canvas canvas").boundingBox();
  let card = false;
  for (let gy = 0.45; gy <= 0.8 && !card; gy += 0.05)
    for (let gx = 0.35; gx <= 0.8 && !card; gx += 0.05) {
      await page.mouse.move(box.x + box.width * gx, box.y + box.height * gy);
      card = await page.locator("[data-testid=table-card]").count() > 0;
    }
  check(card, "hovering the store never opened a table card");
  await page.waitForTimeout(800);
  await snap(page, "guided-night");
  await page.click("[aria-label=재생]");
}
// in-night decisions: skip jumps to the next decision point, a card is answered (prefer the given option), until the 정산
let nightCards = 0;
async function driveNight(page, prefer, afterCard) {
  for (let i = 0; i < 40; i++) {
    if (await page.locator("[data-testid=settlement]").count()) return;
    const card = page.locator("[data-testid=night-choice]");
    if (await card.count()) {
      if (!(await card.locator("[aria-disabled=true]").count())) nightCards++;
      if (nightCards === 1) await snap(page, "night-card");
      const opt = prefer && await card.locator(`[data-night-option=${prefer}]`).count() ? `[data-night-option=${prefer}]` : "[data-night-option] >> nth=0";
      if (await card.locator("[aria-disabled=true]").count()) { await page.waitForTimeout(500); continue; }
      const id = await card.getAttribute("data-dp");
      await card.locator(opt).click({ timeout: 5000 }).catch(() => {});
      await page.waitForFunction((dp) => document.querySelector("[data-testid=night-choice]")?.getAttribute("data-dp") !== dp
        || document.querySelector("[data-testid=night-choice] [aria-disabled=true]"), id, { timeout: 15000 }).catch(() => {});
      await page.waitForTimeout(300);
      if (afterCard && !(await page.locator("[data-testid=night-choice]").count())) {
        await page.waitForFunction(() => !document.querySelector("[data-testid=night-choice]"), null, { timeout: 30000 });
        await afterCard(page);
        afterCard = null;
      }
      continue;
    }
    const skip = page.locator("[data-testid=skip]");
    if (await skip.count()) await skip.click().catch(() => {});
    await page.waitForTimeout(400);
  }
  throw new Error("night never reached the 정산");
}
async function playMonths(page, label, maxMonths, onMonth) {
  for (let m = 1; m <= maxMonths; m++) {
    at(`${label} month ${m}: play`);
    await page.waitForSelector("[data-testid=plan-board]");
    if (onMonth) await onMonth(m);
    const played = page.waitForResponse((r) => /\/season\/[^/]+\/play$/.test(r.url()) && r.request().method() === "POST" && r.request().postDataJSON()?.events === undefined, { timeout: 90000 });
    await page.click("[data-testid=play]");
    await guess(page, m);
    await page.waitForSelector("[data-testid=transport]", { timeout: 60000 });
    if (m === 1) { await page.waitForTimeout(2000); await snap(page, `${label}-night`); }
    await driveNight(page);
    const r = await (await played).json();
    const op = await page.getAttribute("[data-testid=settle-op]", "data-value");
    check(near(op, r.draw.kpis.op), `${label} month ${m}: 정산 op ${op} vs API ${r.draw.kpis.op}`);
    const cash = await page.getAttribute("[data-testid=hud-cash]", "data-value");
    check(near(cash, r.state_after.cash), `${label} month ${m}: HUD cash ${cash} vs API ${r.state_after.cash}`);
    if (r.shadow) check(near(await page.getAttribute("[data-testid=shadow]", "data-value"), r.shadow.kpis.op), `${label} month ${m}: 평소 headline != shadow.kpis.op`);
    if (r.waterfall[0]?.kind === "start" && r.shadow) check(near(r.waterfall[0].delta, r.shadow.kpis.op), `${label} month ${m}: waterfall start != shadow (API)`);
    const ownerLine = await page.locator("[data-testid=owner-line]").innerText();
    check(ownerLine === r.owner_line.text, `${label} month ${m}: owner line differs from API`);
    if (m === 2) await snap(page, `${label}-settle`);
    const chip = page.locator("[data-testid=settlement] button.v2-cause").first();
    if (label === "free-win" && m === 2 && !r.state_after.closed && await chip.count()) {
      // cause chip: opens that lever on next month's board
      const lever = await chip.getAttribute("data-cause");
      await chip.click();
      await page.waitForSelector(`[data-lever-card=${lever}].focus`, { timeout: 10000 }).catch(() => failures.push(`cause chip ${lever} did not focus the lever`));
      await snap(page, "free-cause-focus");
      if (r.state_after.closed) return { closed: true, months: m, last: r };
      continue;
    }
    await page.click("[data-testid=next]");
    if (r.state_after.closed) return { closed: true, months: m, last: r };
  }
  return { closed: false, months: maxMonths };
}

async function freeRun() {
  const page = await newPage();
  // lose path: everything expensive at once
  at("free lose: start"); await page.goto(base + "#/?tutorial=0&seed=11", { waitUntil: "load" });
  const created = page.waitForResponse((r) => /\/season$/.test(r.url()) && r.request().method() === "POST" && r.request().postDataJSON()?.mode === "free");
  await page.click("[data-testid=mode-free]");
  const season = await (await created).json();
  const apiBase = season && (await created).url().replace(/\/season$/, "");
  await page.waitForSelector("[data-testid=plan-board]");
  await previewSettled(page);
  at("free lose: first month shows three levers and a first question");
  check(await page.locator("[data-testid=first-question]").count() === 1, "first month: no first question");
  check(await page.locator("[data-lever-card][data-locked]").count() === 11, "first month: expected 11 locked levers");
  at("free lose: consequence dots");
  await page.hover("[data-lever-card=meat_grade]");
  await page.waitForSelector("[data-testid=dot-cash][data-sign]", { timeout: 10000 }).catch(() => failures.push("hovering 원육 lit no signed consequence dots"));
  check(await page.locator("[data-testid=dot-caption]").count() === 1, "dots: no caption saying which step they describe");
  await snap(page, "free-dots");
  await page.click("[data-testid=unlock-all]");
  at("free lose: set levers");
  await setRange(page, "meat_price", 15000); await previewSettled(page);
  await page.click("[data-lever=meat_grade] button:has-text('숙성')");
  await page.click("[data-lever=staff_per_shift] button[aria-label$='늘리기']");
  await page.click("[data-lever=staff_per_shift] button[aria-label$='늘리기']");
  await page.click("button[data-lever=lunch]");
  await page.click("[data-lever=close_hour] button:has-text('01시')");
  await page.click("[data-lever=marketing_budget] button:has-text('300만원')");
  await page.click("[data-lever=hygiene] button:has-text('철저')");
  const pv = await previewSettled(page);
  check(pv.plan.staff_per_shift === 4 && pv.plan.meat_grade === "aged" && pv.plan.lunch === true, `lose plan not sent: ${JSON.stringify(pv.plan)}`);
  at("free lose: board == /preview for the multi-lever plan");
  await page.waitForFunction(() => document.querySelector("[data-testid=preview]")?.dataset.stale === "0", null, { timeout: 15000 });
  const plan = { meat_price: 15000, meat_grade: "aged", staff_per_shift: 4, lunch: true, close_hour: 25, marketing_budget: 3000000, hygiene: "high" };
  const direct = await (await fetch(`${apiBase}/season/${season.id}/preview`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ plan }) })).json();
  const board = await page.$eval("[data-testid=preview]", (el) => ({ ...el.dataset }));
  check(near(board.op, direct.expected.op), `board op ${board.op} != /preview ${direct.expected.op}; board plan ${JSON.stringify(pv.plan)} vs ${JSON.stringify(direct.plan)}; pv op ${pv.expected.op}`);
  check(near(board.p10, direct.op_range.p10) && near(board.p90, direct.op_range.p90), `board range ${board.p10}~${board.p90} != /preview ${direct.op_range.p10}~${direct.op_range.p90}`);
  check(near(board.baseOp, direct.vs_base.base_op) && near(board.vsBase, direct.vs_base.op), `board 평소 ${board.baseOp}/${board.vsBase} != /preview ${direct.vs_base.base_op}/${direct.vs_base.op}`);
  await snap(page, "free-plan-lose");
  const lose = await playMonths(page, "free-lose", 6);
  check(lose.closed, "lose path: the store did not close");
  if (lose.closed) {
    await page.waitForSelector("[data-testid=end-closed]");
    await snap(page, "free-end-closed");
  }

  // win path: 미나리 곁들임 + 리뷰 이벤트, everything else 평소
  at("free win: start"); await page.goto(base + "#/?tutorial=0&seed=11", { waitUntil: "load" });
  await page.reload();
  await page.click("[data-testid=mode-free]");
  await page.waitForSelector("[data-testid=plan-board]");
  await previewSettled(page);
  await page.click("[data-testid=unlock-all]");
  await page.click("[data-lever=menu_extras] button:has-text('미나리 곁들임')");
  await page.click("button[data-lever=review_event]");
  await previewSettled(page);
  let reviewAsked = false;
  const win = await playMonths(page, "free-win", 6, async (m) => {
    if (m === 2 && !reviewAsked) {
      reviewAsked = true;
      at("free win: interview");
      const [sv] = await Promise.all([page.waitForResponse((r) => r.url().endsWith("/survey"), { timeout: 150000 }), page.click("[data-testid=open-interview]")]);
      const body = await sv.json();
      await page.waitForSelector("[data-testid=interview] li[data-q]", { timeout: 150000 });
      check(await page.locator("[data-testid=interview] li[data-q]").count() === body.items.length, "interview: item count differs from /survey");
      await snap(page, "free-interview");
      await page.click("[data-testid=interview] .v2-close");
    }
  });
  check(!win.closed && win.months === 6, `win path: closed=${win.closed} months=${win.months}`);
  at("free win: end");
  await page.waitForSelector("[data-testid=end-survived]");
  check(await page.locator("[data-testid=guess-score]").count() === 1, "season end: no prediction score");
  await page.waitForSelector("[data-testid=vs-baseline]", { timeout: 20000 }).catch(() => failures.push("win path: no 평소 baseline comparison"));
  const vs = await page.locator("[data-testid=vs-baseline]").innerText().catch(() => "");
  check(vs.includes("더 남겼습니다"), `win path: did not beat the 평소 plan: "${vs}"`);
  await snap(page, "free-end-survived");
  at("free win: 개선 리포트");
  await page.waitForSelector("[data-testid=report] [data-testid=improvements] li", { timeout: 60000 });
  check(await page.locator("[data-testid=report-table] tbody tr").count() === 6, "report: month table should have 6 rows");
  await page.click("[data-testid=report-table] [data-sort=op]");
  const ops = await page.$$eval("[data-testid=report-table] tbody td[data-k=op]", (tds) => tds.map((td) => td.textContent));
  check(ops.length === 6, "report: sort lost rows");
  await page.click("[data-testid=report] [data-filter=behind]");
  await page.click("[data-testid=report] [data-filter=all]");
  const csvHref = await page.getAttribute("[data-testid=csv]", "href");
  const csv = await fetch(csvHref);
  check(csv.ok && /attachment/.test(csv.headers.get("content-disposition") ?? ""), `report: CSV download ${csv.status} ${csv.headers.get("content-disposition")}`);
  const html = await fetch(await page.getAttribute("[data-testid=print]", "href"));
  check(html.ok && (html.headers.get("content-type") ?? "").includes("text/html"), "report: printable report did not open");
  const [askResp] = await Promise.all([
    page.waitForResponse((r) => r.url().endsWith("/report/ask"), { timeout: 30000 }),
    page.click("[data-testid=report-ask] .v2-chips button >> nth=0"),
  ]);
  const ra = await askResp.json();
  await page.waitForSelector("[data-testid=report-answer]");
  check((await page.locator("[data-testid=report-answer]").first().innerText()).startsWith(ra.answer.slice(0, 20)), "report: answer on screen differs from /report/ask");
  await page.locator("[data-testid=report]").scrollIntoViewIfNeeded();
  await snap(page, "free-report");
  at("free win: 이 달을 비교로 보기");
  const cmpBtn = page.locator("[data-testid=imp-compare]").first();
  check(await cmpBtn.count() > 0, "report: no improvement offers 비교 (sim.report alternatives missing)");
  if (await cmpBtn.count()) {
    const forks = [];
    page.on("response", (r) => { if (r.url().endsWith("/fork")) forks.push(r.status()); });
    await cmpBtn.click();
    await page.waitForSelector("[data-testid=compare]");
    await page.click("[data-testid=compare-run]");
    await page.waitForSelector("[data-testid=compare-table]", { timeout: 120000 });
    check(forks.length === 2 && forks.every((x) => x === 200), `report compare: forks ${forks.join(",")}`);
    await snap(page, "free-report-compare");
    await page.click("text=리포트로 돌아가기");
    await page.waitForSelector("[data-testid=end-survived]");
  }

  // ask a reviewer through the API (new season, one month)
  at("free ask"); await page.click("text=새 시즌");
  await page.waitForSelector("[data-testid=plan-board]");
  await page.click("[data-testid=play]");
  await guess(page, 0);
  await page.waitForSelector("[data-testid=transport]");
  await driveNight(page);
  await page.click("[data-testid=reviews] [data-review] >> nth=0");
  const [ask] = await Promise.all([page.waitForResponse((r) => r.url().includes("/persona/")), page.click("[data-testid=ask-panel] .v2-chips button >> nth=1")]);
  const a = await ask.json();
  await page.waitForSelector("[data-testid=ask-panel] [data-role=answer]");
  const shown = await page.locator("[data-testid=ask-panel] [data-role=answer]").last().evaluate((el) => el.firstChild?.textContent ?? "");
  check(shown === a.answer, "reviewer answer on screen differs from /persona");
  await snap(page, "free-ask-reviewer");

  // 비교
  at("compare"); await page.goto(base + "#/?mode=compare", { waitUntil: "load" });
  await page.reload();
  await page.waitForSelector("[data-testid=compare]");
  const plays = [];
  page.on("response", (r) => { if (/\/play$/.test(r.url())) plays.push(r); });
  await page.click("[data-testid=compare-run]");
  await page.waitForSelector("[data-testid=compare-table]", { timeout: 60000 });
  check(plays.length === 2, `compare: ${plays.length} /play calls`);
  await snap(page, "compare");
  if (page.errors.length) failures.push(`free page errors: ${[...new Set(page.errors)].join(" | ")}`);
  await page.close();
}

try {
  if (which === "all" || which === "guided") {
    await guidedRun();
    if (guidedFile("index.json").story.some((x) => x.night_decision)) check(nightCards > 0, "guided: no in-night decision card appeared");
  }
  if (which === "all" || which === "free") await freeRun();
} catch (e) {
  failures.push(`flow error at "${step}": ${e.message.split("\n").slice(0, 12).join(" / ")}`);
  if (currentPage) {
    if (currentPage.errors?.length) failures.push(`page errors: ${[...new Set(currentPage.errors)].join(" | ")}`);
    await snap(currentPage, "error").catch(() => {});
  }
} finally {
  await browser.close();
}
const what = { guided: "guided offline, 4 months, no API request", free: "free lose + win paths; preview, 정산, persona, survey, compare match the API" };
console.log(failures.length ? "E2E V2 FAIL:\n" + failures.join("\n") : `E2E V2 PASS: ${which === "all" ? `${what.guided}; ${what.free}` : what[which]}`);
process.exitCode = failures.length ? 1 : 0;
