// Step 4. Six months, one day at a time, in the store the user built. The top bar keeps the day, guests,
// satisfaction and cash in view; each day's money in and out flashes next to the cash and is kept in the ledger
// drawer on the right; an event stops the clock until the user picks a response. Rewind restores an earlier day.
import { useEffect, useMemo, useRef, useState } from "react";
import { Canvas } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import { GLGuard } from "../shared/GLGuard";
import { Items, Room, seatSpots } from "./Parts3D";
import { COVERS_PER_STAFF, SEAT_TURN, breakEven, man, roomSize, storeStats, sunkCost, type Levers, type Profile, type Store } from "./model";
import { DAYS, NO_WORLD, START_YEAR, choose, dateOf, dowKo, months, newSim, step, type DayRow, type Sim, type World } from "./sim";

const DAY_MS = { play: 1000, fast: 110 };
const SHIRTS = ["#e0735a", "#43648a", "#d4a032", "#5679a3", "#ec8a4f", "#35614a"];

const ICONS = {
  day: <path d="M7 2a1 1 0 0 1 1 1v1h8V3a1 1 0 1 1 2 0v1h1a3 3 0 0 1 3 3v12a3 3 0 0 1-3 3H5a3 3 0 0 1-3-3V7a3 3 0 0 1 3-3h1V3a1 1 0 0 1 1-1zM4 10v9a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-9zm3 3h3v3H7z" />,
  guest: <><circle cx="12" cy="7.5" r="4.5" /><path d="M3.5 21a8.5 8.5 0 0 1 17 0 1 1 0 0 1-1 1h-15a1 1 0 0 1-1-1z" /></>,
  guests: <><circle cx="12" cy="9.5" r="3.6" /><path d="M5.2 22a6.8 6.8 0 0 1 13.6 0z" /><circle cx="4.9" cy="6.4" r="2.9" /><path d="M0 16.5a5 5 0 0 1 7.6-4.3A8.6 8.6 0 0 0 3.6 16.5z" /><circle cx="19.1" cy="6.4" r="2.9" /><path d="M24 16.5a5 5 0 0 0-7.6-4.3 8.6 8.6 0 0 1 4 4.3z" /></>,
  sat: <path fillRule="evenodd" d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20zM8.5 8a1.5 1.5 0 1 1 0 3 1.5 1.5 0 0 1 0-3zm7 0a1.5 1.5 0 1 1 0 3 1.5 1.5 0 0 1 0-3zM6.6 13.5h10.8a5.5 5.5 0 0 1-10.8 0z" />,
  cash: <path fillRule="evenodd" d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20zM6.2 7.5h1.9l1.2 5.3 1.6-5.3h2.2l1.6 5.3 1.2-5.3h1.9l-2.1 9h-2L12 11l-1.7 5.5h-2z" />,
};
function Icon({ name }: { name: keyof typeof ICONS }) {
  return <svg className="m-ico" viewBox="0 0 24 24" aria-hidden="true">{ICONS[name]}</svg>;
}
const CTRL = {
  weekBack: <path d="M4 5h2.4v14H4zM20 5v14l-10-7z" />,
  dayBack: <path d="M12 5v14L2 12zM22 5v14l-10-7z" />,
  play: <path d="M6 4l14 8-14 8z" />,
  pause: <path d="M6 4h4.4v16H6zM13.6 4H18v16h-4.4z" />,
  fast: <path d="M2 5l10 7-10 7zM12 5l10 7-10 7z" />,
  skip: <path d="M4 5l10 7-10 7zM17.6 5H20v14h-2.4z" />,
};
function Ctrl({ icon, label, ...rest }: { icon: keyof typeof CTRL; label: string } & React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return <button type="button" aria-label={label} title={label} {...rest}><svg viewBox="0 0 24 24" aria-hidden="true">{CTRL[icon]}</svg></button>;
}

