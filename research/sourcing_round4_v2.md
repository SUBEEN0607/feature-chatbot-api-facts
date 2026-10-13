# Sourcing round 4: v2 game mechanisms

Date: 2026-10-01. Targets: `docs/GAME-V2-SPEC.md` §3–6. Same rules as rounds 2–3: URLs were opened unless marked
otherwise, and source IDs continue from S79. Local computations use `data/processed/seoul_sales.csv` and
`seoul_stores.csv` (3120012, 한식 CS100001).

**Yardstick for "moves OP".** Current `hero_base.yaml` P&L (after the round-2/3 updates): revenue ₩26.54M/month, OP
₩1.22M after the imputed owner wage, break-even 916 covers vs 983. Variable cost per cover is about ₩8,600 against a
₩27,000 ticket, so **1% of revenue ≈ ₩180k of OP**. The base margin is thin (4.6%). Any lever worth ±₩1M is the
difference between a profitable month and a loss.

## Ranking by OP impact (per month, vs base OP ₩1.22M)

| Rank | Mechanism | Typical OP swing | Evidence strength |
|---|---|---|---|
| 1 | Monthly seasonality (Dec peak, Jul–Aug and Jan–Feb dips) | **+₩3.2M (Dec)** to −₩1.4M (Jul/Aug) | H for quarters, assumption for the monthly split |
| 2 | 원육 choice (수입 냉동 vs 국내산 냉장 vs 숙성) | **+₩2.5M** (imported, before demand loss) to −₩1.0M (숙성, before premium) | M (live wholesale prices) |
| 3 | 직원이 구워주기 | **−₩1.8M** if it needs +1 part-timer per shift | L for minutes; H for wage |
| 4 | Reputation (±1 star) | ±₩0.9–1.6M | M (US); KR evidence is directional only |
| 5 | 점심 영업 | about −₩0.5M to +₩0.5M (labor eats most of it) | M for demand share, L for lunch ticket |
| 6 | 연말 회식 bookings with no-shows | −₩0.1M to −₩0.4M on a December booking slate | M (20% no-show, 2017) |
| 7 | Hours to 01시 | about +₩0.2M net, high variance | M for demand share, L for split |
| 8 | Review events | ±₩0.1–0.3M direct; mostly a rating/visibility lever | M |
| 9 | Event shocks (위생점검, 알바 퇴사, competitor opening) | Small expected values; competitor opening −₩0.5M to −₩0.9M when it hits | M/L |
| n/a | Starting cash and the 폐업 rule | Not an OP lever; decides survival | L (no direct survey of cash on hand) |

---

## 1. Reputation and demand

**Luca (HBS), "Reviews, Reputation, and Revenue: The Case of Yelp.com"** (HBS Working Knowledge, 2011-10-24; S03,
page re-opened):
- Each extra Yelp star = **5–9% revenue**. The effect sits with independents; chains showed minimal impact.
- Data: Seattle, Washington State revenue records, through 2009.

**Korea, directional only:**
- 네이버 D-플레이스 리포트 Part 2 (2023; S80): fixed/random-effects panel of 109,463 businesses, 17.6% of them
  restaurants. For SMEs, **+100 place reviews → +65 page visitors, +239 page views, +5 길찾기, +2 phone calls** (the
  report does not state the period). The SME effect is **1.5× the franchise effect**. No revenue figure.
- Naver replaced star ratings with keyword reviews (rolled out from 2021), so a "평점" in Korea mostly means
  Kakao Map or Google stars. The v2 rating state should be labelled as a generic star rating, not a Naver one.
- KDI School research (Park, 동아일보 column 2024-10-10, S81): positive emotional text and food photos predict
  survival better than the star average. Chicago Yelp data, not Korean.
- Already in `sources.csv`: Li et al. (S06), where review-score variance predicts 1-year survival.

**Proposal:** `rep_star_revenue_elasticity` low 0.05, base 0.07, high 0.09 (revenue per star). Apply to arrivals for
independents. Do not stack a separate review-count effect on top; Naver's count effect is on page views, not revenue
(UNVERIFIED conversion).

## 2. Review rate and review events

| Fact | Value | Source |
|---|---|---|
| Delivery-app users who wrote reviews (past year) | 77.3% | 한국소비자원 survey of 1,000 users, reported 2024-07-23 (S82) |
| Reviewers who cite 리뷰이벤트 as the reason | 65.2% | S82 |
| Event participants saying the event raised their star rating | 79.6%; 98.3% of those rated above actual satisfaction | S82 |
| Restaurants running review events | 67.1% | S82 |
| Users who "heavily reference" reviews when choosing | 73.4% | S82 |
| Compensated vs organic review rating (Amazon) | +0.48 stars | Management Science 2023 study, reported in 조세금융신문 2026-09-16 (S83) |
| Airbnb $25 coupon for a review (RCT) | Review rate 24.17% → 37.01% (+53%); ratings **fell** 0.07 (4.48 → 4.41); +9.1% transactions over 120 days, no significant revenue effect | Fradkin & Holtz 2021 (S84) |

