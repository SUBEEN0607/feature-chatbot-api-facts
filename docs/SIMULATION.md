# Simulation engine (`sim/`)

A discrete-event model (SimPy) of the composite hero store: a 미도입 independent 삼겹살집 in 대학로(혜화역),
상권 3120012. **Every number it produces is illustrative.** The inputs are seed guesstimates that have not
been reviewed yet (see `research/guesstimate.xlsx`, column `reviewed_by`).

```
python -m sim.run --shock none --runs 200 --out out/base
python -m sim.run --shock SH03 --runs 200 --out out/sh03
python -m sim.run --shock all  --runs 200 --out out/all      # every shock + summary.json
python -m pytest sim/tests -q
```

## Inputs

| File | Written by | Used for |
|---|---|---|
| `research/hero_base.yaml` | `research/build_workbook.py` | every store parameter, keyed by `criterion_id`; `_pnl_base` = the workbook P&L (calibration target) |
| `research/shocks.yaml` | same, from the Shocks sheet | shock catalog (`--yaml-from-xlsx` re-exports after members edit the workbook) |
| `data/processed/district_profile.json` | pipelines | 요일 and time-band sales shares for 3120012, averaged over the latest 4 quarters (weighted by sales) |
| `industry/pork_bbq.yaml` | pipelines | which 상권 is primary |

## Model

**One night** (17:00 → close, `drv_open_hours` = 7):

1. **Arrivals.** Non-homogeneous Poisson, piecewise constant in 15-minute slots. Expected parties per night =
   `drv_arrival_rate` (14.2, derived in the workbook from P&L covers ÷ (1 − `drv_balk_rate`) ÷ `mkt_party_size`)
   × the 요일 factor (that day's sales share ÷ the mean over open days; Monday is closed).
   Shape: card sales are stamped at **payment**, so a party arriving at t is weighted by the sales
   intensity of the time band that contains t + `drv_dwell_time`. No seatings in the last hour.
2. **Customer segment and party size.** Each party is 20대 친구 모임 (`twenties`), 직장인 회식 (`office`) or
   동네 가족 (`family`). P(segment | arrival slot) ∝ the segment's card-sales age share in 3120012 (twenties =
   10대+20대, office = 30대+40대, family = 50대+60대 이상) × `seg_<s>_early_mult` before 19:00 or
   `seg_<s>_late_mult` from 21:00. The segment scales party size, dwell, bottles per person and patience
   through `seg_<s>_party_factor`, `_dwell_factor`, `_alcohol_factor` and `_patience_factor`. These are relative
   factors: each is rescaled so the store-wide mean still equals `mkt_party_size`, `drv_dwell_time`,
   `prd_alcohol_per_cover` (cover-weighted) and `mkt_patience`, so segments change who comes when and how they
   behave without moving the calibrated totals. Party size is 1 + Binomial(3, p) with the segment's mean, max 4
   (every table is a 4-top). The base mix comes out at about 25% twenties, 39% office, 36% family (parties).
   All 18 segment parameters are HeroStore rows with confidence L (no source).
3. **Tables.** `sto_tables` indoor 4-tops, plus `sto_terrace` ÷ 4 야장 tables on nights the terrace is open.
   Each night it is open with probability `sto_terrace_availability`. Indoor tables are filled first.
4. **Queue and walk-aways.** A party with no free table waits. Its patience is Gamma(shape 4, mean
   `mkt_patience`); when the wait exceeds it, the party walks away (`balk` event).
5. **Orders.** Target portions = `prd_portions_per_cover` × size. The first order is ceil(0.75 × target),
   and the rest is a Poisson re-order mid-meal, so expected portions match the parameter. Bottles are
   Poisson(`prd_alcohol_per_cover` × size). Meals are Binomial(size, `prd_side_spend_per_cover` ÷ ₩7,000).
   Prices: `prd_meat_price`, `prd_alcohol_price`, meal ₩7,000.
