"""Refresh web/public/data from the repo's own outputs (run from the repo root):

  .venv/bin/python web/scripts/sync_data.py            # reruns the simulation (all shocks, 200 runs)
  .venv/bin/python web/scripts/sync_data.py --no-sim   # only re-export ontology / hero / district

Reads (never writes): research/*.yaml, ontology/*.csv, data/processed/*, sim/.
Writes: web/public/data/{hero,ontology,district,shocks,summary}.json, kpis/<SH>.json, events/<SH>.json.
All numbers are illustrative seed guesstimates until reviewed in research/guesstimate.xlsx.
"""
from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "web" / "public" / "data"
REPLAY_SHOCKS = ["SH03", "SH09"]  # events.json copied for the 3D replay toggle


def dump(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def hero() -> dict:
    h = yaml.safe_load(open(ROOT / "research" / "hero_base.yaml", encoding="utf-8"))
    b = {k: v["base"] for k, v in h.items() if not k.startswith("_")}
    sys.path.insert(0, str(ROOT))
    from sim.params import SIM_ASSUMPTIONS  # noqa: E402
    return {
        "tables": int(b["sto_tables"]), "seats_per_table": int(b["sto_seats_per_table"]),
        "terrace_tables": int(round(b["sto_terrace"] / b["sto_seats_per_table"])),
        "servers": int(b["sto_parttimers"]) + SIM_ASSUMPTIONS["owner_on_floor"],
        "open_hours": b["drv_open_hours"], "open_clock": "17:00",
        "meat_price": b["prd_meat_price"], "soju_price": b["prd_alcohol_price"],
        "area_pyeong": b["sto_area_pyeong"], "pnl": h["_pnl_base"],
        "owner_wage": b["cst_owner_imputed_wage"],
        # HeroStore rows a named member has reviewed (reviewed_by), out of all HeroStore rows
        "review": {"reviewed": sum(1 for k, v in h.items() if not k.startswith("_") and v.get("method") != "derived"
                                   and v.get("reviewed_by")),
                   "total": sum(1 for k, v in h.items() if not k.startswith("_") and v.get("method") != "derived")},
    }


def ontology() -> dict:
    sys.path.insert(0, str(ROOT))
    from sim.tour import formula_ko  # noqa: E402  (one parser for the tour and the ontology export)
    h = yaml.safe_load(open(ROOT / "research" / "hero_base.yaml", encoding="utf-8"))
    crit = list(csv.DictReader(open(ROOT / "ontology" / "criteria.csv", encoding="utf-8")))
    edges = list(csv.DictReader(open(ROOT / "ontology" / "edges.csv", encoding="utf-8")))
    nodes = []
    for c in crit:
        v = h.get(c["criterion_id"], {})
        nodes.append({"id": c["criterion_id"], "ko": c["name_ko"], "en": c["name_en"], "category": c["category"],
                      "parent": c["driver_node"] or None, "unit": c["unit"], "method": c["method"],
                      "in_sim": c["in_sim"] == "Y", "source": c["source_id"] or None,
                      "base": v.get("base"), "low": v.get("low"), "high": v.get("high"),
                      "confidence": v.get("confidence"),
                      # a named member signed the row off (reviewed_by): the web drops the PRELIMINARY badge for it
                      "reviewed": bool(v.get("reviewed_by")), "formula": formula_ko(c["notes"])})
    return {"nodes": nodes, "edges": [{"from": e["from_id"], "to": e["to_id"], "sign": e["sign"],
                                       "why": e["mechanism_ko"], "confidence": e["confidence"],
                                       "source": e["source_id"] or None} for e in edges]}


def district() -> dict:
    g = json.load(open(ROOT / "data" / "processed" / "trdar_boundaries.geojson", encoding="utf-8"))
    stores = list(csv.DictReader(open(ROOT / "data" / "processed" / "stores_sbiz.csv", encoding="utf-8")))
    prof = json.load(open(ROOT / "data" / "processed" / "district_profile.json", encoding="utf-8"))
    t = prof["trdar"]["3120012"]
    q = t["quarters"][sorted(t["quarters"])[-1]]
    return {
        "areas": [{"code": f["properties"]["trdar_code"], "name": f["properties"]["trdar_name"],
                   "geometry": f["geometry"]} for f in g["features"]],
        # Public attributes only: no store name carries any guessed number.
        "stores": [{"lon": float(s["lon"]), "lat": float(s["lat"]), "code": s["class_code"], "role": s["role"],
                    "trdar": s["trdar_code"], "franchise": s["franchise_flag"] == "1"} for s in stores],
        "profile": {"quarter": sorted(t["quarters"])[-1], "hansik_stores": q["stores_total"],
                    "pork_stores": t["sbiz_stores"]["I20107"]["stores"], "evening_share": q["evening_share_17_24"],
                    "age20_share": q["age_share"]["age20"], "timeband_share": q["timeband_share"],
                    "dow_share": q["dow_share"], "sales_per_store_month": q["sales_per_store_month_krw"]},
    }


def shocks() -> dict:
    s = yaml.safe_load(open(ROOT / "research" / "shocks.yaml", encoding="utf-8"))
    return {k: v for k, v in s.items() if not k.startswith("_")}


def chat_presets() -> list[dict]:
    """The owner-chat questions exactly as agents.prewarm plans them (byte-identical text, so cache hits work)."""
    sys.path.insert(0, str(ROOT))
    from agents.prewarm import QUESTIONS  # noqa: E402  (plain data; importing makes no LLM call)
    return [{"q": q, "shocks": shocks, "after_choice": q.startswith("이번 달 결정")} for q, shocks in QUESTIONS]


def run_sim() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run([sys.executable, "-m", "sim.run", "--shock", "all", "--runs", "200", "--out", tmp],
                       cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
        shutil.copy(Path(tmp) / "summary.json", OUT / "summary.json")
        for d in sorted(Path(tmp).iterdir()):
            if d.is_dir():
                k = json.load(open(d / "kpis.json", encoding="utf-8"))
                k["shock"].pop("description", None)
                dump(OUT / "kpis" / f"{d.name}.json", k)
                if d.name in REPLAY_SHOCKS:
                    shutil.copy(d / "events.json", OUT / "events" / f"{d.name}.json")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-sim", action="store_true")
    args = ap.parse_args()
    (OUT / "events").mkdir(parents=True, exist_ok=True)
    dump(OUT / "hero.json", hero())
    dump(OUT / "ontology.json", ontology())
    dump(OUT / "district.json", district())
    dump(OUT / "shocks.json", shocks())
    dump(OUT / "chat_presets.json", chat_presets())
    if not args.no_sim:
        run_sim()
    print("wrote", sorted(str(p.relative_to(OUT)) for p in OUT.rglob("*.json")))


if __name__ == "__main__":
    main()
