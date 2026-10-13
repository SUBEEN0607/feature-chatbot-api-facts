// The management game: map → store → 이번 달 사건 → 사장님의 선택 → the month plays → 월말 정산 → 다음 달,
// for a season of N months. Lasting choices (price, staff, menu) carry into the next month (sim/season.py).
// Fully offline: every number comes from web/public/runs (python -m sim.precompute --season).
import { Suspense, lazy, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { load, man, useData, type BaseFile, type District, type Hero, type Night, type Ontology, type RunFile, type RunIndex, type SeasonIndex, type SeasonState } from "../data";
import { DistrictMap } from "../shared/components";
import { GLGuard } from "../shared/GLGuard";
import { clockLabel, parties, statsAt, SEGMENTS, STAFF_COLOR } from "../replay/timeline";
import type { CamMode } from "../replay/Scene";
import { ACTION_ORDER, ChoiceCards, EventPicker, ImpactCard, SeasonSummary, Settlement, type ChoiceRow } from "./Overlays";
import { HUD_KPIS, KpiCell } from "./parts";
import { MapIntro } from "./MapIntro";
import { OwnerChat } from "./OwnerChat";
import { StatsDrawer } from "./StatsDrawer";
import { headline, type MonthRecord } from "./season";
import "./game.css";

const Stage = lazy(() => import("./Stage"));

type Phase = "map" | "idle" | "event" | "impact" | "choice" | "playing" | "settle" | "season" | "review";
const SPEEDS = [10, 60, 300, 900] as const;

declare global {
  interface Window {
    __game?: { phase: Phase; setTime: (t: number) => void; finish: () => void; month: number; state: string };
  }
}

export default function Game({ query }: { query: URLSearchParams }) {
  const hero = useData<Hero>("hero.json");
  const district = useData<District>("district.json");
  const ontology = useData<Ontology>("ontology.json");
  const index = useData<RunIndex>("runs/index.json");
  const baseFile = useData<BaseFile>("runs/base.json");
  const season = useData<SeasonIndex>("runs/season/index.json");

  const [phase, setPhase] = useState<Phase>((query.get("phase") as Phase) ?? "map");
  const [returnTo, setReturnTo] = useState<Phase>("idle");
  const [month, setMonth] = useState(1);
  const [stateKey, setStateKey] = useState<string>("P0A0H0S0X0");
  const [shock, setShock] = useState<string | null>(null);
  const [cells, setCells] = useState<Record<string, SeasonState>>({});
  const [nightRun, setNightRun] = useState<RunFile | null>(null);
  const [shockNight, setShockNight] = useState<RunFile | null>(null);
  const [current, setCurrent] = useState<MonthRecord | null>(null);
  const [history, setHistory] = useState<MonthRecord[]>([]);
  const [review, setReview] = useState<MonthRecord | null>(null);
  const [drawer, setDrawer] = useState(false);
  const [chat, setChat] = useState(false);
  const [cam, setCam] = useState<CamMode>(query.get("cam") === "fps" ? "fps" : "orbit");
  const [speed, setSpeed] = useState<number>(60);
  const [playing, setPlaying] = useState(true);

  const flags = index?.meta.flags ?? {};
  const badges = flags.l_mechanism_badge !== false;
  const months = season?.meta.months ?? flags.season_months ?? 6;
  const carry = season?.meta.carry_state ?? flags.carry_state ?? true;
  const baseKey = season?.base_state ?? "P0A0H0S0X0";

  const stateFile = useCallback(async (key: string) => {
    if (cells[key]) return cells[key];
    const f = await load<SeasonState>(`runs/season/${key}.json`);
    setCells((c) => ({ ...c, [key]: f }));
    return f;
  }, [cells]);

  // which night is on stage
  const night: Night | null = phase === "playing" || phase === "settle" ? nightRun?.night ?? null
    : phase === "impact" || phase === "choice" ? shockNight?.night ?? null : baseFile?.night ?? null;
  const list = useMemo(() => (night ? parties(night) : []), [night]);
  const end = useMemo(() => Math.max(420, ...(night?.events.map((e) => e.t) ?? [0])), [night]);

  const tRef = useRef<number>(0);
  const [t, setT] = useState(0);
  const seek = useCallback((v: number) => { tRef.current = Math.max(0, Math.min(end, v)); setT(tRef.current); }, [end]);

  const phaseRef = useRef(phase);
  phaseRef.current = phase;
  useEffect(() => {
    let raf = 0;
    let last = performance.now();
    let lastUi = 0;
    const tick = (now: number) => {
      const dt = (now - last) / 1000;
      last = now;
      if (playing && phaseRef.current !== "settle") {
        tRef.current += (dt * speed) / 60;
        if (tRef.current >= end) {
          if (phaseRef.current === "playing") {
            tRef.current = end;
            setPhase("settle");
          } else tRef.current = 0;
        }
      }
      if (now - lastUi > 100) {
        lastUi = now;
        setT(tRef.current);
      }
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
  }, [query, seek, night]);

  const describeState = (key: string) => cells[key]?.describe ?? [];
  // actions present in this build (industry game.exclude removes some from runs/index.json)
  const actionsInGame = ACTION_ORDER.filter((a) => index?.actions[a]);
  const lasting = describeState(stateKey);

  async function pickShock(id: string) {
    const [, r] = await Promise.all([stateFile(stateKey), load<RunFile>(`runs/${id}/absorb.json`)]);
    if (season) await Promise.all(actionsInGame.map((a) => stateFile(carry ? season.transitions[stateKey][a] : season.transitions[baseKey][a])));
    setShock(id);
    setShockNight(r);
    setPhase("impact");
  }

  const cell = (key: string, k: string) => cells[key]?.shocks[k];
  const choiceRows: ChoiceRow[] = useMemo(() => {
    if (!shock || !season || !baseFile) return [];
    const before = cell(stateKey, shock);
    if (!before) return [];
    return actionsInGame.map((a) => {
      const next = carry ? season.transitions[stateKey][a] : season.transitions[baseKey][a];
      const after = cell(next, shock);
      const op = after?.kpis.op.p50 ?? 0;
      return { action: a, op, vsShock: op - before.kpis.op.p50, vsBase: op - baseFile.kpis.op.p50,
        applied: a !== "absorb" && next === stateKey };
    });
  }, [shock, season, baseFile, cells, stateKey, carry, baseKey, index]);

  async function choose(action: string) {
    if (!shock || !season || !baseFile || !index) return;
    const next = carry ? season.transitions[stateKey][action] : season.transitions[baseKey][action];
    const [before, after, nr] = await Promise.all([stateFile(stateKey), stateFile(next), load<RunFile>(`runs/${shock}/${action}.json`)]);
    const sc = before.shocks[shock], rc = after.shocks[shock];
    const rec: MonthRecord = {
      month, shock, action, stateBefore: stateKey, stateAfter: next, lasting: before.describe,
      base: baseFile.kpis, shocked: sc.kpis, reacted: rc.kpis,
      drivers: { base: baseFile.drivers, shocked: sc.drivers, reacted: rc.drivers },
      headline: headline(index.shocks[shock].if, next === stateKey && stateKey !== baseKey ? "지금 선택을 그대로 유지하면" : index.actions[action].phrase,
        baseFile.kpis.op.p50, rc.kpis.op.p50),
      op: rc.kpis.op.p50, baseOp: baseFile.kpis.op.p50,
    };
    setCurrent(rec);
    setNightRun(nr);
    tRef.current = 0;
    setT(0);
    setSpeed(900);
    setPlaying(true);
    setPhase("playing");
  }
  const finishMonth = useCallback(() => { tRef.current = end; setT(end); setPhase("settle"); }, [end]);

  const recorded = useRef<number>(0);
  useEffect(() => {
    if (phase === "settle" && current && recorded.current !== current.month) {
      recorded.current = current.month;
      setHistory((h) => [...h, current]);
    }
  }, [phase, current]);

  function nextMonth() {
    if (!current) return;
    if (month >= months) {
      setPhase("season");
      return;
    }
    setStateKey(carry ? current.stateAfter : baseKey);
    setMonth((m) => m + 1);
    setCurrent(null);
    setNightRun(null);
    setShockNight(null);
    setShock(null);
    setSpeed(60);
    setPhase("event");
  }
  function restart() {
    recorded.current = 0;
    setHistory([]);
    setMonth(1);
    setStateKey(baseKey);
    setCurrent(null);
    setNightRun(null);
    setShockNight(null);
    setShock(null);
    setReview(null);
    setSpeed(60);
    setPhase("event");
  }

  useEffect(() => {
    window.__game = { phase, setTime: seek, finish: finishMonth, month, state: stateKey };
  }, [phase, seek, finishMonth, month, stateKey]);

  // KPI values on the HUD by phase; while the month plays they move from the shock-only month to the chosen one
  const progress = Math.min(1, t / end);
  const shockCell = shock ? cell(stateKey, shock) : undefined;
  const kpiNow = (key: string): number => {
    const b = baseFile?.kpis[key]?.p50 ?? 0;
    if ((phase === "impact" || phase === "choice") && shockCell) return shockCell.kpis[key].p50;
    if (phase === "playing" && current) return current.shocked[key].p50 + (current.reacted[key].p50 - current.shocked[key].p50) * progress;
    if ((phase === "settle" || phase === "season") && current) return current.reacted[key].p50;
    return b;
  };
  const drivers = (phase === "settle" || phase === "playing" || phase === "season") && current ? current.drivers.reacted
    : (phase === "impact" || phase === "choice") && shockCell ? shockCell.drivers : baseFile?.drivers;
  const scenarioLabel = current && (phase === "settle" || phase === "playing" || phase === "season") && index
    ? `${index.shocks[current.shock].label}, ${index.actions[current.action].label}`
    : shock && index && (phase === "impact" || phase === "choice") ? `${index.shocks[shock].label}, 버틸 때` : "평소 달";

  const total = history.reduce((s, m) => s + m.op, 0);
  const totalBase = history.reduce((s, m) => s + m.baseOp, 0);
  const stats = statsAt(list, t);

  if (!hero || !district || !ontology || !index || !baseFile || !season) return <p className="g-loading">게임 데이터를 불러오는 중입니다</p>;

  if (phase === "map") {
    return <MapIntro district={district} resume={history.length > 0 || returnTo !== "idle"} onEnter={() => setPhase(returnTo)} />;
  }
  const impactHeadline = shock && shockCell
    ? headline(index.shocks[shock].if, null, baseFile.kpis.op.p50, shockCell.kpis.op.p50) : "";

  return (
    <div className="g" data-phase={phase}>
      <div className="g-stage">
        {night && (
          <GLGuard>
            <Suspense fallback={<p className="g-loading">매장을 짓는 중입니다</p>}>
              <Stage hero={hero} night={night} tRef={tRef} mode={cam} />
            </Suspense>
          </GLGuard>
        )}
      </div>

      <header className="g-hud" aria-label="이번 달 지표">
        <div className="g-score">
          <p className="g-kpi-label">{month}월차 / {months}개월</p>
          <p className="g-kpi-value" data-testid="hud-cumulative" data-value={total}>{history.length ? man(total) : "0만원"}</p>
          <p className="g-kpi-delta flat">누적 영업이익</p>
        </div>
        {HUD_KPIS.map((k) => (
          <KpiCell key={k.key} def={k} value={kpiNow(k.key)} base={baseFile.kpis[k.key].p50} smooth={phase !== "playing"}
            note={k.key === "op" && hero.owner_wage ? `사장님 인건비 ${man(hero.owner_wage)} 차감 후` : undefined} />
        ))}
      </header>

      <div className="g-tools">
        <button className="g-btn" onClick={() => setDrawer((d) => !d)} aria-pressed={drawer}>가게 능력치</button>
        <div className="g-seg" role="group" aria-label="시점">
          <button aria-pressed={cam === "orbit"} onClick={() => setCam("orbit")}>전체 보기</button>
          <button aria-pressed={cam === "fps"} onClick={() => setCam("fps")}>1인칭</button>
        </div>
        {hero.review && (
          <p className="g-review-chip" data-testid="review-status" title="HeroStore 추정값 중 reviewed_by에 이름이 적힌 행의 수">
            검토 {hero.review.reviewed}/{hero.review.total}
          </p>
        )}
        {lasting.length > 0 && <p className="g-lasting-chip" data-testid="lasting">유지 중: {lasting.join(", ")}</p>}
      </div>

      {cam === "fps" && phase !== "settle" && <p className="g-hint">화면을 클릭하면 마우스로 둘러봅니다. WASD로 걷고, Esc로 마우스를 풀어 줍니다.</p>}

      {drawer && drivers && (
        <StatsDrawer ontology={ontology} drivers={drivers} excel={baseFile.excel} scenarioLabel={scenarioLabel} onClose={() => setDrawer(false)} />
      )}

      <button className="g-minimap" onClick={() => { setReturnTo(phase === "playing" ? "settle" : phase); setPhase("map"); }} aria-label="지도로 나가기">
        <DistrictMap district={district} className="dm g-mini" competitor={shock === "SH11"} />
        <span>지도</span>
      </button>

      {phase === "idle" && (
        <div className="g-cta">
          <p>평소의 토요일 밤입니다. {SEGMENTS.twenties.label}, {SEGMENTS.office.label}, {SEGMENTS.family.label}이 찾아옵니다. {months}개월 시즌을 운영해 봅니다.</p>
          <button className="g-btn g-btn-primary g-btn-big" onClick={() => setPhase("event")}>이번 달 사건 뽑기</button>
        </div>
      )}
      {phase === "event" && <div className="g-veil"><EventPicker index={index} month={month} months={months} badges={badges} onPick={pickShock} /></div>}
      {phase === "impact" && shock && (
        <div className="g-veil">
          <ImpactCard index={index} shock={shock} headline={impactHeadline} month={month} badges={badges} lasting={lasting} onNext={() => setPhase("choice")} />
        </div>
      )}
      {phase === "choice" && shock && (
        <div className="g-veil">
          <ChoiceCards index={index} shock={shock} rows={choiceRows} badges={badges} lasting={lasting} review={hero.review} onChoose={choose} />
        </div>
      )}
      {phase === "playing" && current && (
        <div className="g-banner" role="status">
          <span><b>{month}월차</b> {index.shocks[current.shock].label}, {index.actions[current.action].label}</span>
          <span className="g-progress" style={{ ["--p" as string]: progress }} aria-hidden="true" />
          <button className="g-btn" onClick={finishMonth}>정산으로 건너뛰기</button>
          {current.lasting.length > 0 && <span className="g-banner-note">재생 화면은 이번 달 사건과 선택만 반영한 예시 밤입니다</span>}
        </div>
      )}
      {phase === "settle" && current && (
        <div className="g-veil">
          <Settlement rec={current} index={index} total={total} totalBase={totalBase} last={month >= months} badges={badges}
            onNext={nextMonth} onStats={() => setDrawer(true)} onAsk={() => setChat(true)} />
        </div>
      )}
      {phase === "season" && (
        <div className="g-veil">
          <SeasonSummary history={history} index={index} lasting={describeState(current?.stateAfter ?? stateKey)}
            onOpen={(m) => { setReview(history.find((h) => h.month === m) ?? null); setPhase("review"); }} onRestart={restart} />
        </div>
      )}
      {phase === "review" && review && (
        <div className="g-veil">
          <Settlement rec={review} index={index} total={history.filter((h) => h.month <= review.month).reduce((s, m) => s + m.op, 0)}
            totalBase={history.filter((h) => h.month <= review.month).reduce((s, m) => s + m.baseOp, 0)} last badges={badges}
            onNext={() => setPhase("season")} onStats={() => setDrawer(true)} nextLabel="시즌 결산으로" />
        </div>
      )}

      {chat ? (
        <OwnerChat run={phase === "playing" || phase === "settle" ? nightRun : shockNight} baseOp={baseFile.kpis.op.p50} onClose={() => setChat(false)} />
      ) : (
        <button className="g-btn g-ask" onClick={() => setChat(true)}>사장님에게 묻기</button>
      )}

      <footer className="g-transport">
        <button className="g-play" onClick={() => setPlaying((p) => !p)} aria-label={playing ? "일시정지" : "재생"}>
          {playing ? (
            <svg viewBox="0 0 16 16" aria-hidden="true"><rect x="3" y="2" width="3.5" height="12" rx="1" /><rect x="9.5" y="2" width="3.5" height="12" rx="1" /></svg>
          ) : (
            <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M4 2.5v11l9.5-5.5z" /></svg>
          )}
        </button>
        <div className="g-clock">
          <strong>{clockLabel(t)}</strong>
          <span>{night?.dow === "sat" ? "토요일" : ""} 밤</span>
        </div>
        <dl className="g-night">
          <div><dt>앉은 손님</dt><dd>{stats.seated}명</dd></div>
          <div><dt>대기</dt><dd>{stats.waiting}명</dd></div>
          <div><dt>돌아간 팀</dt><dd>{stats.walkaways}팀</dd></div>
          <div><dt>오늘 매출</dt><dd>{man(stats.revenue)}</dd></div>
        </dl>
        <div className="g-seg g-speed" role="group" aria-label="재생 속도">
          {SPEEDS.map((s) => <button key={s} aria-pressed={speed === s} onClick={() => setSpeed(s)}>{s}배</button>)}
        </div>
        <input className="g-scrub" type="range" min={0} max={end} step={0.5} value={t} aria-label="재생 시각" onChange={(e) => seek(Number(e.target.value))} />
        <ul className="g-legend-row" aria-label="손님 색">
          {Object.values(SEGMENTS).map((s) => <li key={s.label}><i style={{ background: s.color }} />{s.label}</li>)}
          <li><i style={{ background: STAFF_COLOR }} />직원</li>
          {flags.peak_reshape && <li className="g-assume" title="카드 데이터는 17~21시 합계만 있어 시간대 안의 분포는 가정입니다">도착 피크 19~21시는 가정</li>}
        </ul>
      </footer>
    </div>
  );
}