- **Per-visit review rate for dine-in Korean BBQ: UNVERIFIED.** The 77.3% is "ever reviewed in a year" on delivery,
  not per visit.
- **Proposal (가정):**
  - Per-party review probability: base 0.03 (low 0.01, high 0.06).
  - 리뷰이벤트 multiplies it by 1.5 (Airbnb +53%, low 1.2, high 2.5).
  - A conditional event (서비스 for a good review) adds +0.3 stars to event reviews (low +0.1, high +0.48).
  - Downsides: event cost per review (e.g. one free 음료 ≈ ₩1,600 cost) and a "rating noise" flag.
- Note the two designs pull in opposite directions. Conditional rewards inflate ratings (S82, S83). Unconditional
  rewards bring in more critical reviewers and lower the average (S84). The game can expose both.

## 3. Satisfaction drivers

- **No aT 외식소비행태조사 table with weighted drivers was reachable.** aT/KREI coverage reports frequency and spend.
- Weak secondary: a search summary of a 2021 Korean poll (hrcopinion "맛집 선택의 기준", 403 when opened) puts
  taste 84%, price 64%, cleanliness 53% among top criteria, with taste first for 45%. **UNVERIFIED.**
- Peer-reviewed analogue in hand: de Vries et al. (S61). Waiting raises reneging and shortens dining.
- **Proposal:** make satisfaction a weighted sum with weights tagged 가정: taste/meat quality 0.35, price vs
  expectation 0.25, wait 0.15, service 0.15, cleanliness 0.10. Order follows the unverified poll. Expose the weights
  in the UI as assumptions. The owner interview (Q2, Q25) can re-rank them.

## 4. 원육 options: wholesale cost per kg and menu price

| Option | Wholesale ₩/kg | Cost per 200g portion | Source |
|---|---|---|---|
| 수입 냉동 삼겹 (Spain 미박) | 7,000 | ₩1,400 + margin/trim → about ₩1,800 | Live B2B listing, 수입육거래소 2026-10-01 (S85) |
| 수입 냉동 삼겹 (Austria) | 9,250 | about ₩2,300 | S85 |
| 국내산 냉동 일반 | 14,500 | about ₩3,500 | KMTA week-2 2026-09 (S68) |
| **국내산 냉장 일반 (current base)** | 20,050 | **₩4,500** (round 3) | S68 |
| 국내산 냉장 브랜드 | 23,250 | about ₩5,200 | S68 |
| 숙성 (wet/dry aged, domestic) | 냉장 + aging loss | about ₩5,500–6,500 | **UNVERIFIED**: aging weight loss and labor not sourced |

**Menu price consumers accept:** no willingness-to-pay study found.
- Observed menus: 숙성 ₩16,000 per 150g (≈ ₩21,300 per 200g); 서울 평균 ₩21,321 per 200g (참가격 2026-06, S23).
  The 숙성 menu is a search snippet; the 서울 평균 is a secondary report.
- Imported 냉삼 places price well below that. No opened source.

**Proposal:**
- 수입 냉동: cost ₩2,000, satisfaction −0.3 on meat quality, price-tolerance ceiling about ₩15,000.
- 숙성: cost ₩6,000, satisfaction +0.3, ceiling about ₩22,000.
- All tolerances tagged 가정.

**OP:** switching 국내산 → 수입 saves about ₩2,500 per portion. Over 983 portions that is **+₩2.5M/month** before
any demand or price change, the largest single lever. That is why it needs the satisfaction downside.

## 5. 직원이 구워주기

- **No source** for extra staff minutes or dwell change. Current SIM_ASSUMPTIONS: +10 staff-min per table, dwell
  ×0.90.
- Labor cost is sourced: one extra part-timer per shift = 5h × 26 nights × ₩10,320 × 1.33 = **₩1.78M/month** (round 2
  §7). The lever only pays if it lifts price tolerance or 회식 demand by about 10% of revenue.
- **Proposal:** keep 10 min (low 6, high 15) and dwell factor 0.90 (low 0.85, high 1.0). Tag 가정; the interview Q18
  measures it.

