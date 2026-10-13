# Port to 양고기집 (양꼬치/양갈비): same frame, different config

Date: 2026-10-01. Proves the "같은 틀로 복제" claim. Only `industry/lamb_bbq.draft.yaml` and this file are new;
`pork_bbq.yaml` and every pipeline are untouched. All counts come from local files already downloaded by the pork
pipelines:
- `data/raw/sbiz/sbiz_20260630.zip`: the Seoul CSV, 554,092 stores.
- `data/raw/seoul_trdar_relm_OA-15560.zip`: 1,650 상권 polygons, point-in-polygon in EPSG:5181.
- `data/raw/seoul/VwsmTrdarSelngQq/*.csv.gz`: all 상권 × service codes.

Web sources were opened unless marked otherwise.

## 1. Classification: there is no lamb code

- The 2023+ 상권업종 classification has no 양고기 소분류. Within 대분류 I2 (음식), the 중분류 are I201 한식, I202 중식,
  I203 일식, I204 서양식, I205 동남아, I206 기타 외국, I207 구내식당, I210 간이, I211 주점, I212 비알코올. None of the
  소분류 names mention 양.
- **Filter that works:** store-name keywords across I2, then drop I212 (cafés).
  - Regex: `양꼬치|양갈비|양고기|징기스칸|칭기즈칸|양육관|양다리|양뼈|라무진|羊`
  - Dropping I212 removes two cafés whose branch names are "건대양꼬치" and "성수양꼬치", the street name.
- **Seoul-wide: 680 stores.** Where lamb shops actually sit in the classification:

| 소분류 | Stores | Share |
|---|---|---|
| I20201 중국집 | 545 | 80% |
| I20107 돼지고기 구이/찜 | 64 | 9% |
| I21104 요리 주점 | 35 | 5% |
| Scattered (I20101, I20501 베트남식, I20301 일식 회/초밥, …) | 36 | 5% |

  The scattered group is mostly the 라무진 franchise: 25 stores, misfiled under 베트남식 and 일식 회/초밥. A code-only
  filter would miss them.
- Keyword hits by term: 양꼬치 584, 양갈비 51, 라무진 25, 징기스칸 4.
- Branch name present (franchise hint): 13.1% of lamb stores, vs 6/27 for pork in 대학로.
- Keyword false negatives (lamb shops with no keyword in the name) are not measured. Treat counts as a floor.

**Consequence for the pipeline.** `fetch_sbiz.py` filters on `sbiz.primary_codes` only. A lamb run needs a new
`sbiz.name_keywords` filter applied inside I2. That is a pipeline change; the config key is drafted but no code
reads it yet. `fetch_license.py` already supports `license.name_keywords`.

## 2. Where lamb lives in Seoul

By 구: 영등포 83, 구로 71, 송파 52, 강남 48, 광진 40. Top 상권 (point-in-polygon; 91 of 680 stores fall outside
any 상권 polygon):

| 상권 | Type | Lamb stores | I20201 stores | 중식 sales 2025 (CS100002) | Evening share (17–24h) | 20대 share |
|---|---|---|---|---|---|---|
| **3110140 건대입구역 6번** (양꼬치거리) | 골목 | **12** | 44 | ₩131.2억 | **74%** | **29%** |
| 3120142 대림역 | 발달 | 12 | 82 | ₩359.1억 | 57% | 8% |
| 3110710 남구로역 3번 | 골목 | 11 | | | | |
| 3120229 방이동먹자골목 | 발달 | 10 | | | | |
| 3120053 건대입구역(건대) | 발달 | 6 | 34 | ₩108.7억 | 67% | 41% |
| **3120012 대학로(혜화역)** | 발달 | **3** | 26 | ₩56.3억 | 65% | 16% |

- Clusters: every 상권 named 대림 together holds 33 lamb stores; the two 건대 상권 hold 18.
- **Recommendation for the demo: primary 3110140, fringe 3120053.**
  - Densest single 상권 for lamb.
  - Its 중식 sales are evening-heavy (74%) and young (29% 20대). The customer mix resembles 대학로's, so the
    twenties/office/family segment logic carries over with refit factors.
  - Adjacent to 건국대, which gives a vacation test.
- 대림 is the bigger market by sales. Its customers differ (20대 8%, daytime-heavy), and 대림's 중식 code mixes in many
  non-lamb Chinese restaurants. Keep it as the second twin, not the first.
- 대학로 (3 stores) is too thin for a lamb twin.
- Caveat: CS100002 중식음식점 sales include 짜장면 places. In 3110140, lamb shops are 12 of the 44 stores coded
  I20201. The 상권 sales are a context signal, not lamb revenue.

