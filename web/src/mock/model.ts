// Mock model for the pre-founder flow. Not the sim engine: a transparent monthly formula.
// District numbers are real (서울시 상권분석서비스 2025, built by pipelines/build_gu_stats.py into gu_stats.json) except
// rent, which is still a placeholder. Store constants are borrowed from the 대학로 hero store (hero.json pnl) and the
// shock sizes from research/shocks.yaml. Every input and its standing is listed on the #/sources page (sources.ts).

export type Industry = "bbq" | "cafe";
export type Profile = { industry: Industry; gu: string; reasons: string[]; capital: number; age: string }; // capital in 만원
export type Gu = { code: string; name: string; rings: [number, number][][]; c: [number, number]; r: number }; // c: label point, r: room around it
// demand: 점포당 월매출 ÷ 서울 평균. stores: 상권 안 한식음식점 수. closure: 1년 폐업률(%). sales: 점포당 월매출(만원).
// tx: 점포당 하루 결제 건수. ticket: 결제 1건 금액(원). rent: 만원/평·월, 예시값. pork: 구 전체의 돼지고기 구이 가게 수.
// dow: 요일별 매출 비중 (월..일). qidx: 분기별 매출 지수 (1~4분기, 연평균 1).
export type GuStat = { demand: number; stores: number; closure: number; sales: number; tx: number; ticket: number; rent: number; pork: number; opening: number; dow: number[]; qidx: number[] };
type Row = Record<string, number> & { dow_share: number[]; quarter_index: number[] };
type Block = { service_name: string; seoul: Row; gu: Record<string, Row> };
export type GuData = {
  _meta: { generated: string; year: number; quarters: string[]; sources: Record<string, string>; license: string; method: string; caveats: string[] };
  bbq: Block; cafe: Block;
  pork?: { snapshot: string; source: string; codes: Record<string, string>; gu: Record<string, { hansik: number; pork: number; beef: number; tripe: number }> };
};
let DATA: GuData | null = null;
export const setGuData = (d: GuData) => { DATA = d; };
export const guData = () => DATA;

export const DEFAULT_PROFILE: Profile = { industry: "bbq", gu: "마포구", reasons: [], capital: 12000, age: "30대" };

function hash(s: string): number {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) h = Math.imul(h ^ s.charCodeAt(i), 16777619);
  return (h >>> 0) / 4294967296;
}

export function guStat(name: string): GuStat {
  const g = DATA?.bbq.gu[name];
  const rent = Math.round(9 + hash(name + "r") * 20); // placeholder: no rent data is connected
  if (!g) return { demand: 1, stores: 0, closure: 0, sales: 0, tx: 0, ticket: 0, rent, pork: 0, opening: 0, dow: Array(7).fill(1 / 7), qidx: [1, 1, 1, 1] };
  return {
    demand: g.demand_index, stores: g.stores, closure: +(g.closure_rate * 100).toFixed(1), sales: g.sales_per_store_month, tx: g.tx_per_store_day,
    ticket: g.ticket, rent, pork: DATA?.pork?.gu[name]?.pork ?? 0, opening: g.opening_rate, dow: g.dow_share, qidx: g.quarter_index,
  };
}

export const RAMP = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]; // one hue, light to dark

export type Metric = "demand" | "pork" | "closure";
export const METRICS: Record<Metric, { label: string; fmt: (v: number) => string; hint: string }> = {
  demand: { label: "매출 지수", fmt: (v) => v.toFixed(2), hint: "한식음식점 한 곳의 월매출, 서울 평균이 1" },
  pork: { label: "고깃집 수", fmt: (v) => `${v.toLocaleString("ko-KR")}곳`, hint: "돼지고기 구이 가게, 구 전체" },
  closure: { label: "1년 폐업률", fmt: (v) => `${v}%`, hint: "2025년에 문 닫은 한식음식점 비율" },
};

export function rankOf(name: string, metric: Metric, names: string[]): number {
  const v = guStat(name)[metric];
  return names.filter((n) => guStat(n)[metric] > v).length + 1;
}

// 을/를 by the last syllable's 받침 (non-Hangul endings take 를)
export function eul(word: string): string {
  const c = word.charCodeAt(word.length - 1);
  return word + (c >= 0xac00 && c <= 0xd7a3 && (c - 0xac00) % 28 ? "을" : "를");
}

