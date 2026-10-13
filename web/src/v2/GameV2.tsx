// v2 game (docs/GAME-V2-SPEC.md): 시연 모드 (guided, offline), 자유 플레이 (local API), 비교 (two plans, one seed).
// One month = one turn: 달력 + 사건 and the 운영 계획 board with a live preview, the month plays as one night in
// 3D, then 정산. Cash, reputation, regulars, fatigue and the plan carry over. 폐업 = cash below zero at two
// consecutive month-ends; 생존 = six months.
import { Suspense, lazy, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useData, type District, type Hero } from "../data";
import { clockLabel, parties, statsAt, SEGMENTS } from "../replay/timeline";
import { DistrictMap } from "../shared/components";
import { GLGuard } from "../shared/GLGuard";
import type { CamMode } from "../store3d/Store3D";
import type { TourShot } from "../store3d/Interact";
import { STAFF_SHIRT } from "../store3d/Store3D";
import { api, guided, type GuidedIndex, type GuidedOption } from "./api";
import { Compare, type CompareFrom } from "./Compare";
import { ReportPanel } from "./ReportPanel";
import type { Improvement } from "./report";
import { AskDrawer, DistrictDrawer, InterviewDrawer, TreeDrawer } from "./Drawers";
import { man, manSigned, num } from "./format";
import { Hud, type HudState } from "./Hud";
import { changedKeys, LEVERS, leverValueLabel } from "./levers";
import { useSeasonMeta, type SeasonMeta } from "./meta";
import { dotLevel, Prelim, Tag } from "./parts";
import { eventsOf, MonthCard, ownerOpening } from "./MonthCard";
import { Levers, PreviewStrip } from "./PlanBoard";
import { CashChart, Settle } from "./Settle";
import { Tutorial } from "./Tutorial";
import { Tour, tourSeen } from "./Tour";
import type { TourData } from "./tourData";
import { NightCard } from "./NightCard";
import { bucketOf, GuessSheet, predictionPayload } from "./Predict";
import { BASE_PLAN, nightOf, type DecisionPoint, type MonthEvent, type MonthResult, type NightV2, type Plan, type PlanPreview, type Review, type SeasonState } from "./types";
import "./v2.css";

const Stage3D = lazy(() => import("../store3d/Stage3D"));

type Mode = "home" | "guided" | "free" | "compare";
type Phase = "plan" | "playing" | "settle" | "end";
type DrawerKind = null | "tree" | "interview" | "district" | "owner" | { review: Review };
const SPEEDS = [12, 25, 50, 100] as const; // simulated minutes per second; after the last night decision the rest plays at 2x
// month 1 opens three levers (interactivity #6); the rest unlock from month 2
const FIRST_OPEN = new Set(["meat_price", "meat_grade", "staff_per_shift"]);
const FIRST_LOCKED = new Set(LEVERS.map((l) => l.key as string).filter((k) => !FIRST_OPEN.has(k)));

type FirstAnswer = { id: string; label: string; change: Partial<Plan>; focus?: string; primary?: boolean };
function firstQuestion(events: string[], plan: Plan): { text: string; answers: FirstAnswer[] } {
  if (events.includes("festival_week") || events.includes("viral_blog")) {
    return { text: "이번 달은 손님이 몰릴 것 같습니다. 알바를 한 명 더 쓸까요?", answers: [
      { id: "staff_up", label: "한 명 더 쓰기", change: { staff_per_shift: Math.min(4, plan.staff_per_shift + 1) }, focus: "staff_per_shift", primary: true },
      { id: "keep", label: "지금 인원으로", change: {}, focus: "staff_per_shift" }] };
  }
  if (events.includes("pork_up")) {
    return { text: "돼지고기 도매가가 올랐습니다. 1인분 가격을 1,000원 올릴까요?", answers: [
      { id: "price_up", label: "1,000원 올리기", change: { meat_price: plan.meat_price + 1000 }, focus: "meat_price", primary: true },
      { id: "keep", label: "그대로 버티기", change: {}, focus: "meat_price" }] };
  }
  return { text: "첫 달입니다. 고기를 국내산 생고기에서 숙성육으로 바꿔 볼까요? 원가는 오르지만 손님 만족이 오릅니다.", answers: [
    { id: "aged", label: "숙성육으로 바꾸기", change: { meat_grade: "aged" }, focus: "meat_grade", primary: true },
    { id: "keep", label: "국내산 그대로", change: {}, focus: "meat_grade" }] };
}
const MONTHS = 6;
const CAL_ORDER = [10, 11, 12, 1, 2, 3];

declare global {
  interface Window {
    __v2?: { mode: Mode; phase: Phase; month: number; setTime: (t: number) => void; finish: () => void; cash: number; closed: boolean; tour: boolean };
  }
}

const START: HudState = { cash: 20000000, rating: 4.2, review_count: 180, awareness: 1, regular_share: 0.25, fatigue: 30, negative_months: 0 };

