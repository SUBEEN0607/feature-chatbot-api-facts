// Headless v2 season check (never opens a window). Two modes:
//   node tests/e2e/v2_season.mjs free   <webUrl> <apiBase> [outDir]
//     #/v2, 자유 플레이, unlock all, change >= 5 levers, play 3 months (guess sheet answered in months 1 and 3,
//     skipped in month 2; any in-night decision card answered), ask one reviewer and the owner, open 트윈 인터뷰;
//     every on-screen number/text checked against the API response the page itself received.
//   node tests/e2e/v2_season.mjs guided <webUrl> [outDir]      (web started with an unreachable API)
//     #/v2, 시연 모드, first two scripted months; settle-op must equal web/public/guided/index.json.
// Selector contract agreed with the web3d agent (see message 2026-10-01); exit 3 = v2 UI not routed yet (SKIP).
import { existsSync, mkdirSync, readFileSync, readdirSync } from "node:fs";
import { homedir } from "node:os";
import { join, resolve } from "node:path";
import { pathToFileURL } from "node:url";

const repo = resolve(new URL("../..", import.meta.url).pathname);
const { chromium } = await import(pathToFileURL(join(repo, "web/node_modules/playwright-core/index.mjs")).href);
const [mode, base, a3, a4] = process.argv.slice(2);
const apiBase = mode === "free" ? a3 : null;
const out = mode === "free" ? a4 : a3;
if (out) mkdirSync(out, { recursive: true });

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
await page.addInitScript(() => { try { localStorage.setItem("v2-tour-done", "1"); } catch { /* */ } }); // the welcome tour has its own run (tour.mjs)
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
const snap = async (name) => out && page.screenshot({ path: join(out, `${name}.png`) });
let step = "start";
const at = (s) => { step = s; };
const num = async (sel, attr = "data-value") => Number(await page.getAttribute(sel, attr));
const apiResp = (re, method = "POST") => {
  const p = page.waitForResponse((r) => re.test(r.url()) && r.request().method() === method, { timeout: 120000 });
  p.catch(() => {});   // an unused wait (e.g. when the UI is not routed) must not crash the run
  return p;
};
let exit = 0;

// interactivity round (web3d, feat/interactivity): guess sheet before the month, in-night decision cards during it
async function passGuess(guess) {
  const sheet = page.locator("[data-testid=guess]");
  if (!(await sheet.waitFor({ timeout: 8000 }).then(() => true, () => false))) return false;
  if (guess) await page.locator("[data-guess]").first().click();
  else await page.click("[data-testid=guess-skip]");
  return true;
}
async function untilSettlement(timeout = 120000) {
  const end = Date.now() + timeout;
  let choices = 0;
  const answered = new Set();
  while (Date.now() < end) {
    if (await page.locator("[data-testid=settlement]").isVisible().catch(() => false)) return choices;
    const late = page.locator("[data-testid=guess]");         // a guess sheet that showed up after passGuess gave up
    if (await late.isVisible().catch(() => false)) {
      await page.click("[data-testid=guess-skip]").catch(() => {});
      continue;
    }
    const card = page.locator("[data-testid=night-choice]");
    if (await card.isVisible().catch(() => false)) {
      const dp = await card.getAttribute("data-dp").catch(() => null);
      const opt = card.locator("[data-night-option]").first();
      // answer each decision once; while the rest of the night re-runs the card stays up with aria-disabled
      if (dp && !answered.has(dp) && (await opt.getAttribute("aria-disabled").catch(() => "true")) !== "true") {
        await opt.click({ timeout: 5000 }).catch(() => {});
        answered.add(dp);
        choices += 1;
      }
      await page.waitForTimeout(300);
      continue;
    }
    const skip = page.locator("[data-testid=skip]");
    if (await skip.isVisible().catch(() => false)) await skip.click().catch(() => {});
    await page.waitForTimeout(250);
  }
  throw new Error("settlement did not appear");
}

