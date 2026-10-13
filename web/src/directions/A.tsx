// Direction A: an editorial report. The shock is read as one sentence; the numbers are a typeset table.
import { KPI_META, SHOCK_LABELS, isFlat, signed } from "../data";
import { CONF_KO, DRIVER_KO, FloorPlan, OntologyTree, RangeBar, SHOCK_ORDER, headline, useDashboard } from "../shared/components";
import "./a.css";

export default function DirectionA({ shock, setShock }: { shock: string; setShock: (s: string) => void }) {
  const { hero, ontology, shocks, kpis } = useDashboard(shock);
  const rows = KPI_META;
  return (
    <div className="da">
      <nav className="da-nav" aria-label="상황 고르기">
        <a className="da-home" href="#/lab">목록으로</a>
        <p className="da-nav-title">이런 일이 생기면</p>
        <ul>
          {SHOCK_ORDER.map((id) => (
            <li key={id}>
              <button aria-current={id === shock} onClick={() => setShock(id)}>
                <span className="da-nav-driver">{shocks ? DRIVER_KO[shocks[id].driver] ?? shocks[id].driver : ""}</span>
                {SHOCK_LABELS[id]}
              </button>
            </li>
          ))}
        </ul>
      </nav>

      <main className="da-main">
        <p className="da-kicker">대학로 삼겹살집 트윈, 월간 시뮬레이션 {kpis?.meta.runs ?? 200}회</p>
        <h1 className="da-head">{kpis ? headline(kpis) : " "}</h1>
        {shocks && (
          <div className="da-deck">
            {shocks[shock].params.map((p) => (
              <p key={p.parameter}>{p.mechanism}. {p.rationale}. 근거 수준 {CONF_KO[p.confidence] ?? p.confidence}.</p>
            ))}
          </div>
        )}

        <figure className="da-table">
          <figcaption>표 1. 한 달 결과, 중앙값과 10~90 백분위 범위</figcaption>
          <table>
            <thead>
              <tr><th scope="col">지표</th><th scope="col">평소</th><th scope="col">충격 후</th><th scope="col">차이</th><th scope="col" className="da-rangecol">범위</th></tr>
            </thead>
            <tbody>
              {kpis && rows.map((r) => {
                const b = kpis.base[r.key], s = kpis.shocked[r.key];
                const d = s.p50 - b.p50;
                const good = r.better === "up" ? d > 0 : d < 0;
                return (
                  <tr key={r.key}>
                    <th scope="row">{r.label}</th>
                    <td>{r.fmt(b.p50)}</td>
                    <td>{r.fmt(s.p50)}</td>
                    <td className={isFlat(d, r.fmt) ? "da-flat" : good ? "da-up" : "da-down"}>{isFlat(d, r.fmt) ? "변화 없음" : signed(d, r.fmt)}</td>
                    <td className="da-rangecol"><RangeBar base={b} shock={s} className="rb da-rb" /></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <p className="da-foot">초록 막대는 평소, 주황 막대는 충격 후입니다. 모든 값은 사람이 검토하기 전의 예시값입니다.</p>
        </figure>

        <figure className="da-plan">
          {hero && <FloorPlan hero={hero} className="fp da-fp" />}
          <figcaption>
            그림 1. 합성 매장 평면. 실내 4인 테이블 {hero?.tables ?? ""}개와 야장 {hero?.terrace_tables ?? ""}개, 직원 {hero?.servers ?? ""}명.{" "}
            <a href={`#/lab/replay?scenario=${shock === "SH09" ? "SH09" : "SH03"}`}>3D로 하룻밤 다시 보기</a>
          </figcaption>
        </figure>

        <section className="da-chat" aria-label="사장님에게 묻기">
          <h2>사장님에게 묻기</h2>
          <p className="da-chat-note">예시 질문입니다. 답변은 사장님 에이전트를 연결한 뒤에 채워집니다.</p>
          <p className="da-q">도매가가 이만큼 오르면 가격을 올리실 건가요, 버티실 건가요?</p>
          <p className="da-a">답변 대기 중</p>
          <form className="da-ask" onSubmit={(e) => e.preventDefault()}>
            <label htmlFor="da-input">질문</label>
            <input id="da-input" disabled placeholder="사장님에게 물어볼 내용을 적어 주세요" />
            <button disabled>보내기</button>
          </form>
        </section>
      </main>

      <aside className="da-margin" aria-label="이익을 움직이는 요인">
        <h2>무엇이 이익을 움직이나</h2>
        <p>영업이익에서 시작해 매출과 비용으로 내려가는 요인 나무입니다. 항목을 누르면 아래 요인이 펼쳐집니다.</p>
        {ontology && <OntologyTree ontology={ontology} className="ot da-ot" />}
      </aside>
    </div>
  );
}
