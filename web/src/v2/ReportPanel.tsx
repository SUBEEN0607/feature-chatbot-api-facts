// 개선 리포트 on the season end screens: top 5 improvements (cash and 가게 가치 difference, cost, 근거/가정, a jump into
// 비교 for that month), 잘한 결정, 운이 작용한 달, a sortable and filterable month table, CSV and printable report,
// and 리포트에 묻기 with four preset questions. Free play reads the API; 시연 reads guided/report.json offline.
import { useEffect, useMemo, useState } from "react";
import { man, manSigned, num, pct } from "./format";
import { leverLabel } from "./levers";
import type { SeasonMeta } from "./meta";
import { Prelim, Tag } from "./parts";
import { COLS, offlineAnswer, PRESET_QUESTIONS, reportApi, reportCsv, type Improvement, type ReportAnswer, type ReportRow, type SeasonReport } from "./report";

const fmt = (v: unknown, kind: string) => {
  if (v == null || v === "") return "";
  if (kind === "won") return man(Number(v));
  if (kind === "int") return num(Number(v));
  if (kind === "float2") return Number(v).toFixed(2);
  if (kind === "pct") return pct(Number(v));
  return String(v);
};

type Filter = "all" | "loss" | "behind" | "luck";
const FILTERS: [Filter, string][] = [["all", "모든 달"], ["loss", "적자인 달"], ["behind", "평소보다 못한 달"], ["luck", "운이 크게 작용한 달"]];

