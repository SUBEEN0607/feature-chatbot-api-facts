// Building blocks shared by the three dashboard directions. Each direction styles them with its own CSS.
import { useMemo, useState } from "react";
import { buildTables, COUNTER, DOOR_OUT, ROOM, queueSpot } from "../replay/layout";
import { SHOCK_IF, useData, type Band, type District, type Hero, type KpiFile, type OntNode, type Ontology, type Shocks } from "../data";

export function useDashboard(shockId: string) {
  return {
    hero: useData<Hero>("hero.json"),
    ontology: useData<Ontology>("ontology.json"),
    shocks: useData<Shocks>("shocks.json"),
    kpis: useData<KpiFile>(`kpis/${shockId}.json`),
    district: useData<District>("district.json"),
  };
}

export const DRIVER_KO: Record<string, string> = { COGS: "원가", "수요(비)": "날씨" };
export const SHOCK_ORDER = ["SH01", "SH02", "SH03", "SH04", "SH05", "SH06", "SH07", "SH08", "SH09", "SH10", "SH10b", "SH11"];

// One sentence that states the shock's effect on monthly operating profit (p50, base vs shock).
export function headline(k: KpiFile) {
  const a = k.base.op.p50, b = k.shocked.op.p50;
  const m = (v: number) => `${v < 0 ? "적자 " : ""}${Math.round(Math.abs(v) / 10000).toLocaleString("ko-KR")}만원`;
  const cond = SHOCK_IF[k.shock.id] ?? k.shock.id;
  if (Math.abs(b - a) < 5000) return `${cond}, 한 달 영업이익은 ${m(a)}에서 거의 변하지 않습니다`;
  return `${cond}, 한 달 영업이익은 ${m(a)}에서 ${m(b)}으로 ${b < a ? "줄어듭니다" : "늘어납니다"}`;
}

export const CONF_KO: Record<string, string> = { H: "높음", M: "보통", L: "낮음" };

export const METHOD_KO: Record<string, string> = {
  public: "공공데이터",
  guesstimate: "추정",
  interview_later: "인터뷰 예정",
  derived: "계산",
};

// p10 to p90 of the base month and the shocked month on one shared scale, p50 as a tick.
export function RangeBar({ base, shock, className = "rb" }: { base: Band; shock?: Band; className?: string }) {
  const lo = Math.min(base.p10, shock?.p10 ?? base.p10);
  const hi = Math.max(base.p90, shock?.p90 ?? base.p90);
  const pad = (hi - lo) * 0.08 || Math.abs(hi) * 0.05 || 1;
  const x = (v: number) => ((v - (lo - pad)) / (hi - lo + 2 * pad)) * 100;
  const row = (b: Band, cls: string, y: number) => (
    <g className={cls}>
      <rect x={x(b.p10)} y={y} width={Math.max(0.6, x(b.p90) - x(b.p10))} height="4" />
      <rect x={x(b.p50) - 0.4} y={y - 3} width="0.8" height="10" />
    </g>
  );
  return (
    <svg className={className} viewBox="0 0 100 20" preserveAspectRatio="none" width="100%" height="20" role="img"
      aria-label="평소와 충격 후의 10~90 백분위 범위">
      {row(base, "rb-base", shock ? 3 : 8)}
      {shock && row(shock, "rb-shock", 13)}
    </svg>
  );
}

