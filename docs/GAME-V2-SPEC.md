# Game v2 spec: 대학로 삼겹살집 twin

_2026-10-01. Source of truth for the v2 build. Decisions by Keonhee: balanced management sim + interviewable
persona; guided story first, then the CEO plays hands-on; rich stylized low-poly 3D that carries information;
unsourced levers allowed only with an explicit modelled downside and a visible 가정 tag._

## 1. Why v2

v1 playtest (10-01): two clicks per month, a receipt where 9 of 10 numbers don't move, a 3D replay that never
reflects choices, no state across months, no way to lose, identical p50 every run, events that are really owner
decisions, and 22 team criteria (원산지, 형태, 리뷰, 청결, 마케팅 …) with zero effect. v2 fixes the model first,
then the experience.

## 2. Core loop (one month = one turn, 6-month season starting October)

1. **달력 + 사건**: the month opens with its real calendar context (10월 축제·중간고사, 11월, 12월 연말 회식,
   1월·2월 방학과 설, 3월 개강) and 0 to 2 external events drawn by month-specific probability (guided mode
   uses a script).
2. **운영 계획** (the main interaction): the player sets levers on one planning board, sees a live preview of
   the expected effect (fast estimate), then confirms.
3. **한 달 플레이**: the month is simulated stochastically (one actual draw, seeded); the 3D plays a
   representative night that reflects the plan and events (queue, prices on the menu board, staff count, 야장,
   weather, food on tables, reactions).
4. **정산**: profit waterfall (평소 OP to this month's OP by driver), cash balance, reputation change, review
   feed, owner's reaction line, where this draw landed in the p10–p90 range.
5. **상태 이월**: cash, reputation, regulars, staff fatigue, and lever settings carry into next month.

Win/lose: **폐업** when cash stays below zero at two consecutive month-ends (ties the game to the research's
survival label). Season score = ending cash vs 평소대로였다면 baseline, plus reputation. Show a 생존 badge
for surviving 6 months.

## 3. State variables (persist across months)

| State | Start (가정 unless sourced) | Moves with |
|---|---|---|
| 현금 (운영자금) | ₩2,000만 (가정) | monthly OP (after owner wage) |
| 평판: 평점 (1–5) and 리뷰 수 | 4.2, 180 (가정) | satisfaction of parties → review probability by segment |
| 인지도 | index 1.0 | marketing, viral events, review count |
| 단골 비율 | 25% (가정) | satisfaction, consistency of price/quality |
| 직원 피로 | 0–100 | load per staff hour; high fatigue → service slows, quit-event probability |
| 레버 상태 | current plan | player |

Demand multiplier from reputation: +1 star ≈ +5–9% revenue for independents (Luca, HBS; source in
ontology/sources.csv or add). Review probability, satisfaction weights, fatigue dynamics = 가정 with stated
downside, tagged in UI.

## 4. Levers (planning board), each with upside AND modelled downside

| Group | Lever | Upside | Downside (must be modelled) |
|---|---|---|---|
| 가격 | 삼겹 1인분 가격 (slider) | 객단가 | demand via elasticity; satisfaction vs price expectation |
| 가격 | 소주 가격 | margin | alcohol per person, satisfaction |
| 품질 | 원육 (수입 냉동 / 국내산 / 숙성) | satisfaction, reviews, price tolerance | meat cost per 인분 |
| 메뉴 | 형태 추가 (냉삼, 통삼, 시그니처 곁들임 미나리 등) | 인지도, segment appeal | cost, prep time, menu complexity |
| 메뉴 | 반찬 가짓수 | satisfaction | cost per cover |
| 서비스 | 직원이 구워주기 on/off | satisfaction, 회식 appeal | staff time per table, dwell ↑ |
| 인력 | 알바 수 per shift (0–4) | service speed, fatigue ↓ | labor cost |
| 운영 | 영업시간 (마감 23/24/01시), 점심 영업 on/off | covers | labor, utilities, fatigue |
| 공간 | 야장 on/off | seats in good weather | weather risk, noise complaint event |
| 마케팅 | 리뷰이벤트, SNS 협찬 예산 | reviews, 인지도 | cost, review-quality noise |
| 예약 | 단체·회식 예약 받기 | 12월 회식 demand | walk-in seats blocked, no-show risk |
| 위생 | 청결 관리 수준 | rating stability, 위생점검 pass | labor time |

Every lever without a source carries a 가정 tag and its downside is shown on the card. A guard test keeps
"no lever setting dominates every month" (extend the existing dominance test to the plan space by sampling).

## 5. External events (no owner decisions here)

원가: 돼지고기 도매가 ±, 수입육 단가, 채소값(쌈채소) · 고정비: 재계약 임대료, 최저임금 · 수요: 방학, 시험기간,
개강, 연말 회식 시즌, 대학로 공연·축제 주간, 설 연휴 · 날씨: 비 주간, 한파 · 경쟁: 근처 고깃집 개점·폐업 ·
평판: 맛집 블로거 방문(바이럴), 악성 리뷰, 위생점검 · 인력: 알바 갑작스런 퇴사, 사장님 몸살.
Each has a month-dependent probability, a mechanism, and a source or 가정 tag.

## 6. Calendar from data

Monthly demand index for 3120012 한식 from the quarterly sales (Q split to months by an assumption, tagged)
plus known events (12월 회식, 1·2월 방학/설, 3월 개강). Weather from 기상청 normals by month.

## 7. Modes

- **시연 모드 (guided)**: scripted 4-month story with narration cards for the presenter (e.g. 10월 normal,
  11월 pork price spike → reprice decision, 12월 회식 season with 예약 lever, 1월 방학 + 경쟁점 → survival
  pressure). Works fully offline from precomputed data.
- **자유 플레이**: tutorial overlay (3 steps), goal = survive 6 months and beat the baseline; random events;
  needs the local API.
- **비교 (sandbox)**: two plans side by side for one month, same seed, with the waterfall difference.

## 8. Persona layer (interviewable twin)

- **사장님** is a visible character in the store (apron, distinct model). At each event the owner reacts in a
  short dialogue (LLM via the guarded adapter, or template) and can be questioned.
- **손님 리뷰 피드**: each month, simulated parties write short reviews in their segment's voice (20대 모임,
  직장인 회식, 동네 가족), driven by what actually happened to them (wait, price, quality, service).
  Click a review to question that customer persona.
