"""출처 검색 API (목업 챗봇용). 실행: python -m uvicorn api.cite_api:app --port 8001

ontology/sources.csv 에서 공신력 있는 출처만 골라 질문과 가장 가까운 것을 돌려준다.
- 포함: 논문(paper), 공공데이터(public_data), 공공기관 보고서(report)
- 제외: 뉴스(news), 블로그(blog), 내부 문서(internal), 익명·미검증 표시가 있는 행
답변 문장은 모델이 만들지 않고, 출처 메모(reliability_note)를 그대로 옮긴다.
"""
from __future__ import annotations

import csv
import re
from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

ROOT = Path(__file__).resolve().parent.parent
CSV = ROOT / "ontology" / "sources.csv"
CREDIBLE_TYPES = {"paper", "public_data", "report"}
# 뉴스는 원자료를 만든 기관이 제목·발행처·메모에 명시된 경우만 쓴다 (예: "참가격", "국세청 2023").
PRIMARY_AGENCIES = (
    "참가격", "축산물품질평가원", "KAMIS", "국세청", "한국은행", "식약처", "식품의약품안전처", "KREI", "농촌경제연구원",
    "한국부동산원", "농림축산식품부", "중소벤처기업부", "국가데이터처", "통계청", "소상공인시장진흥공단",
    "금융위원회", "기상청", "서울특별시",
)
NEWS_EXCLUDE = ("anecdotal", "opinion", "vendor", "snippet", "scope unclear")  # 사례, 의견, 업체 추정, 검색 조각, 범위 불명
EXCLUDE_PREFIXES = ("UNVERIFIED",)              # whole source flagged by the research team
EXCLUDE_MARKERS = (                                 # only a summary, snippet or preprint was read, not the checked original
    "anonymous", "search snippet", "search summary", "not the paper", "preprint", "not opened",
)

app = FastAPI(title="출처 검색 (목업 챗봇)")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5174", "http://localhost:5174"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


def _load() -> list[dict]:
    rows = []
    with CSV.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            note = r.get("reliability_note", "") or ""
            if r.get("type") not in CREDIBLE_TYPES:
                if r.get("type") != "news":
                    continue
                named = " ".join([r["title"], r.get("publisher_author", ""), note])
                if not any(a in named for a in PRIMARY_AGENCIES):
                    continue
                if any(m in note.lower() for m in NEWS_EXCLUDE):
                    continue
            if note.upper().startswith(EXCLUDE_PREFIXES) or any(m in note.lower() for m in EXCLUDE_MARKERS):
                continue
            rows.append({
                "id": r["source_id"],
                "title": r["title"],
                "publisher": r.get("publisher_author", ""),
                "year": r.get("year", "") or "",
                "url": r.get("url", ""),
                "type": r["type"],
                "note": note,
            })
    return rows


SOURCES = _load()
TYPE_LABEL = {"paper": "논문", "public_data": "공공데이터", "report": "공공기관 보고서", "news": "언론 보도 (원자료 기관 명시)"}


def _grams(text: str) -> set[str]:
    t = re.sub(r"[^0-9A-Za-z가-힣]+", "", text.lower())
    return {t[i:i + 2] for i in range(len(t) - 1)}


def _score(q: set[str], s: dict) -> float:
    """Share of the question's two-character pieces that appear in the source's title, publisher or note."""
    doc = _grams(" ".join([s["title"], s["publisher"], s["note"]]))
    if not q or not doc:
        return 0.0
    overlap = len(q & doc)
    return overlap / len(q) if overlap >= 2 else 0.0


@app.get("/cite")
def cite(q: str = Query(..., min_length=1, max_length=300), k: int = Query(3, ge=1, le=5)):
    qg = _grams(q)
    ranked = sorted(((_score(qg, s), s) for s in SOURCES), key=lambda x: -x[0])
    hits = [s for sc, s in ranked if sc >= 0.15][:k]
    cites = [{
        "id": s["id"], "title": s["title"], "publisher": s["publisher"], "year": s["year"],
        "type": TYPE_LABEL[s["type"]], "url": s["url"], "note": s["note"],
    } for s in hits]
    if not cites:
        answer = "목업에서 쓰는 공신력 있는 출처 중에는 이 질문에 맞는 자료가 없어요. 출처 장부에서 전체 목록을 볼 수 있어요."
    else:
        answer = "공신력 있는 출처에서 찾은 내용이에요. 아래 자료 메모를 그대로 옮긴 것이라 숫자의 맥락은 원자료로 확인해 주세요."
    return {"answer": answer, "citations": cites, "credible_count": len(SOURCES)}


@app.get("/health")
def health():
    return {"ok": True, "credible_sources": len(SOURCES)}


# ---- 근거 항목 기반 답변 (pipelines/build_facts.py 가 만든 facts.json) ----
FACTS_PATH = ROOT / "web" / "public" / "mock" / "facts.json"


def _facts() -> dict:
    import json
    return json.loads(FACTS_PATH.read_text(encoding="utf-8"))


def _tag_in(tag: str, q_raw: str) -> bool:
    # "1월"이 "11월" 안에 들어가 잘못 맞지 않도록, 숫자로 시작하는 태그는 앞에 숫자가 없어야 한다.
    if tag[:1].isdigit():
        return re.search(r"(?<![0-9])" + re.escape(tag), q_raw) is not None
    return tag in q_raw


def _fact_score(q: set[str], q_raw: str, fact: dict) -> tuple[int, float]:
    tags = fact.get("tags", [])
    tag_hits = sum(1 for t in tags if t and _tag_in(t, q_raw))
    doc = _grams(fact["text"] + " " + " ".join(tags))
    overlap = len(q & doc)
    return tag_hits, overlap / max(1, len(q))


@app.get("/ask")
def ask(q: str = Query(..., min_length=1, max_length=300), k: int = Query(4, ge=1, le=6)):
    data = _facts()
    qg = _grams(q)
    scored = [(_fact_score(qg, q, f), f) for f in data["facts"]]
    scored = [(s, f) for s, f in scored if s[0] > 0 or s[1] >= 0.5]
    if scored:
        top_tag = max(s[0] for s, _ in scored)
        # 태그가 가장 많이 맞은 항목끼리만 답한다 (예: "강남 카페"면 강남구 카페 항목만)
        scored = [(s, f) for s, f in scored if s[0] == top_tag] if top_tag > 0 else scored
    scored.sort(key=lambda x: (-x[0][0], -x[0][1]))
    hits = [f for _, f in scored][:k]
    if not hits:
        return {"answer": None, "facts": [], "citations": [],
                "message": "등록된 근거 자료에 없는 질문이에요. 화면의 숫자에 대한 질문이나 상권·상가·날씨·공휴일에 대한 질문을 해 주세요."}
    used_ids: list[str] = []
    facts_out = []
    for f in hits:
        cites = []
        for sid in f["sources"]:
            if sid not in used_ids:
                used_ids.append(sid)
            cites.append(sid)
        facts_out.append({"text": f["text"], "source_ids": cites})
    citations = []
    for sid in used_ids:
        s = data["sources"][sid]
        citations.append({"id": sid, "title": s["title"], "publisher": s["publisher"], "year": s["period"],
                          "type": "공공 API", "url": s["url"], "note": f"호출 식별자: {s['api']}"})
    answer = " ".join(f["text"] for f in facts_out)
    return {"answer": answer, "facts": facts_out, "citations": citations}
