import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Canvas } from "@react-three/fiber";
import { GLGuard } from "../shared/GLGuard";
import { SHOCK_LABELS, useData, won, type EventsFile, type Hero } from "../data";
import { StoreScene, type CamMode } from "./Scene";
import { SEGMENTS, STAFF_COLOR, clockLabel, parseClock, parties, statsAt } from "./timeline";
import "./replay.css";

const SCENARIOS = ["SH03", "SH09"] as const;
const SPEEDS = [1, 10, 60] as const;
type Variant = "base" | "shock";

declare global {
  interface Window {
    __replay?: {
      setTime: (t: number | string) => void;
      play: () => void;
      pause: () => void;
      setCamera: (m: CamMode) => void;
      setVariant: (v: Variant) => void;
      ready: boolean;
    };
  }
}

export default function Replay({ query }: { query: URLSearchParams }) {
  const hero = useData<Hero>("hero.json");
  const [scenario, setScenario] = useState<string>(SCENARIOS.includes(query.get("scenario") as never) ? query.get("scenario")! : "SH09");
  const [variant, setVariant] = useState<Variant>(query.get("variant") === "shock" ? "shock" : "base");
  const [mode, setMode] = useState<CamMode>(query.get("cam") === "fps" ? "fps" : "orbit");
  const [speed, setSpeed] = useState<number>(60);
  const [playing, setPlaying] = useState(query.get("paused") !== "1");
  const file = useData<EventsFile>(`events/${scenario}.json`);
  const night = file ? (variant === "shock" && file.shocked ? file.shocked : file.base) : null;
  const list = useMemo(() => (night ? parties(night) : []), [night]);
  const end = useMemo(() => Math.max(420, ...(night?.events.map((e) => e.t) ?? [0])), [night]);

  const initial = parseClock(query.get("t") ?? "") ?? 0;
  const tRef = useRef<number>(initial);
  const [t, setT] = useState(initial);

  const seek = useCallback((v: number) => {
    tRef.current = Math.max(0, Math.min(end, v));
    setT(tRef.current);
  }, [end]);

  useEffect(() => {
    let raf = 0;
    let last = performance.now();
    let lastUi = 0;
    const tick = (now: number) => {
      const dt = (now - last) / 1000;
      last = now;
      if (playing) {
        tRef.current = Math.min(end, tRef.current + (dt * speed) / 60);
        if (tRef.current >= end) setPlaying(false);
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
    window.__replay = {
      setTime: (v) => seek(typeof v === "string" ? parseClock(v) ?? 0 : v),
      play: () => setPlaying(true),
      pause: () => setPlaying(false),
      setCamera: setMode,
      setVariant,
      ready: Boolean(hero && night),
    };
  }, [seek, hero, night]);

  const stats = statsAt(list, t);
  const ticks = Array.from({ length: Math.floor(end / 60) + 1 }, (_, i) => i * 60).filter((m) => m <= end);

  return (
    <div className="rp">
      <div className="rp-stage">
        {hero && night ? (
          <GLGuard>
            <Canvas shadows dpr={[1, 2]} camera={{ fov: mode === "fps" ? 70 : 42, near: 0.1, far: 120 }} id="fps-start">
              <StoreScene hero={hero} night={night} tRef={tRef} mode={mode} />
            </Canvas>
          </GLGuard>
        ) : (
          <p className="rp-loading">매장 데이터를 불러오는 중입니다</p>
        )}
        {mode === "fps" && <p className="rp-hint">화면을 클릭하면 마우스로 둘러봅니다. WASD로 걷고, Esc로 마우스를 풀어 줍니다.</p>}
      </div>

      <header className="rp-top">
        <div className="rp-title">
          <a href="#/lab" className="rp-back">목록</a>
          <h1>토요일 밤, 대학로 삼겹살집</h1>
          <p>합성 매장 한 곳의 하룻밤 시뮬레이션. 숫자는 검토 전 예시값입니다.</p>
        </div>
        <div className="rp-controls">
          <label className="rp-field">
            <span>충격 시나리오</span>
            <select value={scenario} onChange={(e) => setScenario(e.target.value)}>
              {SCENARIOS.map((s) => <option key={s} value={s}>{SHOCK_LABELS[s]}</option>)}
            </select>
          </label>
          <div className="rp-seg" role="group" aria-label="재생할 밤">
            <button aria-pressed={variant === "base"} onClick={() => setVariant("base")}>평소</button>
            <button aria-pressed={variant === "shock"} onClick={() => setVariant("shock")}>충격 후</button>
          </div>
          <div className="rp-seg" role="group" aria-label="시점">
            <button aria-pressed={mode === "orbit"} onClick={() => setMode("orbit")}>전체 보기</button>
            <button aria-pressed={mode === "fps"} onClick={() => setMode("fps")}>1인칭</button>
          </div>
        </div>
      </header>

      <aside className="rp-hud" aria-live="polite">
        <div className="rp-clock">{clockLabel(t)}</div>
        <dl>
          <div><dt><span className="l">앉아 있는 손님</span><span className="s">앉은 손님</span></dt><dd>{stats.seated}명</dd></div>
          <div><dt><span className="l">밖에서 기다리는 손님</span><span className="s">대기</span></dt><dd>{stats.waiting}명</dd></div>
          <div><dt><span className="l">기다리다 돌아간 팀</span><span className="s">돌아간 팀</span></dt><dd>{stats.walkaways}팀</dd></div>
          <div><dt><span className="l">지금까지 매출</span><span className="s">매출</span></dt><dd>{won(stats.revenue)}</dd></div>
          <div><dt>찾아온 팀</dt><dd>{stats.arrived}팀</dd></div>
        </dl>
        <ul className="rp-legend">
          {Object.values(SEGMENTS).map((s) => (
            <li key={s.label}><i style={{ background: s.color }} />{s.label}</li>
          ))}
          <li><i style={{ background: STAFF_COLOR }} />직원</li>
        </ul>
        <p className="rp-note">손님 색은 보기 쉽게 나눈 표시용 분류로, 시뮬레이션이 정한 값이 아닙니다.</p>
      </aside>

      <footer className="rp-transport">
        <button className="rp-play" onClick={() => setPlaying((p) => !p)} aria-label={playing ? "일시정지" : "재생"}>
          {playing ? (
            <svg viewBox="0 0 16 16" aria-hidden="true"><rect x="3" y="2" width="3.5" height="12" rx="1" /><rect x="9.5" y="2" width="3.5" height="12" rx="1" /></svg>
          ) : (
            <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M4 2.5v11l9.5-5.5z" /></svg>
          )}
        </button>
        <div className="rp-seg rp-speed" role="group" aria-label="재생 속도">
          {SPEEDS.map((s) => (
            <button key={s} aria-pressed={speed === s} onClick={() => setSpeed(s)}>{s}배</button>
          ))}
        </div>
        <div className="rp-scrub">
          <input type="range" min={0} max={end} step={0.5} value={t} aria-label="재생 시각"
            onChange={(e) => seek(Number(e.target.value))} />
          <div className="rp-ticks" aria-hidden="true">
            {ticks.map((m) => (
              <span key={m} style={{ left: `${(m / end) * 100}%` }}>{clockLabel(m).slice(0, 2)}시</span>
            ))}
          </div>
        </div>
      </footer>
    </div>
  );
}