- **트윈 인터뷰 (설문 모드)**: a standard 소상공인 survey (about 15 items: 매출 추이, 가장 큰 비용, 가격 인상
  의향, 애로사항, 인력 문제, 상권 평가 …) answered by the owner twin from its current state, each answer citing
  state values or sources. Same question set as research/interview/owner_interview_guide.md, so one real
  interview can be compared item by item (인터뷰 1명 = 트윈 1개).

## 9. 3D information design (rich stylized low-poly)

Correct human/table proportions; exhaust ducts that hang from a visible ceiling; walls that hide on camera
side; first-person collision. Storefront with a Korean sign (composite name, e.g. "대학로 삼겹살") and lighting
from dusk to neon night. **Menu board shows live prices** from the plan. Queue outside when waiting; meat on
grills and soju bottles that accumulate per table in proportion to orders; grill smoke; staff count = plan,
moving faster under load; owner character; speech bubbles from the review engine ("비싸다", "고기 좋다",
"너무 오래 기다림"); rain/snow when the event says so; 야장 with string lights; competitor storefront across
the street when that event is active; floating ₩ when a table pays. Night replay reflects plan + events.

## 10. Information design

Profit waterfall each month; cash runway line; reputation sparkline; district layer (27 stores, rent ×3,
survival curves) reachable from the minimap; 능력치 tree highlights the drivers this month moved; every
가정 tag clickable to its rationale. Keep 검토 N/82.

## 11. Contracts (so builders can work in parallel)

- `sim.season` (Python): `new_season(seed, mode) -> SeasonState`; `preview(state, plan) -> PlanPreview`;
  `play_month(state, plan, events) -> MonthResult`. MonthResult JSON = {month, calendar, events[], plan,
  draw: {kpis, p10, p50, p90}, waterfall[], state_after, reviews[], owner_line, night_events[] (EVENT_LOG
  schema + bubbles), labels[] (가정/source per mechanism)}.
- API: `POST /season` → id + state; `POST /season/{id}/preview` {plan}; `POST /season/{id}/play` {plan} →
  MonthResult; `GET /season/{id}`; `POST /persona/{id}/ask` {who: owner|review_id, question};
  `GET /season/{id}/survey` (twin answers). Guided mode reads `web/public/guided/*.json` (precomputed
  MonthResults).
- Web reads only these shapes.

### 11.1 Shapes as `sim/season.py` emits them (2026-10-01; web/src/v2/types.ts mirrors this)

