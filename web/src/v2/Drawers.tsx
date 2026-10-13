// Right-hand drawers: ask the owner or a reviewer, 트윈 인터뷰 (survey), the district layer, the 능력치 tree.
import { useEffect, useRef, useState } from "react";
import type { District } from "../data";
import { DistrictMap } from "../shared/components";
import { api, guided } from "./api";
import { man, manSigned, num, pct } from "./format";
import { REASON_KO, SEGMENT_KO, type SeasonMeta, type SurvivalTable } from "./meta";
import { Tag } from "./parts";
import type { Citation, MonthResult, Plan, Review, Survey } from "./types";

export function Drawer({ title, sub, onClose, children, testid }: { title: string; sub?: string; onClose: () => void; children: React.ReactNode; testid?: string }) {
  useEffect(() => {
    const k = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    addEventListener("keydown", k);
    return () => removeEventListener("keydown", k);
  }, [onClose]);
  return (
    <aside className="v2-drawer" role="dialog" aria-label={title} data-testid={testid}>
      <div className="v2-sheet-head" style={{ paddingBlockEnd: 8 }}>
        <div><h2 style={{ fontSize: 18 }}>{title}</h2>{sub && <p>{sub}</p>}</div>
        <button className="v2-close" onClick={onClose} aria-label="닫기">×</button>
      </div>
      <div className="v2-scroll">{children}</div>
    </aside>
  );
}

// --- ask -------------------------------------------------------------------------------------------------
const OWNER_CHIPS = ["이번 달 장사 어떻게 보세요?", "가격을 올리면 단골이 빠질까요?", "알바를 더 뽑아야 할까요?", "제일 부담되는 비용이 뭐예요?"];
const REVIEW_CHIPS = ["얼마나 기다리셨어요?", "가격은 어땠어요?", "고기는 어땠어요?", "직원 서비스는요?", "다시 오실 거예요?"];

function offlineReviewer(r: Review, q: string, plan?: Plan): string {
  const seg = SEGMENT_KO[r.segment] ?? "손님";
  const c = new Set(r.reason_codes);
  const who = `${seg}로 ${r.party_size ?? ""}명이 왔던 손님이에요.`.replace("  ", " ");
  if (/기다|대기|줄/.test(q)) return `${who} 그날 ${Math.round(r.wait_min ?? 0)}분 기다렸어요. ${c.has("wait_long") ? "솔직히 너무 길었어요." : "그 정도면 참을 만했어요."}`;
  if (/가격|비싸|얼마/.test(q)) return `${who} 1인분 ${plan ? plan.meat_price.toLocaleString("ko-KR") + "원" : "가격"}이었는데 ${c.has("price_high") ? "저희한테는 비싸게 느껴졌어요." : "그 정도면 괜찮았어요."}`;
  if (/고기|맛|품질/.test(q)) return `${who} ${c.has("meat_good") ? "고기는 정말 좋았어요." : c.has("meat_bad") ? "고기는 좀 아쉬웠어요." : "고기는 무난했어요."}`;
  if (/직원|서비스|친절|구워/.test(q)) return `${who} ${c.has("staff_grill") ? "직원분이 구워 주셔서 편했어요." : c.has("understaffed") || c.has("service_slow") ? "직원 부르기가 좀 힘들었어요." : "서비스는 보통이었어요."}`;
  return `${who} 별점은 ${r.stars}점 줬어요. ${r.stars >= 4 ? "다시 올 거예요." : "다시 올지는 잘 모르겠어요."}`;
}

