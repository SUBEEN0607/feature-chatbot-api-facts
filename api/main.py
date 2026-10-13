"""FastAPI app.  uvicorn api.main:app --reload

DATABASE_URL  sqlite:///data/twin.db (default) or postgresql://... (compose)
LLM_BACKEND   mock (default) | claude_cli | gemini      RAG_EMBEDDER  e5 (default) | hash
CORS_ORIGINS  comma-separated (default http://localhost:5173,http://127.0.0.1:5173)
RUNS_DIR      precomputed game runs (default web/public/runs/<shock>/<action>.json)
"""
from __future__ import annotations

import os
import threading
import uuid
from contextlib import asynccontextmanager, contextmanager

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import select

from agents import chat as chat_agent
from agents import guesstimate as guess
from agents import llm
from agents import owner as owner_agent
from agents.ko import ro
from db import models as M
from db.session import database_url, get_engine, init_db, session_factory
from rag.retrieve import retrieve

from . import game, sim_bridge


@asynccontextmanager
async def lifespan(_app):
    init_db(engine())
    try:   # load the RAG embedder now, not inside the first /chat (e5 takes ~9 s cold)
        from rag.embed import warm
        warm()
    except Exception as e:  # noqa: BLE001 - a missing model must not stop the API; /chat will retry the load
        print(f"embedder warm-up skipped: {type(e).__name__}: {e}")
    yield


