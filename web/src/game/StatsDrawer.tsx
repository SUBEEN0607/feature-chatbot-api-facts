// 가게 능력치: the ontology driver tree with each node's value, source and confidence. Selecting a node
// highlights everything it affects downstream (edges.csv).
import { useMemo, useState } from "react";
import type { Drivers, OntNode, Ontology } from "../data";
import { CONF_KO } from "./parts";

// Survival labels come from 인허가 data at 상권 level; the store simulation does not compute them.
const SIM_DOES_NOT_COMPUTE = ["lbl_survival_months", "lbl_closed_24m"];

const METHOD_KO: Record<string, string> = { public: "공공데이터", guesstimate: "추정", interview_later: "인터뷰 예정", derived: "계산" };

function fmt(v: number | string | null | undefined, unit: string): string {
  if (v == null) return "값 없음";
  if (typeof v === "string") return v;
  if (unit.startsWith("₩")) return Math.abs(v) >= 1e6 ? `${Math.round(v / 10000).toLocaleString("ko-KR")}만원` : `${Math.round(v).toLocaleString("ko-KR")}원`;
  if (unit === "비율") return `${(v * 100).toFixed(1)}%`;
  const n = Math.abs(v) >= 100 ? Math.round(v).toLocaleString("ko-KR") : String(Number(v.toFixed(2)));
  return `${n} ${unit}`;
}

export function StatsDrawer({ ontology, drivers, excel, scenarioLabel, onClose }: {
  ontology: Ontology; drivers: Drivers; excel: Drivers; scenarioLabel: string; onClose: () => void;
}) {
  const [open, setOpen] = useState<Set<string>>(new Set(["drv_operating_profit", "drv_revenue", "drv_total_cost"]));
  const [sel, setSel] = useState<string | null>(null);
  const byId = useMemo(() => new Map(ontology.nodes.map((n) => [n.id, n])), [ontology]);
  const kids = useMemo(() => {
    const m = new Map<string, OntNode[]>();
    for (const n of ontology.nodes) if (n.parent) m.set(n.parent, [...(m.get(n.parent) ?? []), n]);
    return m;
  }, [ontology]);
  const affected = useMemo(() => {
    if (!sel) return new Set<string>();
    const out = new Set<string>();
    const q = [sel];
    while (q.length) {
      const id = q.shift()!;
      for (const e of ontology.edges) if (e.from === id && !out.has(e.to)) {
        out.add(e.to);
        q.push(e.to);
      }
    }
    for (const lbl of SIM_DOES_NOT_COMPUTE) out.delete(lbl);
    return out;
  }, [sel, ontology]);

  const toggle = (id: string) => setOpen((s) => {
    const n = new Set(s);
    if (n.has(id)) n.delete(id);
    else n.add(id);
    return n;
  });

  const render = (n: OntNode, depth: number): React.ReactNode => {
    const ch = kids.get(n.id) ?? [];
    const sim = drivers[n.id];
    const xl = excel[n.id];
    const value = sim != null ? fmt(sim, n.unit) : fmt(n.base, n.unit);
    const cls = ["g-node", n.id === sel ? "is-sel" : "", affected.has(n.id) ? "is-hit" : ""].join(" ");
    return (
      <li key={n.id}>
        <div className={cls} style={{ paddingInlineStart: 8 + depth * 14 }}>
          {ch.length ? (
            <button className="g-node-caret" aria-expanded={open.has(n.id)} aria-label={`${n.ko} 펼치기`} onClick={() => toggle(n.id)} />
          ) : <span className="g-node-caret-sp" />}
          <button className="g-node-name" onClick={() => setSel(sel === n.id ? null : n.id)} aria-pressed={n.id === sel}>
            {n.ko}
          </button>
          <span className="g-node-val" data-node={n.id} data-value={sim ?? ""}>{value}</span>
          <span className="g-node-meta">
            {[
              sim != null ? "시뮬레이션" : METHOD_KO[n.method] ?? n.method,
              xl != null ? `엑셀 추정 ${fmt(xl, n.unit)}` : null,
              n.confidence ? `근거 ${CONF_KO[n.confidence] ?? n.confidence}` : null,
              n.source ? `출처 ${n.source.replaceAll(";", " ")}` : null,
            ].filter(Boolean).join(", ")}
          </span>
        </div>
        {ch.length > 0 && open.has(n.id) && <ul>{ch.map((c) => render(c, depth + 1))}</ul>}
      </li>
    );
  };
  const root = byId.get("drv_operating_profit");
  const labels = ontology.nodes.filter((n) => n.id.startsWith("lbl_"));
  const selNode = sel ? byId.get(sel) : null;
  return (
    <aside className="g-drawer" aria-label="가게 능력치">
      <header className="g-drawer-head">
        <div>
          <h2>가게 능력치</h2>
          <p>{scenarioLabel} 기준. 숫자는 시뮬레이션 중앙값이고, 엑셀 추정은 워크북 손익표 값입니다.</p>
        </div>
        <button className="g-icon-btn" onClick={onClose} aria-label="능력치 닫기">닫기</button>
      </header>
      {selNode && (
        <div className="g-affects">
          <p>선택한 요인 <b>{selNode.ko}</b>. {affected.size ? `영향을 받는 항목 ${affected.size}개` : "다른 항목에 직접 연결된 화살표가 없습니다"}</p>
          {affected.size > 0 && <p className="g-affects-list">{[...affected].map((id) => byId.get(id)?.ko).filter(Boolean).join(", ")}</p>}
        </div>
      )}
      <ul className="g-tree">{root && render(root, 0)}</ul>
      <p className="g-tree-group">성공 지표</p>
      <p className="g-tree-note">생존기간과 24개월 내 폐업은 인허가 데이터로 본 상권 수준의 성공 기준입니다. 이 매장 시뮬레이션은 계산하지 않으므로 영향 목록에 넣지 않았습니다.</p>
      <ul className="g-tree">{labels.map((l) => render(l, 0))}</ul>
    </aside>
  );
}