function offlineOwner(q: string, last: MonthResult | null): string {
  if (!last) return "아직 정산한 달이 없어서 숫자로 말씀드리기 어려워요. 한 달 운영해 보고 다시 물어봐 주세요.";
  const k = last.draw.kpis;
  const big = [...last.waterfall].filter((w) => w.kind === "step").sort((a, b) => Math.abs(b.delta) - Math.abs(a.delta))[0];
  if (/비용|부담/.test(q)) return `인건비가 한 달 ${man(k.labor)}, 임차료 ${man(k.rent)}, 식재료비 ${man(k.cogs)}예요. 대학로 임대료가 전국 평균의 세 배 가까이 돼요.`;
  if (/알바|뽑/.test(q)) return `지금 교대당 ${last.plan.staff_per_shift}명이에요. 직원 피로가 ${Math.round(last.state_after.fatigue)}이라 ${last.state_after.fatigue >= 60 ? "한 명 더 쓰는 게 맞을 것 같아요." : "아직은 버틸 만해요."}`;
  if (/가격|단골/.test(q)) return `1인분 ${last.plan.meat_price.toLocaleString("ko-KR")}원 받고 있어요. 단골 비율이 ${pct(last.state_after.regular_share)}인데, 가격이나 고기를 바꾸면 조금씩 빠져요.`;
  return `${last.calendar.label}은 영업이익 ${man(k.op)}였어요. 평소와 비교하면 ${big ? `${big.driver} 쪽에서 ${manSigned(big.delta)}` : "큰 차이는 없었어요"}.`;
}

export function AskDrawer({ who, seasonId, last, onClose }: { who: "owner" | Review; seasonId: string | null; last: MonthResult | null; onClose: () => void }) {
  const [msgs, setMsgs] = useState<{ me: boolean; text: string; src?: string; backend?: string; cites?: Citation[] }[]>([]);
  const [busy, setBusy] = useState(false);
  const [text, setText] = useState("");
  const end = useRef<HTMLDivElement>(null);
  const isOwner = who === "owner";
  const review = isOwner ? null : who;
  useEffect(() => { end.current?.scrollIntoView({ block: "end" }); }, [msgs]); // scrollIntoView may return a Promise in new Chromium
  async function ask(q: string) {
    if (!q.trim() || busy) return;
    setMsgs((m) => [...m, { me: true, text: q }]);
    setText("");
    setBusy(true);
    try {
      if (!seasonId) throw new Error("offline");
      const a = await api.ask(seasonId, isOwner ? "owner" : review!.id, q);
      const practice = /mock|template/.test(a.backend ?? "");
      const src = a.numbers_from?.length ? `숫자 출처: ${a.numbers_from.join(", ")}${practice ? " (연습 응답)" : ""}` : practice ? "연습 응답: 언어 모델 없이 기록된 사실로 만든 문장" : undefined;
      setMsgs((m) => [...m, { me: false, text: a.answer, src, backend: a.backend ?? "api", cites: a.citations }]);
    } catch {
      const t = isOwner ? offlineOwner(q, last) : offlineReviewer(review!, q, last?.plan);
      setMsgs((m) => [...m, { me: false, text: t, src: "오프라인 답변: 기록된 숫자로 만든 문장입니다", backend: "offline" }]);
    } finally {
      setBusy(false);
    }
  }
  const title = isOwner ? "사장님에게 묻기" : `${SEGMENT_KO[review!.segment]} 손님에게 묻기`;
  const sub = isOwner ? "가게의 지금 상태와 근거 자료로 답합니다" : `별 ${review!.stars}개, ${(review!.shown_codes ?? review!.reason_codes).map((c) => REASON_KO[c] ?? c).join(", ") || "특별한 이유 없음"}`;
  return (
    <Drawer title={title} sub={sub} onClose={onClose} testid="ask-panel">
      <div className="v2-msgs" aria-live="polite">
        {!isOwner && review!.text && <div className="v2-msg them">{review!.text}</div>}
        {msgs.map((m, i) => (
          <div key={i} className={`v2-msg ${m.me ? "me" : "them"}`} data-role={m.me ? "me" : "answer"} data-testid={m.me ? undefined : "ask-answer"}
            data-who={m.me ? undefined : isOwner ? "owner" : review!.id} data-backend={m.backend}>{m.text}{m.src && <span className="src">{m.src}</span>}
            {m.cites?.length ? (
              <span className="src v2-cites" data-testid="ask-cites">근거 자료
                {m.cites.map((c) => <span key={c.label} className="v2-cite" data-cite={c.label}><b>{c.label}</b> {c.title}</span>)}
              </span>
            ) : null}</div>
        ))}
        {busy && <div className="v2-msg them">답을 쓰는 중입니다</div>}
        <div ref={end} />
      </div>
      <div className="v2-chips" style={{ marginBlock: 8 }}>
        {(isOwner ? OWNER_CHIPS : REVIEW_CHIPS).map((c) => <button key={c} onClick={() => ask(c)} disabled={busy}>{c}</button>)}
      </div>
      <form className="v2-ask-form" onSubmit={(e) => { e.preventDefault(); ask(text); }}>
        <input value={text} onChange={(e) => setText(e.target.value)} placeholder="직접 물어보기" aria-label="질문" maxLength={200} />
        <button className="v2-btn primary" disabled={busy || !text.trim()}>보내기</button>
      </form>
    </Drawer>
  );
}

