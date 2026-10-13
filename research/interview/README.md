# Owner interview kit: one interview = one twin

Files:
- `owner_interview_guide.md`: the Korean script for members. It has 25 questions, starts with rapport, puts money
  questions last, and includes the consent text and anonymisation rules.
- `answer_sheet_template.csv`: one row per field the interview can fill, pre-keyed by `criterion_id` and
  `question_no`. It is saved as UTF-8 with BOM so Excel opens the Korean correctly; keep "CSV UTF-8" on save.
  Copy it to `T01_answer_sheet.csv` per store. Never put a store or person name in the file name or the cells.

## Row kinds in the answer sheet

The `criterion_id` column holds four kinds of key:

| Kind | Example | Where it goes |
|---|---|---|
| Ontology criterion with a HeroStore row | `drv_dwell_time`, `mkt_patience`, `seg_office_dwell_factor` | HeroStore sheet of `guesstimate.xlsx`, so `hero_base.yaml` |
| `sim.<name>` | `sim.svc_clear_min`, `sim.dwell_sigma` | `SIM_ASSUMPTIONS` in `sim/params.py`. These have no criterion row yet; promoting them is a code change, owned by whoever owns `sim/` |
| Raw observation | `teams_per_night`, `bottles_per_table`, `meat_cost_per_kg`, `vacation_index` | Not applied directly. Converted into a criterion or shock value (rules below), or used as a calibration check |
| `owner_reaction.<shock_id>` | `owner_reaction.SH03` | The twin's owner policy (an action id from `sim/owner_actions.MENU` plus its argument). Not a workbook value |

Two keys exist in `criteria.csv` but have no HeroStore row: `cst_order_volume` (derived in the P&L) and
`lbl_survival_months` (a label). Use the interview values only as checks. `cst_employer_burden_rate` is proposed in
`sourcing_round2.md` and does not exist yet.

## From filled sheet to `accepted_patch.yaml`

**The applier is `research/build_workbook.py --apply-patch <patch.yaml> [--out DIR]`.** It reads this
interview shape (`hero:` and `shocks:`) and the guesstimation helper's `research/review/accepted_patch.yaml`
(top-level criterion ids). Rules:
- A row is applied only when it names a reviewer: the row's `reviewed_by`, or `_meta.reviewed_by` for an interview
  patch.
- It refuses rows with no reviewer, an unknown criterion / shock row / `source_id`, or `base` outside
  [low, high]. Refused rows are printed as `REFUSED <id>: <reason>`.
- `sim_assumptions`, `owner_policy` and `rejected` are reported, not applied, because they are not workbook values.
- Every applied field change goes to the workbook's `ChangeLog` sheet (criterion, field, old, new, source,
  reviewer, date, patch).
- `unit` and `method` still come from `ontology/criteria.csv`, so "this came from an interview" is carried in
  `source_id` and `reasoning_chain`.

Steps:
1. **Two-person check.** The interviewer and note-taker reconcile the sheet within 30 minutes of leaving. A third
   member reviews it.
2. **Convert raw rows.** Use the rules in the next section, and show the arithmetic in the patch `reasoning`.
3. **Write `research/interview/T01/accepted_patch.yaml`.** Include only rows the reviewer accepted:

