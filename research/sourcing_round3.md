# Sourcing round 3: party size, dwell, portions, pork pass-through

Date: 2026-10-01. Follows `research/sourcing_round2.md`; source IDs continue from S67. Read-only on existing files.
Every URL in the source table was opened in this session unless marked otherwise.

## Headline

| Target | Current | Proposed | Strength |
|---|---|---|---|
| Pork pass-through, 지육 → 삼겹 wholesale | assumed 1:1 | **0.8 (annual) to 0.9 (seasonal); the 삼겹/지육 price ratio holds at 3.10–3.16** | **Sourced** (KMTA weekly series, 2023–2026) |
| `cst_meat_cost_per_portion` | ₩6,500 | **₩4,500** (low 3,700, high 5,200) | **Sourced, M.** The current value is above the retail price |
| SH03 (pork cost shock) | +20% → round 2 proposed +10% | **+8%** base, low +5%, high +28% | Sourced from the 삼겹 부분육 series itself |
| `drv_dwell_time` | 105 min | keep 105; bounded by 47 min (US casual) and 100–120 min (Korean AYCE caps) | Weak. No Korean 고깃집 measurement found |
| SIM `dwell_sigma` | 0.25 | **0.36** | Sourced (Kimes 2004, US casual) |
| `mkt_party_size` | 2.8, 1 + Binomial(3, p) | keep the mean; **consider 2.6 and a 2-heavy shape** | Weak (US casual reference distribution) |
| `prd_portions_per_cover` | 1.0 (0.8–1.4) | widen high to **1.5** | Anecdote only |

**Calibration note.** Moving meat cost from ₩6,500 to ₩4,500 saves about ₩2,000 per portion. At about 983 portions a
month that is about +₩2.0M of operating profit, which roughly offsets the round-2 rent increase (−₩2.4M). Apply the two
together or neither, or the P&L will swing.

---

## 1. Pork pass-through and meat cost (sourced)

**Data.** 한국육류유통수출협회 (KMTA) 돈육 부위별 시세: 냉장 일반 삼겹살, ₩/kg, factory-out (공장출고) price,
"trade average, varies by firm" (S68). I pulled week 2 of each month, 2023-01 to 2026-09, by POSTing the site's
own query form. 2025-10 returned no row.

| Year | Mean | Min (vs mean) | Max (vs mean) |
|---|---|---|---|
| 2023 | ₩16,525 | 14,750 (−11%) | 18,975 (+15%) |
| 2024 | ₩16,631 | 14,000 (−16%) | 19,050 (+15%) |
| 2025 | ₩17,866 (11 months) | 15,000 (−16%) | 20,450 (+15%) |
| 2026 Jan–Sep | ₩18,647 | 16,625 | 20,375 |

- Monthly YoY changes (n = 32): min **−13.4%**, median **+6.7%**, max **+15.1%**.
- 2024 → 2025 annual mean: **+8.1%** (지육 over the same years: +10.0%, round-2 S48).
- 2025-01 → 2025-08: 삼겹 **+27.8%** vs 지육 +30.6%.
- **Ratio of 삼겹 wholesale to 지육:** 3.16 (2025-01), 3.10 (2025-08), 3.12 (2025-09), 3.12 (2024-09).
  Wholesale 삼겹 moves almost proportionally with 지육. Implied pass-through elasticity: about 0.8 on annual means and
  about 0.9 on the seasonal swing.
- Retail lags behind. In April 2026, 지육 was +9.3% YoY but retail 삼겹살 only +1.5% YoY (₩2,559/100g). Over the same
  period, the restaurant price of 1인분 200g in Seoul was ₩21,218, +4.6% YoY (S69, 헤럴드경제 2026-04-20, citing
  축산물품질평가원 / KAMIS / 참가격). 축산물품질평가원 puts the distribution-cost share of the pork consumer price at
  43.7% (2017 유통실태, S70). A margin that large in absolute won is one reason retail moves less than 지육.

**Meat cost per portion.** 200g × ₩18,647/kg (2026 Jan–Sep mean) = **₩3,729 at the factory gate**. Two steps add cost
before the meat reaches the grill: the distributor's margin and trim/yield loss. Neither is sourced. Assume +15–25%,
giving about ₩4,300–4,700. The ceiling is retail: ₩2,559/100g → ₩5,118 per 200g (S69). A restaurant buying through a
wholesaler should not pay above retail. The current ₩6,500 is above that ceiling.

- `cst_meat_cost_per_portion`: low **3,700** (factory gate), base **4,500**, high **5,200** (retail ceiling).
  Confidence **M**. If the hero serves 180g, scale by 0.9.