// Top view of the hero store, drawn from the same layout as the 3D replay.
export function FloorPlan({ hero, className = "fp" }: { hero: Hero; className?: string }) {
  const tables = useMemo(() => buildTables(hero), [hero]);
  const vb = { x: -9, y: -5.2, w: 18, h: 13.4 };
  return (
    <svg className={className} viewBox={`${vb.x} ${vb.y} ${vb.w} ${vb.h}`} role="img"
      aria-label={`매장 평면도: 실내 4인 테이블 ${hero.tables}개, 야장 테이블 ${hero.terrace_tables}개`}>
      <rect className="fp-street" x={vb.x} y={7.9} width={vb.w} height={vb.h} />
      <rect className="fp-walk" x={vb.x} y={ROOM.z1} width={vb.w} height={7.9 - ROOM.z1} />
      <rect className="fp-room" x={ROOM.x0} y={ROOM.z0} width={ROOM.x1 - ROOM.x0} height={ROOM.z1 - ROOM.z0} />
      <line className="fp-glass" x1={ROOM.x0} y1={ROOM.z1} x2={-0.8} y2={ROOM.z1} />
      <line className="fp-glass" x1={0.8} y1={ROOM.z1} x2={ROOM.x1} y2={ROOM.z1} />
      <rect className="fp-counter" x={COUNTER[0] - 1.8} y={COUNTER[1] - 0.35} width={3.6} height={0.7} rx={0.08} />
      <rect className="fp-fridge" x={4.15} y={ROOM.z0 + 0.05} width={1.7} height={0.6} rx={0.06} />
      {tables.map((t) => (
        <g key={t.id} className={t.terrace ? "fp-t fp-terrace" : "fp-t"}>
          {t.seats.map(([sx, sz], i) => (
            <circle key={i} className="fp-stool" cx={sx} cy={sz + (sz > t.z ? 0.12 : -0.12)} r={0.18} />
          ))}
          <rect className="fp-top" x={t.x - 0.65} y={t.z - 0.4} width={1.3} height={0.8} rx={0.08} />
          <circle className="fp-grill" cx={t.x} cy={t.z} r={0.22} />
        </g>
      ))}
      {Array.from({ length: 4 }, (_, i) => queueSpot(i)).map(([qx, qz], i) => (
        <circle key={i} className="fp-queue" cx={qx} cy={qz} r={0.16} />
      ))}
      <path className="fp-door" d={`M -0.8 ${ROOM.z1} A 0.8 0.8 0 0 1 0 ${DOOR_OUT[1] - 0.1}`} />
      <text className="fp-label" x={COUNTER[0]} y={COUNTER[1] + 0.08}>계산대</text>
      <text className="fp-label" x={5} y={ROOM.z0 + 1.15}>소주 냉장고</text>
      <text className="fp-label" x={-4.1} y={5.25}>대기 줄</text>
      <text className="fp-label" x={4.55} y={6.55}>야장</text>
    </svg>
  );
}

function children(nodes: OntNode[], parent: string | null) {
  return nodes.filter((n) => n.parent === parent);
}

function valueText(n: OntNode) {
  if (n.base == null) return n.method === "derived" ? "" : "값 없음";
  if (typeof n.base === "number") {
    const v = Math.abs(n.base) >= 1000 ? Math.round(n.base).toLocaleString("ko-KR") : String(Number(n.base.toFixed(3)));
    return `${v} ${n.unit}`;
  }
  return String(n.base);
}

// Driver tree: 영업이익 at the root; each driver lists the criteria that move it.
export function OntologyTree({ ontology, className = "ot", open: initiallyOpen = ["drv_operating_profit", "drv_revenue", "drv_total_cost"], showValues = true }: {
  ontology: Ontology; className?: string; open?: string[]; showValues?: boolean;
}) {
  const [open, setOpen] = useState<Set<string>>(new Set(initiallyOpen));
  const toggle = (id: string) => setOpen((s) => {
    const n = new Set(s);
    if (n.has(id)) n.delete(id);
    else n.add(id);
    return n;
  });
  const render = (n: OntNode, depth: number): React.ReactNode => {
    const kids = children(ontology.nodes, n.id);
    const isOpen = open.has(n.id);
    return (
      <li key={n.id} className={n.id.startsWith("drv_") ? "ot-driver" : "ot-leaf"}>
        <div className="ot-row" style={{ paddingInlineStart: depth * 14 }}>
          {kids.length ? (
            <button className="ot-toggle" aria-expanded={isOpen} onClick={() => toggle(n.id)}>
              <span className="ot-caret" aria-hidden="true" />
              <span className="ot-name">{n.ko}</span>
              <span className="ot-count">{kids.length}</span>
            </button>
          ) : (
            <span className="ot-name ot-plain">{n.ko}</span>
          )}
          {showValues && <span className="ot-val">{valueText(n)}</span>}
          <span className="ot-method">{METHOD_KO[n.method] ?? n.method}</span>
        </div>
        {kids.length > 0 && isOpen && <ul>{kids.map((k) => render(k, depth + 1))}</ul>}
      </li>
    );
  };
  const root = ontology.nodes.find((n) => n.id === "drv_operating_profit");
  const labels = ontology.nodes.filter((n) => n.id.startsWith("lbl_"));
  return (
    <div className={className}>
      <ul className="ot-tree">{root && render(root, 0)}</ul>
      <p className="ot-group">성공 지표</p>
      <ul className="ot-tree">{labels.map((l) => render(l, 0))}</ul>
    </div>
  );
}

