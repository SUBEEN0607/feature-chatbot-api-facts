"""Guesstimation helper: AI drafts low/base/high for a criterion, a member reviews, only reviewed drafts move on.

  python -m agents.guesstimate --criterion drv_rent [--criterion mkt_patience ...]
  python -m agents.guesstimate --all-low-confidence          # every guesstimate row with confidence L
  python -m agents.guesstimate --apply-reviewed              # reviewed + accept=Y rows -> accepted_patch.yaml

Each draft = RAG top-k evidence + a prompt asking for low/base/high, a one-line reasoning chain and cited
source ids, through agents/llm.py. On the command line only the offline mock backend runs: it derives a
clearly labelled 초안 from the current hero values and the retrieved evidence. A real model drafts one
criterion per API request (POST /review/drafts/{criterion_id}).

Writes ONLY research/review/ai_drafts.csv and research/review/accepted_patch.yaml. It never writes
research/guesstimate.xlsx, research/hero_base.yaml or research/shocks.yaml (guarded in code).
The patch uses the HeroStore column names of research/build_workbook.py (low, base, high,
reasoning_chain, source_id, confidence, filled_by, reviewed_by); a member applies it with
  .venv/bin/python research/build_workbook.py --apply-patch research/review/accepted_patch.yaml
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

from . import llm

REPO = Path(__file__).resolve().parents[1]
PROTECTED = {REPO / "research" / n for n in ("guesstimate.xlsx", "hero_base.yaml", "shocks.yaml")}
COLUMNS = ["criterion_id", "name_ko", "unit", "current_low", "current_base", "current_high", "current_confidence",
           "current_source_id", "draft_low", "draft_base", "draft_high", "draft_reasoning", "draft_sources",
           "ai_confidence", "backend", "model", "drafted_at", "reviewed_by", "accept", "review_note"]
DRAFT_FIELDS = ("draft_low", "draft_base", "draft_high", "draft_reasoning", "draft_sources")
REVIEW_FIELDS = ("reviewed_by", "accept", "review_note")
MARKER = "RESPOND_WITH_GUESSTIMATE_JSON"


def review_dir() -> Path:
    return Path(os.environ.get("REVIEW_DIR", REPO / "research" / "review")).resolve()


def drafts_path() -> Path:
    return review_dir() / "ai_drafts.csv"


def patch_path() -> Path:
    return review_dir() / "accepted_patch.yaml"


def _guard(path: Path, suffix: str) -> Path:
    """Refuse any write outside the review dir, to a protected research file, or with an unexpected type."""
    p = Path(path).resolve()
    if p in PROTECTED or p.name in {"guesstimate.xlsx", "hero_base.yaml", "shocks.yaml"}:
        raise PermissionError(f"refusing to write {p}: research inputs change only through a member's review")
    if review_dir() not in p.parents or p.suffix != suffix:
        raise PermissionError(f"refusing to write {p}: drafts go to {review_dir()}/*{suffix} only")
    return p


# --- inputs ---

def criteria() -> dict:
    with open(REPO / "ontology" / "criteria.csv", encoding="utf-8") as f:
        return {r["criterion_id"]: r for r in csv.DictReader(f)}


def source_ids() -> set[str]:
    with open(REPO / "ontology" / "sources.csv", encoding="utf-8") as f:
        return {r["source_id"] for r in csv.DictReader(f)}


def hero() -> dict:
    h = yaml.safe_load((REPO / "research" / "hero_base.yaml").read_text(encoding="utf-8"))
    return {k: v for k, v in h.items() if not k.startswith("_")}


def low_confidence_ids() -> list[str]:
    return [k for k, v in hero().items() if v.get("method") == "guesstimate" and v.get("confidence") == "L"]


EVIDENCE_DOCS = ("rag/corpus/", "ontology/sources.csv")   # research reports + source list, not project docs


def evidence(c: dict, k: int, cited: str | None = None) -> list[dict]:
    """The criterion's already-cited sources first, then top-k evidence chunks by similarity."""
    from rag.retrieve import retrieve
    q = f"{c['name_ko']} {c['name_en']} {c.get('notes', '')}"[:300]
    hits = retrieve(q, k=k, doc_prefixes=EVIDENCE_DOCS)
    want = [x for x in (cited or "").split(";") if x]
    if want:
        pinned = retrieve(" ".join(want) + " " + q, k=40, doc_prefixes=("ontology/sources.csv",))
        pinned = [h for h in pinned if h["source_id"] in want]
        seen = {h["chunk_id"] for h in pinned}
        hits = pinned + [h for h in hits if h["chunk_id"] not in seen]
    return hits[: k + len(want)]


# --- drafting ---

def _is_num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _round(v: float) -> float | int:
    return int(round(v)) if abs(v) >= 100 else round(v, 4)