- **SH03 (pct):** low **+0.05**, base **+0.08**, high **+0.28**. These come from the 부분육 series the restaurant
  actually buys: +8.1% annual, +15% max monthly YoY, +28% January→August. This supersedes round 2's +5/+10/+30.
  The optional mirror shock (−12%) still holds; the January low is about −16% vs the annual mean.

Caveats:
- Week-2 snapshots are not monthly averages.
- KMTA quotes general 냉장 product. Branded 냉장 삼겹 runs about 10–20% higher (e.g. ₩23,250 vs ₩20,050 in 2026-09).
- Imported 냉동 삼겹 is far cheaper (₩14,500). That matters if `prd_meat_origin` = 수입.

## 2. Dwell time (weak)

- **No Korean measurement found.** I searched aT/KREI 외식·식품소비행태조사 coverage, 외식산업 통계연감 references,
  and trade press. None report 소요시간 or 체류시간 for 고깃집.
- Revealed upper bound: 명륜진사갈비 (an all-you-can-eat 고기 chain) caps tables at **120 min on weekdays and 100 min
  on weekends and holidays** (S71, branch listing). An operator caps stays only when some guests would otherwise stay
  longer. So a busy-night mean of 105 min is near the top of plausible.
- US casual-dining reference (Kimes & Robson 2004, Cornell HRA Quarterly 45(4); a 210-seat Chevys, 1,345 dinner
  parties, S72):
  - Mean duration **46.7 min** (SD 17.2).
  - By party size: 2 → 44.6 min, 3 → 48.8, 4 → 51.2. Each extra person adds about 7%.
- Expectations survey (Kimes, S73; n = 134 Cornell students): for a casual dinner with friends, the expected time is
  60.2 min, "long" 81.6 min, "too long" 93.0 min.
