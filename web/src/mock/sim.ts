// Day-by-day run for the 시뮬레이션 tab (mock, not the SimPy engine). One step = one day: guests, sales, costs, the
// cash movements of that day, satisfaction, and the events that stop the clock for a choice.
// Real inputs: the 구's sales per store, day-of-week shares and quarter index (서울시 상권분석서비스 2025), 2026 holidays
// (특일 정보). Borrowed: cost ratios and event sizes from the 대학로 hero store and research/events.yaml. Assumed: the
// rest. Each is listed on #/sources.
import {
  COVERS_PER_STAFF, FEE_SHARE, FOOD_SHARE, LOAN_RATE, MGMT_PER_PYEONG, OPEN_CURVE, OPEN_DAYS, OWNER_DRAW, PERSON_TICKET, SEAT_TURN,
  SIDE_TICKET, cashLeft, guStat, staffPay, storeStats, type Levers, type Profile, type Store,
} from "./model";

export const DAYS = 180;
// holidays: 특일 정보 2026~2027. rain: share of days with 1mm or more by calendar month, 기상청 ASOS 서울 2016~2025.
export type World = { holidays: Record<string, string>; rain: number[] };
export const NO_WORLD: World = { holidays: {}, rain: Array(12).fill(0.2) };
export const RAIN_FX = 0.9; // research/shocks.yaml SH10: 비 오는 밤 손님 −10% (원 레포도 가정으로 표시)