def mock_draft(cid: str, c: dict, cur: dict, hits: list[dict]) -> dict:
    """Deterministic 초안 from the current hero values; the evidence is listed for the reviewer, not used."""
    unit = c.get("unit") or ""
    cands = list(dict.fromkeys(h["source_id"] for h in hits if h.get("source_id")))[:3]
    tag = re.compile(r"^\[S\d+\]\s*")
    lead = "; ".join(f"[{h.get('source_id') or Path(h['doc_id']).stem[:24]}] {tag.sub('', h['text'].strip())[:40]}"
                     for h in hits[:3]).replace("\n", " ")[:240]
    base = cur.get("base")
    if base is None:
        return {"low": None, "base": None, "high": None, "sources": cands,
                "reasoning": f"초안(mock): 현재 값이 없어 숫자를 만들지 않음. 인터뷰나 자료로 채울 항목. 확인할 근거 후보 {lead or '없음'}"}
    lo, hi = cur.get("low"), cur.get("high")
    if _is_num(base):
        span = abs(base) * 0.2
        lo = lo if _is_num(lo) else _round(base - span)
        hi = hi if _is_num(hi) else _round(base + span)
    else:
        lo, hi = (lo if lo is not None else base), (hi if hi is not None else base)
    show = (lambda v: f"{v:,} {unit}".rstrip()) if _is_num(base) else str
    return {"low": lo, "base": base, "high": hi, "sources": cands,
            "reasoning": (f"초안(mock, 모델 없음): 현재 시드 값 {show(base)} 유지, 범위 {show(lo)}에서 {show(hi)}. "
                          f"근거 후보를 읽고 사람이 고칠 것: {lead or '검색된 출처 없음'}")}


def build_prompt(cid: str, c: dict, cur: dict, hits: list[dict]) -> str:
    ctx = "\n\n".join(f"[{h.get('source_id') or 'doc'}] {h['text'][:600]}" for h in hits)
    return f"""대학로 독립 삼겹살집(가상 composite) 디지털 트윈의 기준값을 추정합니다.

기준: {cid} / {c['name_ko']} ({c['name_en']}), 단위 {c.get('unit') or '-'}, 자료형 {c.get('data_type')}
설명: {c.get('notes', '')}
현재 시드 값: low={cur.get('low')} base={cur.get('base')} high={cur.get('high')} (신뢰도 {cur.get('confidence')}, 출처 {cur.get('source_id') or '없음'})

[근거 자료]
{ctx}

규칙: 근거 자료에 있는 숫자와 계산으로만 추정하고, 근거가 없으면 현재 값을 유지하며 그렇다고 쓰세요.
sources 에는 위 대괄호 안의 S 로 시작하는 출처 id만 쓰세요.
{MARKER}
JSON 객체 하나만 출력: {{"low": <값>, "base": <값>, "high": <값>, "reasoning": "<한 줄 계산 근거>", "sources": ["S..", ...]}}"""


def parse_draft(text: str, c: dict, allowed: set[str]) -> dict:
    """Strict: one JSON object; numbers for number criteria; base inside [low, high]; known source ids only."""
    t = (text or "").strip()
    m = re.fullmatch(r"```(?:json)?\s*(\{.*\})\s*```", t, re.S)
    t = m.group(1) if m else t
    d = json.loads(t)
    if not isinstance(d, dict) or set(d) != {"low", "base", "high", "reasoning", "sources"}:
        raise ValueError("keys must be exactly low, base, high, reasoning, sources")
    if c.get("data_type") == "number":
        if not all(_is_num(d[k]) for k in ("low", "base", "high")):
            raise ValueError("number criterion needs numeric low/base/high")
        if not min(d["low"], d["high"]) <= d["base"] <= max(d["low"], d["high"]):
            raise ValueError("base outside [low, high]")
    if not isinstance(d["reasoning"], str) or not d["reasoning"].strip():
        raise ValueError("reasoning missing")
    if not isinstance(d["sources"], list) or not set(d["sources"]) <= allowed:
        raise ValueError(f"unknown source ids {sorted(set(d['sources']) - allowed)}")
    return d


def draft_one(cid: str, ctx: llm.RequestContext, k: int = 5) -> dict:
    """One criterion, one llm.complete call. Returns a CSV row (review columns blank)."""
    crit, cur_all = criteria(), hero()
    if cid not in crit:
        raise KeyError(cid)
    c, cur = crit[cid], cur_all.get(cid, {})
    hits = evidence(c, k, cur.get("source_id") or c.get("source_id"))
    mock = mock_draft(cid, c, cur, hits)
    res = llm.complete(build_prompt(cid, c, cur, hits), ctx=ctx, mock_text=json.dumps(
        {"low": mock["low"], "base": mock["base"], "high": mock["high"], "reasoning": mock["reasoning"],
         "sources": mock["sources"]}, ensure_ascii=False))
    backend = res.backend
    try:
        d = parse_draft(res.text, c, source_ids())
    except (ValueError, json.JSONDecodeError) as e:
        d = mock
        backend = f"{res.backend} (invalid output: {str(e)[:80]}; mock 초안 사용)"
    return {"criterion_id": cid, "name_ko": c["name_ko"], "unit": c.get("unit"),
            "current_low": cur.get("low"), "current_base": cur.get("base"), "current_high": cur.get("high"),
            "current_confidence": cur.get("confidence"), "current_source_id": cur.get("source_id"),
            "draft_low": d["low"], "draft_base": d["base"], "draft_high": d["high"],
            "draft_reasoning": d["reasoning"], "draft_sources": ";".join(d["sources"]),
            "ai_confidence": "L", "backend": backend, "model": res.model,
            "drafted_at": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "reviewed_by": "", "accept": "", "review_note": ""}