- **Plan** keys: `meat_price, soju_price, meat_grade (imported|domestic|aged), menu_extras [naengsam|tongsam|minari],
  banchan, staff_grilling, staff_per_shift (0-4), close_hour (23|24|25), lunch, terrace, marketing_budget,
  review_event, group_reservations, hygiene (basic|normal|high)`. Missing keys take `base_plan()`.
- **SeasonState**: `engine, mode, seed, month_index, cash, rating (= rating_recent: last 30 reviews, drives demand),
  rating_recent, rating_all (count-weighted mean of every review), review_count, awareness, regular_share, fatigue,
  negative_months, low_revenue_months, closed, closed_reason (cash|revenue|null), plan, flags {competitor, rent_mult,
  wage_mult}, history [{month, label, op, cash, rating, events}]`, plus `season_over` after the last month.
- **MonthResult**: `engine, month (10..3), month_index, calendar {label, note, demand_index, tags}, events [{id,
  label, group, mechanism, tag, outcome?}], plan, draw {kpis, p10, p50, p90, op_percentile, band_runs},
  demand_factors, shadow {basis, kpis} (this month, base plan, same state, events and seed: 평소대로였다면),
  waterfall [{driver, key, delta, kind: start|step|end, note}] (starts from shadow.kpis.op, ends at draw op),
  state_before, state_after, reviews [{id,
  month, segment, segment_ko, stars, party_size, wait_min, service_wait_min, walked_away, satisfaction, drivers,
  reason_codes (incl. comped, reviews_inflated), incentivized, night, dow}] (max 12), reviews_total, owner_line {mood (from cash runway), text, codes, placeholder, net_vs_shadow, runway_months,
  top_positive {driver, delta}, top_negative {driver, delta}},
  night_events [{night: {dow, rain, weather (clear|rain|snow), terrace_open, tables_available, servers, open_clock, close_hour}}, ...EVENT_LOG
  events (a typical Saturday: closest of 8 draws to the mean arrivals; booked 회식 on the held table carry
  group: true), leave/balk events may carry satisfaction and bubble {code, text}], labels [{mechanism, label, tag,
  downside?, detail?}], season_end (null until the last month or 폐업) {cash, forward_value (6-month OP forecast on the base plan
  from the ending reputation; minus the S89 closure cost if closed), reputation_effect, store_value (= cash +
  forward_value), label, horizon_months, closed, tag, basis?, drivers? {rating|regular_share|awareness: {end, start}}}`. The end screen shows cash (the
  score the guards use) and store_value (가게 가치, 가정 horizon).
- **kpis** keys: `revenue, op, op_margin, covers, dinner_covers, ticket, walkaways, avg_wait_min, table_utilization,
  staff_load, alcohol_share, cogs, labor, rent, mgmt, fees, lunch_revenue, group_revenue, groups` (+ `satisfaction,
  reviews` on the draw).