// 트윈 인터뷰 근거 line in Korean: agents/persona.py survey() `used` keys and sources mapped to labels; anything without
// a label (a new key, an English method note, an action id) is left out rather than shown raw
const USED_KO: Record<string, string> = {
  sto_franchise: "가게 형태", months_played: "운영한 달", sto_open_days: "한 달 영업일", drv_open_hours: "하루 영업시간",
  "plan.close_hour": "마감 시각", "month covers": "달별 손님 수", mkt_party_size: "한 팀 평균 인원", "review segments": "리뷰 손님 구성",
  reg_age_mix: "20대 매출 비중", mkt_patience: "손님이 기다리는 시간(분)", "minutes as said (rounded to 5)": "말로 한 분 (5분 단위)",
  "review wait_min": "리뷰 손님 대기(분)", "month walkaways": "달별 돌아간 팀", "calendar demand_index": "달별 수요 지수",
  "percent as said (rounded to 5)": "말로 한 비율 (5% 단위)", "plan.meat_price": "삼겹살 1인분 가격", prd_portion_grams: "1인분 무게(g)",
  "plan.soju_price": "소주 가격", prd_alcohol_per_cover: "1인당 소주(병)", sto_tables: "테이블 수", sto_seats_per_table: "테이블당 좌석",
  sto_area_pyeong: "매장 평수", "plan.staff_per_shift": "교대당 알바", sto_parttime_wage: "알바 시급", "state.fatigue": "직원 피로",
  cst_meat_cost_per_portion: "1인분 고기 원가", "plan.meat_grade": "원육", "won as said (rounded)": "말로 한 금액 (반올림)", drv_rent: "월 임대료",
  band: "임대료 구간 카드", cst_card_share: "카드 결제 비중", "card payers per 10 customers": "열 명 중 카드 손님",
  "owner decide (confidence-gated rule pick)": "사장님 대응 규칙", "state.cash": "현금",
};
const SOURCE_KO: Record<string, string> = {
  "season state": "시즌 상태", "season state (가정)": "시즌 상태, 가정", "season plan": "운영 계획", "season month results": "시즌 월별 결과",
  "season reviews": "시즌 리뷰", "season calendar (가정 unless sourced)": "시즌 달력, 출처 없으면 가정", "계산": "계산", "가정": "가정",
  "guide Q22 card": "인터뷰 가이드 Q22 카드", "계산 (cst_card_share × 10)": "계산, 카드 비중 × 10", "web/public/runs + agents.owner": "미리 계산한 대응 결과",
};
const VALUE_KO: Record<string, string> = {
  patience: "참는 시간", longest_wait: "가장 긴 대기", vacation_drop_pct: "방학 감소", peak_up_pct: "최고 달 증가",
  twenties: "20대", office: "직장인", family: "가족", imported: "수입 냉동", domestic: "국내산", aged: "숙성",
};
const isId = (s: string) => /^[A-Z]{1,3}\d+$/.test(s); // source, decision and shock ids (S20, D0930, SH03) are shown as ids
const latin = (s: string) => /[A-Za-z]/.test(s);

