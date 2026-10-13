// Headless run of the N2 demo order (never opens a window): 시연 모드 two months with the room deciding the night
// card, then 이제 직접 운영해 보기 hands over to a 1개월 체험 against the LIVE API (guess, first question, night card),
// ending on the 개선 리포트. Asks the owner a 테이블링 question (citations) and opens 트윈 인터뷰 (Korean only).
// Usage: node tests/e2e/n2_demo.mjs [webUrl] [outDir] [seed]   (the API must be running behind the web's VITE_API_BASE)
import { existsSync, mkdirSync, readFileSync, readdirSync } from "node:fs";
import { homedir } from "node:os";
import { join, resolve } from "node:path";
import { pathToFileURL } from "node:url";

const repo = resolve(new URL("../..", import.meta.url).pathname);
const { chromium } = await import(pathToFileURL(join(repo, "web/node_modules/playwright-core/index.mjs")).href);
const base = process.argv[2] ?? "http://127.0.0.1:5173/";
const out = process.argv[3] || undefined;
const seed = process.argv[4] ?? "12";
if (out) mkdirSync(out, { recursive: true });

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
const at = (s) => { step = s; console.log(`- ${s}`); };
let n = 0;
const browser = await chromium.launch({ headless: true, executablePath: chromiumPath(), args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader"] });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
await page.addInitScript(() => { try { localStorage.setItem("v2-tour-done", "1"); } catch { /* */ } });
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
const snap = async (name) => out && page.screenshot({ path: join(out, `${String(++n).padStart(2, "0")}-${name}.png`) });

async function guess(g = "mid") {
  await page.waitForSelector("[data-testid=guess]");
  await page.click(`[data-testid=guess] [data-guess=${g}]`);
}
// play the night: skip to each decision point, answer its card (the room picks the first option), until the 정산
async function driveNight(label) {
  let cards = 0;
  for (let i = 0; i < 60; i++) {
    if (await page.locator("[data-testid=settlement]").count()) return cards;
    const card = page.locator("[data-testid=night-choice]");
    if (await card.count()) {
      if (await card.locator("[aria-disabled=true]").count()) { await page.waitForTimeout(500); continue; }
      cards++;
      if (cards === 1) { await page.waitForTimeout(600); await snap(`${label}-night-card`); }
      const id = await card.getAttribute("data-dp");
      await card.locator("[data-night-option] >> nth=0").click({ timeout: 5000 }).catch(() => {});
      await page.waitForFunction((dp) => document.querySelector("[data-testid=night-choice]")?.getAttribute("data-dp") !== dp, id, { timeout: 30000 }).catch(() => {});
      continue;
    }
    const skip = page.locator("[data-testid=skip]");
    if (await skip.count()) await skip.click().catch(() => {});
    await page.waitForTimeout(400);
  }
  throw new Error("night never reached the 정산");
}

try {
  at("home");
  await page.goto(base + `#/?tutorial=0&seed=${seed}`, { waitUntil: "load" });
  await page.waitForSelector("[data-testid=mode-guided]");
  await page.waitForTimeout(1500);
  const guidedCopy = await page.locator("[data-testid=mode-guided]").innerText();
  check(/4개월 이야기/.test(guidedCopy) && /두 달째 정산에서 직접 운영/.test(guidedCopy), `home guided copy: ${guidedCopy}`);
  check(await page.locator("[data-testid=mode-trial]").count() === 1, "home: no 1개월 체험");
  await snap("home");

  const story = JSON.parse(readFileSync(join(repo, "web/public/guided/index.json"), "utf8")).story;
  // --- 시연 모드, two months -------------------------------------------------------------------------------
  await page.click("[data-testid=mode-guided]");
  for (const m of [1, 2]) {
    at(`guided month ${m}`);
    await page.waitForSelector("[data-testid=narration]");
    if (m === 1) {
      check(await page.locator("[data-testid=baseline-note]").count() === 1, "guided month 1: no 평균 예상 baseline note");
      await snap("guided-1-plan");
    }
    if (await page.locator("[data-testid=room-open]").count()) {
      await page.click("[data-testid=room-open]");
      await page.waitForSelector("[data-testid=room]");
      await snap(`guided-${m}-room`);
      await page.click(`[data-room-option=${story[m - 1].story_choice}]`);   // the story's choice carries the room's night card
    } else {
      await page.click(`[data-option=${story[m - 1].story_choice}]`);
    }
    await guess();
    await page.waitForSelector("[data-testid=transport]");
    const cards = await driveNight(`guided-${m}`);
    check(cards >= 1, `guided month ${m}: no night card for the room`);
    await page.waitForSelector("[data-testid=settlement]");
    const handover = await page.locator("[data-testid=handover]").count();
    check(handover === (m === 2 ? 1 : 0), `guided month ${m}: handover button count ${handover}`);
    await page.waitForTimeout(800);
    await snap(`guided-${m}-settle`);
    if (m === 2) {
      await page.locator("[data-testid=handover]").scrollIntoViewIfNeeded();
      await snap("guided-2-handover");
    }
    if (m === 1) await page.click("[data-testid=next]");
  }

  // --- hand over: 1개월 체험 against the API -----------------------------------------------------------------
  at("handover to 1개월 체험");
  const created = page.waitForResponse((r) => /\/season$/.test(r.url()) && r.request().method() === "POST" && r.request().postDataJSON()?.mode === "free", { timeout: 60000 });
  await page.click("[data-testid=handover]");
  const season = await (await created).json();
  check(season.months_total === 1, `trial season months_total ${season.months_total}`);
  await page.waitForSelector("[data-testid=plan-board]", { timeout: 60000 });
  await page.waitForSelector("[data-testid=preview][data-op]", { timeout: 60000 });
  check((await page.locator(".v2-hud-month .s").innerText()).includes("1 / 1개월"), "HUD should read 1 / 1개월");
  check((await page.locator("[data-testid=preview]").innerText()).includes("평균 예상"), "preview not labelled 평균 예상");
  await snap("trial-plan");
  if (await page.locator("[data-testid=first-question] [data-answer]").count()) {
    await page.click("[data-testid=first-question] [data-answer] >> nth=0");
    await page.waitForTimeout(1200);
  }
  at("trial: play with a guess");
  await page.click("[data-testid=play]");
  await guess("high");
  await page.waitForSelector("[data-testid=transport]", { timeout: 60000 });
  const cards = await driveNight("trial");
  check(cards >= 1, "trial month: no night card");
  await page.waitForSelector("[data-testid=settlement]");
  check(await page.locator("[data-testid=guess-result]").count() === 1, "trial: guess vs actual missing");
  check((await page.locator("[data-testid=next]").innerText()).includes("개선 리포트"), "trial: next button does not lead to the report");
  await page.waitForTimeout(800);
  await snap("trial-settle");

  at("trial: ask the owner about 테이블링");
  await page.click("[data-testid=ask-owner]");
  const asked = page.waitForResponse((r) => /\/persona\/[^/]+\/ask$/.test(r.url()), { timeout: 60000 });
  await page.fill("[data-testid=ask-panel] input[aria-label=질문]", "테이블링 같은 웨이팅 앱 쓰세요?");
  await page.locator("[data-testid=ask-panel]").getByRole("button", { name: "보내기" }).click();
  const a = await (await asked).json();
  await page.waitForSelector('[data-testid=ask-answer][data-who="owner"] [data-cite]');
  check(a.answer.includes("웨이팅 앱"), `owner 테이블링 answer: ${a.answer}`);
  check(await page.locator('[data-testid=ask-answer][data-who="owner"] [data-cite]').count() === a.citations.length, "citations shown != API");
  await snap("trial-ask-citations");
  await page.click("[data-testid=ask-panel] .v2-close");

  at("trial: 트윈 인터뷰");
  await page.click("[data-testid=open-interview]");
  await page.waitForSelector("[data-testid=survey-basis]", { timeout: 120000 });
  const drawer = (await page.locator("[data-testid=interview]").innerText()).replace(/\b[A-Z]{1,3}\d+\b/g, "").replace(/(?<![A-Za-z])k?g(?![A-Za-z])/g, "");
  check(!/[A-Za-z]/.test(drawer), `interview drawer shows English: ${drawer.match(/.{0,30}[A-Za-z]+.{0,30}/)?.[0]}`);
  await snap("trial-interview");
  await page.click("[data-testid=interview] .v2-close");

  at("trial: end + 개선 리포트");
  await page.click("[data-testid=next]");
  await page.waitForSelector("[data-testid=end-survived], [data-testid=end-closed]");
  await page.waitForSelector("[data-testid=report] [data-testid=report-table] tbody tr", { timeout: 90000 });
  check(await page.locator("[data-testid=report-table] tbody tr").count() === 1, "report: one month row");
  check(await page.locator("[data-testid=report] [data-filter]").count() === 0, "report: month filter should hide for one row");
  const imps = await page.locator("[data-testid=improvements] li").count();
  check(imps > 0 || await page.locator("[data-testid=no-improvements]").count() === 1, "report: no improvements and no note");
  check(await page.locator("[data-testid=season-end]").count() === 1, "end: season_end (가게 가치) missing for the short season");
  for (const em of await page.locator("[data-testid=good] em").all()) {   // 잘한 결정: the decision's own effect, coloured by its sign
    const [v, cls] = [Number(await em.getAttribute("data-good-delta")), await em.getAttribute("class")];
    check(Number.isFinite(v) && (v >= 0 ? cls === "up" : cls === "down") && !(cls === "up" && /−|-/.test(await em.innerText())), `good decision shows ${await em.innerText()} as ${cls}`);
  }
  await page.waitForTimeout(800);
  await snap("trial-end");
  await page.locator("[data-testid=report]").scrollIntoViewIfNeeded();
  await page.waitForTimeout(500);
  await snap("trial-report");
  await page.locator("[data-testid=report-table]").scrollIntoViewIfNeeded();
  await snap("trial-report-table");
} catch (e) {
  failures.push(`${step}: ${e.message.split("\n")[0]}`);
  await snap("failure").catch(() => {});
} finally {
  await browser.close();
}
if (errors.length) failures.push(...errors.map((e) => `page error: ${e}`));
if (failures.length) { console.log("FAIL n2 demo\n  " + failures.join("\n  ")); process.exit(1); }
console.log("PASS n2 demo");