## 6. 점심 영업 and late hours (our data, 3120012 한식, last 4 quarters)

| Band | Share of sales | Share of card transactions | Avg ticket per transaction |
|---|---|---|---|
| 11–14 | **23.0%** | 30.4% | ₩28,213 |
| 14–17 | 9.9% | 13.8% | ₩26,916 |
| 17–21 | 44.1% | 41.1% | ₩40,026 |
| 21–24 | **17.8%** | 11.0% | ₩60,464 |
| 00–06 | **4.1%** | 2.2% | ₩70,408 |

- **Lunch.** The 상권 does a quarter of its 한식 sales at lunch, but at a lower, more individual ticket. A 고깃집
  lunch (점심 특선) captures a fraction of that.
  - Proposal (가정): lunch adds +8% revenue (low +4%, high +12%) at 60% of the dinner contribution margin.
  - Cost: 3h × 2 staff × 26 days × ₩10,320 × 1.33 ≈ ₩2.1M, plus utilities.
  - Net is about **−₩0.5M to +₩0.5M**. Lunch is a fatigue and labor trade-off, not a free win.
- **Close at 01시 instead of 24시.** The 00–06 band is 4.1% of 상권 한식 sales, 6.6% relative to the hero's 17–24
  window.
  - Proposal (가정): the extra hour captures 60% of that band, about +4% revenue (≈ +₩0.7M OP gross).
  - Cost: 1h × 2–3 staff × 26 × ₩10,320 × 1.33. If the store has 5 or more workers, the 22–06 night premium (+50%)
    applies to all late hours (round 2 §7).
  - Net about +₩0.2M, with a fatigue cost.
- Closing at 23시 loses roughly a third of the 21–24 band, about −6% revenue (가정: uniform within the band).

## 7. 연말 회식 season

- National 외식 card sales (aT using 신한카드 merchant data; 아시아경제 2023-04-21, S86): Dec 2022 ₩10.65조 vs
  Nov 2022 ₩9.61조, **+10.8% month over month**. Dec 2019 (pre-COVID) ₩9.83조.
- Our quarterly data: 3120012 Q4 is +10.6% over the annual quarterly mean (2023–25 average; round 2 §8).
- **No-show rate: 20% for restaurants** (현대경제연구원 2017, via 한국경제 생글생글 2024-12, S87; search-snippet level).
  The 2025-12 소비자분쟁해결기준 revision raised the allowed 노쇼 penalty for 일반음식점 from 10% to 20% of the bill
  (뉴시스 2025-12-31, S88; search snippet).
- Share of December covers from group bookings: **UNVERIFIED** (no source).
- **Proposal:**
  - December demand ×1.18 vs the annual mean (see §8).
  - 회식 bookings: share of December covers 0.25 (가정, low 0.10, high 0.40).
  - No-show 0.20 (low 0.10, high 0.30) on booked tables. A blocked table that no-shows loses the walk-in it
    displaced on peak nights only.
  - With a 20% penalty deposit option (S88) as the mitigation lever.

## 8. Monthly seasonality (split of the 3120012 quarterly index)

There is no monthly card-sales series for 3120012 in hand. The split below is an **assumption with three anchors**:
- Quarter indices, 2023–25 average (H): Q1 0.975, Q2 0.979, Q3 0.940, Q4 1.106.
- Dec = Nov × 1.108 (S86, national).
- Break months = term months × 0.94 (round 2 §8 derivation), applied to Jul/Aug and Jan/Feb.

Each quarter's three months average to its index:

| Month | Index (annual mean = 1.00) | Rule |
|---|---|---|
| Jan | 0.955 | Q1: Jan = Feb = 0.94 × Mar |
| Feb | 0.955 | 설 sits in Jan or Feb (also a dip; not separated) |
| Mar | 1.016 | 개강 |
| Apr | 0.979 | Q2 flat (no anchor) |
| May | 0.979 | |
| Jun | 0.979 | June exams and the start of break are not separated |
| Jul | 0.921 | Q3: Jul = Aug = 0.94 × Sep |
| Aug | 0.921 | |
| Sep | 0.979 | |
| Oct | 1.068 | Q4: Oct = Nov |
| Nov | 1.068 | |
| Dec | **1.183** | Dec = 1.108 × Nov |

- These are per-month totals. If the sim treats the index as per-night intensity, divide by days in month ÷ 30.4.
- Tag the whole table 가정 in the UI, citing the three anchors.

## 9. Starting cash and the 폐업 rule