export function iga(word: string): string {
  const c = word.charCodeAt(word.length - 1);
  return word + (c >= 0xac00 && c <= 0xd7a3 && (c - 0xac00) % 28 ? "이" : "가");
}

// ---- money -------------------------------------------------------------------------------------------
export function man(v: number): string {
  const r = Math.round(v);
  const neg = r < 0 ? "−" : "";
  const a = Math.abs(r);
  const eok = Math.floor(a / 10000);
  const rest = a % 10000;
  if (eok && rest) return `${neg}${eok}억 ${rest.toLocaleString("ko-KR")}만원`;
  if (eok) return `${neg}${eok}억원`;
  return `${neg}${a.toLocaleString("ko-KR")}만원`;
}

// ---- store plan (the builder's output) ---------------------------------------------------------------
export type Grade = "basic" | "mid" | "high";
export const GRADES: Record<Grade, { label: string; perPyeong: number; floor: string; wall: string }> = {
  basic: { label: "기본", perPyeong: 150, floor: "#cbb9a0", wall: "#efe6d6" },
  mid: { label: "중급", perPyeong: 220, floor: "#9a8672", wall: "#e4ddd0" },
  high: { label: "고급", perPyeong: 320, floor: "#5b4a3f", wall: "#d8cdbb" },
};

export type CatalogItem = {
  id: string; name: string; cat: "seat" | "equip" | "deco"; price: number; // 만원, 가정
  w: number; d: number; h: number; seats?: number; max?: number; note?: string; fixed?: boolean; // fixed: part of the shell, not in the catalog
};
export const CATALOG: CatalogItem[] = [
  { id: "table4", name: "4인 테이블", cat: "seat", price: 85, w: 1.5, d: 2, h: 0.74, seats: 4, note: "불판, 환기 포함" },
  { id: "table2", name: "2인 테이블", cat: "seat", price: 60, w: 1.5, d: 1, h: 0.74, seats: 2, note: "불판, 환기 포함" },
  { id: "kitchen", name: "주방", cat: "equip", price: 900, w: 4, d: 2.5, h: 2.6, max: 1, fixed: true, note: "벽으로 나눈 방" },
  { id: "counter", name: "계산대와 POS", cat: "equip", price: 150, w: 1.5, d: 1, h: 1.05, max: 1 },
  { id: "kiosk", name: "키오스크", cat: "equip", price: 120, w: 0.5, d: 0.5, h: 1.5 },
  { id: "fridge", name: "주류 냉장고", cat: "equip", price: 180, w: 1, d: 1, h: 1.9 },
  { id: "bench", name: "대기 의자", cat: "deco", price: 12, w: 1.5, d: 0.5, h: 0.45 },
  { id: "plant", name: "화분", cat: "deco", price: 8, w: 0.5, d: 0.5, h: 1.1 },
  { id: "lamp", name: "스탠드 조명", cat: "deco", price: 15, w: 0.5, d: 0.5, h: 1.6 },
];
export const ITEM = Object.fromEntries(CATALOG.map((c) => [c.id, c])) as Record<string, CatalogItem>;

export type Placed = { uid: number; id: string; x: number; z: number; rot: 0 | 1 }; // x,z = centre in metres; rot 1 = quarter turn
export type Store = { pyeong: number; grade: Grade; items: Placed[]; loan: number }; // loan in 만원

export const CELL = 0.5;
export function roomSize(pyeong: number): { w: number; d: number } {
  const area = pyeong * 3.3;
  const w = Math.round(Math.sqrt(area * 1.45) / CELL) * CELL;
  return { w, d: Math.round(area / w / CELL) * CELL };
}
export function footprint(p: { id: string; rot: 0 | 1 }): { w: number; d: number } {
  const it = ITEM[p.id];
  return p.rot ? { w: it.d, d: it.w } : { w: it.w, d: it.d };
}
export function fits(store: Store, cand: { id: string; x: number; z: number; rot: 0 | 1 }, ignore?: number): boolean {
  const { w, d } = roomSize(store.pyeong);
  const f = footprint(cand);
  if (cand.x - f.w / 2 < -w / 2 - 1e-6 || cand.x + f.w / 2 > w / 2 + 1e-6) return false;
  if (cand.z - f.d / 2 < -d / 2 - 1e-6 || cand.z + f.d / 2 > d / 2 + 1e-6) return false;
  return store.items.every((o) => {
    if (o.uid === ignore) return true;
    const g = footprint(o);
    return Math.abs(o.x - cand.x) >= (f.w + g.w) / 2 - 1e-6 || Math.abs(o.z - cand.z) >= (f.d + g.d) / 2 - 1e-6;
  });
}
export function snap(v: number, size: number): number {
  // centre so that the item's edges sit on the grid
  const half = size / 2;
  return Math.round((v - half) / CELL) * CELL + half;
}