```yaml
_meta:
  twin_id: T01
  interview_date: 2026-10-XX
  consent: Y
  interviewer: <member>
  reviewed_by: <member, not the interviewer>
  source_id: INT-T01          # add one row to ontology/sources.csv: type=interview, no identifying fields
hero:                         # keys = HeroStore criterion_id; fields = HeroStore columns
  drv_dwell_time:
    low: 80                   # answer_low
    base: 100                 # answer_typical
    high: 130                 # answer_high
    confidence: M             # from the sheet: H = 장부/POS/계약서, M = confident recall, L = guess
    reasoning_chain: "T01 사장님 인터뷰 Q8: 보통 1시간 40분, 학생 팀 1시간 20분, 회식 2시간 10분"
    source_id: INT-T01
    filled_by: <interviewer>
    reviewed_by: <reviewer>
shocks:                       # keys = Shocks sheet shock_id + parameter; fields = SHOCK_COLS
  SH09:
    parameter: drv_arrival_rate
    delta_low: -0.10
    delta_base: -0.15
    delta_high: -0.25
    rationale: "T01 Q10: 방학 달은 평소의 75~90"
    source_id: INT-T01
    confidence: M
sim_assumptions:              # proposals for sim/params.py, applied by the sim owner
  svc_clear_min: 5
  dwell_sigma: 0.30
owner_policy:                 # sim/owner_actions.MENU ids, args inside MENU bounds
  SH03: {action: reprice, args: {pct: 0.07}, experienced: true, note: "2025년에 실제로 1,000원 올림"}
  SH06: {action: cut_staff_hours, args: {hours: 1.0}, experienced: false}
rejected:                     # rows the reviewer did not accept, with reason
  drv_rent: "사장님이 구간 답변 거부"
```

4. **Build the twin without touching the composite hero.** Add the interview's source row (e.g. `INT-T01`) to
   `ontology/sources.csv` first, then:

   ```
   .venv/bin/python research/build_workbook.py --apply-patch research/interview/T01/accepted_patch.yaml \
       --out research/interview/T01
   ```

   This writes `guesstimate.xlsx`, `hero_base.yaml` and `shocks.yaml` into `research/interview/T01/`. The composite
   hero files are not touched (tested in `research/tests/test_build_workbook.py`).
5. **Run the twin** with the same commands as the composite, pointed at the twin yaml. Check the calibration rows
   below before reading any shock result.

## Conversion rules for raw rows

| Raw answer (Q) | Becomes | Rule |
|---|---|---|
| `teams_per_night` (Q4) | check on `drv_covers`, `sto_table_turns` | monthly covers ≈ teams × `mkt_party_size` × `sto_open_days`. Compare with the P&L `covers_month`; turns = teams ÷ `sto_tables`. Mismatch > 20% means the twin's demand must be rescaled, not the dwell or patience inputs |
| `party_mix_per_10_teams` (Q6) | `mkt_party_size`, shape check | mean = Σ size × count ÷ 10. If pairs are > 50%, flag that the sim's 1 + Binomial(3, p) shape is wrong for this store (`sourcing_round3.md` §3) |
| `segment_mix` (Q7) | `seg_*` factors | Factors are relative; the store-wide mean stays pinned to `mkt_party_size`, `drv_dwell_time`, etc. (criteria.csv notes) |
| low/high dwell in minutes (Q8) | `sim.dwell_sigma` | σ ≈ ln(high ÷ low) ÷ 2.56 if low/high read as p10/p90 |
| `walkaways_per_month` (Q9) | check on `drv_balk_rate` | rate ≈ walk-away parties ÷ (served parties + walk-aways). `drv_balk_rate` is a sim output: tune `mkt_patience` until the sim reproduces it |
| `vacation_index`, `rain_index` (Q10–11) | SH09, SH10 `delta_*` | delta = index ÷ 100 − 1. The 3120012 district data suggests about −8% (`sourcing_round2.md` §8); an owner answer far outside that is store-specific, keep it |
| `first_order_portions_2p`, `reorder_share` (Q12) | `prd_portions_per_cover`, `sim.initial_order_ratio` | portions/cover = (first-order portions + reorder share × reorder size) ÷ 2. initial ratio = first ÷ total |
| `bottles_per_table` (Q14) | `prd_alcohol_per_cover` | ÷ the party size given in the same answer, never ÷ 2.8 by default |
| `last_price_rise` (Q13) | check on `mkt_price_elasticity` | ε ≈ %Δcustomers ÷ %Δprice. A single episode is evidence for the twin only; do not change the composite's range |
| `meat_cost_per_kg`, `trim_loss` (Q20) | `cst_meat_cost_per_portion` | = ₩/kg × `prd_portion_grams` ÷ 1000 ÷ (1 − trim_loss). Sanity band: KMTA factory-gate ₩18–20k/kg (`sourcing_round3.md` §1) |
| rent band (Q22) | `drv_rent` | Use band midpoints (① 1.5M ② 2.5M ③ 3.5M ④ 4.5M ⑤ 5.5M); low/high = band edges; confidence M at best. R-ONE 혜화동 1층 ₩60,033/㎡ is the cross-check |
| `last_renewal_increase` (Q22) | SH08 | Above 5% means the 5% statutory cap did not apply (환산보증금 over ₩9억 or a new lease). Note it |
| Q19 answers | `cst_holiday_pay_factor` | 주휴 paid and 4대보험 enrolled: 1.33; 주휴 only: 1.20; neither: 1.00 (record it, do not judge it) |