- **No survey of cash on hand was found.** 2024 소상공인실태조사 dropped revenue/cost items (S42).
- Proxies:
  - 2022 소상공인 (all sectors): start-up cost ₩8,500만, own funds ₩6,400만, revenue ₩2.34억, OP ₩3,100만 per
    business (search snippet of the 2023 소상공인실태조사; not opened).
  - Closed 소상공인: 68.5% held debt, average ₩8,531만. 70.9% closed for poor sales; 64.4% decided to close after
    sales fell 40%+. Average closure cost ₩1,286만. (중소벤처기업부 survey of 1,500 closed owners, 헤럴드경제
    2026-06-29, S89)
  - KREI 2023 외식업체 경영실태: average revenue ₩2.3억, OP ₩2,657만 (11.6%), rent 9.6% of cost (아시아경제
    2024-04-23, S90).
- **Proposal:**
  - Start cash ₩2,000만 (low ₩1,000만, high ₩3,000만). That is about 0.8 months of total cost (₩25.3M), so two bad
    months can trigger the rule. Tag 가정.
  - Keep the "cash < 0 at two consecutive month-ends" rule.
  - Add a soft closure trigger that matches the survey: revenue down ≥40% vs 평소 for two months (S89).

## 10. Event frequencies

| Event | Monthly probability | Basis |
|---|---|---|
| 근처 고깃집 개점 | **0.33** (low 0.15, high 0.45) | 3120012 한식 openings 2023Q1–2026Q2: 7.1 per quarter (개업률 4.2%/quarter), closures 5.6 per quarter (폐업률 3.3%). Times the pork share of 한식 stores (27/160 = 17%) gives 1.2 pork openings per quarter = 0.40/month, P(≥1) = 0.33. Openings slowed in 2026 (Q1 4, Q2 1). From local `seoul_stores.csv` (S13) |
| 근처 고깃집 폐업 | 0.27 | Same method: 5.6 × 0.17 per quarter |
| 위생점검 visit | about 0.08 (annual cadence) | Seoul 통합위생점검 once a year (서울신문 2010-04-01, old, search snippet). Violation rate 1.2% in a targeted 2025 MFDS sweep that prioritised never-inspected or prior violators (한국경제 2025-03-06, S91). Fail probability given a visit: 0.01–0.05 by 청결 lever (가정) |
| 알바 갑작스런 퇴사 | 0.05–0.10 per 알바 per month (base 0.07, 가정) | KR all-industry monthly 이직률 4.9% (2026-05, 사업체노동력조사 via newstomato, search snippet). US accommodation and food quit rate 4.3% (2026-03, JOLTS via news, snippet). Students in 대학로 likely higher; fatigue raises it |
| 맛집 블로거 바이럴, 악성 리뷰, 사장님 몸살, 한파, 비 주간 | 가정 | No sources sought this round; weather can come from 기상청 normals |

## Sources (proposed IDs)

| id | Title | Publisher | Date | URL |
|---|---|---|---|---|
| S80 | 네이버 D-플레이스 리포트 Part 2: 플레이스 리뷰의 사업자 성과 향상 효과 | NAVER | 2023-03 | https://www.navercorp.com/navercorp_/research/2023/20230308115144_2.pdf |
| S81 | 맛집 흥행에 영향력 큰 소비자 게시물은… 음식사진 > 리뷰 글 > 별점 | KDI School (박재혁), 동아일보 기고 | 2024-10-10 | https://www.kdi.re.kr/share/pressContriView?bd_no=50813 |
| S82 | 리뷰 작성 소비자 79.6%, 리뷰 이벤트 참여 음식점 별점에 영향 (한국소비자원 조사) | 식품저널 | 2024-07-23 | https://www.foodnews.co.kr/news/articleView.html?idxno=109090 |
| S83 | [평점의 민낯 ①] 리뷰 이벤트에 별점 더 후하게 | 조세금융신문 | 2026-09-16 | https://www.tfmedia.co.kr/news/article.html?no=207248 |
| S84 | More Reviews May Not Help: Evidence from Incentivized First Reviews on Airbnb | Fradkin & Holtz (arXiv 2112.09783) | 2021 | https://arxiv.org/pdf/2112.09783 |
| S85 | 수입육거래소 live listings (수입 냉동 삼겹 스페인 ₩7,000/kg, 오스트리아 ₩9,250/kg) | meat-asia.com | 2026-10-01 | https://www.meat-asia.com/ |
| S86 | 외식산업 12월 매출 10조6483억 (aT, 신한카드 가맹점 데이터) | 아시아경제 | 2023-04-21 | https://view.asiae.co.kr/article/2023041914281606250 |
| S87 | 음식점 예약부도율 20% (현대경제연구원 2017) | 한국경제 생글생글 (search snippet) | 2024-12 | https://sgsg.hankyung.com/article/2024120682601 |
| S88 | 소비자분쟁해결기준 개정 (노쇼 위약금 10% → 20%) | 뉴시스 (search snippet) | 2025-12-31 | https://mobile.newsis.com/view/NISX20251231_0003461509 |
| S89 | 폐업 소상공인 '8531만원' 빚만 남겼다 | 헤럴드경제 | 2026-06-29 | https://www.heraldk.com/article/2026062918381282119 |
| S90 | 농경연 2023년 외식업체 경영실태조사 | 아시아경제 | 2024-04-23 | https://view.asiae.co.kr/article/2024042311260144428 |
| S91 | 식약처 분식·패스트푸드 4,474곳 점검, 55곳 적발 | 한국경제 | 2025-03-06 | https://www.hankyung.com/article/2025030680607 |

