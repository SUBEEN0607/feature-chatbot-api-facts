// The planning board's levers (docs/GAME-V2-SPEC.md §4). Each lever names its upside and its modelled downside
// and points at the research/season_params.yaml leaf that carries its tag and note (shown by the 가정 chip).
import { leaf, type SeasonMeta } from "./meta";
import type { Plan } from "./types";

export type LeverKind = "slider" | "stepper" | "seg" | "toggle" | "multi";
export type Opt = { value: string | number; label: string };
export type Lever = {
  key: keyof Plan;
  group: string;
  label: string;
  kind: LeverKind;
  min?: number;
  max?: number;
  step?: number;
  options?: Opt[];
  fmt?: (v: number) => string;
  up: string;
  down: string;
  downData?: (meta: SeasonMeta | null) => string | null; // `down` with the sim's own numbers (season.json), when loaded
  tagPaths: string[]; // season_params leaves; the first one with a tag decides the chip
  mechanism?: string; // preview/MonthResult label mechanism that also describes this lever
};

const wonK = (v: number) => `${v.toLocaleString("ko-KR")}원`;
const manK = (v: number) => (v === 0 ? "없음" : `${(v / 10000).toLocaleString("ko-KR")}만원`);
const GRADE_OPTS: Opt[] = [{ value: "imported", label: "수입 냉동" }, { value: "domestic", label: "국내산" }, { value: "aged", label: "숙성" }];

// 원육 원가 per 200g portion from season_params meat_grade.<grade>.cost, the value the sim and its preview label use
function gradeCostDown(meta: SeasonMeta | null): string | null {
  const costs = GRADE_OPTS.map((o) => ({ label: o.label, cost: leaf(meta, `meat_grade.${o.value}`)?.cost }));
  if (costs.some((c) => typeof c.cost !== "number")) return null;
  return `1인분 원가가 오릅니다 (${costs.map((c) => `${c.label} ${wonK(c.cost as number)}`).join(", ")})`;
}

export const LEVERS: Lever[] = [
  { key: "meat_price", group: "가격", label: "삼겹살 1인분", kind: "slider", min: 15000, max: 25000, step: 500, fmt: wonK,
    up: "객단가가 오릅니다", down: "손님 수가 줄고, 기대보다 비싸면 만족이 떨어집니다",
    tagPaths: ["satisfaction.expected_price"], mechanism: "price_elasticity" },
  { key: "soju_price", group: "가격", label: "소주 한 병", kind: "slider", min: 4000, max: 7000, step: 500, fmt: wonK,
    up: "주류 마진이 늘어납니다", down: "1인당 술 주문이 줄고 비싸다는 반응이 나옵니다",
    tagPaths: ["satisfaction.expected_soju", "satisfaction.soju_over_weight"] },
  { key: "meat_grade", group: "품질", label: "원육", kind: "seg",
    options: GRADE_OPTS,
    up: "만족과 리뷰가 좋아지고 비싼 가격을 받아 줍니다", down: "1인분 원가가 오릅니다", downData: gradeCostDown,
    tagPaths: ["meat_grade.aged", "meat_grade.imported", "meat_grade.domestic"], mechanism: "meat_grade" },
  { key: "menu_extras", group: "메뉴", label: "메뉴 추가", kind: "multi",
    options: [{ value: "naengsam", label: "냉삼" }, { value: "tongsam", label: "통삼겹" }, { value: "minari", label: "미나리 곁들임" }],
    up: "인지도와 20대 손님 호감이 오릅니다", down: "원가, 준비 시간, 폐기가 늘어납니다",
    tagPaths: ["menu_extras.minari", "menu_extras.naengsam"] },
  { key: "banchan", group: "메뉴", label: "반찬 가짓수", kind: "stepper", min: 2, max: 10, step: 1, fmt: (v) => `${v}가지`,
    up: "가짓수마다 만족이 조금씩 오릅니다", down: "가짓수마다 1인당 240원이 듭니다",
    tagPaths: ["banchan.satisfaction_per_item", "banchan.cost_per_item"] },
  { key: "staff_grilling", group: "서비스", label: "직원이 구워주기", kind: "toggle",
    up: "만족이 오르고 회식 손님이 더 찾습니다", down: "테이블에 오래 머물러 회전이 느려지고 직원 일이 늘어납니다",
    tagPaths: ["staff_grilling.dwell_factor", "staff_grilling.satisfaction"] },
  { key: "staff_per_shift", group: "인력", label: "교대당 알바 수", kind: "stepper", min: 0, max: 4, step: 1, fmt: (v) => `${v}명`,
    up: "응대가 빨라지고 직원 피로가 줄어듭니다", down: "인건비가 늘어납니다",
    tagPaths: ["staff.attentive_tables_per_server", "staff.table_tasks_min"], mechanism: "fatigue" },
  { key: "close_hour", group: "운영", label: "마감 시간", kind: "seg",
    options: [{ value: 23, label: "23시" }, { value: 24, label: "24시" }, { value: 25, label: "01시" }],
    up: "늦게 닫을수록 손님이 조금 늘어납니다", down: "공과금과 직원 피로가 늘어납니다",
    tagPaths: ["hours.demand", "hours.fatigue_per_late_hour"] },
  { key: "lunch", group: "운영", label: "점심 영업", kind: "toggle",
    up: "점심 손님 매출이 생깁니다", down: "알바 시간, 공과금, 피로가 늘어납니다",
    tagPaths: ["lunch.covers_per_day", "lunch.fatigue"] },
  { key: "terrace", group: "공간", label: "야장", kind: "toggle",
    up: "날씨 좋은 날 자리가 늘어납니다", down: "비 오면 못 쓰고, 소음 민원이 생길 수 있습니다",
    tagPaths: ["terrace.noise_complaint_prob"] },
  { key: "marketing_budget", group: "마케팅", label: "SNS 협찬 예산", kind: "seg",
    options: [0, 500000, 1000000, 2000000, 3000000].map((v) => ({ value: v, label: manK(v) })),
    up: "인지도가 오릅니다", down: "비용이 들고, 기대가 높아져 만족이 떨어질 수 있습니다",
    tagPaths: ["marketing.awareness_per_million", "marketing.expectation_per_million"], mechanism: "awareness" },
  { key: "review_event", group: "마케팅", label: "리뷰 이벤트", kind: "toggle",
    up: "리뷰가 더 많이 쌓입니다", down: "리뷰마다 음료값이 들고, 보상 리뷰라 별점이 들쭉날쭉합니다",
    tagPaths: ["marketing.review_event_prob_mult", "marketing.review_event_star_noise"] },
  { key: "group_reservations", group: "예약", label: "단체·회식 예약", kind: "toggle",
    up: "회식 손님을 미리 잡습니다 (12월에 특히 큼)", down: "예약석이 워크인 손님을 막고, 노쇼 10%가 생깁니다",
    tagPaths: ["groups.noshow", "groups.blocked_tables", "groups.incremental"] },
  { key: "hygiene", group: "위생", label: "청결 관리", kind: "seg",
    options: [{ value: "basic", label: "기본" }, { value: "normal", label: "보통" }, { value: "high", label: "철저" }],
    up: "깔끔하다는 평이 늘고 위생점검을 통과합니다", down: "청소에 드는 근무 시간이 늘어납니다",
    tagPaths: ["hygiene.high", "hygiene.basic"] },
];

