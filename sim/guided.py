"""Precompute the guided story (시연 모드) into web/public/guided/ so the demo runs offline.

  python -m sim.guided [--out web/public/guided]

Reads research/guided.yaml. For each month every option is played from the same state (the story so far) with
the scripted events; the story then continues along `story_choice`. Every option also carries `followup`: the
remaining story months played from that option's state (same events, the story's later choices on top of that
option's plan), so a choice that wins this month but costs later shows it, plus a one-line `next_line`. Writes index.json (story, narration,
options, file names, cash path) and one MonthResult per option (<n>_<month>_<option>.json). Deterministic.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import yaml

from agents.ko import eun, ga, man_won
from agents.persona import render_month
from sim import season as S
from sim.engine import simulate_month
from sim.params import ROOT


def _shadow_band(state: dict, events: list[str]) -> np.ndarray:
    """The base plan's own DES band for this state and events (60 runs, sorted): where a typical 평소 month falls."""
    su = S._setup(state, S.base_plan(), events, quit_now="staff_quit" in events)
    return np.sort([S._pnl(simulate_month(su["params"], su["profile"], 4000 + j, a=su["a"]), su, None, 0)["op"]
                    for j in range(60)])


def _shadow_pct(band: np.ndarray, shadow_op: float) -> float:
    """Where the 정산 shadow (base plan, this stream, before the night's situations) sits in that band."""
    return float(np.searchsorted(band, shadow_op) / len(band))


def _representative(state: dict, plans: list[dict], events: list[str], band: int | None = None) -> tuple[list[dict], dict]:
    """Play every option on one shared customer stream, choosing (from up to 48) the first stream on which each
    option's draw AND the base plan's draw (the 정산's 평소대로였다면 shadow) sit near their own medians
    (percentile within 0.3-0.7), so neither a choice nor the baseline rests on luck. Streams are scored without the
    night (fast); the chosen one is replayed with its night and default in-night decisions. Returns the results and
    the state used (its stream), with the season seed restored in state_after."""
    best_k, best_score = 0, 9.0
    shadow_band = _shadow_band(state, events)
    for k in range(48):   # most months settle in the first few streams
        st = {**state, "seed": state["seed"] * 100 + k}
        rs = [S.play_month(st, p, events, band_runs=band, night=False) for p in plans]
        score = max([abs(r["draw"]["op_percentile"] - 0.5) for r in rs]
                    + [abs(_shadow_pct(shadow_band, rs[0]["shadow"]["kpis"]["op"]) - 0.5)])
        if score < best_score:
            best_k, best_score = k, score
        if score <= 0.2:
            break
    st = {**state, "seed": state["seed"] * 100 + best_k}
    best = [S.play_month(st, p, events, band_runs=band) for p in plans]
    for r in best:
        r["state_after"]["seed"] = state["seed"]
        r["representative"] = True
    return best, st