## proposed_updates

```yaml
proposed_updates:
  rep_star_revenue_elasticity:       # NEW state mechanism
    low: 0.05
    base: 0.07
    high: 0.09
    unit: "revenue share per star (independents)"
    confidence: M
    source_id: S03
  review_prob_per_party:             # NEW
    low: 0.01
    base: 0.03
    high: 0.06
    confidence: L
    source_id: null
    note: "가정; delivery 77.3% ever-reviewed (S82) is not a per-visit rate"
  review_event_rate_mult:            # NEW
    low: 1.2
    base: 1.5
    high: 2.5
    confidence: M
    source_id: S84;S82
  review_event_star_bias:            # NEW, conditional reward design only
    low: 0.1
    base: 0.3
    high: 0.48
    confidence: M
    source_id: S83;S82
  satisfaction_weights:              # NEW, all 가정
    meat_quality: 0.35
    price_vs_expectation: 0.25
    wait: 0.15
    service: 0.15
    cleanliness: 0.10
    confidence: L
  meat_option_cost_per_portion:      # NEW lever values, ₩ per 200g
    imported_frozen: {low: 1800, base: 2000, high: 2400, source_id: S85, confidence: M}
    domestic_chilled: {low: 3700, base: 4500, high: 5200, source_id: S68, confidence: M}
    aged: {low: 5500, base: 6000, high: 6500, source_id: null, confidence: L}
  svc_staff_grill_min:               # SIM_ASSUMPTIONS
    low: 6
    base: 10
    high: 15
    confidence: L
  dwell_factor_staff_grill:
    low: 0.85
    base: 0.90
    high: 1.00
    confidence: L
  lunch_revenue_uplift:              # NEW
    low: 0.04
    base: 0.08
    high: 0.12
    margin_vs_dinner: 0.6
    confidence: L
    source_id: S12
    note: "상권 11-14 band = 23.0% of 한식 sales, ticket ₩28,213"
  late_close_01_uplift:              # NEW
    low: 0.02
    base: 0.04
    high: 0.06
    confidence: L
    source_id: S12
    note: "00-06 band = 4.1% of sales (6.6% of 17-24)"
  early_close_23_loss:
    base: -0.06
    confidence: L
    source_id: S12
  monthly_demand_index:              # NEW calendar, annual mean = 1
    jan: 0.955
    feb: 0.955
    mar: 1.016
    apr: 0.979
    may: 0.979
    jun: 0.979
    jul: 0.921
    aug: 0.921
    sep: 0.979
    oct: 1.068
    nov: 1.068
    dec: 1.183
    confidence: M
    source_id: S12;S86
    note: "quarters H (2023-25); within-quarter split is 가정"
  group_booking_share_dec:           # NEW
    low: 0.10
    base: 0.25
    high: 0.40
    confidence: L
  no_show_rate:
    low: 0.10
    base: 0.20
    high: 0.30
    confidence: M
    source_id: S87;S88
  cash_start:
    low: 10000000
    base: 20000000
    high: 30000000
    confidence: L
    source_id: S89;S90
  closure_rule:
    hard: "cash < 0 at two consecutive month-ends"
    soft: "revenue <= 0.6 x 평소 for two consecutive months (S89: 64.4% closed after a 40%+ drop)"
  event_probabilities_per_month:
    competitor_open: {low: 0.15, base: 0.33, high: 0.45, source_id: S13;S20, confidence: M}
    competitor_close: {base: 0.27, source_id: S13;S20, confidence: M}
    hygiene_visit: {base: 0.08, fail_given_visit: [0.01, 0.05], source_id: S91, confidence: L}
    staff_quit_per_parttimer: {low: 0.05, base: 0.07, high: 0.10, confidence: L}
```
