// Step 2. The flat map stays on the left; the right column shows one finding at a time: 동네 → 예산 → 자금.
import { useState } from "react";
import SeoulMap from "./SeoulMap";
import { METRICS, RAMP, guStat, man, openingCost, rankOf, type Gu, type Metric, type Profile, type Store } from "./model";

type Tab = "place" | "budget" | "fund";
const TABS: { key: Tab; label: string }[] = [{ key: "place", label: "동네" }, { key: "budget", label: "드는 돈" }, { key: "fund", label: "모자란 돈" }];
const RUNWAY_MONTHS = 3; // 가정: 자리 잡기 전 석 달 치 적자와 생활비
const MONTHLY_BURN = 550;

// 후보 목록의 틀만 잡아 둔 것. 실제 상품명, 한도, 금리는 사람이 기관 공고를 보고 채운다.
const LOANS = [
  { name: "소상공인 정책자금 (직접대출)", who: "창업 초기 소상공인", age: "" },
  { name: "지역 신용보증재단 보증부 대출", who: "서울 소재 사업장", age: "" },
  { name: "청년 창업 지원 자금", who: "나이 조건 있음", age: "2030" },
];

export default function Analysis({ profile, setProfile, gus, store, onNext }: {
  profile: Profile; setProfile: (p: Profile) => void; gus: Gu[]; store: Store; onNext: () => void;
}) {
  const [tab, setTab] = useState<Tab>("place");
  const [metric, setMetric] = useState<Metric>("demand");
  const names = gus.map((g) => g.name);
  const st = guStat(profile.gu);
  const all = names.map(guStat);
  const span = (k: Metric) => ({ lo: Math.min(...all.map((a) => a[k])), hi: Math.max(...all.map((a) => a[k])) });
  const porkRank = rankOf(profile.gu, "pork", names);
  const cost = openingCost(store, profile.gu);
  const need = cost.total + RUNWAY_MONTHS * MONTHLY_BURN;
  const gap = need - profile.capital;
  const young = profile.age === "20대" || profile.age === "30대";
  const demandRank = rankOf(profile.gu, "demand", names);
  const rentRank = names.filter((n) => guStat(n).rent > st.rent).length + 1;
  const m = span(metric);

  return (
    <main className="m-area">
      <section className="m-mapcol" aria-label="서울 지도">
        <div className="m-seg" role="group" aria-label="지도에 표시할 값">
          {(Object.keys(METRICS) as Metric[]).map((k) => (
            <button type="button" key={k} aria-pressed={metric === k} onClick={() => setMetric(k)}>{METRICS[k].label}</button>
          ))}
        </div>
        {gus.length > 0
          ? <SeoulMap gus={gus} metric={metric} selected={profile.gu} onSelect={(gu) => setProfile({ ...profile, gu })} />
          : <p className="m-loading">지도를 그리는 중이에요</p>}
        <div className="m-legend">
          <span>{METRICS[metric].fmt(m.lo)}</span>
          <span className="m-legend-ramp" aria-hidden="true">{RAMP.map((c) => <i key={c} style={{ background: c }} />)}</span>
          <span>{METRICS[metric].fmt(m.hi)}</span>
          <span className="m-legend-note">색이 진할수록 {METRICS[metric].label}가 커요. 구를 누르면 그 구로 바뀌어요.</span>
        </div>
      </section>

      <section className="m-panel">
        <div className="m-tabs" role="tablist" aria-label="분석 내용">
          {TABS.map((t) => <button type="button" role="tab" key={t.key} aria-selected={tab === t.key} onClick={() => setTab(t.key)}>{t.label}</button>)}
        </div>

        {tab === "place" && (
          <div className="m-finding" key="place">
            <h1>{profile.gu} 한식음식점은 한 곳당 한 달에 <mark>{man(st.sales)}</mark>을 팔아요. 25개 구 중 {demandRank}번째예요.</h1>
            <dl className="m-rows">
              <div><dt>매출 지수<small>한식음식점 한 곳의 월매출, 서울 평균이 1</small></dt><dd>{st.demand.toFixed(2)}</dd></div>
              <div><dt>고깃집 수<small>돼지고기 구이 가게, 구 전체. 25개 구 중 {porkRank}번째로 많아요</small></dt><dd>{st.pork.toLocaleString("ko-KR")}곳</dd></div>
              <div><dt>한식음식점 수<small>상권 안의 가게</small></dt><dd>{st.stores.toLocaleString("ko-KR")}곳</dd></div>
              <div><dt>하루 결제 건수<small>한식음식점 한 곳당, 결제 1건은 보통 한 팀</small></dt><dd>{st.tx}건</dd></div>
              <div><dt>1년 폐업률<small>2025년에 문 닫은 한식음식점 비율</small></dt><dd>{st.closure}%</dd></div>
              <div><dt>평당 월세<small>예시값이에요. 아직 실제 자료가 없어요.</small></dt><dd className="is-fake">{st.rent}만원</dd></div>
            </dl>
            {profile.reasons.includes("월세가 쌀 것 같아서") && (
              <p className="m-aside">월세가 쌀 것 같다고 하셨는데, 월세는 아직 실제 자료가 없어 확인해 드릴 수 없어요. 지금 값은 예시값이에요 ({rentRank}번째).</p>
            )}
            {profile.reasons.includes("유동 인구가 많아서") && (
              <p className="m-aside">유동 인구가 많다고 하셨죠. 가게 한 곳의 매출로는 {demandRank}번째예요. 지나가는 사람이 많아도 가게마다 손님이 많다는 뜻은 아니에요.</p>
            )}
            <p className="m-src">매출과 폐업률은 서울시 상권분석서비스 2025년의 한식음식점 값이에요. 고깃집만의 매출 통계는 없어요. 고깃집 수는 소상공인 상가정보 2026년 6월 기준이에요. <a href="#/sources">출처 보기</a></p>
            <button type="button" className="m-btn" onClick={() => setTab("budget")}>여는 데 드는 돈 보기</button>
          </div>
        )}

        {tab === "budget" && (
          <div className="m-finding" key="budget">
            <h1>{profile.gu}에 {store.pyeong}평 고깃집을 열려면 <mark>{man(need)}</mark>쯤 필요해요.</h1>
            <table className="m-quote">
              <caption>기본 구성으로 낸 견적. 다음 단계에서 직접 바꿀 수 있어요.</caption>
              <tbody>
                {cost.lines.filter((l) => l.amount > 0).map((l) => (
                  <tr key={l.key}><th scope="row">{l.label}<small>{l.basis}</small></th><td>{man(l.amount)}</td></tr>
                ))}
                <tr><th scope="row">석 달 치 버틸 돈<small>자리 잡기 전 적자와 생활비, 가정</small></th><td>{man(RUNWAY_MONTHS * MONTHLY_BURN)}</td></tr>
              </tbody>
              <tfoot>
                <tr><th scope="row">합계</th><td>{man(need)}</td></tr>
                <tr><th scope="row">내가 가진 돈</th><td>{man(profile.capital)}</td></tr>
              </tfoot>
            </table>
            <button type="button" className="m-btn" onClick={() => setTab("fund")}>{gap > 0 ? "모자란 돈 구할 방법 보기" : "남는 돈 확인하기"}</button>
          </div>
        )}

        {tab === "fund" && (
          <div className="m-finding" key="fund">
            {gap > 0 ? (
              <>
                <h1>가진 돈으로는 <mark>{man(gap)}</mark>이 모자라요.</h1>
                <p>모자란 돈을 구하는 길은 셋이에요. 평수나 마감을 낮추거나, 월세가 싼 구로 옮기거나, 정책자금을 알아보는 거예요.</p>
                <table className="m-quote">
                  <caption>알아볼 만한 정책자금 종류. 한도와 금리는 기관 공고에서 확인하세요.</caption>
                  <tbody>
                    {LOANS.filter((l) => !l.age || young).map((l) => (
                      <tr key={l.name}><th scope="row">{l.name}<small>{l.who}</small></th><td>기관 확인 필요</td></tr>
                    ))}
                  </tbody>
                </table>
                {!young && <p className="m-aside">나이 조건이 있는 청년 자금은 목록에서 뺐어요.</p>}
              </>
            ) : (
              <>
                <h1>가진 돈으로 열 수 있고 <mark>{man(-gap)}</mark>이 남아요.</h1>
                <p>남는 돈은 장사가 자리 잡기 전까지 버티는 데 쓰여요. 한 달에 {man(MONTHLY_BURN)}쯤 줄어든다고 보면 {Math.floor(-gap / MONTHLY_BURN) + RUNWAY_MONTHS}개월을 버틸 수 있어요.</p>
              </>
            )}
            <button type="button" className="m-btn" onClick={onNext}>가게 꾸미러 가기</button>
          </div>
        )}
      </section>
    </main>
  );
}