export const GROUPS = [...new Set(LEVERS.map((l) => l.group))];

export function changedKeys(a: Plan, b: Plan): (keyof Plan)[] {
  return (Object.keys(a) as (keyof Plan)[]).filter((k) => JSON.stringify(a[k]) !== JSON.stringify(b[k]));
}

export const leverDown = (l: Lever, meta: SeasonMeta | null): string => l.downData?.(meta) ?? l.down;

export function leverValueLabel(l: Lever, v: Plan[keyof Plan]): string {
  if (l.kind === "toggle") return v ? "켬" : "끔";
  if (l.kind === "multi") {
    const arr = v as string[];
    return arr.length ? arr.map((x) => l.options?.find((o) => o.value === x)?.label ?? x).join(", ") : "없음";
  }
  if (l.options) return l.options.find((o) => o.value === v)?.label ?? String(v);
  return l.fmt ? l.fmt(v as number) : String(v);
}

// Cause chips (interactivity #4): the sim names levers in Korean in waterfall notes (sim/season.py _LEVER_KO) and
// reviews carry reason codes; both map back to the plan key so a chip can open that lever on next month's board.
const SIM_LEVER_KO: Record<string, keyof Plan> = {
  "삼겹살 가격": "meat_price", "소주 가격": "soju_price", "원육": "meat_grade", "메뉴 추가": "menu_extras", "반찬 수": "banchan",
  "직원이 구워 주기": "staff_grilling", "교대당 알바": "staff_per_shift", "영업시간": "close_hour", "점심 영업": "lunch", "야장": "terrace",
  "SNS 협찬": "marketing_budget", "리뷰 이벤트": "review_event", "단체 예약": "group_reservations", "청결 관리": "hygiene",
};
export function leversInNote(note?: string | null): (keyof Plan)[] {
  if (!note || !note.includes(":")) return [];
  return note.split(":")[1].split(",").map((x) => SIM_LEVER_KO[x.trim()]).filter((k): k is keyof Plan => Boolean(k));
}
export const REASON_LEVER: Record<string, keyof Plan> = {
  price_high: "meat_price", price_good: "meat_price", soju_high: "soju_price", banchan_good: "banchan", banchan_poor: "banchan",
  staff_grill: "staff_grilling", understaffed: "staff_per_shift", tired_staff: "staff_per_shift", service_slow: "staff_per_shift",
  wait_long: "staff_per_shift", crowded: "group_reservations", dirty: "hygiene", clean: "hygiene", menu_fun: "menu_extras",
  meat_good: "meat_grade", meat_bad: "meat_grade", hyped: "marketing_budget", comped: "review_event", reviews_inflated: "review_event",
};
export const leverLabel = (k: keyof Plan) => LEVERS.find((l) => l.key === k)?.label ?? k;