// the kitchen is a walled room in the back-left corner; it moves with the walls when the size changes
export function kitchenSpot(pyeong: number): { x: number; z: number } {
  const { w, d } = roomSize(pyeong);
  return { x: -w / 2 + ITEM.kitchen.w / 2, z: -d / 2 + ITEM.kitchen.d / 2 };
}

// Where tables can go: rows from the front wall back, half a metre of aisle around each, clear of the kitchen room.
export function tableSlots(pyeong: number): { x: number; z: number }[] {
  const { w, d } = roomSize(pyeong);
  const k = kitchenSpot(pyeong), kw = ITEM.kitchen.w, kd = ITEM.kitchen.d, tw = ITEM.table4.w, td = ITEM.table4.d, gap = 0.5;
  const cols = Math.floor((w - gap) / (tw + gap));
  const x0 = -((cols - 1) * (tw + gap)) / 2; // centre the columns across the room
  const out: { x: number; z: number }[] = [];
  for (let z = d / 2 - gap - td / 2; z - td / 2 >= -d / 2 + gap - 1e-6; z -= td + gap) {
    for (let i = 0; i < cols; i++) {
      const x = snap(x0 + i * (tw + gap), tw);
      const clearK = Math.abs(x - k.x) >= (tw + kw) / 2 + gap - 1e-6 || Math.abs(z - k.z) >= (td + kd) / 2 + gap - 1e-6;
      const fx = -w / 2 + kw + 0.5, fz = -d / 2 + 0.5; // the fridge, next to the kitchen
      const clearF = Math.abs(x - fx) >= (tw + 1) / 2 + gap - 1e-6 || Math.abs(z - fz) >= (td + 1) / 2 + gap - 1e-6;
      if (clearK && clearF) out.push({ x, z: snap(z, td) });
    }
  }
  return out;
}

// the kitchen room, one drinks fridge and `tables` four-seat tables, laid out automatically
export function starterStore(pyeong = 20, grade: Grade = "basic", loan = 0, tables = 3): Store {
  const store: Store = { pyeong, grade, items: [], loan };
  const { w, d } = roomSize(pyeong);
  let uid = 1;
  store.items.push({ uid: uid++, id: "kitchen", ...kitchenSpot(pyeong), rot: 0 });
  const fr = { id: "fridge", x: snap(-w / 2 + ITEM.kitchen.w + 0.5, 1), z: snap(-d / 2 + 0.5, 1), rot: 0 as const };
  if (fits(store, fr)) store.items.push({ uid: uid++, ...fr });
  for (const t of tableSlots(pyeong).slice(0, tables)) {
    const c = { id: "table4", ...t, rot: 0 as const };
    if (fits(store, c)) store.items.push({ uid: uid++, ...c });
  }
  return store;
}
export const nextUid = (s: Store) => s.items.reduce((m, i) => Math.max(m, i.uid), 0) + 1;

export function storeStats(store: Store) {
  const seats = store.items.reduce((n, i) => n + (ITEM[i.id].seats ?? 0), 0);
  const tables = store.items.filter((i) => ITEM[i.id].cat === "seat").length;
  const hasKitchen = store.items.some((i) => i.id === "kitchen");
  const furnish = store.items.reduce((n, i) => n + ITEM[i.id].price, 0);
  return { seats, tables, hasKitchen, furnish };
}