export default function GameV2({ query }: { query: URLSearchParams }) {
  const hero = useData<Hero>("hero.json");
  const district = useData<District>("district.json");
  const meta = useSeasonMeta();
  const [gIndex, setGIndex] = useState<GuidedIndex | null>(null);
  const [homeNight, setHomeNight] = useState<MonthResult | null>(null);

  const [mode, setMode] = useState<Mode>((query.get("mode") as Mode) ?? "home");
  const [phase, setPhase] = useState<Phase>("plan");
  const [results, setResults] = useState<MonthResult[]>([]);
  const [current, setCurrent] = useState<MonthResult | null>(null);
  const [drawer, setDrawer] = useState<DrawerKind>(null);
  const [cam, setCam] = useState<CamMode>((query.get("cam") as CamMode) ?? "orbit");
  const [speed, setSpeed] = useState<number>(25);
  const [playing, setPlaying] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // free play
  const [seasonId, setSeasonId] = useState<string | null>(null);
  const [seasonMonths, setSeasonMonths] = useState(MONTHS); // 6, or 1 for 1개월 체험 (?months=N sets the default)
  const [shadowId, setShadowId] = useState<string | null>(null);
  const [shadow, setShadow] = useState<Record<number, MonthResult>>({});
  // shadow (평소) plays run one at a time in month order, per shadow season; two at once used to corrupt it
  const shadowQ = useRef<{ id: string | null; p: Promise<void> }>({ id: null, p: Promise.resolve() });
  const [state, setState] = useState<SeasonState | null>(null);
  const [plan, setPlan] = useState<Plan>(BASE_PLAN);
  const [preview, setPreview] = useState<PlanPreview | null>(null);
  const [monthEvents, setMonthEvents] = useState<MonthEvent[] | null>(null);
  const [pvStatus, setPvStatus] = useState<"idle" | "loading" | "error">("idle");
  const [tutorial, setTutorial] = useState(false);
  const [unlocked, setUnlocked] = useState(query.get("unlock") === "1");
  const [firstAnswer, setFirstAnswer] = useState<string | null>(null);
  const [focusLever, setFocusLever] = useState<string | null>(null);
  const [hoverLever, setHoverLever] = useState<keyof Plan | null>(null);
  // predict, then reveal: the sheet holds the action to run after the guess
  const [guessFor, setGuessFor] = useState<null | { run: () => void }>(null);
  const [guesses, setGuesses] = useState<Record<number, string>>({});
  const guessRef = useRef<string | null>(null); // the guess for the month being started (sent with /play)
  const [room, setRoom] = useState(false);
  const [compareFrom, setCompareFrom] = useState<CompareFrom | null>(null); // 비교 opened from the 개선 리포트
  const [overlay, setOverlay] = useState(false); // 만족도 보기: tint rings under tables
  const [camFocus, setCamFocus] = useState<keyof Plan | null>(null); // the lever just changed: the camera turns to it
  // in-night decisions (interactivity #2): the night up to its decision points plays first; each point pauses the
  // replay for a card; the month is played with the choices once the last card is answered
  type Pending = { dps: DecisionPoint[]; idx: number; choices: Record<string, string>; night: NightV2; label: string;
    resolve: (choices: Record<string, string>) => Promise<MonthResult>; monthNum?: number };
  const [pending, setPending] = useState<Pending | null>(null);
  const [atGate, setAtGate] = useState(false);
  const gateRef = useRef<number>(Infinity);
  const [marks, setMarks] = useState<{ clock: number; kind: string; text: string }[]>([]); // 시연 모드: the decision shown large for the room (interactivity #7)

  // welcome tour (가게 둘러보기): first entry to 시연 or 자유 플레이, again from the HUD; ?tour=1 forces it, ?tour=0 never
  const [tourOn, setTourOn] = useState(false);
  const [tourShot, setTourShot] = useState<TourShot | null>(null);
  const tourData = useData<TourData>(tourOn ? "tour.json" : null); // make tour (sim/tour.py); offline in both modes
  const maybeTour = useCallback(() => {
    const q = query.get("tour");
    if (q === "1" || (q !== "0" && !tourSeen())) { setTourShot(null); setTourOn(true); setCam("orbit"); }
  }, [query]);

  // guided
  const [step, setStep] = useState(0);
  const [choice, setChoice] = useState<string | null>(null);

  useEffect(() => {
    guided<GuidedIndex>("index.json").then((g) => {
      setGIndex(g);
      return guided<MonthResult>(g.story[0].decision.options[0].file);
    }).then(setHomeNight).catch(() => setError("시연 데이터(web/public/guided)를 불러오지 못했습니다."));
  }, []);

  // ---------- derived ----------
  const monthIdx = results.length - (phase === "plan" || (phase === "playing" && !current) ? 0 : 1); // 0-based index of the month on screen
  const last = results[results.length - 1] ?? null;
  const gStep = gIndex?.story[step];
  const calMonth = mode === "guided" ? gStep?.month ?? 10 : (phase === "plan" ? preview?.month : current?.month ?? pending?.monthNum) ?? CAL_ORDER[Math.min(5, monthIdx)];
  const monthLabel = meta?.calendar[String(calMonth)]?.label ?? `${calMonth}월`;
  const hudState: HudState = (phase === "plan" ? last?.state_after : current?.state_before && phase === "playing" ? { ...START, ...current.state_before } as HudState : current?.state_after)
    ?? (state ? state : gIndex ? { ...START, ...gIndex.start } as HudState : START);
  const startCash = (gIndex?.start.cash as number | undefined) ?? state?.cash ?? START.cash;
  const shown = phase === "plan" ? results : results.slice(0, monthIdx + 1);
  const cashHist = [mode === "free" && results.length === 0 && state ? state.cash : startCash, ...(phase === "playing" ? shown.slice(0, -1) : shown).map((r) => r.state_after.cash)];
  const ratingHist = [START.rating, ...(phase === "playing" ? shown.slice(0, -1) : shown).map((r) => r.state_after.rating)];
  const cashLabels = ["시작", ...shown.map((r) => r.calendar.label)];

  const option: GuidedOption | undefined = gStep?.decision.options.find((o) => o.id === (choice ?? gStep.story_choice)) ?? gStep?.decision.options[0];
  const guidedPlan: Plan = useMemo(() => ({ ...(last?.plan ?? BASE_PLAN), ...(option?.changes ?? {}) }) as Plan, [last, option]);
  const scenePlan: Plan = phase === "plan" ? (mode === "free" || mode === "compare" ? plan : guidedPlan) : current?.plan ?? plan;
  const sceneResult = phase === "plan" ? last ?? homeNight : current;
  const resultNight: NightV2 | null = useMemo(() => (sceneResult ? nightOf(sceneResult) : null), [sceneResult]);
  const night: NightV2 | null = phase === "playing" && pending && !current ? pending.night : resultNight;
  const upcomingEvents = useMemo(() => {
    if (mode === "guided") return eventsOf(gStep?.events ?? [], meta);
    if (phase === "plan" && monthEvents) {
      return monthEvents.map((e) => ({ id: e.id, label: e.label, group: e.kind ?? meta?.events[e.id]?.group, mechanism: e.effect ?? meta?.events[e.id]?.mechanism,
        tag: e.tag ?? meta?.events[e.id]?.tag ?? "가정" }));
    }
    if (phase === "plan") return eventsOf(preview?.events ?? [], meta);
    return current?.events ?? [];
  }, [mode, gStep, meta, phase, preview, current, monthEvents]);
  const sceneNight: NightV2 | null = useMemo(() => {
    if (!night) return null;
    if (phase !== "plan") return night;
    // planning view: show the coming month's weather and competitor on last month's night
    const ids = new Set(upcomingEvents.map((e) => e.id));
    // the plan's 야장 switch shows before play: terrace off = no Y tables (and their parties leave the replay)
    const terrace = night.terrace_open && scenePlan.terrace;
    const base = terrace ? night : { ...night, terrace_open: false, events: night.events.filter((e) => !e.table_id?.startsWith("Y")) };
    return { ...base, competitor: night.competitor || ids.has("competitor_open"), festival: ids.has("festival_week") || ids.has("viral_blog"), weather: ids.has("rain_week") ? "rain" : ids.has("cold_wave") ? "snow" : night.weather === "rain" ? "clear" : night.weather,
      staff: scenePlan.staff_per_shift };
  }, [night, phase, upcomingEvents, scenePlan.staff_per_shift, scenePlan.terrace]);

  // ---------- time ----------
  const list = useMemo(() => (night ? parties(night as never) : []), [night]);
  const end = useMemo(() => Math.max(420, ...(night?.events.map((e) => e.t) ?? [0])), [night]);
  const tRef = useRef<number>(150);
  const [t, setT] = useState(150);
  const phaseRef = useRef(phase);
  phaseRef.current = phase;
  const pendingRef = useRef(false);
  const holdRef = useRef(false); // the welcome tour's 인건비 stop holds the night where a server is working
  holdRef.current = tourOn && tourShot?.stop === "staff";
  const seek = useCallback((v: number) => { tRef.current = Math.max(0, Math.min(end, v)); setT(tRef.current); }, [end]);
  useEffect(() => {
    let raf = 0, lastNow = performance.now(), lastUi = 0;
    const tick = (now: number) => {
      const dt = Math.min(0.1, (now - lastNow) / 1000);
      lastNow = now;
      const ph = phaseRef.current;
      if (playing && !holdRef.current) {
        if (ph === "playing") {
          tRef.current += dt * speed;
          if (tRef.current >= gateRef.current) { tRef.current = gateRef.current; setAtGate(true); }
          else if (tRef.current >= end && gateRef.current === Infinity && !pendingRef.current) { tRef.current = end; setPhase("settle"); }
        } else {
          tRef.current += dt * 4;
          if (tRef.current > 330) tRef.current = 90;
        }
      }
      if (now - lastUi > 120) { lastUi = now; setT(tRef.current); }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [playing, speed, end]);
  useEffect(() => {
    const q = query.get("t");
    if (q) {
      const [h, m] = q.split(":").map(Number);
      seek((h < 17 ? h + 24 : h) * 60 + m - 17 * 60);
      if (query.get("paused") === "1") setPlaying(false);
    }
  }, [query, seek]);

  // ---------- free play ----------
  const startFree = useCallback(async (months: number = Number(query.get("months")) || MONTHS) => {
    const n = Math.max(1, Math.min(MONTHS, Math.round(months)));
    setMode("free");
    setPhase("plan");
    setResults([]);
    setCurrent(null);
    setShadow({});
    setMonthEvents(null);
    setFirstAnswer(null);
    setFocusLever(null);
    setGuesses({});
    setPending(null);
    pendingRef.current = false;
    gateRef.current = Infinity;
    setError(null);
    setBusy(true);
    try {
      await api.health();
      const seed = query.get("seed") ? Number(query.get("seed")) : undefined;
      const s = await api.newSeason("free", seed, n < MONTHS ? n : undefined);
      setSeasonMonths(s.months_total ?? n);
      const sh = await api.newSeason("sandbox", s.seed);
      setSeasonId(s.id);
      setShadowId(sh.id);
      setMonthEvents(s.month_events ?? s.state.month_events ?? null);
      setState(s.state);
      setPlan({ ...BASE_PLAN, ...(s.state.plan ?? s.default_plan ?? {}) });
      let seen = false;
      try { seen = localStorage.getItem("v2-tutorial-done") === "1"; } catch { /* storage blocked */ }
      setTutorial(false && !seen); // the first month's question replaces the text tutorial (interactivity #6)
      maybeTour();
    } catch (e) {
      setError(`자유 플레이는 로컬 API가 필요합니다 (${(e as Error).message}). 저장소에서 make api 를 실행한 뒤 다시 누르세요. 시연 모드는 API 없이 됩니다.`);
      setMode("home");
    } finally {
      setBusy(false);
    }
  }, [query, maybeTour]);

  // live preview (debounced)
  // only the response to the latest request is shown: an older, slower /preview must never overwrite a newer plan
  const pvSeq = useRef(0);
  useEffect(() => {
    if (mode !== "free" || phase !== "plan" || !seasonId) return;
    setPvStatus("loading");
    const seq = ++pvSeq.current;
    const id = setTimeout(() => {
      api.preview(seasonId, plan).then((p) => {
        if (seq !== pvSeq.current) return;
        setPreview(p);
        setPvStatus("idle");
      }).catch(() => { if (seq === pvSeq.current) setPvStatus("error"); });
    }, 220);
    return () => clearTimeout(id);
  }, [mode, phase, seasonId, plan, results.length]);

  async function playFree() {
    if (!seasonId) return;
    setFocusLever(null);
    setBusy(true);
    setError(null);
    const idx = results.length;
    const done = (r: MonthResult) => {
      setState(r.state_after);
      setMonthEvents(r.next_month_events ?? null);
      if (shadowId) {
        const sid = shadowId, ids = r.events.map((e) => e.id);
        const once = () => api.play(sid, BASE_PLAN, ids, undefined, undefined, idx);
        if (shadowQ.current.id !== sid) shadowQ.current = { id: sid, p: Promise.resolve() };
        shadowQ.current.p = shadowQ.current.p.then(() => once().catch(once)).then(
          (s) => { if (shadowQ.current.id === sid) setShadow((m) => ({ ...m, [idx]: s })); },
          (e) => { if (shadowQ.current.id === sid) setError(`평소 계획 비교를 계산하지 못했습니다 (${idx + 1}개월차): ${(e as Error).message}`); });
      }
    };
    try {
      const ms = await api.startMonth(seasonId, plan).catch(() => null);
      if (ms && ms.decision_points?.length) {
        afterResultRef.current = done;
        beginPending({ dps: ms.decision_points, night: nightOf({ night_events: [{ night: ms.night.night }, ...ms.night.events], events: ms.events, state_after: undefined as never, plan: ms.plan }),
          label: ms.calendar.label, monthNum: ms.month, resolve: (choices) => api.play(seasonId, plan, undefined, choices, predictionPayload(guessRef.current)) });
        return;
      }
      const r = await api.play(seasonId, plan, undefined, undefined, predictionPayload(guessRef.current));
      setResults((x) => [...x, r]);
      setCurrent(r);
      done(r);
      beginNight();
    } catch (e) {
      setError(`한 달을 돌리지 못했습니다: ${(e as Error).message}`);
    } finally {
      setBusy(false);
    }
  }

  function beginNight() {
    setSpeed(25);
    tRef.current = 0;
    setT(0);
    setMarks([]);
    setAtGate(false);
    setPlaying(true);
    setPhase("playing");
  }

  // night with decision points: play the prefix, stop at each point, then resolve the month with the choices
  function beginPending(p: Omit<Pending, "idx" | "choices">) {
    const dps = [...p.dps].sort((a, b) => a.clock_min - b.clock_min);
    setPending({ ...p, dps, idx: 0, choices: {} });
    pendingRef.current = true;
    gateRef.current = dps[0]?.clock_min ?? Infinity;
    setCurrent(null);
    beginNight();
  }
  async function chooseNight(optionId: string) {
    if (!pending) return;
    const dp = pending.dps[pending.idx];
    const choices = { ...pending.choices, [dp.id]: optionId };
    const label = dp.options.find((o) => o.id === optionId)?.label_ko ?? optionId;
    setMarks((m) => [...m, { clock: dp.clock_min, kind: dp.kind, text: label }]);
    if (pending.idx + 1 < pending.dps.length) {
      // the API gives the night only up to the first point: later points are asked right away, at their own clock
      setPending({ ...pending, idx: pending.idx + 1, choices });
      return;
    }
    setBusy(true);
    try {
      const r = await pending.resolve(choices);
      setResults((x) => [...x, r]);
      setCurrent(r);
      pendingRef.current = false;
      gateRef.current = Infinity;
      setPending(null);
      setAtGate(false);
      setSpeed((sp) => Math.max(sp, 50)); // the decisions are made: the rest of the night is a quick recap
      setPlaying(true);
      afterResult(r);
    } catch (e) {
      setError(`남은 밤을 돌리지 못했습니다: ${(e as Error).message}`);
    } finally {
      setBusy(false);
    }
  }
  const afterResultRef = useRef<(r: MonthResult) => void>(() => {});
  const afterResult = (r: MonthResult) => afterResultRef.current(r);

  // ---------- guided ----------
  function startGuided() {
    setGuesses({});
    setPending(null);
    pendingRef.current = false;
    gateRef.current = Infinity;
    setMode("guided");
    setPhase("plan");
    setStep(0);
    setChoice(null);
    setResults([]);
    setCurrent(null);
    setError(null);
    maybeTour();
  }
  async function playGuided(o: GuidedOption | undefined = option) {
    if (!o) return;
    setChoice(o.id);
    setBusy(true);
    try {
      const r = await guided<MonthResult>(o.file);
      const nd = gStep?.night_decision;
      if (nd && o.id === gStep?.story_choice && nd.branches.length > 1) {
        // the story plan's night, with the room deciding at the decision point; both branches are precomputed
        afterResultRef.current = () => {};
        const dp = nd.decision_point;
        const prefix = nightOf(r);
        beginPending({ dps: [dp], night: { ...prefix, events: prefix.events.filter((e) => e.t <= dp.clock_min) }, label: r.calendar.label,
          resolve: (choices) => { const b = nd.branches.find((x) => x.option_id === choices[dp.id]); return guided<MonthResult>(b?.file ?? o.file); } });
        return;
      }
      setResults((x) => [...x, r]);
      setCurrent(r);
      beginNight();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  function next() {
    if (!current) return;
    if (mode === "guided") {
      if (!gIndex || step >= gIndex.story.length - 1) { setPhase("end"); return; }
      setStep((s) => s + 1);
      setChoice(null);
      setRoom(false);
      setPhase("plan");
      return;
    }
    if (current.state_after.closed || results.length >= seasonMonths) { setPhase("end"); return; }
    setPhase("plan");
    setPreview(null);
  }
  const finish = useCallback(() => {
    if (pendingRef.current || gateRef.current !== Infinity) { tRef.current = Math.min(gateRef.current, end); setT(tRef.current); setAtGate(gateRef.current !== Infinity); return; }
    tRef.current = end; setT(end); setPhase("settle");
  }, [end]);

  useEffect(() => {
    window.__v2 = { mode, phase, month: results.length, setTime: seek, finish, cash: hudState.cash, closed: Boolean(current?.state_after.closed), tour: tourOn };
  }, [mode, phase, results.length, seek, finish, hudState.cash, current, tourOn]);

  // consequence dots for the hovered lever (preview.sensitivity: one step either way, the larger move counts)
  const dots = useMemo(() => {
    const sv = hoverLever && phase === "plan" && mode === "free" ? preview?.sensitivity?.[hoverLever] : undefined;
    if (!sv) return null;
    // the step the player would take next: one step up (or switching on); if that is not possible, one step down
    const d = sv.up ?? sv.down;
    if (!d) return null;
    const lever = LEVERS.find((l) => l.key === hoverLever);
    const isToggle = lever?.kind === "toggle";
    const step = `${lever?.label ?? ""} ${sv.up ? (isToggle ? "켜면" : "한 단계 올리면") : (isToggle ? "끄면" : "한 단계 내리면")}`;
    const dot = (v: number, small: number, big: number, higherIsBetter: boolean) => ({ n: dotLevel(v, small, big), good: higherIsBetter ? v >= 0 : v <= 0 });
    return { cash: dot(d.op, 300000, 1000000, true), rating: dot(d.rating_recent, 0.03, 0.1, true), fatigue: dot(d.fatigue, 1, 4, false),
      covers: dot(d.covers, 15, 40, true), step };
  }, [hoverLever, phase, mode, preview]);

  // ---------- render ----------
  const stats = statsAt(list, t);
  const ownerText = mode === "guided" ? ownerOpening(upcomingEvents, meta?.calendar[String(calMonth)]?.note)
    : ownerOpening(upcomingEvents, meta?.calendar[String(calMonth)]?.note);
  const tools = (
    <>
      <div className="v2-seg" role="group" aria-label="시점">
        {(["orbit", "street", "fps"] as CamMode[]).map((c) => (
          <button key={c} aria-pressed={cam === c} onClick={() => setCam(c)}>{c === "orbit" ? "전체" : c === "street" ? "길 건너" : "1인칭"}</button>
        ))}
      </div>
      <button className="v2-btn quiet" onClick={() => setDrawer("tree")} data-testid="open-tree">가게 능력치</button>
      <button className="v2-btn quiet" onClick={() => setDrawer("interview")} data-testid="open-interview">트윈 인터뷰</button>
      {phase === "plan" && <button className="v2-btn quiet" onClick={() => { setDrawer(null); setTourShot(null); setTourOn(true); setCam("orbit"); }} data-testid="tour-replay">가게 둘러보기</button>}
      <button className="v2-btn quiet" onClick={() => { setMode("home"); setPhase("plan"); }}>처음으로</button>
    </>
  );

  const stage = sceneNight && hero && (
    <div className="v2-stage">
      <GLGuard>
        <Suspense fallback={<p className="v2-loading">매장을 짓는 중입니다</p>}>
          <Stage3D hero={hero} night={sceneNight} plan={scenePlan} tRef={tRef} mode={mode === "home" ? "street" : tourOn ? "orbit" : cam} tour={tourOn ? tourShot : null}
            monthNum={calMonth} weather={sceneNight.weather} competitor={sceneNight.competitor} overlay={overlay}
            planning={phase === "plan" && mode !== "home"} basePlan={mode === "free" ? state?.plan ?? BASE_PLAN : last?.plan ?? BASE_PLAN}
            focus={query.get("nofocus") === "1" ? null : camFocus} marks={marks} />
        </Suspense>
      </GLGuard>
    </div>
  );

  if (mode === "home") {
    return (
      <div className="v2" data-mode="home">
        {stage}
        <section className="v2-home" aria-label="시작">
          <p className="kicker">대학로 혜화역 상권, 합성 삼겹살집 디지털 트윈</p>
          <h1>대학로 삼겹살</h1>
          <p className="lead">공공데이터와 추정값으로 만든 가게 한 곳을 6개월 동안 운영합니다. 가격, 원육, 인력, 영업시간을 정하면 손님 한 팀 한 팀이 시뮬레이션되고, 현금이 두 달 연속 바닥나면 문을 닫습니다.</p>
          <div className="v2-modes">
            <button className="v2-mode primary" onClick={startGuided} data-testid="mode-guided"><strong>시연 모드</strong><span>{gIndex?.story.length ?? 4}개월 이야기를 발표자 설명과 함께 봅니다. 두 달째 정산에서 직접 운영으로 넘어갈 수 있습니다. 인터넷과 API 없이 됩니다.</span></button>
            <button className="v2-mode" onClick={() => startFree()} disabled={busy} data-testid="mode-free"><strong>자유 플레이</strong><span>직접 사장님이 되어 {MONTHS}개월을 버팁니다. 로컬 API가 필요합니다.</span></button>
            <button className="v2-mode" onClick={() => startFree(1)} disabled={busy} data-testid="mode-trial"><strong>1개월 체험</strong><span>한 달만 직접 운영하고 바로 개선 리포트를 봅니다. 로컬 API가 필요합니다.</span></button>
            <button className="v2-mode" onClick={() => { setMode("compare"); setError(null); }} data-testid="mode-compare"><strong>비교</strong><span>두 계획을 같은 달, 같은 운으로 나란히 돌립니다.</span></button>
          </div>
          <p className="foot"><span>{hero?.review && <Prelim input={{ review: hero.review }} testid="home-prelim" />}모든 숫자는 검토 전 예시값이며 근거 또는 가정 표시가 붙어 있습니다.</span><a href="#/v1">이전 버전</a><a href="#/lab">실험실</a></p>
        </section>
        {error && <p className="v2-error" role="alert">{error}</p>}
      </div>
    );
  }

  if (mode === "compare") {
    return (
      <div className="v2" data-mode="compare">
        {stage}
        <Hud meta={meta} monthLabel="10월" monthNo={1} months={1} st={START} cashHist={[START.cash]} ratingHist={[START.rating]} lastOp={null}
          review={hero?.review} modeLabel="비교" tools={<button className="v2-btn quiet" onClick={() => setMode("home")}>처음으로</button>} />
        <Compare key={compareFrom ? `${compareFrom.monthIndex}-${compareFrom.title}` : "free"} meta={meta} from={compareFrom}
          onBack={compareFrom ? () => { setCompareFrom(null); setMode("free"); setPhase("end"); } : undefined} />
      </div>
    );
  }

  if (tourOn && hero && phase === "plan" && tourData) {
    // the planning board waits under the tour
    return (
      <div className="v2" data-mode={mode} data-phase="tour">
        {stage}
        <Tour hero={hero} data={tourData} meta={meta}
          onStop={(s) => setTourShot({ stop: s, label: null })} onLabel={(label) => setTourShot((x) => (x ? { ...x, label } : x))}
          onDone={() => { setTourOn(false); setTourShot(null); }} />
      </div>
    );
  }

  const decisionChanged = mode === "guided" ? changedKeys(guidedPlan, last?.plan ?? BASE_PLAN) : [];
  const shadowR = mode === "free" && current ? shadow[results.indexOf(current)] : undefined;
  // the 평소 plan is already the headline (MonthResult.shadow), so compare against another option that changes something
  const otherOpt = mode === "guided" && current ? gStep?.decision.options.find((o) => o.id !== option?.id && Object.keys(o.changes ?? {}).length > 0) : undefined;

  return (
    <div className="v2" data-mode={mode} data-phase={phase} data-hover-lever={hoverLever ?? ""}>
      {stage}
      <Hud meta={meta} monthLabel={monthLabel} monthNo={Math.min(seasonMonths, monthIdx + 1)} months={mode === "guided" ? gIndex?.story.length ?? 4 : seasonMonths}
        st={hudState} cashHist={cashHist} ratingHist={ratingHist} lastOp={(phase === "plan" || (phase === "playing" && !current) ? last : phase === "playing" ? results[results.length - 2] : current)?.draw.kpis.op ?? null}
        review={hero?.review} modeLabel={mode === "guided" ? "시연 모드" : "자유 플레이"} tools={tools} dots={dots} />

      {phase === "plan" && mode === "free" && (
        <section className="v2-left" aria-label="운영 계획" data-testid="plan-board">
          <div className="v2-panel-head">
            <h2>{monthLabel} 운영 계획</h2>
            <p>레버를 움직이면 아래 예상 영업이익과 가게 모습이 바로 바뀝니다. 바꾼 레버는 파란 점으로 표시됩니다.</p>
          </div>
          <div className="v2-scroll">
            {results.length === 0 && !firstAnswer && (() => {
              const q = firstQuestion(upcomingEvents.map((e) => e.id), plan);
              return (
                <div className="v2-first" data-testid="first-question">
                  <p>{q.text}</p>
                  <div className="row">
                    {q.answers.map((a) => (
                      <button key={a.id} className={`v2-btn ${a.primary ? "" : "quiet"}`} data-answer={a.id}
                        onClick={() => { setFirstAnswer(a.id); setPlan((x) => ({ ...x, ...a.change })); if (a.focus) setFocusLever(a.focus); }}>{a.label}</button>
                    ))}
                  </div>
                </div>
              );
            })()}
            {results.length === 0 && firstAnswer && <p className="v2-note v2-unlock">좋아요. 아래 예상 영업이익과 가게 모습이 바뀐 걸 보세요. 이번 달은 가격, 원육, 알바 수만 고를 수 있습니다.</p>}
            {results.length === 1 && !unlocked && <p className="v2-note v2-unlock" data-testid="unlock-note">이번 달부터 메뉴, 서비스, 영업시간, 야장, 마케팅, 예약, 위생 레버가 열렸습니다.</p>}
            {results.length === 0 && !unlocked && (
              <button className="v2-btn quiet v2-unlock" onClick={() => setUnlocked(true)} data-testid="unlock-all">모든 레버 열기</button>
            )}
            <Levers plan={plan} base={state?.plan ?? BASE_PLAN} set={(p) => { setPlan((x) => ({ ...x, ...p })); setCamFocus(Object.keys(p)[0] as keyof Plan); }} meta={meta} labels={preview?.labels}
              locked={results.length === 0 && !unlocked ? FIRST_LOCKED : undefined} focus={focusLever} onHover={setHoverLever} />
          </div>
          <div className="v2-panel-foot">
            <PreviewStrip preview={preview} stale={pvStatus === "loading"} status={pvStatus} coversDots={dots?.covers} dotStep={dots?.step} prevOp={last?.draw.kpis.op ?? null} meta={meta} />
            <div style={{ display: "flex", gap: 8 }}>
              <button className="v2-btn" onClick={() => setPlan(state?.plan ?? BASE_PLAN)} disabled={!changedKeys(plan, state?.plan ?? BASE_PLAN).length}>되돌리기</button>
              <button className="v2-btn primary big" style={{ flex: 1 }} onClick={() => setGuessFor({ run: playFree })} disabled={busy} data-testid="play">{busy ? "한 달을 돌리는 중" : `이 계획으로 ${monthLabel} 운영`}</button>
            </div>
          </div>
        </section>
      )}

      {phase === "plan" && mode === "guided" && gStep && (
        <section className="v2-left" aria-label="발표자 설명" data-testid="narration">
          <div className="v2-scroll">
            <div className="v2-narr">
              <span className="step">{step + 1} / {gIndex?.story.length}장</span>
              <h2>{gStep.label}, {gStep.title}</h2>
              <ol>{gStep.narration.map((l) => <li key={l}>{l}</li>)}</ol>
              {step === 0 && gIndex?.representative_note && <p className="v2-note" data-testid="representative-note">{gIndex.representative_note}</p>}
              {step === 0 && gIndex?.baseline_op != null && (
                <p className="v2-note" data-testid="baseline-note">외부 사건이 없는 평소 달의 평균 예상 영업이익은 {man(gIndex.baseline_op)}입니다 (10월, 기본 계획). 선택지와 정산의 숫자는 이번 달 사건이 들어간 이번 달 결과입니다</p>
              )}
            </div>
            <div className="v2-options" role="group" aria-label={gStep.decision.prompt}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8 }}>
                <h3>{gStep.decision.prompt}</h3>
                {gStep.decision.options.length > 1 && <button className="v2-btn" onClick={() => setRoom(true)} data-testid="room-open">방에 물어보기</button>}
              </div>
              {gStep.decision.options.map((o) => (
                <button key={o.id} className="v2-option" aria-pressed={o.id === option?.id} data-option={o.id} disabled={busy}
                  onPointerEnter={() => setChoice(o.id)} onFocus={() => setChoice(o.id)} onClick={() => setGuessFor({ run: () => playGuided(o) })}>
                  <span className="l">{o.label}{o.id === gStep.story_choice && gStep.decision.options.length > 1 && <span className="rec">이야기의 선택</span>}</span>
                  <span className="o">이번 달 결과 영업이익 {man(o.op)} (운의 범위 {man(o.p10_op)} ~ {man(o.p90_op)}), 월말 현금 {man(o.cash_after)}</span>
                  {o.next_line && <span className="o next" data-testid="next-line">그다음: {o.next_line}</span>}
                </button>
              ))}
              {decisionChanged.length > 0 && (
                <p className="v2-note">바뀌는 것: {decisionChanged.map((k) => { const l = LEVERS.find((x) => x.key === k); return l ? `${l.label} ${leverValueLabel(l, guidedPlan[k])}` : k; }).join(", ")}</p>
              )}
              {option && option.id !== gStep.story_choice && <p className="v2-note">다음 장은 이야기의 선택을 기준으로 이어집니다.</p>}
            </div>
          </div>
          <div className="v2-panel-foot">
            <p className="v2-note">선택지에 마우스를 올리면 가게 모습이 그 계획으로 바뀌고, 누르면 그 선택으로 {gStep.label}을 운영합니다.</p>
          </div>
        </section>
      )}

      {phase === "plan" && (
        <MonthCard label={monthLabel} note={meta?.calendar[String(calMonth)]?.note} demandIndex={meta?.calendar[String(calMonth)]?.demand_index}
          calTag={meta?.calendar[String(calMonth)]?.tags?.demand_index} events={upcomingEvents} meta={meta} ownerText={ownerText}
          onAsk={() => setDrawer("owner")} />
      )}

      {phase === "playing" && (current || pending) && (
        <>
          <div className="v2-transport" role="status" data-testid="transport">
            <button className="v2-btn" onClick={() => setPlaying((p) => !p)} aria-label={playing ? "일시정지" : "재생"}>{playing ? "멈춤" : "재생"}</button>
            <div><span className="v2-clock">{clockLabel(t)}</span><span className="v2-note" style={{ marginInlineStart: 6 }}>{current?.calendar.label ?? pending?.label}의 토요일 밤</span></div>
            <dl className="v2-night">
              <div><dt>앉은 손님</dt><dd>{stats.seated}명</dd></div>
              <div><dt>대기</dt><dd>{stats.waiting}명</dd></div>
              <div><dt>돌아간 팀</dt><dd>{stats.walkaways}팀</dd></div>
              <div><dt>오늘 매출</dt><dd>{man(stats.revenue)}</dd></div>
            </dl>
            <span className="v2-progress" aria-hidden="true"><i style={{ inlineSize: `${(t / end) * 100}%` }} /></span>
            <div className="v2-seg" role="group" aria-label="재생 속도">
              {SPEEDS.map((s, i) => <button key={s} aria-pressed={speed === s} onClick={() => setSpeed(s)}>{["0.5배", "1배", "2배", "4배"][i]}</button>)}
            </div>
            <button className="v2-btn primary" onClick={finish} data-testid="skip">정산 보기</button>
          </div>
          <ul className="v2-legend" aria-label="색 안내">
            {Object.values(SEGMENTS).map((s) => <li key={s.label} style={{ listStyle: "none" }}><i style={{ background: s.color }} />{s.label}</li>)}
            <li style={{ listStyle: "none" }}><i style={{ background: STAFF_SHIRT }} />직원</li>
            <li style={{ listStyle: "none" }}><i style={{ background: "oklch(0.5 0.17 30)" }} />사장님</li>
          </ul>
        </>
      )}

      {phase === "settle" && current && (
        <Settle r={current} guess={guesses[results.indexOf(current)]} meta={meta} monthNo={monthIdx + 1} months={mode === "guided" ? gIndex?.story.length ?? 4 : seasonMonths}
          cashLabels={cashLabels} cashHist={cashHist} ratingHist={ratingHist}
          shadowOp={mode === "guided" ? otherOpt?.op ?? null : null}
          shadowLabel={otherOpt ? `"${otherOpt.label}"였다면` : undefined}
          seasonShadow={mode === "free" && shadowR ? { cash: shadowR.state_after.cash, label: "시즌 내내 평소 계획이었다면 (같은 사건, 누적)" } : null}
          onCause={mode === "free" && !current.state_after.closed && results.length < seasonMonths ? (k) => { setFocusLever(k); next(); } : undefined}
          onNext={next} onAsk={(rv) => setDrawer({ review: rv })} onAskOwner={() => setDrawer("owner")} onTree={() => setDrawer("tree")}
          nextLabel={current.state_after.closed ? "결과 보기" : mode === "guided" ? (step >= (gIndex?.story.length ?? 4) - 1 ? "시연 마치기" : "다음 장") : results.length >= seasonMonths ? (seasonMonths < MONTHS ? "체험 결과와 개선 리포트 보기" : "시즌 결과 보기") : "다음 달 계획"}
          onHandover={mode === "guided" && step >= 1 && step < (gIndex?.story.length ?? 4) - 1 && !current.state_after.closed ? () => startFree(1) : undefined}
          fixtureNote={mode === "guided" ? "시연 모드의 숫자는 미리 계산한 시즌 엔진 결과입니다. 모두 검토 전 예시값입니다." : undefined}
          branches={mode === "guided" ? gStep?.decision.options.filter((o) => o.id !== option?.id && o.next_line).map((o) => ({ label: o.label, line: o.next_line! })) : undefined} />
      )}

      {room && mode === "guided" && phase === "plan" && gStep && !guessFor && (
        <div className="v2-sheet-wrap v2-room-wrap">
          <section className="v2-sheet v2-room" role="dialog" aria-label="방에 물어보기" data-testid="room">
            <div className="v2-sheet-body">
              <p className="v2-note">{gStep.label}, {gStep.title}</p>
              <h2>{gStep.decision.prompt}</h2>
              <p className="lead">어느 쪽으로 할까요? 대표님이 정해 주세요.</p>
              <div className="v2-room-grid" style={{ gridTemplateColumns: `repeat(${gStep.decision.options.length}, 1fr)` }}>
                {gStep.decision.options.map((o, i) => (
                  <button key={o.id} className="v2-room-opt" data-room-option={o.id} onPointerEnter={() => setChoice(o.id)} onFocus={() => setChoice(o.id)}
                    onClick={() => { setRoom(false); setGuessFor({ run: () => playGuided(o) }); }}>
                    <span className="k">{String.fromCharCode(65 + i)}</span>
                    <strong>{o.label}</strong>
                    <span className="o">운의 범위 영업이익 {man(o.p10_op)} ~ {man(o.p90_op)}</span>
                    {o.next_line && <span className="n">{o.next_line}</span>}
                  </button>
                ))}
              </div>
              <button className="v2-btn quiet" onClick={() => setRoom(false)}>닫기</button>
            </div>
          </section>
        </div>
      )}
      {phase === "playing" && pending && atGate && pending.dps[pending.idx] && (
        <NightCard key={pending.dps[pending.idx].id} dp={pending.dps[pending.idx]} room={mode === "guided"} meta={meta} busy={busy} onChoose={chooseNight} />
      )}
      {guessFor && phase === "plan" && (
        <GuessSheet monthLabel={monthLabel} room={mode === "guided"}
          onGuess={(g) => { setGuesses((x) => ({ ...x, [results.length]: g })); guessRef.current = g; const r = guessFor.run; setGuessFor(null); r(); }}
          onSkip={() => { guessRef.current = null; const r = guessFor.run; setGuessFor(null); r(); }} />
      )}

      {phase === "end" && (
        <EndScreen mode={mode} trial={mode === "free" && seasonMonths < MONTHS} results={results} startCash={startCash} shadow={Object.values(shadow)}
          meta={meta} summary={mode === "guided" ? gIndex?.summary : undefined} guesses={guesses} seasonId={mode === "free" ? seasonId : null}
          onCompare={mode === "free" && seasonId ? (imp) => {
            const actual = results[imp.month_index!]?.plan ?? BASE_PLAN;
            setCompareFrom({ seasonId, monthIndex: imp.month_index!, monthLabel: imp.month_label ?? results[imp.month_index!]?.calendar.label ?? "",
              a: actual, b: { ...actual, ...(imp.alt_plan ?? {}) }, bChoices: imp.alt_night_choices, title: imp.takeaway_ko ?? imp.why_ko ?? "이 달을 다른 계획으로" });
            setMode("compare");
          } : undefined}
          onRestart={mode === "guided" ? startGuided : () => startFree(seasonMonths)} onFree={() => startFree(MONTHS)} onHome={() => setMode("home")} />
      )}

      <button className="v2-btn v2-overlay-toggle" aria-pressed={overlay} onClick={() => setOverlay((o) => !o)} data-testid="overlay"
        title="테이블 아래 고리 색: 초록 만족, 노랑 보통, 빨강 불만. 테이블을 누르면 그 손님 카드가 열립니다">만족도 보기</button>
      {overlay && <p className="v2-overlay-legend" aria-live="polite"><i style={{ background: "#2f8f5b" }} />만족 <i style={{ background: "#d9a441" }} />보통 <i style={{ background: "#c8402e" }} />불만 <i style={{ background: "#b9bec4" }} />기록 없음</p>}
      <button className="v2-minimap" onClick={() => setDrawer("district")} aria-label="상권 지도 열기" data-testid="minimap">
        {district && <DistrictMap district={district} competitor={Boolean(sceneNight?.competitor)} />}
        <span>상권 보기</span>
      </button>

      {drawer === "tree" && <TreeDrawer r={current ?? last} onClose={() => setDrawer(null)} />}
      {drawer === "interview" && <InterviewDrawer seasonId={mode === "free" ? seasonId : null} onClose={() => setDrawer(null)} />}
      {drawer === "district" && <DistrictDrawer district={district} meta={meta} competitor={Boolean(sceneNight?.competitor)} onClose={() => setDrawer(null)} />}
      {drawer === "owner" && <AskDrawer who="owner" seasonId={mode === "free" ? seasonId : null} last={last} onClose={() => setDrawer(null)} />}
      {drawer && typeof drawer === "object" && <AskDrawer who={drawer.review} seasonId={mode === "free" ? seasonId : null} last={current ?? last} onClose={() => setDrawer(null)} />}

      {tutorial && mode === "free" && phase === "plan" && (
        <Tutorial onDone={() => { setTutorial(false); try { localStorage.setItem("v2-tutorial-done", "1"); } catch { /* storage blocked */ } }} />
      )}
      {error && <p className="v2-error" role="alert">{error} <button className="v2-btn quiet" onClick={() => setError(null)}>닫기</button></p>}
    </div>
  );
}

// 시연 모드 final card: every decision's branches to March, cash and 가게 가치 side by side, then the takeaways.
function GuidedSummary({ summary, meta }: { summary: NonNullable<GuidedIndex["summary"]>; meta: SeasonMeta | null }) {
  const months = [...new Set(summary.branches.map((b) => b.label))];
  const maxV = Math.max(...summary.branches.flatMap((b) => [b.cash, b.store_value]), 1);
  const bar = (v: number, cls: string) => <i className={`gs-bar ${cls}`} style={{ inlineSize: `${Math.max(0, v / maxV) * 100}%` }} />;
  return (
    <div className="v2-gsum" data-testid="guided-summary">
      <h3>{summary.title} <Tag tag="가정" title="가게 가치" note={summary.basis} meta={meta} /></h3>
      <div className="gs-legend"><span><i className="gs-bar cash" />3월 현금</span><span><i className="gs-bar value" />가게 가치</span></div>
      {months.map((m) => (
        <div key={m} className="gs-month">
          <b>{m}의 선택</b>
          {summary.branches.filter((b) => b.label === m).map((b) => (
            <div key={b.option} className={`gs-row ${b.is_story ? "story" : ""}`} data-branch={b.option}>
              <span className="gs-name">{b.option_label}{b.is_story && <small>이야기의 선택</small>}{b.closed && <small className="closed">{b.end_label} 전에 폐업</small>}</span>
              <span className="gs-bars">{bar(b.cash, "cash")}{bar(b.store_value, "value")}</span>
              <span className="gs-nums num">{man(b.cash)}<br />{man(b.store_value)}</span>
              <span className="gs-sub num">단골 {Math.round(b.regular_share * 100)}%, 평점 {b.rating.toFixed(2)}</span>
            </div>
          ))}
        </div>
      ))}
      <ul className="gs-take">{summary.takeaways.map((t) => <li key={t}>{t}</li>)}</ul>
      <p className="v2-note">{summary.basis}</p>
    </div>
  );
}

function EndScreen({ mode, trial = false, results, startCash, shadow, meta, summary, guesses, seasonId, onCompare, onRestart, onFree, onHome }: {
  mode: Mode; trial?: boolean; results: MonthResult[]; startCash: number; shadow: MonthResult[]; meta: SeasonMeta | null; summary?: GuidedIndex["summary"]; guesses: Record<number, string>;
  seasonId: string | null; onCompare?: (imp: Improvement) => void;
  onRestart: () => void; onFree: () => void; onHome: () => void;
}) {
  const last = results[results.length - 1];
  if (!last) return null;
  const closed = last.state_after.closed;
  const cash = last.state_after.cash;
  const shadowCash = shadow.length === results.length ? shadow[shadow.length - 1].state_after.cash : null;
  const shadowValue = shadow.length === results.length ? shadow[shadow.length - 1].season_end?.store_value ?? null : null;
  const total = results.reduce((s, r) => s + r.draw.kpis.op, 0);
  return (
    <div className="v2-sheet-wrap">
      <section className="v2-sheet v2-end with-report" role="dialog" aria-label="시즌 결과" data-testid={closed ? "end-closed" : "end-survived"}>
        <div className="v2-sheet-body" style={{ paddingBlockStart: 26 }}>
          <span className={`badge ${closed ? "closed" : "ok"}`}>{closed ? "폐업" : mode === "guided" ? "시연 끝" : trial ? "체험 끝" : "생존"}</span>
          <h2 style={{ fontSize: 26, fontWeight: 800 }}>
            {closed ? `${last.calendar.label}에 문을 닫았습니다` : mode === "guided" ? `${results.length}개월 이야기를 마쳤습니다` : trial ? `${results.length}개월 체험을 마쳤습니다` : `${results.length}개월을 버텼습니다`}
          </h2>
          <p style={{ color: "var(--ink-2)" }}>
            {closed ? (last.state_after.closed_reason === "revenue"
              ? "매출이 평소의 60% 아래로 두 달 연속 떨어져 사장님이 문을 닫기로 했습니다. 폐업 소상공인 대부분이 매출 40% 이상 감소 뒤 결정했다는 조사(S89)를 따른 규칙입니다."
              : "현금이 두 달 연속 0 아래로 내려가 운영자금이 바닥났습니다. 대학로 고깃집 인허가 자료의 폐업 라벨과 같은 기준입니다.")
              : `${summary ? `이야기가 끝난 ${last.calendar.label} 말` : "월말"} 현금 ${man(cash)} (시작 ${man(startCash)}, ${manSigned(cash - startCash)}). 누적 영업이익 ${man(total)}.${summary ? " 아래는 각 선택을 3월까지 이어 본 결과입니다." : ""}`}
          </p>
          {Object.keys(guesses).length > 0 && (() => {
            const tried = results.map((r, i) => [r, guesses[i]] as const).filter(([, g]) => g);
            const hits = tried.filter(([r, g]) => bucketOf(r.draw.kpis.op).id === g).length;
            return <p data-testid="guess-score">영업이익 예측 {tried.length}번 중 {hits}번 맞혔습니다. 달마다 운의 폭이 커서 계획만으로는 다 맞히기 어렵습니다.</p>;
          })()}
          {last.season_end && (
            <div className="v2-two" data-testid="season-end" style={{ textAlign: "start" }}>
              <div className="v2-month-cell"><span>점수: 시즌 끝 현금</span><b className="num">{man(last.season_end.cash)}</b></div>
              <div className="v2-month-cell">
                <span>가게 가치 <Tag tag={last.season_end.tag} title="가게 가치" note={last.season_end.basis} meta={meta} /></span>
                <b className="num">{man(last.season_end.store_value)}</b>
                {last.season_end.closed
                  ? <span className="v2-note">폐업 정리 비용을 뺀 현금입니다 (S89)</span>
                  : <span className="v2-note">{last.season_end.label ?? "현금 + 앞으로 6개월 예상 영업이익"}: 앞으로 {last.season_end.horizon_months}개월 {manSigned(last.season_end.forward_value)}
                    {last.season_end.reputation_effect != null && <>, 그중 평판 효과 {manSigned(last.season_end.reputation_effect)}</>}
                    {last.season_end.drivers?.rating && <> (평점 {last.season_end.drivers.rating.start.toFixed(2)}에서 {last.season_end.drivers.rating.end.toFixed(2)}로)</>}</span>}
              </div>
            </div>
          )}
          {shadowCash != null && !closed && (
            <p data-testid="vs-baseline">시즌 내내 평소 계획이었다면 (같은 사건) 월말 현금 {man(shadowCash)}. 내 운영이 <b className={cash - shadowCash >= 0 ? "up" : "down"}>{man(Math.abs(cash - shadowCash))}</b> {cash >= shadowCash ? "더 남겼습니다" : "덜 남겼습니다"}.{shadowValue != null && last.season_end && <> 가게 가치로는 {man(shadowValue)} 대비 <b className={last.season_end.store_value >= shadowValue ? "up" : "down"}>{manSigned(last.season_end.store_value - shadowValue)}</b>.</>}</p>
          )}
          {summary && <GuidedSummary summary={summary} meta={meta} />}
          {!summary && <div className="v2-rules" data-testid="closure-rules">
            {[["closure_cash", "cash"], ["closure_revenue", "revenue"]].map(([mech, reason]) => {
              const l = last.labels.find((x) => x.mechanism === mech);
              if (!l) return null;
              const hit = closed && last.state_after.closed_reason === reason;
              return (
                <p key={mech} className={hit ? "hit" : ""}>
                  <span>{hit ? "이 규칙으로 폐업" : "폐업 규칙"}</span> {l.label} <Tag tag={l.tag} title={l.label} note={l.detail} meta={meta} />
                </p>
              );
            })}
          </div>}
          <CashChart labels={["시작", ...results.map((r) => r.calendar.label)]} values={[startCash, ...results.map((r) => r.state_after.cash)]} w={520} h={110} />
          <div className="v2-months">
            {results.map((r) => (
              <div key={r.month_index} className="v2-month-cell"><b>{r.calendar.label}</b><span className={r.draw.kpis.op < 0 ? "down" : ""}>{man(r.draw.kpis.op)}</span><span>평점 {r.state_after.rating.toFixed(2)}</span></div>
            ))}
          </div>
          <div style={{ display: "flex", gap: 8, justifyContent: "center", flexWrap: "wrap" }}>
            <button className="v2-btn" onClick={onHome}>처음으로</button>
            <button className="v2-btn" onClick={onRestart}>{mode === "guided" ? "시연 다시 보기" : trial ? "다시 체험하기" : "새 시즌"}</button>
            {(mode === "guided" || trial) && <button className="v2-btn primary big" onClick={onFree}>{trial ? "6개월 시즌 해 보기" : "직접 운영해 보기"}</button>}
          </div>
          <ReportPanel seasonId={seasonId} offline={mode === "guided"} meta={meta} onCompare={onCompare} />
          <p className="v2-note">평점, 리뷰, 단골, 피로 메커니즘의 크기는 대부분 가정입니다. 숫자 옆 가정 표시를 누르면 이유와 대가가 나옵니다. 누적 영업이익 {num(Math.round(total / 10000))}만원.</p>
        </div>
      </section>
    </div>
  );
}
