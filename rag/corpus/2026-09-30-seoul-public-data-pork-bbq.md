_2026-09-30, research agent for the Team 1 고깃집 project. Counts from live downloads/sample APIs at run time._

# Free data for a Seoul pork BBQ 상권 digital twin (checked 2026-09-30)

**Short answer:** I recommend **대학로(혜화역), 상권코드 3120012**. It has 191 한식 stores, 27 돼지고기 구이 stores inside its boundary, full data coverage, and it is walking distance from 명륜. One catch: the Seoul 매출 data has no category finer than 한식음식점 (CS100001), so pork-level detail has to come from the 소상공인 store list (소분류 I20107).

I downloaded the actual files or called the sample APIs for every dataset below; the counts and field names come from those runs, not from the documentation. All downloaded files were deleted afterwards, and no API key was used.

## 1. 서울시 상권분석서비스 (data.seoul.go.kr)

- **Common to all:**
  - Owner: 서울특별시. Provider: 서울신용보증재단.
  - License: 공공누리 1유형 (commercial use and changes allowed).
  - Granularity: 상권 (about 1,650 areas); separate versions exist per 행정동, 자치구 and 상권배후지.
  - Access: CSV files (where offered) plus OpenAPI at `openapi.seoul.go.kr:8088/{KEY}/json/{SERVICE}/{start}/{end}/{STDR_YYQU_CD}`.
  - Key: the `sample` key works with no signup but returns at most 5 rows. Pulling everything needs a free Seoul key (1,000 rows per call).
  - Since 2026-07-03, only 2021 onward is served, because the areas moved to 표준단위구역 in 2024.