// 대학로 상권 map from the public boundary + store list. The hero marker is symbolic: the store is a composite.
export function DistrictMap({ district, className = "dm", competitor = false, heroLabel }: { district: District; className?: string; competitor?: boolean; heroLabel?: string }) {
  const { polys, pts, center, w, h } = useMemo(() => {
    const rings: { code: string; ring: [number, number][] }[] = [];
    for (const a of district.areas) {
      const g = a.geometry;
      const coords = g.type === "Polygon" ? [g.coordinates as [number, number][][]] : (g.coordinates as [number, number][][][]);
      for (const poly of coords) rings.push({ code: a.code, ring: poly[0] });
    }
    const all = [...rings.flatMap((r) => r.ring), ...district.stores.map((s) => [s.lon, s.lat] as [number, number])];
    const lat0 = all.reduce((s, p) => s + p[1], 0) / all.length;
    const k = Math.cos((lat0 * Math.PI) / 180);
    const xs = all.map((p) => p[0] * k);
    const ys = all.map((p) => p[1]);
    const minX = Math.min(...xs), maxX = Math.max(...xs), minY = Math.min(...ys), maxY = Math.max(...ys);
    const W = 1000;
    const scale = W / (maxX - minX);
    const H = (maxY - minY) * scale;
    const pad = 40;
    const proj = (p: [number, number]): [number, number] => [pad + (p[0] * k - minX) * scale, pad + (maxY - p[1]) * scale];
    const main = rings.filter((r) => r.code === "3120012").sort((a, b) => b.ring.length - a.ring.length)[0];
    const c = main.ring.reduce((s, p) => [s[0] + p[0] / main.ring.length, s[1] + p[1] / main.ring.length], [0, 0]) as [number, number];
    return {
      polys: rings.map((r) => ({ code: r.code, d: "M" + r.ring.map((p) => proj(p).map((v) => v.toFixed(1)).join(" ")).join("L") + "Z" })),
      pts: district.stores.map((s) => ({ ...s, xy: proj([s.lon, s.lat]) })),
      center: proj(c),
      w: W + pad * 2,
      h: H + pad * 2,
    };
  }, [district]);
  return (
    <svg className={className} viewBox={`0 0 ${w} ${h}`} role="img"
      aria-label={`대학로 상권 지도: 돼지고기 구이집 ${district.profile.pork_stores}곳`}>
      {polys.map((p, i) => <path key={i} className={p.code === "3120012" ? "dm-main" : "dm-fringe"} d={p.d} />)}
      {pts.filter((s) => s.role === "context").map((s, i) => <circle key={`c${i}`} className="dm-hansik" cx={s.xy[0]} cy={s.xy[1]} r={4} />)}
      {pts.filter((s) => s.role === "comparison").map((s, i) => <circle key={`m${i}`} className="dm-other" cx={s.xy[0]} cy={s.xy[1]} r={5.5} />)}
      {pts.filter((s) => s.role === "primary").map((s, i) => <circle key={`p${i}`} className="dm-pork" cx={s.xy[0]} cy={s.xy[1]} r={6.5} />)}
      {competitor && <circle className="dm-rival" cx={center[0] + 38} cy={center[1] - 26} r={10} />}
      <circle className="dm-hero-ring" cx={center[0]} cy={center[1]} r={22} />
      <circle className="dm-hero" cx={center[0]} cy={center[1]} r={9} />
      {heroLabel && (
        <text className="dm-hero-label" x={center[0] + 30} y={center[1] + 6}>{heroLabel}</text>
      )}
    </svg>
  );
}
