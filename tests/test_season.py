"""v2 season API + persona layer: lifecycle, persistence, no invented numbers in any generated text,
survey alignment with the interview guide and answer sheet. The real claude is never run."""
import pytest
from fastapi.testclient import TestClient

from agents import persona
from agents.numbers import invented, pool
from api import season_store

from .conftest import REPO


@pytest.fixture(scope="module")
def client(loaded):
    from api import main
    with TestClient(main.app) as c:
        yield c


def _new(client, seed=11):
    r = client.post("/season", json={"mode": "free", "seed": seed})
    assert r.status_code == 200, r.text
    return r.json()


def _play(client, sid, plan=None, events=None):
    body = {"plan": plan or {}}
    if events is not None:
        body["events"] = events
    r = client.post(f"/season/{sid}/play", json=body)
    assert r.status_code == 200, r.text
    return r.json()


def test_lifecycle_and_shapes(client, fresh_llm):
    s = _new(client)
    assert s["months_played"] == 0 and s["default_plan"] and s["engine"] in ("stub", "sim.season")
    prev = client.post(f"/season/{s['id']}/preview", json={"plan": {}}).json()
    assert prev
    m = _play(client, s["id"])
    for k in ("month", "calendar", "events", "plan", "draw", "waterfall", "state_after", "reviews", "owner_line",
              "night_events", "labels"):
        assert k in m, k
    assert m["owner_line"]["text"] and all(r.get("text") for r in m["reviews"])
    if s["engine"] == "stub":
        assert all("가정" in lab["tag"] for lab in m["labels"]), "stub numbers must be labelled"
    g = client.get(f"/season/{s['id']}").json()
    assert g["months_played"] == 1 and {k: v for k, v in g["state"].items() if k != "month_events"} == m["state_after"]
    assert g["state"]["month_events"] == m["next_month_events"]


def test_season_ends(client, fresh_llm):
    s = _new(client, seed=5)
    for _ in range(6):
        st = client.get(f"/season/{s['id']}").json()["state"]
        if st.get("closed"):
            break
        _play(client, s["id"])
    assert client.post(f"/season/{s['id']}/play", json={"plan": {}}).status_code == 409


def test_persistence_survives_restart(client, fresh_llm):
    s = _new(client, seed=21)
    m1 = _play(client, s["id"])
    season_store.forget_memory()                     # as if the API process restarted
    g = client.get(f"/season/{s['id']}").json()
    assert g["months_played"] == 1 and g["months"][0]["reviews"][0]["text"] == m1["reviews"][0]["text"]
    m2 = _play(client, s["id"])
    assert m2["month"] != m1["month"]
    season_store.forget_memory()
    assert client.get(f"/season/{s['id']}").json()["months_played"] == 2


def test_no_invented_numbers_in_month_text(client, fresh_llm):
    s = _new(client, seed=33)
    for plan in ({}, {"meat_price": 21000, "staff_per_shift": 1}, {"meat_grade": "aged", "staff_grilling": True}):
        m = _play(client, s["id"], plan=plan, events=["pork_up", "staff_quit"])
        allowed = pool(persona.VOCAB, m["owner_line"].get("runway_months"), m["owner_line"].get("net_vs_shadow"),
                       (m.get("shadow") or {}).get("kpis"), m["draw"], m["state_after"].get("cash"), m["reviews"], m["plan"], m["calendar"], m["events"],
                       m["waterfall"])
        texts = [m["owner_line"]["text"], *m["owner_line"].get("event_lines", {}).values(), *(r["text"] for r in m["reviews"])]
        for t in texts:
            assert not invented(t, allowed), f"invented {invented(t, allowed)} in: {t}"
        assert len({r["text"] for r in m["reviews"]}) >= len(m["reviews"]) - 2, "reviews should vary"


def test_ask_reviewer_and_owner_grounded(client, fresh_llm):
    s = _new(client, seed=44)
    m = _play(client, s["id"], plan={"meat_price": 21000})
    rev = m["reviews"][0]
    for q in ("얼마나 기다리셨어요?", "가격은 어땠어요?", "고기 맛은요?", "다시 오실 거예요?", "어떠셨어요?"):
        a = client.post(f"/persona/{s['id']}/ask", json={"who": rev["id"], "question": q}).json()
        assert a["grounded_in"]["id"] == rev["id"]
        assert not invented(a["answer"], pool(rev, q, persona.VOCAB, m["plan"])), a["answer"]
    o = client.post(f"/persona/{s['id']}/ask", json={"who": "owner", "question": "요즘 장사는 어떠세요?"}).json()
    assert o["who"] == "owner" and "21,000원" in o["answer"]       # quotes the season's current price
    assert client.post(f"/persona/{s['id']}/ask", json={"who": "r99-9", "question": "x"}).status_code == 404
    assert client.post("/persona/nosuchseason/ask", json={"who": "owner", "question": "x"}).status_code == 404