## 3. Driver tree: what carries over

The ontology splits rows into 77 generic and 21 bbq rows (`industry_scope`).
- **All 77 generic rows carry over unchanged:** the P&L identity, seats, labor, rent, fees, region, labels, patience,
  party size, elasticity and segment structure.
- The 21 bbq rows:

| bbq row | Lamb treatment |
|---|---|
| `drv_ticket` | Same identity; components re-labelled: 꼬치/양갈비 인분 × price + 요리 (꿔바로우, 마라 등) + 주류 |
| `drv_dwell_time` | Keep. New modifier for 무한리필 formats with a time limit (one 건대 store sells a 30-min extension for ₩4,000/인, S76) |
| `prd_meat_origin` | Becomes import origin (호주 ~88% of Korean lamb imports, Tridge page, UNVERIFIED) |
| `prd_cut_style` | Becomes **`prd_lamb_rib_share`** (share of 양갈비 vs 꼬치 orders) |
| `prd_chobeol` | Becomes **`prd_preskewered`** (buys pre-skewered vs skewers in-house, which is prep labor) |
| `prd_signature_side` | 쯔란 / 요리 메뉴 |
| `prd_meat_price` | 양꼬치 1인분 (10꼬치) price; second price for 양갈비 |
| `prd_portion_grams` | **`prd_skewers_per_portion`** × g per skewer |
| `prd_portions_per_cover` | Keep |
| `prd_side_spend_per_cover` | Keep; 요리 share is larger than pork's 식사 |
| `cst_alcohol_meat_ratio` | Keep |
| `svc_staff_grilling` | Replaced by **`svc_auto_rotisserie`** (자동 회전 꼬치 구이기 Y/N). Cuts the staff-grill minutes in SIM_ASSUMPTIONS; no source for its dwell effect |
| `cst_banchan_cost_per_cover` | Keep row, lower value (땅콩, 짜사이, 양배추) |
| `seg_*_alcohol_factor` | Keep, refit |
| `reg_competitors` | Lamb store count from the keyword filter |
| `cst_meat_cost_per_portion` | Rebuilt from the import chain: AUD/kg × KRW/AUD × (1 + importer/distributor margin) × kg per portion |
| `cst_side_cost_ratio`, `cst_order_volume`, `cst_utilities` (숯) | Keep |

New nodes the lamb template needs:
- **`prd_alcohol_mix`**: shares of 소주 / 칭따오·하얼빈 / 고량주, each with its own price and cost. Imported beer
  and 고량주 make the alcohol line FX-exposed too.
- **`cst_lamb_import_price_aud`**: input.
- **`cst_fx_krw_aud`**: input.
- **`cst_import_passthrough`**: share of restaurant meat cost that moves with landed price. UNVERIFIED; draft 0.7.

## 4. Prices and costs (sourced where findable)

| Item | Value | Source |
|---|---|---|
| 양꼬치 1인분 (10꼬치), 건대 | ₩16,000 (경성 양육관), ₩18,000 (연길 왕꼬치) | S75 (polle listings) |
| 양꼬치 1인분, 송파 방이동 | ₩17,000; 양고급갈비 ₩23,000 | S75 |
| 양갈비살 | ₩23,000–25,000 | S75 |
| 양꼬치 무한리필 (건대) | ₩19,900/인; 30-min extension ₩4,000 | S76 |
| 칭따오 / 연태고량 at restaurants | ₩5,000–7,000 | **UNVERIFIED** (search snippets only) |
| Imported lamb, sample landed price | US$15.0–17.8/kg (Sept 2026 sample transactions) | Tridge sample page, weak, S77 |
| Implied meat cost per 1인분 | ₩3,100–4,800 for 150–200g at ₩1,358/USD, before importer margin and trim | derived |
| Tariff | 22.5% sheepmeat tariff phased out under KAFTA by 2023-01-01 | search snippet of DFAT (PDF timed out), **UNVERIFIED** |

**Import price trend.** Australian lamb is in a supply squeeze (KREI 세계농업 2026 봄호, 강지석, citing ABARES; S78).
For 2025/26:
- Lamb meat production −14%.
- Average export unit price A$8.7 to A$11.2/kg, **+29.1%**.
- Lamb saleyard price **+31%** (A$10.85/kg cwt). Mutton +63%.
- Real lamb price possibly a record high.

**Exchange rate (ECB reference rates, KRW per AUD, cross via EUR; S79).**

