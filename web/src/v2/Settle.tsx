// 월말 정산 as a printed slip: owner's line, profit waterfall, where the draw landed in p10-p90, cash runway,
// reputation, the review feed (click a review to question that customer), and the month's mechanisms with tags.
import { man, manSigned, noArrow, num, pct, runwayMonths } from "./format";
import { type SeasonMeta } from "./meta";
import { Band, ReviewCard, Spark, Tag, Waterfall } from "./parts";
import { GuessResult } from "./Predict";
import { CountUp, MoodStamp, RatingStar } from "./juice";
import type { MonthResult, Plan, Review, WaterfallStep } from "./types";

export function CashChart({ labels, values, w = 260, h = 96 }: { labels: string[]; values: number[]; w?: number; h?: number }) {
  if (values.length < 2) return null;
  const lo = Math.min(0, ...values), hi = Math.max(...values, 1);
  const padL = 4, padR = 4, padT = 8, padB = 18;
  const x = (i: number) => padL + (i / (values.length - 1)) * (w - padL - padR);
  const y = (v: number) => padT + (1 - (v - lo) / (hi - lo)) * (h - padT - padB);
  const d = values.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join("");
  return (
    <svg width="100%" viewBox={`0 0 ${w} ${h}`} role="img" aria-label={`현금 추이 ${values.map(man).join(", ")}`} className="v2-cash-chart">
      <line x1={0} x2={w} y1={y(0)} y2={y(0)} stroke="oklch(0.57 0.17 33)" strokeDasharray="3 3" />
      <text x={w - 2} y={y(0) - 3} textAnchor="end" fontSize="9" fill="oklch(0.57 0.17 33)">0원, 두 달 연속이면 폐업</text>
      <path d={d} fill="none" stroke="oklch(0.24 0.016 255)" strokeWidth="2" />
      {values.map((v, i) => <circle key={i} cx={x(i)} cy={y(v)} r={3} fill={v < 0 ? "oklch(0.57 0.17 33)" : "oklch(0.24 0.016 255)"} />)}
      {labels.map((l, i) => <text key={i} x={x(i)} y={h - 4} textAnchor={i === 0 ? "start" : i === labels.length - 1 ? "end" : "middle"} fontSize="9.5" fill="oklch(0.54 0.012 255)">{l}</text>)}
    </svg>
  );
}