def test_survey_aligned_with_interview_guide(client, fresh_llm):
    s = _new(client, seed=55)
    _play(client, s["id"])
    _play(client, s["id"], plan={"staff_per_shift": 1})
    items = client.get(f"/season/{s['id']}/survey").json()["items"]
    guide, sheet = persona.guide_questions(), persona.sheet_rows()
    assert 14 <= len(items) <= 16 and [it["guide_q"] for it in items] == persona.SURVEY_Q
    for it in items:
        if it["rows"]:   # every answer fills at least one answer-sheet row of its own guide question
            assert any(r["question_no"] == it["guide_q"] for r in it["rows"]), f"Q{it['guide_q']} rows misfiled"
        assert guide[it["guide_q"]] == it["question"], "question text must match the guide verbatim"
        assert it["answer"] and it["used"], it["guide_q"]
        for r in it["rows"]:
            assert (r["criterion_id"], r["question_no"]) in sheet, f"row not in answer sheet: {r}"
        assert not invented(it["answer"], pool(it["rows"], it["used"], persona.VOCAB)), f"Q{it['guide_q']}: {it['answer']}"
    cmp = persona.compare(items, REPO / "research" / "interview" / "answer_sheet_template.csv")
    assert cmp and all(c["in_sheet"] for c in cmp) and all(c["real_typical"] is None for c in cmp)


def test_render_month_real_backend_one_call_and_number_check(client, fresh_llm, fake_claude, monkeypatch):
    s = _new(client, seed=66)
    m0 = _play(client, s["id"])
    ids = [r["id"] for r in m0["reviews"]]
    # month 2 with a fake model: we cannot know the review ids in advance, so the fake answers prose
    log = fake_claude('echo "이번 달은 999만 원 벌었어요"')
    monkeypatch.setenv("LLM_BACKEND", "claude_cli")
    m = _play(client, s["id"])
    assert "invalid output" in m["persona_backend"] and m["owner_line"]["text"]
    assert log.read_text().count("---") == 1, "exactly one model call per /play"
    assert "999" not in m["owner_line"]["text"] and all("999" not in r["text"] for r in m["reviews"])
    assert ids  # month 1 rendered on mock


def test_ask_reviewer_rejects_invented_number(client, fresh_llm, fake_claude, monkeypatch):
    s = _new(client, seed=77)
    m = _play(client, s["id"])
    rev = m["reviews"][0]
    fake_claude('echo "한 시간 반, 그러니까 95분 기다렸어요"')
    monkeypatch.setenv("LLM_BACKEND", "claude_cli")
    a = client.post(f"/persona/{s['id']}/ask", json={"who": rev["id"], "question": "얼마나 기다리셨어요?"}).json()
    assert "template used" in a["backend"] and "95" not in a["answer"]


def test_district_layer(client):
    d = client.get("/district/layer").json()
    assert len(d["stores"]) == 27 and all(x["lon"] for x in d["stores"])
    assert d["rent"]["hyehwa_vs_national"] and 2.5 < d["rent"]["hyehwa_vs_national"] < 3.5
    assert d["survival"]["study_area_hansik"]["n"] > 0 and d["survival"]["wide_pork_name_only"]["n"] > 0


def test_stub_engine_contract(client, fresh_llm, monkeypatch):
    """The API also runs on the labelled stub (fresh clones before sim.season v2 lands)."""
    from api import season_engine, season_stub
    monkeypatch.setattr(season_engine, "engine", lambda: (season_stub, "stub"))
    s = _new(client, seed=88)
    assert s["engine"] == "stub" and s["default_plan"]["meat_price"]
    m = _play(client, s["id"], events=["pork_up"])
    assert m["engine"] == "stub" and all("가정" in lab["tag"] for lab in m["labels"])
    allowed = pool(persona.VOCAB, m["owner_line"].get("runway_months"), m["owner_line"].get("net_vs_shadow"),
                       (m.get("shadow") or {}).get("kpis"), m["draw"], m["state_after"].get("cash"), m["reviews"], m["plan"], m["calendar"],
                   m["events"], m["waterfall"])
    for t in [m["owner_line"]["text"], *m["owner_line"]["event_lines"].values(), *(r["text"] for r in m["reviews"])]:
        assert not invented(t, allowed), t


def test_survey_is_fast_and_never_simulates_live(client, fresh_llm, monkeypatch):
    import time

    from api import game, main
    main._REACTIONS.clear()
    monkeypatch.setattr(game, "_live", lambda *a, **k: (_ for _ in ()).throw(AssertionError("live sim in survey")))
    s = _new(client, seed=91)
    _play(client, s["id"])
    t = time.time()
    items = client.get(f"/season/{s['id']}/survey").json()["items"]
    assert time.time() - t < 5 and len(items) == len(persona.SURVEY_Q)
    q24 = next(it for it in items if it["guide_q"] == 24)
    assert q24["rows"], "Q24 should answer from the precomputed runs"


def test_sandbox_play_never_calls_a_model(client, fresh_llm, fake_claude, monkeypatch):
    log = fake_claude('echo "{}"')
    monkeypatch.setenv("LLM_BACKEND", "claude_cli")
    s = client.post("/season", json={"mode": "sandbox", "seed": 92}).json()
    m = _play(client, s["id"])
    assert m["persona_backend"] == "template" and m["owner_line"]["text"]
    assert not log.exists(), "sandbox (shadow/compare) seasons must not spend model calls"