6. **Dwell.** Mean = `drv_dwell_time` × 0.85 if `prd_chobeol` × 0.90 if `svc_staff_grilling`, × (1 + 0.3 ×
   relative change in bottles per cover). Lognormal noise (σ 0.36, matching the dwell CV of 0.37 in Kimes & Robson
   2004, S72).
7. **Staff.** Servers = `sto_parttimers` + the owner. They are a capacity-limited SimPy resource. Every
   party needs a server for:
   - the first order (+10 min if staff grill);
   - a mid-meal visit (0.5 min per bottle, + 1.5 min if re-ordering);
   - payment (2 min, while the table is still held);
   - clearing (4 min; the table stays blocked until it is cleared).

   Fewer servers → slower turnover → longer waits → more walk-aways.

**Month.** `sto_open_days` (26) nights, cycling Tue→Sun, with the terrace drawn per night. Costs use the
workbook P&L's arithmetic on simulated quantities:
- **Food:** portions × `cst_meat_cost_per_portion` + bottles × `cst_alcohol_cost_per_bottle` + meals ×
  ₩7,000 × `cst_side_cost_ratio` + covers × `cst_banchan_cost_per_cover`.
- **Labor:** `sto_parttimers` × `sto_parttime_shift_hours` × nights × `sto_parttime_wage` ×
  `cst_holiday_pay_factor` + `sto_employees` × `cst_employee_wage` + `cst_owner_imputed_wage`.
- **Fixed and fees:** `drv_rent`; `cst_utilities` + `cst_other_opex`; fees = revenue × `cst_card_share` ×
  `cst_card_fee_rate`.

**Monte Carlo.** N months (default 200). Each run gets a child seed. Base and shock runs share seeds
(common random numbers), so their difference is the shock, not noise. Per run, the price elasticity is
drawn from triangular(−2.5, −0.81, −0.3) (`mkt_price_elasticity`, confidence L: −0.81 is the category-level FAFH meta-analysis value, S58; one store among 27 nearby 고깃집 is likely more elastic, so the high end is −2.5), and each shock delta is drawn from
triangular(low, base, high). The output is p10/p50/p90 for: covers, revenue, 객단가, table utilization,
average wait, walk-aways, labor hours, COGS, OP, OP margin, RevPASH, alcohol share, and arrivals.

**Price response.** Arrivals × (meat price ÷ reference price)^ε. Bottles per cover × (soju price ÷
reference)^ε. The reference is the unshocked base, kept in `params['_ref']`. This is an assumption: the
research files contain no measured elasticity.

## Shocks (`research/shocks.yaml`, main profit drivers only; tech adoption out of scope)

| id | parameter(s) | base delta |
|---|---|---|
| SH01 / SH02 | `prd_meat_price` | +10% / −10% (elasticity range above) |
| SH03 | `cst_meat_cost_per_portion` | +8% (low +5%, high +28%; KMTA 삼겹 wholesale: annual +8.1%, Jan→Aug +28%) |
| SH04 | `prd_alcohol_price` | +₩1,000 |
| SH05 | `prd_alcohol_per_cover` | −20% |
| SH06 | `sto_parttime_wage` | +5% |
| SH07 | `sto_parttimers` | −1 per shift |
| SH08 | `drv_rent` | +5% at renewal (statutory cap, S57); the high +15% is only possible on a new lease |
| SH09 | `drv_arrival_rate` | −8% (low −5%, high −15%; 3120012 Q3 vs Q2 card sales → −6% to −11% per break month) |
| SH10 | `wx_rain_nights_share` = 19% (13–35%) | an average October: rainy nights close the terrace, −10% arrivals each |
| SH10b | `wx_rain_nights_share` = 100% | every night rains (worst case) |
| SH11 | `reg_competitors` +1, `drv_arrival_rate` −10% | nearby competitor opens |

Each run prints the mechanism, the assumption, the confidence and the source from the Shocks sheet.
`sim/owner_actions.py` holds the owner's reaction menu as pure functions: absorb, reprice, reprice_alcohol,
cut_staff_hours, cut_staff, change_mix. An LLM owner agent picks one and its arguments, and the sim reruns
with the result. There are no LLM calls in `sim/`.

