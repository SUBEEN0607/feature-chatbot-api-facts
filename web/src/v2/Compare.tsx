// 비교 (sandbox): two plans for the same month with the same seed, so the only difference is the plan.
// Two sandbox seasons are created with one seed and each plays its first month (POST /season/{id}/play).
import { useState } from "react";
import { api } from "./api";
import { man, manSigned, num } from "./format";
import { changedKeys, LEVERS, leverValueLabel } from "./levers";
import type { SeasonMeta } from "./meta";
import { Waterfall } from "./parts";
import { Levers } from "./PlanBoard";
import { BASE_PLAN, type MonthResult, type Plan } from "./types";

const ROWS: [string, string, (v: number) => string, boolean][] = [
  ["op", "영업이익", man, true], ["revenue", "매출", man, true], ["covers", "손님", (v) => `${num(v)}명`, true],
  ["ticket", "객단가", (v) => `${num(v)}원`, true], ["walkaways", "돌아간 팀", (v) => `${num(v)}팀`, false],
  ["labor", "인건비", man, false], ["cogs", "식재료비", man, false],
];

// `from`: opened from the 개선 리포트 — that month's actual plan (A) against the suggested alternative (B), both played
// on sandbox forks of the season at that month (same state, same events, same customer stream)
export type CompareFrom = { seasonId: string; monthIndex: number; monthLabel: string; a: Plan; b: Plan; title: string; bChoices?: Record<string, string> };