SENT = __import__("re").compile(r"(?<=[!?])\s+|\.\s+")


@pytest.mark.parametrize("seed,plan", [(11, {"review_event": True, "staff_per_shift": 1}),
                                       (12, {"review_event": True}), (13, {"meat_price": 22000, "meat_grade": "imported"}),
                                       (14, {"staff_per_shift": 1, "banchan": 3, "hygiene": "basic"})])
def test_month_reviews_vary_and_match_stars(client, fresh_llm, seed, plan):
    from agents import review_bank as RB
    s = _new(client, seed=seed)
    for _ in range(2):
        m = _play(client, s["id"], plan=plan)
        sents = [x.strip() for r in m["reviews"] for x in SENT.split(r["text"]) if x.strip()]
        dup = {x for x in sents if sents.count(x) > 1}
        assert not dup, f"sentences reused within the month: {dup}"
        allowed = pool(persona.VOCAB, m["owner_line"].get("runway_months"), m["owner_line"].get("net_vs_shadow"),
                       (m.get("shadow") or {}).get("kpis"), m["draw"], m["state_after"].get("cash"), m["reviews"], m["plan"], m["calendar"],
                       m["events"], m["waterfall"])
        for r in m["reviews"]:
            assert not invented(r["text"], allowed), r["text"]
            assert "이벤트" not in r["text"], "review-event status is a flag, not the text"
            if r.get("incentivized"):
                assert r.get("event_label") == "이벤트 참여"
            f = persona._facts(r, m["plan"])
            complaint_sents = {o.format(**f) for c in RB.COMPLAINT for seg in RB.MAIN.get(c, {}).values() for o in seg}
            meta = r["text_meta"]
            if r["stars"] >= 4:
                assert meta["main"] == "positive" and meta["complaints"] == 0, r
                assert not any(cs in r["text"] for cs in complaint_sents), f"complaint as main point on {r['stars']}★: {r['text']}"
                shown_neg = [c for c in r["shown_codes"] if RB.ALIASES.get(c, c) in RB.COMPLAINT]
                assert len(shown_neg) <= 1 and (r["stars"] == 4 or r.get("incentivized") or not shown_neg), r
            if r["stars"] <= 2:
                assert meta["main"] == "complaint", r



@pytest.mark.parametrize("seed,plan", [(21, {"review_event": True}), (22, {"meat_price": 22000, "staff_per_shift": 1}),
                                       (23, {"meat_grade": "aged", "meat_price": 21000})])
def test_reviewer_answers_follow_the_card(client, fresh_llm, seed, plan):
    """The answer never voices a complaint the card does not show, never contradicts 4-5 stars, and quotes the
    month's actual price."""
    import re
    s = _new(client, seed=seed)
    m = _play(client, s["id"], plan=plan)
    price = f"{m['plan']['meat_price']:,}원"
    for r in m["reviews"]:
        shown = set(r["shown_codes"])
        ans = {q: client.post(f"/persona/{s['id']}/ask", json={"who": r["id"], "question": q}).json()["answer"]
               for q in ("가격은 어땠어요?", "기다리셨어요?", "서비스는요?", "고기 맛은요?", "다시 오실 거예요?")}
        assert price in ans["가격은 어땠어요?"] and "이 가격" not in ans["가격은 어땠어요?"]
        if "price_high" not in shown:
            assert "비싸" not in ans["가격은 어땠어요?"], (r, ans)
        if not ({"slow_service", "service_slow", "understaffed"} & shown):
            assert "늦" not in ans["서비스는요?"] and "어려웠" not in ans["서비스는요?"], (r, ans)
        if "meat_bad" not in shown and "meat_poor" not in shown:
            assert "아쉬웠" not in ans["고기 맛은요?"], (r, ans)
        if r["stars"] >= 4:
            assert "다시 오진 않" not in ans["다시 오실 거예요?"] and "모르겠" not in ans["다시 오실 거예요?"]
        for q, a in ans.items():
            assert not invented(a, pool(r, q, persona.VOCAB, m["plan"])), a
            assert not re.search(r"\b0분", a), a


