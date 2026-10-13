// Small v2 pieces: the clickable 가정/근거 tag, sparklines, the profit waterfall, the p10-p90 band, review cards.
import { useId, useRef, useState } from "react";
import { SEGMENTS } from "../replay/timeline";
import { man, manSigned } from "./format";
import { parseTag, REASON_KO, reviewFallback, SEGMENT_KO, type SeasonMeta } from "./meta";
import { leverLabel, leversInNote, REASON_LEVER } from "./levers";
import type { Draw, Plan, Review, WaterfallStep } from "./types";

// 가정 / 근거 chip. Click opens a popover with the rationale, the downside and the sources' titles.
export function Tag({ tag, title, note, downside, meta, compact = false }: {
  tag?: string | null; title?: string; note?: string | null; downside?: string | null; meta: SeasonMeta | null; compact?: boolean;
}) {
  const info = parseTag(tag);
  const id = useId().replace(/:/g, "");
  const btn = useRef<HTMLButtonElement>(null);
  const [pos, setPos] = useState<{ top: number; left: number } | null>(null);
  const label = info.assume ? "가정" : `근거 ${info.ids.join(", ")}`;
  const open = () => {
    const r = btn.current?.getBoundingClientRect();
    if (r) setPos({ top: Math.min(window.innerHeight - 220, r.bottom + 6), left: Math.max(8, Math.min(window.innerWidth - 350, r.left - 40)) });
  };
  return (
    <>
      <button ref={btn} type="button" className={`v2-tag ${info.assume ? "assume" : "sourced"}`} popoverTarget={`pop-${id}`}
        onClick={open} aria-label={`${label}: ${title ?? "설명 보기"}`} data-tag={info.assume ? "assume" : "source"}>
        {compact && !info.assume ? info.ids[0] ?? "근거" : label}
      </button>
      <span id={`pop-${id}`} popover="auto" className="v2-pop" style={pos ? { top: pos.top, left: pos.left } : undefined}>
        {title && <strong className="h">{title}</strong>}
        {info.assume && <span className="p">근거 자료가 아직 없어 추정값으로 넣은 메커니즘입니다. 사장님 인터뷰로 확인할 항목입니다.</span>}
        {note && <span className="p">{note}</span>}
        {downside && <span className="p"><b>대가:</b> {downside}</span>}
        {info.ids.map((s) => {
          const src = meta?.sources[s];
          return <span key={s} className="p" data-src="1">{s} {src ? `${src.title}, ${src.by} (${src.year})` : ""}</span>;
        })}
      </span>
    </>
  );
}

// PRELIMINARY badge (N11): shown while the value under it is not signed off. Reasons come from the data itself: the
// 사람 검토 count (hero.json review, rows with reviewed_by), the row's own reviewed flag, a 가정 tag, confidence L.
export type PrelimInput = { review?: { reviewed: number; total: number } | null; reviewed?: boolean | null; tag?: string | null;
  confidence?: string | null; range?: string | null };
export function prelimReasons({ review, reviewed, tag, confidence, range }: PrelimInput): string[] {
  const out: string[] = [];
  if (reviewed === false) out.push("이 값은 아직 사람 검토 전입니다");
  if (review && review.reviewed < review.total) out.push(`가게 추정값 ${review.total}개 중 사람 검토를 마친 값 ${review.reviewed}개`);
  if (tag !== undefined && parseTag(tag).assume) out.push("근거 자료 없이 넣은 가정이 들어 있습니다");
  if (confidence === "L") out.push(`신뢰도 낮음 (L)${range ? `, 추정 범위 ${range}` : ""}`);
  return out;
}
export function Prelim({ input, testid, plain = false }: { input: PrelimInput; testid?: string; plain?: boolean }) {
  const reasons = prelimReasons(input);
  const id = useId().replace(/:/g, "");
  const btn = useRef<HTMLButtonElement>(null);
  const [pos, setPos] = useState<{ top: number; left: number } | null>(null);
  if (!reasons.length) return null;
  // print and other static surfaces: the badge and its reasons as text, no popover
  if (plain) return <span className="v2-prelim" data-testid={testid ?? "prelim"} title={reasons.join(", ")}>PRELIMINARY</span>;
  const open = () => {
    const r = btn.current?.getBoundingClientRect();
    if (r) setPos({ top: Math.min(window.innerHeight - 160, r.bottom + 6), left: Math.max(8, Math.min(window.innerWidth - 350, r.right - 300)) });
  };
  return (
    <>
      <button ref={btn} type="button" className="v2-prelim" popoverTarget={`prelim-${id}`} onClick={open} data-testid={testid ?? "prelim"}
        data-reasons={reasons.length} aria-label={`PRELIMINARY: ${reasons.join(", ")}`}>PRELIMINARY</button>
      <span id={`prelim-${id}`} popover="auto" className="v2-pop" style={pos ? { top: pos.top, left: pos.left } : undefined}>
        <strong className="h">검토 전 값</strong>
        {reasons.map((r) => <span key={r} className="p">{r}</span>)}
        <span className="p">숫자 옆 근거와 가정 표시를 누르면 출처와 이유가 나옵니다</span>
      </span>
    </>
  );
}