function Guests({ store, filled }: { store: Store; filled: number }) {
  const spots = useMemo(() => seatSpots(store.items), [store.items]);
  // fill seats in a fixed shuffled order so the same people stay put from day to day
  const order = useMemo(() => spots.map((_, i) => i).sort((a, b) => ((a * 7919) % 13) - ((b * 7919) % 13)), [spots]);
  return (
    <>
      {order.slice(0, filled).map((i) => (
        <group key={i} position={[spots[i][0], 0, spots[i][1]]}>
          <mesh position={[0, 0.72, 0]} castShadow><capsuleGeometry args={[0.15, 0.36, 4, 10]} /><meshStandardMaterial color={SHIRTS[i % SHIRTS.length]} roughness={0.8} /></mesh>
          <mesh position={[0, 1.18, 0]} castShadow><sphereGeometry args={[0.13, 14, 12]} /><meshStandardMaterial color="#f1d3b8" roughness={0.7} /></mesh>
        </group>
      ))}
    </>
  );
}

const W = 640, H = 240, PAD = { l: 92, r: 16, t: 14, b: 30 };
function CashLine({ sim, start }: { sim: Sim; start: number }) {
  const [hover, setHover] = useState<number | null>(null);
  const ref = useRef<SVGSVGElement>(null);
  const cash = [start, ...sim.rows.map((r) => r.cash)];
  const min = Math.min(0, ...cash), max = Math.max(0, ...cash);
  const pad = (max - min) * 0.1 || 100;
  const y0 = min - pad, y1 = max + pad;
  const x = (d: number) => PAD.l + (d / DAYS) * (W - PAD.l - PAD.r);
  const y = (v: number) => PAD.t + (1 - (v - y0) / (y1 - y0)) * (H - PAD.t - PAD.b);
  const stepSize = [500, 1000, 2000, 5000, 10000].find((s) => (y1 - y0) / s <= 4) ?? 20000;
  const ticks: number[] = [];
  for (let t = Math.ceil(y0 / stepSize) * stepSize; t <= y1; t += stepSize) ticks.push(t);
  const onMove = (e: React.PointerEvent) => {
    const r = ref.current!.getBoundingClientRect();
    const d = Math.round((((e.clientX - r.left) / r.width) * W - PAD.l) / (W - PAD.l - PAD.r) * DAYS);
    setHover(d >= 1 && d <= sim.rows.length ? d : null);
  };
  const row = hover ? sim.rows[hover - 1] : null;
  return (
    <div className="m-chart">
      <svg ref={ref} viewBox={`0 0 ${W} ${H}`} role="img" aria-label="날마다 남은 현금" onPointerMove={onMove} onPointerLeave={() => setHover(null)}>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={PAD.l} x2={W - PAD.r} y1={y(t)} y2={y(t)} className={t === 0 ? "zero" : "grid"} />
            <text x={PAD.l - 8} y={y(t) + 4} textAnchor="end">{t === 0 ? "0" : man(t)}</text>
          </g>
        ))}
        {[0, 1, 2, 3, 4, 5].map((m) => <text key={m} x={x(m * 30 + 15)} y={H - 8} textAnchor="middle">{m + 1}개월</text>)}
        {[1, 2, 3, 4, 5].map((m) => <line key={m} x1={x(m * 30)} x2={x(m * 30)} y1={PAD.t} y2={H - PAD.b} className="grid" />)}
        <line x1={PAD.l} x2={W - PAD.r} y1={y(start)} y2={y(start)} className="cross" />
        <path d={cash.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join("")} className="line" />
        {sim.decisions.map((d) => <path key={d.event} transform={`translate(${x(d.day)},${y(cash[d.day] ?? start)})`} d="M0-6 6 0 0 6-6 0z" className="event" />)}
        {row && <><line x1={x(hover!)} x2={x(hover!)} y1={PAD.t} y2={H - PAD.b} className="cross" /><circle cx={x(hover!)} cy={y(row.cash)} r="5" className="dot" /></>}
      </svg>
      {row && (
        <div className="m-tip" style={{ insetInlineStart: `${(x(hover!) / W) * 100}%`, insetBlockStart: 0 }} data-flip={x(hover!) / W > 0.6 || undefined}>
          <strong>{row.day + 1}일차 ({row.date.slice(5).replace("-", "월 ")}일 {dowKo(row.dow)})</strong>
          <span>{row.open ? `손님 ${Math.round(row.covers)}명, 그날 ${signed(row.net)}` : row.note}</span>
          <span>현금 {man(row.cash)}</span>
        </div>
      )}
      <p className="m-src">점선은 문 연 날의 현금, 마름모는 일이 생긴 날이에요. 1일에 월세, 10일에 급여, 25일에 생활비가 한꺼번에 나가서 계단처럼 꺾여요.</p>
    </div>
  );
}