@pytest.mark.parametrize("stub", [False, True])
def test_month_events_drawn_once_and_shared(client, fresh_llm, monkeypatch, stub):
    """GET /season shows the coming month's events; preview, play and a shadow sandbox run use that exact list."""
    from api import season_engine, season_stub
    S, name = (season_stub, "stub") if stub else season_engine.engine()
    seen = {"preview": [], "play": []}

    class Spy:
        def __getattr__(self, k):
            return getattr(S, k)

        def preview(self, state, plan, events=None):
            seen["preview"].append(list(events or []))
            return S.preview(state, plan, events)

        def play_month(self, state, plan, events=None):
            seen["play"].append(list(events or []))
            return S.play_month(state, plan, events)

    monkeypatch.setattr(season_engine, "engine", lambda: (Spy(), name))
    for seed in range(40, 52):     # find a seed whose first month has at least one event
        s = _new(client, seed=seed)
        me = client.get(f"/season/{s['id']}").json()["state"]["month_events"]
        if me:
            break
    assert me, "no seed in range drew an event"
    for e in me:
        assert {"id", "label", "kind", "effect", "tag"} <= set(e) and e["tag"]
    ids = [e["id"] for e in me]
    for _ in range(2):    # the list is stable across repeated GETs and previews
        assert [e["id"] for e in client.get(f"/season/{s['id']}").json()["state"]["month_events"]] == ids
        client.post(f"/season/{s['id']}/preview", json={"plan": {"meat_price": 20000}})
    m = _play(client, s["id"])
    shadow = client.post("/season", json={"mode": "sandbox", "seed": s["seed"]}).json()
    sm = _play(client, shadow["id"], events=ids)                        # the web passes month_events to its shadow
    assert seen["preview"] == [ids, ids] and seen["play"][0] == ids and seen["play"][1] == ids
    assert [e["id"] for e in m["events"]] == ids == [e["id"] for e in sm["events"]] == m["events_used"]
    nxt = client.get(f"/season/{s['id']}").json()["state"]["month_events"]
    assert nxt == m["next_month_events"]


def test_demo_text_has_no_internals(client, fresh_llm):
    """Owner answers and the 트윈 인터뷰 read like a person: no mock/가상 disclaimers, HUD-style rounding,
    no raw indices or internal metric names."""
    import re
    s = _new(client, seed=61)
    for i in range(3):
        _play(client, s["id"], plan={"staff_per_shift": 1} if i == 2 else {})
    for q in ("요즘 장사는 어떠세요?", "임대료는 얼마나 부담되세요?", "손님은 주로 어떤 분들이 오세요?"):
        a = client.post(f"/persona/{s['id']}/ask", json={"who": "owner", "question": q}).json()["answer"]
        for leak in ("가상", "mock", "자료에 없는 숫자", "시뮬레이션"):
            assert leak not in a, f"{leak!r} in owner answer: {a}"
        assert not re.search(r"\d\.\d{3,}", a), f"unrounded number: {a}"
    for it in client.get(f"/season/{s['id']}/survey").json()["items"]:
        t = it["answer"]
        assert not re.search(r"\(\d+\)", t), f"raw index in Q{it['guide_q']}: {t}"
        assert not re.search(r"\d+\.\d+\s*(분|병|명)", t), f"over-precise in Q{it['guide_q']}: {t}"
        for leak in ("운영 기록", "피로도", "100 중에", "(계산)", "지수"):
            assert leak not in t, f"{leak!r} in Q{it['guide_q']}: {t}"


def test_lifespan_warms_the_embedder(loaded, monkeypatch):
    from api import main
    from rag import embed
    calls = []
    monkeypatch.setenv("RAG_EMBEDDER", "e5")

    class Fake:
        def encode(self, texts, **kw):
            calls.append(texts)
            import numpy as np
            return np.zeros((len(texts), 384), dtype="float32")
    monkeypatch.setattr(embed, "_load_e5", lambda: Fake())
    with TestClient(main.app):
        assert calls, "the embedder must be loaded during startup, before the first request"


E5 = (__import__("pathlib").Path.home() / ".cache/huggingface/hub/models--intfloat--multilingual-e5-small").exists()


@pytest.mark.skipif(not E5, reason="e5 model not downloaded")
def test_first_owner_answer_is_fast_after_startup(loaded, fresh_llm, monkeypatch):
    import time

    from api import main
    from rag import embed
    monkeypatch.setenv("RAG_EMBEDDER", "e5")
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    embed._load_e5.cache_clear()                    # cold, as on a fresh API process
    with TestClient(main.app) as c:                 # lifespan pays the model load here
        t = time.time()
        r = c.post("/chat", json={"persona": "owner", "message": "요즘 장사는 어떠세요?"})
        assert r.status_code == 200 and time.time() - t < 3, f"first answer took {time.time() - t:.1f}s"



def _mr(op, cash, closed=False, shadow=None, steps=()):
    return {"month": 1, "calendar": {"label": "1월"}, "draw": {"kpis": {"op": op}},
            "state_after": {"cash": cash, "closed": closed},
            "shadow": {"kpis": {"op": shadow}} if shadow is not None else None,
            "waterfall": [{"driver": d, "delta": v, "kind": "step"} for d, v in steps], "owner_line": {}, "events": []}


@pytest.mark.parametrize("op,cash", [(-300_000, 20_000_000), (-1_500_000, 25_000_000), (500_000, 1_000_000),
                                     (2_000_000, 30_000_000), (-100_000, 5_000_000)])
def test_long_runway_never_sounds_like_danger(op, cash):
    o = persona.owner_template(_mr(op, cash, shadow=op + 200_000, steps=[("손님 수", -400_000), ("객단가", 150_000)]))
    runway = cash / -op if op < 0 else None
    assert runway is None or runway >= 12
    assert not any(w in o["text"] for w in persona.DANGER_WORDS), o["text"]