- **PlanPreview** (`preview(state, plan)`; events default to this month's draw, the same ones play uses): `engine, estimate, month, calendar {label, demand_index}, events, plan, expected {revenue, op,
  op_margin, covers, ticket, walkaways, staff_load, satisfaction, satisfaction_loyal, cogs, labor, rent, mgmt, fees, lunch_revenue,
  group_revenue}, state_next {fatigue, quit_risk, cash}, vs_base {op, revenue, base_op, basis} (vs the base plan this month with the same events), op_range {p10, p90, error, overload, tag} (DES spread + the preview's own measured error), risks [{id, label, prob, op_delta, tag}], lunch {revenue,
  cost, net} | null, warnings [text], warning_codes [code incl. lunch_negative, risk:<event id>], labels`.
- **Guided** (`web/public/guided/index.json`): `{engine, mode, seed, start, baseline_op, illustrative, note, story:
  [{n, month, label, title, events, narration [], decision {prompt, options [{id, label, changes, file, op,
  revenue, cash_after, rating_after, regular_share_after, p10_op, p90_op, followup [{month, label, op, covers, cash,
  rating, regular_share, scripted, store_value? (last row)}], next_line}]}, story_choice}], representative,
  representative_note, summary {title, basis, branches [{month, label, option, option_label, is_story, cash,
  store_value, regular_share, rating, end_label}], takeaways [text generated from the numbers]}}`; each `file` is a MonthResult (with `representative: true`). `followup` plays the remaining
  story months from that option (same events, the story's later choices on top), then holds the plan to the season
  end with no scripted events (`scripted: false`). `next_line` is the "다음 달에 나타나는 결과" text, comparing it
  with the story path at the last story month and at the season end. Guided months use a shared customer stream on
  which every option's draw sits near its own median, so a demo month never rests on one option's luck.

### 11.2 What the web needs (web agent, 2026-10-01)

The web reads the 11.1 shapes as they are (web/src/v2/types.ts). On top of them it relies on:

- **Persona text on every MonthResult**, API and guided files alike: `reviews[].text`, `owner_line.text`,
  `owner_line.event_lines`. Without text the web falls back to a short template from `reason_codes`.
- **Night header**: `night.weather` (rain/snow/clear), `night.servers` (staff = servers − 1 owner),
  `night.terrace_open`; leave/balk events with `bubble {code, text}` (the text is drawn as a speech bubble).
- **Competitor**: `state_after.flags.competitor` or an event `competitor_open` puts the rival shop across the street.
- **Luck vs skill**: `draw.op_percentile` and `draw.band_runs` (shown under the p10-p90 band).
- **End screen**: `labels` entries `closure_cash` and `closure_revenue` (both 폐업 rules with tags) and
  `state_after.closed_reason`.
- **평소대로였다면 baseline**: free play opens a second season `POST /season {mode: "sandbox", seed: <same>}` and
  plays the base plan each month with the player's month events (`POST /season/{id}/play {plan, events}`). Persona
  text for sandbox seasons is not shown, so the API may skip the LLM call when `mode == "sandbox"`.
- **비교**: two sandbox seasons with one seed, one month each.
- **Latency**: preview under 1 s (called on every lever change, debounced 220 ms); play under 5 s;
  `GET /season/{id}/survey` under 5 s (today it can take 30-120 s on a fresh API, which times the e2e out).
- **Offline metadata**: `web/scripts/sync_season.py` copies research/season_params.yaml, events.yaml,
  calendar.yaml, ontology/sources.csv, the survival curves and rent benchmarks BM42-44 into
  `web/public/data/season.json` for the 가정 popovers and the district layer. Rerun it when those files change.
- **e2e selectors** (tests/e2e/v2_season.mjs and game_v2.mjs): route `#/v2` (also `#/`); `mode-guided`,
  `mode-free`, `mode-compare`; `plan-board`, `input[data-lever=meat_price]`, `[data-lever=<key>] button`,
  role=switch with the lever label, `preview[data-op]`, `play`; guided `[data-option=<id>]` plays that option;
  `transport`, `skip`, `settlement`, `settle-op[data-value]`, `hud-cash|hud-rating|hud-fatigue[data-value]`,
  `owner-line`, `button[data-review=<id>]` (all reviews), `next`; `ask-owner`, `ask-panel` (input aria-label
  질문, button 보내기), `ask-answer[data-who][data-backend]`; `open-interview`, `survey-item[data-q]`,
  `survey-answer`; `end-closed` / `end-survived`, `vs-baseline`, `closure-rules`; `compare-run`, `compare-table`.

## 12. Interactivity (sim contract, 2026-10-01; research/2026-10-01-sim-game-interactivity-best-practices.md top 8)

Decisions move inside the night, every number names its cause, and the planning board shows which way each lever
pushes before the player commits. `sim/season.py` owns these shapes; web reads them, API passes them through.

### 12.1 In-night decision points (research #2, #7)

Two-step month:

- `start_month(state, plan, events=None) -> MonthStart`:
  `{engine, month, month_index, calendar, events[], plan, night: {night: {header as 11.1}, events: [EVENT_LOG up to
  and including the first decision point's clock]}, decision_points: [DecisionPoint], seed}`. No KPIs. Deterministic
  by (state, plan, events).
- `play_month(state, plan, events=None, *, night_choices={dp_id: option_id}) -> MonthResult` (11.1 shape plus the
  fields below). An omitted choice takes the decision point's `default` option. The night prefix before each
  decision is identical to `start_month`'s.
- DecisionPoint: `{id, kind, clock_min (minutes after 17:00), clock, prompt_ko, default, monthly_count, count_tag,
  options: [{id, label_ko, effect_hint_ko, tag ("근거" | "가정"), source_id?, downside_ko}]}`. 1-2 per night, drawn
  (seeded) from `research/events.yaml` `_night_decisions` when their condition holds (e.g. the terrace is open for
  a rain burst). Kinds: walkin_group (10-12 without booking at a full house), staff_late (an 알바 calls in late),
  meat_low (a cut runs low at 21시), rain_burst (sudden rain on the 야장), blogger (a food blogger asks for a free
  meal).
