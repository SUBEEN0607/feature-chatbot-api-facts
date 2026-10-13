# Sourcing round 2: replacing the weakest guesses

Date: 2026-10-01. Scope: the 8 priority targets from the team lead. Read-only on the repo apart from this file.
Every URL listed under "Source" was opened in this session unless the row says otherwise. Proposed source IDs
(S48 onward) do not exist in `ontology/sources.csv` yet. They are suggestions for whoever edits that file.

Confidence uses the workbook's scale: H = official statistic for this exact quantity, M = official or peer-reviewed
but a proxy (other area, other population, or category level), L = anecdote, vendor, or derived.

## Headline

| # | Target | Current base | Proposed base | Verdict |
|---|---|---|---|---|
| 1 | SH03 pork cost shock | +20% | **+10%** (low +5%, high +30%) | Sourced. +20% is plausible only as a seasonal peak month, not as a year-on-year move |
| 2 | `drv_rent` | ₩2.3M (back-solved) | **₩4.7M** cash rent for 25평 1층 | Sourced (R-ONE 혜화동). **About 2× the current guess.** Breaks the P&L calibration (see §2) |
| 2b | SH08 rent shock | +15% | **+5%** (high +15% only on a new lease) | Statutory 5% cap applies at renewal |
| 3 | `mkt_price_elasticity` | −0.8 | **−0.81** (keep range, widen high to −1.8) | Sourced (meta-analysis, US). Current triangular is already close |
| 4 | `mkt_patience` | 15 min | **25 min** (low 10, high 35) | Weak. US survey of stated maximum wait |
| 4b | `drv_dwell_time` | 105 min | unchanged | **UNVERIFIED.** No source found |
| 5 | `mkt_party_size` | 2.8 | unchanged | **UNVERIFIED.** One indirect cross-check only |
| 5b | `prd_alcohol_per_cover` | 1.1 | **0.9** (low 0.6, high 1.2) | Weak (2017 survey, per drinker per occasion) |
| 5c | `cst_meat_cost_per_portion` | ₩6,500 | flag only | Retail 상차림 benchmark suggests the base may be high (see §5) |
| 6 | `cst_card_fee_rate` | 1.2% | **0.95%** (low 0.40%, high 1.15%) | Sourced (FSC table) |
| 6b | `cst_card_share` | 0.90 | **0.88** (low 0.80, high 0.95) | BOK survey, count basis |
| 7 | `cst_holiday_pay_factor` | 1.20 | **1.33** (low 1.20, high 1.43) | 주휴 1.20 confirmed; 4대보험 employer share added |
| 8 | SH09 vacation shock | −20% | **−8%** (low −5%, high −15%) | Sourced from our own pipeline data (3120012) |

---

## 1. Pork wholesale price and the SH03 shock

**Facts (돼지 지육 도매가격, ₩/kg, 제주·등외 제외, 축산물품질평가원 basis as reported):**

| Period | ₩/kg | Change | Source |
|---|---|---|---|
| 2024 annual average | 5,239 | | S48 |
| 2025 annual average | 5,763 | **+10.0% YoY** | S48 |
| 2025-01 monthly average | 5,056 | +15.3% YoY, −10.0% MoM | search snippet of pigpeople (page not opened) |
| 2025-08 monthly average | 6,602 | | S49 |
| 2025-09 monthly average | 6,499 | +6.6% YoY (2024-09: 6,098) | S49 |
| 2026 annual (KREI forecast, June 2026) | 5,700–5,900 | +0.6% vs 2025 | S50 |
| 2026 H1 / H2 (KREI forecast) | | H1 +6.6% YoY, H2 −3.9% YoY | S50 |

Seasonal swing inside 2025: January 5,056 → August 6,602 = **+30.6% trough to peak**. Against the 2025 annual mean
(5,763), January sits at −12% and August at +15%.

Forecast error is large: forecasters expected 5,100–5,300 for 2025 and the outturn was 5,763, a miss of about 10% (S48).

Retail cross-check (S51, MAFRA press release 2026-08-25): KAMIS 삼겹살 1인분 상차림 재료비 ₩7,082 in 2026 H1
(+6.2% YoY) and ₩7,594 in July–August 2026 (+1.5% YoY). 한국소비자원's basket: ₩10,191 in 2026 H1 (+11.8% YoY).