def _night_decision(n: int, mo: dict, story_file: str, r: dict, st: dict, plan: dict, out: Path,
                    used: set) -> dict | None:
    """§12.5: the story month's first in-night decision with every branch played on the same stream, so presenter
    mode can let the room decide offline. The default branch is the story's own file; the story continues on it."""
    if not r.get("decision_points"):
        return None
    fresh = [d for d in r["decision_points"] if d["kind"] not in used]   # a different situation each month if possible
    dp = (fresh or r["decision_points"])[0]
    used.add(dp["kind"])
    branches = []
    for o in dp["options"]:
        if o["id"] == dp["default"]:
            rb, fname = r, story_file
        else:
            rb = render_month(S.play_month(st, plan, mo["events"], night_choices={dp["id"]: o["id"]}), None)
            rb["state_after"]["seed"] = r["state_after"]["seed"]
            rb["representative"] = True
            fname = story_file.replace(".json", f"__{dp['kind']}_{o['id']}.json")
            (out / fname).write_text(json.dumps(rb, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        nd = next(x for x in rb["night_decisions"] if x["id"] == dp["id"])
        k = rb["draw"]["kpis"]
        vs = nd["vs_default_op"]
        line = (f"{rb['calendar']['label']} 영업이익 {man_won(k['op'])}"
                + ("" if o["id"] == dp["default"] else f" (기본 대응보다 {man_won(abs(vs))} {'많음' if vs >= 0 else '적음'})")
                + "".join(f", {lab} {x:+.2f}" for key, lab in (("fatigue", "직원 피로"), ("awareness", "인지도"), ("rating", "평점"))
                          if (x := nd["state_delta"].get(key))))
        branches.append({"option_id": o["id"], "label_ko": o["label_ko"], "file": fname, "op": k["op"],
                         "cash_after": rb["state_after"]["cash"], "next_line": line})
    return {"decision_point": dp, "story_option": dp["default"], "branches": branches}


def _follow(state: dict, plan: dict, script: dict, n: int) -> list[dict]:
    """Play story months n+1.. from this state: scripted events, the story's later choices applied to this plan."""
    rows = []
    for mo in script["months"][n:]:
        # same stream choice as the story makes for this month (all options), then keep the story's choice
        opts = mo["decision"]["options"]
        i = next(j for j, o in enumerate(opts) if o["id"] == mo["story_choice"])
        r = _representative(state, [{**plan, **o["changes"]} for o in opts], mo["events"])[0][i]
        plan = {**plan, **opts[i]["changes"]}
        state = r["state_after"]
        k = r["draw"]["kpis"]
        rows.append({"month": mo["month"], "label": r["calendar"]["label"], "op": k["op"], "covers": k["covers"],
                     "cash": state["cash"], "rating": state["rating"], "regular_share": state["regular_share"],
                     "scripted": True})
        if state["closed"]:
            break
    # after the story: hold the plan to the season end, no scripted events (delayed costs show in cash here)
    while not state["closed"] and state["month_index"] < len(S.months()):
        r = _representative(state, [plan], [])[0][0]
        state, k = r["state_after"], r["draw"]["kpis"]
        rows.append({"month": r["month"], "label": r["calendar"]["label"], "op": k["op"], "covers": k["covers"],
                     "cash": state["cash"], "rating": state["rating"], "regular_share": state["regular_share"],
                     "scripted": False})
    if rows:
        rows[-1]["store_value"] = S.season_value(state)["store_value"]   # 가게 가치 at the end of this path
        rows[-1]["closed"] = bool(state["closed"])
    return rows


def _next_line(opt: dict, story: dict, reveal_end: bool = True) -> str | None:
    """다음 달에 나타나는 결과: this branch's next months against the story's own path (numbers only from the runs)."""
    f, g = opt["followup"], story["followup"]
    if not f:
        return None
    a = f[0]
    if opt["id"] == story["id"]:
        return (f"{a['label']}: 손님 {a['covers']:,.0f}명, 평점 {a['rating']:.2f}, 단골 {a['regular_share']:.0%}."
                + (f" {_ends(f)}" if reveal_end else ""))
    b = g[0]
    return (f"{a['label']}: 손님 {a['covers']:,.0f}명 (이야기 {b['covers']:,.0f}명), 평점 {a['rating']:.2f} ({b['rating']:.2f}), "
            f"단골 {a['regular_share']:.0%} ({b['regular_share']:.0%}). {_ends(f, g)}")


def _ends(f: list[dict], g: list[dict] | None = None) -> str:
    """Cash at the last story month and at the season end (story path in brackets)."""
    def at(rows, scripted):
        sel = [x for x in rows if x["scripted"] == scripted]
        return sel[-1] if sel else None
    parts = []
    for scripted, tail in ((True, ""), (False, " (이후 계획 유지, 사건 없음)")):
        x = at(f, scripted)
        if x is None:
            continue
        y = at(g, scripted) if g else None
        parts.append(f"{x['label']} 말 현금 {man_won(x['cash'])}" + (f" (이야기 {man_won(y['cash'])})" if y else "") + tail)
    return ", ".join(parts)


def _summary(story: list[dict]) -> dict:
    """Final card: every branch's March cash and 가게 가치 side by side, and takeaways that are true for these
    numbers (generated from them, never written by hand)."""
    rows, lines = [], []
    for st in story:
        opts = [o for o in st["decision"]["options"] if o["followup"]]
        if len(opts) < 2:
            continue
        story_opt = next(o for o in opts if o["id"] == st["story_choice"])
        for o in opts:
            end = o["followup"][-1]
            rows.append({"month": st["month"], "label": st["label"], "option": o["id"], "option_label": o["label"],
                         "is_story": o["id"] == st["story_choice"], "cash": end["cash"], "store_value": end["store_value"],
                         "regular_share": end["regular_share"], "rating": end["rating"], "end_label": end["label"],
                         "closed": bool(end.get("closed"))})
        cash_best = max(opts, key=lambda o: o["followup"][-1]["cash"])
        value_best = max(opts, key=lambda o: o["followup"][-1]["store_value"])
        if cash_best is value_best:
            lines.append(f"{st['label']}: {ga(cash_best['label'])} 3월 현금과 가게 가치 모두 가장 높습니다")
        else:
            lines.append(f"{st['label']}: {eun(cash_best['label'])} 현금을, {eun(value_best['label'])} 단골과 가게 가치를 지킵니다")
        for o in opts:   # ahead in cash at the story's end, behind by March
            mid = [x for x in o["followup"] if x["scripted"]]
            smid = [x for x in story_opt["followup"] if x["scripted"]]
            if o is not story_opt and mid and smid and mid[-1]["cash"] > smid[-1]["cash"] \
                    and o["followup"][-1]["cash"] < story_opt["followup"][-1]["cash"]:
                end = o["followup"][-1]
                tail = (f"{end['label']}에 문을 닫습니다 (폐업)" if end.get("closed") else
                        f"단골이 {end['regular_share']:.0%}로 줄어 가게 가치가 {man_won(end['store_value'])}에 그칩니다")
                lines.append(f"{eun(o['label'])} {mid[-1]['label']}까지 현금이 앞서지만 3월에는 뒤처지고, {tail}")
    story_end = rows and next(r for r in rows if r["is_story"])
    best_value = rows and max(rows, key=lambda r: r["store_value"])
    best_cash = rows and max(rows, key=lambda r: r["cash"])
    if rows:
        cost = (f"이야기가 고른 길: 3월 말 현금 {man_won(story_end['cash'])}"
                + (" (모든 길 중 가장 많음)" if best_cash["cash"] <= story_end["cash"] else
                   f" (가장 많은 길은 {best_cash['label']} {best_cash['option_label']}, {man_won(best_cash['cash'])})")
                + f", 가게 가치 {man_won(story_end['store_value'])}"
                + (" (가장 높음)" if best_value["store_value"] <= story_end["store_value"] else
                   f". 가게 가치는 {best_value['label']}에 '{best_value['option_label']}' 쪽이 "
                   f"{man_won(best_value['store_value'] - story_end['store_value'])} 더 높습니다"))
        lines.insert(0, cost)
    return {"title": "3월까지 갈래별 결과", "basis": "각 선택 이후 이야기의 나머지 선택을 따르고, 1월 이후는 계획 유지·사건 없음. "
            "가게 가치 (6개월 전망) = 3월 말 현금 + 그 시점의 평판(평점·단골·인지도)으로 평소 계획을 6개월 더 운영할 때 예상 영업이익 (가정)",
            "branches": rows, "takeaways": lines}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "web" / "public" / "guided"))
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    script = yaml.safe_load((ROOT / "research" / "guided.yaml").read_text(encoding="utf-8"))
    state = S.new_season(script["seed"], "guided")
    plan = S.base_plan()
    story, used_kinds = [], set()
    for n, mo in enumerate(script["months"], start=1):
        assert S.current_month(state) == mo["month"], f"story month {mo['month']} != calendar {S.current_month(state)}"
        options, chosen = [], None
        plans = [{**plan, **opt["changes"]} for opt in mo["decision"]["options"]]
        runs, st_used = _representative(state, plans, mo["events"])
        for opt, p, r in zip(mo["decision"]["options"], plans, runs):
            r = render_month(r, None)  # template text: guided mode has no API
            fname = f"{n}_{mo['month']:02d}_{opt['id']}.json"
            (out / fname).write_text(json.dumps(r, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
            k = r["draw"]["kpis"]
            options.append({"id": opt["id"], "label": opt["label"], "changes": opt["changes"], "file": fname,
                            "op": k["op"], "revenue": k["revenue"], "cash_after": r["state_after"]["cash"],
                            "rating_after": r["state_after"]["rating"], "p10_op": r["draw"]["p10"]["op"],
                            "p90_op": r["draw"]["p90"]["op"], "regular_share_after": r["state_after"]["regular_share"],
                            "followup": _follow(r["state_after"], p, script, n)})
            if opt["id"] == mo["story_choice"]:
                chosen = (r, p, fname)
        story_opt = next(o for o in options if o["id"] == mo["story_choice"])
        for o in options:
            o["next_line"] = _next_line(o, story_opt, reveal_end=len(options) > 1)  # a month without choices spoils nothing
        story.append({"n": n, "month": mo["month"], "label": chosen[0]["calendar"]["label"], "title": mo["title"],
                      "events": mo["events"], "narration": mo["narration"], "decision": {"prompt": mo["decision"]["prompt"],
                      "options": options}, "story_choice": mo["story_choice"],
                      "night_decision": _night_decision(n, mo, chosen[2], chosen[0], st_used, chosen[1], out, used_kinds)})
        state, plan = chosen[0]["state_after"], chosen[1]
        print(f"{n} {mo['title']}: " + ", ".join(f"{o['label']} OP {o['op'] / 1e4:.0f}만" for o in options))
    index = {"engine": "sim.season v2", "mode": "guided", "seed": script["seed"], "story": story,
             "summary": _summary(story),
             "start": {k: S.new_season(script["seed"])[k] for k in ("cash", "rating", "review_count", "awareness",
                                                                       "regular_share", "fatigue")},
             "baseline_op": round(S._baseline()["op"]), "illustrative": True, "representative": True,
             "representative_note": "시연 모드는 같은 손님 흐름에서 각 선택이 중앙값 근처에 오는 달을 보여 줍니다 (자유 플레이는 매달 무작위)",
             "note": "모든 숫자는 검토 전 예시값입니다. 가정 태그가 붙은 메커니즘은 sim/season.py와 research/*.yaml에 근거가 있습니다."}
    (out / "index.json").write_text(json.dumps(index, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