// ---- opening cost -------------------------------------------------------------------------------------
export const SIGN = 250, FIRST_STOCK = 300, DEPOSIT_MONTHS = 10; // 가정
export const LOAN_RATE = 0.06; // 연 이자율, 가정. 이자만 매달 냄
export const cashLeft = (profile: Profile, store: Store) => profile.capital + store.loan - openingCost(store, profile.gu).total;
export type CostLine = { key: string; label: string; amount: number; basis: string };
export function openingCost(store: Store, gu: string): { lines: CostLine[]; total: number } {
  const st = guStat(gu);
  const s = storeStats(store);
  const seatCost = store.items.filter((i) => ITEM[i.id].cat === "seat").reduce((n, i) => n + ITEM[i.id].price, 0);
  const equip = store.items.filter((i) => ITEM[i.id].cat === "equip").reduce((n, i) => n + ITEM[i.id].price, 0);
  const lines: CostLine[] = [
    { key: "deposit", label: "보증금", amount: st.rent * store.pyeong * DEPOSIT_MONTHS, basis: `월세 ${DEPOSIT_MONTHS}개월분으로 가정` },
    { key: "interior", label: "인테리어 공사", amount: GRADES[store.grade].perPyeong * store.pyeong, basis: `${store.pyeong}평, 평당 ${GRADES[store.grade].perPyeong}만원 (${GRADES[store.grade].label})` },
    { key: "equip", label: "주방과 설비", amount: equip, basis: "주방, 냉장고, 계산대 등" },
    { key: "seat", label: "테이블과 의자", amount: seatCost, basis: `테이블 ${s.tables}개, ${s.seats}석` },
    { key: "deco", label: "꾸밈", amount: s.furnish - seatCost - equip, basis: "화분, 조명, 대기 의자" },
    { key: "sign", label: "간판", amount: SIGN, basis: "전면 간판 1개" },
    { key: "stock", label: "첫 재료와 소모품", amount: FIRST_STOCK, basis: "고기, 주류, 반찬 재료" },
  ];
  return { lines, total: lines.reduce((n, l) => n + l.amount, 0) };
}

// ---- six-month run ------------------------------------------------------------------------------------
export type Levers = { price: number; staff: number; days: 26 | 30 };
export const DEFAULT_LEVERS: Levers = { price: 19000, staff: 3, days: 26 };
export type ShockId = "rain" | "cost" | "rival" | "quit";
export const SHOCKS: Record<ShockId, { label: string; detail: string }> = {
  rain: { label: "비가 잦은 달이 이어진다", detail: "밤의 35%에 비, 그날 손님 10% 감소 (기존 시뮬의 가정값)" },
  cost: { label: "고깃값이 10% 오른다", detail: "재료비가 약 7% 늘어남" },
  rival: { label: "근처에 고깃집이 새로 생긴다", detail: "손님 10% 감소 (기존 시뮬의 가정값)" },
  quit: { label: "직원 한 명이 그만둔다", detail: "받을 수 있는 손님이 줄어듦" },
};

export const PERSON_TICKET = 27000;   // hero pnl ticket per guest (팀 추정): turns district sales into guests
export const OPEN_DAYS = 26;          // hero pnl days
export const SIDE_TICKET = 8000;      // hero pnl t_alc + t_side
export const FOOD_SHARE = 0.31;       // hero pnl food ÷ rev
export const STAFF_COST = 199;        // 만원/월, hero pnl (l_pt + l_emp) ÷ servers
export const MGMT_PER_PYEONG = 12.8;  // 만원/월, hero pnl mgmt ÷ area
export const FEE_SHARE = 0.0084;      // hero pnl fees ÷ rev
export const OWNER_DRAW = 300;        // 만원/월, hero owner_wage
export const OPEN_CURVE = [0.55, 0.7, 0.82, 0.9, 0.96, 1.0]; // 오픈 곡선, 가정
export const SEAT_TURN = 1.5;         // covers per seat per day the room can take, 가정
export const COVERS_PER_STAFF = 15;   // 가정
// opening every day means four more shifts a month to pay for (가정: 급여가 영업일에 비례)
export const staffPay = (staff: number, days: 26 | 30) => staff * STAFF_COST * (days === 30 ? 30 / 26 : 1);

export type MonthRow = { m: number; demand: number; capacity: number; covers: number; revenue: number; cost: number; op: number; cash: number };
export type Run = { rows: MonthRow[]; start: number; opening: number; capMonthly: number };

