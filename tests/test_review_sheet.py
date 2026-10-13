"""research/sync_review_sheet.py against a fake gws (no network): validation, dry run, patch shape, refresh scope."""
import json
import sys
from pathlib import Path

import pytest
import yaml

from research import build_workbook as BW
from research import sync_review_sheet as R

FAKE = r'''#!/usr/bin/env python3
import json, os, sys
args = sys.argv[1:]
with open(os.environ["FAKE_GWS_LOG"], "a", encoding="utf-8") as fh:
    fh.write(json.dumps(args, ensure_ascii=False) + "\n")
if args[:4] == ["sheets", "spreadsheets", "values", "batchGet"]:
    print(open(os.environ["FAKE_GWS_VALUES"], encoding="utf-8").read())
else:
    print("{}")
'''


@pytest.fixture
def fake_gws(tmp_path, monkeypatch):
    exe = tmp_path / "gws"
    exe.write_text(FAKE.replace("#!/usr/bin/env python3", f"#!{sys.executable}"), encoding="utf-8")
    exe.chmod(0o755)
    log, values = tmp_path / "gws.log", tmp_path / "values.json"
    monkeypatch.setenv("GWS_BIN", str(exe))
    monkeypatch.setenv("FAKE_GWS_LOG", str(log))
    monkeypatch.setenv("FAKE_GWS_VALUES", str(values))
    sheet_json = tmp_path / "review_sheet.json"
    sheet_json.write_text(json.dumps({"spreadsheet_id": "SHEET1"}), encoding="utf-8")
    monkeypatch.setattr(R, "SHEET_JSON", sheet_json)
    monkeypatch.setattr(R, "PATCH", tmp_path / "accepted_patch.yaml")
    src = tmp_path / "sources.csv"
    src.write_text(R.SOURCES.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(R, "SOURCES", src)

    def tabs(rows_by_member: dict):
        """rows_by_member: member -> [dict of header -> value]; the 현재 columns come from the real workbook."""
        items, cur = R.member_items(), R.current_values()
        ranges = []
        for m in R.MEMBERS:
            base = {r[0]: r for r in R.member_rows(m, items, cur)}
            vals = [R.HEAD]
            for rid, row in base.items():
                inp = next((x for x in rows_by_member.get(m, []) if x["기준ID"] == rid), {})
                vals.append(list(row) + [inp.get(h, "") for h in R.HEAD[8:]])
            ranges.append({"range": f"'{m}'!A1:P500", "values": vals})
        values.write_text(json.dumps({"valueRanges": ranges}, ensure_ascii=False), encoding="utf-8")

    def calls():
        return [json.loads(x) for x in log.read_text(encoding="utf-8").splitlines()] if log.exists() else []
    return tabs, calls


def test_member_tabs_hold_their_tasks_rows():
    items = R.member_items()
    assert set(items) == set(R.MEMBERS)
    assert "cst_meat_cost_per_portion" in [i for i, _ in items["김정연"]]
    assert "sim_params:svc_order_min" in [i for i, _ in items["박재현"]] and "BM45" in [i for i, _ in items["박재현"]]
    assert "season_params:demand.rating_per_star" in [i for i, _ in items["이지우"]]
    assert "drv_covers" not in [i for i, _ in items["오하영"]]          # derived, no HeroStore row
    cur = R.current_values()
    for m in R.MEMBERS:
        assert all(rid in cur for rid, _ in items[m]), m


def _row(rid, **kw):
    return {"기준ID": rid, **kw}


def test_valid_rows_become_a_patch_build_workbook_accepts(fake_gws, capsys):
    tabs, calls = fake_gws
    tabs({"김정연": [_row("cst_meat_cost_per_portion", **{"확인 결과": "수정", "수정 낮음": 3800, "수정 기본": "4,600",
                                                         "수정 높음": 5300, "근거 링크": "S68", "메모": "현장 3곳 평균", "검토자": "김정연"}),
                     _row("prd_meat_price", **{"확인 결과": "맞음", "검토자": "김정연"})],
          "이지우": [_row("season_params:demand.rating_per_star", **{"확인 결과": "맞음", "검토자": "이지우"})]})
    res = R.collect(R.read_member_tabs("SHEET1"), R.current_values(), R._sources())
    assert not res["refused"], res["refused"]
    assert res["hero"]["cst_meat_cost_per_portion"]["base"] == 4600
    assert res["hero"]["prd_meat_price"] == {"filled_by": R.VIA, "reviewed_by": "김정연"}
    assert "season_params:demand.rating_per_star" in res["sim"]
    doc = R.merged_patch(res, {})
    p = R.PATCH
    p.write_text(yaml.safe_dump(doc, allow_unicode=True), encoding="utf-8")
    hero, _, review, changelog, refused, ignored = BW.apply_patch(p, BW.read_csv("sources.csv"))
    assert not refused and ignored == ["sim_assumptions"]
    assert {c["criterion_id"] for c in changelog} == {"cst_meat_cost_per_portion"}
    assert review["prd_meat_price"][1] == "김정연" and review["cst_meat_cost_per_portion"][0] == R.VIA


@pytest.mark.parametrize("inp,reason", [
    ({"확인 결과": "수정", "수정 낮음": 1, "수정 기본": "많음", "수정 높음": 3, "근거 링크": "S68", "검토자": "김정연"}, "숫자가 아님"),
    ({"확인 결과": "수정", "수정 낮음": 6000, "수정 기본": 4500, "수정 높음": 7000, "근거 링크": "S68", "검토자": "김정연"}, "낮음 <= 기본"),
    ({"확인 결과": "수정", "수정 낮음": 4000, "수정 기본": 4500, "수정 높음": 5000, "검토자": "김정연"}, "근거 링크가 필요"),
    ({"확인 결과": "수정", "수정 낮음": 4000, "수정 기본": 4500, "수정 높음": 5000, "근거 링크": "S999", "검토자": "김정연"}, "모르는 출처"),
    ({"확인 결과": "수정", "수정 기본": 4500, "근거 링크": "S68", "검토자": "김정연"}, "모두 숫자로"),
    ({"확인 결과": "맞음"}, "검토자가 비어"),
    ({"확인 결과": "좋아요", "검토자": "김정연"}, "맞음 또는 수정"),
])
def test_invalid_rows_are_refused(fake_gws, inp, reason):
    tabs, _ = fake_gws
    tabs({"김정연": [_row("cst_meat_cost_per_portion", **inp)]})
    res = R.collect(R.read_member_tabs("SHEET1"), R.current_values(), R._sources())
    assert not res["hero"] and len(res["refused"]) == 1 and reason in res["refused"][0][3], res["refused"]


def test_two_tabs_that_disagree_apply_neither(fake_gws):
    tabs, _ = fake_gws
    tabs({"오하영": [_row("sto_open_days", **{"확인 결과": "맞음", "검토자": "오하영"})],
          "박재현": [_row("sto_open_days", **{"확인 결과": "수정", "수정 낮음": 24, "수정 기본": 25, "수정 높음": 26,
                                              "근거 링크": "https://example.org/days", "검토자": "박재현"})]})
    res = R.collect(R.read_member_tabs("SHEET1"), R.current_values(), R._sources())
    assert "sto_open_days" not in res["hero"] and len(res["refused"]) == 2


def test_dry_run_writes_nothing(fake_gws, capsys):
    tabs, calls = fake_gws
    tabs({"김정연": [_row("cst_meat_cost_per_portion", **{"확인 결과": "수정", "수정 낮음": 3800, "수정 기본": 4600,
                                                         "수정 높음": 5300, "근거 링크": "https://example.org/new",
                                                         "검토자": "김정연"})]})
    before = R.SOURCES.read_text(encoding="utf-8")
    R.main([])
    out = capsys.readouterr().out
    assert "dry run" in out and "new source" in out
    assert not R.PATCH.exists() and R.SOURCES.read_text(encoding="utf-8") == before
    assert [c[:4] for c in calls()] == [["sheets", "spreadsheets", "values", "batchGet"]]   # read only


def test_apply_merges_ai_rows_adds_sources_and_stamps_only_p(fake_gws, monkeypatch, capsys):
    tabs, calls = fake_gws
    tabs({"김정연": [_row("cst_meat_cost_per_portion", **{"확인 결과": "수정", "수정 낮음": 3800, "수정 기본": 4600,
                                                         "수정 높음": 5300, "근거 링크": "https://example.org/new",
                                                         "검토자": "김정연"})]})
    R.PATCH.write_text(yaml.safe_dump({"_meta": {}, "drv_rent": {"base": 1, "filled_by": "AI", "reviewed_by": "김건희"},
                                       "prd_meat_price": {"filled_by": R.VIA, "reviewed_by": "old"}}, allow_unicode=True),
                       encoding="utf-8")
    ran = []
    monkeypatch.setattr(R, "_reviewed_in_xlsx", lambda: set())
    monkeypatch.setattr(R, "_run_build", lambda cmd, **kw: (ran.append(cmd), type("P", (), {"returncode": 0, "stdout": "ok", "stderr": ""})())[1])
    R.main(["--apply", "--stamp"])
    doc = yaml.safe_load(R.PATCH.read_text(encoding="utf-8"))
    assert doc["drv_rent"]["filled_by"] == "AI"                    # AI-helper row kept
    assert "prd_meat_price" not in doc                             # an old sheet row the sheet no longer has: dropped
    new_id = doc["cst_meat_cost_per_portion"]["source_id"]
    assert new_id in R.SOURCES.read_text(encoding="utf-8") and "https://example.org/new" in R.SOURCES.read_text(encoding="utf-8")
    assert ran and "--apply-patch" in ran[0] and "--force" in ran[0]
    writes = [c for c in calls() if c[:4] == ["sheets", "spreadsheets", "values", "batchUpdate"]]
    assert len(writes) == 1
    body = json.loads(writes[0][writes[0].index("--json") + 1])
    assert body["data"] and all(d["range"].split("!")[1].startswith("P") for d in body["data"])


def test_apply_refuses_when_reviewed_rows_would_be_lost(fake_gws, monkeypatch):
    tabs, _ = fake_gws
    tabs({})
    monkeypatch.setattr(R, "_reviewed_in_xlsx", lambda: {"drv_rent"})
    with pytest.raises(SystemExit, match="drv_rent"):
        R.apply(R.collect(R.read_member_tabs("SHEET1"), R.current_values(), R._sources()), run=lambda *a, **k: None)
    assert not R.PATCH.exists()


def test_refresh_touches_only_the_current_columns(fake_gws):
    tabs, calls = fake_gws
    tabs({"김정연": [_row("prd_meat_price", **{"확인 결과": "맞음", "검토자": "김정연", "메모": "keep me"})]})
    n = R.refresh("SHEET1")
    writes = [c for c in calls() if c[:4] == ["sheets", "spreadsheets", "values", "batchUpdate"]]
    body = json.loads(writes[0][writes[0].index("--json") + 1])
    assert n == len(body["data"]) > 0
    for d in body["data"]:
        cols = d["range"].split("!")[1]
        assert cols.startswith("B") and ":H" in cols, d["range"]
        assert len(d["values"][0]) == 7 and "keep me" not in d["values"][0]


def test_refresh_appends_new_rows_below_the_last(fake_gws, monkeypatch):
    tabs, calls = fake_gws
    tabs({})
    real = R.member_items

    def plus_one():
        items = real()
        items["이지우"] = items["이지우"] + [("drv_rent", "임대료")]
        return items
    monkeypatch.setattr(R, "member_items", plus_one)
    R.refresh("SHEET1")
    body = json.loads([c for c in calls() if "batchUpdate" in c][0][-1])
    added = [d for d in body["data"] if d["range"].startswith("'이지우'!A")]
    assert len(added) == 1 and added[0]["values"][0][0] == "drv_rent"


def test_guide_has_no_sentence_periods_dashes_or_arrows():
    for (line,) in R.GUIDE:
        assert not line.endswith("."), line
        assert not any(ch in line for ch in "—–→←⇒"), line
