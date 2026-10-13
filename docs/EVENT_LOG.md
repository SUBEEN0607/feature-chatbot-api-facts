# Event log schema (3D replay input)

`python -m sim.run --shock <id> --out <dir>` writes `<dir>/events.json`: one simulated **Saturday** night
(the busiest open night), base and shocked, **same seed**, so the replay can toggle before/after on the
same night. `--shock none` writes `shocked: null`.

```json
{
  "schema": "docs/EVENT_LOG.md",
  "seed": 42,
  "base":    {"dow": "sat", "terrace_open": true, "tables_available": 12, "open_clock": "17:00", "events": [ ... ]},
  "shocked": {"dow": "sat", "terrace_open": false, "tables_available": 10, "open_clock": "17:00", "events": [ ... ]}
}
```

## Event object

Events are sorted by time. Several events can share one timestamp (e.g. `arrive` and `seat` when a table
is free).

| field | type | meaning |
|---|---|---|
| `t` | float | minutes since opening (17:00); can exceed the opening hours, because seated parties finish after close |
| `clock` | "HH:MM" | wall clock, wraps after midnight |
| `type` | string | one of the types below |
| `party` | int or null | party id, unique within the night; `null` for table events |
| other fields | | depend on `type` |

| type | extra fields | meaning |
|---|---|---|
| `arrive` | `size` (1–4), `segment` (`twenties` / `office` / `family`) | a party reaches the door; the segment is simulated (see docs/SIMULATION.md) |
| `queue` | `size`, `queue_len` (parties already waiting) | no free table; the party starts waiting |
| `balk` | `size`, `waited` (min) | patience ran out; the party walks away (a "walk-away") |
| `seat` | `size`, `table_id`, `waited` (min) | the party takes a table |
| `order` | `table_id`, `portions`, `bottles`, `meals`, optional `reorder: true` | first order (after a server is free) or a re-order mid-meal |
| `leave` | `table_id`, `bill` (₩), `segment` | the party pays and leaves; the table still needs clearing |
| `table_ready` | `table_id` | a server has cleared the table; it is free again |

## Table ids

- `T01`…`T10`: indoor 4-tops (`sto_tables`), filled first.
- `Y01`, `Y02`: 야장 (terrace) 4-tops (`sto_terrace` ÷ 4). They exist only when `terrace_open` is true; the
  rain shock (SH10) turns them off, so no `Y` id appears in a rain night.

## Replay notes

- A table is occupied from `seat` to `table_ready`, and the party is at the table from `seat` to `leave`.
- Walk-aways: draw the party at the door from `arrive` to `balk`.
- The log is deterministic for a given seed and parameters (checked by `test_same_seed_identical`).
