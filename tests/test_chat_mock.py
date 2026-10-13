"""The mock owner answers depend on the question: intent-specific template over the tagged store facts
(agents/store_facts.py), each number cited with its fact's source tag, and only numbers taken from the facts / the
sim result. Accuracy per question is measured by tests/test_chat_eval.py."""
import re

import pytest
from fastapi.testclient import TestClient

from agents import chat as chat_agent
from agents.prewarm import QUESTIONS

NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")


@pytest.fixture(scope="module")
def client(loaded):
    from api import main
    with TestClient(main.app) as c:
        yield c


def _context(q, shocks):
    if not shocks:
        return None
    return {"shock": shocks[0], "action": "reprice" if q.startswith("이번 달 결정") else "absorb"}


def test_classify_covers_every_preset():
    intents = [chat_agent.classify(q) for q, _ in QUESTIONS]
    assert len(set(intents)) >= 12, intents        # not one template for everything
    assert chat_agent.classify("돼지고기 값이 오르면?") == "cost"
    assert chat_agent.classify("임대료가 오르면?") == "rent"
    assert chat_agent.classify("이번 달 결정은 왜 그렇게 하셨어요?") == "why"


def test_twenty_presets_distinct_cited_and_no_invented_numbers(client, fresh_llm):
    from api import main
    from db.session import database_url, get_engine, session_factory
    answers = {}
    with session_factory(get_engine(database_url()))() as s:
        hero = main._with_baseline(main._hero(s))   # what /chat feeds the persona (chat_inputs)
        for q, shocks in QUESTIONS:
            ctx = _context(q, shocks)
            r = client.post("/chat", json={"persona": "owner", "message": q, "context": ctx})
            assert r.status_code == 200, r.text
            d = r.json()
            body = d["answer"]
            for leak in ("가상 매장", "mock", "자료에 없는 숫자"):
                assert leak not in body, f"{q}: demo text leaks '{leak}'"
            assert q not in body, "the answer should not just echo the question"
            labels = {c["label"] for c in d["citations"]}       # fact sources the answer cites + retrieved chunks
            cited = set(re.findall(r"\[([^\]]+)\]", body))
            assert cited and cited <= labels, f"{q}: cites {cited}, citations {labels}"
            shock, action = (ctx or {}).get("shock"), (ctx or {}).get("action")
            sim, _ = main._sim_context(shock, action)
            allowed = (" ".join(chat_agent.facts(hero, district=main._chat_district(s)).values()) + " ".join(chat_agent.sim_lines(sim)) + q
                       + main._shock_note(s, shock, action) + " ".join(labels))
            for n in NUM.findall(body):
                assert n in allowed, f"{q}: number {n} not from hero/sim inputs"
            answers[q] = body
    bodies = list(answers.values())
    assert len(set(bodies)) == len(bodies) == 20, "two preset questions got the same answer"


def test_waiting_app_question_is_tech_and_plain_waiting_is_busy():
    assert chat_agent.classify("테이블링 같은 웨이팅 앱 쓰세요?") == "tech"
    assert chat_agent.classify("웨이팅이 얼마나 길어요?") == "busy"
    hits = [{"doc_id": "docs/RESEARCH.md", "source_id": None, "title": "리서치 과정과 분류 기준", "text": "기술 도입은 이번 분석 범위에서 뺐습니다.", "score": 0.5}]
    F = {"tables": chat_agent.SF.Fact("tables", "테이블", "10개 (테이블당 4석)", "S34")}
    t = chat_agent.mock_answer("owner", "테이블링 같은 웨이팅 앱 쓰세요?", hits, F, None, "")
    assert "웨이팅 앱" in t and "테이블 10개" in t, t
    t2 = chat_agent.mock_answer("owner", "키오스크 들이실 거예요?", hits, {}, None, "")
    assert "키오스크" in t2 and "웨이팅" not in t2


def test_persona_answer_citations_carry_ids_and_titles(client, fresh_llm):
    s = client.post("/season", json={"mode": "free", "seed": 3}).json()
    a = client.post(f"/persona/{s['id']}/ask", json={"who": "owner", "question": "임대료가 오르면 어떡하세요?"}).json()
    cites = a["citations"]
    assert cites and all(c["label"] and c["title"] for c in cites)
    assert len({c["label"] for c in cites}) == len(cites), "one row per source"
    from db.session import database_url, get_engine, session_factory
    from db import models as M
    with session_factory(get_engine(database_url()))() as db:
        for c in cites:
            if c.get("source_id"):
                assert c["title"] == db.get(M.Source, c["source_id"]).title
    cited = set(re.findall(r"\[([^\]]+)\]", a["answer"]))
    assert cited <= {c["label"] for c in cites}, (cited, cites)