export function ReportPanel({ seasonId, offline, meta, onCompare }: {
  seasonId: string | null; offline: boolean; meta: SeasonMeta | null; onCompare?: (imp: Improvement) => void;
}) {
  const [rep, setRep] = useState<SeasonReport | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [sort, setSort] = useState<{ key: string; dir: 1 | -1 }>({ key: "month_index", dir: 1 });
  const [filter, setFilter] = useState<Filter>("all");
  const [answers, setAnswers] = useState<ReportAnswer[]>([]);
  const [asking, setAsking] = useState(false);
  const [q, setQ] = useState("");
  useEffect(() => {
    let live = true;
    (offline || !seasonId ? reportApi.guided() : reportApi.get(seasonId))
      .then((r) => live && setRep(r))
      .catch(() => live && setErr(offline ? "시연용 리포트 파일(guided/report.json)이 아직 없습니다." : "리포트를 불러오지 못했습니다. API가 켜져 있는지 확인하세요."));
    return () => { live = false; };
  }, [seasonId, offline]);

  const rows = useMemo(() => {
    if (!rep) return [];
    const withIdx: ReportRow[] = rep.table.map((r, i) => ({ ...r, month_index: (r.month_index as number | undefined) ?? i }));
    const f = withIdx.filter((r) => filter === "all" ? true : filter === "loss" ? Number(r.op) < 0
      : filter === "behind" ? Number(r.net_vs_shadow) < 0 : Number(r.band_position) <= 0.2 || Number(r.band_position) >= 0.8);
    return [...f].sort((a, b) => {
      const x = a[sort.key], y = b[sort.key];
      const c = typeof x === "number" && typeof y === "number" ? x - y : String(x ?? "").localeCompare(String(y ?? ""), "ko");
      return c * sort.dir;
    });
  }, [rep, sort, filter]);

  async function ask(question: string) {
    if (!rep || !question.trim() || asking) return;
    setAsking(true);
    setQ("");
    try {
      const a = offline || !seasonId ? offlineAnswer(rep, question) : await reportApi.ask(seasonId, question);
      setAnswers((x) => [...x, a]);
    } catch {
      setAnswers((x) => [...x, offlineAnswer(rep, question)]);
    } finally {
      setAsking(false);
    }
  }

  const csvHref = useMemo(() => (rep && (offline || !seasonId) ? URL.createObjectURL(new Blob([reportCsv(rep)], { type: "text/csv;charset=utf-8" })) : null), [rep, offline, seasonId]);
  useEffect(() => () => { if (csvHref) URL.revokeObjectURL(csvHref); }, [csvHref]);

  if (err) return <section className="v2-report" data-testid="report"><h3>개선 리포트</h3><p className="v2-note">{err}</p></section>;
  if (!rep) return <section className="v2-report" data-testid="report"><h3>개선 리포트</h3><p className="v2-note">리포트를 만드는 중입니다</p></section>;
  const imps = rep.improvements.slice(0, 5);
  return (
    <section className="v2-report" data-testid="report" aria-label="개선 리포트">
      <div className="rp-head">
        <h3>개선 리포트</h3>
        <div className="rp-actions">
          {csvHref
            ? <a className="v2-btn" href={csvHref} download="season-report.csv" data-testid="csv">CSV 다운로드</a>
            : <a className="v2-btn" href={reportApi.csvUrl(seasonId!)} data-testid="csv">CSV 다운로드</a>}
          {offline || !seasonId
            ? <a className="v2-btn" href="#/report-print" target="_blank" rel="noopener" data-testid="print">리포트 열기 (인쇄용)</a>
            : <a className="v2-btn" href={reportApi.htmlUrl(seasonId)} target="_blank" rel="noopener" data-testid="print">리포트 열기 (인쇄용)</a>}
        </div>
      </div>

      <div className="rp-grid">
        <div>
          <h4>{imps.length ? `이렇게 했다면 더 나았을 ${["한", "두", "세", "네", "다섯"][imps.length - 1]} 가지` : "이렇게 했다면 더 나았을 선택"}</h4>
          {!imps.length && <p className="v2-note" data-testid="no-improvements">이번 시즌에는 가게 가치를 올리는 다른 선택을 찾지 못했습니다. 계획이 평소 계획에 가깝거나 운영한 달이 짧으면 그럴 수 있습니다</p>}
          <ol className="rp-imps" data-testid="improvements">
            {imps.map((m, i) => {
              const title = m.takeaway_ko ?? m.why_ko ?? (m.lever ? `${m.month_label} ${m.lever_ko ?? leverLabel(m.lever)}: ${m.from_ko ?? String(m.from ?? "")}에서 ${m.to_ko ?? String(m.to ?? "")}로` : `${m.driver}에서 시즌 동안 ${man(Math.abs(m.loss ?? 0))} 손해`);
              const tag = m.tag ?? m.basis ?? "가정";
              return (
                <li key={m.id ?? i} data-imp={i}>
                  <b>{title}</b>
                  <span className="rp-nums num">
                    {m.cash_delta != null ? <>현금 <em className={m.cash_delta >= 0 ? "up" : "down"}>{manSigned(m.cash_delta)}</em></> : m.loss != null ? <>손해 <em className="down">{man(m.loss)}</em></> : null}
                    {m.store_value_delta != null && <>, 가게 가치 <em className={m.store_value_delta >= 0 ? "up" : "down"}>{manSigned(m.store_value_delta)}</em></>}
                    {m.cost != null && <>, 비용 {man(m.cost)}</>}
                  </span>
                  {m.downside_ko && <span className="v2-note"><b className="down">대가</b> {m.downside_ko}</span>}
                  {(m.months?.length || m.levers?.length) ? <span className="v2-note">{m.months?.join(", ")}{m.levers?.length ? `, 관련 운영 ${m.levers.join(", ")}` : ""}</span> : null}
                  <span className="rp-row">
                    <Tag tag={tag.replace(/^근거\s*/, "")} title={title} note={m.basis ?? null} meta={meta} />
                    {(m.alt_plan || m.alt_night_choices) && m.month_index != null && onCompare && !offline
                      ? <button className="v2-btn" onClick={() => onCompare(m)} data-testid="imp-compare">이 달을 비교로 보기</button>
                      : null}
                  </span>
                </li>
              );
            })}
          </ol>
        </div>
        {rep.cash_only && rep.cash_only.length > 0 && (
          <div className="rp-cash" data-testid="cash-only">
            <h4>현금만 늘리는 선택 (주의)</h4>
            <p className="v2-note">시즌 끝 현금은 늘지만 가게 가치(앞으로 벌 힘)는 줄어드는 선택입니다. 개선으로 치지 않았습니다.</p>
            <ul>
              {rep.cash_only.map((c, i) => (
                <li key={c.id ?? i} data-cash-only={i}>
                  <b>{c.warning_ko ?? c.takeaway_ko}</b>
                  <span className="rp-nums num">현금 <em className="up">{manSigned(c.cash_delta ?? 0)}</em>, 가게 가치 <em className="down">{manSigned(c.store_value_delta ?? 0)}</em></span>
                  <span className="rp-row"><Tag tag={c.tag ?? "가정"} title={c.takeaway_ko ?? "현금만 늘리는 선택"} note={c.basis ?? null} downside={c.downside_ko ?? null} meta={meta} />
                    {(c.alt_plan || c.alt_night_choices) && c.month_index != null && onCompare && !offline
                      ? <button className="v2-btn" onClick={() => onCompare(c)}>이 달을 비교로 보기</button> : null}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
        <div className="rp-side">
          <h4>잘한 결정</h4>
          {rep.good_decisions.length ? (
            <ul data-testid="good">{rep.good_decisions.map((g, i) => <li key={i}><b>{g.month_label}</b> {g.what_ko ?? g.what} {g.store_value_delta != null && <em className={g.store_value_delta >= 0 ? "up" : "down"} data-good-delta={g.store_value_delta}>가게 가치 {manSigned(g.store_value_delta)}</em>}{g.why_ko && <span className="v2-note" style={{ display: "block" }}>{g.why_ko}</span>}</li>)}</ul>
          ) : <p className="v2-note">평소 계획보다 5만원 넘게 더 번 결정이 없었습니다.</p>}
          <h4>운이 작용한 달</h4>
          {rep.luck_months.length ? (
            <ul data-testid="luck">{rep.luck_months.map((l, i) => <li key={i}><b>{l.month_label}</b> {l.luck_ko ?? l.luck}: {man(l.op)} (예상 {man(l.p10_op)} ~ {man(l.p90_op)})</li>)}</ul>
          ) : <p className="v2-note">모든 달이 예상 범위 가운데쯤에 떨어졌습니다. 결과는 대체로 계획 때문입니다.</p>}
        </div>
      </div>

      <div className="rp-table-head">
        <h4>달별 기록</h4>
        {rep.table.length > 1 && <div className="v2-seg" role="group" aria-label="달 거르기">
          {FILTERS.map(([id, label]) => <button key={id} aria-pressed={filter === id} onClick={() => setFilter(id)} data-filter={id}>{label}</button>)}
        </div>}
      </div>
      <div className="rp-table-wrap">
        <table className="rp-table" data-testid="report-table">
          <thead>
            <tr>{COLS.map(([k, h]) => (
              <th key={k} aria-sort={sort.key === k ? (sort.dir === 1 ? "ascending" : "descending") : "none"}>
                <button onClick={() => setSort((s) => ({ key: k, dir: s.key === k ? (s.dir === 1 ? -1 : 1) : (k === "month_label" ? 1 : -1) }))} data-sort={k}>{h}</button>
              </th>
            ))}</tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={String(r.month_index)} data-row={String(r.month_label)}>
                {COLS.map(([k, , kind]) => <td key={k} className={kind === "text" ? "" : "num"} data-k={k}>{fmt(r[k], kind)}</td>)}
              </tr>
            ))}
            {!rows.length && <tr><td colSpan={COLS.length} className="v2-note">조건에 맞는 달이 없습니다.</td></tr>}
          </tbody>
        </table>
      </div>

      <div className="rp-ask" data-testid="report-ask">
        <h4>리포트에 묻기</h4>
        <div className="v2-chips">{PRESET_QUESTIONS.map((p) => <button key={p} onClick={() => ask(p)} disabled={asking}>{p}</button>)}</div>
        <div className="v2-msgs">
          {answers.map((a, i) => (
            <div key={i} style={{ display: "grid", gap: 6 }}>
              <div className="v2-msg me">{a.question}</div>
              <div className="v2-msg them" data-testid="report-answer">{a.answer}{a.citations?.length ? <span className="src">근거: {a.citations.join(", ")}</span> : null}</div>
            </div>
          ))}
          {asking && <div className="v2-msg them">이 시즌 기록을 찾아보는 중입니다</div>}
        </div>
        <form className="v2-ask-form" onSubmit={(e) => { e.preventDefault(); ask(q); }}>
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="이 시즌에 대해 직접 묻기" aria-label="리포트 질문" maxLength={200} />
          <button className="v2-btn primary" disabled={asking || !q.trim()}>묻기</button>
        </form>
      </div>
      {(typeof rep.summary.caveat_ko === "string" || rep.data_limits?.total) && (
        <p className="v2-note v2-report-caveat" data-testid="report-caveat">
          {rep.data_limits?.total ? <Prelim input={{ review: { reviewed: rep.data_limits.reviewed ?? 0, total: rep.data_limits.total }, tag: "가정" }} testid="report-prelim" /> : null}
          {typeof rep.summary.caveat_ko === "string" ? rep.summary.caveat_ko : null}
        </p>
      )}
      <p className="v2-note">{rep.data_limits?.total ? `숫자는 사람 검토 ${rep.data_limits.reviewed ?? 0}/${rep.data_limits.total}인 가정 위에서 계산했습니다. ` : ""}{rep.source?.startsWith("api.report") ? "개선 항목은 손해가 컸던 항목 기준이며, 대안 계획 비교는 시즌 엔진 리포트가 들어오면 붙습니다." : ""}</p>
    </section>
  );
}
