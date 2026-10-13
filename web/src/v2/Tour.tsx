// Welcome tour (가게 둘러보기; engines/_shared/ui/TOUR-SPEC.md, a 7-stop P&L walk confirmed 2026-10-03): every stop
// is a node of the driver tree and every number on its card comes from web/public/data/tour.json (make tour). A stop
// flies the camera to its anchor, the 사장님 asks about the headline value, the player taps one of four buckets, then
// the card reveals: name, value, formula, parameters (레버 / 근거 / 가정) and the sim's own one-step lever effect. The
// last stop is the month's P&L as a waterfall. Esc or 건너뛰기 ends it at any stop; seen-state lives in localStorage.
import { useCallback, useEffect, useMemo, useState } from "react";
import type { Hero } from "../data";
import { hasWebGL } from "../shared/GLGuard";
import type { SeasonMeta } from "./meta";
import { OwnerFace } from "./MonthCard";
import { Prelim, Tag } from "./parts";
import { PNL_ORDER, type TourData } from "./tourData";

// the camera's flight between stops (UI-SPEC §5 camera token); the card waits for it
export const TOUR_FLY_MS = 1400;

const SEEN_KEY = "v2-tour-done";
export function tourSeen(): boolean {
  try { return localStorage.getItem(SEEN_KEY) === "1"; } catch { return false; }
}
export function markTourSeen() {
  try { localStorage.setItem(SEEN_KEY, "1"); } catch { /* storage blocked: the tour shows again next time */ }
}

// money as everywhere in the game (format.ts man, agents.ko.man_won): rounded first, U+2212 minus, 만원
const MINUS = "−";
export const manKo = (v: number, plus = false) => {
  const r = Math.round(v / 1e4);
  return `${r < 0 ? MINUS : plus && r > 0 ? "+" : ""}${Math.abs(r).toLocaleString("ko-KR")}만원`;
};
const signed = (v: number, unit: string) => (v === 0 ? "그대로" : `${v < 0 ? MINUS : "+"}${Math.abs(v).toLocaleString("ko-KR")}${unit}`);
const pct1 = (v: number) => `${(Math.round(v * 1000) / 10).toLocaleString("ko-KR")}%`;

