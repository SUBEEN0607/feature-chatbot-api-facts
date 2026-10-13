// Small presentational pieces of the game HUD and screens.
import { useEffect, useRef, useState } from "react";
import { isFlat, man, pct, signed, won, type Band } from "../data";

export const API_BASE: string = (import.meta.env.VITE_API_BASE as string | undefined) ?? "http://localhost:8000";

export type KpiDef = { key: string; label: string; fmt: (v: number) => string; better: "up" | "down" };
const count = (unit: string) => (v: number) => `${Math.round(v).toLocaleString("ko-KR")}${unit}`;

export const HUD_KPIS: KpiDef[] = [
  { key: "revenue", label: "월 매출", fmt: man, better: "up" },
  { key: "op", label: "영업이익", fmt: man, better: "up" },
  { key: "covers", label: "손님 수", fmt: count("명"), better: "up" },
  { key: "walkaways", label: "기다리다 돌아간 팀", fmt: count("팀"), better: "down" },
  { key: "ticket", label: "객단가", fmt: won, better: "up" },
  { key: "table_utilization", label: "테이블 가동률", fmt: (v) => pct(v, 0), better: "up" },
];

export const SETTLE_KPIS: KpiDef[] = [
  HUD_KPIS[0],
  HUD_KPIS[1],
  { key: "op_margin", label: "영업이익률", fmt: (v) => pct(v), better: "up" },
  HUD_KPIS[2],
  HUD_KPIS[4],
  HUD_KPIS[3],
  HUD_KPIS[5],
  { key: "cogs", label: "식재료비", fmt: man, better: "down" },
  { key: "alcohol_share", label: "주류 매출 비중", fmt: (v) => pct(v), better: "up" },
];

export function tone(d: number, k: KpiDef) {
  if (isFlat(d, k.fmt)) return "flat";
  return (k.better === "up" ? d > 0 : d < 0) ? "good" : "bad";
}

// Eases a displayed number toward its target so KPI changes read as a tick, not a jump.
export function useTicker(target: number, ms = 600) {
  const [v, setV] = useState(target);
  const from = useRef(target);
  const vRef = useRef(target);
  useEffect(() => {
    from.current = vRef.current;
    const start = performance.now();
    if (matchMedia("(prefers-reduced-motion: reduce)").matches || ms === 0) {
      vRef.current = target;
      setV(target);
      return;
    }
    let raf = 0;
    const step = (now: number) => {
      const f = Math.min(1, (now - start) / ms);
      const e = 1 - (1 - f) ** 3;
      vRef.current = from.current + (target - from.current) * e;
      setV(vRef.current);
      if (f < 1) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [target, ms]);
  return v;
}

export function KpiCell({ def, value, base, smooth = true, note }: { def: KpiDef; value: number; base: number; smooth?: boolean; note?: string }) {
  const shown = useTicker(value, smooth ? 600 : 0);
  const d = value - base;
  const t = tone(d, def);
  return (
    <div className="g-kpi" data-kpi={def.key} data-value={value}>
      <p className="g-kpi-label">{def.label}</p>
      <p className="g-kpi-value">{def.fmt(shown)}</p>
      <p className={`g-kpi-delta ${t}`}>{t === "flat" ? `평소 ${def.fmt(base)}` : `평소 ${def.fmt(base)}, ${signed(d, def.fmt)}`}</p>
      {note && <p className="g-kpi-note">{note}</p>}
    </div>
  );
}

// p10 to p90 bars for several scenarios on one scale, p50 as a tick.
export function BandBars({ bands }: { bands: { band: Band; cls: string }[] }) {
  const lo = Math.min(...bands.map((b) => b.band.p10));
  const hi = Math.max(...bands.map((b) => b.band.p90));
  const pad = (hi - lo) * 0.08 || Math.abs(hi) * 0.05 || 1;
  const x = (v: number) => ((v - (lo - pad)) / (hi - lo + 2 * pad)) * 100;
  const rowH = 7;
  return (
    <svg className="g-bars" viewBox={`0 0 100 ${bands.length * rowH + 2}`} preserveAspectRatio="none" role="img"
      aria-label="10~90 백분위 범위와 중앙값">
      {bands.map(({ band, cls }, i) => (
        <g key={cls} className={cls}>
          <rect x={x(band.p10)} y={i * rowH + 3} width={Math.max(0.6, x(band.p90) - x(band.p10))} height="3" />
          <rect x={x(band.p50) - 0.5} y={i * rowH + 1} width="1" height="7" />
        </g>
      ))}
    </svg>
  );
}

export const DRIVER_KO: Record<string, string> = { COGS: "원가", "수요(비)": "날씨" };
export const CONF_KO: Record<string, string> = { H: "높음", M: "보통", L: "낮음" };