**Recommendation for SH03 (`cst_meat_cost_per_portion`, pct):** low **+0.05**, base **+0.10**, high **+0.30**.
- Base +10% = the realised 2024→2025 annual move. It is also in the band of the 2026 상차림 YoY figures (+1.5% to +11.8%).
- High +30% = the 2025 trough-to-peak seasonal swing. A store buying in August against a budget set in January faces it.
- +20% is not wrong, but it is a seasonal-peak scenario (August vs annual mean was +15%), not a typical year.
- Consider adding a mirror shock (−12%, a January month vs the annual mean) so the sim also shows cost relief.

**Caveat (UNVERIFIED):** these are 지육 (carcass) prices. A restaurant buys 삼겹살 부분육, whose price can move more
than the carcass (spring 삼겹살 demand). The proposal assumes 1:1 pass-through from 지육 to the 삼겹 portion cost.
No 부분육 wholesale series was opened (KAMIS and ekapepia need an API key or JS; 육류협회 tables not reached).

Confidence: **M** for the size of the moves; **L** for pass-through.
Replaces: Shocks row SH03 rationale "돼지고기 도매가 시계열은 아직 없다".

## 2. 대학로/혜화 상가 임대료 (`drv_rent`) and SH08

**Facts.** 한국부동산원 상업용부동산 임대동향조사, 상권 "서울>기타>혜화동", pulled from the R-ONE open API
(no key needed for single-row queries; table IDs below so anyone can re-pull):

| Series (R-ONE table) | 혜화동 | 서울 | 전국 |
|---|---|---|---|
| 소규모 상가 임대료, 2026Q2 (T248223134698125) | **₩60,033/㎡/월** | ₩52,778 | ₩20,646 |
| 소규모 상가 임대료, 2024Q3 | ₩60,807 | ₩51,210 | ₩20,659 |
| 소규모 상가 공실률, 2024Q3–2026Q2 (T241833134686576) | 0.55–3.32% (2026Q2 2.13%) | 4.8–6.4% | 6.5–8.5% |
| 일반 상가 1층 공실률 (T268603140832693) | 0–6.2% (2026Q1 4.52%) | 3.4–4.6% | 4.7–6.5% |
| 소규모 상가 전환율 (T246253134905233) | 7.481% | 7.04% | |
| 중대형 상가 임대료, 2026Q2 (T244363134858603) | ₩68,285/㎡/월 | ₩56,708 | |
| 소규모 상가 층별 효용비율, 서울, 2026Q2 (T246233134891629) | | 1층 100 / 2층 51.3 / 지하 37.7 | |

- The published 소규모 상가 임대료 is the **1층** rent. Seoul's regional figure (52.78) equals its 1층 row (52.78) in the
  floor table. 한국부동산원 states that 상가 rent is set on the 1층, the most efficiently used floor (S53).
- The rent includes the deposit converted to monthly rent at the 전환율, which is why R-ONE publishes the two together.
  Whether the ㎡ is 전용 or 계약 area: **UNVERIFIED** (the methodology page did not load).
- Trend: 혜화동 1층 small-shop rent fell 1.3% from 2024Q3 to 2026Q2 while Seoul rose 3.1%. The old series
  (A_2024_00279) runs from ₩49,547 (2022Q1) to ₩52,468 (2024Q2). The jump to ₩60,807 in 2024Q3 is a **sample/series
  break** (new 2024Q3~ tables), not a +16% rent rise. Do not read it as a trend.
- 2026Q2 national: 소규모 상가 ₩20,600/㎡, 공실률 8.5% (S54, newsis 2026-07-29), consistent with the API pull.