export function Compare({ meta, from, onBack }: { meta: SeasonMeta | null; from?: CompareFrom | null; onBack?: () => void }) {
  const [a, setA] = useState<Plan>(from?.a ?? BASE_PLAN);
  const [b, setB] = useState<Plan>(from?.b ?? { ...BASE_PLAN, meat_price: 21000 });
  const [res, setRes] = useState<[MonthResult, MonthResult] | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [seed, setSeed] = useState(() => 1 + Math.floor(Math.random() * 99999));
  async function run() {
    setBusy(true);
    setErr(null);
    try {
      let ra: MonthResult, rb: MonthResult;
      if (from) {
        // forks of that month; A replays what was played there (incl. its night choices: start_month first), B the alternative
        const [fa, fb] = await Promise.all([api.fork(from.seasonId, from.monthIndex), api.fork(from.seasonId, from.monthIndex)]);
        const choices = (fa as unknown as { actual?: { night_choices?: Record<string, string> } }).actual?.night_choices ?? {};
        const playA = async () => {
          if (Object.keys(choices).length) { await api.startMonth(fa.id, a); return api.play(fa.id, a, undefined, choices); }
          return api.play(fa.id, a);
        };
        // B: the alternative plan, or the same plan with a different night choice (start_month first, then the choice)
        const bChoices = from.bChoices ? { ...choices, ...from.bChoices } : null;
        const playB = async () => {
          if (bChoices && Object.keys(bChoices).length) { await api.startMonth(fb.id, b); return api.play(fb.id, b, undefined, bChoices); }
          return api.play(fb.id, b);
        };
        [ra, rb] = await Promise.all([playA(), playB()]);
      } else {
        const [sa, sb] = await Promise.all([api.newSeason("sandbox", seed), api.newSeason("sandbox", seed)]);
        [ra, rb] = await Promise.all([api.play(sa.id, a), api.play(sb.id, b)]);
      }
      setRes([ra, rb]);
    } catch (e) {
      setErr(from ? `이 달을 다시 돌리려면 API의 시즌 복사(fork)가 필요합니다 (${(e as Error).message}).` : `비교는 로컬 API가 필요합니다 (${(e as Error).message}).`);
    } finally {
      setBusy(false);
    }
  }
  const diffs = changedKeys(a, b);
  const col = (name: string, p: Plan, set: (x: Plan) => void) => (
    <div>
      <div className="v2-panel-head"><h2>계획 {name}</h2><p>{changedKeys(p, BASE_PLAN).length ? `평소와 다른 레버 ${changedKeys(p, BASE_PLAN).length}개` : "평소 계획"}</p></div>
      <div className="v2-scroll"><Levers plan={p} base={BASE_PLAN} set={(x) => set({ ...p, ...x })} meta={meta} /></div>
    </div>
  );
  return (
    <section className="v2-compare" aria-label="두 계획 비교" data-testid="compare">
      {col("A", a, setA)}
      {col("B", b, setB)}
      <div>
        <div className="v2-panel-head">
          <h2>{from ? from.title : "같은 달, 같은 운으로"}</h2>
          <p>{from ? `${from.monthLabel}, 그 달의 상태와 사건 그대로. A는 실제로 한 운영, B는 리포트가 권한 운영입니다.` : `10월, 시드 ${seed}. 사건과 손님 도착은 두 계획이 같고 계획만 다릅니다.`}</p>
          {from && <p className="v2-note">리포트의 차이는 시즌 끝 현금까지 이어진 효과(단골, 평점, 이후 달)를 합한 값이고, 여기 표는 이 한 달만의 차이입니다.</p>}
          {onBack && <button className="v2-btn quiet" onClick={onBack}>리포트로 돌아가기</button>}
        </div>
        <div className="v2-diff">
          <p style={{ fontSize: 13 }}>다른 점: {diffs.length ? diffs.map((k) => { const l = LEVERS.find((x) => x.key === k)!; return `${l.label} ${leverValueLabel(l, a[k])} 대 ${leverValueLabel(l, b[k])}`; }).join(", ") : "없음"}</p>
          <div style={{ display: "flex", gap: 8 }}>
            <button className="v2-btn primary big" onClick={run} disabled={busy} data-testid="compare-run">{busy ? "돌리는 중" : "두 계획 돌리기"}</button>
            {!from && <button className="v2-btn" onClick={() => { setSeed(1 + Math.floor(Math.random() * 99999)); setRes(null); }}>다른 운</button>}
          </div>
          {err && <p className="v2-warn">{err}</p>}
          {res && (
            <>
              <table style={{ inlineSize: "100%", borderCollapse: "collapse", fontSize: 13.5 }} data-testid="compare-table">
                <thead><tr><th style={{ textAlign: "start" }} /><th style={{ textAlign: "end" }}>A</th><th style={{ textAlign: "end" }}>B</th><th style={{ textAlign: "end" }}>B − A</th></tr></thead>
                <tbody>
                  {ROWS.map(([k, label, f, upGood]) => {
                    const d = res[1].draw.kpis[k] - res[0].draw.kpis[k];
                    const good = upGood ? d > 0 : d < 0;
                    return (
                      <tr key={k} style={{ borderBlockStart: "1px solid var(--line)" }}>
                        <td style={{ paddingBlock: 6 }}>{label}</td>
                        <td className="num" style={{ textAlign: "end" }}>{f(res[0].draw.kpis[k])}</td>
                        <td className="num" style={{ textAlign: "end" }}>{f(res[1].draw.kpis[k])}</td>
                        <td className={`num ${Math.abs(d) < 1e-6 ? "flat" : good ? "up" : "down"}`} style={{ textAlign: "end", fontWeight: 700 }}>{k === "op" || k === "revenue" || k === "labor" || k === "cogs" ? manSigned(d) : `${d > 0 ? "+" : ""}${num(d)}`}</td>
                      </tr>
                    );
                  })}
                  <tr style={{ borderBlockStart: "1px solid var(--line)" }}><td style={{ paddingBlock: 6 }}>월말 평점</td><td className="num" style={{ textAlign: "end" }}>{res[0].state_after.rating.toFixed(2)}</td><td className="num" style={{ textAlign: "end" }}>{res[1].state_after.rating.toFixed(2)}</td><td /></tr>
                  <tr><td style={{ paddingBlock: 6 }}>직원 피로</td><td className="num" style={{ textAlign: "end" }}>{Math.round(res[0].state_after.fatigue)}</td><td className="num" style={{ textAlign: "end" }}>{Math.round(res[1].state_after.fatigue)}</td><td /></tr>
                </tbody>
              </table>
              <h3 style={{ fontSize: 14 }}>B가 A보다 어디서 벌고 잃었나</h3>
              <Waterfall steps={[
                { driver: "A의 영업이익", key: "base", delta: res[0].draw.kpis.op, kind: "start" },
                ...res[1].waterfall.filter((w) => w.kind === "step").map((w) => ({ ...w, delta: w.delta - (res[0].waterfall.find((x) => x.key === w.key)?.delta ?? 0) })),
                { driver: "B의 영업이익", key: "end", delta: res[1].draw.kpis.op, kind: "end" as const },
              ]} />
              <p className="v2-note">한 번 뽑은 결과입니다. 운의 범위는 A {man(res[0].draw.p10.op)} ~ {man(res[0].draw.p90.op)}, B {man(res[1].draw.p10.op)} ~ {man(res[1].draw.p90.op)}.</p>
            </>
          )}
        </div>
      </div>
    </section>
  );
}
