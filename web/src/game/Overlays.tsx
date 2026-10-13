// The game screens over the store: 사건 고르기, 사건 카드, 사장님의 선택, 월말 정산, 시즌 결산.
import { useState } from "react";
import { man, signed, type Evidence, type RunIndex } from "../data";
import { BandBars, CONF_KO, DRIVER_KO, SETTLE_KPIS, tone } from "./parts";
import { moved, type MonthRecord } from "./season";

export const ACTION_ORDER = ["absorb", "reprice", "discount", "reprice_alcohol", "cut_staff_hours", "cut_staff", "change_mix"];
const shockOrder = (index: RunIndex) => Object.keys(index.shocks).sort((a, b) => a.localeCompare(b, "en", { numeric: true }));

// "인터뷰로 확인 필요": shown when the card's effect rests on a confidence-L mechanism; tap or hover for the reason.
export function Badge({ ev, on }: { ev?: Evidence; on: boolean }) {
  const [open, setOpen] = useState(false);
  if (!on || !ev?.needs_interview) return null;
  return (
    <span className="g-badge-wrap">
      <button type="button" className="g-badge" title={ev.reasons.join(" ")} aria-expanded={open}
        onClick={(e) => { e.stopPropagation(); setOpen((o) => !o); }}>
        인터뷰로 확인 필요
      </button>
      {open && <span className="g-badge-reason" role="note">{ev.reasons.join(" ")}</span>}
    </span>
  );
}

export const STAFF_LIMIT = "한계: 인력 감축, 근무시간 단축, 추가 권유처럼 효과의 근거가 없는 선택지는 사장님 인터뷰로 확인하기 전까지 제외했습니다";

export function EventPicker({ index, month, months, badges, onPick }: {
  index: RunIndex; month: number; months: number; badges: boolean; onPick: (id: string) => void;
}) {
  const order = shockOrder(index);
  const draw = () => onPick(order[Math.floor(Math.random() * order.length)]);
  return (
    <section className="g-sheet g-events" role="dialog" aria-labelledby="g-events-title">
      <header className="g-sheet-head">
        <p className="g-step">{month}월차 / {months}개월 시즌</p>
        <h2 id="g-events-title">이번 달에는 어떤 일이 생길까요</h2>
        <button className="g-btn g-btn-primary" onClick={draw}>무작위로 뽑기</button>
        {index.excluded?.includes("SH07") && <p className="g-limit" data-testid="limit-events">{STAFF_LIMIT}</p>}
      </header>
      <ul className="g-event-grid">
        {order.map((id) => {
          const s = index.shocks[id];
          return (
            <li key={id} className="g-card-wrap">
              <button className="g-event-card" onClick={() => onPick(id)} data-shock={id}>
                <span className="g-tag">{DRIVER_KO[s.driver] ?? s.driver}</span>
                <span className="g-event-title">{s.label}</span>
                <span className="g-event-mech">{s.params[0]?.mechanism}</span>
              </button>
              <Badge ev={s.evidence} on={badges} />
            </li>
          );
        })}
      </ul>
    </section>
  );
}

export function ImpactCard({ index, shock, headline, month, badges, lasting, onNext }: {
  index: RunIndex; shock: string; headline: string; month: number; badges: boolean; lasting: string[]; onNext: () => void;
}) {
  const s = index.shocks[shock];
  return (
    <section className="g-sheet g-impact" role="dialog" aria-labelledby="g-impact-title">
      <p className="g-step">{month}월차 사건</p>
      <p className="g-tag g-tag-shock">{DRIVER_KO[s.driver] ?? s.driver}</p>
      <h2 id="g-impact-title" className="g-event-big">{s.label}</h2>
      <p className="g-headline" data-testid="shock-headline">{headline}</p>
      {lasting.length > 0 && <p className="g-lasting">유지 중인 선택이 반영된 숫자입니다: {lasting.join(", ")}</p>}
      <ul className="g-mech">
        {s.params.map((p) => (
          <li key={p.parameter}>{p.mechanism}. {p.rationale}. 근거 수준 {CONF_KO[p.confidence] ?? p.confidence}.</li>
        ))}
      </ul>
      {badges && s.evidence?.needs_interview && (
        <p className="g-interview"><b>인터뷰로 확인 필요</b> {s.evidence.reasons.join(" ")}</p>
      )}
      <button className="g-btn g-btn-primary g-wide" onClick={onNext}>사장님의 선택</button>
    </section>
  );
}

export type ChoiceRow = { action: string; op: number; vsShock: number; vsBase: number; applied: boolean };