- What a choice does: (1) the night's remaining events are re-simulated from `clock_min` on the same customer
  stream (seat the group: two tables held 150 min, the queue grows; buy meat in a hurry: a cost line; ...). (2) The
  month KPIs move by `monthly_count` (how many such situations a month has; 가정 where unsourced) x the night's
  difference between the chosen branch and a night without the situation (revenue, food cost, labor, extra costs,
  covers, walk-aways, satisfaction). (3) Direct state effects per occurrence (fatigue, 인지도, rating), x
  `monthly_count`.
- MonthResult adds `night_decisions: [{id, kind, option_id, monthly_count, night_delta {revenue, op, covers,
  walkaways, satisfaction}, month_delta {revenue, op}, vs_default_op, state_delta {...}}]` and `decision_points`;
  each also appears as its own waterfall line (`key: "dp:<id>"`, `kind: "step"`, delta = chosen vs default
  handling; the 평소 shadow handles every situation the default way).
- Every option has a modelled downside. Guard (Pareto): no option is at least as good on month OP, night
  satisfaction and state effects as every other option (noise counts as a tie: OP 5만, satisfaction 0.5), and
  better on one, in every sampled state where its decision appears.
- Decision clocks come from the night: a walk-in 회식 only at a full house with a queue (18:30-21:00), a rain burst
  when the most 야장 tables are taken. `title_ko` names the situation.

### 12.2 Consequence data on the planning board (research #3)

`preview(...)` adds `sensitivity: {lever: {up: Delta | null, down: Delta | null, step}}` with `Delta = {op, covers,
rating_recent, fatigue}` as changes and `runway_months` as the variant's absolute cash runway (null = not losing money),
for one step of that lever from the current plan (analytic, same month and
events; null where the lever cannot move further). Steps: meat_price ±1,000, soju_price ±500, meat_grade
next/previous, menu_extras add/remove one, banchan ±1, staff_per_shift ±1, close_hour ±1, marketing_budget ±500,000,
hygiene next/previous; booleans toggle (up = on, down = off; the current state is null).

### 12.3 Cause links (research #4)

- Each waterfall step adds `levers: [lever keys that differ from the base plan and move this line]`, `events:
  [month event ids that move it]`, and `decisions: [dp ids]`.
- Each review adds `cause_levers: [lever keys behind its reason codes]` and `cause_events: [month event ids behind
  them]`.
- Each review adds `cause_decisions: [dp ids]` and `decision_party: dp id | null`. Month reviews have none. Reviews from
  the decision night (`from_decision_night: true`, listed first, count in `decision_reviews`) come from parties a
  decision touched: its own party, a flagged party, or one whose wait, service or bill changed against the same night
  without the decisions. They write at twice the usual rate (가정); a comped blogger always writes.
  `decision_options: {dp id: option}`. Unknown decision ids in `night_choices` raise.

### 12.4 Night events with mood (research #5)

Every EVENT_LOG event that belongs to a party carries `satisfaction` (0-1, that party's score), `spend` (the party's
final bill; 0 for a walk-away), and `reason` (its top reason code, the same vocabulary as reviews and bubbles).
Group-booking and decision-point parties carry them too.

### 12.5 Guided decisions (research #7)

`web/public/guided/index.json` story steps add `night_decision: {decision_point, story_option, branches: [{option_id,
label_ko, file, op, cash_after, next_line}]}`: one in-night decision per month on the story's chosen plan, both
branches precomputed (each file a MonthResult), so presenter mode can let the room decide offline. The story chain
continues on `story_option`. The month's first decision of a kind not shown earlier in the story is used, so the room sees a
different situation each month; the default branch is the story's own file, other branches are
`<story file>__<kind>_<option>.json`.

`start_month`'s prefix carries mood, spend and reason only for parties that finished before the first decision (the
others' outcome depends on it).

## 14. Season report (sim contract, 2026-10-01; `sim/report.py`)

Keonhee: "a queryable system, a csv or report for the user at the end on what to improve". Pure functions over a
played season `season = {seed, mode, months: [MonthResult], state}` (the API session). `api/report.py` serves them
(GET /season/{id}/report, CSV, print) and uses them automatically.

- `season_table(season) -> [Row]`, one per played month: `month_index, month, month_label, events, event_ids,
  lever_<key>` for all 14 levers, `levers_changed, levers_changed_keys, decisions, night_choices [{id, title_ko,
  option_id, option_ko, vs_default_op}]`, `prediction, prediction_metric, prediction_actual, prediction_error_pct`,
  `revenue, op, covers, walkaways, shadow_op, net_vs_shadow, p10_op, p50_op, p90_op, op_percentile (= band_position),
  rating_after, rating_recent, regular_share, fatigue, cash_after, waterfall`.
