// #/report-print: the 시연 season report as a printable page (offline; the API's /report.html covers free play).
import { useEffect, useState } from "react";
import { man, num } from "./format";
import { Prelim } from "./parts";
import { COLS, reportApi, type SeasonReport } from "./report";
import "./v2.css";

export default function ReportPrint() {
  const [rep, setRep] = useState<SeasonReport | null>(null);
  useEffect(() => { reportApi.guided().then(setRep).catch(() => setRep(null)); }, []);
  if (!rep) return <p style={{ padding: 24 }}>시연용 리포트를 불러오는 중입니다</p>;
  const s = rep.summary as Record<string, number | string | null>;
  return (
    <main className="rp-print">
      <header>
        <h1>대학로 삼겹살 시즌 리포트 {rep.data_limits?.total ? <Prelim plain input={{ review: { reviewed: rep.data_limits.reviewed ?? 0, total: rep.data_limits.total } }} testid="print-prelim" /> : null}</h1>
        <p>시연 모드 이야기 경로. 모든 숫자는 검토 전 예시값이며, 가정 표시는 화면의 원문을 따릅니다.</p>
        <button className="no-print" onClick={() => print()}>인쇄</button>
      </header>
      <section>
        <h2>요약</h2>
        <p>{num(Number(s.months_played ?? rep.table.length))}개월, 누적 영업이익 {man(Number(s.total_op ?? 0))}, 시즌 끝 현금 {man(Number(s.ending_cash ?? 0))}</p>
      </section>
      <section>
        <h2>이렇게 했다면 더 나았을 다섯 가지</h2>
        <ol>{rep.improvements.slice(0, 5).map((m, i) => <li key={i}>{m.takeaway_ko ?? m.why_ko ?? `${m.driver}에서 시즌 동안 ${man(Math.abs(m.loss ?? 0))} 손해`} ({m.tag ?? "가정"}){m.downside_ko ? `. 대가: ${m.downside_ko}` : ""}</li>)}</ol>
      </section>
      {rep.cash_only && rep.cash_only.length > 0 && (
        <section>
          <h2>현금만 늘리는 선택 (주의)</h2>
          <p>시즌 끝 현금은 늘지만 가게 가치는 줄어드는 선택입니다. 개선으로 치지 않았습니다.</p>
          <ul>{rep.cash_only.map((c, i) => <li key={i}>{c.warning_ko ?? c.takeaway_ko}</li>)}</ul>
        </section>
      )}
      <section>
        <h2>달별 기록</h2>
        <table>
          <thead><tr>{COLS.map(([k, h]) => <th key={k}>{h}</th>)}</tr></thead>
          <tbody>{rep.table.map((r, i) => <tr key={i}>{COLS.map(([k, , kind]) => <td key={k}>{r[k] == null ? "" : kind === "won" ? man(Number(r[k])) : kind === "float2" ? Number(r[k]).toFixed(2) : kind === "pct" ? `${Math.round(Number(r[k]) * 100)}%` : kind === "int" ? num(Number(r[k])) : String(r[k])}</td>)}</tr>)}</tbody>
        </table>
      </section>
    </main>
  );
}
