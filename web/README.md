# web: demo front end

```
npm install
npm run sync                        # refresh public/data (ontology, hero, district, lab KPIs; repo .venv)
(cd .. && .venv/bin/python -m sim.precompute --season)   # public/runs: shock x action, base, and the season grid
npm run build
npx vite preview                    # http://127.0.0.1:4173
```

## The v2 game (`#/`, also `#/v2`)

- **시연 모드**: the 4-month story from `public/guided/` (written by `python -m sim.guided`), presenter narration on
  the left, decision options (hover shows the plan in 3D, click plays it). No API needed.
- **자유 플레이**: 6 months on the local API (`VITE_API_BASE`, default http://localhost:8000). Planning board with 14
  levers (each with its upside, modelled downside and 가정/근거 tag), live preview (`POST /season/{id}/preview`),
  the month plays as one Saturday night in 3D, then the 정산 slip (waterfall, p10-p90 band with the draw's
  percentile, cash runway, reputation, review feed: click a review to question that customer). A shadow sandbox
  season plays the 평소 plan with the same events, so the end screen can say whether you beat it. 폐업 = cash below
  zero at two month-ends in a row, or revenue at 60% of 평소 for two months.
- **비교**: two plans, one seed, one month, with the waterfall difference.
- Drawers: 가게 능력치 (driver tree, moved drivers highlighted), 트윈 인터뷰 (`GET /season/{id}/survey`), 상권 (map,
  rent, survival curves from `public/data/season.json`, refreshed by `.venv/bin/python web/scripts/sync_season.py`).
- `#/store?m=1&t=20:30&cam=orbit|fps|street&weather=rain&competitor=1` shows the 3D store alone
  (`node scripts/shoot3d.mjs <dir>` screenshots it).
- Checks: `node ../tests/e2e/game_v2.mjs <webUrl> <outDir> guided|free|all` (headless; guided must not call the API).

## The v1 game (`#/v1`)

1. Map of 대학로 (level select); "가게로 들어가기" zooms into the composite store (symbolic location).
2. The 3D store replays a simulated Saturday night (orbit or first person). HUD: 월 매출, 영업이익, 손님 수,
   기다리다 돌아간 팀, 객단가, 테이블 가동률 against the base month; clock, speed and scrub at the bottom;
   minimap in the corner.
3. 이번 달 사건 (pick one of 11 shocks or draw at random), then a one-sentence headline of its impact.
4. 사장님의 선택: 7 owner actions, each with its expected operating profit from the precomputed runs.
5. The month plays (that run's Saturday night; the HUD moves from the shock-only month to the chosen one),
   then 월말 정산 (receipt: 평소 / 사건만 / 선택 후 with p10~p90 bars and what moved).
6. A season is 6 months. Price, staff and menu choices persist into the next month (sim/season.py; every path is
   precomputed in public/runs/season). The season ends with 시즌 결산: cumulative operating profit vs
   평소대로였다면, best and worst month, each month's receipt, and 새 시즌 시작.
- Cards whose effect rests on a confidence-L mechanism show 인터뷰로 확인 필요; tap or hover for the reason.
- Switches (decision page) live in industry/pork_bbq.yaml `game:`; rerun the precompute after changing one.
- 가게 능력치: the driver tree with simulated values (엑셀 추정 = workbook P&L), sources and confidence; selecting
  a node highlights everything it affects.
- 사장님에게 묻기: POST `${VITE_API_BASE:-http://localhost:8000}/chat` with
  `{persona: "owner", message, context: {shock, action}}`. Without the API, a clearly labelled offline answer
  is built from the precomputed headline.

Runs fully offline: everything comes from `public/runs` and `public/data`.
URL parameters for headless capture: `#/?phase=idle&t=20:30&paused=1&cam=fps`; `window.__game` exposes
`phase`, `setTime`, `finish`.

## Checks (headless only, never a visible window)

- `node scripts/playthrough.mjs <outDir>` plays a full 6-month season (SH03 reprice, SH09 absorb, SH07 cut_staff,
  SH10 discount, SH11 change_mix, SH04 reprice_alcohol), asserts every on-screen number against `public/runs`,
  checks the badges and the season summary, and saves screenshots.
- `node scripts/shoot.mjs <outDir>` screenshots the older lab views.

## Lab (`#/lab`)

The earlier replay and the three dashboard directions (A report, B console, C map) stay for reference at
`#/lab/replay`, `#/lab/a`, `#/lab/b`, `#/lab/c`. All numbers are illustrative seed guesstimates until reviewed
in `research/guesstimate.xlsx`.
