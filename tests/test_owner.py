import json

import pytest

from agents import owner

MENU = {"absorb": {"args": {}}, "reprice": {"args": {"pct": [-0.15, 0.15]}}}


@pytest.mark.parametrize("text,action,fallback", [
    ('{"action": "reprice", "args": {"pct": 0.1}, "reason": "원가 상승 [1]"}', "reprice", False),
    ('```json\n{"action": "absorb", "args": {}, "reason": "버틴다"}\n```', "absorb", False),
    ('사장 생각: {"action": "reprice", "args": {"pct": 0.1}, "reason": "x"}', "absorb", True),
    ('{"action": "close_store", "args": {}, "reason": "x"}', "absorb", True),
    ('{"action": "reprice", "args": {"pct": 0.5}, "reason": "x"}', "absorb", True),
    ('{"action": "reprice", "args": {"pct": true}, "reason": "x"}', "absorb", True),
    ('{"action": "reprice", "args": {"pct": 0.1}, "reason": "x", "extra": 1}', "absorb", True),
    ('{"action": "reprice", "args": {"pct": 0.1}, "reason": ""}', "absorb", True),
    ('{"action": "reprice", "args": {"hours": 1}, "reason": "x"}', "absorb", True),
    ('', "absorb", True),
])
def test_parse_strict(text, action, fallback):
    d = owner.parse_decision(text, MENU)
    assert d["action"] == action and d["fallback"] is fallback
    if fallback:
        assert d["reason"].startswith("fallback:") and d["args"] == {}


def test_menu_has_absorb():
    assert "absorb" in owner.action_menu()


def test_prompt_lists_menu_and_marker():
    p = owner.build_prompt({"prd_meat_price": {"base": "19000", "unit": "₩/인분"}},
                           [{"doc_id": "d", "source_id": "S01", "text": "근거"}], shock={"id": "SH03"}, menu=MENU)
    assert owner.MARKER in p and "reprice" in p and "19000" in p and "(S01)" in p


def test_decide_with_mock(fresh_llm):
    d = owner.decide(fresh_llm.RequestContext(session_id="t"), {}, [{"doc_id": "d", "text": "x"}])
    assert d["action"] == "absorb" and d["fallback"] is False and d["backend"] == "mock"
    json.dumps(d, ensure_ascii=False)