| Period | KRW per AUD |
|---|---|
| 2024 average | 899.7 |
| 2025 average | 916.5 |
| 2026 Jan–Sep average | 1,028.4 |
| Peak month (2026-06) | 1,075.3 |
| 2026-09-30 | 944.4 |

Monthly year-on-year change, 2021–2026 (n = 57): p10 −3.2%, median +3.0%, p90 +12.2%, max **+21.1%** (2026-06).

## 5. Shock list for lamb

Pork shocks that carry over unchanged: SH01/SH02 (price ±), SH05 (drinking down), SH06 (wage), SH07 (staff),
SH08 (rent, same 5% renewal cap), SH10 (rain), SH11 (competitor).

| id | Parameter | low / base / high | Basis |
|---|---|---|---|
| **SHL03** (replaces SH03) | `cst_lamb_import_price_aud` | +10% / **+29%** / +63% | ABARES 2025/26 export unit price +29.1%; mutton +63% as the high case if skewers use mutton (UNVERIFIED) (S78) |
| **SHL12** (new) | `cst_fx_krw_aud` | +3% / **+12%** / +21% | ECB KRW/AUD monthly YoY median / p90 / max (S79). Also a relief case of −8% (min YoY) |
| SHL03 × SHL12 | `cst_meat_cost_per_portion` | | Combine multiplicatively, scaled by `cst_import_passthrough`. Base case: (1.29 × 1.12 − 1) × 0.7 ≈ **+31%** to restaurant meat cost |
| SH04 → **SHL04** | `prd_alcohol_mix` prices | | Imported beer and 고량주 also move with FX; second-order |
| SH09 | `drv_arrival_rate` | −3% / **−5%** / −10% | 3110140 중식 Q3/Q2 = 0.931 (2023–25), about −10% per break month by the round-2 method. Fringe 3120053 shows none (1.02). Draft base −5% |

## 6. Rent check (R-ONE, same method as round 2)

- 서울>기타>건대입구, 소규모 상가 1층 2026Q2: **₩51,451/㎡/월**, vacancy 11.2%.
- 혜화동 is ₩60,033/㎡ with 2.1% vacancy.
- Same table T248223134698125, CLS_ID 520032.
- 건대 is about 14% cheaper per ㎡ with more vacancy. The rent node carries over; only the value changes.

## 7. What it would take to run

1. **Pipeline:** implement `sbiz.name_keywords` in `fetch_sbiz.py` (keyword filter inside the I2 prefix, excluding
   I212). It is the only code change.
2. **Pipeline:** switch the license service to the 광진구 per-구 LOCALDATA service. The service suffix and
   `opnsfteam_codes` for 광진구 are **UNVERIFIED**; the draft leaves placeholders.
3. **Ontology:** swap the 21 bbq rows per §3 and add the 4 new nodes.
4. **Workbook:** a new hero in the workbook (lamb prices above, rent ₩51,451/㎡), plus the two new shocks.
5. **Unchanged:** sim engine, API and UI. They read whatever nodes, edges and shocks exist (`ontology/README.md`).

## Sources (proposed IDs, continuing from S74)

| id | Title | Publisher | Date | URL |
|---|---|---|---|---|
| S75 | 양꼬치 menus: 경성 양육관 건대, 연길 왕꼬치 건대, 미성 양꼬치 방이동 | polle.com listings | n.d. | https://polle.com/place/3fpSdY ; https://polle.com/place/2j4KfY ; https://polle.com/place/4Fmkpa |
| S76 | 미친 양꼬치 (건대) 무한리필 ₩19,900, 30분 연장 ₩4,000 | polle.com listing | n.d. | https://polle.com/place/1ZPS8d |
| S77 | South Korea fresh boneless lamb import samples (US$15.0–17.8/kg) | Tridge (sample, paywalled detail) | 2026-09 | https://www.tridge.com/ko/intelligences/lamb/KR/import |
| S78 | 2025/26년 호주 농업 전망: 축산부문 (세계농업 2026 봄호) | KREI, 강지석 (ABARES data) | 2026 | https://repository.krei.re.kr/bitstream/2018.oak/32818/1/ |
| S79 | Euro foreign exchange reference rates, history (KRW, AUD, USD) | European Central Bank | pulled 2026-10-01 | https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.zip |
| S52 | 상업용부동산 임대동향 R-ONE (건대입구 CLS 520032) | 한국부동산원 | 2026Q2 | see sourcing_round2.md |
| S12, S20 | 상권 추정매출 / 상가정보 (local raw files) | 서울시 / 소진공 | 2025, 2026-06 | see ontology/sources.csv |