@pytest.mark.parametrize("op,cash,closed", [(-2_000_000, -500_000, False), (-1_000_000, 0, False),
                                            (-3_000_000, 2_000_000, False), (-1_000_000, -4_000_000, True)])
def test_empty_or_closed_cash_always_sounds_like_danger(op, cash, closed):
    o = persona.owner_template(_mr(op, cash, closed=closed, shadow=0))
    assert any(w in o["text"] for w in persona.DANGER_WORDS), o["text"]
    assert o["mood"] == "desperate" or closed


def test_owner_line_agrees_with_the_sim_mood(client, fresh_llm):
    """With the real engine, the persona keeps the sim's mood and runway (the numbers the HUD shows)."""
    s = _new(client, seed=71)
    for plan in ({}, {"staff_per_shift": 4, "meat_grade": "aged", "meat_price": 16000}):
        m = _play(client, s["id"], plan=plan)
        if "runway_months" in (m.get("owner_line") or {}) and s["engine"] == "sim.season":
            o = persona.owner_state(m)
            danger = any(w in m["owner_line"]["text"] for w in persona.DANGER_WORDS)
            assert danger == (o["mood"] == "desperate" or o["closed"]), m["owner_line"]


def test_prediction_stored_and_scored(client, fresh_llm):
    s = _new(client, seed=81)
    m1 = client.post(f"/season/{s['id']}/play", json={"plan": {}, "prediction": 1_000_000}).json()
    assert m1["prediction"]["metric"] == "op" and m1["prediction"]["predicted"] == 1_000_000
    assert m1["prediction"]["actual"] == m1["draw"]["kpis"]["op"] and m1["prediction"]["scored"]
    m2 = client.post(f"/season/{s['id']}/play", json={"plan": {}, "prediction": {"covers": 900}}).json()
    assert m2["prediction"]["metric"] == "covers" and m2["prediction"]["actual"] == m2["draw"]["kpis"]["covers"]
    m3 = client.post(f"/season/{s['id']}/play", json={"plan": {}}).json()          # no guess this month
    assert m3["prediction"] is None
    season_store.forget_memory()                                                 # survives a restart
    v = client.get(f"/season/{s['id']}").json()
    p = v["predictions"]
    assert p["months_predicted"] == 2 and len(p["per_month"]) == 2
    errs = [abs(m["draw"]["kpis"][k] - g) / abs(m["draw"]["kpis"][k]) for m, k, g in ((m1, "op", 1_000_000), (m2, "covers", 900))]
    assert abs(p["mean_abs_pct_error"] - sum(errs) / 2) < 1e-3


def _engine_or_stub(monkeypatch, stub):
    from api import season_engine, season_stub
    if stub:
        monkeypatch.setattr(season_engine, "engine", lambda: (season_stub, "stub"))
        return season_stub
    S, _ = season_engine.engine()
    if not season_engine.supports_choices(S):
        pytest.skip("this sim has no in-night decisions yet")
    return S


@pytest.mark.parametrize("stub", [True, False])
def test_two_step_month_with_night_choices(client, fresh_llm, monkeypatch, stub):
    _engine_or_stub(monkeypatch, stub)
    for seed in range(1, 15):
        s = _new(client, seed=seed)
        ms = client.post(f"/season/{s['id']}/start_month", json={"plan": {}}).json()
        if ms.get("decision_points"):
            break
    dps = ms["decision_points"]
    assert dps and "draw" not in ms and "state_after" not in ms        # step 1 carries no KPIs
    for dp in dps:
        assert dp["owner_prompt"] and all(o["owner_foresight"] for o in dp["options"])
    # an unknown option is refused; a changed plan asks for a new start_month
    bad = client.post(f"/season/{s['id']}/play", json={"plan": {}, "night_choices": {dps[0]["id"]: "nope"}})
    assert bad.status_code == 422
    moved = client.post(f"/season/{s['id']}/play", json={"plan": {"meat_price": 25000},
                                                         "night_choices": {dps[0]["id"]: dps[0]["options"][0]["id"]}})
    assert moved.status_code == 409
    choices = {dp["id"]: next(o["id"] for o in dp["options"] if o["id"] != dp["default"]) for dp in dps}
    m = client.post(f"/season/{s['id']}/play", json={"plan": {}, "night_choices": choices}).json()
    got = {nd["id"]: nd["option_id"] for nd in m["night_decisions"]}
    assert got == choices
    assert set(m["owner_line"]["decision_lines"]) == set(choices)
    assert {f"dp:{k}" for k in choices} <= {w.get("key") for w in m["waterfall"]}
    allowed = pool(persona.VOCAB, m["night_decisions"], m["decision_points"], m["owner_line"].get("runway_months"),
                   m["owner_line"].get("net_vs_shadow"), (m.get("shadow") or {}).get("kpis"), m["draw"],
                   m["state_after"].get("cash"), m["reviews"], m["plan"], m["calendar"], m["events"], m["waterfall"])
    texts = [m["owner_line"]["text"], *m["owner_line"]["decision_lines"].values(), *(r["text"] for r in m["reviews"])]
    texts += [dp["owner_prompt"] for dp in dps] + [o["owner_foresight"] for dp in dps for o in dp["options"]]
    for t in texts:
        assert not invented(t, allowed), t
    if stub:   # the stub marks the affected party and the group itself
        assert "단체" in m["reviews"][0]["text"] and m["reviews"][0]["text_meta"].get("decision")
        assert "받아 주셨어요" in m["reviews"][1]["text"] or "붙여 주셨어요" in m["reviews"][1]["text"]
    for r in m["reviews"]:     # only parties the sim links to a decision mention it
        if not (r.get("cause_decisions") or r.get("decision_party")):
            assert not r["text_meta"].get("decision")