async function open(modeName, testid) {
  at("open #/v2");
  await page.goto(base + "#/v2", { waitUntil: "networkidle" });
  const btn = page.locator(`[data-testid=${testid}]`).or(page.getByRole("button", { name: modeName }));
  try {
    await btn.first().waitFor({ timeout: 10000 });
  } catch {
    console.log(`SKIP: #/v2 has no "${modeName}" entry yet (v2 UI not routed)`);
    exit = 3;
    return false;
  }
  at(`click ${modeName}`);
  await btn.first().click();
  return true;
}

try {
  if (mode === "free") {
    const started = apiResp(/\/season$/);
    if (await open("자유 플레이", "mode-free")) {
      const season = await (await started).json();
      const unlock = page.locator("[data-testid=unlock-all]");
      if (await unlock.isVisible().catch(() => false)) { at("unlock all levers"); await unlock.click(); }
      at("plan: change 5 levers");
      await page.locator("input[data-lever=meat_price]").fill("20000");
      await page.locator("[data-lever=meat_grade] button", { hasText: "숙성" }).click();
      await page.getByRole("button", { name: "교대당 알바 수 늘리기" }).click();
      await page.getByRole("switch", { name: "직원이 구워주기" }).click();
      await page.getByRole("switch", { name: "야장" }).click();
      const cards = await page.locator(".v2-lever.changed, [data-lever-card].changed").count();
      check(cards >= 5, `only ${cards} lever cards marked changed`);
      await snap("v2-01-plan");
      for (let m = 1; m <= 3; m++) {
        at(`play month ${m}`);
        const played = apiResp(new RegExp(`/season/${season.id}/play$`));
        await page.locator("[data-testid=play]").or(page.getByRole("button", { name: "이번 달 시작" })).first().click();
        const guessed = await passGuess(m !== 2);              // guess in months 1 and 3, skip in month 2
        const settled = untilSettlement();                      // answers night cards; /play is sent after the last one
        settled.catch(() => {});
        const resp = await played;
        const res = await resp.json();
        const sent = JSON.parse(resp.request().postData() || "{}");
        await settled;
        if (res.decision_points?.length) check(sent.night_choices && Object.keys(sent.night_choices).length === res.decision_points.length,
          `month ${m}: night cards answered but night_choices not sent for every decision`);
        if (guessed && m !== 2) check(sent.prediction != null && res.prediction?.scored === true, `month ${m}: guess not sent or not scored`);
        if (m === 2) check(sent.prediction == null && res.prediction == null, "month 2: skipped guess still sent a prediction");
        check(await num("[data-testid=settle-op]") === res.draw.kpis.op, `month ${m}: settle-op != API op ${res.draw.kpis.op}`);
        check(await num("[data-testid=hud-cash]") === res.state_after.cash, `month ${m}: hud-cash != API cash`);
        check((await page.locator("[data-testid=owner-line]").innerText()).trim() === res.owner_line.text.trim(), `month ${m}: owner line differs`);
        check(await page.locator("button[data-review]").count() === res.reviews.length, `month ${m}: review count differs`);
        if (m === 1) check(res.plan.meat_price === 20000 && res.plan.meat_grade === "aged" && res.plan.staff_grilling === true,
          "plan sent to the API does not carry the lever changes");
        await snap(`v2-0${m + 1}-settle-month${m}`);
        if (m === 3) {
          at("ask a reviewer");
          const rid = res.reviews[0].id;
          await page.click(`button[data-review="${rid}"]`);
          const asked = apiResp(new RegExp(`/persona/${season.id}/ask$`));
          await page.fill("[data-testid=ask-panel] input[aria-label=질문]", "얼마나 기다리셨어요?");
          await page.locator("[data-testid=ask-panel]").getByRole("button", { name: "보내기" }).click();
          const a = await (await asked).json();
          await page.waitForSelector(`[data-testid=ask-answer][data-who="${rid}"]`);
          check((await page.locator(`[data-testid=ask-answer][data-who="${rid}"]`).last().innerText()).includes(a.answer.slice(0, 20)), "reviewer answer differs");
          at("ask the owner");
          await page.click("[data-testid=ask-owner]");
          const asked2 = apiResp(new RegExp(`/persona/${season.id}/ask$`));
          await page.fill("[data-testid=ask-panel] input[aria-label=질문]", "요즘 장사는 어떠세요?");
          await page.locator("[data-testid=ask-panel]").getByRole("button", { name: "보내기" }).click();
          const o = await (await asked2).json();
          await page.waitForSelector('[data-testid=ask-answer][data-who="owner"]');
          check((await page.locator('[data-testid=ask-answer][data-who="owner"]').last().innerText()).includes(o.answer.slice(0, 20)), "owner answer differs");
          const cites = page.locator('[data-testid=ask-answer][data-who="owner"]').last().locator("[data-cite]");
          check(await cites.count() === (o.citations ?? []).length && (o.citations ?? []).length > 0, `owner answer: ${await cites.count()} citations shown, API gave ${(o.citations ?? []).length}`);
          for (const c of o.citations ?? []) check((await cites.allInnerTexts()).some((t) => t.includes(c.label) && t.includes(c.title)), `citation ${c.label} not shown with its title`);
          await snap("v2-05-ask");
          at("트윈 인터뷰");
          const sv = apiResp(new RegExp(`/season/${season.id}/survey$`), "GET");
          await page.click("[data-testid=open-interview]");
          const survey = await (await sv).json();
          await page.waitForSelector("[data-testid=survey-item]");
          for (const it of survey.items) {
            const shown = (await page.locator(`[data-testid=survey-item][data-q="${it.guide_q}"] [data-testid=survey-answer]`).innerText()).trim();
            check(shown === it.answer.trim(), `survey Q${it.guide_q} differs`);
          }
          // no raw ids or English in the drawer: only source/shock ids (S20, D0930, SH03) and the g/kg units may carry Latin letters
          const drawerText = (await page.locator("[data-testid=interview]").innerText()).replace(/\b[A-Z]{1,3}\d+\b/g, "").replace(/(?<![A-Za-z])k?g(?![A-Za-z])/g, "");
          check(!/[A-Za-z]/.test(drawerText), `interview drawer shows English: ${drawerText.match(/.{0,30}[A-Za-z]+.{0,30}/)?.[0]}`);
          await snap("v2-06-interview");
        } else {
          at(`next month after ${m}`);
          await page.click("[data-testid=next]");
        }
      }
      // the API is the source of truth for the season as a whole
      const view = await (await fetch(`${apiBase}/season/${season.id}`)).json();
      check(view.months_played === 3, `API months_played ${view.months_played}`);
    }
  } else if (mode === "guided") {
    const idx = JSON.parse(readFileSync(join(repo, "web/public/guided/index.json"), "utf8"));
    if (await open("시연 모드", "mode-guided")) {
      for (const s of idx.story.slice(0, 2)) {
        at(`guided month ${s.n}`);
        const opt = s.decision.options.find((o) => o.id === s.story_choice) ?? s.decision.options[0];
        await page.click(`[data-option="${opt.id}"]`);
        await passGuess(false);
        await untilSettlement(60000);
        // the month file the option points to is what the screen plays (index op is a rounded summary)
        const file = JSON.parse(readFileSync(join(repo, "web/public/guided", opt.file), "utf8"));
        const shown = await num("[data-testid=settle-op]");
        check(Math.abs(shown - file.draw.kpis.op) <= 1, `guided ${s.label}: settle-op ${shown} != ${opt.file} op ${file.draw.kpis.op}`);
        check(Math.abs(await num("[data-testid=hud-cash]") - file.state_after.cash) <= 1, `guided ${s.label}: hud-cash != ${opt.file}`);
        await snap(`v2-guided-${s.n}`);
        if (s.n < 2) await page.click("[data-testid=next]");
      }
    }
  } else {
    throw new Error("mode must be free or guided");
  }
} catch (e) {
  failures.push(`flow error at "${step}": ${e.message.split("\n")[0]}`);
  await snap("v2-error").catch(() => {});
} finally {
  await browser.close();
}
if (errors.length) console.log("PAGE ERRORS:\n" + errors.join("\n"));
if (exit === 3 && !failures.length) process.exit(3);
console.log(failures.length ? `V2 ${mode} FAIL:\n` + failures.join("\n") : `V2 ${mode} PASS`);
process.exitCode = failures.length ? 1 : 0;