**Computation (stated assumptions):**
- 1평 = 3.3058㎡. 30평 = 99.17㎡; the hero's `sto_area_pyeong` base 25평 = 82.64㎡. Area is treated as the area R-ONE uses.
- All-in monthly equivalent = ㎡ × ₩60,033.
- Cash rent split: assume deposit = 10 × monthly rent (a common Seoul retail norm; **UNVERIFIED**, but in line with the
  2023 Seoul survey's ₩956k/㎡ deposit vs ₩74.9k/㎡ 통상임대료 ≈ 12.8×, S55). Then all-in = M × (1 + 10 × 0.07481 / 12)
  = M × 1.0623.

| Store | All-in equivalent | Cash 월세 M | Deposit (10×M) |
|---|---|---|---|
| 30평 1층 (99.17㎡) | ₩5.95M | **₩5.60M** | ₩5,600만 |
| 25평 1층, hero (82.64㎡) | ₩4.96M | **₩4.67M** | ₩4,670만 |

**Recommendation for `drv_rent` (₩/월, cash rent, 25평 1층):** low **3,000,000**, base **4,700,000**, high **5,800,000**.
- Base = R-ONE 혜화동 small-shop 1층 rent, cash part.
- Low = between Seoul "기타" 1층 (₩45,101/㎡ → ₩3.5M) and alley asking prices. One forum post (S56, **UNVERIFIED**,
  likely AI-written, asking prices only) lists a 118㎡ 1층 near 대학로 at ₩3,000만/₩250만 (≈₩22.8k/㎡ all-in) and a
  69㎡ unit at 성대사거리 at ₩5,000만/₩350만 (≈₩55k/㎡). That spread shows 골목 vs main-road variance.
- High = 서울 도심 1층 (₩74,111/㎡ → ₩5.8M), or a 30평 unit at the 혜화동 rate.

**Impact the team must decide on.** ₩4.7M is 17% of the ₩27.5M P&L revenue, against the KREI 임차료 share of about 9%
(S31) that the current ₩2.3M was back-solved from. Swapping it in drops monthly OP by about ₩2.4M. Either the composite
sits in a cheaper alley unit (use the low end), or it is smaller, or revenue is higher than the P&L anchor. This is a
calibration choice, not a sourcing one. Flag it before changing `hero_base.yaml`.

**SH08 (`drv_rent`, pct):** low **+0.05**, base **+0.05**, high **+0.15**.
- 상가건물 임대차보호법 시행령 제4조: a rent increase claimed during the lease may not exceed 5%, and not again within a
  year. This applies while 환산보증금 ≤ ₩9억 in Seoul (S57). Hero: ₩4,670만 + ₩467만 × 100 ≈ ₩5.1억 → covered.
  계약갱신요구권 runs 10 years.
- +15% is only reachable on a new lease (after 10 years, a new tenant, or by agreement). The market is not pushing it:
  혜화동 rent was flat to slightly down over 2024Q3–2026Q2.

Confidence: **H** for the per-㎡ rent, vacancy and 전환율 (official, this exact 상권). **M** for the store-level rent
(area basis and deposit ratio are assumptions). **H** for the 5% cap.
Replaces: `drv_rent` (reasoning "역산, 실측 임대료 없음"); SH08 rationale "법 증액 상한 적용 여부는 확인 필요".

## 3. Price elasticity (`mkt_price_elasticity`)

**Facts.**
- Andreyeva, Long & Brownell (2010), *American Journal of Public Health*, systematic review of 160 studies (S58):
  **food away from home: mean −0.81, 95% CI −0.56 to −1.07, range −0.23 to −1.76, 13 estimates.** Pork: −0.72
  (CI −0.66 to −0.78). US data, category level.
- 곽대영·김종진 (2026), 농촌경제 49(2), KREI, ARDL-ECM on 가계동향조사 (S59): the own-price elasticity for
  '음식서비스' is **not significant** in the short or long run (point estimates +0.02 to +0.29). Spending on eating out is
  driven by income (elasticity 0.88 long-run, 0.78 short-run). This is the category level for Korea.

**Reasoning.** Both sources measure the whole category. A single store with about 20 independent 고깃집 nearby
(`reg_competitors`) should be more elastic than the category, because diners switch stores rather than stop eating out.
A consistency check (derived, not sourced): a store that prices to maximise profit with variable cost about 38% of price
(food 37% + card fee) implies a firm-level elasticity near −1/(1 − 0.38) ≈ −1.6.

**Recommendation:** triangular low **−0.3**, base **−0.81**, high **−1.8**.
- Base = the Andreyeva FAFH mean (sourced). Low reflects the Korean category result (near zero). High covers the
  Andreyeva maximum (−1.76) and the derived firm-level −1.6.
- The current triangular(−1.5, −0.8, −0.4) is already close. The change is to the tails and to the source column.

Confidence: **M** for the category value; **L** for applying it to one store.
Replaces: `mkt_price_elasticity` ("연구 파일에 외식 가격탄력성 값 없음").

## 4. Queue patience, walk-aways and dwell

**Patience (`mkt_patience`, SIM_ASSUMPTIONS `patience_shape` = 4).**
- Toast diner survey, as reported by Tasting Table (2024-03-27) and Chowhound (S60): **72% of diners will not wait more
  than 30 minutes** for a table. Sample size and date not disclosed; Toast's own page returned 403.
- Calibrating the sim's Gamma(shape 4) so that P(patience ≤ 30 min) = 0.72 gives **mean ≈ 24.5 min**. With the current
  mean of 15 min, 96% of parties would leave before 30 min, more impatient than the survey.
- de Vries, Roy & de Koster (2018), *Journal of Operations Management* 63:59–78 (S61): 94,404 customers at one Indian
  restaurant. Longer waits raise reneging and shorten dining time; removing waiting would raise revenue by about 15%.
  The numeric hazard was not reachable (paywalled). It supports the mechanism, not a value.
- Recommendation: low **10**, base **25**, high **35** minutes; keep shape 4. Confidence **L** (US, stated rather than
  revealed, all restaurant types). An unremarkable composite store probably earns less patience than a 맛집. If the team
  agrees, base 20 is defensible. No Korean 웨이팅 포기 survey was found.

**Dwell (`drv_dwell_time`) and the dwell constants in SIM_ASSUMPTIONS: UNVERIFIED.** No study or survey of 삼겹살 or
Korean BBQ table time was found. The only related finding is the mechanism above (waiting shortens dining).
Keep 105 min (75–140) at confidence L. This needs the owner interview or a stopwatch visit.

**`drv_balk_rate`:** no external value. It should stay a simulation output, as the workbook already says.

## 5. Party size, portions, soju

- **`mkt_party_size`: UNVERIFIED.** aT 외식소비행태조사 press coverage does not report party size, and 캐치테이블
  releases give no party counts. One indirect cross-check from our own data (S12, 3120012 한식, last 4 quarters): the
  average card ticket is **₩40,026 at 17–21h and ₩60,464 at 21–24h**. At about ₩28k per person, that is at least 1.4–2.2
  people per payment. It is a floor, since split payments (더치페이) lower it. It is consistent with 2–3 people, but it
  does not pin 2.8. Keep at L.
- **`prd_alcohol_per_cover`:** 식약처 주류 소비·섭취 실태조사 (2017, n = 2,000, aged 15+ who drink; S62): average per
  drinking occasion is **소주 6.1잔 (50 ml)** = 305 ml ≈ **0.85 bottle (360 ml) per drinker**, or beer 4.8잔 (200 ml).
  Not every diner drinks, and 소맥 replaces some soju with beer. 1.1 bottles per cover looks high. Proposed low **0.6**,
  base **0.9**, high **1.2**; confidence L (old survey, per occasion rather than per restaurant visit). This moves the
  alcohol share, which the calibration test holds at 17–25%. Check before swapping.
- **`prd_portions_per_cover`: UNVERIFIED.** No consumption survey of 인분 per person was found. Keep.
- **`cst_meat_cost_per_portion` (flag, not a replacement):** the KAMIS 1인분 상차림 basket (meat plus 쌈 vegetables at
  **retail**) was ₩7,082–7,594 in 2026 (S51). The workbook's restaurant cost of ₩6,500 (meat) + ₩1,200 (banchan) =
  ₩7,700 sits at or above the retail basket. A restaurant buying wholesale should pay less than retail, so the base
  may be 15–30% too high. The basket's gram weight is **UNVERIFIED**. Leave the value; ask the owner interview for
  the actual ₩/kg paid.

## 6. Card fees and card share

**`cst_card_fee_rate`.** 금융위원회 2025년 카드수수료 개편, in force 2025-02-14 (S63). Annual-sales brackets:

| 연매출 | 신용카드 | 체크카드 |
|---|---|---|
| ≤ ₩3억 | 0.40% | 0.15% |
| ₩3억–5억 | 1.00% | 0.75% |
| ₩5억–10억 | 1.15% | 0.90% |
| ₩10억–30억 | 1.45% | 1.15% |

The hero's P&L revenue of ₩27.5M × 12 = ₩3.3억 puts it in the **₩3–5억 bracket**. Blended at the BOK credit:check
ratio (46.2 : 16.4 → 74 : 26): 0.74 × 1.00% + 0.26 × 0.75% = **0.935%**. Some 간편결제 is billed by PGs at higher
rates (**UNVERIFIED**), so the proposal rounds up.
- Recommendation: low **0.004** (if annual sales fall below ₩3억; SH09-type demand shocks can cross that line), base
  **0.0095**, high **0.0115**. Confidence **H** for the table; M for the blend.
- Related, not currently modelled: 개인사업자 with sales ≤ ₩10억 get a VAT credit of **1.3% of card sales** (up to
  ₩1,000만/yr) through 2026. The 2026 tax reform proposal cuts it to 1.2% and a ₩500만 cap from 2027, extended to
  2029, pending the National Assembly (S64, KB Think 2026-08-24). For this store, net of the credit, card acceptance
  costs roughly zero. Worth a line in the P&L notes if VAT is ever modelled.

**`cst_card_share`.** 한국은행, 2024년 지급수단 및 모바일금융서비스 이용행태 조사 (published 2025-03-25; S65), share
by transaction **count**: 신용카드 46.2%, 체크카드 16.4%, 현금 15.9%, 모바일카드 12.9%. Cards together are 75.5% of
counts. A dinner ticket of ₩40–60k is larger than the average transaction, and cash share falls with ticket size, so
the store-level share should be above 75%. Recommendation: low **0.80**, base **0.88**, high **0.95**; confidence M
(national, count basis, no amount-basis split found).

## 7. Part-timer employer cost factor (`cst_holiday_pay_factor`)

- 2026 최저임금 ₩10,320/h; 209 h/month = ₩2,156,880 (S36, S66).
- 주휴수당: for anyone working ≥ 15 h/week, paid 주휴 hours = (weekly hours ÷ 40) × 8, so the factor is **8/40 = +20%**
  regardless of shift length (S66: 주 15시간 이상). 5 h × 6 nights = 30 h/week → eligible. The current 1.20 is right
  for 주휴 alone.
- Employer social insurance, 2026:
  - 국민연금 4.75%, 건강보험 3.595% (search snippets of several payroll sites; pages not opened).
  - 장기요양 0.9448% of pay in total → 0.4724% employer (S67, search snippet citing 보건복지부).
  - 산재 0.8% (음식·숙박) + 0.06% 출퇴근 = 0.86% (S67).
  - 고용보험 employer 0.9% + 0.25% = 1.15% (statutory, **UNVERIFIED** for 2026, not opened).
  - Total ≈ **10.83%**. Toss Place's 2026 guide gives "약 11–12%" (S66), which agrees.
- 퇴직금 accrues at 1/12 = 8.33% of pay for staff with ≥ 15 h/week and ≥ 1 year of service.
- **Factor:** 1.20 × 1.1083 = **1.33** with 4대보험. Adding the 퇴직금 accrual: 1.20 × (1.1083 + 0.0833) = **1.43**.
- Recommendation: low **1.20** (no 4대보험 enrolment: common, but non-compliant), base **1.33**, high **1.43**.
  Confidence **M** (statutory rates, partly from snippets).
- Also: 야간근로 가산 (+50% for 22:00–06:00) applies only at 5인 이상 사업장. Counting all part-timers across the week,
  the hero may cross 5 workers. Then the 22–23h hour of an 18–23h shift adds about +10% to that shift. Not in the base
  factor; a candidate SIM_ASSUMPTIONS flag.
- The same 10.83% (+8.33% 퇴직) applies to `cst_employee_wage`. Today the sim adds nothing on top of that wage.
  Suggest a new criterion `cst_employer_burden_rate` = 0.108 (low 0.0, high 0.192).

## 8. Seasonality / 방학 (SH09) from our own pipeline data

Method: `data/processed/seoul_sales.csv`, 한식 CS100001, each quarter's sales ÷ that year's quarterly mean.
Years 2023–2025 (2021–22 are distorted by COVID). Code is reproducible from the CSV in a few lines of pandas.

| 상권 | Q1 | Q2 | Q3 | Q4 | Q3/Q2 | Q1/Q2 |
|---|---|---|---|---|---|---|
| **3120012 대학로(혜화역)**, total sales | 0.975 | 0.979 | 0.940 | 1.106 | 0.960 | 0.996 |
| 3120012, 20대 sales | 1.006 | 0.986 | 0.936 | 1.072 | 0.949 | 1.020 |
| 3120012, 21–24h sales | 0.984 | 1.000 | 0.924 | 1.092 | 0.924 | 0.984 |
| 3110021 성균관대학교 (골목상권), total | 0.950 | 1.155 | 0.871 | 1.023 | 0.754 | 0.823 |

- In 대학로, **Q3 is the trough (−6% vs the annual mean, −4% vs Q2)** and Q4 is the peak (+11%, year-end gatherings).
  Q1 shows no winter-break dip: the theatre and visitor trade likely offsets it.
- Monthly translation: Q3 = Jul + Aug (break) + Sep (term). If the break months run at v × term level,
  (2v + 1)/3 = 0.960 → **v ≈ 0.94, i.e. −6% per break month**. Late-evening sales (21–24h, the 고깃집 hours):
  (2v + 1)/3 = 0.924 → **v ≈ 0.89, −11%**.
- The campus-adjacent 성균관대 상권 shows the hard version: Q3/Q2 = 0.754 → about **−37%** per break month.
- National cross-check: KREI ARDL (S59) estimates household 음식서비스 consumption Q1 −8.4% and Q2 +4.2% vs Q4.
  That matches 대학로's Q4 peak.
- Recent drift: 3120012 한식 sales 2026Q1 −3.1% YoY, 2026Q2 −1.4% YoY. The 20대 share fell from 27% (2023) to 21.5%
  (2026Q2), so the vacation lever is getting weaker over time.

**Recommendation for SH09 (`drv_arrival_rate`, pct):** low **−0.05**, base **−0.08**, high **−0.15**.
- Base −8% sits between the total-sales (−6%) and late-evening (−11%) break-month estimates for 3120012.
- High −15% covers a store skewed to students (20대 share 28% × roughly half away), well short of the
  campus-alley −37%.
- −20% overstates the 대학로 effect. It fits a 성균관대-side 골목 store, not this 상권.
- Optional: add a positive December/Q4 shock (+10%), sourced from the same table.

Confidence: **H** for the quarterly pattern (official card data, this 상권). **M** for the monthly translation (it
assumes June and September are full-term months).

## Sources opened this round (proposed IDs)

| id | Title | Publisher | Date | URL |
|---|---|---|---|---|
| S48 | 지난해 돈가 예측 왜 크게 빗나갔나? (2024 avg 5,239 / 2025 avg 5,763) | 양돈타임스 pigpeople.net | 2026-01-07 | https://pigpeople.net/news/article.html?no=18429 |
| S49 | 9월 도매가격 7개월 만에 하락 전환 (2025-09 6,499; 08 6,602; 2024-09 6,098) | pigpeople.net | 2025-10-16 | https://pigpeople.net/news/article.html?no=17903 |
| S50 | 하반기 돼지 도매가격 전년 대비 3.9% 내외 하락 전망 (KREI 농업관측 6월호) | pigpeople.net citing KREI | 2026-06-06 | https://www.pigpeople.net/mobile/article.html?no=19357 |
| S51 | 추석 성수품 수급관리 (KAMIS 삼겹살 상차림 ₩7,082 / ₩7,594; 소비자원 ₩10,191) | 농림축산식품부 | 2026-08-25 | https://www.mafra.go.kr/bbs/home/793/578847/artclView.do |
| S52 | 상업용부동산 임대동향조사, R-ONE open API: tables T248223134698125, T241833134686576, T268603140832693, T246253134905233, T244363134858603, T246233134891629, A_2024_00279; 상권 CLS_ID 520059 (혜화동) | 한국부동산원 | pulled 2026-10-01 | https://www.reb.or.kr/r-one/openapi/SttsApiTblData.do?STATBL_ID=T248223134698125&DTACYCLE_CD=QY&WRTTIME_IDTFR_ID=202602&CLS_ID=520059&Type=json |
| S53 | 상가는 1층 기준, 오피스는 3층 이상 기준 임대료 산정 | 시대일보 (한국부동산원 설명) | 2023-04-26 | https://www.sidae.com/article/2023042617091572592 |
| S54 | 경기 침체에 전국 공실률 13.4% (2026Q2 임대동향) | 뉴시스 | 2026-07-29 | https://mobile.newsis.com/view/NISX20260729_0003728100 |
| S55 | 서울시 주요 상권 통상임대료 ㎡당 7만4900원 (2023 상가임대차 실태조사, 145상권 1층 12,531곳) | 뉴스핌 | 2024-03-06 | https://www.newspim.com/news/view/20240306000198 |
| S56 | 혜화역·대학로 상업용 부동산 시장 분석 (asking-price listings; vacancy table) | dbritz.kr forum (anonymous) | n.d. | https://dbritz.kr/forum/?bmode=view&idx=172165235 (UNVERIFIED, weak) |
| S57 | 상가건물 임대차보호법 시행령 제4조 (증액 5% 상한; 서울 기준 9억) | korea.legal (statute mirror; search snippet, page not opened) | | https://korea.legal/wiki/상가건물-임대차보호법-시행령-제4조/ |
| S58 | The impact of food prices on consumption: a systematic review of price elasticity (AJPH 100(2)) | Andreyeva, Long, Brownell | 2010 | https://pmc.ncbi.nlm.nih.gov/articles/PMC2804646 |
| S59 | 품목·분위별 식생활 관련 가계 소비지출 결정요인 분석 (농촌경제 49(2):23–48) | 곽대영·김종진, KREI | 2026-06 | https://repository.krei.re.kr/bitstream/2018.oak/33106/1/RE49-2-02.pdf |
| S60 | How long diners will wait for a table (Toast survey: 72% ≤ 30 min) | Chowhound / Tasting Table | 2024-03 | https://chowhound.com/1550126/how-long-diners-wait-restaurant-table |
| S61 | Worth the wait? How restaurant waiting time influences customer behavior and revenue (JOM 63:59–78) | de Vries, Roy, de Koster | 2018 | https://facultynewsletter.iima.ac.in/pastideas/november2019/Worth-the-wait-How-restaurant-waiting-time-influences-customer-behavior-and-revenue%3Csup%3E1%3Csup%3E.html |
| S62 | 식약처 주류 소비·섭취 실태조사 (1회 평균 소주 6.1잔) | 데일리팜 | 2017-12-21 | https://dailypharm.com/user/news/91742 |
| S63 | 2025년 카드수수료 개편 우대수수료율 (시행 2025-02-14) | 금융위원회 | 2025-02 | https://www.fsc.go.kr/edu/news/84133 |
| S64 | 2026년 세제개편안, 사장님이 주목해야 할 포인트 (신용카드 매출세액공제) | KB Think | 2026-08-24 | https://kbthink.com/business/tips/ceo-tip/260824.html |
| S65 | 2024년 지급수단 및 모바일금융서비스 이용행태 조사 | 뉴시스 citing 한국은행 | 2025-03-25 | https://www.newsis.com/view/NISX20250325_0003111896 |
| S66 | 2026년 최저임금 기준, 급여 및 4대보험 계산법 | 토스플레이스 | 2026 | https://tossplace.com/story/2026_minimum_wage |
| S67 | 2026 장기요양 0.9448% / 산재 음식·숙박 8‰ + 출퇴근 0.6‰ | search snippets (daum/heraldk/glasswallet; pages not opened) | 2025-12 | https://www.heraldk.com/article/2025123016313362622 |

Not reached: KAMIS and ekapepia (API key or JS), the Toast primary page (403), 서울시 상가임대차 실태조사 per-상권
tables (sftc.seoul.go.kr not tried), and a 2026 고용보험 rate page.

## proposed_updates

```yaml
proposed_updates:
  SH03:                       # cst_meat_cost_per_portion, pct
    delta_low: 0.05
    delta_base: 0.10
    delta_high: 0.30
    confidence: M
    source_id: S48;S49;S50;S51
    note: "2025 annual +10.0% YoY; 2025 Jan->Aug +30.6%; assumes 1:1 지육->삼겹 pass-through (UNVERIFIED)"
  SH03b_proposed_new:         # optional mirror shock
    parameter: cst_meat_cost_per_portion
    delta_type: pct
    delta_low: -0.05
    delta_base: -0.12
    delta_high: -0.15
    confidence: M
    source_id: S48
  drv_rent:
    low: 3000000
    base: 4700000
    high: 5800000
    unit: "₩/월 cash rent, 25평 1층"
    method: public
    confidence: M
    source_id: S52;S53;S55
    note: "R-ONE 혜화동 소규모 1층 ₩60,033/㎡ (2026Q2) x 82.64㎡ / 1.0623 (deposit 10x at 전환율 7.481%). Breaks P&L calibration (~17% of revenue); team decision"
  drv_rent_per_sqm_hyehwa:    # new reference criterion
    base: 60033
    unit: "₩/㎡/월, 1층, deposit converted"
    confidence: H
    source_id: S52
  SH08:                       # drv_rent, pct
    delta_low: 0.05
    delta_base: 0.05
    delta_high: 0.15
    confidence: H
    source_id: S57;S52
    note: "5% statutory cap at renewal when 환산보증금 <= ₩9억 (Seoul); +15% only on new lease"
  mkt_price_elasticity:
    low: -0.3
    base: -0.81
    high: -1.8
    confidence: M
    source_id: S58;S59
    note: "category-level; store-level likely more elastic"
  mkt_patience:
    low: 10
    base: 25
    high: 35
    unit: min
    confidence: L
    source_id: S60;S61
    note: "Gamma(shape 4) calibrated to P(<=30min)=0.72 -> mean 24.5"
  SIM_ASSUMPTIONS.patience_shape:
    value: 4.0
    note: "kept; used for the calibration above"
  drv_dwell_time:
    status: UNVERIFIED
    keep: [75, 105, 140]
  mkt_party_size:
    status: UNVERIFIED
    keep: [2.2, 2.8, 3.5]
    cross_check: "3120012 card ticket ₩40,026 (17-21h) / ₩60,464 (21-24h) -> >=1.4-2.2 persons per payment"
  prd_alcohol_per_cover:
    low: 0.6
    base: 0.9
    high: 1.2
    confidence: L
    source_id: S62
    note: "6.1 soju glasses/occasion per drinker = 0.85 bottle; check alcohol-share calibration (17-25%)"
  prd_portions_per_cover:
    status: UNVERIFIED
  cst_meat_cost_per_portion:
    status: FLAG
    note: "workbook cost ₩6,500 + banchan ₩1,200 >= KAMIS retail 상차림 ₩7,082-7,594 (S51); may be 15-30% high; verify ₩/kg in owner interview"
  cst_card_fee_rate:
    low: 0.004
    base: 0.0095
    high: 0.0115
    confidence: H
    source_id: S63;S65
    note: "₩3-5억 bracket: credit 1.00%, check 0.75%, blended 0.935%; VAT card credit 1.3% (2026) not modelled (S64)"
  cst_card_share:
    low: 0.80
    base: 0.88
    high: 0.95
    confidence: M
    source_id: S65
  cst_holiday_pay_factor:
    low: 1.20
    base: 1.33
    high: 1.43
    confidence: M
    source_id: S36;S66;S67
    note: "1.20 주휴 x 1.1083 employer 4대보험; high adds 퇴직금 1/12"
  cst_employer_burden_rate_proposed_new:
    low: 0.0
    base: 0.108
    high: 0.192
    applies_to: cst_employee_wage
    confidence: M
    source_id: S66;S67
  SH06:                       # sto_parttime_wage
    note: "unchanged; the 2026 rate rise is already the low (2.9%)"
  SH09:                       # drv_arrival_rate, pct
    delta_low: -0.05
    delta_base: -0.08
    delta_high: -0.15
    confidence: H
    source_id: S12;S59
    note: "3120012 Q3/Q2 = 0.960 (total), 0.924 (21-24h) -> -6% / -11% per break month; 성균관대 골목 -37% is the out-of-scope extreme"
  SH12_proposed_new:          # optional year-end peak
    parameter: drv_arrival_rate
    delta_type: pct
    delta_low: 0.06
    delta_base: 0.10
    delta_high: 0.14
    confidence: H
    source_id: S12
```
