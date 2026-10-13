"""The owner-chat eval (tests/chat_eval/questions.yaml) on the offline mock backend: every question answered right on
both chat paths, through the real API. No network: temp SQLite, hash embedder, mock LLM (conftest). The real-model
run is opt-in: scripts/chat_eval_gemini.sh."""
import re

import pytest
from fastapi.testclient import TestClient

from agents import chat as chat_agent
from agents import store_facts as SF
from tests.chat_eval import run as chat_eval
from tests.chat_eval import score

NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")


@pytest.fixture(scope="module")
def client(loaded):
    from api import main
    with TestClient(main.app) as c:
        yield c


@pytest.fixture(scope="module")
def result(client):
    return chat_eval.run(client, "mock", ("persona", "chat"))


def test_eval_set_is_well_formed():
    items = score.load()
    assert len(items) >= 25 and len({it["id"] for it in items}) == len(items)
    assert sum(it["category"] == "trap" for it in items) >= 3
    for it in items:
        assert it.get("source") and it.get("truth") and (it.get("expect") or it.get("expect_season")), it["id"]


def test_mock_answers_every_question_on_both_paths(result):
    fails = [(r["path"], r["id"], r["why"], r["answer"][:120]) for r in result["rows"] if not r["pass"]]
    assert not fails, fails
    assert {r["path"] for r in result["rows"]} == {"persona", "chat"}


def test_mock_numbers_all_come_from_the_facts(result, client):
    """Every number a mock answer says is in the facts block, the season facts, the question or a cited label."""
    from api import main
    from db.session import database_url, get_engine, session_factory
    sess = main._season(result["season_id"])
    with session_factory(get_engine(database_url()))() as s:
        F = SF.build(main._season_hero(main._hero(s), sess), district=main._chat_district(s), season=main._season_facts(sess))
    allowed = SF.block(F) + main._owner_note(sess)
    for r in result["rows"]:
        for n in NUM.findall(r["answer"]):
            assert n in allowed + r["q"] + " ".join(re.findall(r"\[([^\]]+)\]", r["answer"])), (r["id"], n, r["answer"])


def test_scorer_catches_wrong_answers():
    """The gate fails on known-bad answers (stale numbers, a number in an off-topic answer, a missing number)."""
    items = {it["id"]: it for it in score.load()}
    assert score.score_answer(items["q01_revenue"], "한 달 매출은 2,613만 원이에요")["pass"]
    assert not score.score_answer(items["q01_revenue"], "한 달 매출은 2,654만원이에요")["pass"]           # stale workbook
    assert not score.score_answer(items["q02_profit"], "122만원 남아요")["pass"]
    assert not score.score_answer(items["q29_trap_weather"], "모르겠어요. 야장은 8석이에요")["pass"]      # number in a trap
    assert score.score_answer(items["q29_trap_weather"], "그건 제가 가진 자료에 없어서 모르겠어요")["pass"]
    assert not score.score_answer(items["q31_trap_annual"], "연간으로는 1,138만원쯤이에요")["pass"]
    assert not score.score_answer(items["q22_price_up"], "영업이익이 24만원 늘어요")["pass"]               # covers missing


def test_offtopic_and_name_are_refused_without_numbers():
    F = {"tables": SF.Fact("tables", "테이블", "10개")}
    for q in ("내일 서울 날씨 어때요?", "비트코인 지금 사도 될까요?", "숙제 좀 도와주세요"):
        assert chat_agent.classify(q) == "unknown", q
        t = chat_agent.mock_answer("owner", q, [{"doc_id": "docs/RESEARCH.md", "text": "", "score": 0.1}], F, None, "")
        assert "모르" in t and not NUM.search(t), t
    assert chat_agent.classify("비 오는 날은 장사가 어때요?") == "weather"     # rain as a business question stays
    assert chat_agent.classify("사장님 가게 이름이 뭐예요?") == "name"


def test_real_backend_is_checked_and_falls_back(loaded, fresh_llm, monkeypatch):
    """A model answer with a number in none of its inputs, or a backend that is down, gets the template (marked)."""
    from api import main
    from db.session import database_url, get_engine, session_factory
    with session_factory(get_engine(database_url()))() as s:
        hero = main._with_baseline(main._hero(s))
    hits = [{"doc_id": "docs/RESEARCH.md", "source_id": None, "title": "t", "section": "s", "text": "근거 문장", "score": 0.5}]
    monkeypatch.setenv("LLM_BACKEND", "gemini")
    replies = iter(["월 임차료는 470만원이에요 [평소 달] — 고정비라 무서워요",
                    "월 임차료는 520만원이에요 [평소 달]"])
    monkeypatch.setitem(fresh_llm._BACKEND_FN, "gemini", lambda p, m: next(replies))
    ok = chat_agent.answer(fresh_llm.RequestContext("t1"), "owner", "월세는 얼마예요?", hits, hero)
    assert ok["backend"] == "gemini" and "470만원" in ok["answer"] and "—" not in ok["answer"]
    assert ok["citations"][0]["label"] == "평소 달" and ok["citations"][0]["title"] == SF.TAG_TITLES["평소 달"]
    bad = chat_agent.answer(fresh_llm.RequestContext("t2"), "owner", "월세는 얼마 내세요?", hits, hero)   # not a cache hit
    assert "invented a number 520" in bad["backend"] and "520" not in bad["answer"] and "470만원" in bad["answer"]

    def down(p, m):
        raise fresh_llm.LLMBackendError("gemini HTTP 503 (gemini-2.5-flash): busy")
    monkeypatch.setitem(fresh_llm._BACKEND_FN, "gemini", down)
    d = chat_agent.answer(fresh_llm.RequestContext("t3"), "owner", "객단가는 얼마예요?", hits, hero)
    assert "template used" in d["backend"] and "27,000원" in d["answer"]


def test_model_text_keeps_only_real_tags():
    tags = {"S36", "S31", "평소 달", "시즌 기록", "가정"}
    t = chat_agent.tidy("시급은 10,320원을 주고 있어요 [S36], [S31]. 요즘 쉽지 않네요 [상황].", tags)
    assert t == "시급은 10,320원을 주고 있어요 [S36], [S31]. 요즘 쉽지 않네요.", t
    t = chat_agent.tidy("폐업 비율이 10.1%예요 [근거 자료]. 고깃집은 15.4%입니다 [가게 숫자]. 평소 달 95만원 [평소 달].", tags)
    assert t == "폐업 비율이 10.1%예요. 고깃집은 15.4%입니다. 평소 달 95만원 [평소 달].", t
    assert chat_agent.tidy("그대로 [상황]", None) == "그대로 [상황]"          # no tag set: unchanged


def test_particle_skips_trailing_brackets():
    from agents.ko import eun, ga, ieyo
    assert eun("고깃집 생존율 (종로구 전체와 신촌역 상권, 이름 기준)") == "고깃집 생존율 (종로구 전체와 신촌역 상권, 이름 기준)은"
    assert eun("이름 기준)") == "이름 기준)은" and ga("가게(대학로)") == "가게(대학로)가" and ieyo("[평소 달]") == "[평소 달]이에요"
    assert eun("사과") == "사과는" and ga("2") == "2가" and ieyo("3") == "3이에요"     # unchanged cases