- **Recommendation:**
  - Keep `drv_dwell_time` 105 (low 75, high 140) at L. Grilling at the table plus soju makes it longer than US casual
    dining, and the AYCE caps put the busy-night ceiling around 100–120.
  - Raise SIM `dwell_sigma` from 0.25 to **0.36** (the lognormal σ matching Kimes' CV of 0.37).
  - Optional new mechanism constant: `dwell_per_extra_person` = **+0.07** relative to a 2-person party (Kimes).

## 3. Party size (weak)

- **No Korean party-size distribution found.** The aT/MAFRA 외식소비행태조사 press coverage reports frequency, spend
  and 혼밥 share (32% of occasions in 2019), not group size. Card-company releases do not publish people per payment.
- US reference (S72, Chevys): 1 = 4.2%, 2 = 58.4%, 3 = 17.4%, 4 = 14.6%, 5 = 3.8%, 6 = 1.7%. Mean **2.61**.
  Truncated to 1–4 people (the sim's limit): mean 2.45, shape {1: 0.044, 2: 0.618, 3: 0.184, 4: 0.154}.
- Korean cross-check from round 2: in 3120012 the 21–24h card ticket of ₩60,464 implies at least about 2.2 people per
  payment.
- **Shape matters more than the mean.** 1 + Binomial(3, 0.6) gives {1: 0.06, 2: 0.29, 3: 0.43, 4: 0.22}, with 3-person
  parties as the mode. Real casual dining is 2-heavy, and pairs occupying 4-tops waste seats. **UNVERIFIED** for 고깃집:
  the many 2인분-minimum menus and student groups may push toward 3–4.
- **Recommendation:** keep `mkt_party_size` 2.8 (2.2–3.5) at L. Add a sensitivity run with mean 2.6 and a categorical
  {1: 0.04, 2: 0.50, 3: 0.24, 4: 0.22} (labelled illustrative). Ask the owner interview for the 2인 vs 4인 table split.

## 4. Portions per person (anecdote only)

- No 한돈자조금 or other consumer survey of 인분 ordered per person was found.
- The only figure: a 2022 경향신문 column by a Greenpeace campaigner (S74): "어지간한 사내 넷이면 적게는 6인분, 많게는
  12인분도 주문한다". That is 1.5–3.0 인분 per man, an upper-tail anecdote. The same piece takes 1인분 as 180g.
- **Recommendation:** keep base 1.0 at L; raise high from 1.4 to **1.5**. Do not raise the base without the owner
  interview.

## Sources (proposed IDs)

| id | Title | Publisher | Date | URL |
|---|---|---|---|---|
| S68 | 돈육 부위별 시세 (냉장/냉동, 일반/브랜드, 공장출고 ₩/kg; weekly) | 한국육류유통수출협회 | pulled 2026-10-01 (2023-01 to 2026-09, week 2) | https://www.kmta.or.kr/m/price/pork.php (POST form: ymw_y, ymw_m, ymw_w) |
| S69 | 소·돼지값 들썩…더 커진 '외식물가 공포' (지육 ₩6,177 +9.3%; 소매 삼겹 ₩2,559/100g +1.5%; 서울 외식 200g ₩21,218 +4.6%) | 헤럴드경제 | 2026-04-20 | https://www.heraldk.com/article/2026042018372851890 |
| S70 | 주요 축산물 유통비용 비중 45.8% (돼지고기 43.7%; 2017 축산물 유통실태) | 데일리벳 citing 축산물품질평가원 | 2018-04 | https://www.dailyvet.co.kr/?p=93337 |
| S71 | 명륜진사갈비 수원영통점 이용시간 (평일 120분 / 주말·공휴일 100분) | mom-mom.net listing | n.d. | https://mom-mom.net/travel/places/68ac35f0ca795b20d1869bd8 |
| S72 | The Impact of Restaurant Table Characteristics on Meal Duration and Spending (CHRAQ 45(4):333–346), Exhibit 4 | Kimes & Robson, Cornell | 2004 | https://ecommons.cornell.edu/server/api/core/bitstreams/e4a944d8-bdad-4220-9281-df8203ba1e8c/content |
| S73 | How long should dinner take? Measuring expected meal duration for restaurant revenue management | Kimes, Cornell | n.d. | https://ecommons.cornell.edu/server/api/core/bitstreams/019c3aa9-4744-4709-9d77-d18dd8abfa30/content |
| S74 | [녹색세상] 삼겹살 1인분은 왜 180그램? | 경향신문 (김연식) | 2022-09-30 | https://www.khan.co.kr/article/202209300300015 |

Not found or not reached:
- aT/KREI survey tables with 동반인원 or 소요시간 (foodsurvey.krei.re.kr raw data not tried).
- 신한/KB/BC card-company 고깃집 people-per-payment data.
- 한돈자조금 consumer survey.
- The 2020 외식산업 통계연감 PDF (download failed).

## proposed_updates

```yaml
proposed_updates:
  cst_meat_cost_per_portion:
    low: 3700
    base: 4500
    high: 5200
    unit: "₩/인분 (200g)"
    confidence: M
    source_id: S68;S69
    note: "KMTA 냉장 일반 삼겹 2026 Jan-Sep mean ₩18,647/kg x 0.2kg = ₩3,729 factory gate; +15-25% distributor/trim (UNVERIFIED); retail ceiling ₩5,118. Apply together with round-2 drv_rent or P&L swings (~+₩2.0M OP)"
  SH03:
    delta_low: 0.05
    delta_base: 0.08
    delta_high: 0.28
    confidence: M
    source_id: S68;S48
    note: "삼겹 부분육: 2024->2025 +8.1%; monthly YoY median +6.7%, max +15.1%; Jan->Aug 2025 +27.8%. Supersedes round 2"
  SH03b_proposed_new:
    delta_low: -0.05
    delta_base: -0.12
    delta_high: -0.16
    confidence: M
    source_id: S68
  pork_passthrough_jiyuk_to_samgyeop_wholesale:   # reference, new
    value: 0.85
    range: [0.8, 0.9]
    ratio_samgyeop_to_jiyuk: [3.10, 3.16]
    confidence: M
    source_id: S68;S48;S49
  drv_dwell_time:
    keep: [75, 105, 140]
    confidence: L
    source_id: S71;S72;S73
    note: "no Korean measurement; AYCE 고기 caps 100-120 min; US casual mean 46.7"
  SIM_ASSUMPTIONS.dwell_sigma:
    value: 0.36
    confidence: L
    source_id: S72
  SIM_ASSUMPTIONS.dwell_per_extra_person_proposed_new:
    value: 0.07
    confidence: L
    source_id: S72
  mkt_party_size:
    keep: [2.2, 2.8, 3.5]
    confidence: L
    sensitivity_case:
      mean: 2.6
      categorical: {1: 0.04, 2: 0.50, 3: 0.24, 4: 0.22}   # illustrative
    reference_us_casual: {1: 0.044, 2: 0.618, 3: 0.184, 4: 0.154}   # S72, truncated at 4
    source_id: S72
  prd_portions_per_cover:
    low: 0.8
    base: 1.0
    high: 1.5
    confidence: L
    source_id: S74;S28
```