| Dataset | ID / API service | Cadence (page says) | Key fields (checked) |
|---|---|---|---|
| 추정매출-상권 | [OA-15572](https://data.seoul.go.kr/dataList/OA-15572/S/1/datasetView.do) / `VwsmTrdarSelngQq` | 분기별 (quarterly); yearly zips 2021–2025 | 기준_년분기_코드, 상권_코드, 서비스_업종_코드; sales amount and count split by 주중/주말, 월~일, 6 time bands (00-06, 06-11, 11-14, 14-17, 17-21, 21-24), 성별, 연령대 10–60+ |
| 점포-상권 | [OA-15577](https://data.seoul.go.kr/dataList/OA-15577/S/1/datasetView.do) / `VwsmTrdarStorQq` | 년간 (rows are quarterly) | stor_co, similr_induty_stor_co (= total), frc_stor_co (franchise), opbiz_rt / opbiz_stor_co (openings), clsbiz_rt / clsbiz_stor_co (closures) |
| 길단위인구-상권 | [OA-15568](https://data.seoul.go.kr/dataList/OA-15568/S/1/datasetView.do) / `VwsmTrdarFlpopQq` | 월간 (rows quarterly) | TOT/ML/FML_FLPOP_CO, age bands, 6 time bands, 요일 |
| 상주인구-상권 | [OA-15584](https://data.seoul.go.kr/dataList/OA-15584/S/1/datasetView.do) / `VwsmTrdarRepopQq` | 반기 | age × sex, TOT/APT/NON_APT_HSHLD_CO |
| 직장인구-상권 | [OA-15569](https://data.seoul.go.kr/dataList/OA-15569/S/1/datasetView.do) / `VwsmTrdarWrcPopltnQq` | 반기 | age × sex worker counts |
| 집객시설-상권 | [OA-15580](https://data.seoul.go.kr/dataList/OA-15580/S/1/datasetView.do) / `VwsmTrdarFcltyQq` | 년간 | UNIV_CO, SUBWAY_STATN_CO, BUS_STTN_CO, THEAT_CO, BANK_CO, etc. |
| 소비-상권 | [OA-21278](https://data.seoul.go.kr/dataList/OA-21278/S/1/datasetView.do) / `trdarNcmCnsmp` | 반기 | spending totals by category only |
| 영역-상권 | [OA-15560](https://data.seoul.go.kr/dataList/OA-15560/S/1/datasetView.do) / `TbgisTrdarRelm` | 비정기 | **Shapefile of 상권 boundaries (EPSG:5181)**: TRDAR_CD, center X/Y, SIGNGU_CD, ADSTRD_CD, RELM_AR |
| 상권변화지표-상권 | [OA-15576](https://data.seoul.go.kr/dataList/OA-15576/S/1/datasetView.do) / `VwsmTrdarIxQq` | 년간 | TRDAR_CHNGE_IX (e.g. 정체), average months open and months to closure |

- 상주, 직장 and 집객 have no downloadable file ("파일이 없습니다"); get them through the API or the page's sheet export. They are refreshed once a year (Q4), so the next year's Q1–Q3 repeat that value.
- **소비-상권 has no income data.** 월평균소득 was removed on 2026-05-13, 소득구간 was nulled, and the page says the dataset is no longer updated. For income, the page points to 국세통계포털 and 국민연금 figures by 자치구.
- **Food codes:** there are exactly 10 외식 codes, CS100001–CS100010. 한식음식점 is CS100001. **There is no finer code for 고기**; I checked all 62 industry codes in the 2025 file.

## 2. 소상공인시장진흥공단 상가(상권)정보

- **URL:** [data.go.kr/data/15083033](https://www.data.go.kr/data/15083033/fileData.do). The current file is `_20260630` (registered 2026-08-05); next one due 2026-10-31.
- **Access:** quarterly CSV zip split by 시도, UTF-8. Free, 이용허락범위 "제한 없음", and the file downloads without a key. The Seoul file has 554,092 rows.
- **Grain:** one row per currently open store.
- **Fields:**
  - 상가업소번호, 상호명, **지점명** (the franchise hint)
  - 대/중/소분류 코드 and names; 표준산업분류 code
  - 시군구코드, **행정동코드**, 법정동코드
  - 지번 and 도로명 주소, 건물관리번호, 층정보
  - **경도/위도 (WGS84)**
- **Pork code:** **I20107 = "돼지고기 구이/찜"**, under I2 음식 → I201 한식. Seoul has **7,834** of these.
  - Neighbouring codes: I20108 소고기 구이/찜 (911) and I20109 곱창 (1,335).
  - All of them roll up to 표준산업분류 I56111 한식 일반 음식점업.

## 3. 인허가 data (일반음식점)

- **localdata.go.kr is gone.** 행정안전부 moved the 195 license types to data.go.kr as APIs in January 2026 ([경향 2026-01-25](https://www.khan.co.kr/article/202601251400011/)).
  - The old national CSV link on [data.go.kr/15045016](https://www.data.go.kr/data/15045016/fileData.do) now redirects to a 403 error.
  - The replacement API is [data.go.kr/15154916](https://www.data.go.kr/data/15154916/openapi.do) (`apis.data.go.kr/1741000/general_restaurants`). It updates daily and needs a free, auto-approved data.go.kr key (10,000 calls per day). I did not confirm its field list without a key.
- **Easiest source for Seoul:** [서울시 일반음식점 인허가 정보 OA-16094](https://data.seoul.go.kr/dataList/OA-16094/S/1/datasetView.do), API `LOCALDATA_072404`. It updates daily, has 538,197 rows (open and closed), and is 공공누리 1.
- **Fields I confirmed in live rows:**
  - 인허가일자 (APVPERMYMD), 폐업일자 (DCBYMD)
  - 영업상태명 / 상세영업상태명
  - **소재지면적 (SITEAREA) is present and filled**, e.g. 29.70. It is in **㎡**, so divide by 3.3058 for 평.
  - 시설총규모, 업태구분명 (e.g. 한식)
  - 종사자수, 보증액/월세액 (mostly empty)
  - X/Y in **EPSG:5174**
- **What this gives you:** a survival label per store (open date → closure date) plus floor area. That is the only free store-level source with closed stores in it.

## 4. Other sources

- **우리마을가게 상권분석 ([golmok.seoul.go.kr](https://golmok.seoul.go.kr/)):** the web front end for the same 상권 data, with ready-made reports per area. It defines the 100 생활밀접업종 codes (see the FAQ on OA-15572). It adds no new data.
- **소상공인365 ([bigdata.sbiz.or.kr](https://bigdata.sbiz.or.kr/)):** web reports built on the same store list; the site loads. It is the reference for the classification changes. Use it for cross-checks, not bulk data.
- **참가격 외식비 (price.go.kr):** it blocked my connection from here. Monthly 삼겹살 200g restaurant prices by 시도 do exist. As reported secondhand, Seoul was ₩21,321 last month, up 4.3% year on year ([세계일보](https://www.segye.com/newsView/20260801501857)). Enter these by hand as a price input.
- **KOSIS 소상공인실태조사:** the 2024 survey was released 2026-03-13. It gives 숙박·음식점업 totals of 796,000 businesses and ₩83M average startup cost ([파이낸셜뉴스](https://www.fnnews.com/news/202603130840507888)). This is national/sector level only; use it to calibrate cost structure.
- **Scraping flags:**
  - **Naver Place/Map:** robots.txt disallows `/` for all bots and explicitly bans AI training and RAG use. Do not scrape; enter data by hand in small amounts.
  - **캐치테이블:** robots.txt allows only named search-engine crawlers; the terms prohibit automated collection. Do not scrape.
  - **테이블링:** robots.txt returned 403. Assume collection is not allowed.

## 5. Choosing the 상권

2025 figures below are for 한식 (CS100001) only. Store counts are as of 2025 Q4. The pork count is I20107 stores whose coordinates fall inside the 상권 boundary.

| 상권 (code) | 한식 stores (franchise) | 2025 openings / closures | I20107 pork | 2025 한식 card sales | 20대 / 30대 share | Evening 17–24 / lunch |
|---|---|---|---|---|---|---|
| **대학로(혜화역) 3120012**, 혜화동, 종로구 | 191 (31) | 25 / 11 | **27** | ₩591억 | 28% / 25% | 63% / 21% |
| 성균관대학교 3110021 (골목, next door) | 19 (2) | 0 / 2 | 1 | ₩27억 | 35% / 17% | 64% / 19% |
| 신촌역 3120094 | 342 (46) | 39 / 46 | **64** | ₩817억 | 34% / 22% | 62% / 20% |
| 을지로3가역 3120031 | 185 (16) | 44 / 22 | 19 | ₩1,002억 | 24% / 32% | 65% / 27% |
| 성수역 3120052 | 160 (16) | 20 / 22 | 24 | ₩638억 | 23% / 32% | 51% / 37% |

- **Why 대학로:**
  - It is walkable from campus for fieldwork.
  - It has 27 pork stores, of which 6 have a 지점명 (possible franchise), so about 20 are independent candidates.
  - Demand is a real mix of 20대 and 30대, and 63% of sales are in the evening, which fits a 구이집.
  - Closures are low (11 in 2025), which makes survival modelling harder. Getting closed stores from the 인허가 data is essential here.
- **Optional wider study area:** add 3110021 성균관대학교, 3110024 혜화동주민센터 and 3110027 혜화역 1번 as a fringe.
- **Backup choice: 신촌역.** It has more than twice the pork stores and more closures (better for survival labels). It is more student-heavy and farther from campus.
- **Weaker options:**
  - 을지로 leans toward office workers (32% 30대, 27% lunch).
  - 성수 has the lowest evening share (51%) and the highest lunch share (37%), so it looks more like an office/lunch area, and it has high churn.

## 6. Join keys

- **상권코드 (TRDAR_CD, 7 digits):** links all 상권분석서비스 tables and the boundary shapefile.
- **행정동코드 (8 digits):** in the boundary shapefile (ADSTRD_CD) and the store list (행정동코드), and links to the 행정동 versions of the tables. It uses the 행정안전부 code, not the 통계청 code.
- **Coordinates → 상권 boundary:**
  - Store list is WGS84 → convert to EPSG:5181 → point-in-polygon against the shapefile.
  - 인허가 data is EPSG:5174 (Bessel, unshifted), so it needs its own conversion.
  - I tested this conversion on the 대학로 boundary and it matched the published center point.
- **Store list ↔ 인허가:** there is no shared business ID. Match on 도로명주소 (or 건물관리번호 on the store-list side) plus a fuzzy 상호명 match plus distance under about 20 m.
- **Time:** STDR_YYQU_CD (e.g. 20254) joins to quarter-end snapshots of the store list and 인허가 status.

## 7. Pitfalls

- **Sales are estimates:** 추정매출 is card-company data scaled up. The 당월_매출_금액 column is actually a quarterly total despite its name.
- **Totals don't add up:** age and sex splits leave out corporate cards, so they sum to less than the total (stated in the FAQ).
- **Suppressed cells:** small 상권 × 업종 combinations show 0 or are missing.
- **One mismatched industry code:** CS100001 covers every 한식 restaurant. Pork demand has to be allocated using the I20107 share of stores, which is an assumption.
- **Boundaries changed:** 상권 moved to 표준단위구역 in 2024, and only data from 2021 onward is served. Don't mix older downloads.
- **Different kinds of 상권:** 발달상권, 골목상권, 전통시장 and 관광특구 have different boundary logic. For example, the 종로·청계 관광특구 overlaps 종로3가.
- **Encodings and headers:** Seoul CSVs are **cp949**; the store-list CSV is UTF-8 with BOM. The 2025 매출 CSV has Korean headers, but the 2025 점포 CSV has English lowercase headers (`trdar_cd`).
- **Values repeated across quarters:** 상주, 직장 and 집객 repeat the Q4 value in the following Q1–Q3, so they don't really vary within a year.
- **Store list is a snapshot:** it has only stores open now. Closures must come from 인허가 data (DCBYMD) or by comparing quarterly snapshots.
- **Area units:** SITEAREA is ㎡ and some entries are missing or 0, so clean it before converting to 평.