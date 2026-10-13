"""Season report (docs/GAME-V2-SPEC.md §14): deterministic, finds a planted bad lever first, traceable to the table."""
import json

import pytest

from sim import report as R
from sim import season as S

B = S.base_plan()


def _season(plans, seed=5, night=True):
    st, months = S.new_season(seed), []
    for p in plans:
        r = S.play_month(st, p, None, band_runs=5, night=night)
        months.append(r)
        st = r["state_after"]
        if st["closed"]:
            break
    return {"seed": seed, "mode": "free", "months": months, "state": st}


@pytest.fixture(scope="module")
def planted():
    return _season([B, {**B, "soju_price": 9000}, B, B, B, B])


def test_planted_bad_lever_is_the_top_improvement(planted):
    top = R.improvements(planted)[0]
    assert (top["month_index"], top["lever"], top["from"]) == (1, "soju_price", 9000)
    assert top["store_value_delta"] > 0 and top["to"] < 9000
    other = _season([B, B, {**B, "meat_grade": "imported"}, B, B, B], seed=9, night=False)
    top = R.improvements(other)[0]
    assert (top["month_index"], top["lever"], top["from"]) == (2, "meat_grade", "imported")


def test_counterfactuals_are_deterministic(planted):
    a = json.dumps(R.improvements(planted), sort_keys=True, default=str)
    R._MEMO.clear()
    b = json.dumps(R.improvements(planted), sort_keys=True, default=str)
    assert a == b


def test_every_number_traces_to_the_table(planted):
    table = R.season_table(planted)
    summary = R.season_summary(planted, review={"reviewed": 3, "total": 82})
    assert len(table) == summary["months_played"] == 6
    assert summary["total_op"] == pytest.approx(sum(r["op"] for r in table))
    assert summary["total_vs_shadow"] == pytest.approx(sum(r["net_vs_shadow"] for r in table))
    assert summary["ending_cash"] == table[-1]["cash_after"] and "검토 3/82" in summary["caveat_ko"]
    rows = {r["month_index"]: r for r in table}
    for x in R.improvements(planted):
        idx = x.get("month_indices") or [x["month_index"]]
        assert x["month_label"].split("~")[0] == rows[idx[0]]["month_label"]
        assert x["month_label"].split("~")[-1] == rows[idx[-1]]["month_label"]
        if x["kind"] == "lever":
            for i in idx:
                assert rows[i][f"lever_{x['lever']}"] == x["from"]
            plan = planted["months"][x["month_index"]]["plan"]
            assert {k for k in plan if plan[k] != x["alt_plan"][k]} == {x["lever"]}
        assert {"cash_delta", "store_value_delta", "cost", "tag", "basis", "takeaway_ko", "alt_plan"} <= set(x)
        assert "→" not in x["takeaway_ko"]
    for g in R.good_decisions(planted):
        assert g["month_label"] == rows[g["month_index"]]["month_label"] and g["cash_delta"] > 0
    for lm in R.luck_months(planted):
        row = rows[lm["month_index"]]
        assert (lm["op"], lm["p10_op"], lm["p90_op"]) == (row["op"], row["p10_op"], row["p90_op"])
        assert abs(lm["luck_won"]) > abs(lm["plan_effect_won"])


def test_ranked_by_store_value_and_cash_only_kept_apart(planted):
    """Lead 2026-10-01: rank by 가게 가치 gained; an alternative that raises cash but lowers 가게 가치 is never an
    improvement, it goes to cash_only with both numbers."""
    imp = R.improvements(planted)
    assert imp and all(x["store_value_delta"] > 0 for x in imp)
    assert [x["store_value_per_month"] for x in imp] == sorted((x["store_value_per_month"] for x in imp), reverse=True)
    for x in R.cash_only(planted):
        assert x["cash_delta"] > 0 >= x["store_value_delta"] and "가게 가치" in x["warning_ko"]
    assert all({"month_index", "alt_plan"} <= set(x) for x in imp)   # web3d's 비교로 보기


def test_runs_merge_and_one_lever_fills_at_most_two_slots():
    """The same change in adjacent months is one item over the month range (re-estimated jointly); at most two of
    the top five come from one lever."""
    s = _season([B, {**B, "soju_price": 9000}, {**B, "soju_price": 9000}, {**B, "soju_price": 9000}, B, B], night=False)
    imp = R.improvements(s)
    soju = [x for x in imp if x["lever"] == "soju_price"]
    assert soju and soju[0]["month_indices"] == [1, 2, 3] and soju[0]["month_label"] == "11월~1월"
    assert set(soju[0]["alt_plans"]) == {1, 2, 3} and all(p["soju_price"] < 9000 for p in soju[0]["alt_plans"].values())
    from collections import Counter
    assert max(Counter(x["lever"] or x["decision_ko"] for x in imp).values()) <= 2


def test_des_rescoring_keeps_overstated_staff_levers_out_of_the_top():
    """Lead 2026-10-02: the analytic path overstated 교대당 알바 1명 (its cost comes through fatigue-driven quits and
    owner-alone months). The top analytic candidates are re-scored with paired DES paths (plan-driven events
    redrawn); a candidate the DES does not confirm (opposite sign or >2x apart) leaves the top 5 for uncertain()."""
    s = _season([B] * 6, seed=7)
    imp = R.improvements(s)
    flagged = R.uncertain(s)
    assert all(x["kind"] != "lever" or (x["agree"] and x["des"]["store_value_delta"] > 0) for x in imp)
    assert not any(x["lever"] == "staff_per_shift" and x["to"] < 2 for x in imp)
    assert any(x["lever"] == "staff_per_shift" for x in flagged)
    for x in flagged:
        a, d = x["analytic"]["store_value_delta"], x["des"]["store_value_delta"]
        assert d <= 0 or not 0.5 <= a / d <= 2.0


def test_a_lever_the_des_calls_small_cannot_reach_the_top(monkeypatch):
    """Forced check of the gate: if the DES says grilling and 알바 cuts gain almost nothing, they are not improvements
    however large the analytic estimate."""
    s = _season([B] * 6, seed=7)
    real = R._des_path

    def tiny(job):
        s0, plans, exo, k = job
        out = real(job)
        if any(p.get("staff_grilling") or p.get("staff_per_shift", 2) < 2 for p in plans):
            out = {**out, "store_value": out["store_value"] - 5e7}   # DES: these alternatives do not pay
        return out
    monkeypatch.setattr(R, "_des_path", tiny)
    monkeypatch.setattr(R, "_DES_CACHE", {})
    monkeypatch.setattr(R, "_MEMO", {})
    imp = R.improvements(s)
    assert not any(x["lever"] in ("staff_grilling", "staff_per_shift") for x in imp)
    assert {x["lever"] for x in R.uncertain(s)} >= {"staff_grilling"}


def test_money_rounds_before_the_sign_and_uses_the_ui_minus():
    """'가게 가치는 -0만원' came from formatting -3,000원 with a sign before rounding (N19)."""
    assert R._won(-3_000) == "0만원" and R._won(4_999) == "0만원"
    assert R._won(-1_430_000) == "\u2212143만원" and R._won(520_000) == "+52만원"
    t = R._takeaway("11월", "소주 가격을 바꿨다면", {"cash_delta": 3_200_000, "store_value_delta": -3_000, "regular_share_delta": -0.031})
    assert t == "11월에 소주 가격을 바꿨다면, 시즌 끝 현금 +320만원, 가게 가치 0만원, 단골 \u22123%p"
    assert "-" not in t and "+0" not in t
