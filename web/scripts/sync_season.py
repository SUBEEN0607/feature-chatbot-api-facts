"""Copy the v2 season inputs the web shows offline into web/public/data/season.json:

- research/season_params.yaml, events.yaml, calendar.yaml (every 가정/source tag and its note, for the
  clickable 가정 tags and the lever cards)
- ontology/sources.csv (source id -> title, publisher, year, url)
- the district layer for guided mode (no API): survival curves (data/processed/survival_wide.json and
  district_profile.json) and the 혜화동/서울/전국 rent benchmarks BM42-44 (research/build_workbook.py rows)

Usage (repo root): .venv/bin/python web/scripts/sync_season.py
"""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "web" / "public" / "data" / "season.json"


def load_yaml(name: str) -> dict:
    return yaml.safe_load((ROOT / "research" / name).read_text(encoding="utf-8"))


def sources() -> dict:
    with (ROOT / "ontology" / "sources.csv").open(encoding="utf-8") as f:
        return {r["source_id"]: {"title": r["title"], "by": r["publisher_author"], "year": r["year"], "url": r["url"],
                                 "note": r["reliability_note"]} for r in csv.DictReader(f)}


def rent() -> dict:
    text = (ROOT / "research" / "build_workbook.py").read_text(encoding="utf-8")
    out = {}
    for bid, key in (("BM42", "hyehwa_per_m2"), ("BM43", "seoul_per_m2"), ("BM44", "national_per_m2")):
        m = re.search(rf'\("{bid}", "([^"]+)", None, (\d+), None, "([^"]+)", "[^"]*", "([^"]+)"', text)
        if m:
            out[key] = int(m.group(2))
            out[f"{key}_label"] = m.group(1)
            out.setdefault("source_ids", set()).update(m.group(4).split(";"))
    out["unit"] = "₩/㎡/월"
    out["source_ids"] = sorted(out.get("source_ids", []))
    return out


def survival() -> dict:
    wide = json.loads((ROOT / "data" / "processed" / "survival_wide.json").read_text(encoding="utf-8"))
    prof_path = ROOT / "data" / "processed" / "district_profile.json"
    narrow = json.loads(prof_path.read_text(encoding="utf-8")).get("survival", {}) if prof_path.exists() else {}
    return {"scope": wide.get("scope"), "areas": wide.get("areas"), "cohort": wide.get("cohort"),
            "wide_pork_name_only": wide.get("pork_name_only"), "wide_hansik_all": wide.get("hansik_all"),
            "logrank": wide.get("logrank"), "study_area_hansik": narrow.get("hansik_primary")}


def main() -> None:
    out = {"params": load_yaml("season_params.yaml"), "events": load_yaml("events.yaml"),
           "calendar": load_yaml("calendar.yaml"), "sources": sources(),
           "district": {"rent": rent(), "survival": survival()}}
    OUT.write_text(json.dumps(out, ensure_ascii=False, default=str))
    print("wrote", OUT.relative_to(ROOT), f"{OUT.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