- `improvements(season, top=5) -> [Improvement]`. For every month, each lever's best other value and each night
  choice's best other option are re-estimated over that month and the rest of the season: same state before the
  month, same events, the player's later plans. Lever alternatives use the analytic path (step_estimate) and are
  compared with the same path for what was played, so the estimator's bias cancels; night choices re-play the
  month's own night. Ranked by 가게 가치 gained per month of change; an alternative that lowers 가게 가치 is never an
  improvement. Adjacent months with the same change merge into one item (`month_indices`, `month_label` "11월~1월",
  `alt_plans {month_index: plan}`), re-estimated jointly; at most 2 of the top 5 per lever (or decision kind).
  `store_value_per_month` is the ranking key.
  DES re-scoring (2026-10-02): the analytic top 10 lever candidates are re-run as paired DES paths (8 seeds, the same
  seeds for the alternative and for what was played). The months' outside events stay fixed; the plan-driven ones
  (staff_quit, owner_sick, noise_complaint, aged_spoilage) are redrawn from each run's own state. A lever item is kept
  only if the DES confirms it (same sign, within 2x on 가게 가치), and it then carries the DES numbers
  (`analytic {..}`, `des {cash_delta, store_value_delta, regular_share_delta, runs, store_value_se}`, `agree`).
  `uncertain(season)` lists the unconfirmed ones with `note_ko`. Night-choice items come from a re-played night.
  A cold report is about 4 s on a 12-process pool; `warm(season)` precomputes it (call it in the background after the
  last month), after which a report is instant. Item: `{id, kind (lever | night_choice),
  month_index, month_label, lever | decision, lever_ko | decision_ko, from, to, from_ko, to_ko, alt_plan,
  alt_night_choices?, cash_delta, store_value_delta, regular_share_delta, rating_delta, cost (₩ the alternative
  spends more that month), downside_ko, confidence {sourced_share, tag, values}, tag (근거 | 가정), basis, takeaway_ko,
  why_ko}`. `takeaway_ko` is generated from the numbers, e.g. "11월에 소주 가격을 9,000원에서 4,500원으로 바꿨다면, 시즌
  끝 현금 +543만 원, 가게 가치 ...".
- `cash_only(season, top=3)` (현금만 늘리는 선택, 주의): alternatives that would have raised season-end cash but lowered
  가게 가치, same item shape plus `warning_ko` with both numbers.
- An open store's 6-month forecast is floored at minus the closure cost (S89): an owner can always close.
- Replays use each month's `state_seed` (the seed it was played with; guided months use a representative stream).
- `good_decisions(season, top=3)`: levers set away from 평소 that beat going back to 평소 on the same path, and night
  choices that beat every other option: `{month_index, month_label, kind, lever | decision, levers, what_ko, why_ko,
  cash_delta, store_value_delta, regular_share_delta, rating_delta, net_vs_shadow}`.
- `luck_months(season)`: the month sits in the outer fifth of its own band and the draw's distance from the band
  median exceeds the plan's effect (median − 평소): `{month_index, month_label, band_position, op, p10_op, p50_op,
  p90_op, luck_won, plan_effect_won, luck, luck_ko}`.
- `season_summary(season, review=None)`: `months_played, total_op, total_shadow_op, total_vs_shadow, ending_cash,
  ending_rating, ending_regular_share, store_value, closed, closed_reason, closed_reason_ko, best_month, worst_month,
  prediction_months, prediction_mean_abs_error_pct, review {reviewed, total}, caveat_ko` (검토 N/82; review counts
  from the API, else web/public/data/hero.json).
- Tests: a planted bad lever (soju ₩9,000 in 11월; imported meat in 12월) is the #1 improvement (mutation: judging
  alternatives backwards fails it); counterfactuals are deterministic; summary totals, improvement months and
  from-values, and luck-month numbers trace to the table. A full report on a 6-month season takes about 2 s.

## 15. Definition of done

- Played end to end by Claude (headless) as a player: every month at least 5 meaningful decisions, visible
  consequences in 3D and 정산, at least one lose path and one win path reachable.
- Dominance guard over sampled plans; tests green; make e2e covers guided + free modes.
- Every unsourced mechanism tagged 가정 with its downside; no number on screen without a label.