export function simulate(profile: Profile, store: Store, lv: Levers, shocks: ShockId[], demandMult = 1): Run {
  const st = guStat(profile.gu);
  const s = storeStats(store);
  const opening = openingCost(store, profile.gu).total;
  const start = profile.capital + store.loan - opening;
  const staff = Math.max(0, lv.staff - (shocks.includes("quit") ? 1 : 0));
  const capacity = s.hasKitchen ? Math.min(s.seats * SEAT_TURN, (staff + 1) * COVERS_PER_STAFF) : 0;
  const ticket = lv.price + SIDE_TICKET;
  const priceFx = Math.pow(lv.price / 19000, -0.8);
  const shockFx = (shocks.includes("rain") ? 1 - 0.35 * 0.1 : 1) * (shocks.includes("rival") ? 0.9 : 1);
  const food = FOOD_SHARE * (19000 / lv.price) * (shocks.includes("cost") ? 1.07 : 1);
  // a settled store is assumed to draw what the average 한식음식점 in this 구 does (real sales ÷ the hero ticket per guest)
  const settled = (st.sales * 10000) / (PERSON_TICKET * OPEN_DAYS);
  let cash = start;
  const rows = OPEN_CURVE.map((r, i) => {
    const demand = settled * r * priceFx * shockFx * demandMult * (lv.days === 30 ? 0.96 : 1);
    const covers = Math.min(demand, capacity);
    const revenue = (covers * ticket * lv.days) / 10000;
    const cost = revenue * (food + FEE_SHARE) + staffPay(staff, lv.days) + st.rent * store.pyeong + MGMT_PER_PYEONG * store.pyeong;
    const op = revenue - cost;
    cash += op - OWNER_DRAW - (store.loan * LOAN_RATE) / 12;
    return { m: i + 1, demand, capacity, covers, revenue, cost, op, cash };
  });
  return { rows, start, opening, capMonthly: (capacity * ticket * lv.days) / 10000 };
}

export const LOW = 0.8, HIGH = 1.15; // 범위: 손님이 20% 적을 때와 15% 많을 때 (가정)

// ---- operating numbers ---------------------------------------------------------------------------------
// what the store must pay every month whether or not anyone comes, and how many guests a day cover it
export function breakEven(profile: Profile, store: Store, lv: Levers) {
  const st = guStat(profile.gu);
  const lines = [
    { label: "월세", amount: st.rent * store.pyeong },
    { label: "관리비", amount: MGMT_PER_PYEONG * store.pyeong },
    { label: `직원 ${lv.staff}명 급여`, amount: staffPay(lv.staff, lv.days) },
    { label: "사장 생활비", amount: OWNER_DRAW },
    { label: "대출 이자", amount: (store.loan * LOAN_RATE) / 12 },
  ].filter((l) => l.amount > 0);
  const fixed = lines.reduce((n, l) => n + l.amount, 0);
  const margin = (lv.price + SIDE_TICKET) * (1 - FOOD_SHARE * (19000 / lv.price) - FEE_SHARE); // 원, what one guest leaves after food and card fees
  return { lines, fixed, margin, perDay: (fixed * 10000) / (margin * lv.days) };
}
// money that does not come back: everything spent to open except the deposit
export const sunkCost = (store: Store, gu: string) => openingCost(store, gu).lines.filter((l) => l.key !== "deposit").reduce((n, l) => n + l.amount, 0);
// settled month: what is left after every cost, the owner's pay and loan interest
export const settledNet = (run: Run, store: Store) => run.rows[5].op - OWNER_DRAW - (store.loan * LOAN_RATE) / 12;

// The store this money can best afford: among the sizes, table counts and staff numbers that survive six months even
// with 20% fewer guests, the one that leaves the most each month once settled. If none survives, the one that ends
// the six months with the most cash.
export function recommend(profile: Profile): { store: Store; staff: number; safe: boolean } {
  let best: { store: Store; staff: number; safe: boolean; score: number } | null = null;
  for (let pyeong = 12; pyeong <= 30; pyeong++) {
    const slots = tableSlots(pyeong).length;
    for (let tables = 2; tables <= slots; tables++) {
      const store = starterStore(pyeong, "basic", 0, tables);
      if (cashLeft(profile, store) < 0) break;
      for (let staff = 0; staff <= 6; staff++) {
        const lv = { ...DEFAULT_LEVERS, staff };
        const low = simulate(profile, store, lv, [], LOW);
        const safe = low.rows.every((r) => r.cash >= 0);
        const score = safe ? settledNet(simulate(profile, store, lv, []), store) : low.rows[5].cash;
        if (!best || (safe && !best.safe) || (safe === best.safe && score > best.score + 1e-6)) best = { store, staff, safe, score };
      }
    }
  }
  return best ?? { store: starterStore(12, "basic", 0, 2), staff: 1, safe: false };
}