export function Spark({ values, w = 72, h = 22, zero = false, className = "" }: { values: number[]; w?: number; h?: number; zero?: boolean; className?: string }) {
  if (values.length < 2) return <svg className={`v2-spark ${className}`} width={w} height={h} aria-hidden="true" />;
  const lo = Math.min(...values, zero ? 0 : Infinity), hi = Math.max(...values, zero ? 0 : -Infinity);
  const y = (v: number) => (hi === lo ? h / 2 : h - 2 - ((v - lo) / (hi - lo)) * (h - 4));
  const x = (i: number) => (i / (values.length - 1)) * (w - 4) + 2;
  const d = values.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join("");
  const last = values[values.length - 1];
  return (
    <svg className={`v2-spark ${className}`} width={w} height={h} aria-hidden="true">
      {zero && lo < 0 && <line x1={0} x2={w} y1={y(0)} y2={y(0)} stroke="oklch(0.57 0.17 33)" strokeDasharray="2 2" strokeWidth={1} />}
      <path d={d} fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinejoin="round" />
      <circle cx={x(values.length - 1)} cy={y(last)} r={2.4} fill="currentColor" />
    </svg>
  );
}

export function Stars({ n }: { n: number }) {
  const k = Math.max(0, Math.min(5, Math.round(n)));
  return <span className="stars" aria-label={`별 ${k}개`}>{"★".repeat(k)}{"☆".repeat(5 - k)}</span>;
}

// Waterfall: 평소 영업이익, then each driver's signed change, then this month's operating profit.
export function CauseChip({ lever, onCause }: { lever: keyof Plan; onCause?: (k: keyof Plan) => void }) {
  if (!onCause) return <span className="v2-cause static" data-cause={lever}>{leverLabel(lever)}</span>;
  return (
    <button type="button" className="v2-cause" data-cause={lever} onClick={(e) => { e.stopPropagation(); onCause(lever); }}
      title={`다음 달 계획판에서 ${leverLabel(lever)} 열기`}>{leverLabel(lever)}</button>
  );
}

export function Waterfall({ steps, onCause }: { steps: WaterfallStep[]; onCause?: (k: keyof Plan) => void }) {
  let run = 0;
  const rows = steps.map((s) => {
    if (s.kind === "start") { run = s.delta; return { ...s, a: 0, b: s.delta }; }
    if (s.kind === "end") return { ...s, a: 0, b: s.delta };
    const a = run;
    run += s.delta;
    return { ...s, a, b: run };
  });
  const lo = Math.min(0, ...rows.flatMap((r) => [r.a, r.b]));
  const hi = Math.max(0, ...rows.flatMap((r) => [r.a, r.b]));
  const pct = (v: number) => ((v - lo) / (hi - lo || 1)) * 100;
  return (
    <div className="v2-wf" data-testid="waterfall">
      {rows.map((r) => {
        const cls = r.kind === "start" ? "base" : r.kind === "end" ? "end" : r.delta >= 0 ? "pos" : "neg";
        const quiet = r.kind === "step" && Math.abs(r.delta) < 10000;
        return (
          <div key={r.key} className={`v2-wf-row ${r.kind !== "step" ? "total" : ""} ${quiet ? "quiet" : ""}`} data-key={r.key} data-value={r.delta}>
            <span className="l" title={r.note ? `${r.driver}: ${r.note}` : r.driver}>{r.driver}
              {r.kind === "step" && (r.levers ?? leversInNote(r.note)).length > 0 && (
                <span className="wf-causes">{(r.levers ?? leversInNote(r.note)).map((k) => <CauseChip key={k} lever={k} onCause={onCause} />)}</span>
              )}</span>
            <span className="v2-wf-track" aria-hidden="true">
              <i className="zero" style={{ insetInlineStart: `${pct(0)}%` }} />
              <i className={`bar ${cls}`} style={{ insetInlineStart: `${pct(Math.min(r.a, r.b))}%`, inlineSize: `${Math.abs(pct(r.b) - pct(r.a))}%` }} />
            </span>
            <span className={`v ${r.kind === "step" ? (r.delta > 0 ? "up" : r.delta < 0 ? "down" : "flat") : ""}`}>
              {r.kind === "step" ? manSigned(r.delta) : man(r.delta)}
            </span>
          </div>
        );
      })}
    </div>
  );
}

