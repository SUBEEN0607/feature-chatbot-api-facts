// 운영 계획 board: every lever with its upside, its modelled downside and its 가정/근거 chip, plus the live
// preview from POST /season/{id}/preview (fast analytic estimate, no randomness).
import { useEffect, useRef } from "react";
import { GROUPS, LEVERS, changedKeys, leverDown, leverValueLabel, type Lever } from "./levers";
import { man, manSigned, noArrow, num } from "./format";
import { leaf, type SeasonMeta } from "./meta";
import { Dots, Tag, type Dot } from "./parts";
import type { Label, Plan, PlanPreview } from "./types";

function Control({ l, plan, set }: { l: Lever; plan: Plan; set: (p: Partial<Plan>) => void }) {
  const v = plan[l.key];
  const id = `lv-${l.key}`;
  if (l.kind === "slider") {
    return <input id={id} type="range" min={l.min} max={l.max} step={l.step} value={v as number} aria-valuetext={l.fmt?.(v as number)}
      onChange={(e) => set({ [l.key]: Number(e.target.value) } as Partial<Plan>)} data-lever={l.key} />;
  }
  if (l.kind === "stepper") {
    const n = v as number;
    return (
      <span className="v2-step" data-lever={l.key}>
        <button type="button" aria-label={`${l.label} 줄이기`} disabled={n <= (l.min ?? 0)} onClick={() => set({ [l.key]: n - (l.step ?? 1) } as Partial<Plan>)}>−</button>
        <output htmlFor={id} aria-live="polite">{l.fmt ? l.fmt(n) : n}</output>
        <button type="button" aria-label={`${l.label} 늘리기`} disabled={n >= (l.max ?? 99)} onClick={() => set({ [l.key]: n + (l.step ?? 1) } as Partial<Plan>)}>+</button>
      </span>
    );
  }
  if (l.kind === "toggle") {
    return <button id={id} type="button" role="switch" aria-checked={Boolean(v)} aria-label={l.label} className="v2-switch" data-lever={l.key}
      onClick={() => set({ [l.key]: !v } as Partial<Plan>)} />;
  }
  if (l.kind === "multi") {
    const arr = v as string[];
    return (
      <span className="v2-seg" role="group" aria-label={l.label} data-lever={l.key}>
        {l.options!.map((o) => {
          const on = arr.includes(o.value as string);
          return <button key={o.value} type="button" aria-pressed={on}
            onClick={() => set({ [l.key]: on ? arr.filter((x) => x !== o.value) : [...arr, o.value] } as Partial<Plan>)}>{o.label}</button>;
        })}
      </span>
    );
  }
  return (
    <span className="v2-seg" role="group" aria-label={l.label} data-lever={l.key}>
      {l.options!.map((o) => (
        <button key={o.value} type="button" aria-pressed={v === o.value} onClick={() => set({ [l.key]: o.value } as Partial<Plan>)}>{o.label}</button>
      ))}
    </span>
  );
}

export function leverTag(l: Lever, meta: SeasonMeta | null, labels: Label[] = [], plan?: Plan) {
  const lab = l.mechanism ? labels.find((x) => x.mechanism === l.mechanism) : undefined;
  if (lab) return { tag: lab.tag, note: noArrow(lab.label) + (lab.detail ? `. ${lab.detail}` : ""), downside: lab.downside ?? leverDown(l, meta) };
  // a choice lever whose options each carry their own tag (원육, 위생): the selected option decides
  const own = plan && typeof plan[l.key] === "string" ? leaf(meta, `${String(l.key)}.${plan[l.key]}`) : null;
  if (own?.tag) return { tag: String(own.tag), note: (own.note as string) ?? null, downside: leverDown(l, meta) };
  for (const p of l.tagPaths) {
    const lf = leaf(meta, p);
    if (lf?.tag) return { tag: String(lf.tag), note: (lf.note as string) ?? null, downside: leverDown(l, meta) };
  }
  return { tag: "가정", note: null, downside: leverDown(l, meta) };
}

export function Levers({ plan, base, set, meta, labels, only, locked, focus, onHover }: {
  plan: Plan; base: Plan; set: (p: Partial<Plan>) => void; meta: SeasonMeta | null; labels?: Label[]; only?: string[];
  locked?: Set<string>; focus?: string | null; onHover?: (key: keyof Plan | null) => void;
}) {
  const changed = new Set(changedKeys(plan, base));
  const focusRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (focus) focusRef.current?.scrollIntoView({ block: "center", behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
  }, [focus]);
  return (
    <>
      {GROUPS.filter((g) => (!only || only.includes(g)) && (!locked || LEVERS.some((l) => l.group === g && !locked.has(l.key)))).map((g) => (
        <div className="v2-group" key={g}>
          <h3>{g}</h3>
          {LEVERS.filter((l) => l.group === g).map((l) => {
            const t = leverTag(l, meta, labels, plan);
            if (locked?.has(l.key)) return null;
            return (
              <div key={l.key} ref={focus === l.key ? focusRef : undefined}
                className={`v2-lever ${changed.has(l.key) ? "changed" : ""} ${focus === l.key ? "focus" : ""}`} data-lever-card={l.key}
                onPointerEnter={() => onHover?.(l.key)} onPointerLeave={() => onHover?.(null)} onFocus={() => onHover?.(l.key)} onBlur={() => onHover?.(null)}>
                <div className="v2-lever-top">
                  <label className="name" htmlFor={`lv-${l.key}`}>{l.label} <Tag tag={t.tag} title={l.label} note={t.note} downside={t.downside} meta={meta} /></label>
                  {(l.kind === "slider") && <span className="val">{leverValueLabel(l, plan[l.key])}</span>}
                </div>
                <Control l={l} plan={plan} set={set} />
                <div className="v2-trade">
                  <b className="plus">얻는 것</b><span>{l.up}</span>
                  <b className="minus">대가</b><span>{leverDown(l, meta)}</span>
                </div>
              </div>
            );
          })}
        </div>
      ))}
      {locked && locked.size > 0 && (
        <div className="v2-group v2-locked-list" data-testid="locked-levers">
          <h3>2월차부터 열리는 레버</h3>
          <p>{LEVERS.filter((l) => locked.has(l.key)).map((l) => <span key={l.key} className="v2-lever locked" data-lever-card={l.key} data-locked="1">{l.label}</span>)}</p>
        </div>
      )}
    </>
  );
}