export function ChoiceCards({ index, shock, rows, badges, lasting, review, onChoose }: {
  index: RunIndex; shock: string; rows: ChoiceRow[]; badges: boolean; lasting: string[];
  review?: { reviewed: number; total: number }; onChoose: (a: string) => void;
}) {
  return (
    <section className="g-sheet g-choices" role="dialog" aria-labelledby="g-choice-title">
      <header className="g-sheet-head">
        <p className="g-step">{index.shocks[shock].label}</p>
        <h2 id="g-choice-title">사장님의 선택</h2>
        <p className="g-sub">
          고른 선택은 다음 달에도 이어집니다. 숫자는 200번 돌린 한 달의 중앙값이고, 추정값 중 사람이 검토한 것은 {review ? `${review.reviewed}/${review.total}` : "아직 없음"}입니다.
          {lasting.length > 0 && ` 지금 유지 중: ${lasting.join(", ")}.`}
        </p>
        {(index.excluded ?? []).some((x) => !x.startsWith("SH")) && <p className="g-limit" data-testid="limit-choices">{STAFF_LIMIT}</p>}
      </header>
      <ul className="g-choice-grid">
        {rows.map((r) => {
          const act = index.actions[r.action];
          const t = r.action === "absorb" ? "flat" : r.vsShock > 0 ? "good" : r.vsShock < 0 ? "bad" : "flat";
          return (
            <li key={r.action} className="g-card-wrap">
              <button className={`g-choice-card ${r.applied ? "is-applied" : ""}`} onClick={() => onChoose(r.action)}
                data-action={r.action} data-op={r.op} data-applied={r.applied}>
                {badges && act.evidence?.needs_interview && <span className="g-badge-space" aria-hidden="true" />}
                <span className="g-choice-title">{act.label}</span>
                <span className="g-choice-desc">{r.applied ? "이미 적용 중입니다. 고르면 이번 달에도 그대로 유지합니다" : act.description}</span>
                <span className="g-choice-op"><small>예상 영업이익</small>{man(r.op)}</span>
                <span className={`g-choice-delta ${t}`}>
                  {r.action === "absorb" ? `평소보다 ${signed(r.vsBase, man)}` : `버틸 때보다 ${signed(r.vsShock, man)}`}
                </span>
              </button>
              <Badge ev={act.evidence} on={badges} />
            </li>
          );
        })}
      </ul>
    </section>
  );
}

export function Settlement({ rec, index, total, totalBase, last, badges, onNext, onStats, onAsk, nextLabel }: {
  rec: MonthRecord; index: RunIndex; total: number; totalBase: number; last: boolean; badges: boolean;
  onNext: () => void; onStats: () => void; onAsk?: () => void; nextLabel?: string;
}) {
  const shockMove = moved(rec.drivers.base, rec.drivers.shocked)[0];
  const choiceMove = moved(rec.drivers.shocked, rec.drivers.reacted)[0];
  const s = index.shocks[rec.shock], a = index.actions[rec.action];
  const flagged = [s.evidence, a.evidence].filter((e) => badges && e?.needs_interview) as Evidence[];
  const reasons = [...new Set(flagged.flatMap((e) => e.reasons))];
  return (
    <section className="g-receipt-scroll" role="dialog" aria-labelledby="g-settle-title" data-testid="settlement">
      <div className="g-receipt">
        <header>
          <h2 id="g-settle-title">{rec.month}월차 정산</h2>
          <p className="g-receipt-meta">{s.label}, {a.label}</p>
          {rec.lasting.length > 0 && <p className="g-receipt-meta">유지 중: {rec.lasting.join(", ")}</p>}
        </header>
        <p className="g-headline" data-testid="settle-headline">{rec.headline}</p>
        <table className="g-receipt-table">
          <thead>
            <tr><th scope="col">항목</th><th scope="col">평소</th><th scope="col">사건만</th><th scope="col">선택 후</th><th scope="col" className="g-col-bars"><span className="sr">범위</span></th></tr>
          </thead>
          <tbody>
            {SETTLE_KPIS.map((k) => {
              const b = rec.base[k.key], sh = rec.shocked[k.key], r = rec.reacted[k.key];
              return (
                <tr key={k.key} data-kpi={k.key}>
                  <th scope="row">{k.label}</th>
                  <td data-col="base" data-value={b.p50}>{k.fmt(b.p50)}</td>
                  <td data-col="shocked" data-value={sh.p50} className={tone(sh.p50 - b.p50, k)}>{k.fmt(sh.p50)}</td>
                  <td data-col="reacted" data-value={r.p50} className={tone(r.p50 - b.p50, k)}>{k.fmt(r.p50)}</td>
                  <td className="g-col-bars"><BandBars bands={[{ band: b, cls: "bb-base" }, { band: sh, cls: "bb-shock" }, { band: r, cls: "bb-react" }]} /></td>
                </tr>
              );
            })}
          </tbody>
        </table>
        <p className="g-legend"><i className="lg-base" />평소 <i className="lg-shock" />사건만 <i className="lg-react" />선택 후. 막대는 10~90 백분위, 세로선은 중앙값.</p>
        {flagged.length > 0 && (
          <div className="g-interview" data-testid="settle-interview">
            <b>인터뷰로 확인 필요</b>
            {reasons.map((r) => <span key={r}> {r}</span>)}
          </div>
        )}
        <div className="g-receipt-foot">
          <div className="g-moved">
            <p>{rec.lasting.length ? "사건과 유지 중인 선택 때문에" : "사건 때문에"} 가장 크게 움직인 항목은 <b>{shockMove.label}</b>입니다 (영업이익에 {signed(shockMove.op_effect, man)}).</p>
            {rec.stateAfter === rec.stateBefore ? (
              <p>이번 달 선택으로 새로 바뀐 것은 없습니다.</p>
            ) : (
              <p>선택으로 가장 크게 움직인 항목은 <b>{choiceMove.label}</b>입니다 (영업이익에 {signed(choiceMove.op_effect, man)}).</p>
            )}
          </div>
          <div>
            <div className="g-total" data-testid="cumulative" data-value={total}>
              <span>누적 영업이익 ({rec.month}개월)</span>
              <strong>{man(total)}</strong>
              <span className={total >= totalBase ? "good" : "bad"}>평소대로였다면 {man(totalBase)}</span>
            </div>
          </div>
        </div>
        <div className="g-receipt-actions">
          {onAsk && <button className="g-btn" onClick={onAsk}>사장님에게 묻기</button>}
          <button className="g-btn" onClick={onStats}>가게 능력치 보기</button>
          <button className="g-btn g-btn-primary" onClick={onNext}>{nextLabel ?? (last ? "시즌 결산" : "다음 달")}</button>
        </div>
      </div>
    </section>
  );
}