@pytest.mark.parametrize("stub", [True, False])
def test_one_step_play_still_works(client, fresh_llm, monkeypatch, stub):
    _engine_or_stub(monkeypatch, stub)
    s = _new(client, seed=3)
    m = _play(client, s["id"])
    for nd in m.get("night_decisions") or []:
        assert nd["option_id"] == nd["default"]
    m2 = _play(client, s["id"])               # no start_month in between either
    assert m2["month"] != m["month"]


@pytest.mark.parametrize("stub", [True, False])
def test_night_choices_need_start_month(client, fresh_llm, monkeypatch, stub):
    _engine_or_stub(monkeypatch, stub)
    s = _new(client, seed=2)
    r = client.post(f"/season/{s['id']}/play", json={"plan": {}, "night_choices": {"dp1-x": "y"}})
    assert r.status_code == 409 and "start_month" in r.json()["detail"]


def test_decision_aftermath_varies_across_the_season(client, fresh_llm, monkeypatch):
    """Banks of four and a season-wide 'already said' set: no aftermath line more than twice a season
    (without the set, seeds 1-8 repeat one line four times)."""
    from collections import Counter
    _engine_or_stub(monkeypatch, False)
    for seed in range(1, 9):
        s = _new(client, seed=seed)
        said = []
        for _ in range(6):
            ms = client.post(f"/season/{s['id']}/start_month", json={"plan": {}}).json()
            choices = {dp["id"]: dp["options"][0]["id"] for dp in ms.get("decision_points") or []}
            body = {"plan": {}, "night_choices": choices} if choices else {"plan": {}}
            said += list(client.post(f"/season/{s['id']}/play", json=body).json()["owner_line"].get("decision_lines", {}).values())
        assert said and max(Counter(said).values()) <= 2, (seed, said)


@pytest.mark.parametrize("stub", [False, True])
def test_fork_replays_the_same_month(client, fresh_llm, monkeypatch, stub):
    """A fork stands just before month i with the same state and events: replaying the actual plan (and night
    choices) reproduces the original month exactly; the source season is untouched."""
    _engine_or_stub(monkeypatch, stub)
    s = _new(client, seed=5)
    for plan in ({}, {"meat_price": 21000}, {}):
        _play(client, s["id"], plan)
    before = client.get(f"/season/{s['id']}").json()
    for i in (0, 1, 2):
        f = client.post(f"/season/{s['id']}/fork", json={"month_index": i})
        assert f.status_code == 200, f.text
        f = f.json()
        orig = before["months"][i]
        assert f["mode"] == "sandbox" and f["forked_from"] == {"season_id": s["id"], "month_index": i}
        assert f["months_played"] == i and [e["id"] for e in f["state"]["month_events"]] == orig["events_used"]
        body = {"plan": f["actual"]["plan"]}
        if f["actual"]["night_choices"]:
            client.post(f"/season/{f['id']}/start_month", json=body)
            body["night_choices"] = f["actual"]["night_choices"]
        m = client.post(f"/season/{f['id']}/play", json=body).json()
        assert m["draw"]["kpis"]["op"] == orig["draw"]["kpis"]["op"], i
        assert m["state_after"]["cash"] == orig["state_after"]["cash"]
        assert client.get(f"/season/{f['id']}").json()["forked_from"]["month_index"] == i   # survives a play
    after = client.get(f"/season/{s['id']}").json()
    assert after["months_played"] == 3 and after["state"]["cash"] == before["state"]["cash"]
    assert client.post(f"/season/{s['id']}/fork", json={"month_index": 3}).status_code == 200    # the open month
    assert client.post(f"/season/{s['id']}/fork", json={"month_index": 4}).status_code == 409
    assert client.post(f"/season/{s['id']}/fork", json={"month_index": 9}).status_code == 422


