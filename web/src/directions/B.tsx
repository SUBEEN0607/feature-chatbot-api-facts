// Direction B: a light operations console. Everything on one screen; the KPI strip reads like instruments.
import { KPI_META, SHOCK_LABELS, isFlat, man, signed, useData } from "../data";
import { DRIVER_KO, FloorPlan, OntologyTree, RangeBar, SHOCK_ORDER, useDashboard } from "../shared/components";
import "./b.css";

type Summary = { base: Record<string, number>; shocks_p50: Record<string, Record<string, number>>; runs: number };

export default function DirectionB({ shock, setShock }: { shock: string; setShock: (s: string) => void }) {
  const { hero, ontology, shocks, kpis } = useDashboard(shock);
  const summary = useData<Summary>("summary.json");
  const groups: { driver: string; ids: string[] }[] = [];
  if (shocks) {
    for (const id of SHOCK_ORDER) {
      const d = DRIVER_KO[shocks[id].driver] ?? shocks[id].driver;
      const g = groups.find((x) => x.driver === d);
      if (g) g.ids.push(id);
      else groups.push({ driver: d, ids: [id] });
    }
  }
  return (
    <div className="db">
      <header className="db-bar">
        <a href="#/lab" className="db-home">목록</a>
        <h1>대학로 삼겹살집 운영 콘솔</h1>
        <p className="db-meta">합성 매장 1곳, 한 달 시뮬레이션 {summary?.runs ?? 200}회. 모든 값은 검토 전 예시값</p>
        <p className="db-now">지금 보는 상황 <strong>{SHOCK_LABELS[shock]}</strong></p>
      </header>

      <section className="db-kpis" aria-label="한 달 지표">
        {kpis && KPI_META.map((m) => {
          const b = kpis.base[m.key], s = kpis.shocked[m.key];
          const d = s.p50 - b.p50;
          const flat = isFlat(d, m.fmt);
          const good = m.better === "up" ? d > 0 : d < 0;
          return (
            <div className="db-kpi" key={m.key}>
              <p className="db-kpi-label">{m.label}</p>
              <p className="db-kpi-value">{m.fmt(s.p50)}</p>
              <p className={`db-kpi-delta ${flat ? "flat" : good ? "good" : "bad"}`}>{flat ? "평소와 같음" : `평소 대비 ${signed(d, m.fmt)}`}</p>
              <RangeBar base={b} shock={s} className="rb db-rb" />
            </div>
          );
        })}
      </section>

      <nav className="db-shocks" aria-label="상황 목록">
        <p className="db-panel-title">상황</p>
        {groups.map((g) => (
          <div key={g.driver} className="db-group">
            <p className="db-group-name">{g.driver}</p>
            <ul>
              {g.ids.map((id) => {
                const op = summary ? summary.shocks_p50[id].op - summary.base.op : 0;
                return (
                  <li key={id}>
                    <button aria-current={id === shock} onClick={() => setShock(id)}>
                      <span>{SHOCK_LABELS[id]}</span>
                      <span className={op < 0 ? "bad" : "good"}>{signed(op, man)}</span>
                    </button>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
        <p className="db-legend"><i className="lg-base" />평소 <i className="lg-shock" />충격 후. 막대는 10~90 백분위, 세로선은 중앙값, 오른쪽 숫자는 영업이익 변화</p>
      </nav>

      <section className="db-stage" aria-label="매장">
        <div className="db-stage-head">
          <p className="db-panel-title">매장 평면</p>
          <a className="db-open" href={`#/lab/replay?scenario=${shock === "SH09" ? "SH09" : "SH03"}`}>3D 재생 열기</a>
        </div>
        {hero && <FloorPlan hero={hero} className="fp db-fp" />}
        <p className="db-stage-note">실내 4인 테이블 {hero?.tables}개, 야장 {hero?.terrace_tables}개, 서빙 {hero?.servers}명. 3D 재생 화면에서 토요일 밤을 다시 볼 수 있습니다.</p>
      </section>

      <section className="db-chat" aria-label="사장님 대화">
        <p className="db-panel-title">사장님 대화</p>
        <div className="db-log">
          <p className="db-log-q"><span>질문 예시</span>이 상황이면 무엇부터 바꾸시겠어요?</p>
          <p className="db-log-a">사장님 에이전트를 연결하면 답변과 근거 출처가 여기에 표시됩니다.</p>
        </div>
        <form className="db-ask" onSubmit={(e) => e.preventDefault()}>
          <input aria-label="질문" disabled placeholder="질문 입력 (연결 전)" />
          <button disabled>보내기</button>
        </form>
      </section>

      <aside className="db-tree" aria-label="요인 나무">
        <p className="db-panel-title">요인 나무</p>
        {ontology && <OntologyTree ontology={ontology} className="ot db-ot" />}
      </aside>
    </div>
  );
}