## Decision-page defaults (flags in `industry/pork_bbq.yaml` → `game:`)

Each decision runs on the recommended option and is one line to switch; rerun `python -m sim.precompute` after.

- **2.1 `l_mechanism_badge: true`.** `sim/evidence.py` lists which mechanisms each shock and owner action rests on
  and how well each is evidenced. A card whose effect rests on a confidence-L mechanism shows "인터뷰로 확인 필요"
  with a one-line reason; nothing is hidden. Flagged now:
  - staff service minutes: SH07, 교대당 알바 1명 줄이기;
  - staff hours: 알바 근무 1시간 줄이기;
  - soju elasticity: SH04, 소주 500원 올리기;
  - upselling: 술과 식사 더 권하기;
  - dwell vs drinking: SH05;
  - rainy-night demand: SH10, SH10b;
  - competitor split: SH11.
- **2.2 `peak_reshape: true`.** The card data only gives the 17–21 band total. Inside it, arrivals are split
  12% / 23% / 33% / 32% per hour (17, 18, 19, 20h), an assumed 삼겹살 peak at 19–21 (`SIM_ASSUMPTIONS.peak_hour_weights_17_21`,
  confidence L). The band total is unchanged (`test_peak_reshape_keeps_band_total_and_moves_peak`). The busier peak
  fills the tables on Friday and Saturday evenings. The measured walk-away rate is now about 1%, and the workbook
  prior is reset to 1%. The sim month sits at revenue −1.9% vs the workbook (p50) and OP margin 3.4% vs 4.6%,
  because some peak demand cannot be seated.
- **2.3 `rain_mode: average_october`.** SH10 is now a normal October: rainy nights = 기상청 10월 전국 평년 강수일수 5.9일
  (1991~2020) ÷ 31 = 19% of nights, range 13–35% (2024 had 11 days; S75). The Seoul station normal was not reached,
  so the national value stands in. Each rainy night closes the terrace and cuts arrivals by
  `wx_rain_arrival_effect` (−10%, L). SH10b keeps the every-night worst case; `rain_mode: every_night` makes SH10
  the worst case again.
- **3.2 `season_months: 6`, `carry_state: true`.** See "Season mode" below.

## Season mode v1 (decision 3.2; `sim/season_v1.py`, the v1 game)

A season is `season_months` (6) months. Each month draws one event, and the owner picks one action. Price, staff
and menu choices **persist** (`carry_state: true`), so the next month starts from them. `sim/season_v1.py` defines
the lasting state as five levers (`sim/season_v1.py`):
- price step: −5% / 0 / +5%;
- soju +₩500;
- part-timer shift −1 h;
- one fewer part-timer;
- upselling.

"그대로 버티기" keeps the state. Choosing a lever that is already applied changes nothing, and its card says so.
A month's outcome depends only on (state after the choice, this month's shock). `python -m sim.precompute --season`
therefore writes every one of the 48 states × 12 shocks (200 runs each) to `web/public/runs/season/`. Every
season path is covered offline. Month 1 equals the single-month files exactly (`test_season_grid_matches_single_month_run`).

The 3D replay of a season month shows the single-month night for that event and choice. It is labelled as an
illustrative night, because lasting levers are not replayed. The season summary shows:
- the cumulative operating profit against "평소대로였다면" (N × the base month);
- the best and the worst month;
- a list of months, each of whose receipts can be reopened.

## Season engine v2 (`sim/season.py`, docs/GAME-V2-SPEC.md §2-7)

One month = one turn, October to March. Inputs live in three tagged data files: `research/season_params.yaml`
(levers, satisfaction, reviews, fatigue, closure), `research/calendar.yaml` (monthly demand index, segment mix,
terrace, group bookings) and `research/events.yaml` (17 events with monthly probabilities and effects). Every value
carries a source id or 가정; round 4 (`research/sourcing_round4_v2.md`) is applied.