function usedValue(v: unknown): string {
  if (v == null) return "";
  if (Array.isArray(v)) return v.length <= 6 ? v.map((x) => usedValue(x)).filter(Boolean).join("/") : `${v.length}개 값`;
  if (typeof v === "object") {
    return Object.entries(v as Record<string, unknown>).map(([k, x]) => {
      const key = VALUE_KO[k] ?? (latin(k) && !isId(k) ? null : k);
      const val = usedValue(x);
      return key && val ? `${key} ${val}` : "";
    }).filter(Boolean).join(", ");
  }
  if (typeof v === "number") return v.toLocaleString("ko-KR", { maximumFractionDigits: 2 });
  const s = String(v);
  return VALUE_KO[s] ?? (latin(s) && !isId(s) ? "" : s);
}

function usedSource(src: string): string | null {
  if (SOURCE_KO[src]) return SOURCE_KO[src];
  const ids = src.split(/[;,]/).map((x) => x.trim()).filter(Boolean);
  if (ids.length && ids.every(isId)) return `출처 ${ids.join(", ")}`;
  return latin(src) ? null : src;
}

export function usedLine(u: { key: string; value: unknown; source: string }): string | null {
  const label = USED_KO[u.key];
  if (!label) return null;
  const v = usedValue(u.value), src = usedSource(u.source);
  return `${label}${v ? ` ${v}` : ""}${src ? ` (${src})` : ""}`;
}

// --- 트윈 인터뷰 -------------------------------------------------------------------------------------------
export function InterviewDrawer({ seasonId, onClose }: { seasonId: string | null; onClose: () => void }) {
  const [s, setS] = useState<Survey | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    let live = true;
    const go = seasonId ? api.survey(seasonId) : guided<Survey>("survey.json");
    go.then((x) => live && setS(x)).catch(() => live && setErr(seasonId ? "API에서 설문 답을 받지 못했습니다." : "시연 모드용 설문 답 파일이 아직 없습니다. 자유 플레이에서 API로 답을 받습니다."));
    return () => { live = false; };
  }, [seasonId]);
  return (
    <Drawer title="트윈 인터뷰" sub="소상공인 설문 15문항에 사장님 트윈이 지금 상태로 답합니다. 실제 사장님 인터뷰와 같은 문항이라 한 줄씩 비교할 수 있습니다." onClose={onClose} testid="interview">
      {err && <p className="v2-note">{err}</p>}
      {!s && !err && <p className="v2-note">답을 불러오는 중입니다</p>}
      <ol style={{ margin: 0, paddingInlineStart: 18, display: "grid", gap: 14 }}>
        {s?.items.map((it) => {
          const basis = it.used.map(usedLine).filter((x): x is string => Boolean(x));
          return (
            <li key={it.guide_q} data-q={it.guide_q} data-testid="survey-item">
              <p style={{ fontWeight: 700 }}>{it.guide_q}번. {it.question}</p>
              <p style={{ marginBlockStart: 2 }} data-testid="survey-answer">{it.answer}</p>
              {basis.length > 0 && <p className="v2-note" data-testid="survey-basis">근거: {basis.join(", ")}</p>}
            </li>
          );
        })}
      </ol>
    </Drawer>
  );
}