const signed = (v: number) => `${v >= 0 ? "+" : "−"}${man(Math.abs(v))}`;
const span = (n: number) => (n >= 12 ? `${Math.floor(n / 12)}년${n % 12 ? ` ${n % 12}개월` : ""}` : `${n}개월`);

// what an owner watches: is a day's trade above break-even, has a month ended in profit, how much of the outlay is back
function opsOf(sim: Sim, profile: Profile, store: Store, levers: Levers) {
  const be = breakEven(profile, store, levers);
  const open = sim.rows.filter((r) => r.open);
  const week = open.slice(-7);
  const avg = week.length ? week.reduce((n, r) => n + r.covers, 0) / week.length : 0;
  const monthly = months(sim);
  const cur = monthly.at(-1);
  const firstBlack = monthly.find((m) => m.days === 30 && m.profit >= 0);
  const earned = sim.rows.reduce((n, r) => n + r.profit, 0);
  const recent = sim.rows.slice(-30);
  const pace = recent.length >= 14 ? (recent.reduce((n, r) => n + r.profit, 0) / recent.length) * 30.4 : null;
  const sunk = sunkCost(store, profile.gu);
  const left = pace && pace > 0 ? Math.ceil((sunk - earned) / pace) : null;
  return { be, avg, monthly, cur, firstBlack, earned, pace, sunk, left };
}

function Ledger({ rows, open, setOpen }: { rows: DayRow[]; open: boolean; setOpen: (v: boolean) => void }) {
  if (!open) return <button type="button" className="m-ledgertab" aria-expanded="false" onClick={() => setOpen(true)}>현금 흐름 기록 펴기</button>;
  return (
    <aside className="m-ledger" aria-label="현금 흐름 기록">
      <header><h2>현금 흐름 기록</h2><button type="button" className="m-link" aria-expanded="true" onClick={() => setOpen(false)}>접기</button></header>
      {rows.length === 0 ? <p className="m-src">문을 열면 날마다 들어오고 나간 돈이 여기에 쌓여요.</p> : (
        <ol>
          {[...rows].reverse().map((r) => (
            <li key={r.day}>
              <p><b>{Number(r.date.slice(5, 7))}월 {Number(r.date.slice(8))}일 {dowKo(r.dow)}</b><span>{r.day + 1}일차{r.open ? `, 손님 ${Math.round(r.covers)}명` : `, ${r.note}`}{r.rain ? ", 비" : ""}{r.holiday ? `, ${r.holiday}` : ""}</span></p>
              <ul>
                {r.ticks.map((t) => <li key={t.label} className={t.amount >= 0 ? "in" : "out"}><span>{t.label}</span><b>{signed(t.amount)}</b></li>)}
              </ul>
              <p className="sum"><span>그날 <b className={r.net >= 0 ? "in" : "out"}>{signed(r.net)}</b></span><span>남은 현금 <b>{man(r.cash)}</b></span></p>
            </li>
          ))}
        </ol>
      )}
    </aside>
  );
}

