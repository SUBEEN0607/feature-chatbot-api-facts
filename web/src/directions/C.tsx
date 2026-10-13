// Direction C: place first. The 대학로 상권 map is the canvas; the store and its numbers sit beside it.
import { KPI_META, SHOCK_LABELS, isFlat, pct, signed } from "../data";
import { DistrictMap, FloorPlan, OntologyTree, RangeBar, SHOCK_ORDER, useDashboard } from "../shared/components";
import "./c.css";

const C_KPIS = ["revenue", "op", "covers", "walkaways", "ticket", "alcohol_share"];

export default function DirectionC({ shock, setShock }: { shock: string; setShock: (s: string) => void }) {
  const { hero, ontology, kpis, district } = useDashboard(shock);
  const p = district?.profile;
  return (
    <div className="dc">
      <section className="dc-map" aria-label="대학로 상권 지도">
        {district && <DistrictMap district={district} className="dm dc-dm" competitor={shock === "SH11"} />}
        <div className="dc-title">
          <a href="#/lab" className="dc-home">목록</a>
          <h1>대학로에 삼겹살집이 하나 있다면</h1>
          {p && (
            <p className="dc-facts">
              혜화역 상권 한식당 <b>{p.hansik_stores}곳</b> 가운데 돼지고기 구이집 <b>{p.pork_stores}곳</b>.
              한식 매출의 <b>{pct(p.evening_share, 0)}</b>가 저녁 5시 이후에, <b>{pct(p.age20_share, 0)}</b>가 20대에게서 나옵니다.
            </p>
          )}
        </div>
        <nav className="dc-shocks" aria-label="상황 고르기">
          <p>이 동네에 생길 수 있는 일</p>
          <ul>
            {SHOCK_ORDER.map((id) => (
              <li key={id}>
                <button aria-current={id === shock} onClick={() => setShock(id)}>{SHOCK_LABELS[id]}</button>
              </li>
            ))}
          </ul>
        </nav>
        <ul className="dc-legend" aria-label="지도 범례">
          <li><i className="lg-hero" />합성 매장 (위치는 상징)</li>
          <li><i className="lg-pork" />돼지고기 구이집</li>
          <li><i className="lg-other" />소고기·곱창집</li>
          <li><i className="lg-hansik" />그 밖의 한식당</li>
          {shock === "SH11" && <li><i className="lg-rival" />새로 생긴 경쟁 고깃집 (가정)</li>}
        </ul>
        {p && <p className="dc-source">서울시 상권분석서비스 {p.quarter.slice(0, 4)}년 {p.quarter.slice(4)}분기, 소상공인 상가정보</p>}
      </section>

      <section className="dc-store" aria-label="합성 매장">
        <header className="dc-store-head">
          <h2>매장 안</h2>
          <a href={`#/lab/replay?scenario=${shock === "SH09" ? "SH09" : "SH03"}`}>토요일 밤 3D로 보기</a>
        </header>
        {hero && <FloorPlan hero={hero} className="fp dc-fp" />}

        <h2 className="dc-sub">{SHOCK_LABELS[shock]}, 한 달 뒤</h2>
        <table className="dc-kpis">
          <thead><tr><th scope="col">지표</th><th scope="col">평소</th><th scope="col">충격 후</th><th scope="col"><span className="sr">범위</span></th></tr></thead>
          <tbody>
            {kpis && C_KPIS.map((key) => {
              const m = KPI_META.find((x) => x.key === key)!;
              const b = kpis.base[key], s = kpis.shocked[key];
              const d = s.p50 - b.p50;
              const good = m.better === "up" ? d > 0 : d < 0;
              return (
                <tr key={key}>
                  <th scope="row">{m.label}</th>
                  <td>{m.fmt(b.p50)}</td>
                  <td className={isFlat(d, m.fmt) ? "" : good ? "good" : "bad"}>
                    {m.fmt(s.p50)}
                    {!isFlat(d, m.fmt) && <small>{signed(d, m.fmt)}</small>}
                  </td>
                  <td className="dc-rbcell"><RangeBar base={b} shock={s} className="rb dc-rb" /></td>
                </tr>
              );
            })}
          </tbody>
        </table>
        <p className="dc-note">200번 돌린 한 달 시뮬레이션의 중앙값. 막대는 10~90 백분위이고, 모든 값은 검토 전 예시값입니다.</p>

        <details className="dc-tree">
          <summary>이익을 움직이는 요인 {ontology ? `${ontology.nodes.length}개` : ""}</summary>
          {ontology && <OntologyTree ontology={ontology} className="ot dc-ot" open={["drv_operating_profit"]} />}
        </details>

        <div className="dc-chat">
          <h2 className="dc-sub">사장님에게 묻기</h2>
          <p>사장님 에이전트를 연결하면 이 상황에서 어떻게 대응할지 근거와 함께 답합니다.</p>
          <form onSubmit={(e) => e.preventDefault()}>
            <input aria-label="질문" disabled placeholder="예: 방학 때는 영업시간을 줄이시나요?" />
            <button disabled>묻기</button>
          </form>
        </div>
      </section>
    </div>
  );
}