export function Tour({ hero, data, meta, onStop, onLabel, onDone }: {
  hero: Hero; data: TourData; meta: SeasonMeta | null;
  onStop: (anchor: string) => void; onLabel: (text: string | null) => void; onDone: (completed: boolean) => void;
}) {
  const stops = data.stops;
  const [idx, setIdx] = useState(0);
  const [phase, setPhase] = useState<"fly" | "guess" | "reveal">("fly");
  const [picks, setPicks] = useState<(number | null)[]>([]);
  const reduced = useMemo(() => matchMedia("(prefers-reduced-motion: reduce)").matches, []);
  const month = data.month_ko ?? `${data.month}월`;
  const stop = stops[idx];
  const done = useCallback((completed: boolean) => { markTourSeen(); onDone(completed); }, [onDone]);

  // fly in, then ask
  useEffect(() => {
    onStop(stop.anchor);
    setPhase("fly");
    const id = setTimeout(() => setPhase("guess"), reduced || !hasWebGL() ? 0 : TOUR_FLY_MS);
    return () => clearTimeout(id);
  }, [idx]); // eslint-disable-line react-hooks/exhaustive-deps
  // the world callout at the anchor: the stop's name while asking, name and value once revealed (none on the pull-back)
  useEffect(() => {
    const label = stop.anchor === "room" ? null : phase === "guess" ? stop.title_ko : phase === "reveal" ? `${stop.title_ko} ${stop.display_ko}` : null;
    onLabel(label);
  }, [phase, stop]); // eslint-disable-line react-hooks/exhaustive-deps

  const pick = useCallback((i: number) => {
    if (phase !== "guess") return;
    setPicks((p) => { const n = [...p]; n[idx] = i; return n; });
    setPhase("reveal");
  }, [phase, idx]);
  const next = useCallback(() => {
    if (phase !== "reveal") return;
    if (idx + 1 < stops.length) setIdx(idx + 1);
    else done(true);
  }, [phase, idx, stops.length, done]);

  useEffect(() => {
    const k = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        if (document.querySelector(":popover-open")) return; // Esc first closes an open 근거 / 가정 popover
        e.preventDefault(); done(false); return;
      }
      if (phase === "guess" && /^[1-4]$/.test(e.key)) { e.preventDefault(); pick(Number(e.key) - 1); }
      else if (phase === "reveal" && (e.key === "Enter" || e.key === " " || e.key === "ArrowRight")) {
        if ((e.target as HTMLElement)?.tagName === "BUTTON" && e.key !== "ArrowRight") return; // the focused button handles its own Enter
        e.preventDefault(); next();
      }
    };
    addEventListener("keydown", k);
    return () => removeEventListener("keydown", k);
  }, [phase, pick, next, done]);

  const hits = stops.map((s, i) => (picks[i] == null ? null : picks[i] === s.answer_bucket));
  const scoreLine = idx === stops.length - 1 && phase === "reveal"
    ? `${stops.length}개 중 ${hits.filter(Boolean).length}개 맞힘`
    : hits.some((h) => h != null) ? `${hits.filter((h) => h != null).length}개 중 ${hits.filter(Boolean).length}개 맞힘`
      : "하나 고르면 시뮬레이션 값이 열립니다";
  const result = stop.side === "result";
  const sideKo = stop.side === "cost" ? "비용" : stop.side === "revenue" ? "매출" : "결과";

  return (
    <div className="v2-tour" data-testid="tour" data-stop={stop.criterion_id} data-anchor={stop.anchor} data-phase={phase} aria-live="polite">
      <header className="v2-tour-bar top">
        <span className="t">가게 둘러보기</span>
        <span className="t2" data-testid="tour-baseline">대학로 삼겹살, {hero.area_pyeong}평 1층, {month} {data.baseline_ko ?? "평소 달"}의 손익을 따라갑니다</span>
        <button type="button" className="v2-tour-skip" onClick={() => done(false)} data-testid="tour-skip">건너뛰기 <kbd>Esc</kbd></button>
      </header>
      <footer className="v2-tour-bar bot">
        <ol className="v2-tour-stops" aria-label="둘러볼 곳">
          {stops.map((s, i) => (
            <li key={s.order} className={i === idx ? "now" : i < idx ? "done" : ""} aria-current={i === idx ? "step" : undefined}><b>{s.order}</b>{s.title_ko}</li>
          ))}
        </ol>
        <span className="t2" data-testid="tour-score">{scoreLine}</span>
      </footer>

      {phase !== "fly" && (
        <section key={`${stop.order}-${phase === "guess" ? "g" : "r"}`} className={`v2-tour-card ${result && phase === "reveal" ? "wide" : ""}`} role="dialog"
          aria-label={`${stop.title_ko}, ${sideKo}`}>
          <div className="eh">
            <span className="eyebrow">{stop.order} / {stops.length} · {sideKo} · {stop.title_ko}</span>
            {stop.preliminary && <Prelim input={{ review: data.review, tag: "가정" }} testid="tour-prelim" />}
          </div>
          {phase === "guess" && (
            <div className="v2-tour-owner"><OwnerFace /><p><span className="who">사장님</span>{stop.question_ko}</p></div>
          )}
          <div className={`v2-tour-opts ${phase === "reveal" ? "compact" : ""}`} role="group" aria-label={stop.question_ko}>
            {stop.buckets.map((b, i) => {
              const st = phase === "guess" ? "" : i === stop.answer_bucket ? "right" : i === picks[idx] ? "picked" : "dim";
              const tagTxt = phase === "reveal" ? (i === stop.answer_bucket ? (i === picks[idx] ? "정답, 내 답" : "정답") : i === picks[idx] ? "내 답" : "") : "";
              return (
                <button key={i} type="button" className={`v2-tour-opt ${st}`} disabled={phase !== "guess"} onClick={() => pick(i)} data-option={i}>
                  <span>{b.label_ko}</span>{phase === "guess" ? <kbd>{i + 1}</kbd> : tagTxt && <small>{tagTxt}</small>}
                </button>
              );
            })}
          </div>

          {phase === "reveal" && (
            <div className="v2-tour-val" data-testid="tour-value" data-id={stop.criterion_id} data-raw={stop.value} data-answer={stop.answer_bucket}>
              <div className="row">
                <span className="display num">{stop.display_ko}</span>
              </div>
              <span className="cap" data-testid="tour-reveal">{stop.reveal_ko}</span>
            </div>
          )}
          {phase === "reveal" && stop.formula_ko && (
            <p className="v2-tour-formula" data-testid="tour-formula"><b>{stop.title_ko}</b> = {stop.formula_ko}</p>
          )}
          {phase === "reveal" && !result && stop.params.length > 0 && (
            <div className="v2-tour-params" data-testid="tour-params">
              {stop.params.map((p) => (
                <div key={p.criterion_id} className="r" data-param={p.criterion_id}>
                  <span className="l">{p.name_ko}</span>
                  <span className="v num">{p.display_ko}</span>
                  <span className="c">
                    {p.is_lever ? <span className="v2-lever-tag">레버</span>
                      : <Tag tag={p.source_ids.length ? p.source_ids.join(";") : "가정"} title={p.name_ko} meta={meta} compact />}
                    {p.confidence === "L" && <span className="v2-conf cL" title="신뢰도 낮음">L</span>}
                  </span>
                </div>
              ))}
            </div>
          )}
          {phase === "reveal" && stop.sensitivity.length > 0 && (
            <div className="v2-tour-sens" data-testid="tour-sens">
              {stop.sensitivity.map((s) => (
                <p key={s.lever} data-lever={s.lever}>
                  <b>{s.lever_ko}</b>
                  {s.up && <span>{s.up_ko ?? `${s.step_ko} 올리면`} 영업이익 <i className={s.up.op >= 0 ? "up" : "down"}>{manKo(s.up.op, true)}</i>, 손님 {signed(s.up.covers, "명")}</span>}
                  {s.down && <span>{s.down_ko ?? `${s.step_ko} 내리면`} 영업이익 <i className={s.down.op >= 0 ? "up" : "down"}>{manKo(s.down.op, true)}</i>, 손님 {signed(s.down.covers, "명")}</span>}
                </p>
              ))}
            </div>
          )}
          {phase === "reveal" && result && <Waterfall data={data} />}

          {phase === "reveal" && (
            <div className="foot">
              <span className="cap">{result ? `${month} ${data.baseline_ko ?? "평소 달"}의 빠른 추정, 평판과 단골 효과는 빠져 있습니다` : "숫자는 시뮬레이션과 가게 온톨로지에서 그대로 가져옵니다"}</span>
              <button type="button" className="v2-btn primary" onClick={next} autoFocus data-testid="tour-next">
                {idx + 1 < stops.length ? `다음: ${stops[idx + 1].title_ko}` : `${month} 계획 시작`}
              </button>
            </div>
          )}
        </section>
      )}
    </div>
  );
}