// --- district layer ----------------------------------------------------------------------------------------
function Survival({ series }: { series: { name: string; t: SurvivalTable; color: string }[] }) {
  const W = 440, H = 170, pl = 30, pb = 22, pt = 8, pr = 8;
  const maxM = 120;
  const x = (m: number) => pl + (m / maxM) * (W - pl - pr);
  const y = (s: number) => pt + (1 - (s - 0.4) / 0.6) * (H - pt - pb);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label="생존 곡선">
      {[0.4, 0.6, 0.8, 1].map((s) => <g key={s}><line x1={pl} x2={W - pr} y1={y(s)} y2={y(s)} stroke="oklch(0.9 0.005 240)" /><text x={pl - 4} y={y(s) + 3} fontSize="9" textAnchor="end" fill="oklch(0.54 0.012 255)">{Math.round(s * 100)}%</text></g>)}
      {[0, 24, 60, 120].map((m) => <text key={m} x={x(m)} y={H - 6} fontSize="9" textAnchor="middle" fill="oklch(0.54 0.012 255)">{m}개월</text>)}
      {series.map((s) => {
        const pts = [{ month: 0, survival: 1 }, ...s.t.table];
        const d = pts.map((p, i) => `${i ? "L" : "M"}${x(p.month).toFixed(1)},${y(p.survival).toFixed(1)}`).join("");
        return <path key={s.name} d={d} fill="none" stroke={s.color} strokeWidth="2" />;
      })}
    </svg>
  );
}

export function DistrictDrawer({ district, meta, competitor, onClose }: { district: District | null; meta: SeasonMeta | null; competitor: boolean; onClose: () => void }) {
  const rent = meta?.district.rent;
  const sv = meta?.district.survival;
  const series = [
    sv?.wide_pork_name_only && { name: "고깃집 (이름 기준)", t: sv.wide_pork_name_only, color: "oklch(0.57 0.17 33)" },
    sv?.wide_hansik_all && { name: "한식 전체", t: sv.wide_hansik_all, color: "oklch(0.42 0.014 255)" },
  ].filter(Boolean) as { name: string; t: SurvivalTable; color: string }[];
  const maxRent = rent ? Math.max(rent.hyehwa_per_m2, rent.seoul_per_m2, rent.national_per_m2) : 1;
  return (
    <Drawer title="대학로 상권" sub="혜화역 상권 3120012, 우리 가게는 가운데 검은 점" onClose={onClose} testid="district">
      {district && <DistrictMap district={district} competitor={competitor} heroLabel="대학로 삼겹살" />}
      <p className="v2-note">빨간 점 = 돼지고기 구이집 {district?.profile.pork_stores ?? ""}곳, 회색 = 다른 한식. 소상공인시장진흥공단 상가정보.</p>
      {rent && (
        <div style={{ display: "grid", gap: 6, marginBlockStart: 16 }}>
          <h3 style={{ fontSize: 14, display: "flex", gap: 8, alignItems: "center" }}>임대료 (1층 소규모 상가, ㎡당 월) <Tag tag={rent.source_ids.join(";")} title="임대료 비교" note="한국부동산원 상업용부동산 임대동향 2026년 2분기" meta={meta} /></h3>
          {([["혜화동", rent.hyehwa_per_m2], ["서울", rent.seoul_per_m2], ["전국", rent.national_per_m2]] as const).map(([n, v]) => (
            <div key={n} style={{ display: "grid", gridTemplateColumns: "56px 1fr 80px", gap: 8, alignItems: "center", fontSize: 13 }}>
              <span>{n}</span>
              <span style={{ blockSize: 12, background: "var(--sunk)", borderRadius: 3 }}><i style={{ display: "block", blockSize: "100%", inlineSize: `${(v / maxRent) * 100}%`, background: n === "혜화동" ? "var(--ink)" : "oklch(0.7 0.01 255)", borderRadius: 3 }} /></span>
              <span className="num" style={{ textAlign: "end" }}>{num(v)}원</span>
            </div>
          ))}
          <p className="v2-note">혜화동은 전국의 {(rent.hyehwa_per_m2 / rent.national_per_m2).toFixed(1)}배입니다. 전국 평균 비용 비중을 이 상권에 그대로 쓰면 안 되는 이유입니다.</p>
        </div>
      )}
      {series.length > 0 && (
        <div style={{ display: "grid", gap: 6, marginBlockStart: 16 }}>
          <h3 style={{ fontSize: 14 }}>문 연 뒤 살아남는 비율</h3>
          <Survival series={series} />
          <div className="v2-chips">{series.map((s) => <span key={s.name} className="v2-chip"><i className="v2-seg-dot" style={{ background: s.color, marginInlineEnd: 6 }} />{s.name} {s.t.n}곳</span>)}</div>
          <p className="v2-note">{sv?.areas?.join(", ")} 인허가 자료, {sv?.cohort}. 대학로만으로는 폐업 수가 적어 범위를 넓혔습니다. 게임의 폐업 규칙(현금 두 달 연속 0 아래)은 이 생존 라벨에 맞춘 것입니다.</p>
        </div>
      )}
    </Drawer>
  );
}