// Where this month's single draw landed inside the p10-p90 range of 30 runs.
export function Band({ draw }: { draw: Draw }) {
  const p10 = draw.p10.op, p90 = draw.p90.op, p50 = draw.p50.op, v = draw.kpis.op;
  const lo = Math.min(p10, v, 0), hi = Math.max(p90, v);
  const x = (n: number) => `${((n - lo) / (hi - lo || 1)) * 100}%`;
  const where = v < p10 ? "운이 나쁜 쪽 바깥" : v > p90 ? "운이 좋은 쪽 바깥" : v < p50 ? "중간보다 아래" : "중간보다 위";
  return (
    <div className="v2-band" data-testid="band">
      <div className="v2-band-track">
        <i className="rng" style={{ insetInlineStart: x(p10), inlineSize: `calc(${x(p90)} - ${x(p10)})` }} />
        <i className="p50" style={{ insetInlineStart: x(p50) }} />
        <i className="draw" style={{ insetInlineStart: x(v) }} />
      </div>
      <div className="v2-band-legend"><span>p10 {man(p10)}</span><span>중간 {man(p50)}</span><span>p90 {man(p90)}</span></div>
      <p className="v2-note" data-testid="percentile" data-value={draw.op_percentile ?? ""}>
        같은 계획을 {draw.band_runs ?? 30}번 돌린 범위입니다. 이번 달은 {where}에 떨어졌습니다
        {draw.op_percentile != null && <> (아래에서 {Math.round(draw.op_percentile * 100)}% 지점)</>}. 운이 좋은 달과 계획이 좋은 달은 다릅니다.
      </p>
    </div>
  );
}

export function ReviewCard({ r, plan, onAsk, onCause }: { r: Review; plan?: Plan; onAsk?: (r: Review) => void; onCause?: (k: keyof Plan) => void }) {
  const codes = r.shown_codes ?? r.reason_codes;
  const causes = [...new Set(((r.cause_levers ?? r.levers) as (keyof Plan)[] | undefined) ?? codes.map((c) => REASON_LEVER[c]).filter(Boolean))];
  const NEG = new Set(["wait_long", "service_slow", "price_high", "meat_bad", "banchan_poor", "dirty", "soju_high", "crowded", "hyped", "understaffed", "tired_staff", "reviews_inflated"]);
  return (
    <div className="v2-review-wrap">
    <button type="button" className="v2-review" onClick={() => onAsk?.(r)} data-review={r.id} aria-label={`${SEGMENT_KO[r.segment]} 손님 리뷰, 눌러서 질문하기`}>
      <span className="h">
        <i className="v2-seg-dot" style={{ background: SEGMENTS[r.segment]?.color }} />
        <span className="seg">{r.segment_ko ?? SEGMENT_KO[r.segment]}</span>
        <Stars n={r.stars} />
        {(r.event_label ?? (r.incentivized ? "이벤트 참여" : null)) && <span className="evt">{r.event_label ?? "이벤트 참여"}</span>}
      </span>
      <span className="t">{reviewFallback(r, plan)}</span>
      {codes.length > 0 && (
        <span className="codes">{codes.map((c) => <span key={c} className={NEG.has(c) ? "neg" : ""}>{REASON_KO[c] ?? c}</span>)}</span>
      )}
    </button>
    {causes.length > 0 && <span className="v2-review-causes">원인 {causes.map((k) => <CauseChip key={k} lever={k} onCause={onCause} />)}</span>}
    </div>
  );
}

export function Meter({ value, max = 100, hot = 70 }: { value: number; max?: number; hot?: number }) {
  return <span className={`v2-meter ${value >= hot ? "hot" : ""}`} aria-hidden="true"><i style={{ inlineSize: `${Math.min(100, (value / max) * 100)}%` }} /></span>;
}

// Consequence dots (interactivity #3): while a lever is hovered or dragged, the meters it moves light up; size =
// how strongly (one step of that lever, from preview.sensitivity), no direction, as in Reigns.
// A dot carries a sign: d = level (1..3), good = the move helps the store (green +) or hurts it (red −).
export type Dot = { n: number; good: boolean };
export function Dots({ d, testid }: { d?: Dot | null; testid?: string }) {
  if (!d || !d.n) return null;
  const word = ["", "조금", "보통으로", "크게"][d.n];
  return (
    <span className={`v2-dots d${d.n} ${d.good ? "good" : "bad"}`} data-testid={testid} data-dots={d.n} data-sign={d.good ? "+" : "-"}
      aria-label={`이 레버를 움직이면 ${word} ${d.good ? "좋아짐" : "나빠짐"}`}>
      <b aria-hidden="true">{d.good ? "+" : "−"}</b>{Array.from({ length: d.n }, (_, i) => <i key={i} />)}
    </span>
  );
}
export function dotLevel(v: number | undefined, small: number, big: number) {
  const a = Math.abs(v ?? 0);
  return a >= big ? 3 : a >= small ? 2 : a > small / 4 ? 1 : 0;
}