**API.** `new_season(seed, mode)` → state. `draw_events(state)` → this month's event ids (seeded by seed and
month; at most two random events, plus the 야장 noise complaint and a staff quit). `preview(state, plan, events)` →
analytic estimate in under 1 ms, calibrated so the base plan in October equals 평소. `play_month(state, plan,
events)` → MonthResult: one seeded DES draw (the month that happened) plus a p10-p90 band (30 runs), the waterfall
from 평소 to this month, structured reviews, a Saturday night with speech bubbles, labels, and `state_after`.
`estimate_season(plan, events_by_month)` holds one plan for a season analytically (dominance guard, planning aids).
`python -m sim.guided` writes the guided story (`research/guided.yaml`) to `web/public/guided/`.

**State carried month to month:** cash, rating (recent-review window 30), review count, 인지도, 단골 share,
staff fatigue (0-100), flags (competitor, rent and wage multipliers), negative and low-revenue month counters.
폐업 when cash is below zero at two consecutive month-ends, or revenue is at or under 60% of 평소 for two
months (S89).

**Demand** = base arrivals × calendar × rating (S03, 7% per star) × 인지도^0.3 × 단골 × competitor 0.91 × events
× hours (S12: 23시 −6%, 01시 +4%) × menu appeal × menu price index ^ elasticity. The menu must state the meat's
origin, so the 원육 grade enters the price index as a perceived price (price ÷ (1 + 0.3 × tolerance), 가정).

**Per-party satisfaction** (0-1, weights 가정) adds signed terms: wait, waiting for a server (order and mid-meal),
meat quality, price vs the segment's expected price (S25, S23), soju price, banchan, cleanliness, staff grilling,
menu fun, crowding, marketing hype, too many tables per server, tired staff. Satisfaction drives the review
probability (0.03 per party, review event ×1.5, S84), stars (centred on the starting rating, +0.3 for incentivized
reviews, S83), 단골 share and the reason codes the persona layer turns into text. Stars and 단골 move relative to
the measured mean satisfaction of 평소, so the base plan is stationary. 단골 respond to satisfaction without the
price terms (price already moves demand through the elasticity). They are lost faster than they are won
(0.8 vs 0.3 per unit, deadband 0.01, cap 0.35), and a lost 단골 is a lost cover within the season (가정).

**Staff.** Every party needs 11.5 min of order, refill, payment and clearing plus 8 min of table work (가정,
itemised in the yaml). Servers = 알바 per shift + the owner. When the mid-meal visit is late, the party drops add-on
portions and half its later bottles (patience 5 min, 가정). Load drives fatigue (carry 0.5); fatigue slows every
task, makes staff curt, raises owner sickness and the per-알바 quit risk (0.07 a month, rising with fatigue).

**Lever downsides (all modelled):** price → fewer covers and lower satisfaction; 원육 → cost (S85, S68) against
quality and price tolerance; menu extras → cost, prep time, waste; banchan → cost; staff grilling → 10 min per table
and fatigue; fewer 알바 → slow service, lost add-ons, fatigue, curt staff; more 알바 → wage and more people who can
quit; hours → wage, utilities, fatigue; lunch → part-timer hours, utilities, fatigue at 60% of the dinner margin;
terrace → noise complaints; review event → cost per review and inflated stars; marketing → cost and higher
expectations; group bookings → a blocked table and 20% no-shows (S87); hygiene → labor against inspection risk.

**Tests** (`sim/tests/test_season.py`):
- calibration against the hero base month;
- preview equals the baseline;
- the waterfall adds up;
- the upside and the downside of every lever;
- no sampled plan is best in every month of three event scenarios;
- a 폐업 path and a beat-the-baseline path are reachable;
- determinism by seed;
- the MonthResult shape;
- the guided precompute is deterministic and chained.

