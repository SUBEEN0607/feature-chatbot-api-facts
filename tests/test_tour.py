"""Welcome tour data contract (engines/_shared/ui/TOUR-SPEC.md, generator sim/tour.py): the committed
web/public/data/tour.json is a fresh build, matches the schema, every number traces to the sim or the ontology,
every bucket set holds its answer, and the Korean text follows the UI rules."""
import csv
import json
import re

import pytest
import yaml

from sim import season as S
from sim import tour as T
from sim.params import ROOT

FILE = ROOT / "web" / "public" / "data" / "tour.json"


@pytest.fixture(scope="module")
def data():
    return json.loads(FILE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def sim():
    state = S.new_season()
    events = []
    pv = S.preview(state, S.base_plan(), events)
    calc, su = S._calibrated(state, S.base_plan(), events)
    return {"pv": pv, "calc": calc, "params": su["params"]}


def test_committed_file_is_a_fresh_build(data):
    assert FILE.read_text(encoding="utf-8") == T.dumps(T.build()), "tour.json is stale: run make tour (python -m sim.tour)"
    eng = T.ENGINES / "tour.json"
    if eng.exists():   # the engines copy, when this checkout sits next to engines/
        assert eng.read_text(encoding="utf-8") == FILE.read_text(encoding="utf-8"), "engines/_shared/ui/tour.json differs: run make tour"


def test_baseline_is_the_event_free_month(data, sim):
    """A drawn event (festival_week) would show a boosted month as 평소: the tour's month has no external events,
    its P&L and sensitivity are preview(default plan, events=[]), and it says so."""
    assert data["events"] == [] and sim["pv"]["events"] == []
    assert data["baseline_ko"] == "외부 사건이 없는 평소 달"
    with_festival = S.preview(S.new_season(), S.base_plan(), ["festival_week"])["expected"]
    assert data["pnl"]["revenue"] != with_festival["revenue"] and data["pnl"]["op"] != with_festival["op"]
    for seed in (7, 2026):   # the season seed does not move the event-free month
        assert S.preview(S.new_season(seed), S.base_plan(), [])["expected"]["op"] == data["pnl"]["op"]
    b = S.baseline_month()   # the game's one declared baseline: the tour is that month
    assert b["label_ko"] == data["baseline_ko"] and b["month"] == data["month"]
    assert all(b[k] == data["pnl"][k] for k in ("revenue", "op"))
    assert all(b[k] == data["pnl"]["lines"][k] for k in ("cogs", "labor", "rent", "mgmt", "fees"))


def test_schema(data):
    assert data["version"] == 1 and isinstance(data["month"], int) and isinstance(data["plan"], dict)
    assert set(data["pnl"]) >= {"revenue", "cost", "op", "op_margin", "lines"}
    assert set(data["pnl"]["lines"]) == {"cogs", "labor", "rent", "mgmt", "fees"}
    anchors = ["sign", "menu_board", "tables", "grill", "staff", "fridge", "room"]
    assert [s["anchor"] for s in data["stops"]] == anchors and [s["order"] for s in data["stops"]] == list(range(1, 8))
    keys = {"order", "anchor", "criterion_id", "title_ko", "side", "value", "unit", "display_ko", "share_of_revenue", "formula_ko",
            "params", "sensitivity", "question_ko", "buckets", "answer_bucket", "reveal_ko", "preliminary"}
    for s in data["stops"]:
        assert keys <= set(s), keys - set(s)
        assert s["side"] in ("revenue", "cost", "result") and isinstance(s["preliminary"], bool)
        for p in s["params"]:
            assert {"criterion_id", "name_ko", "value", "unit", "display_ko", "confidence", "source_ids", "is_lever", "tag_ko"} <= set(p)
            assert p["confidence"] in ("H", "M", "L", None) and isinstance(p["source_ids"], list)
        for e in s["sensitivity"]:
            assert {"lever", "step_ko", "up", "down"} <= set(e) and (e["up"] or e["down"])
            for d in (e["up"], e["down"]):
                assert d is None or set(d) == {"op", "covers"}
        assert len(s["buckets"]) == 4 and all({"label_ko", "min", "max"} <= set(b) for b in s["buckets"])


def test_every_stop_is_a_driver_tree_node(data):
    crit = {r["criterion_id"]: r for r in csv.DictReader(open(ROOT / "ontology" / "criteria.csv", encoding="utf-8"))}
    edges = list(csv.DictReader(open(ROOT / "ontology" / "edges.csv", encoding="utf-8")))
    for s in data["stops"]:
        cid = s["criterion_id"]
        assert cid in crit
        # a drv_ node, or (주류) a term of 객단가's own formula
        assert cid.startswith("drv_") or any(e["from_id"] == cid and e["to_id"].startswith("drv_") for e in edges)
        if s["formula_ko"] and cid.startswith("drv_"):
            assert s["formula_ko"] == T.formula_ko(crit[cid]["notes"])


def test_every_number_traces_to_the_sim(data, sim):
    ex, calc, used = sim["pv"]["expected"], sim["calc"], sim["params"]
    hero = yaml.safe_load(open(ROOT / "research" / "hero_base.yaml", encoding="utf-8"))
    pnl = data["pnl"]
    assert pnl["revenue"] == ex["revenue"] and pnl["op"] == ex["op"] and pnl["op_margin"] == ex["op_margin"]
    for k, v in pnl["lines"].items():
        assert v == ex[k]
    assert pnl["revenue"] - sum(pnl["lines"].values()) == pytest.approx(pnl["op"], abs=1)
    stat = {"drv_rent": "rent", "drv_ticket": "ticket", "drv_covers": "covers", "drv_food_cost": "cogs", "drv_labor_cost": "labor",
            "drv_operating_profit": "op"}
    sens = sim["pv"]["sensitivity"]
    for s in data["stops"]:
        if s["criterion_id"] in stat:
            assert s["value"] == ex[stat[s["criterion_id"]]], s["criterion_id"]
        else:
            assert s["value"] == calc["alcohol_share"] == s["share_of_revenue"]
        if s["unit"].startswith("₩/월") and s["criterion_id"] != "drv_revenue":
            assert s["share_of_revenue"] == pytest.approx(s["value"] / ex["revenue"])
        for p in s["params"]:
            assert p["value"] == used.get(p["criterion_id"], (hero.get(p["criterion_id"]) or {}).get("base")), p["criterion_id"]
        for e in s["sensitivity"]:
            for d in ("up", "down"):
                if e[d]:
                    assert e[d]["op"] == round(sens[e["lever"]][d]["op"]) and e[d]["covers"] == round(sens[e["lever"]][d]["covers"])
    # the formulas the sim actually computes reproduce the headline from the card's own parameters
    by = {s["criterion_id"]: {p["criterion_id"]: p["value"] for p in s["params"]} for s in data["stops"]}
    t = by["drv_ticket"]
    assert t["prd_portions_per_cover"] * t["prd_meat_price"] + t["prd_alcohol_per_cover"] * t["prd_alcohol_price"] \
        + t["prd_side_spend_per_cover"] == pytest.approx(ex["ticket"])
    lab = by["drv_labor_cost"]
    assert lab["sto_parttimers"] * lab["sto_parttime_shift_hours"] * used["sto_open_days"] * lab["sto_parttime_wage"] \
        * lab["cst_holiday_pay_factor"] + used["sto_employees"] * used["cst_employee_wage"] + lab["cst_owner_imputed_wage"] \
        == pytest.approx(ex["labor"])


def test_buckets_contain_the_answer(data):
    for s in data["stops"]:
        b = s["buckets"]
        assert b[0]["min"] is None and b[-1]["max"] is None
        assert all(b[i]["max"] == b[i + 1]["min"] for i in range(3))
        inside = [i for i, x in enumerate(b) if (x["min"] is None or s["value"] >= x["min"]) and (x["max"] is None or s["value"] < x["max"])]
        assert inside == [s["answer_bucket"]], (s["criterion_id"], inside)
        assert s["answer_bucket"] in (1, 2)


def _texts(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, str) and (k.endswith("_ko") or k in ("formula_ko",)):
                yield k, v
            else:
                yield from _texts(v)
    elif isinstance(obj, list):
        for x in obj:
            yield from _texts(x)


def test_money_and_korean_text_rules(data):
    texts = list(_texts(data))
    assert len(texts) > 50
    for k, t in texts:
        assert "-" not in t, f"ASCII minus in {k}: {t}"       # money and deltas use U+2212
        assert not re.search(r"[−-]0만", t), f"minus zero in {k}: {t}"
        assert not re.search(r"[—–→←⇒]", t), f"dash or arrow in {k}: {t}"
        assert not t.rstrip().endswith("."), f"sentence-final period in {k}: {t}"
    for s in data["stops"]:
        assert s["question_ko"].endswith(("?", "요"))
