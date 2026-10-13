"""Guesstimation helper: drafts go only to research/review/, and only reviewed + accepted rows reach the patch."""
import csv
import hashlib
import re

import pytest
import yaml
from fastapi.testclient import TestClient

from agents import guesstimate as G

from .conftest import REPO

PROTECTED = [REPO / "research" / n for n in ("guesstimate.xlsx", "hero_base.yaml", "shocks.yaml")]


def _sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None


@pytest.fixture
def review(tmp_path, monkeypatch, loaded, fresh_llm):
    d = tmp_path / "review"
    monkeypatch.setenv("REVIEW_DIR", str(d))
    return d


def _rows(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def test_cli_drafts_mock_and_never_touches_research_inputs(review):
    before = [_sha(p) for p in PROTECTED]
    G.main(["--criterion", "drv_rent", "--criterion", "prd_cut_style"])
    rows = _rows(review / "ai_drafts.csv")
    assert [r["criterion_id"] for r in rows] == ["drv_rent", "prd_cut_style"]
    assert list(rows[0]) == G.COLUMNS
    r = rows[0]
    assert r["backend"] == "mock" and r["draft_reasoning"].startswith("초안") and r["ai_confidence"] == "L"
    assert r["draft_base"] == r["current_base"] != ""          # mock keeps the current seed value
    cited = [x for x in r["current_source_id"].split(";") if x]
    assert not cited or cited[0] in r["draft_sources"].split(";")   # already-cited source is pinned first
    assert r["reviewed_by"] == r["accept"] == ""
    G.main(["--apply-reviewed"])
    assert [_sha(p) for p in PROTECTED] == before, "a research input file changed"


def test_all_low_confidence(review):
    G.main(["--all-low-confidence"])
    assert len(_rows(review / "ai_drafts.csv")) == len(G.low_confidence_ids()) > 30


@pytest.mark.parametrize("name", ["hero_base.yaml", "guesstimate.xlsx", "shocks.yaml"])
def test_guard_refuses_research_inputs(review, name):
    with pytest.raises(PermissionError):
        G._guard(REPO / "research" / name, ".yaml" if name.endswith("yaml") else ".xlsx")
    with pytest.raises(PermissionError):
        G._guard(review / name, ".yaml")          # same name inside the review dir is refused too


def test_guard_refuses_outside_review_dir(review, tmp_path):
    with pytest.raises(PermissionError):
        G._guard(tmp_path / "elsewhere.csv", ".csv")
    with pytest.raises(PermissionError):
        G._guard(review / "ai_drafts.txt", ".csv")


def _write(review, rows):
    review.mkdir(parents=True, exist_ok=True)
    with open(review / "ai_drafts.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=G.COLUMNS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in G.COLUMNS})


def _row(cid, reviewer, accept):
    return {"criterion_id": cid, "draft_low": "1800000", "draft_base": "2300000", "draft_high": "3200000",
            "draft_reasoning": "초안", "draft_sources": "S31", "ai_confidence": "L",
            "reviewed_by": reviewer, "accept": accept}


def test_unreviewed_rows_never_reach_patch(review):
    _write(review, [_row("ok", "김민수", "Y"), _row("rejected", "김민수", "N"), _row("no_reviewer", "", "Y"),
                    _row("blank", "", ""), _row("space_reviewer", "   ", "Y"), _row("lower_y", "이지은", "y"),
                    _row("maybe", "이지은", "maybe")])
    path, n = G.apply_reviewed()
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    rows = {k for k in doc if not k.startswith("_")}
    assert rows == {"ok", "lower_y"} and n == 2 and doc["_meta"]["rows"] == 2
    assert doc["ok"]["base"] == 2300000 and doc["ok"]["reviewed_by"] == "김민수" and doc["ok"]["filled_by"] == "AI"


def test_patch_fields_match_workbook_herostore_columns(review):
    src = (REPO / "research" / "build_workbook.py").read_text(encoding="utf-8")
    hcols = re.search(r"hcols = \[(.*?)\]", src, re.S).group(1)
    cols = set(re.findall(r'"([a-z_]+)"', hcols))
    _write(review, [_row("ok", "김민수", "Y")])
    path, _ = G.apply_reviewed()
    fields = set(yaml.safe_load(path.read_text(encoding="utf-8"))["ok"])
    assert fields <= cols, f"patch fields not in HeroStore columns: {fields - cols}"


def test_redraft_keeps_review_only_if_values_unchanged(review):
    G.main(["--criterion", "drv_rent"])
    rows = _rows(review / "ai_drafts.csv")
    rows[0].update(reviewed_by="김민수", accept="Y")
    _write(review, rows)
    G.main(["--criterion", "drv_rent"])                       # identical draft: review kept
    assert _rows(review / "ai_drafts.csv")[0]["reviewed_by"] == "김민수"
    changed = dict(_rows(review / "ai_drafts.csv")[0], draft_base="9999999")
    G.upsert([changed])                                         # values changed: review cleared
    r = _rows(review / "ai_drafts.csv")[0]
    assert r["draft_base"] == "9999999" and r["reviewed_by"] == r["accept"] == ""


def test_parse_draft_strict():
    c = {"data_type": "number"}
    ok = '{"low": 1, "base": 2, "high": 3, "reasoning": "x", "sources": ["S31"]}'
    assert G.parse_draft(ok, c, {"S31"})["base"] == 2
    for bad in ['{"low": 1, "base": 5, "high": 3, "reasoning": "x", "sources": []}',
                '{"low": 1, "base": 2, "high": 3, "reasoning": "x", "sources": ["S99"]}',
                '{"low": "a", "base": 2, "high": 3, "reasoning": "x", "sources": []}',
                '{"low": 1, "base": 2, "high": 3, "reasoning": "", "sources": []}',
                '{"low": 1, "base": 2, "high": 3, "reasoning": "x", "sources": [], "extra": 1}']:
        with pytest.raises(ValueError):
            G.parse_draft(bad, c, {"S31"})


def test_cli_refuses_real_backend(review, monkeypatch, fake_claude):
    log = fake_claude()
    monkeypatch.setenv("LLM_BACKEND", "claude_cli")
    from agents import llm
    with pytest.raises(llm.LLMRefused):
        G.main(["--criterion", "drv_rent"])
    assert not log.exists() and not (review / "ai_drafts.csv").exists()


@pytest.fixture
def client(loaded):
    from api import main
    with TestClient(main.app) as c:
        yield c


def test_api_draft_one_with_real_backend_and_list(client, review, monkeypatch, fake_claude):
    fake_claude("""echo '{"low": 2000000, "base": 2400000, "high": 3000000, "reasoning": "KREI 임차료 비중 기준 [S31]", "sources": ["S31"]}'""")
    monkeypatch.setenv("LLM_BACKEND", "claude_cli")
    r = client.post("/review/drafts/drv_rent").json()
    assert r["backend"] == "claude_cli" and r["draft_base"] == 2400000 and r["draft_sources"] == "S31"
    fake_claude('echo "임대료는 아마 250만 원쯤"')                 # prose: falls back to the mock 초안
    r2 = client.post("/review/drafts/mkt_patience").json()
    assert "invalid output" in r2["backend"] and r2["draft_reasoning"].startswith("초안")
    d = client.get("/review/drafts").json()
    assert d["counts"] == {"drafts": 2, "reviewed": 0, "accepted": 0}
    assert client.post("/review/drafts/nope").status_code == 404


def test_apply_reviewed_keeps_review_sheet_rows(review):
    """research/sync_review_sheet.py writes into the same patch (filled_by 검토표); the AI helper keeps those rows
    and never overwrites a member's sheet review with an AI draft."""
    review.mkdir(parents=True, exist_ok=True)
    (review / "accepted_patch.yaml").write_text(yaml.safe_dump({
        "_meta": {}, "drv_rent": {"base": 1, "filled_by": "검토표", "reviewed_by": "박재현"},
        "old_ai": {"base": 2, "filled_by": "AI", "reviewed_by": "x"},
        "sim_assumptions": {"sim_params:svc_order_min": {"verdict": "맞음"}}}, allow_unicode=True), encoding="utf-8")
    _write(review, [_row("ok", "김민수", "Y"), _row("drv_rent", "김민수", "Y")])
    path, _ = G.apply_reviewed()
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert doc["drv_rent"] == {"base": 1, "filled_by": "검토표", "reviewed_by": "박재현"}
    assert doc["ok"]["filled_by"] == "AI" and "old_ai" not in doc and doc["sim_assumptions"]
