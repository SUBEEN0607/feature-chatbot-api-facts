"""End-of-season report: JSON shape, CSV round-trip (BOM), printable HTML, Q&A with the number guard."""
import re

import pytest
from fastapi.testclient import TestClient

from agents.numbers import invented, pool
from agents import persona
from api import report as R


@pytest.fixture(scope="module")
def client(loaded):
    from api import main
    with TestClient(main.app) as c:
        yield c


@pytest.fixture(scope="module")
def season(client):
    s = client.post("/season", json={"mode": "free", "seed": 4}).json()
    for i in range(4):
        r = client.post(f"/season/{s['id']}/play", json={"plan": {"meat_price": 21000} if i == 1 else {},
                                                       "prediction": 1_000_000})
        assert r.status_code == 200, r.text
    return s["id"]


def test_report_json(client, season):
    rep = client.get(f"/season/{season}/report").json()
    assert set(rep) >= {"summary", "improvements", "uncertain", "good_decisions", "luck_months", "cash_only", "table",
                        "data_limits", "source"}
    for x in rep["cash_only"]:     # never presented as an improvement
        assert x["cash_delta"] > 0 and x["store_value_delta"] <= 0 and x["warning_ko"]
        assert all((i.get("month_label"), i.get("lever"), i.get("to")) != (x.get("month_label"), x.get("lever"), x.get("to"))
                   for i in rep["improvements"])
    assert len(rep["table"]) == 4 and rep["summary"]["months_played"] == 4
    assert rep["data_limits"]["total"] > 0 and 0 <= rep["data_limits"]["reviewed"] <= rep["data_limits"]["total"]
    assert len(rep["improvements"]) <= 5
    assert any(r["levers_changed"] for r in rep["table"]), "the month with a price change should list it"
    assert all("meat_price" not in (r["levers_changed"] or "") for r in rep["table"]), "levers shown in Korean"


def test_csv_round_trip(client, season):
    rep = client.get(f"/season/{season}/report").json()
    resp = client.get(f"/season/{season}/export.csv")
    assert resp.headers["content-type"].startswith("text/csv") and resp.content.startswith(b"\xef\xbb\xbf")
    cd = resp.headers["content-disposition"]      # plain <a href> download: ASCII name + RFC 5987 Korean name
    assert cd.startswith("attachment;") and cd.isascii() and "filename*=UTF-8''" in cd
    rows = R.from_csv(resp.content.decode("utf-8"))
    assert len(rows) == len(rep["table"])
    assert set(rows[0]) == {k for k, _, _ in R.csv_cols()} and any(k.startswith("lever_") for k in rows[0])
    for got, want in zip(rows, rep["table"]):
        for key, _, kind in R.csv_cols():
            w = want.get(key)
            if w is None or kind == "text" or isinstance(w, (bool, list)):
                assert got[key] == R.cell(w), key
            else:
                assert float(got[key]) == pytest.approx(float(w)), key


def _visible(html_text: str) -> str:
    html_text = re.sub(r"<style.*?</style>", " ", html_text, flags=re.S)
    import html
    return html.unescape(re.sub(r"<[^>]+>", " ", html_text))


def test_report_html_printable_and_grounded(client, season):
    rep = client.get(f"/season/{season}/report").json()
    h = client.get(f"/season/{season}/report.html")
    assert h.headers["content-type"].startswith("text/html")
    t = h.text
    for section in ("요약", "개선할 점 top 5", "잘한 결정", "운이 작용한 달", "월별 표", "데이터 한계"):
        assert f">{section}<" in t, section
    dl = rep["data_limits"]
    assert f"{dl['reviewed']}/{dl['total']}" in t
    assert "color-scheme: light" in t and "@media print" in t
    assert "size: A4 landscape" in t and "word-break: keep-all" in t and t.count("class='text wide'") >= 3
    assert not re.search(r"(src|href)=\"https?://", t), "report must be self-contained"
    vis = _visible(t)
    bad = invented(vis, pool(rep, persona.VOCAB, "0~1 top 5"))
    assert not bad, f"numbers in the HTML that are not in the report: {bad[:10]}"


QUESTIONS = ["왜 11월에 손해?", "가장 큰 실수는?", "다음 시즌엔 뭘 바꿔?", "어떤 달이 운이 좋았어?", "잘한 결정은?", "요약해 줘"]


def test_report_ask_answers_from_the_season(client, season, fresh_llm):
    rep = client.get(f"/season/{season}/report").json()
    answers = []
    for q in QUESTIONS:
        a = client.post(f"/season/{season}/report/ask", json={"question": q}).json()
        assert a["answer"] and a["backend"] == "mock"
        assert not invented(a["answer"], pool(rep, q)), a["answer"]
        answers.append(a["answer"])
        for c in a["citations"]:
            assert f"[{c}]" in a["answer"]
    assert "11월" in answers[0] and len(set(answers)) == len(answers)


def test_report_ask_rejects_invented_numbers(client, season, fresh_llm, fake_claude, monkeypatch):
    fake_claude('echo "11월에는 999만원 손해를 봤어요"')
    monkeypatch.setenv("LLM_BACKEND", "claude_cli")
    a = client.post(f"/season/{season}/report/ask", json={"question": "왜 11월에 손해?"}).json()
    assert "template used" in a["backend"] and "999" not in a["answer"]