export function SeasonSummary({ history, index, lasting, onOpen, onRestart }: {
  history: MonthRecord[]; index: RunIndex; lasting: string[]; onOpen: (m: number) => void; onRestart: () => void;
}) {
  const total = history.reduce((s, m) => s + m.op, 0);
  const totalBase = history.reduce((s, m) => s + m.baseOp, 0);
  const best = history.reduce((a, b) => (b.op > a.op ? b : a));
  const worst = history.reduce((a, b) => (b.op < a.op ? b : a));
  return (
    <section className="g-receipt-scroll" role="dialog" aria-labelledby="g-season-title" data-testid="season-summary">
      <div className="g-receipt g-season">
        <header>
          <p className="g-step">{history.length}개월 시즌</p>
          <h2 id="g-season-title">시즌 결산</h2>
        </header>
        <div className="g-season-total" data-testid="season-total" data-value={total} data-base={totalBase}>
          <div><span>누적 영업이익</span><strong>{man(total)}</strong></div>
          <div><span>평소대로였다면</span><strong className="flat">{man(totalBase)}</strong></div>
          <div><span>차이</span><strong className={total >= totalBase ? "good" : "bad"}>{signed(total - totalBase, man)}</strong></div>
        </div>
        <p className="g-season-line">가장 좋았던 달은 <b>{best.month}월차</b> ({index.shocks[best.shock].label}, {man(best.op)}), 가장 힘들었던 달은 <b>{worst.month}월차</b> ({index.shocks[worst.shock].label}, {man(worst.op)})입니다.</p>
        {lasting.length > 0 && <p className="g-season-line">시즌이 끝날 때 유지 중인 선택: {lasting.join(", ")}</p>}
        <table className="g-receipt-table">
          <thead><tr><th scope="col">달</th><th scope="col">사건</th><th scope="col">선택</th><th scope="col">영업이익</th></tr></thead>
          <tbody>
            {history.map((m) => (
              <tr key={m.month} data-month={m.month} data-value={m.op}>
                <th scope="row"><button className="g-link" onClick={() => onOpen(m.month)}>{m.month}월차 다시 보기</button></th>
                <td className="g-left">{index.shocks[m.shock].label}</td>
                <td className="g-left">{index.actions[m.action].label}</td>
                <td className={m.op >= m.baseOp ? "good" : "bad"}>{man(m.op)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="g-receipt-actions">
          <button className="g-btn g-btn-primary" onClick={onRestart}>새 시즌 시작</button>
        </div>
      </div>
    </section>
  );
}