**Balance (5 seeds, one plan held all season, vs the base plan; 2026-10-01).** Imported meat at the same price
−538만 (0/5 seeds win). Imported with cheap pricing −703만. One 알바 −74만 (3/5). Owner alone −467만 (closes 3/5).
Lean −330만. Aged at ₩21,000 is the win path, but it carries risk: aged stock can come out uneven (숙성육
품질 편차, 0.15 a month: 20% of meat cost written off and lower quality that month), and pork spikes hit it ×1.25.
Over 30 seeds it ends +263만 ± 103만 vs the base and wins 21/30. Hygiene high +13만 (2/5), basic −174만 (cleanliness
weight 0.10, round-4 ordering). Price +10% +191만 (2/5). 냉삼 +105만 (3/5). The season-level guard (60 sampled plans ×
8 seeds, events drawn) requires that no plan ends with the most cash in every seed.

**가게 가치 (season end).** `season_value(state)` = ending cash + forward value. The forward value is the extra OP
that the ending rating, 단골 and 인지도 earn over the starting ones in six more 평소 months on the base plan (one
yardstick for every store, so branches and plans compare)
(step_estimate; horizon 가정, no discounting). A closed store has none. Guards and tests score on cash only.

**One baseline per month.** play_month also runs a shadow: the base plan with the same state, events,
closures and customer stream (seed). The waterfall starts from the shadow's OP and each line carries a note naming
the plan differences behind it. preview defaults to the month's drawn events and reports vs_base against the same
shadow, analytically. Fatigue's full-load point is derived so 평소 (October, base plan, start state) holds the
starting fatigue. 평소 is sustainable; fatigue recovers at carry 0.5 when load falls.