def test_report_unknown_season(client):
    assert client.get("/season/nope/report").status_code == 404


@pytest.mark.parametrize("q,intent", [
    ("가장 큰 실수는 뭐였어?", "mistake"), ("운이 좋았던 달은?", "luck"), ("다음 시즌에 하나만 바꾼다면?", "next"),
    ("잘한 결정은?", "good"), ("왜 11월에 손해?", "why_month"), ("어떤 달이 운이 나빴어?", "luck"),
    ("운영에서 잘한 결정은?", "good"), ("다음 시즌 운영은 뭘 바꿔?", "next"), ("요약해 줘", "summary"),
    ("현금만 늘리는 선택은?", "cash_only"), ("당장 돈 되는 건 뭐였어?", "cash_only"),
])
def test_report_ask_intents(q, intent):
    """The web's preset questions (web/src/v2/report.ts PRESET_QUESTIONS) and near misses route correctly."""
    assert R._intent(q) == intent


def test_web_presets_are_covered():
    from pathlib import Path
    src = (Path(__file__).resolve().parents[1] / "web/src/v2/report.ts").read_text(encoding="utf-8")
    presets = re.findall(r'"([^"]+\?)"', src.split("PRESET_QUESTIONS", 1)[1].split("]", 1)[0])
    assert presets and len({R._intent(q) for q in presets}) == len(presets), presets


def test_luck_answer_follows_the_question():
    rep = {"summary": {}, "improvements": [], "good_decisions": [], "table": [],
           "luck_months": [{"month_label": "11월", "luck": "운이 나빴던 달", "luck_ko": "11월은 운의 몫이 컸습니다"}]}
    good, _ = R.mock_answer("운이 좋았던 달은?", rep)
    bad, cites = R.mock_answer("운이 나빴던 달은?", rep)
    assert good.startswith("운이 좋았던 달은 없었어요") and "운이 나빴던 달은 있었어요" in good
    assert bad.startswith("11월은") and cites == ["운 11월"]


def test_cash_only_section_and_answer():
    x = {"month_label": "11월", "lever": "soju_price", "lever_ko": "소주 가격", "to": 4500, "cash_delta": 5_210_000,
         "store_value_delta": -1_930_000, "tag": "근거",
         "warning_ko": "11월에 소주 가격을 4,500원으로 했다면 현금은 +521만원이지만 가게 가치는 -193만원"}
    rep = {"season_id": "t", "summary": {}, "improvements": [], "good_decisions": [], "luck_months": [], "table": [],
           "cash_only": [x], "data_limits": {}}
    page = R.to_html(rep)
    assert "현금만 늘리는 선택 (주의)" in page and x["warning_ko"] in page
    assert "현금만 늘리는 선택" not in R.to_html({**rep, "cash_only": []})
    a, cites = R.mock_answer("현금만 늘리는 선택은?", rep)
    assert x["warning_ko"] in a and cites == ["현금만 1"] and not invented(a, pool(rep))


def test_season_end_warms_the_report(client, monkeypatch):
    from api import main
    calls = []
    monkeypatch.setenv("REPORT_WARM", "1")
    monkeypatch.setattr(main.season_report, "warm", lambda sess, review: calls.append((sess["id"], review)))
    s = client.post("/season", json={"mode": "free", "seed": 11}).json()
    for k in range(6):
        st = client.get(f"/season/{s['id']}").json()["state"]
        if st.get("closed"):
            break
        client.post(f"/season/{s['id']}/play", json={"plan": {}})
        if k < 4 and not client.get(f"/season/{s['id']}").json()["state"].get("closed"):
            assert calls == [], "warm only once the season is over"
    import time
    for _ in range(50):
        if calls:
            break
        time.sleep(0.05)
    assert len(calls) == 1 and calls[0][0] == s["id"] and calls[0][1]["total"] > 0


def test_concurrent_builds_share_one_run(monkeypatch):
    import threading
    import time
    runs = []

    def slow(sess, review):
        runs.append(1)
        time.sleep(0.3)
        return {"season_id": sess["id"], "summary": {}}
    monkeypatch.setattr(R, "_build", slow)
    sess = {"id": "same-season", "months": [1, 2]}
    out = []
    ts = [threading.Thread(target=lambda: out.append(R.build(sess, {"reviewed": 0, "total": 82}))) for _ in range(3)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert len(runs) == 1 and len(out) == 3 and all(o is out[0] for o in out)


def test_uncertain_section():
    x = {"month_label": "12월", "lever_ko": "반찬 가짓수", "note_ko": "빠른 추정은 가게 가치 +40만원, 시뮬레이션 재실행은 -12만원"}
    rep = {"season_id": "t", "summary": {}, "improvements": [], "good_decisions": [], "luck_months": [], "table": [],
           "cash_only": [], "uncertain": [x], "data_limits": {}}
    assert "결과가 엇갈린 대안" in R.to_html(rep) and x["note_ko"] in R.to_html(rep)
    assert "결과가 엇갈린 대안" not in R.to_html({**rep, "uncertain": []})


def test_won_rounds_before_the_sign_and_uses_the_ui_minus():
    assert R.won(-0.4) == "0원" and R.won(-3_000) == "\u22123,000원" and R.won(-1_234_567) == "\u2212123만원"
    assert R.won(1_234_567) == "123만원" and R.signed(-1_840_000) == "184만원 적자"