function rng(seed: number) { // mulberry32: the same day always rolls the same numbers, so rewinding replays it
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// ---- events -------------------------------------------------------------------------------------------
export type Mod = { until: number; demand?: number; food?: number; ticket?: number; staff?: number; labor?: number; rain?: number; closed?: boolean; label: string };
export type Choice = { id: string; label: string; hint: string; cash?: number; sat?: number; mods?: Omit<Mod, "until">[]; days?: number; risk?: { p: number; sat: number; closedDays: number; text: string } };
export type EventCard = { id: string; title: string; prompt: string; basis: string; months?: number[]; choices: Choice[] };

// Sizes follow research/events.yaml where it has them; the choices and their effects are new assumptions.
export const EVENTS: EventCard[] = [
  {
    id: "pork_up", title: "돼지고기 도매가가 올랐어요", prompt: "거래처에서 삼겹살 납품가를 올린다고 연락이 왔어요. 1인분 원가가 8% 오릅니다.",
    basis: "원가 +8%: events.yaml pork_up (S68, S48). 선택지 효과는 가정",
    choices: [
      { id: "absorb", label: "가격은 그대로 두고 버틴다", hint: "한 달 동안 재료비가 늘어요", mods: [{ food: 1.055, label: "고깃값 인상" }], days: 30 },
      { id: "reprice", label: "1인분 가격을 1,000원 올린다", hint: "남는 돈은 지키지만 손님이 조금 줄어요", mods: [{ food: 1.055, ticket: 1000, demand: 0.96, label: "고깃값 인상, 가격 인상" }], days: 30 },
      { id: "import", label: "수입육을 섞어 쓴다", hint: "재료비는 그대로, 맛 평가가 떨어질 수 있어요", sat: -5 },
    ],
  },
  {
    id: "rain_week", title: "비가 계속 온대요", prompt: "이번 주 내내 비 예보예요. 비 오는 밤에는 손님이 줄어듭니다.", months: [6, 7, 8, 9],
    basis: "비 오는 밤 손님 −10%: shocks.yaml SH10 (원 레포도 가정). 일주일 비 확률 70%와 선택지 효과는 가정",
    choices: [
      { id: "wait", label: "평소대로 장사한다", hint: "일주일 동안 손님이 줄어요", mods: [{ rain: 0.7, label: "비 오는 주간" }], days: 7 },
      { id: "coupon", label: "비 오는 날 소주 한 병 서비스", hint: "손님은 덜 줄지만 한 팀당 남는 돈이 줄어요", mods: [{ rain: 0.7, demand: 1.06, food: 1.04, label: "비 오는 주간, 서비스 행사" }], days: 7 },
    ],
  },
  {
    id: "competitor_open", title: "근처에 고깃집이 새로 생겼어요", prompt: "걸어서 3분 거리에 새 고깃집이 오픈 행사를 시작했어요. 손님을 나눠 갖게 됩니다.",
    basis: "손님 −9%: events.yaml competitor_open (S13, S20). 선택지 효과는 가정",
    choices: [
      { id: "watch", label: "지켜본다", hint: "석 달 동안 손님이 9% 줄어요", mods: [{ demand: 0.91, label: "경쟁점 개점" }], days: 90 },
      { id: "match", label: "2주 동안 맞불 할인을 한다", hint: "2주는 손님을 지키지만 남는 돈이 줄고, 그 뒤엔 똑같이 줄어요", mods: [{ demand: 0.97, ticket: -2000, label: "맞불 할인" }], days: 14 },
      { id: "service", label: "반찬과 서비스를 늘린다", hint: "재료비가 조금 늘고 손님은 덜 줄어요", sat: 3, mods: [{ demand: 0.95, food: 1.03, label: "경쟁점 개점, 반찬 강화" }], days: 90 },
    ],
  },
  {
    id: "staff_quit", title: "알바가 갑자기 그만뒀어요", prompt: "저녁 타임 알바가 오늘부로 못 나온다고 합니다. 사람이 모자라면 받을 수 있는 손님이 줄어요.",
    basis: "events.yaml staff_quit (확률과 효과 모두 가정)",
    choices: [
      { id: "hire", label: "구인 공고를 내고 일주일 버틴다", hint: "공고비 30만원, 일주일 동안 한 명이 모자라요", cash: -30, mods: [{ staff: -1, label: "알바 공백" }], days: 7 },
      { id: "owner", label: "사장인 내가 메운다", hint: "한 달 인건비는 줄지만 서비스가 밀려요", sat: -4, mods: [{ staff: -1, labor: -1, label: "사장이 대신 근무" }], days: 30 },
      { id: "raise", label: "시급을 올려 바로 구한다", hint: "사흘만 비고, 석 달 인건비가 5% 올라요", mods: [{ staff: -1, label: "알바 공백" }], days: 3 },
    ],
  },
  {
    id: "bad_review", title: "악성 리뷰가 달렸어요", prompt: "\"고기는 괜찮은데 불친절\"이라는 별점 1개 리뷰가 지도 앱 맨 위에 올라왔어요.",
    basis: "평점 하락: events.yaml bad_review (가정)",
    choices: [
      { id: "reply", label: "사과 답글을 달고 재방문 쿠폰을 보낸다", hint: "10만원이 들고 만족도가 일부 회복돼요", cash: -10, sat: -3 },
      { id: "ignore", label: "대응하지 않는다", hint: "돈은 안 들지만 만족도가 더 떨어져요", sat: -8 },
    ],
  },
  {
    id: "hygiene", title: "위생점검이 나온대요", prompt: "구청 통합위생점검이 이번 주에 있다는 소식이에요.",
    basis: "연 1회 점검, 지적 시 영업정지 2일: events.yaml hygiene_inspection (S91 적발률 참고, 가정)",
    choices: [
      { id: "clean", label: "전날 마감 후 대청소를 한다", hint: "직원 초과수당 20만원, 지적받을 일이 없어요", cash: -20 },
      { id: "asis", label: "평소대로 둔다", hint: "돈은 안 들지만 지적받으면 이틀 문을 닫아요", risk: { p: 0.05, sat: -6, closedDays: 2, text: "위생 지적으로 이틀 영업정지" } },
    ],
  },
  {
    id: "cold_wave", title: "한파가 왔어요", prompt: "이번 주 최저기온이 영하 10도 아래로 내려가요. 외출이 줄어듭니다.", months: [12, 1, 2],
    basis: "손님 −6%: events.yaml cold_wave (가정)",
    choices: [
      { id: "wait", label: "평소대로 장사한다", hint: "일주일 동안 손님이 6% 줄어요", mods: [{ demand: 0.94, label: "한파" }], days: 7 },
      { id: "warm", label: "따뜻한 국물 서비스를 낸다", hint: "재료비가 조금 늘고 손님이 덜 줄어요", sat: 2, mods: [{ demand: 0.98, food: 1.03, label: "한파, 국물 서비스" }], days: 7 },
    ],
  },
  {
    id: "viral_blog", title: "맛집 블로거가 다녀갔어요", prompt: "구독자 많은 맛집 블로거가 방문 후기를 올렸어요. 한동안 손님이 늘 거예요.",
    basis: "손님 +6%: events.yaml viral_blog (가정)",
    choices: [
      { id: "asis", label: "평소대로 맞는다", hint: "한 달 동안 손님이 6% 늘어요", mods: [{ demand: 1.06, label: "블로그 후기" }], days: 30 },
      { id: "extra", label: "임시로 알바를 한 명 더 쓴다", hint: "인건비가 늘지만 몰리는 손님을 놓치지 않아요", sat: 3, mods: [{ demand: 1.06, staff: 1, labor: 1, label: "블로그 후기, 임시 알바" }], days: 30 },
    ],
  },
];

// ---- state --------------------------------------------------------------------------------------------
export type Tick = { label: string; amount: number }; // 만원, + in / − out
export type DayRow = {
  day: number; date: string; dow: number; open: boolean; rain: boolean; holiday: string | null; note: string | null;
  demand: number; covers: number; turned: number; revenue: number; ticks: Tick[]; net: number; cash: number; sat: number;
  profit: number; // that day's sales minus its food and fees and one day's share of the monthly bills (wages, rent, owner's pay, interest)
};
export type Review = { day: number; stars: number; text: string };
export type Decision = { day: number; event: string; title: string; choice: string; outcome: string };
export type Sim = {
  seed: number; startMonth: number; day: number; cash: number; sat: number; guests: number; negDays: number;
  mods: Mod[]; rows: DayRow[]; reviews: Review[]; decisions: Decision[]; schedule: { day: number; id: string }[];
  pending: EventCard | null; over: null | "done" | "closed";
};

const DOW_KO = ["일", "월", "화", "수", "목", "금", "토"];
export const dowKo = (d: number) => DOW_KO[d];
export const START_YEAR = 2026;
export const dateOf = (startMonth: number, day: number) => new Date(START_YEAR, startMonth - 1, 1 + day);
const iso = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

export function newSim(profile: Profile, store: Store, startMonth: number, seed = 20261013): Sim {
  const r = rng(seed * 7 + startMonth);
  // one event a month on a random day, drawn without repeats from the cards that fit that calendar month
  const used = new Set<string>();
  const schedule: Sim["schedule"] = [];
  for (let m = 0; m < 6; m++) {
    const cal = ((startMonth - 1 + m) % 12) + 1;
    const pool = EVENTS.filter((e) => !used.has(e.id) && (!e.months || e.months.includes(cal)));
    if (!pool.length) continue;
    const pick = pool[Math.floor(r() * pool.length)];
    used.add(pick.id);
    schedule.push({ day: m * 30 + 6 + Math.floor(r() * 18), id: pick.id });
  }
  return { seed, startMonth, day: 0, cash: cashLeft(profile, store), sat: 80, guests: 0, negDays: 0, mods: [], rows: [], reviews: [], decisions: [], schedule, pending: null, over: null };
}

const REVIEW_TEXT: Record<string, string[]> = {
  good: ["고기 질이 좋고 직원분이 친절해요.", "동네에 이런 집이 생겨서 좋아요. 또 올게요.", "반찬이 깔끔하고 불판 관리를 잘해 줘요."],
  wait: ["자리가 없어서 그냥 돌아왔어요.", "30분 기다리다 포기했습니다.", "맛은 괜찮은데 웨이팅이 너무 길어요."],
  slow: ["사람이 모자란지 주문이 한참 걸렸어요.", "불판 갈아 달라고 세 번 말했어요."],
  price: ["맛은 있는데 가격이 부담돼요.", "양에 비해 비싼 편이에요."],
  ok: ["무난한 삼겹살집이에요.", "가까워서 가끔 갑니다."],
};

export function step(s: Sim, profile: Profile, store: Store, lv: Levers, world: World): Sim {
  if (s.over || s.pending) return s;
  const due = s.schedule.find((e) => e.day === s.day && !s.decisions.some((d) => d.event === e.id));
  if (due) return { ...s, pending: EVENTS.find((e) => e.id === due.id)! };

  const r = rng(s.seed + s.day * 101);
  const st = guStat(profile.gu);
  const ss = storeStats(store);
  const date = dateOf(s.startMonth, s.day);
  const dow = date.getDay(), cal = date.getMonth() + 1, dom = date.getDate();
  const holiday = world.holidays[iso(date)] ?? null;
  const mods = s.mods.filter((m) => m.until > s.day);
  const mul = (k: "demand" | "food") => mods.reduce((v, m) => v * (m[k] ?? 1), 1);
  const add = (k: "ticket" | "staff" | "labor") => mods.reduce((v, m) => v + (m[k] ?? 0), 0);
  const closedMod = mods.some((m) => m.closed);
  const open = !closedMod && !(lv.days === 26 && dow === 1 && !holiday); // weekly day off: Monday (the lowest day in the data)
  const rain = r() < Math.max(world.rain[cal - 1], ...mods.map((m) => m.rain ?? 0));

  const price = lv.price + add("ticket");
  const ticket = price + SIDE_TICKET;
  const staff = Math.max(0, lv.staff + add("staff"));
  const capacity = Math.min(ss.seats * SEAT_TURN, (staff + 1) * COVERS_PER_STAFF);
  const ramp = OPEN_CURVE[Math.min(5, Math.floor(s.day / 30))] + (OPEN_CURVE[Math.min(5, Math.floor(s.day / 30) + 1)] - OPEN_CURVE[Math.min(5, Math.floor(s.day / 30))]) * ((s.day % 30) / 30);
  const settled = (st.sales * 10000) / (PERSON_TICKET * OPEN_DAYS);
  const dowShare = st.dow[(dow + 6) % 7] * 7;                       // data order is 월..일
  const dayFx = holiday ? st.dow[6] * 7 : dowShare;                 // a public holiday is assumed to trade like a Sunday
  const demand = !open ? 0 : settled * ramp * dayFx * st.qidx[Math.floor((cal - 1) / 3)] * Math.pow(price / 19000, -0.8)
    * mul("demand") * (rain ? RAIN_FX : 1) * (1 + ((s.sat - 80) / 100) * 0.5) * (0.88 + r() * 0.24);
  const covers = Math.min(demand, capacity);
  const turned = Math.max(0, demand - capacity);

  const revenue = (covers * ticket) / 10000;
  const variable = revenue * (FOOD_SHARE * (19000 / lv.price) * mul("food") + FEE_SHARE);
  const wages = staffPay(Math.max(0, lv.staff + add("labor")), lv.days);
  const rent = st.rent * store.pyeong + MGMT_PER_PYEONG * store.pyeong;
  const interest = (store.loan * LOAN_RATE) / 12;
  const ticks: Tick[] = [];
  if (revenue > 0) {
    ticks.push({ label: "매출", amount: revenue });
    ticks.push({ label: "재료비와 카드 수수료", amount: -variable });
  }
  if (dom === 1) ticks.push({ label: "월세와 관리비", amount: -rent });
  if (dom === 10 && s.day >= 20 && wages > 0) ticks.push({ label: "직원 급여", amount: -wages }); // paid in arrears: nothing is due on the first 10th
  if (dom === 25) {
    ticks.push({ label: "사장 생활비", amount: -OWNER_DRAW });
    if (interest > 0) ticks.push({ label: "대출 이자", amount: -interest });
  }
  const profit = revenue - variable - (wages + rent + OWNER_DRAW + interest) / 30.4;
  const net = ticks.reduce((n, t) => n + t.amount, 0);
  const cash = s.cash + net;

  // satisfaction drifts up on a normal day and drops when guests are turned away or the floor is short-handed
  const staffCap = (staff + 1) * COVERS_PER_STAFF;
  const waitHit = open && demand > 0 && turned / demand > 0.2;
  const slowHit = open && staffCap < ss.seats * SEAT_TURN && covers >= staffCap * 0.95; // the floor staff are the limit and at it
  const sat = Math.max(20, Math.min(98, s.sat + (!open ? 0 : waitHit ? -0.3 : slowHit ? -0.2 : s.sat < 86 ? 0.15 : 0)));
  const reviews = [...s.reviews];
  if (open && covers > 3 && r() < 0.16) {
    const kind = waitHit ? "wait" : slowHit ? "slow" : lv.price >= 22000 && r() < 0.5 ? "price" : sat > 78 ? "good" : "ok";
    const stars = kind === "good" ? 5 : kind === "ok" ? 4 : kind === "price" ? 3 : 2;
    const list = REVIEW_TEXT[kind];
    reviews.push({ day: s.day, stars, text: list[Math.floor(r() * list.length)] });
  }

  const note = closedMod ? mods.find((m) => m.closed)!.label : !open ? "정기 휴무" : null;
  const row: DayRow = { day: s.day, date: iso(date), dow, open, rain, holiday, note, demand, covers, turned, revenue, ticks, net, cash, sat, profit };
  const negDays = cash < 0 ? s.negDays + 1 : 0;
  const day = s.day + 1;
  const over = negDays >= 60 ? "closed" : day >= DAYS ? "done" : null; // 현금이 두 달 내리 0 아래면 폐업 (기존 게임의 규칙)
  return { ...s, day, cash, sat, guests: s.guests + covers, negDays, mods, rows: [...s.rows, row], reviews, over };
}

export function choose(s: Sim, choiceId: string): Sim {
  const card = s.pending;
  if (!card) return s;
  const c = card.choices.find((x) => x.id === choiceId)!;
  const r = rng(s.seed + s.day * 977 + 5);
  let cash = s.cash + (c.cash ?? 0), sat = s.sat + (c.sat ?? 0), outcome = c.hint;
  const mods = [...s.mods, ...(c.mods ?? []).map((m) => ({ ...m, until: s.day + (c.days ?? 30) }))];
  if (card.id === "staff_quit" && c.id === "raise") mods.push({ until: s.day + 90, labor: 0.15, label: "시급 인상" }); // about 5% of three wages
  if (card.id === "competitor_open" && c.id === "match") mods.push({ until: s.day + 90, demand: 0.91, label: "경쟁점 개점" });
  if (c.risk) {
    if (r() < c.risk.p) {
      sat += c.risk.sat;
      mods.push({ until: s.day + c.risk.closedDays, closed: true, label: c.risk.text });
      outcome = `${c.risk.text}를 받았어요.`;
    } else outcome = "별일 없이 지나갔어요.";
  }
  sat = Math.max(20, Math.min(98, sat));
  return { ...s, cash, sat, mods, pending: null, decisions: [...s.decisions, { day: s.day, event: card.id, title: card.title, choice: c.label, outcome }] };
}

// monthly roll-up for the report
export function months(s: Sim) {
  return Array.from({ length: Math.ceil(s.rows.length / 30) }, (_, m) => {
    const rows = s.rows.slice(m * 30, m * 30 + 30);
    const sum = (f: (r: DayRow) => number) => rows.reduce((n, r) => n + f(r), 0);
    return {
      m: m + 1, guests: sum((r) => r.covers), turned: sum((r) => r.turned), revenue: sum((r) => r.revenue),
      spend: sum((r) => r.ticks.filter((t) => t.amount < 0).reduce((n, t) => n + t.amount, 0)), net: sum((r) => r.net), profit: sum((r) => r.profit), days: rows.length,
      cash: rows.at(-1)?.cash ?? 0, sat: rows.at(-1)?.sat ?? 0, rain: rows.filter((r) => r.rain).length,
    };
  });
}