// --- 능력치 tree -----------------------------------------------------------------------------------------
const DF_KO: Record<string, string> = { calendar: "달력 (계절)", rating: "평점", awareness: "인지도", regulars: "단골", competitor: "경쟁점", events: "사건", hours: "영업시간", menu: "메뉴" };

export function TreeDrawer({ r, onClose }: { r: MonthResult | null; onClose: () => void }) {
  if (!r) {
    return <Drawer title="가게 능력치" onClose={onClose} testid="tree"><p className="v2-note">한 달을 운영하면 이번 달 영업이익을 만든 요인이 여기에 나무로 표시됩니다.</p></Drawer>;
  }
  const k = r.draw.kpis;
  const step = (key: string) => r.waterfall.find((w) => w.key === key)?.delta ?? 0;
  const node = (label: string, value: string, depth: number, delta?: number, key?: string) => {
    const moved = delta != null && Math.abs(delta) >= 50000;
    return (
      <div key={label} className={`v2-node ${moved ? `moved ${delta! > 0 ? "up" : "down"}` : ""}`} data-depth={depth} data-node={key}>
        <span>{label}{moved && <b className={delta! > 0 ? "up" : "down"} style={{ marginInlineStart: 8, fontSize: 12 }}>{manSigned(delta!)}</b>}</span>
        <span className="v">{value}</span>
      </div>
    );
  };
  const df = r.demand_factors ?? {};
  return (
    <Drawer title="가게 능력치" sub={`${r.calendar.label}: 평소보다 크게 움직인 요인을 색으로 표시합니다`} onClose={onClose} testid="tree">
      <div className="v2-tree">
        {node("영업이익", man(k.op), 0, k.op - (r.waterfall.find((w) => w.kind === "start")?.delta ?? k.op), "op")}
        {node("매출", man(k.revenue), 1, step("covers") + step("ticket") + step("extra_revenue"), "revenue")}
        {node("손님 수", `${num(k.covers)}명`, 2, step("covers"), "covers")}
        {node("객단가", `${num(k.ticket)}원`, 2, step("ticket"), "ticket")}
        {node("점심·단체 매출", man((k.lunch_revenue ?? 0) + (k.group_revenue ?? 0)), 2, step("extra_revenue"), "extra")}
        {node("식재료비", man(k.cogs), 1, step("cogs"), "cogs")}
        {node("인건비", man(k.labor), 1, step("labor"), "labor")}
        {node("임차료", man(k.rent), 1, step("rent"), "rent")}
        {node("관리비·마케팅", man(k.mgmt), 1, step("mgmt"), "mgmt")}
        {node("카드 수수료", man(k.fees), 1, step("fees"), "fees")}
      </div>
      <h3 style={{ fontSize: 14, marginBlock: "16px 6px" }}>손님 수를 움직인 배수</h3>
      <div className="v2-tree">
        {Object.entries(df).map(([key, v]) => (
          <div key={key} className={`v2-node ${Math.abs(v - 1) >= 0.02 ? `moved ${v > 1 ? "up" : "down"}` : ""}`} data-node={`df-${key}`}>
            <span>{DF_KO[key] ?? key}</span><span className="v">×{v.toFixed(2)}</span>
          </div>
        ))}
      </div>
    </Drawer>
  );
}