// ---- 열기 전 점검: five questions an owner asks, each with the numbers behind the answer ---------------
export type Status = "ok" | "warn" | "weak";
export const STATUS_LABEL: Record<Status, string> = { ok: "여유", warn: "주의", weak: "취약" };
export type Check = { key: string; title: string; status: Status; line: string; todo?: string; rule: string; rows?: { label: string; value: string; ok: boolean }[] };

export function firstNegative(run: Run): number | null {
  if (run.start < 0) return 0;
  const r = run.rows.find((x) => x.cash < 0);
  return r ? r.m : null;
}
const months = (n: number) => (n >= 12 ? `${Math.floor(n / 12)}년${n % 12 ? ` ${n % 12}개월` : ""}` : `${n}개월`);

export function checks(profile: Profile, store: Store, lv: Levers): Check[] {
  const st = guStat(profile.gu);
  const s = storeStats(store);
  const mid = simulate(profile, store, lv, []);
  const low = simulate(profile, store, lv, [], LOW);
  const be = breakEven(profile, store, lv);
  const last = mid.rows[5];
  const want = Math.round(last.demand), need = Math.ceil(be.perDay);
  const bySeat = s.seats * SEAT_TURN, byStaff = (lv.staff + 1) * COVERS_PER_STAFF;
  const cap = Math.round(last.capacity);
  const net = settledNet(mid, store);
  const sunk = sunkCost(store, profile.gu);
  const neg = firstNegative(low);
  const base = last.cash;
  const shockRows = (Object.keys(SHOCKS) as ShockId[]).map((k) => {
    const end = simulate(profile, store, lv, [k]).rows[5].cash;
    return { label: `${SHOCKS[k].label}: ${SHOCKS[k].detail}`, value: `6개월 뒤 ${man(end)} (${man(end - base)})`, ok: end >= 0 };
  });
  const bad = shockRows.filter((r) => !r.ok).length;

  const fit: Check = { key: "fit", title: "자리와 일손이 손님 수에 맞나요?", status: "ok", line: "", rule: "" };
  if (s.seats === 0) { fit.status = "weak"; fit.line = "테이블이 없어서 손님을 받을 수 없어요."; }
  else if (want > cap * 1.15) {
    fit.status = "warn";
    fit.line = `하루 ${want}명쯤 올 텐데 ${cap}명까지만 받을 수 있어요. 날마다 ${want - cap}명쯤 돌려보내요.`;
    fit.todo = byStaff < bySeat ? "자리는 있는데 일손이 모자라요. 직원을 한 명 늘리면 더 받을 수 있어요." : "테이블을 늘리면 그만큼 매출이 늘어요.";
  } else if (want < cap * 0.6) {
    fit.status = "warn";
    fit.line = `${cap}명까지 받을 수 있는데 하루 ${want}명쯤 와요. 자리의 ${Math.round((1 - want / cap) * 100)}%가 비어요.`;
    fit.todo = "빈자리에도 월세가 나가요. 평수를 줄이면 다달이 나가는 돈이 줄어요.";
  } else {
    fit.line = `하루 ${want}명쯤 올 텐데 ${cap}명까지 받을 수 있어요. 금요일처럼 붐비는 날에도 대부분 받아요.`;
  }
  if (s.seats > 0 && lv.staff > 0 && lv.staff * COVERS_PER_STAFF >= want * 1.15 && lv.staff * COVERS_PER_STAFF >= Math.min(bySeat, want * 1.15)) {
    fit.status = fit.status === "ok" ? "warn" : fit.status;
    fit.todo = `직원을 한 명 줄여도 하루 ${Math.round(lv.staff * COVERS_PER_STAFF)}명까지 받을 수 있어요. 한 달에 ${man(STAFF_COST)}을 아껴요.`;
  }
  fit.rule = `올 손님 ${want}명은 ${profile.gu} 한식음식점 한 곳의 월매출 ${man(st.sales)}을 손님 한 명 ${PERSON_TICKET.toLocaleString("ko-KR")}원, 한 달 ${OPEN_DAYS}일로 나눈 값이에요(자리 잡힌 6개월째, 가격 반영). 받을 수 있는 손님은 좌석 ${s.seats}석 × 하루 ${SEAT_TURN}번 = ${Math.round(bySeat)}명과, 일하는 사람 ${lv.staff + 1}명 × ${COVERS_PER_STAFF}명 = ${byStaff}명 가운데 작은 쪽이에요. 회전수와 1인당 손님 수는 가정이에요.`;

  return [
    {
      key: "breakeven", title: "하루에 몇 명이 와야 본전인가요?",
      status: want >= need * 1.1 ? "ok" : want >= need ? "warn" : "weak",
      line: `하루 ${need}명이에요. ${profile.gu}의 비슷한 가게에는 하루 ${want}명쯤 와요.`,
      todo: want >= need ? undefined : `${need - want}명이 모자라요. 다달이 나가는 돈 ${man(be.fixed)}을 줄여야 해요.`,
      rule: `다달이 나가는 돈은 ${be.lines.map((l) => `${l.label} ${man(l.amount)}`).join(", ")}로 모두 ${man(be.fixed)}이에요. 손님 한 명이 재료비와 카드 수수료를 빼고 ${Math.round(be.margin).toLocaleString("ko-KR")}원을 남기니, 한 달 ${lv.days}일 영업이면 하루 ${need}명이 와야 0원이 돼요.`,
    },
    fit,
    {
      key: "runway", title: "현금은 언제까지 버티나요?",
      status: neg === null ? "ok" : neg <= 3 ? "weak" : "warn",
      line: neg === 0 ? `여는 데 드는 돈이 가진 돈보다 ${man(-mid.start)} 많아요.`
        : neg ? `손님이 예상보다 20% 적으면 ${neg}개월째에 현금이 바닥나요.` : `손님이 예상보다 20% 적어도 6개월 뒤 ${man(low.rows[5].cash)}이 남아요.`,
      todo: neg ? "새 가게는 첫 달에 자리 잡힌 뒤의 55%만 온다고 봤어요. 그동안 버틸 현금을 남겨 두세요." : undefined,
      rule: `가게를 열고 남는 현금 ${man(mid.start)}에서 시작해요. 손님은 첫 달 55%에서 6개월째 100%로 늘어난다고 가정했고, 예상대로 오면 6개월 뒤 ${man(base)}이에요.`,
    },
    {
      key: "payback", title: "들인 돈은 언제 돌아오나요?",
      status: net <= 0 ? "weak" : sunk / net <= 36 ? "ok" : sunk / net <= 60 ? "warn" : "weak",
      line: net <= 0 ? `자리가 잡힌 뒤에도 한 달에 ${man(-net)}씩 줄어요. 이 구성으로는 돌아오지 않아요.`
        : `자리가 잡히면 한 달에 ${man(net)}이 남아요. 들인 돈 ${man(sunk)}은 약 ${months(Math.ceil(sunk / net))} 뒤에 돌아와요.`,
      rule: `들인 돈은 보증금을 뺀 공사, 설비, 간판, 첫 재료 값이에요(보증금은 나갈 때 돌려받아요). 한 달에 남는 돈은 6개월째 매출에서 재료비, 급여, 월세, 관리비, 사장 생활비 ${man(OWNER_DRAW)}, 이자를 뺀 값이에요.`,
    },
    {
      key: "shock", title: "나쁜 일이 생기면 어떻게 되나요?",
      status: bad === 0 ? "ok" : bad <= 2 ? "warn" : "weak",
      line: bad === 0 ? "아래 네 가지 가운데 무엇이 하나 생겨도 6개월 뒤 현금이 남아요." : `아래 네 가지 가운데 ${bad}가지는 하나만 생겨도 6개월 안에 현금이 바닥나요.`,
      rows: shockRows,
      rule: "한 가지씩 따로 6개월 내내 이어진다고 보고 계산했어요. 괄호 안은 아무 일 없을 때와의 차이예요. 크기는 기존 시뮬레이터의 가정값이에요.",
    },
  ];
}