export default function Simulate({ profile, store, levers, setLevers, onBack }: {
  profile: Profile; store: Store; levers: Levers; setLevers: (l: Levers) => void; onBack: () => void;
}) {
  const [startMonth, setStartMonth] = useState(11);
  const [sim, setSim] = useState<Sim | null>(null);
  const [playing, setPlaying] = useState(false);
  const [fast, setFast] = useState(false);
  const [world, setWorld] = useState<World>(NO_WORLD);
  const [showReviews, setShowReviews] = useState(false);
  const [ledger, setLedger] = useState(() => innerWidth >= 1500);
  const history = useRef<Sim[]>([]);
  const live = useRef({ profile, store, levers, world });
  live.current = { profile, store, levers, world };

  useEffect(() => {
    const get = (f: string) => fetch(`${import.meta.env.BASE_URL}mock/${f}`).then((r) => r.json());
    Promise.all([get("holidays.json"), get("weather_seoul.json")])
      .then(([h, w]) => setWorld({ holidays: h.days, rain: w.months.map((m: { rain_share: number }) => m.rain_share) })).catch(() => setWorld(NO_WORLD));
  }, []);

  const advance = (s: Sim): Sim => {
    const L = live.current;
    const next = step(s, L.profile, L.store, L.levers, L.world);
    if (next.day !== s.day) history.current[s.day] = s; // the state at the start of that day
    return next;
  };
  useEffect(() => {
    if (!playing || !sim || sim.pending || sim.over) return;
    const id = setInterval(() => setSim((s) => (!s || s.pending || s.over ? s : advance(s))), fast ? DAY_MS.fast : DAY_MS.play);
    return () => clearInterval(id);
  }, [playing, fast, sim?.pending, sim?.over, sim === null]); // eslint-disable-line react-hooks/exhaustive-deps

  const stats = storeStats(store);
  const { w, d } = roomSize(store.pyeong);
  const begin = () => { history.current = []; setSim(newSim(profile, store, startMonth)); setPlaying(true); setFast(false); };
  const rewind = (n: number) => {
    if (!sim) return;
    const target = Math.max(0, sim.day - n);
    const saved = target === 0 ? newSim(profile, store, sim.startMonth, sim.seed) : history.current[target];
    if (saved) { history.current.length = target; setSim({ ...saved, pending: null, over: null }); setPlaying(false); }
  };
  const skip = () => { // run on until something asks for a decision
    if (!sim) return;
    let s = advance(sim);
    while (!s.pending && !s.over) s = advance(s);
    setSim(s); setPlaying(false);
  };

  if (!sim) return (
    <main className="m-simstart">
      <h1>내 가게를 6개월 동안 열어 봐요.</h1>
      <p>{profile.gu}, {store.pyeong}평, {stats.seats}석으로 엽니다. 날마다 손님이 오고 돈이 들어오고 나가요. 일이 생기면 멈춰서 어떻게 할지 물어봅니다.</p>
      <p className="m-label" id="sm">언제 여나요?</p>
      <div className="m-months" role="radiogroup" aria-labelledby="sm">
        {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => (
          <button type="button" key={m} role="radio" aria-checked={startMonth === m} onClick={() => setStartMonth(m)}>{m}월</button>
        ))}
      </div>
      <p className="m-src">여는 달에 따라 요일, 공휴일, 분기별 매출 흐름, 비 오는 날 수가 달라져요. {START_YEAR}년 달력으로 시작해요.</p>
      <div className="m-actions">
        <button type="button" className="m-btn" onClick={begin}>{startMonth}월 1일에 열기</button>
      </div>
      <button type="button" className="m-link" onClick={onBack}>가게 다시 꾸미기</button>
    </main>
  );

  const last = sim.rows.at(-1);
  const date = dateOf(sim.startMonth, Math.min(sim.day, DAYS - 1));
  const capacity = Math.min(stats.seats * SEAT_TURN, (levers.staff + 1) * COVERS_PER_STAFF);
  const filled = last && last.open ? Math.min(stats.seats, Math.round((last.covers / Math.max(1, capacity)) * stats.seats)) : 0;
  const start = sim.rows.length ? sim.rows[0].cash - sim.rows[0].net : sim.cash;
  const ops = opsOf(sim, profile, store, levers);
  const need = Math.ceil(ops.be.perDay);
  const stopped = Boolean(sim.over || sim.pending);

  return (
    <main className={`m-sim ${ledger ? "has-ledger" : ""}`}>
      <div className="m-hud">
        <div><Icon name="day" /><span>{date.getMonth() + 1}월 {date.getDate()}일 {dowKo(date.getDay())}요일{last?.holiday ? `, ${last.holiday}` : ""}</span><strong>{Math.min(sim.day + 1, DAYS)}일차 <small>/ {DAYS}일</small></strong></div>
        <div><Icon name="guest" /><span>오늘 손님{last?.rain ? ", 비" : ""}</span><strong>{last ? (last.open ? `${Math.round(last.covers)}명` : last.note) : "0명"}</strong></div>
        <div><Icon name="guests" /><span>지금까지 손님</span><strong>{Math.round(sim.guests).toLocaleString("ko-KR")}명</strong></div>
        <div>
          <Icon name="sat" /><span>만족도</span>
          <strong><button type="button" className="m-link" aria-expanded={showReviews} onClick={() => setShowReviews((v) => !v)}>{Math.round(sim.sat)}%, 리뷰 {sim.reviews.length}개</button></strong>
        </div>
        <div className={`m-hudcash ${sim.cash < 0 ? "is-short" : ""}`}>
          <Icon name="cash" /><span>현금</span><strong>{man(sim.cash)}</strong>
          {last && (
            <ul key={last.day} aria-live="off">
              {last.ticks.map((t) => <li key={t.label} className={t.amount >= 0 ? "in" : "out"}>{signed(t.amount)} <small>{t.label}</small></li>)}
            </ul>
          )}
        </div>
      </div>

      <div className="m-simbody">
        <section className="m-simstage">
          <div className="m-canvas">
            <GLGuard>
              <Canvas shadows camera={{ position: [w * 0.7, Math.max(w, d) * 1.2, d * 1.6], fov: 38 }} dpr={[1, 2]}>
                <ambientLight intensity={last && !last.open ? 0.6 : 1.15} />
                <directionalLight position={[-6, 12, 8]} intensity={last && !last.open ? 0.5 : 1.7} castShadow shadow-mapSize={[1024, 1024]}
                  shadow-camera-left={-12} shadow-camera-right={12} shadow-camera-top={12} shadow-camera-bottom={-12} />
                <Room w={w} d={d} grade={store.grade} />
                <Items items={store.items} />
                <Guests store={store} filled={filled} />
                <OrbitControls enablePan={false} target={[0, 0.4, 0]} minDistance={7} maxDistance={30} minPolarAngle={0.2} maxPolarAngle={1.35} />
              </Canvas>
            </GLGuard>
          </div>

          <div className="m-transport" role="toolbar" aria-label="재생 조작">
            <Ctrl icon="weekBack" label="일주일 전으로" onClick={() => rewind(7)} disabled={sim.day === 0} />
            <Ctrl icon="dayBack" label="하루 전으로" onClick={() => rewind(1)} disabled={sim.day === 0} />
            <Ctrl icon={playing && !fast ? "pause" : "play"} label={playing && !fast ? "멈춤" : "재생 (하루에 1초)"} className="is-main" disabled={stopped}
              onClick={() => { if (fast) { setFast(false); setPlaying(true); } else setPlaying((p) => !p); }} />
            <Ctrl icon={playing && fast ? "pause" : "fast"} label={playing && fast ? "멈춤" : "빨리 감기"} aria-pressed={playing && fast} disabled={stopped}
              onClick={() => { if (playing && fast) setPlaying(false); else { setFast(true); setPlaying(true); } }} />
            <Ctrl icon="skip" label="다음 일이 생길 때까지 건너뛰기" onClick={skip} disabled={stopped} />
          </div>

          {sim.pending && (
            <div className="m-event" role="dialog" aria-labelledby="ev-t">
              <h2 id="ev-t">{sim.pending.title}</h2>
              <p>{sim.pending.prompt}</p>
              <ul>
                {sim.pending.choices.map((c) => (
                  <li key={c.id}><button type="button" onClick={() => { setSim(choose(sim, c.id)); setFast(false); setPlaying(true); }}><b>{c.label}</b><small>{c.hint}{c.cash ? `. 바로 ${man(Math.abs(c.cash))}이 나가요.` : ""}</small></button></li>
                ))}
              </ul>
              <small>{sim.pending.basis}</small>
            </div>
          )}
          {showReviews && (
            <div className="m-reviews">
              <h2>손님 리뷰 <button type="button" className="m-link" onClick={() => setShowReviews(false)}>닫기</button></h2>
              {sim.reviews.length === 0 ? <p>아직 리뷰가 없어요.</p> : (
                <ul>{[...sim.reviews].reverse().slice(0, 12).map((r, i) => <li key={i}><b>별 {r.stars}개</b> {r.text} <small>{r.day + 1}일차</small></li>)}</ul>
              )}
            </div>
          )}
        </section>

        <section className="m-simside">
          <h2>날마다 남은 현금</h2>
          <CashLine sim={sim} start={start} />

          <div className="m-ops">
            <h2>장사가 되고 있나요?</h2>
            <dl>
              <div>
                <dt>본전이 되는 손님 수</dt>
                <dd>하루 {need}명</dd>
                <small>{ops.avg ? `최근 7일은 하루 ${Math.round(ops.avg)}명이 왔어요. ${ops.avg >= need ? `${Math.round(ops.avg) - need}명 넘겨요.` : `${need - Math.round(ops.avg)}명 모자라요.`}` : "다달이 나가는 돈을 손님 한 명이 남기는 돈으로 나눈 값이에요."}</small>
              </div>
              <div>
                <dt>{ops.monthly.length || 1}개월째 손익</dt>
                <dd className={ops.cur ? (ops.cur.profit >= 0 ? "in" : "out") : undefined}>{ops.cur ? signed(ops.cur.profit) : "0만원"}</dd>
                <small>{ops.firstBlack ? `${ops.firstBlack.m}개월째부터 한 달이 흑자로 끝났어요.` : "아직 흑자로 끝난 달이 없어요."} 월세와 급여를 날짜로 나눠 계산해요.</small>
              </div>
              <div>
                <dt>들인 돈 {man(ops.sunk)} 가운데</dt>
                <dd className={ops.earned >= 0 ? "in" : "out"}>{ops.earned >= 0 ? `${man(ops.earned)} 회수` : `${man(-ops.earned)} 더 까먹음`}</dd>
                <small>{ops.pace === null ? "두 주쯤 지나면 회수 시점을 어림해요." : ops.left === null ? "최근 30일 흐름으로는 돌아오지 않아요. 가격, 직원 수, 쉬는 날을 바꿔 보세요." : ops.left <= 0 ? "들인 돈을 모두 회수했어요." : `최근 30일 흐름이면 앞으로 약 ${span(ops.left)} 뒤에 모두 돌아와요.`}</small>
              </div>
            </dl>
          </div>

          <fieldset className="m-levers">
            <legend>내가 바꿀 수 있는 것</legend>
            <div className="m-stepper">
              <span id="lv-price">고기 1인분 가격</span>
              <button type="button" aria-label="1,000원 내리기" disabled={levers.price <= 14000} onClick={() => setLevers({ ...levers, price: levers.price - 1000 })}>−</button>
              <output aria-labelledby="lv-price">{levers.price.toLocaleString("ko-KR")}원</output>
              <button type="button" aria-label="1,000원 올리기" disabled={levers.price >= 25000} onClick={() => setLevers({ ...levers, price: levers.price + 1000 })}>+</button>
            </div>
            <div className="m-stepper">
              <span id="lv-staff">직원 수</span>
              <button type="button" aria-label="직원 1명 줄이기" disabled={levers.staff <= 0} onClick={() => setLevers({ ...levers, staff: levers.staff - 1 })}>−</button>
              <output aria-labelledby="lv-staff">{levers.staff}명</output>
              <button type="button" aria-label="직원 1명 늘리기" disabled={levers.staff >= 8} onClick={() => setLevers({ ...levers, staff: levers.staff + 1 })}>+</button>
            </div>
            <div className="m-seg" role="group" aria-label="쉬는 날">
              <button type="button" aria-pressed={levers.days === 26} onClick={() => setLevers({ ...levers, days: 26 })}>월요일 휴무</button>
              <button type="button" aria-pressed={levers.days === 30} onClick={() => setLevers({ ...levers, days: 30 })}>쉬는 날 없음</button>
            </div>
            <p className="m-src">바꾸면 다음 날부터 적용돼요. 지금 하루에 {Math.round(capacity)}명까지 받을 수 있어요. 쉬는 날을 없애면 급여가 그만큼 늘어요.</p>
          </fieldset>

          <div className="m-log">
            <h2>지금까지 생긴 일</h2>
            {sim.decisions.length === 0 ? <p className="m-src">아직 없어요. 한 달에 한 번쯤 일이 생겨요.</p> : (
              <ul>{sim.decisions.map((x) => <li key={x.event}><b>{x.day + 1}일차, {x.title}</b><span>{x.choice}. {x.outcome}</span></li>)}</ul>
            )}
          </div>
        </section>
      </div>

      {sim.over && (
        <section className="m-report">
          <h1>{sim.over === "closed"
            ? <>현금이 두 달 내리 바닥이라 <mark>{sim.day}일 만에 문을 닫았어요.</mark></>
            : sim.cash >= 0 ? <>6개월을 버텼고 현금 <mark>{man(sim.cash)}</mark>이 남았어요.</> : <>6개월을 버텼지만 현금이 <mark>{man(-sim.cash)}</mark> 모자라요.</>}</h1>
          <p className="m-sub">
            손님 {Math.round(sim.guests).toLocaleString("ko-KR")}명을 받았고 만족도는 {Math.round(sim.sat)}%로 끝났어요. 처음 현금은 {man(start)}이었어요.{" "}
            {ops.firstBlack ? `${ops.firstBlack.m}개월째부터 한 달이 흑자로 끝났어요.` : "흑자로 끝난 달은 없었어요."}{" "}
            {ops.left === null ? `들인 돈 ${man(ops.sunk)}은 마지막 30일 흐름으로는 돌아오지 않아요.` : ops.left <= 0 ? `들인 돈 ${man(ops.sunk)}을 모두 회수했어요.` : `들인 돈 ${man(ops.sunk)}은 마지막 30일 흐름이면 약 ${span(ops.left)} 더 걸려 돌아와요.`}
          </p>
          <table className="m-quote">
            <thead><tr><th scope="col">달</th><th scope="col">손님</th><th scope="col">돌려보낸 손님</th><th scope="col">매출</th><th scope="col">손익</th><th scope="col">현금 변화</th><th scope="col">달 끝 현금</th></tr></thead>
            <tbody>
              {ops.monthly.map((m) => (
                <tr key={m.m}><th scope="row">{m.m}개월째<small>비 {m.rain}일</small></th><td>{Math.round(m.guests).toLocaleString("ko-KR")}명</td><td>{Math.round(m.turned)}명</td><td>{man(m.revenue)}</td><td>{signed(m.profit)}</td><td>{signed(m.net)}</td><td>{man(m.cash)}</td></tr>
              ))}
            </tbody>
            <caption>손익은 그달 매출에서 재료비, 급여, 월세, 관리비, 사장 생활비, 이자를 뺀 값이에요. 현금 변화는 실제로 돈이 나간 날 기준이라 첫 달에는 급여가 빠져 있어요.</caption>
          </table>
          {sim.decisions.length > 0 && (
            <>
              <h2>생긴 일과 내 선택</h2>
              <ul className="m-decisions">{sim.decisions.map((x) => <li key={x.event}><b>{x.day + 1}일차, {x.title}</b><span>{x.choice}. {x.outcome}</span></li>)}</ul>
            </>
          )}
          <p className="m-src">같은 조건이면 같은 날에 같은 일이 생겨요. 선택을 바꿔 보려면 되감거나 처음부터 다시 하세요. 숫자의 근거는 <a href="#/sources">출처 보기</a>에 있어요.</p>
          <div className="m-actions m-actions-row">
            <button type="button" className="m-btn" onClick={() => { setSim(null); setPlaying(false); }}>처음부터 다시 하기</button>
            <button type="button" className="m-btn m-btn-quiet" onClick={onBack}>가게 다시 꾸미기</button>
          </div>
        </section>
      )}

      <Ledger rows={sim.rows} open={ledger} setOpen={setLedger} />
    </main>
  );
}