app = FastAPI(title="Team 고깃집 digital twin API", version="0.1.0", lifespan=lifespan)
CORS_ORIGINS = [o.strip() for o in os.environ.get(
    "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if o.strip()]
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_methods=["GET", "POST"],
                   allow_headers=["Content-Type", "X-Session-Id"])


def engine():
    return get_engine(database_url())


def db():
    with session_factory(engine())() as s:
        yield s


def _row(o) -> dict:
    return {c.name: getattr(o, c.name) for c in o.__table__.columns if c.name != "embedding"}


def _hero(s) -> dict:
    return {h.criterion_id: _row(h) for h in s.scalars(select(M.HeroAttribute))}


def _llm_ctx(session_id: str | None, header: str | None) -> llm.RequestContext:
    # one RequestContext per HTTP request: the adapter allows one model call per context
    return llm.RequestContext(session_id=(session_id or header or "anon")[:64])


def _llm_errors(e: Exception):
    if isinstance(e, llm.LLMCapExceeded):
        raise HTTPException(429, str(e))
    if isinstance(e, llm.LLMRefused):
        raise HTTPException(403, str(e))
    if isinstance(e, llm.LLMBackendError):
        raise HTTPException(502, str(e))
    raise e


@app.get("/health")
def health(s=Depends(db)):
    """backend lets the web hide free-text questions when answers are mock templates."""
    from sqlalchemy import func
    cache = llm.cache_dir()
    return {"ok": True, "db": engine().dialect.name, "backend": os.environ.get("LLM_BACKEND", "mock"),
            "rag_chunks": s.scalar(select(func.count()).select_from(M.DocChunk)),
            "cache_entries": len(list(cache.glob("*.json"))) if cache.exists() else 0}


@app.get("/ontology")
def ontology(s=Depends(db)):
    hero = _hero(s)
    nodes = []
    for c in s.scalars(select(M.Criterion)):
        n = _row(c)
        h = hero.get(c.criterion_id)
        n["value"] = {k: h[k] for k in ("low", "base", "high", "unit", "method", "confidence", "source_id",
                                        "filled_by", "reviewed_by")} if h else None
        nodes.append(n)
    edges = [_row(e) for e in s.scalars(select(M.CriterionEdge))]
    return {"nodes": nodes, "edges": edges}


@app.get("/sources")
def sources(s=Depends(db)):
    return [_row(x) for x in s.scalars(select(M.Source).order_by(M.Source.source_id))]


@app.get("/shocks")
def shocks(s=Depends(db)):
    return [_row(x) for x in s.scalars(select(M.Shock).order_by(M.Shock.shock_id))]


@app.get("/district")
def district(trdar: str = "3120012", include_context: bool = False, s=Depends(db)):
    d = s.get(M.District, trdar)
    if d is None:
        raise HTTPException(404, f"상권 {trdar} not loaded")
    qs = [_row(q) for q in s.scalars(select(M.DistrictQuarter).where(M.DistrictQuarter.trdar_code == trdar)
                                     .order_by(M.DistrictQuarter.quarter))]
    st = select(M.Store).where(M.Store.trdar_code == trdar)
    if not include_context:
        st = st.where(M.Store.role.in_(["primary", "comparison"]))
    stores = [_row(x) for x in s.scalars(st.order_by(M.Store.role.desc(), M.Store.name))]
    ind = s.get(M.Industry, d.industry_id) if d.industry_id else None
    meta = (ind.meta or {}) if ind else {}
    return {"district": _row(d), "quarters": qs, "stores": stores, "survival": meta.get("survival"),
            "survival_scope": meta.get("survival_scope", "narrow"), "survival_wide": meta.get("survival_wide")}


@app.get("/hero")
def hero(s=Depends(db)):
    sc = s.get(M.Scenario, "hero_base")
    return {"attributes": list(_hero(s).values()), "pnl": (sc.params or {}).get("pnl_base") if sc else None,
            "meta": (sc.params or {}).get("meta") if sc else None}


@app.get("/runs")
def runs_index():
    """Precomputed game runs (sim.precompute writes web/public/runs/<shock>/<action>.json)."""
    return game.run_index()


@app.get("/runs/{shock}/{action}")
def runs_get(shock: str, action: str):
    try:
        r = game.load_run(shock, action)
    except ValueError:
        raise HTTPException(422, "shock and action ids are [A-Za-z0-9_-]")
    if r is None:
        raise HTTPException(404, f"no precomputed run {shock}/{action}; POST /simulate computes it live")
    return r


class SimulateIn(BaseModel):
    shock_id: str
    action: str | None = None              # owner action from sim/owner_actions.MENU
    action_args: dict | None = None        # omitted -> moderate defaults inside the menu bounds
    runs: int = Field(200, ge=1, le=1000)
    seed: int = 42
    owner_reaction: bool = False           # let the owner agent pick the action (one LLM call)
    session_id: str | None = None


def _persist_run(s, shock_id, runs, seed, kpis, owner_action, events=None) -> str:
    run_id = uuid.uuid4().hex[:16]
    s.add(M.SimRun(run_id=run_id, scenario_id="hero_base" if s.get(M.Scenario, "hero_base") else None,
                   shock_id=shock_id if s.get(M.Shock, shock_id) else None, runs=runs, seed=seed, status="done",
                   owner_action=owner_action, meta=kpis.get("meta")))
    s.flush()
    for variant, key in (("base", "base"), ("shock", "shocked"), ("reaction", "reacted")):
        for k, v in (kpis.get(key) or {}).items():
            if isinstance(v, dict):
                s.add(M.SimKpi(run_id=run_id, variant=variant, kpi=k, p10=v.get("p10"), p50=v.get("p50"),
                               p90=v.get("p90")))
    for variant, key in (("base", "base"), ("shock", "shocked")):
        for i, e in enumerate(((events or {}).get(key) or {}).get("events", [])):
            s.add(M.SimEvent(run_id=run_id, variant=variant, seq=i, t_min=e.get("t"), event_type=e.get("type"),
                             party_id=e.get("party"), table_id=e.get("table_id"), payload=e))
    s.commit()
    return run_id


@app.post("/simulate")
def simulate(body: SimulateIn, s=Depends(db), x_session_id: str | None = Header(None)):
    if body.action:
        try:
            kpis = sim_bridge.run_action(body.shock_id, body.action, body.action_args, body.runs, body.seed)
        except sim_bridge.SimUnavailable as e:
            raise HTTPException(501, f"Simulation not available yet: {e}")
        except KeyError:
            raise HTTPException(404, f"unknown shock {body.shock_id}")
        except (ValueError, TypeError) as e:
            raise HTTPException(422, str(e))
        run_id = _persist_run(s, body.shock_id, body.runs, body.seed, kpis, kpis.get("action"))
        return {"run_id": run_id, "kpis": kpis, "owner_reaction": None}

    try:
        res = sim_bridge.simulate(body.shock_id, body.runs, body.seed)
    except sim_bridge.SimUnavailable as e:
        raise HTTPException(501, f"Simulation not available yet: {e}")
    except KeyError:
        raise HTTPException(404, f"unknown shock {body.shock_id}")
    kpis = res["kpis"]
    reaction = None
    if body.owner_reaction:
        hits = retrieve(f"{body.shock_id} 충격 대응 원가 가격 인건비", k=4, engine=engine())
        try:
            reaction = owner_agent.decide(_llm_ctx(body.session_id, x_session_id), _hero(s), hits,
                                          shock=kpis.get("shock"), sim_result={
                                              "base_p50": {k: v["p50"] for k, v in kpis["base"].items()},
                                              "shocked_p50": {k: v["p50"] for k, v in kpis["shocked"].items()}})
        except (llm.LLMGuardError, llm.LLMBackendError) as e:
            _llm_errors(e)
        try:
            kpis["reacted"] = sim_bridge.simulate_reaction(body.shock_id, reaction["action"], reaction["args"],
                                                           body.runs, body.seed)
        except (sim_bridge.SimUnavailable, ValueError, TypeError) as e:
            reaction["kpis_error"] = str(e)
    run_id = _persist_run(s, body.shock_id, body.runs, body.seed, kpis, reaction, res.get("events"))
    ev = res.get("events") or {}
    return {"run_id": run_id, "kpis": kpis, "owner_reaction": reaction,
            "events": {v: len((ev.get(k) or {}).get("events", [])) for v, k in (("base", "base"), ("shock", "shocked"))}}


@app.get("/simulate/{run_id}/events")
def sim_events(run_id: str, variant: str = Query("base", pattern="^(base|shock)$"), s=Depends(db)):
    rows = s.scalars(select(M.SimEvent).where(M.SimEvent.run_id == run_id, M.SimEvent.variant == variant)
                     .order_by(M.SimEvent.seq))
    return [r.payload for r in rows]


def _shock_note(s, shock_id: str | None, action: str | None) -> str:
    parts = []
    if shock_id:
        sh = s.get(M.Shock, shock_id)
        label = game.shock_label(shock_id, sh.name_ko if sh else None)
        parts.append(f"'{label}' ({sh.mechanism})" if sh and sh.mechanism else f"'{label}'")
    if action:
        spec = owner_agent.action_menu().get(action, {})
        label = spec.get("label") or spec.get("description_ko") or action
        parts.append(f"사장님은 '{label}'{ro(label)[len(label):]} 대응하는 중")
    return ", ".join(parts)


def _sim_context(shock_id: str | None, action: str | None) -> tuple[dict | None, str | None]:
    """before/after p50 for the chat; None when no shock is given or the sim is unavailable."""
    if not shock_id:
        return None, None
    try:
        run, src = game.get_run(shock_id, action or "absorb")
    except (sim_bridge.SimUnavailable, KeyError, ValueError):
        return None, None
    after = game.outcome(run) or {}
    base = run.get("base") or {}
    return ({"before": {k: game.p50(base, k) for k in chat_agent.SIM_KPIS},
             "after": {k: game.p50(after, k) for k in chat_agent.SIM_KPIS}},
            f"sim {shock_id}/{action or 'absorb'} ({src})")


# Persona answers are grounded in evidence only: research reports and notes, the source list and the data
# docs; not setup, task or architecture pages.
EVIDENCE_DOCS = ("rag/corpus/", "research/", "ontology/sources.csv", "docs/DATA.md", "docs/RESEARCH.md")


_DISTRICT: dict[str, dict] = {}


def _chat_district(s, trdar: str = "3120012") -> dict:
    """District facts the owner chat may quote: pork-grill store count and survival (data/processed, as loaded) plus
    the rent benchmarks of the district layer (industry meta BM42/BM44). Computed once per process."""
    if trdar not in _DISTRICT:
        from agents.store_facts import default_district
        out = dict(default_district())
        d = s.get(M.District, trdar)
        ind = s.get(M.Industry, d.industry_id) if d is not None and d.industry_id else None
        bm = {b["bench_id"]: b for b in ((ind.meta or {}).get("benchmarks") or [])} if ind else {}
        if bm.get("BM42", {}).get("value") and bm.get("BM44", {}).get("value"):
            out["rent"] = {"hyehwa_per_m2": bm["BM42"]["value"], "national_per_m2": bm["BM44"]["value"]}
        _DISTRICT[trdar] = out
    return _DISTRICT[trdar]


def chat_inputs(s, message: str, shock: str | None, action: str | None, k: int = 5) -> dict:
    """Everything /chat feeds the persona prompt (shared with agents/prewarm.py so cache keys match)."""
    sim, sim_src = _sim_context(shock, action)
    return {"hits": retrieve(message, k=k, engine=engine(), doc_prefixes=EVIDENCE_DOCS), "hero": _with_baseline(_hero(s)),
            "sim": sim, "note": _shock_note(s, shock, action), "district": _chat_district(s),
            "numbers_from": ["research/hero_base.yaml", "sim.season.baseline_month"] + ([sim_src] if sim_src else [])}


class ChatContext(BaseModel):
    shock: str | None = None
    action: str | None = None


class ChatIn(BaseModel):
    persona: str
    message: str = Field(..., min_length=1, max_length=2000)
    context: ChatContext | None = None
    session_id: str | None = None
    k: int = Field(5, ge=1, le=10)


@app.post("/chat")
def chat(body: ChatIn, s=Depends(db), x_session_id: str | None = Header(None)):
    if body.persona not in chat_agent.PERSONAS:
        raise HTTPException(422, f"unknown persona; choose from {sorted(chat_agent.PERSONAS)}")
    c = body.context or ChatContext()
    for v in (c.shock, c.action):
        if v is not None and not game.SAFE.match(v):
            raise HTTPException(422, "context ids are [A-Za-z0-9_-]")
    inp = chat_inputs(s, body.message, c.shock, c.action, body.k)
    try:
        return chat_agent.answer(_llm_ctx(body.session_id, x_session_id), body.persona, body.message,
                                 inp["hits"], inp["hero"], sim=inp["sim"], context_note=inp["note"],
                                 numbers_from=inp["numbers_from"], district=inp["district"])
    except (llm.LLMGuardError, llm.LLMBackendError) as e:
        _llm_errors(e)


class DecideIn(BaseModel):
    shock_id: str = Field(..., pattern="^[A-Za-z0-9_-]{1,40}$")
    allow_low_confidence: bool = False   # include actions whose benefit rests on confidence-L mechanisms
    session_id: str | None = None


@app.post("/owner/decide")
def owner_decide(body: DecideIn, s=Depends(db), x_session_id: str | None = Header(None)):
    """The owner agent picks one menu action for a shock. Mock backend: highest p50 OP (rule).
    Actions whose benefit relies on a confidence-L mechanism are excluded (and listed with the reason)
    unless allow_low_confidence=true."""
    shock = s.get(M.Shock, body.shock_id)
    if shock is None:
        raise HTTPException(404, f"unknown shock {body.shock_id}")
    try:
        cands = game.candidates(body.shock_id, owner_agent.action_menu())
    except sim_bridge.SimUnavailable as e:
        raise HTTPException(501, f"Simulation not available yet: {e}")
    hits = retrieve(f"{shock.driver} {shock.mechanism} 대응", k=4, engine=engine())
    try:
        d = owner_agent.decide_from_candidates(_llm_ctx(body.session_id, x_session_id), _hero(s), hits,
                                               {"id": shock.shock_id, "driver": shock.driver,
                                                "mechanism": shock.mechanism}, cands,
                                               allow_low_confidence=body.allow_low_confidence)
    except (llm.LLMGuardError, llm.LLMBackendError) as e:
        _llm_errors(e)
    return {"shock_id": body.shock_id, **d}


@app.get("/review/drafts")
def review_drafts():
    """AI guesstimate drafts awaiting member review (research/review/ai_drafts.csv)."""
    rows = guess.read_drafts()
    accepted = guess.reviewed_rows(rows)
    return {"path": "research/review/ai_drafts.csv", "rows": rows,
            "counts": {"drafts": len(rows), "reviewed": sum(bool((r.get("reviewed_by") or "").strip()) for r in rows),
                       "accepted": len(accepted)}}


@app.post("/review/drafts/{criterion_id}")
def review_draft_one(criterion_id: str, x_session_id: str | None = Header(None)):
    """Draft ONE criterion with the configured backend (one LLM call) and upsert it into ai_drafts.csv."""
    if not game.SAFE.match(criterion_id):
        raise HTTPException(422, "criterion ids are [A-Za-z0-9_-]")
    try:
        row = guess.draft_one(criterion_id, _llm_ctx(None, x_session_id))
    except KeyError:
        raise HTTPException(404, f"unknown criterion {criterion_id}")
    except (llm.LLMGuardError, llm.LLMBackendError) as e:
        _llm_errors(e)
    guess.upsert([row])
    return row


# ---------------------------------------------------------------------------------------------------
# v2 season (docs/GAME-V2-SPEC.md §11) and persona layer (§8)
# ---------------------------------------------------------------------------------------------------

from agents import persona  # noqa: E402

from . import season_engine, season_store  # noqa: E402

SEASON_MONTHS = 6


class SeasonIn(BaseModel):
    mode: str = Field("free", pattern="^(guided|free|sandbox)$")
    seed: int | None = Field(None, ge=0, le=2**31 - 1)
    months: int = Field(SEASON_MONTHS, ge=1, le=SEASON_MONTHS)   # a short season (1개월 체험) ends, and reports, early


class PlanIn(BaseModel):
    plan: dict = Field(default_factory=dict)
    events: list[str] | None = None      # guided/sandbox scripts pass events; free play draws them
    prediction: float | dict | None = None   # the player's guess before the reveal (client-side); stored with the month
    night_choices: dict[str, str] | None = None   # {decision point id: option id} from /start_month (§12.1)
    month_index: int | None = Field(None, ge=0)   # optional: the month (0-based, = months_played) this request is for; a
                                                  # mismatch is refused (409), a repeat of a played month returns it again
    session_id: str | None = None


PREDICTABLE = ("op", "revenue", "covers", "walkaways", "rating")


def _prediction_record(pred, result: dict) -> dict | None:
    """Normalise the player's guess and score it against what happened. Accepts a bare number (= operating
    profit), {metric: value} for any of PREDICTABLE, or {metric, value}."""
    if pred is None:
        return None
    if isinstance(pred, (int, float)):
        metric, value = "op", float(pred)
    elif isinstance(pred, dict) and "metric" in pred and "value" in pred:
        metric, value = str(pred["metric"]), pred["value"]
    elif isinstance(pred, dict) and len(pred) == 1:
        (metric, value), = pred.items()
    else:
        return {"raw": pred, "scored": False}
    kpis = (result.get("draw") or {}).get("kpis") or {}
    actual = (result.get("state_after") or {}).get("rating") if metric == "rating" else kpis.get(metric)
    rec = {"metric": metric, "predicted": value, "actual": actual, "raw": pred, "scored": False}
    if isinstance(value, (int, float)) and isinstance(actual, (int, float)):
        rec.update(scored=True, error=actual - value,
                   abs_pct_error=round(abs(actual - value) / abs(actual), 4) if actual else None)
    return rec


def _prediction_summary(months: list[dict]) -> dict:
    recs = [m.get("prediction") for m in months if (m.get("prediction") or {}).get("scored")]
    if not recs:
        return {"months_predicted": 0}
    pct = [r["abs_pct_error"] for r in recs if r.get("abs_pct_error") is not None]
    return {"months_predicted": len(recs), "mean_abs_pct_error": round(sum(pct) / len(pct), 4) if pct else None,
            "within_10pct": sum(1 for x in pct if x <= 0.10), "per_month": [
                {"month": m.get("month"), **{k: m["prediction"].get(k) for k in ("metric", "predicted", "actual", "abs_pct_error")}}
                for m in months if (m.get("prediction") or {}).get("scored")]}


class AskIn(BaseModel):
    who: str = Field(..., pattern="^(owner|[A-Za-z0-9_-]{1,40})$")   # "owner" or a review id
    question: str = Field(..., min_length=1, max_length=500)
    session_id: str | None = None


def _season(season_id: str) -> dict:
    if not game.SAFE.match(season_id):
        raise HTTPException(422, "bad season id")
    sess = season_store.get(engine(), season_id)
    if sess is None:
        raise HTTPException(404, f"no season {season_id}")
    return sess


_season_locks: dict[str, threading.Lock] = {}
_season_locks_guard = threading.Lock()


@contextmanager
def _season_lock(season_id: str):
    """One request at a time per season for every endpoint that reads then writes it (play, start_month, preview's
    event draw, fork's source). The handlers are sync, so they run on a thread pool, and the web client's shadow play
    does not wait for the previous one: without this two /play read the same state and both append that month."""
    with _season_locks_guard:
        lock = _season_locks.setdefault(season_id, threading.Lock())
    with lock:
        yield


def _check_month(sess: dict, body: PlanIn) -> dict | None:
    """month_index sent and not the open month: the stored result when it repeats a played month (a retry after a
    timeout, a double click), else 409 with months_played so the client can resync. None = go ahead."""
    played = len(sess["months"])
    i = body.month_index
    if i is None or i == played:
        return None
    prior = sess["months"][i] if i < played else None
    if prior is not None and (body.events is None or list(body.events) == list(prior.get("events_used") or [])) \
            and all((prior.get("plan") or {}).get(k) == v for k, v in body.plan.items()):
        return prior
    raise HTTPException(409, {"error": "month_mismatch", "month_index": i, "months_played": played})


API_STATE_KEYS = ("month_events", "pending_start", "forked_from", "season_months")   # API-side keys kept in the session state, never sent to the sim


def _total(sess: dict) -> int:
    """Months in this season: SEASON_MONTHS unless it was started short (POST /season months)."""
    return int((sess["state"] or {}).get("season_months") or SEASON_MONTHS)


def _over(sess: dict) -> bool:
    return bool((sess["state"] or {}).get("closed")) or len(sess["months"]) >= _total(sess)


def _sim_state(S, st: dict):
    return season_engine.from_json(S, {k: v for k, v in (st or {}).items() if k not in API_STATE_KEYS})


def _open_month(S, sess: dict) -> list[str]:
    """Events of the month about to be played: drawn ONCE when the month opens (from the state after last month)
    and stored as state.month_events, so GET /season, preview, play and a shadow run all see the same list."""
    st = sess["state"] or {}
    if _over(sess):
        st.pop("month_events", None)
        return []
    if st.get("month_events") is None:
        ids = season_engine.draw_events(S, _sim_state(S, st))
        st["month_events"] = [season_engine.event_info(S, e) for e in ids]
        sess["state"] = st
    return [e["id"] for e in st["month_events"]]


def _season_view(sess: dict) -> dict:
    return {"id": sess["id"], "mode": sess["mode"], "seed": sess["seed"], "engine": sess["engine"],
            "state": sess["state"], "months": sess["months"], "months_played": len(sess["months"]),
            "months_total": _total(sess), "predictions": _prediction_summary(sess["months"]),
            "forked_from": (sess["state"] or {}).get("forked_from")}


@app.post("/season")
def season_new(body: SeasonIn):
    import random
    S, name = season_engine.engine()
    seed = body.seed if body.seed is not None else random.randrange(1, 2**31 - 1)
    state = season_engine.to_json(S.new_season(seed, body.mode))
    if body.months != SEASON_MONTHS:
        state["season_months"] = body.months
    sess = season_store.create(engine(), body.mode, seed, name, state)
    _open_month(S, sess)
    season_store.update(engine(), sess)
    return {**_season_view(sess), "default_plan": season_engine.default_plan(S)}


class ForkIn(BaseModel):
    month_index: int = Field(..., ge=0, le=SEASON_MONTHS - 1)


@app.post("/season/{season_id}/fork")
def season_fork(season_id: str, body: ForkIn):
    with _season_lock(season_id):
        return _season_fork(season_id, body)


def _season_fork(season_id: str, body: ForkIn):
    """A sandbox copy of a season standing just before month `month_index` (0-based): the state before that month,
    the months already played before it, and the SAME month events. Used by the compare view to replay the actual
    plan and an alternative from one point. Sandbox = templates only, never a model call. The source is untouched."""
    src = _season(season_id)
    i = body.month_index
    if i > len(src["months"]):
        raise HTTPException(409, f"month {i} is not reached yet ({len(src['months'])} played)")
    S, name = season_engine.engine()
    if i == len(src["months"]):                      # the month that is open right now
        if _over(src):
            raise HTTPException(409, "season is over; fork a month that was played")
        _open_month(S, src)
        state = {k: v for k, v in (src["state"] or {}).items() if k not in API_STATE_KEYS}
        events = [e["id"] for e in src["state"]["month_events"]]
    else:
        prev = src["months"][i - 1]["state_after"] if i else season_engine.to_json(S.new_season(src["seed"], src["mode"]))
        state = {k: v for k, v in dict(prev).items() if k not in API_STATE_KEYS}
        events = list(src["months"][i].get("events_used") or [])
    state["month_events"] = [season_engine.event_info(S, e) for e in events]
    state["forked_from"] = {"season_id": season_id, "month_index": i}
    sess = season_store.create(engine(), "sandbox", src["seed"], name, state)
    sess["months"] = [dict(m) for m in src["months"][:i]]
    season_store.update(engine(), sess)
    played = src["months"][i] if i < len(src["months"]) else None
    return {**_season_view(sess), "default_plan": season_engine.default_plan(S),
            "actual": played and {"plan": played.get("plan"),
                                  "night_choices": {d["id"]: d["option_id"] for d in played.get("night_decisions") or []}}}


@app.get("/season/{season_id}")
def season_get(season_id: str):
    return _season_view(_season(season_id))


def _plan(S, sess: dict, plan: dict) -> dict:
    current = (sess["state"] or {}).get("plan") or season_engine.default_plan(S)
    return {**current, **plan}


@app.post("/season/{season_id}/preview")
def season_preview(season_id: str, body: PlanIn):
    with _season_lock(season_id):
        return _season_preview(season_id, body)


def _season_preview(season_id: str, body: PlanIn):
    sess = _season(season_id)
    S, _ = season_engine.engine()
    events = body.events if body.events is not None else _open_month(S, sess)
    try:
        out = season_engine.to_json(S.preview(_sim_state(S, sess["state"]), _plan(S, sess, body.plan), events))
        out["events_used"] = list(events)
        return out
    except (ValueError, KeyError, TypeError) as e:
        raise HTTPException(422, f"invalid plan: {e}")


@app.post("/season/{season_id}/start_month")
def season_start_month(season_id: str, body: PlanIn):
    with _season_lock(season_id):
        return _season_start_month(season_id, body)


def _season_start_month(season_id: str, body: PlanIn):
    """Step 1 of a two-step month (§12.1): the night up to its decision points, with the owner's voice on each
    prompt and option. No KPIs. Step 2 is /play with night_choices; /play without choices still works."""
    sess = _season(season_id)
    if _check_month(sess, body) is not None:     # a month already played: nothing to start
        raise HTTPException(409, {"error": "month_mismatch", "month_index": body.month_index, "months_played": len(sess["months"])})
    st = sess["state"] or {}
    if _over(sess):
        raise HTTPException(409, "season is over (closed or all months played)")
    S, _ = season_engine.engine()
    if not callable(getattr(S, "start_month", None)):
        raise HTTPException(501, "this engine has no in-night decisions yet")
    events = body.events if body.events is not None else _open_month(S, sess)
    plan = _plan(S, sess, body.plan)
    try:
        ms = season_engine.to_json(S.start_month(_sim_state(S, st), plan, events))
    except (ValueError, KeyError, TypeError) as e:
        raise HTTPException(422, f"invalid plan or events: {e}")
    persona.decision_prompt_lines(ms)
    sess["state"]["pending_start"] = {"plan": plan, "events": list(events),
                                      "decision_points": ms.get("decision_points") or []}
    season_store.update(engine(), sess)
    ms["events_used"] = list(events)
    return ms


@app.post("/season/{season_id}/play")
def season_play(season_id: str, body: PlanIn, x_session_id: str | None = Header(None)):
    with _season_lock(season_id):
        return _season_play(season_id, body, x_session_id)


def _season_play(season_id: str, body: PlanIn, x_session_id: str | None):
    """Play one month. Persona text (owner line, event lines, review texts) is added with at most ONE LLM call
    on a real backend (templates on mock, in sandbox mode, or when the model output fails the number check)."""
    sess = _season(season_id)
    prior = _check_month(sess, body)
    if prior is not None:
        return {**prior, "replayed": True}
    st = sess["state"] or {}
    if _over(sess):
        raise HTTPException(409, "season is over (closed or all months played)")
    S, _ = season_engine.engine()
    events = body.events if body.events is not None else _open_month(S, sess)
    state = _sim_state(S, st)
    plan = _plan(S, sess, body.plan)
    kw = {}
    if body.night_choices:
        if not season_engine.supports_choices(S):
            raise HTTPException(422, "this engine has no in-night decisions; play without night_choices")
        pend = st.get("pending_start")
        if not pend:
            raise HTTPException(409, "night_choices need this month's /start_month first")
        known = {dp["id"]: {o["id"] for o in dp.get("options") or []} for dp in pend.get("decision_points") or []}
        for dp_id, opt in body.night_choices.items():
            if dp_id not in known or opt not in known[dp_id]:
                raise HTTPException(422, f"unknown decision {dp_id}={opt}; use the ids from /start_month")
        if pend.get("plan") and pend["plan"] != plan:
            raise HTTPException(409, "plan changed since /start_month; call /start_month again")
        kw["night_choices"] = dict(body.night_choices)
    elif season_engine.supports_choices(S):
        kw["night_choices"] = {}           # one-step play: every decision takes its default option
    try:
        result = season_engine.to_json(S.play_month(state, plan, events, **kw))
    except (ValueError, KeyError, TypeError) as e:
        raise HTTPException(422, f"invalid plan, events or choices: {e}")
    said = {line for m in sess["months"] for line in ((m.get("owner_line") or {}).get("decision_lines") or {}).values()}
    if sess["mode"] == "sandbox":
        persona.render_month(result, None, said)    # shadow / compare seasons: templates only, never a model call
    else:
        try:
            persona.render_month(result, _llm_ctx(body.session_id, x_session_id), said)
        except (llm.LLMGuardError, llm.LLMBackendError):
            persona.render_month(result, None, said)  # caps or backend trouble never block a month
    sess["state"] = dict(result.get("state_after", st))
    for k in API_STATE_KEYS:
        sess["state"].pop(k, None)
    for k in ("forked_from", "season_months"):
        if st.get(k):
            sess["state"][k] = st[k]
    sess["months"] = sess["months"] + [result]
    if _over(sess) and not result.get("season_end") and callable(getattr(S, "season_value", None)):
        result["season_end"] = season_engine.to_json(S.season_value(result["state_after"]))   # a short season ends here
    result["events_used"] = list(events)
    result["prediction"] = _prediction_record(body.prediction, result)
    _open_month(S, sess)                        # next month's events, drawn now from the new state
    result["next_month_events"] = (sess["state"] or {}).get("month_events", [])
    season_store.update(engine(), sess)
    if _over(sess):
        _warm_report(sess)                      # the end screen's report is ready by the time it is asked for
    return result


def _warm_report(sess: dict) -> None:
    """Season over: build the report in a daemon thread (sim.report.warm runs the DES re-scoring, about 4 s).
    REPORT_WARM=0 turns it off (tests). A GET arriving meanwhile waits for this build instead of repeating it."""
    if os.environ.get("REPORT_WARM", "1") == "0":
        return
    with session_factory(engine())() as s:
        review = _review_counts(s)
    threading.Thread(target=season_report.warm, args=(sess, review), daemon=True, name=f"report-warm-{sess['id']}").start()


def _owner_note(sess: dict) -> str:
    """The season so far in the owner's words (used as the chat's situation line)."""
    if not sess["months"]:
        return "이번 시즌은 이제 막 시작했어요."
    m = sess["months"][-1]
    k = m.get("draw", {}).get("kpis", {})
    st = sess["state"] or {}
    label = (m.get("calendar") or {}).get("label", "지난달")
    parts = []
    if k.get("op") is not None:
        parts.append(f"{label}은 {persona.won(abs(k['op']))} 적자였어요" if k["op"] < 0
                     else f"{label}은 {persona.won(k['op'])} 남았어요")
    if st.get("cash") is not None:
        parts.append(f"운영자금은 {persona.won(st['cash'])} 남아 있어요")
    if st.get("rating") is not None:
        parts.append(f"평점은 {float(st['rating']):.2f}이에요")      # like the HUD: 4.22, never 4.2162
    ev = [e.get("label", e.get("id")) if isinstance(e, dict) else str(e) for e in m.get("events") or []]
    text = ". ".join(parts) + "."
    if ev:
        text += f" {', '.join(ev)} 때문에 신경이 많이 쓰였어요."
    return text


def _season_facts(sess: dict) -> dict | None:
    """The month just played, for the owner chat's 시즌 기록 facts (None before the first month)."""
    if not sess["months"]:
        return None
    m = sess["months"][-1]
    k = (m.get("draw") or {}).get("kpis") or {}
    st = sess["state"] or {}
    return {"label": (m.get("calendar") or {}).get("label", "지난달"), "op": k.get("op"), "revenue": k.get("revenue"),
            "covers": k.get("covers"), "cash": st.get("cash"), "rating": st.get("rating")}


# monthly P&L facts the owner may quote: the declared baseline month (sim.season.baseline_month, 외부 사건이 없는 평소 달), never
# the workbook P&L, so the chat says the same 평소 numbers as the game (agents/store_facts.py builds the chat's facts from it)
BASELINE_FACTS = {"drv_revenue": "revenue", "drv_operating_profit": "op", "drv_food_cost": "cogs", "drv_labor_cost": "labor"}


def _with_baseline(hero: dict) -> dict:
    S, _ = season_engine.engine()
    if not callable(getattr(S, "baseline_month", None)):
        return hero
    b = S.baseline_month()
    h = {k: dict(v) for k, v in hero.items()}
    for cid, key in BASELINE_FACTS.items():
        if cid in h and b.get(key) is not None:
            h[cid]["base_num"], h[cid]["base"] = b[key], str(round(b[key]))
    return h


def _season_hero(hero: dict, sess: dict) -> dict:
    """Hero attributes with the season's current plan on top (the owner quotes the prices he charges now) and the
    declared baseline month for the monthly P&L facts."""
    plan = (sess["state"] or {}).get("plan") or {}
    h = _with_baseline(hero)
    for cid, key in (("prd_meat_price", "meat_price"), ("prd_alcohol_price", "soju_price"),
                     ("sto_parttimers", "staff_per_shift")):
        if key in plan and cid in h:
            h[cid]["base_num"], h[cid]["base"] = plan[key], str(plan[key])
    return h


def _citations(s, cites: list[dict]) -> list[dict]:
    """One row per source the answer drew on (the drawer lists them under the answer): the id the answer cites in
    brackets, and the title from the source table (or the document's own title for a research note)."""
    ids = {c["source_id"] for c in cites if c.get("source_id")}
    titles = {x.source_id: x.title for x in s.scalars(select(M.Source).where(M.Source.source_id.in_(ids)))} if ids else {}
    out, seen = [], set()
    for c in cites:
        label = c.get("label") or c.get("source_id") or c["doc_id"]
        if label in seen:
            continue
        seen.add(label)
        out.append({**c, "label": label, "title": titles.get(c.get("source_id")) or c.get("title") or label})
    return out


@app.post("/persona/{season_id}/ask")
def persona_ask(season_id: str, body: AskIn, s=Depends(db), x_session_id: str | None = Header(None)):
    sess = _season(season_id)
    ctx = _llm_ctx(body.session_id, x_session_id)
    try:
        if body.who == "owner":
            hits = retrieve(body.question, k=5, engine=engine(), doc_prefixes=EVIDENCE_DOCS)
            out = chat_agent.answer(ctx, "owner", body.question, hits, _season_hero(_hero(s), sess), sim=None,
                                    context_note=_owner_note(sess),
                                    numbers_from=["research/hero_base.yaml", "sim.season.baseline_month", f"season {sess['id']} state"],
                                    district=_chat_district(s), season=_season_facts(sess))
            return {"who": "owner", **out, "citations": _citations(s, out["citations"])}
        found = next(((r, m) for m in sess["months"] for r in m.get("reviews") or [] if r.get("id") == body.who), None)
        if found is None:
            raise HTTPException(404, f"no review {body.who} in season {season_id}")
        review, month = found
        return persona.ask_reviewer(review, body.question, ctx, plan=month.get("plan"))
    except (llm.LLMGuardError, llm.LLMBackendError) as e:
        _llm_errors(e)


_REACTIONS: dict[str, dict[str, dict]] = {}   # runs dir -> shock -> pick (season-independent, computed once)


def _reactions(s) -> dict[str, dict]:
    """Owner's confidence-gated pick per interview-guide shock (Q24). Precomputed runs only: actions without a
    file are left out (never simulated live), and the result is cached per runs dir, so the survey stays fast."""
    key = str(game.runs_dir())
    if key in _REACTIONS:
        return _REACTIONS[key]
    hero, menu = _hero(s), owner_agent.action_menu()
    out: dict[str, dict] = {}
    for sh in ("SH03", "SH08", "SH06", "SH09", "SH05", "SH11"):
        try:
            cands = game.candidates(sh, menu, precomputed_only=True)
            if not cands:
                continue
            el, _ = owner_agent.confidence_gate(cands, hero, menu, False)
            pick = owner_agent.rule_pick(el, {a: menu[a] for a in menu if any(c["action"] == a for c in el)} or menu)
        except Exception:  # noqa: BLE001 - malformed run file: Q24 says so instead of failing the survey
            continue
        out[sh] = {"action": pick["action"], "label": menu.get(pick["action"], {}).get("label", pick["action"]),
                   "shock_label": game.shock_label(sh)}
    _REACTIONS[key] = out
    return out


@app.get("/season/{season_id}/survey")
def season_survey(season_id: str, s=Depends(db)):
    """트윈 인터뷰: the owner twin answers 15 interview-guide questions from its state (rows match
    research/interview/answer_sheet_template.csv so a real interview compares item by item)."""
    sess = _season(season_id)
    items = persona.survey(sess, _hero(s), _reactions(s))
    return {"season_id": sess["id"], "guide": "research/interview/owner_interview_guide.md",
            "answer_sheet": "research/interview/answer_sheet_template.csv", "items": items}


@app.get("/district/layer")
def district_layer(trdar: str = "3120012", s=Depends(db)):
    """In-game district layer: the pork-grill stores on the map, rent vs Seoul vs national, survival curves."""
    d = s.get(M.District, trdar)
    if d is None:
        raise HTTPException(404, f"상권 {trdar} not loaded")
    ind = s.get(M.Industry, d.industry_id) if d.industry_id else None
    meta = (ind.meta or {}) if ind else {}
    lic = {x.license_id: x for x in s.scalars(select(M.StoreLicense).where(M.StoreLicense.trdar_code == trdar))}
    stores = []
    for st in s.scalars(select(M.Store).where(M.Store.trdar_code == trdar, M.Store.class_code == "I20107")
                        .order_by(M.Store.name)):
        L = lic.get(st.license_id) if st.match_confidence in ("high", "medium") else None
        stores.append({"store_id": st.store_id, "name": st.name, "branch_name": st.branch_name, "lon": st.lon,
                       "lat": st.lat, "franchise_flag": st.franchise_flag,
                       "license": None if L is None else {"open_date": L.open_date, "months_open": L.months_open,
                                                          "area_pyeong": L.area_pyeong}})
    bm = {b["bench_id"]: b for b in meta.get("benchmarks") or []}
    hyehwa, seoul, nation = (bm.get(k, {}).get("value") for k in ("BM42", "BM43", "BM44"))
    hero = _hero(s)
    rent = {"hyehwa_per_m2": hyehwa, "seoul_per_m2": seoul, "national_per_m2": nation, "unit": "₩/㎡/월",
            "hyehwa_vs_national": round(hyehwa / nation, 2) if hyehwa and nation else None,
            "hero_rent_month": (hero.get("drv_rent") or {}).get("base_num"),
            "source_ids": sorted({x for k in ("BM42", "BM43", "BM44") for x in (bm.get(k, {}).get("source_id") or "").split(";") if x})}
    wide = meta.get("survival_wide") or {}
    narrow = meta.get("survival") or {}
    return {"trdar_code": trdar, "trdar_name": d.trdar_name, "geometry": d.geometry, "stores": stores,
            "rent": rent,
            "survival": {"scope": meta.get("survival_scope", "narrow"),
                         "study_area_hansik": narrow.get("hansik_primary"),
                         "wide_pork_name_only": wide.get("pork_name_only"), "wide_hansik_all": wide.get("hansik_all"),
                         "logrank": wide.get("logrank"), "areas": wide.get("areas")}}



# ---------------------------------------------------------------------------------------------------
# end-of-season report (§14): JSON, CSV, printable HTML, Q&A over the season's own rows
# ---------------------------------------------------------------------------------------------------

from urllib.parse import quote  # noqa: E402

from fastapi.responses import HTMLResponse, Response  # noqa: E402

from . import report as season_report  # noqa: E402


def _review_counts(s) -> dict:
    """검토 N/82: hero rows a member reviewed, out of all non-derived hero rows."""
    rows = [h for h in s.scalars(select(M.HeroAttribute)) if h.method != "derived"]
    return {"reviewed": sum(1 for h in rows if (h.reviewed_by or "").strip()), "total": len(rows)}


def _report(season_id: str, s) -> dict:
    sess = _season(season_id)
    return season_report.build(sess, _review_counts(s))


@app.get("/season/{season_id}/report")
def season_report_json(season_id: str, s=Depends(db)):
    return _report(season_id, s)


@app.get("/season/{season_id}/export.csv")
def season_report_csv(season_id: str, s=Depends(db)):
    text = season_report.to_csv(_report(season_id, s))
    korean = quote(f"시즌리포트-{season_id}.csv")
    return Response(content=text.encode("utf-8"), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f"attachment; filename=\"season-{season_id}.csv\"; filename*=UTF-8''{korean}"})


@app.get("/season/{season_id}/report.html", response_class=HTMLResponse)
def season_report_html(season_id: str, s=Depends(db)):
    return HTMLResponse(season_report.to_html(_report(season_id, s)))


class ReportAskIn(BaseModel):
    question: str = Field(..., min_length=1, max_length=300)
    session_id: str | None = None


@app.post("/season/{season_id}/report/ask")
def season_report_ask(season_id: str, body: ReportAskIn, s=Depends(db), x_session_id: str | None = Header(None)):
    rep = _report(season_id, s)
    try:
        return season_report.ask(rep, body.question, _llm_ctx(body.session_id, x_session_id))
    except (llm.LLMGuardError, llm.LLMBackendError) as e:
        _llm_errors(e)
