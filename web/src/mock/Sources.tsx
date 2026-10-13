// #/sources: operator page. Where every number on the mock comes from and how far it can be trusted.
// Keep this file in step with model.ts: a constant added there gets a row here.
import { useEffect, useState } from "react";
import { CATALOG, GRADES, man, type GuData } from "./model";
import "./sources.css";

type Kind = "실측" | "차용" | "가정" | "예시값";
const KIND_NOTE: Record<Kind, string> = {
  실측: "공공데이터를 내려받아 계산한 값. 출처와 계산 스크립트가 있음",
  차용: "기존 대학로 가상 매장(sdic-persona-team1)의 값. 팀이 출처를 달아 만든 추정치이며 원 레포가 '검토 전 예시'라고 밝힘",
  가정: "근거 자료 없이 정한 값. 바꿔도 되는 설정값",
  예시값: "화면을 채우려고 임의로 만든 값. 사실과 무관",
};

type Row = { item: string; value: string; kind: Kind; source: string; note?: string };

const DATASETS = [
  { name: "서울시 상권분석서비스 (추정매출-상권)", id: "OA-15572", url: "https://data.seoul.go.kr/dataList/OA-15572/S/1/datasetView.do", how: "연도별 파일 내려받기 (인증키 불필요)", status: "연결됨", use: "구별 한식음식점 매출, 결제 건수, 결제 1건 금액, 저녁·주말 비중" },
  { name: "서울시 상권분석서비스 (점포-상권)", id: "OA-15577", url: "https://data.seoul.go.kr/dataList/OA-15577/S/1/datasetView.do", how: "연도별 파일 내려받기 (인증키 불필요)", status: "연결됨", use: "구별 한식음식점 수, 개업·폐업 수" },
  { name: "서울시 상권분석서비스 (영역-상권)", id: "OA-15560", url: "https://data.seoul.go.kr/dataList/OA-15560/F/1/datasetView.do", how: "shapefile 내려받기 (인증키 불필요)", status: "연결됨", use: "상권 1,650곳이 어느 구에 속하는지" },
  { name: "서울 행정구역 경계 (통계청 2013, southkorea/seoul-maps)", id: "GitHub", url: "https://github.com/southkorea/seoul-maps", how: "GitHub 원본 파일", status: "연결됨", use: "지도의 25개 구 모양. 2013년 경계라 최신과 다를 수 있음" },
  { name: "한국천문연구원 특일 정보", id: "data.go.kr 15012690", url: "https://www.data.go.kr/data/15012690/openapi.do", how: "API (공공데이터포털 키)", status: "연결됨", use: "2026~2027년 공휴일 46일. pipelines/fetch_weather.py가 받아 web/public/mock/holidays.json에 저장" },
  { name: "기상청 지상(ASOS) 일자료", id: "data.go.kr 15059093", url: "https://www.data.go.kr/data/15059093/openapi.do", how: "API (공공데이터포털 키)", status: "연결됨", use: "서울(108) 2016~2025년 일자료를 달별 비율로 집계해 web/public/mock/weather_seoul.json에 저장. 일자료 원본은 저장하지 않음" },
  { name: "소상공인시장진흥공단 상가(상권)정보", id: "data.go.kr 15083033", url: "https://www.data.go.kr/data/15083033/fileData.do", how: "파일 내려받기 (인증키 불필요)", status: "연결됨", use: "서울 구별 돼지고기 구이(I20107) 점포 수를 gu_stats.json의 pork 블록에 집계. 원자료 zip(약 350MB)은 저장소에 없음" },
  { name: "서울시 일반음식점 인허가", id: "OA-16094", url: "https://data.seoul.go.kr/dataList/OA-16094/S/1/datasetView.do", how: "API (서울 열린데이터 키)", status: "미연결", use: "개업일, 폐업일로 생존 기간 계산. 원 레포는 종로구만 처리" },
  { name: "상가 임대료 (평당 월세)", id: "없음", url: "", how: "출처 미정", status: "자료 없음", use: "지금 화면의 평당 월세는 예시값. 한국부동산원 상업용부동산 임대동향 등을 확인해야 함" },
  { name: "일별 유동 자료 (생활인구, 지하철 승하차)", id: "미확인", url: "", how: "출처 미확인", status: "미연결", use: "날씨, 공휴일 효과 추정용. 제공 형태를 아직 확인하지 않음" },
];