# --- CSV ---

def _s(v) -> str:
    return "" if v is None else str(v)


def read_drafts(path: Path | None = None) -> list[dict]:
    p = path or drafts_path()
    if not p.exists():
        return []
    with open(p, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def upsert(rows: list[dict], path: Path | None = None) -> Path:
    """Merge by criterion_id. A re-draft with different values clears that row's review, so an acceptance
    never silently carries over to numbers the reviewer did not see."""
    p = _guard(path or drafts_path(), ".csv")
    old = {r["criterion_id"]: r for r in read_drafts(p)}
    for r in rows:
        r = {k: _s(r.get(k)) for k in COLUMNS}
        prev = old.get(r["criterion_id"])
        same = prev is not None and all(prev.get(f, "") == r[f] for f in DRAFT_FIELDS)
        for f in REVIEW_FIELDS:   # review survives only an identical re-draft; never arrives with new numbers
            r[f] = prev.get(f, "") if same else ""
        old[r["criterion_id"]] = r
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8-sig", newline="") as f:   # BOM so Excel shows Korean correctly
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        for cid in sorted(old):
            w.writerow({k: old[cid].get(k, "") for k in COLUMNS})
    tmp.replace(p)
    return p


# --- patch ---

def _typed(v: str):
    if v is None or v.strip() == "":
        return None
    try:
        f = float(v)
        return int(f) if f.is_integer() and "." not in v else f
    except ValueError:
        return v


def reviewed_rows(rows: list[dict]) -> list[dict]:
    """Only rows a named member reviewed AND accepted."""
    return [r for r in rows if (r.get("reviewed_by") or "").strip()
            and (r.get("accept") or "").strip().upper() in ("Y", "YES")]


def apply_reviewed(drafts: Path | None = None, patch: Path | None = None) -> tuple[Path, int]:
    out = _guard(patch or patch_path(), ".yaml")
    rows = reviewed_rows(read_drafts(drafts))
    doc = {"_meta": {
        "generated_by": "python -m agents.guesstimate --apply-reviewed",
        "from": str((drafts or drafts_path()).name),
        "rule": "only rows with reviewed_by filled and accept=Y",
        "fields": "HeroStore columns of research/build_workbook.py",
        "note": "Not applied automatically. Apply with: research/build_workbook.py --apply-patch <this file>",
        "rows": len(rows)}}
    if out.exists():   # rows the review sheet sync wrote (filled_by 검토표) stay; the sheet replaces them, not this
        old = yaml.safe_load(out.read_text(encoding="utf-8")) or {}
        doc.update({k: v for k, v in old.items() if isinstance(v, dict) and v.get("filled_by") == "검토표"})
        if old.get("sim_assumptions"):
            doc["sim_assumptions"] = old["sim_assumptions"]
    for r in rows:
        if doc.get(r["criterion_id"], {}).get("filled_by") == "검토표":
            continue                  # a member's sheet review wins over an AI draft
        doc[r["criterion_id"]] = {
            "low": _typed(r["draft_low"]), "base": _typed(r["draft_base"]), "high": _typed(r["draft_high"]),
            "reasoning_chain": r["draft_reasoning"], "source_id": r["draft_sources"] or None,
            "confidence": r.get("ai_confidence") or "L", "filled_by": "AI", "reviewed_by": r["reviewed_by"].strip()}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return out, len(rows)


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--criterion", action="append", default=[], help="criterion_id (repeatable)")
    ap.add_argument("--all-low-confidence", action="store_true", help="every guesstimate row with confidence L")
    ap.add_argument("--apply-reviewed", action="store_true", help="write accepted_patch.yaml from reviewed rows")
    ap.add_argument("--k", type=int, default=5, help="evidence chunks per criterion")
    a = ap.parse_args(argv)
    if a.apply_reviewed:
        p, n = apply_reviewed()
        print(f"wrote {p} ({n} reviewed + accepted rows)", file=sys.stderr)
        return
    ids = list(dict.fromkeys(a.criterion + (low_confidence_ids() if a.all_low_confidence else [])))
    if a.all_low_confidence:   # also refresh rows already in the file, so current_* never goes stale
        ids += [r["criterion_id"] for r in read_drafts() if r["criterion_id"] not in ids and r["criterion_id"] in criteria()]
    if not ids:
        ap.error("give --criterion, --all-low-confidence or --apply-reviewed")
    rows = []
    for cid in ids:   # mock only on the CLI (enforced in llm.complete); each item gets its own context
        rows.append(draft_one(cid, llm.RequestContext(session_id="guesstimate-cli", origin="cli"), a.k))
    p = upsert(rows)
    print(f"wrote {len(rows)} drafts to {p}", file=sys.stderr)


if __name__ == "__main__":
    main()