def test_decision_review_lines_follow_the_sim_links():
    """Own party: the decision line comes right after the opener. Touched party: the sim's flag picks the line,
    placed after the body (before the sign-off, which may be empty). A comped blogger's table is the last-resort cause. No link, no line."""
    month = {"night_decisions": [
        {"id": "dp1-blogger", "kind": "blogger", "option_id": "comp"},
        {"id": "dp1-meat_low", "kind": "meat_low", "option_id": "swap"},
        {"id": "dp1-staff_late", "kind": "staff_late", "option_id": "wait"}]}
    base = {"segment": "twenties", "party_size": 2, "wait_min": 0, "service_wait_min": 3}
    own = {**base, "id": "a", "stars": 5, "reason_codes": ["comp", "taste_good"], "decision_party": "dp1-blogger",
           "cause_decisions": ["dp1-blogger"]}
    swapped = {**base, "id": "b", "stars": 2, "reason_codes": ["meat_swapped"], "decision_party": None,
               "cause_decisions": ["dp1-blogger", "dp1-meat_low"]}
    staffed = {**base, "id": "c", "stars": 3, "reason_codes": ["understaffed"], "decision_party": None,
               "cause_decisions": ["dp1-blogger", "dp1-staff_late"]}
    plain = {**base, "id": "d", "stars": 4, "reason_codes": ["taste_good"], "decision_party": None, "cause_decisions": []}
    texts = persona.review_texts([own, swapped, staffed, plain], {"meat_price": 19000}, month)
    first_two = texts["a"].split(". ")[:2]
    assert any(x in " ".join(first_two) for x in ("초대받아", "초대로")), texts["a"]
    assert "목살만 먹었어요" in texts["b"] and not texts["b"].startswith("삼겹살 먹으러"), texts["b"]   # sign-off may be empty
    assert "혼자 뛰어다니셨어요" in texts["c"] and "촬영" not in texts["c"], texts["c"]
    assert not plain["text_meta"].get("decision") and all(r["text_meta"].get("decision") for r in (own, swapped, staffed))


def test_short_season_ends_after_its_months_with_a_report(client, fresh_llm):
    """1개월 체험 (N2 demo order): a season started with months=1 ends after one month, carries a season_end like a
    full season's last month, and its report covers that one month."""
    s = client.post("/season", json={"mode": "free", "seed": 12, "months": 1}).json()
    assert s["months_total"] == 1 and s["state"]["month_events"]
    m = _play(client, s["id"])
    if not m["state_after"]["closed"]:
        assert m["season_end"] and m["season_end"]["store_value"] == pytest.approx(
            m["season_end"]["cash"] + m["season_end"]["forward_value"])
    v = client.get(f"/season/{s['id']}").json()
    assert v["months_total"] == 1 and v["months_played"] == 1 and "month_events" not in v["state"]
    assert client.post(f"/season/{s['id']}/play", json={"plan": {}}).status_code == 409
    assert client.post(f"/season/{s['id']}/start_month", json={"plan": {}}).status_code == 409
    rep = client.get(f"/season/{s['id']}/report").json()
    assert len(rep["table"]) == 1 and rep["summary"]["months_played"] == 1
    assert all(x["store_value_delta"] > 0 for x in rep["improvements"])
    # 잘한 결정 carry their own effect (the drawer shows store_value_delta in its sign colour), never the month's 평소 대비
    assert all(g["store_value_delta"] > 0 and "cash_delta" in g for g in rep["good_decisions"]), rep["good_decisions"]
    assert client.post("/season", json={"mode": "free", "months": 0}).status_code == 422
    assert client.post("/season", json={"mode": "free", "months": 7}).status_code == 422
    full = _new(client, seed=12)
    assert full["months_total"] == 6 and "season_months" not in full["state"]


def test_runway_months_round_down_everywhere():
    """HUD (runwayMonths: floor, at least 1), the owner line and the sim's line say the same months: 7.51 = 7."""
    from sim import season as S
    month = {"month": 11, "calendar": {"label": "11월"}, "draw": {"kpis": {"op": -1_000_000}},
             "state_after": {"cash": 7_510_000}, "shadow": {"kpis": {"op": -900_000}}, "waterfall": []}
    o = persona.owner_state(month)
    assert o["mood"] == "worried" and persona.runway_shown(o["runway"]) == 7
    t = persona.owner_template(month)["text"]
    assert "7개월" in t and "8개월" not in t, t
    assert persona.runway_shown(0.4) == 1
    line = S._owner_line(-1_000_000, -900_000, 7_510_000, [], 30, [])
    assert "약 7개월" in line["text"], line["text"]
    assert not invented("이대로면 7개월 정도 버틸 수 있어요", persona._month_pool({**month, "owner_line": line}))


def test_one_declared_baseline_month(client, fresh_llm):
    """The baseline month is the sim's preview of the default plan with events=[] (October, start state, no external
    event, whatever the seed) = the 평소 anchor; the owner quotes it as 외부 사건이 없는 평소 달, never the workbook P&L
    (hero_base.yaml _pnl_base) and never a month with its drawn events (a festival October is not the baseline)."""
    import yaml
    from agents import chat
    from sim import season as S
    b = S.baseline_month()
    for seed in (0, 42, 12):
        pv = S.preview(S.new_season(seed), S.base_plan(), [], sensitivity=False)["expected"]
        assert (b["revenue"], b["op"], b["covers"]) == (pv["revenue"], pv["op"], pv["covers"]), seed
    assert round(b["op"]) == round(S._baseline()["op"]) and b["label_ko"] == "외부 사건이 없는 평소 달"
    festival = S.preview(S.new_season(0), S.base_plan(), ["festival_week"], sensitivity=False)["expected"]
    assert festival["op"] != b["op"], "a month with a drawn event must differ from the baseline"
    s = _new(client, seed=8)
    a = client.post(f"/persona/{s['id']}/ask", json={"who": "owner", "question": "한 달에 얼마나 남으세요?"}).json()
    assert "외부 사건이 없는 평소 달" in a["answer"] and chat.won(b["revenue"]) in a["answer"] and chat.won(b["op"]) in a["answer"], a["answer"]
    wb = yaml.safe_load((REPO / "research" / "hero_base.yaml").read_text(encoding="utf-8"))["_pnl_base"]
    if chat.won(wb["rev"]) != chat.won(b["revenue"]):
        assert chat.won(wb["rev"]) not in a["answer"]
    assert "sim.season.baseline_month" in a["numbers_from"]