export function PreviewStrip({ preview, status, prevOp, meta, stale = false, coversDots, dotStep }: { preview: PlanPreview | null; status: "idle" | "loading" | "error"; prevOp?: number | null; meta: SeasonMeta | null; stale?: boolean; coversDots?: Dot | null; dotStep?: string | null }) {
  if (!preview) {
    return <div className="v2-preview loading" data-testid="preview"><span className="v2-note">{status === "error" ? "미리보기를 불러오지 못했습니다. API가 켜져 있는지 확인하세요." : "예상 영업이익을 계산하는 중입니다"}</span></div>;
  }
  const e = preview.expected;
  const overload = Boolean(preview.op_range?.overload || preview.warning_codes?.includes("overload"));
  return (
    <div className={`v2-preview ${stale ? "loading" : ""}`} data-testid="preview" data-op={e.op} data-overload={overload ? "1" : "0"} data-stale={stale ? "1" : "0"}
      data-p10={preview.op_range?.p10} data-p90={preview.op_range?.p90} data-base-op={preview.vs_base.base_op} data-vs-base={preview.vs_base.op}>
      <div className="v2-preview-row">
        <span className="v2-note">이 계획의 평균 예상 영업이익 (빠른 추정){stale ? ", 다시 계산하는 중" : ""}</span>
        <span className={`delta ${preview.vs_base.op > 0 ? "up" : preview.vs_base.op < 0 ? "down" : "flat"}`}>평소 대비 {manSigned(preview.vs_base.op)}</span>
      </div>
      {preview.vs_baseline && (
        <p className="v2-note" data-testid="vs-baseline-month" data-base-op={preview.vs_baseline.base_op} data-delta={preview.vs_baseline.op}>
          {preview.vs_baseline.label_ko} {man(preview.vs_baseline.base_op)} 대비 {manSigned(preview.vs_baseline.op)}{preview.vs_baseline.events_ko.length ? `: 이번 달 ${preview.vs_baseline.events_ko.join(", ")}` : ""}
        </p>
      )}
      {preview.vs_base.base_op != null && (
        <p className="v2-note">이번 달 사건에 평소 계획을 쓴 평균 예상 {man(preview.vs_base.base_op)}: {preview.vs_base.basis ?? "이번 달 평소 계획"}</p>
      )}
      <div className="v2-preview-row">
        <span className={`big ${e.op < 0 ? "down" : ""} ${overload ? "unsure" : ""}`} title={overload ? "일손이 모자라는 계획이라 빠른 추정이 불안정합니다" : undefined}>{overload ? "약 " : ""}{man(e.op)}</span>
        {prevOp != null && <span className="v2-note">지난달 결과 {man(prevOp)}</span>}
      </div>
      {dotStep && <p className="v2-dots-caption" data-testid="dot-caption">{dotStep} 위쪽 지표에 붙은 점: 초록 +는 좋아지고 빨강 −는 나빠집니다. 점이 많을수록 크게 움직입니다.{coversDots?.n ? <> 손님 수 <Dots d={coversDots} testid="dot-covers" /></> : null}</p>}
      <div className="v2-preview-sub">
        <span>손님 {num(e.covers)}명</span><span>매출 {man(e.revenue)}</span><span>돌아간 팀 {num(e.walkaways, 0)}</span>
        <span>피로 {Math.round(preview.state_next.fatigue)}</span>
        {preview.state_next.quit_risk > 0.12 && <span className="down">퇴사 위험 {Math.round(preview.state_next.quit_risk * 100)}%</span>}
      </div>
      {preview.op_range && (
        <p className={overload ? "v2-range-loud" : "v2-note"} data-testid="preview-range" title={preview.op_range.tag}>{overload ? "추정이 불안정합니다. 범위로 보세요: " : "운에 따라 "}{man(preview.op_range.p10)} ~ {man(preview.op_range.p90)} (p10~p90{preview.op_range.error ? `, 추정 오차 ±${man(preview.op_range.error)} 포함` : ""})</p>
      )}
      {preview.lunch && (
        <p className={`v2-note ${preview.lunch.net < 0 ? "down" : ""}`}>점심 영업: 매출 {man(preview.lunch.revenue)}, 비용 {man(preview.lunch.cost)}, 남는 것 {manSigned(preview.lunch.net)}</p>
      )}
      {preview.risks?.map((r) => (
        <p key={r.id} className="v2-warn" data-risk={r.id}>
          위험: {r.label}, 매달 {Math.round(r.prob * 100)}% 확률, 일어나면 영업이익 {manSigned(r.op_delta)} <Tag tag={r.tag} title={r.label} meta={meta} />
        </p>
      ))}
      {preview.warnings.map((w, i) => {
        const text = typeof w === "string" ? w : (w as { text: string }).text;
        const code = preview.warning_codes?.[i] ?? (typeof w === "string" ? "" : (w as { code: string }).code);
        if (code.startsWith("risk:") || code === "lunch_negative") return null; // shown above as structured lines
        return <p key={text} className="v2-warn">{text}</p>;
      })}
    </div>
  );
}