export function Settle({ r, guess, meta, monthNo, months, cashLabels, cashHist, ratingHist, shadowOp, shadowLabel, seasonShadow, onNext, nextLabel, onHandover, onAsk, onAskOwner, onTree, fixtureNote, branches, onCause }: {
  r: MonthResult; guess?: string; meta: SeasonMeta | null; monthNo: number; months: number; cashLabels: string[]; cashHist: number[]; ratingHist: number[];
  shadowOp?: number | null; shadowLabel?: string; seasonShadow?: { cash: number; label: string } | null; onNext: () => void; nextLabel: string; onHandover?: () => void; onAsk: (rv: Review) => void; onAskOwner: () => void; onTree: () => void; fixtureNote?: string; branches?: { label: string; line: string }[]; onCause?: (k: keyof Plan) => void;
}) {
  const k = r.draw.kpis;
  // plan == 평소: every step is zero, so show the month's P&L instead (매출 down to 영업이익)
  const flatWf = r.waterfall.filter((w) => w.kind === "step").every((w) => Math.abs(w.delta) < 10000);
  const costs: [string, string, number][] = [["cogs", "식재료비", k.cogs], ["labor", "인건비", k.labor], ["rent", "임차료", k.rent], ["mgmt", "관리비·마케팅", k.mgmt], ["fees", "카드 수수료", k.fees]];
  const residual = k.op - (k.revenue - costs.reduce((a, c) => a + (c[2] ?? 0), 0));
  const composition: WaterfallStep[] = [
    { driver: "매출", key: "revenue", delta: k.revenue, kind: "start" },
    ...costs.map(([key, driver, v]) => ({ driver, key, delta: -(v ?? 0), kind: "step" as const })),
    ...(Math.abs(residual) >= 10000 ? [{ driver: "기타", key: "other", delta: residual, kind: "step" as const }] : []),
    { driver: "이번 달 영업이익", key: "end", delta: k.op, kind: "end" },
  ];
  const before = r.state_before ?? {};
  const after = r.state_after;
  const reviews = r.reviews; // the engine's order (as written during the month), not sorted by stars
  const starCount = [5, 4, 3, 2, 1].map((n) => [n, r.reviews.filter((x) => Math.round(x.stars) === n).length]).filter(([, c]) => c > 0);
  const cashDelta = after.cash - (before.cash ?? after.cash - k.op);
  const ratingDelta = after.rating - (before.rating ?? after.rating);
  const runway = runwayMonths(after.cash, k.op);
  return (
    <section className="v2-settle" aria-label="월말 정산" data-testid="settlement">
      <div className="v2-receipt">
        <header>
          <span className="store">대학로 삼겹살</span>
          <h2>{r.calendar.label} 정산</h2>
          <span className={`op ${k.op < 0 ? "down" : ""}`} data-testid="settle-op" data-value={k.op}>{k.op < 0 ? "적자 " : ""}<CountUp value={Math.abs(k.op)} format={man} /></span>
          <span className="sub">이번 달 결과: 영업이익 (사장님 인건비 차감 후), 매출 {man(k.revenue)}, 손님 {num(k.covers)}명, 객단가 {num(k.ticket)}원</span>
          {r.shadow && (
            <span className="sub" data-testid="shadow" data-value={r.shadow.kpis.op} title={r.shadow.basis}>평소대로였다면 (이번 달) {man(r.shadow.kpis.op)}, 차이 <b className={k.op - r.shadow.kpis.op >= 0 ? "up" : "down"}>{manSigned(k.op - r.shadow.kpis.op)}</b></span>
          )}
          {shadowOp != null && (
            <span className="sub" data-testid="branch-op">{shadowLabel} {man(shadowOp)}, 차이 <b className={k.op - shadowOp >= 0 ? "up" : "down"}>{manSigned(k.op - shadowOp)}</b></span>
          )}
          {seasonShadow && (
            <span className="sub" data-testid="season-shadow">{seasonShadow.label}: 월말 현금 {man(seasonShadow.cash)}, 내 가게 {manSigned(after.cash - seasonShadow.cash)}</span>
          )}
          <GuessResult guess={guess} op={k.op} />
          <span className="sub">{monthNo} / {months}개월째</span>
        </header>
        <section>
          <div className="v2-owner-wrap"><MoodStamp mood={r.owner_line.mood} /><p className="v2-owner-line" data-testid="owner-line">{r.owner_line.text}</p></div>
          {r.owner_line.event_lines && Object.values(r.owner_line.event_lines).length > 0 && (
            <p className="v2-note" style={{ textAlign: "center", marginBlockStart: 6 }}>{Object.values(r.owner_line.event_lines).join(" ")}</p>
          )}
        </section>
        <section>
          <h3>{flatWf ? "이번 달 돈의 흐름" : "영업이익은 어디서 왔나"} <small>{flatWf ? "평소 계획과 같은 계획이라 차이 대신 매출에서 영업이익까지를 보여 줍니다" : r.waterfall[0]?.driver.startsWith("평소대로였다면") ? "같은 달, 같은 사건과 손님에 평소 계획을 썼을 때와 비교" : "평소 = 외부 사건이 없는 평소 달 (10월, 기본 계획, 시작 상태의 평균 예상)"}</small></h3>
          <Waterfall steps={flatWf ? composition : r.waterfall} onCause={onCause} />
        </section>
        <section>
          <h3>운의 범위 <small>한 번 뽑은 이번 달 결과</small></h3>
          <Band draw={r.draw} />
        </section>
        <section className="v2-two">
          <div>
            <h3>현금 <small>{manSigned(cashDelta)}</small></h3>
            <CashChart labels={cashLabels} values={cashHist} />
            <p className="v2-note">{after.negative_months > 0 ? `현금이 0 아래로 ${after.negative_months}개월째입니다. 다음 달도 0 아래면 폐업합니다.`
              : runway != null ? `이번 달 같은 적자가 이어지면 ${runway}개월 뒤 현금이 바닥납니다.` : `남은 운영자금 ${man(after.cash)}.`}</p>
          </div>
          <div>
            <h3><span style={{ display: "inline-flex", gap: 6, alignItems: "center" }}><RatingStar delta={ratingDelta} />평판</span> <small>{ratingDelta >= 0 ? "+" : ""}{ratingDelta.toFixed(2)}점</small></h3>
            <dl className="v2-kv">
              <dt>평점</dt><dd>{after.rating.toFixed(2)} <Spark values={ratingHist} w={50} h={16} /></dd>
              <dt>리뷰 수</dt><dd>{num(after.review_count)}개 (+{num(after.review_count - (before.review_count ?? after.review_count))})</dd>
              <dt>단골 비율</dt><dd>{pct(after.regular_share)}</dd>
              <dt>인지도</dt><dd>{after.awareness.toFixed(2)}</dd>
              <dt>직원 피로</dt><dd className={after.fatigue >= 70 ? "down" : ""}>{Math.round(after.fatigue)}</dd>
              <dt>돌아간 팀</dt><dd>{num(k.walkaways)}팀</dd>
            </dl>
          </div>
        </section>
        <section>
          <h3>손님 리뷰 <small>이번 달 {r.reviews_total ?? r.reviews.length}개 중 {reviews.length}개 ({starCount.map(([n, c]) => `별${n} ${c}`).join(", ")}), 누르면 그 손님에게 묻기</small></h3>
          <div className="v2-reviews" data-testid="reviews">
            {reviews.map((rv) => <ReviewCard key={rv.id} r={rv} plan={r.plan} onAsk={onAsk} onCause={onCause} />)}
          </div>
        </section>
        {branches && branches.length > 0 && (
          <section data-testid="branches">
            <h3>고르지 않은 선택은 다음 달에 어땠을까 <small>괄호 안은 이야기의 선택</small></h3>
            {branches.map((b) => <p key={b.label} style={{ fontSize: 13, marginBlockEnd: 6 }}><b>{b.label}</b>: {b.line}</p>)}
          </section>
        )}
        <section>
          <h3>이번 달에 쓰인 가정과 근거</h3>
          <div style={{ display: "grid", gap: 6 }}>
            {r.labels.map((l) => (
              <div key={l.mechanism} style={{ display: "flex", justifyContent: "space-between", gap: 8, fontSize: 13 }}>
                <span>{noArrow(l.label)}</span>
                <Tag tag={l.tag} title={noArrow(l.label)} note={l.detail ?? null} downside={l.downside ?? null} meta={meta} />
              </div>
            ))}
          </div>
          {fixtureNote && <p className="v2-note" style={{ marginBlockStart: 8 }}>{fixtureNote}</p>}
        </section>
      </div>
      <div className="v2-settle-foot">
        <button className="v2-btn" onClick={onAskOwner} data-testid="ask-owner">사장님에게 묻기</button>
        <button className="v2-btn" onClick={onTree}>가게 능력치에서 원인 보기</button>
        <button className={`v2-btn big ${onHandover ? "" : "primary"}`} onClick={onNext} data-testid="next">{nextLabel}</button>
        {/* 시연 모드 from the second month: hand the game to the room for a one-month free season (N2 demo order) */}
        {onHandover && <button className="v2-btn primary big" onClick={onHandover} data-testid="handover">이제 직접 운영해 보기</button>}
      </div>
    </section>
  );
}