def test_interview_drawer_labels_every_survey_key(client, fresh_llm):
    """The 트윈 인터뷰 drawer shows each `used` row in Korean (web/src/v2/Drawers.tsx USED_KO / SOURCE_KO); a key or a
    source the survey emits without a label would be dropped from the 근거 line, so every one must be mapped."""
    import re
    ts = (REPO / "web" / "src" / "v2" / "Drawers.tsx").read_text(encoding="utf-8")
    def table(name):
        body = re.search(rf"const {name}: Record<string, string> = \{{(.*?)\n\}};", ts, re.S).group(1)
        return {a or b for a, b in re.findall(r'(?:"([^"]+)"|([A-Za-z_]\w*)):\s*"', body)}
    used_ko, source_ko = table("USED_KO"), table("SOURCE_KO")
    s = _new(client, seed=17)
    for _ in range(3):
        _play(client, s["id"])
    items = client.get(f"/season/{s['id']}/survey").json()["items"]
    keys = {u["key"] for it in items for u in it["used"]}
    sources = {u["source"] for it in items for u in it["used"]}
    assert keys <= used_ko, keys - used_ko
    ids = re.compile(r"^[A-Z]{1,3}\d+$")
    unmapped = {x for x in sources if x not in source_ko and not all(ids.match(p.strip()) for p in re.split(r"[;,]", x))}
    assert not unmapped, unmapped


def test_month_well_below_usual_is_never_a_good_mood():
    """A month in the black but 125만원 below 평소 (the trial's 10월) is 걱정, never 무난/좋았/잘됐; a month a little
    below 평소 stays 선방; every amount of 1만원 or more in the owner line is said in 만원 (agents.ko.man_won)."""
    from sim import season as S
    import re
    month = {"month": 10, "calendar": {"label": "10월"}, "draw": {"kpis": {"op": 280_000}},
             "state_after": {"cash": 20_280_000}, "shadow": {"kpis": {"op": 1_530_000}},
             "waterfall": [{"driver": "손님 수", "delta": 940_000, "kind": "step"}, {"driver": "식재료비", "delta": -87_650, "kind": "step"}]}
    for line in (None, S._owner_line(280_000, 1_530_000, 20_280_000, [], 30, month["waterfall"])):
        m = {**month, **({"owner_line": line} if line else {})}
        if line:
            assert line["mood"] == "worried", line
        t = persona.owner_template(m)
        assert t["mood"] == "worried", t
        assert not re.search(r"무난|좋았|잘됐", t["text"]), t["text"]
        assert "9만원" in t["text"] and "만 원" not in t["text"] and not re.search(r"\d{1,3}(,\d{3})+원|-\d", t["text"]), t["text"]
        if line:   # a played month always carries the sim line, whose net feeds the number check
            assert not invented(t["text"], persona._month_pool(m)), t["text"]
    near = {**month, "draw": {"kpis": {"op": 1_430_000}}}
    assert persona.owner_template(near)["mood"] == "ok"
    assert S._owner_line(1_430_000, 1_530_000, 20_280_000, [], 30, [])["mood"] == "ok"


def test_preview_states_the_gap_to_the_tour_baseline(client):
    """The welcome tour ends on the baseline month's 영업이익; the very next screen (the planning board) previews this
    month with its drawn events. /preview carries vs_baseline from the same baseline_month() so the board can say
    '외부 사건이 없는 평소 달 95만원 대비 +N만원: 이번 달 <event>' instead of an unexplained jump."""
    from sim import season as S
    b = S.baseline_month()
    s = _new(client, seed=11)
    prev = client.post(f"/season/{s['id']}/preview", json={"plan": {}}).json()
    vb = prev["vs_baseline"]
    assert vb["base_op"] == b["op"] and vb["label_ko"] == b["label_ko"]
    assert abs(vb["op"] - (prev["expected"]["op"] - b["op"])) < 1
    ev = S.data()["EV"]
    assert vb["events_ko"] == [ev[e]["label"] for e in prev["events"]]
    if prev["events"]:   # a drawn event is the named cause of the gap
        assert vb["events_ko"] and vb["op"] != 0
    calm = S.preview(S.new_season(0), S.base_plan(), [], sensitivity=False)["vs_baseline"]
    assert calm == {"base_op": b["op"], "op": 0, "label_ko": b["label_ko"], "events_ko": []}, calm