function rows(d: GuData | null): { title: string; rows: Row[] }[] {
  const seoul = d?.bbq.seoul;
  const src = d ? `서울시 상권분석서비스 ${d._meta.year}년 (${d._meta.quarters[0]}~${d._meta.quarters.at(-1)}), ${d._meta.method}` : "gu_stats.json";
  return [
    {
      title: "동네 분석",
      rows: [
        { item: "한식음식점 한 곳의 월매출", value: seoul ? `서울 평균 ${man(seoul.sales_per_store_month)}` : "", kind: "실측", source: src, note: "카드사 추정 매출을 점포 수로 나눈 평균. 잘 되는 가게가 평균을 끌어올림. 고깃집만의 값이 아님" },
        { item: "매출 지수", value: "구 평균 ÷ 서울 평균", kind: "실측", source: src },
        { item: "한식음식점 수", value: seoul ? `서울 ${seoul.stores.toLocaleString("ko-KR")}곳` : "", kind: "실측", source: src, note: "상권 영역 안의 점포만. 구 전체 점포 수가 아님" },
        { item: "하루 결제 건수", value: seoul ? `서울 평균 ${seoul.tx_per_store_day}건` : "", kind: "실측", source: src, note: "결제 1건은 손님 1명이 아니라 보통 한 팀" },
        { item: "1년 폐업률", value: seoul ? `서울 ${(seoul.closure_rate * 100).toFixed(1)}%` : "", kind: "실측", source: src, note: "2025년 폐업 점포 수 ÷ 평균 점포 수" },
        { item: "고깃집 수", value: d?.pork ? `서울 ${Object.values(d.pork.gu).reduce((n, v) => n + v.pork, 0).toLocaleString("ko-KR")}곳` : "", kind: "실측", source: d?.pork ? `${d.pork.source}, ${d.pork.snapshot} 기준, 소분류 I20107 돼지고기 구이/찜` : "", note: "구 전체의 점포 수. 매출 정보는 없음. 업종 분류는 등록 기준이라 실제 메뉴와 다를 수 있음" },
        { item: "평당 월세", value: "구마다 9~29만원", kind: "예시값", source: "model.ts guStat (구 이름으로 만든 임의 값)", note: "실제 자료 없음. 이 값이 보증금, 월 고정비, 현금 그래프에 들어감" },
        { item: "정책자금 목록", value: "3종", kind: "예시값", source: "Analysis.tsx LOANS", note: "종류 이름만 적은 틀. 상품명, 한도, 금리, 자격은 확인한 적 없음" },
      ],
    },
    {
      title: "여는 데 드는 돈",
      rows: [
        { item: "보증금", value: "월세 10개월분", kind: "가정", source: "model.ts DEPOSIT_MONTHS", note: "월세가 예시값이라 이 금액도 예시값" },
        { item: "인테리어 공사", value: Object.values(GRADES).map((g) => `${g.label} 평당 ${g.perPyeong}만원`).join(", "), kind: "가정", source: "model.ts GRADES" },
        { item: "물건 가격", value: CATALOG.map((c) => `${c.name} ${c.price}`).join(", ") + " (만원)", kind: "가정", source: "model.ts CATALOG" },
        { item: "간판, 첫 재료", value: "250만원, 300만원", kind: "가정", source: "model.ts SIGN, FIRST_STOCK" },
        { item: "석 달 치 버틸 돈", value: "월 550만원 × 3", kind: "가정", source: "Analysis.tsx MONTHLY_BURN" },
      ],
    },
    {
      title: "6개월 현금 계산",
      rows: [
        { item: "자리 잡은 뒤 하루 손님 수", value: "구의 점포당 월매출 ÷ (1인 27,000원 × 26일)", kind: "실측", source: `${src} + 차용값 2개`, note: "새 가게가 그 구 한식음식점 평균만큼 손님을 받는다는 가정이 들어감. 실측 매출을 손님 수로 바꾸는 1인 금액과 영업일은 차용값" },
        { item: "손님 1인 금액", value: "고기 가격 + 8,000원 (기본 27,000원)", kind: "차용", source: "hero.json pnl ticket, t_alc + t_side" },
        { item: "재료비 비율", value: "매출의 31%", kind: "차용", source: "hero.json pnl food ÷ rev" },
        { item: "직원 1명 인건비", value: "월 199만원", kind: "차용", source: "hero.json pnl (l_pt + l_emp) ÷ servers" },
        { item: "관리비 등", value: "평당 월 12.8만원", kind: "차용", source: "hero.json pnl mgmt ÷ area_pyeong" },
        { item: "카드 수수료", value: "매출의 0.84%", kind: "차용", source: "hero.json pnl fees ÷ rev" },
        { item: "사장 생활비", value: "월 300만원", kind: "차용", source: "hero.json owner_wage" },
        { item: "오픈 곡선", value: "1~6개월째 55, 70, 82, 90, 96, 100%", kind: "가정", source: "model.ts OPEN_CURVE", note: "인터뷰 문서의 '오픈 효과' 요인을 숫자로 옮긴 임의 곡선" },
        { item: "좌석 회전", value: "좌석 1개당 하루 1.5명", kind: "가정", source: "model.ts SEAT_TURN" },
        { item: "직원 1명이 받는 손님", value: "하루 15명", kind: "가정", source: "model.ts COVERS_PER_STAFF" },
        { item: "가격 반응", value: "탄력성 −0.8", kind: "가정", source: "model.ts simulate priceFx" },
        { item: "범위", value: "손님 20% 적음, 15% 많음", kind: "가정", source: "model.ts LOW, HIGH" },
      ],
    },
    {
      title: "시뮬레이션 (하루 단위)",
      rows: [
        { item: "요일별 손님 차이", value: seoul ? `서울 평균 월~일 ${seoul.dow_share.map((v) => (v * 100).toFixed(1)).join(", ")}%` : "", kind: "실측", source: src, note: "구마다 그 구의 요일별 매출 비중을 씀" },
        { item: "분기별 손님 차이", value: seoul ? `서울 평균 1~4분기 ${seoul.quarter_index.join(", ")}` : "", kind: "실측", source: src, note: "분기 안의 달은 같은 값. 월별 차이는 자료가 없음" },
        { item: "공휴일 날짜", value: "2026년 22일, 2027년 24일", kind: "실측", source: "한국천문연구원 특일 정보 (data.go.kr 15012690), pipelines/fetch_weather.py가 받은 holidays.json" },
        { item: "공휴일의 손님 수", value: "일요일과 같다고 봄", kind: "가정", source: "sim.ts step" },
        { item: "월별 비 오는 날 비율", value: "1~12월 10, 13, 15, 20, 25, 27, 38, 38, 24, 17, 17, 14%", kind: "실측", source: "기상청 ASOS 일자료 (data.go.kr 15059093), 서울 지점 108, 2016~2025년, weather_seoul.json", note: "일강수량 1mm 이상인 날의 비율. 저녁 장사 시간에 비가 왔는지는 알 수 없음. 어느 날 비가 오는지는 이 비율로 뽑은 난수" },
        { item: "쉬는 날을 없앨 때 급여", value: "30/26배", kind: "가정", source: "model.ts staffPay" },
        { item: "하루 손익", value: "매출 − 재료비·수수료 − 한 달 고정비 ÷ 30.4", kind: "가정", source: "sim.ts step profit", note: "흑자 전환과 들인 돈 회수 시점 계산에 씀" },
        { item: "추천 배치", value: "12~30평, 테이블 수, 직원 0~6명을 모두 계산", kind: "가정", source: "model.ts recommend", note: "손님이 20% 적어도 6개월을 버티는 구성 가운데 자리 잡힌 뒤 한 달에 가장 많이 남는 것. 월세가 예시값이라 결과도 예시" },
        { item: "비 오는 날 손님", value: "−10%", kind: "차용", source: "research/shocks.yaml SH10", note: "원 레포도 가정으로 표시한 값" },
        { item: "하루 손님의 흔들림", value: "±12%", kind: "가정", source: "sim.ts step" },
        { item: "돈이 나가는 날", value: "월세 1일, 급여 10일(둘째 달부터), 생활비와 이자 25일", kind: "가정", source: "sim.ts step" },
        { item: "대출 이자", value: "연 6%, 이자만 냄", kind: "가정", source: "model.ts LOAN_RATE" },
        { item: "만족도", value: "80%에서 시작, 손님을 20% 넘게 돌려보낸 날 −0.3, 직원이 받을 수 있는 한도까지 찬 날 −0.2, 평소 +0.15", kind: "가정", source: "sim.ts step", note: "만족도가 손님 수에 주는 영향(10%p당 5%)도 가정" },
        { item: "리뷰 문구", value: "상황별 문장 12개", kind: "예시값", source: "sim.ts REVIEW_TEXT", note: "실제 리뷰가 아님" },
        { item: "폐업 규칙", value: "현금이 60일 내리 0 아래", kind: "차용", source: "기존 게임의 규칙 (README: 현금이 두 달 연속 0 아래면 폐업)" },
      ],
    },
    {
      title: "시뮬레이션의 사건",
      rows: [
        { item: "돼지고기 도매가 상승", value: "원가 +8%", kind: "차용", source: "research/events.yaml pork_up (S68, S48)" },
        { item: "근처 고깃집 개점", value: "손님 −9%", kind: "차용", source: "research/events.yaml competitor_open (S13, S20)" },
        { item: "비 오는 주간, 한파, 블로거 방문, 악성 리뷰, 알바 퇴사, 위생점검", value: "events.yaml의 크기", kind: "차용", source: "research/events.yaml", note: "원 레포가 대부분 가정으로 표시한 값" },
        { item: "선택지와 그 효과", value: "사건마다 2~3개", kind: "가정", source: "sim.ts EVENTS", note: "새로 지은 것. 근거 없음" },
        { item: "사건이 생기는 때", value: "한 달에 1개, 6~23일 사이", kind: "가정", source: "sim.ts newSim", note: "원 레포의 월별 확률은 아직 쓰지 않음" },
      ],
    },
    {
      title: "점검 기준",
      rows: [
        { item: "여유, 주의, 취약을 나누는 선", value: "항목마다 화면의 '이렇게 판단했어요'에 표시", kind: "가정", source: "model.ts checks", note: "검증한 적 없는 기준선" },
        { item: "좌석 14석당 직원 1명", value: "", kind: "가정", source: "model.ts checks" },
      ],
    },
  ];
}

