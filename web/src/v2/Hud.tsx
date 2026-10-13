// Top bar: month, 현금 with its runway line, 평점 with its sparkline, 단골, 인지도, 직원 피로, 검토 N/82, tools.
import { man, num, pct, runwayMonths } from "./format";
import { leaf, type SeasonMeta } from "./meta";
import { Dots, Meter, Prelim, Spark, Tag, type Dot } from "./parts";

export type HudState = { cash: number; rating: number; rating_recent?: number; rating_all?: number; review_count: number; awareness: number; regular_share: number; fatigue: number; negative_months: number };

export type HudDots = { cash: Dot; rating: Dot; fatigue: Dot; covers: Dot; step: string };

export function Hud({ meta, monthLabel, monthNo, months, st, cashHist, ratingHist, lastOp, review, modeLabel, tools, dots }: {
  meta: SeasonMeta | null; monthLabel: string; monthNo: number; months: number; st: HudState; cashHist: number[]; ratingHist: number[];
  lastOp: number | null; review?: { reviewed: number; total: number }; modeLabel: string; tools: React.ReactNode; dots?: HudDots | null;
}) {
  const runway = runwayMonths(st.cash, lastOp);
  const closeRule = leaf(meta, "closure.negative_months_to_close");
  const warn = st.cash < 0 || st.negative_months > 0;
  return (
    <header className="v2-hud" aria-label="가게 상태">
      <div className="v2-hud-main">
        <div className="v2-hud-cell v2-hud-month">
          <span className="k">{modeLabel}</span>
          <span className="v" data-testid="hud-month">{monthLabel}</span>
          <span className="s">{monthNo} / {months}개월</span>
        </div>
        <div className={`v2-hud-cell v2-hud-cash ${warn ? "warn" : ""}`}>
          <span className="k">현금 (운영자금)<Tag tag={closeRule?.tag as string} title="폐업 규칙" note={closeRule?.note as string} meta={meta} compact /></span>
          <span className="v" data-testid="hud-cash" data-value={st.cash}>
            <span className={st.cash < 0 ? "down" : ""}>{man(st.cash)}</span><Dots d={dots?.cash} testid="dot-cash" />
            <Spark values={cashHist} zero className={st.cash < 0 ? "down" : ""} />
          </span>
          <span className="s">
            {st.negative_months > 0 ? `0 아래 ${st.negative_months}개월째, 한 달 더면 폐업` : runway != null ? `이 적자면 ${runway}개월 버팀` : "두 달 연속 0 아래면 폐업"}
          </span>
        </div>
        <div className="v2-hud-cell">
          <span className="k" title={st.rating_all != null ? `최근 리뷰 30개의 평균. 손님 수를 움직이는 값입니다. 전체 리뷰 평균은 ${st.rating_all.toFixed(2)}` : undefined}>{st.rating_recent != null ? "최근 평점" : "평점"}<Tag tag="S03" title="평점과 손님 수" note="평점 1점이 독립 식당 매출 5~9%와 연결됩니다 (Luca, HBS). 게임에서는 1점 = 손님 ±7%." meta={meta} compact /></span>
          <span className="v" data-testid="hud-rating" data-value={st.rating_recent ?? st.rating}>{(st.rating_recent ?? st.rating).toFixed(2)}<Dots d={dots?.rating} testid="dot-rating" /> <Spark values={ratingHist} w={56} /></span>
          <span className="s">{st.rating_all != null ? `전체 ${st.rating_all.toFixed(2)}, ` : ""}리뷰 {num(st.review_count)}</span>
        </div>
        <div className="v2-hud-cell">
          <span className="k">단골 <Tag tag="가정" title="단골 비율" note={leaf(meta, "regulars.change_penalty")?.note as string} meta={meta} compact /></span>
          <span className="v">{pct(st.regular_share)}</span>
          <span className="s">손님 중 다시 온 비율</span>
        </div>
        <div className="v2-hud-cell">
          <span className="k">인지도 <Tag tag="가정" title="인지도" note={leaf(meta, "awareness.decay")?.note as string} meta={meta} compact /></span>
          <span className="v">{st.awareness.toFixed(2)}</span>
          <span className="s">기준 1.00</span>
        </div>
        <div className="v2-hud-cell">
          <span className="k">직원 피로<Tag tag="가정" title="직원 피로" note={leaf(meta, "fatigue.quit_per_parttimer")?.note as string} meta={meta} compact /></span>
          <span className="v" data-testid="hud-fatigue" data-value={st.fatigue}>{Math.round(st.fatigue)} <Meter value={st.fatigue} /><Dots d={dots?.fatigue} testid="dot-fatigue" /></span>
          <span className="s">{st.fatigue >= 70 ? "퇴사 위험이 큽니다" : st.fatigue >= 50 ? "응대가 느려집니다" : "100이 한계"}</span>
        </div>
      </div>
      <div className="v2-hud-tools">
        {review && (
          <span className="v2-hud-review" data-testid="review-status" title={`가게 추정값 ${review.total}개 중 사람이 검토를 마친 수. 검토 전 값도 모두 출처나 가정 표시가 붙어 있습니다`}>
            <Prelim input={{ review }} testid="hud-prelim" />사람 검토 {review.reviewed}/{review.total}
          </span>
        )}
        {tools}
      </div>
    </header>
  );
}
