// The 정산 reveal (interactivity #8): count-up numbers, a stamp for the owner's mood, a star that fills or cracks.
// Every effect is skipped under prefers-reduced-motion.
import { useEffect, useState } from "react";

const reduced = () => typeof matchMedia !== "undefined" && matchMedia("(prefers-reduced-motion: reduce)").matches;

export function CountUp({ value, format, ms = 750 }: { value: number; format: (v: number) => string; ms?: number }) {
  const [v, setV] = useState(reduced() ? value : 0);
  useEffect(() => {
    if (reduced()) { setV(value); return; }
    let raf = 0;
    const t0 = performance.now();
    const tick = (now: number) => {
      const f = Math.min(1, (now - t0) / ms);
      setV(value * (1 - Math.pow(1 - f, 3)));
      if (f < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [value, ms]);
  return <>{format(v)}</>;
}

const STAMP: Record<string, string> = { great: "대박", ok: "선방", worried: "걱정", desperate: "위기" };
export function MoodStamp({ mood }: { mood?: string }) {
  if (!mood || !STAMP[mood]) return null;
  return <span className={`v2-stamp ${mood}`} data-testid="stamp" aria-label={`사장님 기분: ${STAMP[mood]}`}>{STAMP[mood]}</span>;
}

// A star that fills when the rating rose and cracks when it fell.
export function RatingStar({ delta }: { delta: number }) {
  const up = delta >= 0;
  return (
    <svg className={`v2-star ${up ? "up" : "down"}`} viewBox="0 0 24 24" width="22" height="22" aria-label={up ? "평점 상승" : "평점 하락"}>
      <path d="M12 2.5l2.9 6 6.6.9-4.8 4.6 1.2 6.5L12 17.4l-5.9 3.1 1.2-6.5L2.5 9.4l6.6-.9z" />
      {!up && <path className="crack" d="M12 5l-1.2 4 2.2 2.2-1.8 3.2 1.2 3" />}
    </svg>
  );
}
