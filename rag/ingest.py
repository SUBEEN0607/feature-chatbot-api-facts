"""Chunk the corpus and embed it into doc_chunk.  python -m rag.ingest

Corpus: rag/corpus/*.md (the two research reports), research/*.md (the team's sourcing notes),
docs/*.md, ontology/README.md, and one chunk per row of ontology/sources.csv (title + reliability note,
tagged with its source_id), and one chunk per sourced hero input (research/hero_base.yaml, see hero_docs).
Persona chat retrieves only the evidence part (see api.main.EVIDENCE_DOCS).
Re-running is safe: a document's chunks are replaced, and unchanged chunks keep their embedding.
"""
from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import delete, select

from db.models import DocChunk
from db.session import REPO, get_engine, init_db, session_factory

from .embed import get_embedder

MAX_CHARS, OVERLAP = 900, 150


def md_chunks(text: str) -> list[tuple[str, str]]:
    """(section path, chunk text): split on headings, then window long sections."""
    out, path, buf = [], [], []

    def flush():
        body = "\n".join(buf).strip()
        if body:
            sec = " > ".join(path)
            for i in range(0, len(body), MAX_CHARS - OVERLAP):
                piece = body[i:i + MAX_CHARS].strip()
                if len(piece) > 40:
                    out.append((sec, piece))
                if i + MAX_CHARS >= len(body):
                    break
        buf.clear()

    for line in text.splitlines():
        m = re.match(r"^(#{1,4})\s+(.*)", line)
        if m:
            flush()
            level = len(m.group(1))
            path[:] = path[: level - 1] + [m.group(2).strip()]
        else:
            buf.append(line)
    flush()
    return out


def corpus() -> list[dict]:
    docs = []
    files = sorted((REPO / "rag" / "corpus").glob("*.md")) + sorted((REPO / "research").glob("*.md")) + \
        sorted((REPO / "docs").glob("*.md")) + [REPO / "ontology" / "README.md"]
    for f in files:
        if not f.exists():
            continue
        text = f.read_text(encoding="utf-8")
        title = next((l.lstrip("# ").strip() for l in text.splitlines() if l.startswith("# ")), f.stem)
        docs.append({"doc_id": str(f.relative_to(REPO)), "title": title, "source_id": None,
                     "chunks": md_chunks(text)})
    src = REPO / "ontology" / "sources.csv"
    if src.exists():
        for r in pd.read_csv(src, dtype=str, keep_default_na=False).to_dict("records"):
            body = (f"[{r['source_id']}] {r['title']}. {r['publisher_author']} {r['year']}. "
                    f"Type: {r['type']}. {r['reliability_note']} {r['url']}").strip()
            docs.append({"doc_id": f"ontology/sources.csv#{r['source_id']}", "title": r["title"],
                         "source_id": r["source_id"], "chunks": [("sources.csv", body)]})
    docs += hero_docs()
    return docs


def hero_docs() -> list[dict]:
    """One Korean chunk per sourced hero input (research/hero_base.yaml + its criteria.csv name and note), so a
    question like "고기 원가" retrieves the row that holds the number and its sourcing. Derived rows (매출, 영업이익,
    식재료비 ...) are left out: the workbook P&L is not the game's 평소 달, which the chat gets from the sim at request
    time (agents/store_facts.py), so indexing it would put a stale number in front of the model."""
    import yaml
    hb, cc = REPO / "research" / "hero_base.yaml", REPO / "ontology" / "criteria.csv"
    if not hb.exists() or not cc.exists():
        return []
    crit = {r["criterion_id"]: r for r in pd.read_csv(cc, dtype=str, keep_default_na=False).to_dict("records")}
    out = []
    for cid, h in (yaml.safe_load(hb.read_text(encoding="utf-8")) or {}).items():
        if cid.startswith("_") or not isinstance(h, dict) or h.get("method") == "derived" or h.get("base") in (None, ""):
            continue
        c = crit.get(cid, {})
        name = c.get("name_ko") or cid
        rng = f" (낮게 {h['low']}, 높게 {h['high']})" if h.get("low") not in (None, "") and h.get("high") not in (None, "") else ""
        src = h.get("source_id") or ""
        body = (f"가게 숫자: {name}. 기본값 {h['base']} {h.get('unit') or ''}{rng}. 방법 {h.get('method')}, 확신도 "
                f"{h.get('confidence')}, 출처 {src or '없음 (가정)'}. {c.get('notes', '')}").strip()
        out.append({"doc_id": f"research/hero_base.yaml#{cid}", "title": f"가게 숫자: {name}",
                    "source_id": src.split(";")[0].strip() or None, "chunks": [("hero_base.yaml", body)]})
    return out


def ingest(engine=None, embedder=None) -> dict:
    engine = init_db(engine or get_engine())
    emb = embedder or get_embedder()
    docs = corpus()
    n_new = n_total = 0
    with session_factory(engine)() as s, s.begin():
        for d in docs:
            rows = []
            for i, (sec, text) in enumerate(d["chunks"]):
                cid = hashlib.sha256(f"{d['doc_id']}|{i}|{text}".encode()).hexdigest()[:32]
                rows.append((cid, i, sec, text))
            keep = {r[0] for r in rows}
            old = {c.chunk_id: c for c in s.scalars(select(DocChunk).where(DocChunk.doc_id == d["doc_id"]))}
            s.execute(delete(DocChunk).where(DocChunk.doc_id == d["doc_id"], DocChunk.chunk_id.not_in(keep)))
            todo = [r for r in rows if r[0] not in old or old[r[0]].embed_model != emb.name]
            vecs = emb.passages([f"{d['title']} | {r[2]}\n{r[3]}" for r in todo]) if todo else []
            for (cid, i, sec, text), v in zip(todo, vecs):
                s.merge(DocChunk(chunk_id=cid, doc_id=d["doc_id"], source_id=d["source_id"], title=d["title"],
                                 section=sec, chunk_index=i, text=text, embed_model=emb.name,
                                 embedding=[float(x) for x in v]))
            n_new += len(todo)
            n_total += len(rows)
    return {"docs": len(docs), "chunks": n_total, "embedded_now": n_new, "embed_model": emb.name}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--embedder", default=None, help="e5 (default) | hash")
    a = ap.parse_args()
    print(ingest(embedder=get_embedder(a.embedder)), file=sys.stderr)
