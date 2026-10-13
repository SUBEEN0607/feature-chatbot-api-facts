// #/store: the v2 store on its own, for review and headless screenshots.
// Query: m (guided month 1..4), t (HH:MM), cam (orbit|fps|street), weather (clear|rain|snow), competitor (0|1),
// price (meat price override), staff, paused=1. window.__store exposes setTime / setCam.
import { Suspense, lazy, useEffect, useMemo, useRef, useState } from "react";
import { useData, type Hero } from "../data";
import { parseClock } from "../replay/timeline";
import { GLGuard } from "../shared/GLGuard";
import { guided, type GuidedIndex } from "../v2/api";
import { nightOf, type MonthResult, type Weather } from "../v2/types";
import type { CamMode } from "./Store3D";

const Stage3D = lazy(() => import("./Stage3D"));

declare global {
  interface Window { __store?: { setTime: (t: number) => void; setCam: (m: CamMode) => void; ready: boolean } }
}

export default function StorePreview({ query }: { query: URLSearchParams }) {
  const hero = useData<Hero>("hero.json");
  const m = query.get("m") ?? "1";
  const [month, setMonth] = useState<MonthResult | null>(null);
  useEffect(() => {
    guided<GuidedIndex>("index.json").then((g) => {
      const st = g.story[Number(m) - 1] ?? g.story[0];
      const opt = st.decision.options.find((o) => o.id === (query.get("opt") ?? st.story_choice)) ?? st.decision.options[0];
      return guided<MonthResult>(opt.file);
    }).then(setMonth);
  }, [m, query]);
  const [cam, setCam] = useState<CamMode>((query.get("cam") as CamMode) ?? "orbit");
  const tRef = useRef<number>(parseClock(query.get("t") ?? "") ?? 120);
  const paused = query.get("paused") === "1";
  useEffect(() => {
    let raf = 0, last = performance.now();
    const tick = (now: number) => {
      if (!paused) tRef.current = (tRef.current + ((now - last) / 1000) * 1) % 420;
      last = now;
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [paused]);
  useEffect(() => {
    window.__store = { setTime: (t) => { tRef.current = t; }, setCam, ready: Boolean(month && hero) };
  }, [month, hero]);
  const plan = useMemo(() => month && { ...month.plan, ...(query.get("price") ? { meat_price: Number(query.get("price")) } : {}),
    ...(query.get("staff") ? { staff_per_shift: Number(query.get("staff")) } : {}) }, [month, query]);
  const base = useMemo(() => (month ? nightOf(month) : null), [month]);
  if (!hero || !month || !plan || !base) return null;
  const weather = (query.get("weather") as Weather) ?? base.weather ?? "clear";
  const competitor = query.has("competitor") ? query.get("competitor") === "1" : base.competitor;
  const night = weather !== "clear" && base.terrace_open ? { ...base, terrace_open: false, events: base.events.filter((e) => !e.table_id?.startsWith("Y")) } : base;
  return (
    <div style={{ position: "fixed", inset: 0, background: "#e9ecef" }}>
      <GLGuard>
        <Suspense fallback={null}>
          <Stage3D hero={hero} night={night} plan={plan} tRef={tRef} mode={cam} monthNum={month.month} weather={weather} competitor={competitor} />
        </Suspense>
      </GLGuard>
    </div>
  );
}