// stop 7: 매출, then each cost line down, then 영업이익 (bars on one scale, the running total as a floating bar)
function Waterfall({ data }: { data: TourData }) {
  const { pnl } = data;
  let run = pnl.revenue;
  const rows: { key: string; label: string; from: number; to: number; v: number; kind: "start" | "step" | "end" }[] = [
    { key: "revenue", label: "매출", from: 0, to: pnl.revenue, v: pnl.revenue, kind: "start" },
  ];
  for (const k of PNL_ORDER) {
    const v = pnl.lines[k];
    rows.push({ key: k, label: pnl.lines_ko?.[k] ?? k, from: run - v, to: run, v: -v, kind: "step" });
    run -= v;
  }
  rows.push({ key: "op", label: "영업이익", from: Math.min(0, pnl.op), to: Math.max(0, pnl.op), v: pnl.op, kind: "end" });
  const max = pnl.revenue || 1;
  const x = (n: number) => `${(Math.max(0, n) / max) * 100}%`;
  return (
    <div className="v2-tour-wf" data-testid="tour-waterfall">
      {rows.map((r) => (
        <div key={r.key} className={`r ${r.kind}`} data-line={r.key} data-v={Math.round(r.v)}>
          <span className="l">{r.label}</span>
          <span className="a" aria-hidden="true"><i className={`b ${r.kind}`} style={{ insetInlineStart: x(r.from), inlineSize: `calc(${x(r.to)} - ${x(r.from)})` }} /></span>
          <span className={`v num ${r.kind === "step" ? "down" : r.kind === "end" ? (r.v >= 0 ? "up" : "down") : ""}`}>
            {manKo(r.v)}{r.kind !== "start" && <small>{pct1(Math.abs(r.v) / max)}</small>}
          </span>
        </div>
      ))}
    </div>
  );
}