**The declared baseline month: 외부 사건이 없는 평소 달.** `sim.season.baseline_month()` is the one baseline month a
screen or a persona may quote: the preview of the default plan for October from the starting state with
`events=[]`, no external event, which is the 평소 anchor above (DES mean; the same for every seed; 2,613만 원 revenue,
95만 원 OP, 970 covers, 3.6% margin on 2026-10-03). Test `test_one_declared_baseline_month` pins it to that preview
and checks a festival October differs. Every surface calls it 외부 사건이 없는 평소 달 (평균 예상) and a played
month 이번 달 결과: the 정산 slip and guided options show 이번 달 결과, the guided first chapter states the baseline OP,
and the owner chat quotes the baseline's revenue, OP, food and labor cost (api.main `_with_baseline`) instead of
the workbook P&L. October's preview WITH its drawn events (a festival month: about 2,797만 / 220만) and a guided
10월 (a drawn month near the median, with that month's events) are not the baseline and must not be called 평소.
The plan board's "평소 계획의 평균 예상" line is this month's events on the default plan, labelled as such.
`research/hero_base.yaml` `_pnl_base` stays the workbook P&L that `research/build_workbook.py` derives from the
HeroStore values with the static spreadsheet formula (2,654만 / 122만; regenerating it is a no-op as of 2026-10-03).
It is the calibration target in the section below, never shown as the game's baseline; overwriting it with the
sim's numbers would make that calibration check circular.

**Preview accuracy (2026-10-01).** Every event type is in the analytic preview. That covers rain nights (fewer
arrivals, 야장 shut), closures (owner sickness; inspection fail × probability), cost and demand ops, and quits.
Calibration is per month against 800-2,000-run DES means of the base plan (cached in data/cache, keyed by an input
hash). The crowding curve and the service-retention curve are refit on DES grids. Against the DES mean:
- every event type on the base plan and the lead's plan: within max(30만, 15% of |OP|) (test);
- random multi-lever plans: about 25만 RMSE, +12만 optimistic (left uncorrected: a per-lever correction removed the
  bias but pushed one plan past 1.5× the tolerance), 13/18 within, worst 1.27×, DES mean inside op_range 18/18;
- op_range widens the month's DES spread by this error (24.8만 RMSE; 95만 for overloaded or one-server plans), so the
  board never claims more precision than the estimate has;
- single-server or overloaded plans (load > 0.8): outside the domain; the preview warns (overload).

**Preview honesty.** Over 120 runs per plan-month, the preview equals the DES mean within noise. Over 30 seeds,
aged at ₩21,000 vs base is +301만 analytic vs +263만 ± 103만 DES, winning 21/30. What the analytic estimate lacks
is spread. So the preview carries op_range (p10/p90 from the DES spread, about 4.4% of revenue) and risks (events
the plan invites, e.g. 숙성육 편차 −111만 at 15% a month). Lunch carries a warning that states its net and why.

**Interactivity (GAME-V2-SPEC §12).** A month can be played in two steps. `start_month` returns the representative
Saturday up to its first in-night decision. `play_month(night_choices=...)` re-simulates that same night from each
decision's clock: arrivals and every party draw from their own seeded streams, so a choice changes what follows only
through tables, staff and orders. It also moves the month by `monthly_count` × (the night handled that way − the same
night without the situation).

The five situations are in `research/events.yaml` `_night_decisions`: walk-in 회식 at a full house, 알바 late, meat
running low, a rain burst on the 야장, and a blogger. Every option has a stated downside. A Pareto guard (noise counts
as a tie) keeps any option from dominating every sampled state.

`preview.sensitivity` gives one step of every lever. Waterfall lines and reviews name their levers and events, and
every party event in the night carries its mood, bill and top reason.

**Known v2 limits.** The store's average night is light (about 13 parties), so in DES money terms one fewer 알바
still pays. Its cost comes through satisfaction → 단골 and rating, which are 가정 (interview Q18). Lunch is negative
in every month with the round-4 numbers.

## Owner response loop and offline precompute

`sim.run.run(shock, action, action_args=None, runs=200, seed=42)` applies a shock, then one owner action from
`sim/owner_actions.MENU`, and reruns with the same seeds as the base month. It returns base / shocked / reacted
KPI bands plus driver-tree values. Every action has `default_args`:

| action | default | what it changes |
|---|---|---|
| absorb | none | nothing (the shock-only month) |
| reprice | +5% | `prd_meat_price` (arrivals respond through the elasticity) |
| discount | −5% | `prd_meat_price` |
| reprice_alcohol | +₩500 | `prd_alcohol_price` (bottles respond through the elasticity) |
| cut_staff_hours | −1 h | `sto_parttime_shift_hours` |
| cut_staff | −1 | `sto_parttimers` (fewer servers) |
| change_mix | +10% / +10% | `prd_alcohol_per_cover`, `prd_side_spend_per_cover` (assumes upselling works) |

`python -m sim.precompute` writes `web/public/runs/` for all 11 shocks × 7 actions, plus the base month (about
200 s, 1.2 MB). Each `<shock>/<action>.json` holds:
- base / shocked / reacted bands;
- the shock-only and the shock-plus-action headline (one Korean sentence each);
- driver-tree values;
- which OP line moved most;
- one logged Saturday night after the action.

`index.json` holds the menus and the OP matrix behind the choice cards. Two runs produce byte-identical files
(checked with `diff -r`). The demo needs no API: the game reads only these files.

## Assumptions

Everything in `hero_base.yaml` carries its own criterion_id, range, confidence and source (see the
workbook). The mechanism constants in `sim/params.py::SIM_ASSUMPTIONS` have **no criterion row and no
source yet**. All of them are confidence L:

| constant | value | effect |
|---|---|---|
| closed weekday | Mon | lowest 요일 share in 3120012 |
| last seating | 60 min before close | |
| max party | 4 | no merged tables |
| meal price | ₩7,000 | from the HeroStore reasoning for `prd_side_spend_per_cover` |
| initial order ratio | 0.75 | splits portions into first order vs re-order |
| dwell σ | 0.36 | spread of dwell (S72) |
| dwell alcohol sensitivity | 0.3 | links `prd_alcohol_per_cover` → `drv_dwell_time` |
| dwell factors | 초벌 0.85, staff grilling 0.90 | links `prd_chobeol`, `svc_staff_grilling` → `drv_dwell_time` |
| patience shape | 4 | spread of `mkt_patience` |
| staff minutes | order 3, re-order 1.5, per bottle 0.5, payment 2, clear 4, staff grilling 10 | server workload |
| owner on floor | 1 | servers = part-timers + 1 |

Promote any of these to `ontology/criteria.csv` when it gets a source.

## Calibration and tests (`sim/tests/test_sim.py`)

- Base month p50 revenue and covers within ±10% of the workbook P&L (₩27.5M, 983 covers).
- Cost shares within ±3pp of the P&L; alcohol share within 17–25%.
- Metamorphic tests:
  - price up → covers down (and down → up);
  - wage up → OP down in every run;
  - more tables → fewer walk-aways at 1.8× peak demand;
  - demand down → revenue down;
  - rain → no terrace seating;
  - competitor → fewer arrivals;
  - pork cost up → same revenue, lower OP;
  - same seed → identical output.
- No shock touches a tech-adoption node, and owner actions are pure and bounded.

The suite was mutation-tested. Flipping the elasticity sign, making the wage parameter dead, ignoring
rain, and ignoring demand shocks each made at least one test fail.

## Simulation vs workbook P&L

The first engine version printed an 11.1% OP margin against the workbook's 9.4%. The cause was one input:
`drv_balk_rate`. The workbook derives arrivals as P&L covers ÷ (1 − balk rate) ÷ party size and used a 5%
walk-away prior, but the simulation only loses a fraction of a percent of guests at base demand. So it seated
about 3% more covers than the P&L, and with labor and rent fixed, the extra revenue fell straight into OP.

`python -m sim.calibrate` measures the simulated walk-away share and compares the month with the P&L. After the
sourcing rounds (patience 25 min), the sim measures about 0.4% and the workbook uses 0.5%. Result at p50 over 200
runs (with the 19–21 peak reshape): covers −2.1%, revenue −1.9%, OP margin 3.4% vs 4.6%. Part of the gap is peak demand that cannot be seated. `test_op_margin_within_1_5pp_of_pnl` and
`test_walkaway_rate_close_to_workbook_prior` keep it closed. The driver tree in the UI shows the simulated base
p50 as the main number and the Excel value as 엑셀 추정, so the tree and the KPI strip always agree.

## Sourced values (research/sourcing_round2.md and round3.md, applied together)

| criterion | before | now | source |
|---|---|---|---|
| `drv_rent` | ₩2.3M (back-solved from the KREI share) | ₩4.7M (3.0–5.8M) | R-ONE 혜화동 1층 ₩60,033/㎡ × 25평, cash part (S52) |
| `cst_meat_cost_per_portion` | ₩6,500 | ₩4,500 (3,700–5,200) | KMTA 삼겹 wholesale ₩18,647/kg × 200g + 15–25% markup (assumption) (S68, S69) |
| `prd_alcohol_per_cover` | 1.1 | 0.9 (0.6–1.2) | 식약처 survey (S62) |
| `mkt_patience` | 15 min | 25 min (10–35) | Toast survey, 72% ≤ 30 min (S60) |
| `mkt_price_elasticity` | −0.8 | −0.81 (−0.3 to −2.5), confidence L | Andreyeva 2010 (S58, category level), KREI 2026 (S59) |
| `cst_card_fee_rate` / `cst_card_share` | 1.2% / 0.90 | 0.95% / 0.88 | FSC fee table (S63), BOK survey (S65) |
| `cst_holiday_pay_factor` | 1.20 | 1.33 (1.20–1.43) | 주휴 × employer 4대보험 (S36, S66, S67) |
| `prd_portions_per_cover` high | 1.4 | 1.5 | anecdote (S74) |
| dwell σ (SIM_ASSUMPTIONS) | 0.25 | 0.36 | Kimes & Robson 2004 (S72) |

No other cost was back-solved to restore the old margin. The base workbook month is now revenue ₩26.5M and OP
₩1.2M (4.6%). The rent line is about 18% of revenue against the 2018 national KREI share of about 8%. 혜화동 1층
rent is about 2.9× the national small-shop rent (BM45), so national cost shares do not hold in this 상권. The
workbook keeps this as an INFO row, not a failed check. The food share (31% vs KREI 37%) and the alcohol share
(16.7% vs an unverified 17–25% blog band) are INFO rows for the same reason. Revenue stays calibrated to the
district anchor (+2.9% vs ₩2,578만). `cst_banchan_cost_per_cover` (₩1,200) is still unsourced. It was originally a
residual of the old meat cost, and it is the first number the owner interview should check.

## Party-size sensitivity (illustrative)

`mkt_party_size` stays 2.8, but no Korean distribution was found. `python -m sim.sensitivity` reruns the base
month with a pairs-heavy mix {1: 4%, 2: 58%, 3: 20%, 4: 18%} (mean 2.52; ~58% pairs as in the US casual-dining
reference, S72) for every segment. Parties per night are held fixed, so fewer people arrive per party. The
alternative, holding covers fixed at the anchor, would leave revenue unchanged.

| KPI (p50, 200 runs) | binomial, mean 2.8 | pairs-heavy, mean 2.52 | change |
|---|---|---|---|
| 손님 수 | 962 | 876 | −9.0% |
| 월 매출 | ₩26,023,000 | ₩23,609,000 | −9.3% |
| 영업이익 | ₩879,017 | −₩767,769 | |
| 영업이익률 | 3.4% | −3.3% | |
| 돌아간 팀 | 2 | 3 | |
| 테이블 가동률 | 33.8% | 34.1% | |

With rent at the real 혜화동 level, the store's margin is thin enough that party composition alone can flip the
month to a loss. Ask the owner interview for the split between 2-person and 4-person tables.

## Limits shown in the demo (review fixes 2026-10-01)

- **Choices with an unsourced, downside-free effect are excluded** (`game.exclude: [cut_staff, cut_staff_hours,
  change_mix, SH07]` in `industry/pork_bbq.yaml`). Ruling: a choice whose effect is a confidence-L assumption with
  no modelled downside wins by construction, so it stays out of the game until it is sourced.
  - Staff cut: server minutes are unsourced, and staff never limits the store at about 34% table use.
  - Shorter shifts: shift length never changes service capacity in the model.
  - Upselling: +10% drinks and meals per cover at no cost and no demand effect.

  Each in turn won under every event once the previous one was removed. The service minutes were not retuned to
  manufacture a different answer. `test_no_action_dominates_every_event` fails if any active action is the best
  p50 OP under every event. The game shows: 한계: 인력 감축, 근무시간 단축, 추가 권유처럼 효과의 근거가 없는
  선택지는 사장님 인터뷰로 확인하기 전까지 제외. All remain in `sim.run`, the owner menu and the tests.
- **Price increases are no longer free money.** With the elasticity at confidence L and a high end of −2.5, raising
  the meat price beats 버티기 under 3 of 11 events (SH03, SH06, SH08) and loses under the other 8. SH01 (price +10%)
  now leaves OP flat (₩89만 vs ₩88만).
- **Survival is not simulated.** 생존기간 and 24개월 내 폐업 are 상권-level success criteria from 인허가 data. The
  stats panel leaves them out of "영향을 받는 항목".
- **Review status** is shown in the game as 검토 N/82 (HeroStore rows with `reviewed_by`); it is 0/82 today.

## Known limits

- **Staff capacity barely binds at base demand.** At about 1,000 covers a month, tables sit about 35%
  utilized, so SH07 (one fewer part-timer, now excluded from the demo) saves labor with almost no rise in walk-aways. That result
  depends on the staff-minute assumptions above. Treat it as a question for the owner interview, not a
  finding.
- The time bands are coarse: 17–21 is one band. The demand peak therefore sits at 17:00–19:15, which is
  earlier than a typical 삼겹살 peak.
- The 한식 card-sales profile is used for pork demand (no finer code exists). Seated parties can stay past
  midnight.
- SH10b applies rain to every night of the month. It is a bound, not a forecast; SH10 is the normal-October case.