export default function Sources() {
  const [d, setD] = useState<GuData | null>(null);
  useEffect(() => { fetch(`${import.meta.env.BASE_URL}mock/gu_stats.json`).then((r) => r.json()).then(setD).catch(() => setD(null)); }, []);
  const groups = rows(d);
  const all = groups.flatMap((g) => g.rows);
  const count = (k: Kind) => all.filter((r) => r.kind === k).length;
  const gus = d ? Object.entries(d.bbq.gu).sort((a, b) => b[1].sales_per_store_month - a[1].sales_per_store_month) : [];

  return (
    <main className="src">
      <p><a href="#/">ChangeUp 목업으로 돌아가기</a></p>
      <h1>출처와 근거 (운영자용)</h1>
      <p>화면에 나오는 숫자가 어디서 왔는지 적은 장부입니다. 계산식은 <code>web/src/mock/model.ts</code>에 있고, 기존 시뮬 엔진은 아직 연결하지 않았습니다.</p>

      <h2>구분</h2>
      <table>
        <thead><tr><th>구분</th><th>뜻</th><th>항목 수</th></tr></thead>
        <tbody>
          {(Object.keys(KIND_NOTE) as Kind[]).map((k) => <tr key={k}><td><b className={`k k-${k}`}>{k}</b></td><td>{KIND_NOTE[k]}</td><td className="n">{count(k)}</td></tr>)}
        </tbody>
      </table>

      <h2>화면의 숫자</h2>
      {groups.map((g) => (
        <section key={g.title}>
          <h3>{g.title}</h3>
          <table>
            <thead><tr><th>항목</th><th>값</th><th>구분</th><th>출처</th><th>주의</th></tr></thead>
            <tbody>
              {g.rows.map((r) => <tr key={r.item}><td>{r.item}</td><td>{r.value}</td><td><b className={`k k-${r.kind}`}>{r.kind}</b></td><td>{r.source}</td><td>{r.note}</td></tr>)}
            </tbody>
          </table>
        </section>
      ))}

      <h2>데이터 출처</h2>
      <table>
        <thead><tr><th>자료</th><th>번호</th><th>받는 방법</th><th>상태</th><th>쓰는 곳</th></tr></thead>
        <tbody>
          {DATASETS.map((s) => (
            <tr key={s.name}><td>{s.url ? <a href={s.url} target="_blank" rel="noopener">{s.name}</a> : s.name}</td><td>{s.id}</td><td>{s.how}</td><td><b className={`k k-${s.status === "연결됨" ? "실측" : s.status === "자료 없음" ? "예시값" : "가정"}`}>{s.status}</b></td><td>{s.use}</td></tr>
          ))}
        </tbody>
      </table>
      {d && (
        <p>연결된 서울시 자료: {d._meta.year}년 {d._meta.quarters.length}개 분기, {d._meta.generated} 생성, {d._meta.license}. 다시 만들기: <code>python -m pipelines.build_gu_stats --refresh</code>. 주의: {d._meta.caveats.join(" / ")}.</p>
      )}

      <h2>기존 레포에서 가져오지 않은 것</h2>
      <ul>
        <li>시뮬 엔진 (<code>sim/</code>): 손님 도착, 대기, 좌석 배정을 계산하는 엔진과 6개월 시즌 엔진. 목업은 단순 월별 식을 씀.</li>
        <li>대학로 4개 상권 자료 (<code>data/processed/</code>): 매출, 점포, 유동인구, 직장인구, 거주인구, 집객시설, 인허가 매칭, 생존 분석.</li>
        <li>근거 목록 (<code>ontology/sources.csv</code> 76건)과 가상 매장 입력값 (<code>research/hero_base.yaml</code>): 차용값의 원 출처는 이 두 파일에서 추적.</li>
        <li>사건 목록 (<code>research/shocks.yaml</code>, <code>events.yaml</code>, <code>calendar.yaml</code>): 월별 수요 지수와 사건 크기.</li>
      </ul>

      <h2>구별 값 (한식음식점, 상권 안)</h2>
      {gus.length === 0 ? <p>gu_stats.json을 읽지 못했습니다.</p> : (
        <table className="num">
          <thead><tr><th>구</th><th>상권 수</th><th>점포 수</th><th>점포당 월매출</th><th>하루 결제</th><th>결제 1건</th><th>저녁 비중</th><th>주말 비중</th><th>1년 폐업률</th><th>1년 개업률</th><th>매출 지수</th></tr></thead>
          <tbody>
            {gus.map(([n, v]) => (
              <tr key={n}><td>{n}</td><td>{v.trdar}</td><td>{v.stores.toLocaleString("ko-KR")}</td><td>{man(v.sales_per_store_month)}</td><td>{v.tx_per_store_day}건</td><td>{v.ticket.toLocaleString("ko-KR")}원</td>
                <td>{(v.evening_share * 100).toFixed(1)}%</td><td>{(v.weekend_share * 100).toFixed(1)}%</td><td>{(v.closure_rate * 100).toFixed(1)}%</td><td>{(v.opening_rate * 100).toFixed(1)}%</td><td>{v.demand_index.toFixed(2)}</td></tr>
            ))}
          </tbody>
        </table>
      )}
    </main>
  );
}
