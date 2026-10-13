# Ontology: the driver tree

Every layer (research workbook, simulation, API, ontology explorer, RAG citations) reads these three files.

| File | One row per | Key columns |
|---|---|---|
| `criteria.csv` | criterion (node) | `criterion_id`, `category`, `driver_node` (parent in the tree), `unit`, `method`, `source_id`, `industry_scope`, `in_sim` |
| `edges.csv` | causal link | `from_id → to_id`, `sign` (+ / − / ±), `mechanism_ko`, `source_id`, `confidence` |
| `sources.csv` | evidence | `source_id`, title, publisher, year, url, `type`, reliability note |

## How it works

The top of the tree is plain arithmetic, so any node's effect on profit can be traced:

```
영업이익 = 매출 − 총비용
매출     = 착석고객수 × 객단가 × 영업일수
착석고객수 = f(도착률, 좌석수, 체류시간, 대기이탈률, 영업시간)      (static P&L: 좌석 × 점유율 × 회전율)
객단가   = 인분/인 × 고기가 + 병/인 × 주류가 + 식사·사이드
총비용   = 식재료비 + 인건비 + 임차료 + 관리비 + 수수료
```

- `drv_*` rows are the driver nodes. `driver_node` is each row's parent, so `criteria.csv` alone rebuilds the
  tree. `edges.csv` adds the extra causal links (a criterion can move more than one driver) and the signs.
- Every team-doc criterion maps to one driver. Duplicates in the doc (평수 / 가게 평수, 발주 / 발주량,
  통삼겹 / 대패·냉삼·숙성·통삼) are merged into one row, and the note says so.
- `lbl_*` rows are the success labels: survival months and closed-within-24-months (primary, public 인허가
  data), relative revenue tercile and RevPASH (secondary), review signals (leading indicator only).
- `method`: `public` (a public dataset fills it), `guesstimate` (low/base/high with a reasoning chain),
  `interview_later`, or `derived` (computed from other nodes; never typed in).
- `source_id` may hold several ids separated by `;`. Blank means no source exists yet; the workbook then
  forces confidence L. `D0930` is the team's scope decision, not evidence for any number.
- `build_workbook.py` refuses to run if any id in any file does not resolve (unknown source, unknown node,
  bad sign).

Values do not live here. Hero-store values live in `research/guesstimate.xlsx` (seeded by
`research/build_workbook.py`); the simulation reads `research/hero_base.yaml`.

## Adding an 업종 (카페, 양고기집)

1. **Keep every `industry_scope = generic` row.** Revenue/cost identity, seats, labor, rent, fees, region,
   labels: these are the same for any restaurant.
2. **Swap the `bbq` rows for the new template.** Only rows that describe the product or the table
   experience are industry-specific:
   - 양고기집: close to bbq. Rename the meat rows (`prd_meat_price` → 양갈비 가격), keep grilling and dwell.
   - 카페: drop grilling (`prd_chobeol`, `svc_staff_grilling`, `cst_utilities` charcoal), rewrite `drv_ticket`
     as 음료 + 디저트, add `takeout_share` and a laptop-dwell driver (`sto_wifi` becomes `in_sim = Y`).
3. **Re-point the edges** of the swapped rows; generic edges stay.
4. Add any new evidence to `sources.csv` first, then cite it.
5. Point `industry/<x>.yaml` at the new 소분류 / 서비스 codes, rerun the pipelines, rerun
   `research/build_workbook.py` with the new hero values, and check the Checks tab against that
   업종's own anchor and cost shares.

The simulation engine, loaders, API and UI do not change; they read whatever nodes and edges exist.
