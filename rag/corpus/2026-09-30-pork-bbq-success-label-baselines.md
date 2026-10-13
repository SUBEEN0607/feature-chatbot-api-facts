# Pork BBQ (삼겹살집) success label + economics baselines

_2026-09-30, research agent for the Team 1 고깃집 project. Numbers marked UNVERIFIED/derived are guesstimation inputs, not facts._

I found sources for everything in part A. Part B is weaker: I found no published statistic for liquor share of sales, dinner table turnover, or Seoul-only monthly revenue for pork BBQ stores. Those figures are marked below as derived, blog-only, or UNVERIFIED.

## A) How papers define "success vs failure"

| Study | Data | Label |
|---|---|---|
| Parsa et al. 2005, *Why Restaurants Fail* (Cornell HRAQ) [pdf](https://econ.ucsb.edu/%7Etedb/Courses/Ec1F07/restaurantsfail.pdf) | 2,439 health-department operating permits, Columbus OH, 1996–99 | **Ownership turnover**: a new owner ID at the same location ID. The paper states the definition drives the rate: bankruptcy gives the lowest, ownership change the highest. Year 1 26.16%, Y2 19.23%, Y3 14.35%. 3-year cumulative: independents 61.36%, chains 57.22% |
| Parsa et al. 2011, *Part II* (J. Foodservice Business Research) [pdf](https://foodethics.univie.ac.at/fileadmin/user_upload/p_foodethik/Parsa___et.al._2011_Why_Restaurants_Fail_Part_2.pdf) | Cobb County GA health-department data | **Time to close**, via Kaplan-Meier (K-M) curves and a Cox model. Predictors: zip code, chain vs independent, size category (seats/staff). Small and independent stores fail more |
| Luca, *Reviews, Reputation, and Revenue* (HBS) [summary](https://www.library.hbs.edu/working-knowledge/the-yelp-factor-are-consumer-reviews-good-for-business) | Washington State revenue data plus Yelp, Seattle | **Revenue**. +1 Yelp star = +5–9% revenue, for independents only |
| Mejia, Mankad & Gopal (UMD) [news](https://rhsmith.umd.edu/news/mining-yelp) | 130k Yelp reviews, ~2,000 Washington DC restaurants | **Closed yes/no** (~450 closed 2005–14), with pairs matched on price and cuisine |
| Vallapuram et al. 2021 [arXiv](https://www.arxiv.org/pdf/2109.12370) | Yelp dataset | **Open at end of 2017 → dead by end of 2019** (binary; 36,190 restaurants, 12.8% dead). AUC 0.72 |
| Li et al. 2025 (Tourism Management) [PolyU](https://www.polyu.edu.hk/shtm/news-and-events/news/2026/20260720_restaurant-reviews/) | 500k Yelp reviews, ~3,000 Boston restaurants | **Survival one year ahead**. The *variance* of review scores predicts better than the average |
| Kimes, RevPASH (Revenue Per Available Seat Hour) [Cornell eCommons](https://ecommons.cornell.edu/entities/publication/519ba198-3b5b-4fa3-84ca-042677dd7a5e) | Operations research | **Revenue ÷ (seats × hours open)**. An efficiency measure, not a survival label. The formula was taken from the [search summary](https://sevenrooms.com/blog/restaurant-revpash/); I did not open the eCommons record itself |

**Korean studies**

| Study | Data | Label |
|---|---|---|
| 정동규·윤희연 2017 (대한건축학회) [SNU](https://laplanning.snu.ac.kr/publication/2017-jeong/) | 이태원 음식점, 2001–06 | **폐업 여부 + 영업기간** (K-M + Cox). Median survival: 골목 2,304 days vs 발달상권 2,748 days |
| 이채은·최인수 2026 (한국경영공학회지) [동아시아경제 via dhnews](https://dhnews.co.kr/news/view/1065577402337354) | **LOCALDATA 인허가** (행정안전부 지방행정 인허가 데이터), 28,590 서울 카페, 2010–2025.11 | **폐업 여부 + 영업기간**. Closure risk peaks at 24 months. 3-year survival: 한식 70%, 경양식 68%, 호프·통닭 65%, 분식 63%, 커피 60% |
| 안예린 외 2022 (JCCT) [pdf](https://koreascience.or.kr/article/JAKO202221737437258.pdf) | 강남구 franchise POS + public data | **Revenue normalized by population**: monthly sales per 10,000 행정동 residents. Above ₩25M = success, below ₩5M = failure. RF accuracy 0.92 |
| 이민주 외 2024 (지역연구) [pdf](https://koreascience.or.kr/article/JAKO202409378810072.pdf) | **우리마을가게 상권분석서비스**, 1,490 서울 retail 상권 | **ln(상권 매출액)**, spatial 3SLS (a spatial regression model). The unit is the 상권, not the store |

The Seoul 상권분석서비스 추정매출 data is **card-based, quarterly, 2021 onward, at 상권 × 업종 level**, using 100 생활밀접업종 with 한식음식점 as one bucket ([data.seoul OA-15572](https://data.seoul.go.kr/dataList/OA-15572/S/1/datasetView.do)). It has **no store-level and no pork-BBQ-specific revenue**.

### Recommended label design for a pork BBQ store

- **Primary: survival.** Months from 인허가 date to 폐업 date, taken from LOCALDATA 일반음식점. Stores still open are right-censored. Also derive a binary "closed within 24/36 months," since hazard peaks around 24 months per 이채은·최인수.
  - Pros: public, store-level, the academic standard (Cox/K-M).
  - Cons: a 인허가 폐업 can be a relocation or 양도 rather than a failure (Parsa's turnover problem). Treat 지위승계 separately. It also says nothing about how well an open store is doing.
- **Secondary: relative revenue performance.** Store monthly revenue divided by the 상권 benchmark (상권 한식음식점 추정매출 ÷ 점포수, same quarter), then labelled by tercile.
  - **Normalize by district: yes.** Raw revenue mostly measures location; 안예린 외 normalized for exactly this reason.
  - **Normalize by seats/area: yes for the twin's operational layer** (RevPASH, revenue per 3.3㎡). Otherwise a 60-seat store looks "successful" only because it is big, and Parsa 2011 found size predicts survival.
  - Cons: store revenue needs POS or owner disclosure, and the 상권 benchmark mixes all 한식 with no pork-only split.
- **Leading indicators, not labels:** review velocity and rating variance (Li et al.).
- **Avoid profit margin as a label.** In the Korean survey, 인건비 includes imputed 대표자 인건비 (14.9% of operating cost, see B), so margin is unobservable and noisy. Keep it as a simulation output.

## B) Baselines: independent Seoul 삼겹살집

### Price and ticket

| Item | Range | Source |
|---|---|---|
| 삼겹살 200g, Seoul avg | ₩21,321 (2026.6), ₩21,056 (2026.1); real alley stores ~₩17,000 (마포 2026.3) | 참가격 via [세계일보](https://www.segye.com/newsView/20260801501857), [아시아경제](https://view.asiae.co.kr/article/2026072014394339053); [헤럴드](https://www.heraldk.com/article/2026030317453827657) |
| 소주 per bottle | ₩4,000–6,000 (마포 2026); 강남 ₩7,000–8,000 (2023) | [헤럴드](https://www.heraldk.com/article/2026030317453827657); [데일리안 2023](https://www.dailian.co.kr/news/view/1203849/) |
| 소주 restaurant margin | ₩4,400 at ₩6,000 (73.4%) | [머니투데이 2023](https://www.mt.co.kr/living/2023/02/24/2023022323513823951) |
| 객단가 incl. alcohol | **~₩28,000–40,000 per person** (my derivation from the price rows above). Floor: 2인분 + 소주 each is "well over ₩50k" | [쿠키뉴스 2024](https://www.kukinews.com/article/view/kuk202408160146). The all-외식 average of ₩14,310 is not comparable ([뉴시스](https://www.newsis.com/view/NISX20260328_0003567838)) |
| 주류 share of sales | **~17–25%** (my derivation). Only published split is an anonymous blog: 65% meat / 20% alcohol / 15% meals. UNVERIFIED | [blog](https://moneycat.wandererkator.com/entry/%EA%B3%A0%EA%B8%B0%EC%A7%91-%EC%88%98%EC%9D%B5%EB%A5%A0-%EA%B3%84%EC%82%B0%EB%B2%95%EA%B3%BC-%EB%A7%A4%EC%B6%9C-%EA%B5%AC%EC%A1%B0-%EC%99%84%EB%B2%BD-%EC%A0%95%EB%A6%AC) |

### Cost structure

The only source that breaks out 한식 육류요리전문점 is KREI/서울대 for 농식품부, using 2018 data, nationwide ([pdf](https://repository.krei.re.kr/bitstream/2018.oak/26686/1/C2020_77-6.pdf)). The report gives cost shares as % of *operating cost*; I converted them to % of revenue.

| Metric | 육류구이 (2018) | All 외식, recent |
|---|---|---|
| Annual revenue | ₩2.256억 | ₩2.553억 (2024); 한식 ₩2.911억; non-franchise ₩2.3억 ([농식품부](https://www.mafra.go.kr/bbs/home/792/577439/artclView.do), [뉴시스](https://www.newsis.com/view/NISX20260328_0003567838)) |
| 식재료비 | 41.0% of cost ≈ **37% of revenue** | 40.7% (2024) |
| 인건비 | 34.2% ≈ **31% of revenue** | 33.2% (2022), of which 대표자 14.9%, 고용인 14.8%, 가족 3.5% ([KREI leaflet](https://www.krei.re.kr/namo/binary/files/000025/2403_Leflet_4.pdf)) |
| 임차료 | 9.3% ≈ **8.4% of revenue** | 9.6% (2022); 88.3% of stores rent; avg deposit ₩3,301만 |
| 영업이익률 | **9.4%** | 8.7% (2024), down from 12.1% (2020) |
| Staff | **3.2** (18.3% unpaid family); ₩7,099만 revenue per worker | Independents 2.7 (2018) |

**Caveat:** 영업이익 here is measured *after* imputed owner wage, so owner take-home is margin plus the 대표자 인건비.

### Operations

| Item | Value | Source |
|---|---|---|
| 평수 / tables / seats | 30평, 15 tables, 60 seats. Franchise case in 미금 (Seongnam, not Seoul), 2021 | [한경비즈니스](https://magazine.hankyung.com/business/article/202103043150b) |
| Dinner turnover | "3+ per day" appears only in the unsourced blog. **UNVERIFIED** | blog above |
| 영업시간 | 외식 avg 10.6h/day appeared in a search summary; the page I opened did not state it. **UNVERIFIED**. One Seoul pork store runs evenings only, 6h | [머니투데이 2022](https://www.mt.co.kr/culture/2022/09/01/2022090109505555998) |
| 알바 시급 2026 | ₩10,320 (+2.9%); monthly at 209h = ₩2,156,880 | [bizforms](https://www.bizforms.co.kr/365guide/view.asp?number=162) |

### 월매출

| Range | Basis | Source |
|---|---|---|
| ~₩1,900–2,450만 | National averages: non-franchise and 한식 | 농식품부 2024 |
| ~₩3,000만 | 30평 franchise case | 한경비즈니스 2021 |
| ~₩9,000만–1억 | Top-tier outliers: 한남/삼성 store; a franchise case netting nearly ₩0 at that revenue | [머니투데이](https://www.mt.co.kr/culture/2022/09/01/2022090109505555998), [아시아경제 2025](https://www.asiae.co.kr/visual-news/article/2025101015353443475) |

**Working prior for a small independent Seoul store: ₩2,000–5,000만/month.** This is UNVERIFIED as a Seoul pork statistic. Calibrate it against 상권분석서비스 한식음식점 추정매출 ÷ 점포수 for the target 상권.

### 폐업률 / 생존율

| Figure | Source |
|---|---|
| 한식음식점 5-year survival 34% (국세청, 2023 data) | [택스워치](https://www.taxwatch.co.kr/article/tax/2025/08/13/0002) |
| 100대 생활업종 average: 3-year 53.8%, 5-year 39.6% | [한국경제](https://www.hankyung.com/article/2025043073077) |
| Seoul 한식 3-year survival ~70% (LOCALDATA-based) | [dhnews](https://dhnews.co.kr/news/view/1065577402337354) |
| 외식업 폐업률 2023: national 21.52%, Seoul 18.99%; 쌈밥 44.38% (핀다 오픈업) | [한경비즈니스](https://magazine.hankyung.com/business/article/202404281767b) |
| Seoul Q1 2025: 개업 8,772 vs 폐업 14,988; new-store 1-year survival 78.2% (category scope unclear in the article) | [한국경제](https://www.hankyung.com/article/2025060190501) |

The spread between 34% and 70% is the same definitional effect Parsa describes: 사업자 폐업 vs 인허가 closure. Pick one definition and state it.

**Gaps:**
- There is no pork-BBQ-specific 한식 revenue or cost data newer than 2018.
- 2024 소상공인실태조사 dropped revenue and cost items ([파이낸셜뉴스](https://www.fnnews.com/news/202603130840507888)).
- I did not open the 2025 외식업체 경영실태조사 full report for a 2024 육류 breakdown. Only press summaries were available.