## Which sim parameters each answer moves

| Q | Criterion / constant | What it changes in `sim/` (per `docs/SIMULATION.md`) |
|---|---|---|
| 3 | `sto_open_days`, `drv_open_hours`, `sim.closed_weekday`, `sim.last_seating_before_close` | nights per month, night length, last seating |
| 4–5 | (checks) | arrival level and 요일/time-band shape; `drv_arrival_rate` is derived from P&L covers ÷ (1 − balk) ÷ party size |
| 6–7 | `mkt_party_size`, `seg_*_party_factor`, `sim.max_party` | party draw; seats used per 4-top |
| 8 | `drv_dwell_time`, `sim.dwell_sigma`, `sim.dwell_alcohol_sensitivity`, `seg_*_dwell_factor` | table hold time, so turns, waits and walk-aways |
| 9 | `mkt_patience`, `seg_*_patience_factor` | Gamma(4, mean) patience, so the `balk` events |
| 10–11 | SH09, SH10, `sto_terrace`, `sto_terrace_availability` | demand shocks, nightly terrace draw |
| 12–13 | `prd_portions_per_cover`, `sim.initial_order_ratio`, `prd_portion_grams`, `prd_meat_price` | first order + Poisson reorder, meat revenue, price response |
| 14 | `prd_alcohol_per_cover`, `prd_alcohol_price`, `seg_*_alcohol_factor` | Poisson bottles, alcohol revenue, dwell via alcohol sensitivity |
| 15 | `prd_side_spend_per_cover`, `sim.meal_price` | meal attach probability = side spend ÷ meal price |
| 16 | `sto_tables`, `sto_seats_per_table`, `sto_area_pyeong` | table resource capacity |
| 17–18 | `sto_parttimers`, `sto_parttime_shift_hours`, `sto_employees`, `sto_parttime_wage`, `svc_staff_grilling`, `sim.owner_on_floor`, `sim.svc_*_min` | server resource count and per-party service minutes; labor cost. The staff minutes decide whether SH07 binds (Known limits in SIMULATION.md) |
| 19 | `cst_holiday_pay_factor` | part-timer labor cost |
| 20–21 | `cst_meat_cost_per_portion`, `cst_alcohol_cost_per_bottle` | food cost; SH03 base |
| 22–23 | `drv_rent`, `cst_utilities`, `cst_other_opex`, `cst_card_share` | fixed cost and fees; SH08 base |
| 24 | `owner_policy` | which `owner_actions` function, and which argument, the twin's owner applies after each shock, in place of the LLM owner agent's pick |

## Calibration checks before trusting a twin

- Simulated p50 monthly covers within ±20% of the owner's teams × party size × open days.
- Simulated walk-aways in the same order of magnitude as the owner's count (Q9).
- Alcohol share of revenue matches what the owner's bottles and prices imply (Q14), not the composite's 17–25% test
  band.
- If a check fails, adjust the demand level first (arrival scale). Do not hand-tune dwell or patience to force it;
  those come from the owner's own answers.
