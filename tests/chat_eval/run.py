"""Owner-chat eval: ask every question in questions.yaml through the real API (in process) and score the answers
and the retrieval.

  python -m tests.chat_eval.run                          # mock backend, both chat paths, offline
  python -m tests.chat_eval.run --backend gemini --path persona   # real model (opt-in; see scripts/chat_eval_gemini.sh)
  python -m tests.chat_eval.run --only q01_revenue,q29_trap_weather --json out.json

Paths: `persona` = POST /persona/{season}/ask (the v2 game's 사장님에게 묻기), `chat` = POST /chat (the v1 game).
The eval season is one month played on the default plan (seed 7) so the season questions have a ground truth.
Uses DATABASE_URL / RAG_EMBEDDER as the API does (default data/twin.db with e5: run `make load ingest` first).
A real backend makes one call per question, spaced by --interval seconds (default 11: under the adapter's
LLM_RATE_PER_MIN=6 and the free tier's per-minute limit), each with its own session id so the per-session cap
does not end the run early. The month is always played on the mock backend.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

from . import score

REAL_INTERVAL_S = 11.0


def make_season(client) -> dict:
    s = client.post("/season", json={"mode": "free", "seed": 7}).json()
    r = client.post(f"/season/{s['id']}/play", json={"plan": {}})
    r.raise_for_status()
    return client.get(f"/season/{s['id']}").json() | {"id": s["id"]}


def ask(client, path: str, season_id: str, q: str, sid: str) -> tuple[int, dict]:
    if path == "persona":
        r = client.post(f"/persona/{season_id}/ask", json={"who": "owner", "question": q, "session_id": sid})
    else:
        r = client.post("/chat", json={"persona": "owner", "message": q, "session_id": sid})
    try:
        return r.status_code, r.json()
    except ValueError:
        return r.status_code, {"detail": r.text}


def run(client, backend: str = "mock", paths: tuple[str, ...] = ("persona", "chat"), only: set[str] | None = None,
        interval: float | None = None, log=None, qset: str = "questions") -> dict:
    items = [it for it in score.load(score.HERE / f"{qset}.yaml") if not only or it["id"] in only]
    prev = os.environ.get("LLM_BACKEND")
    os.environ["LLM_BACKEND"] = "mock"
    try:
        season = make_season(client)
    finally:
        os.environ["LLM_BACKEND"] = prev if prev is not None else "mock"
    sv = score.season_values(season)
    gap = interval if interval is not None else (0.0 if backend == "mock" else REAL_INTERVAL_S)
    run_id = f"{int(time.time())}"
    out = {"backend": backend, "season_id": season["id"], "season_values": sv, "rows": []}
    os.environ["LLM_BACKEND"] = backend
    try:
        first = True
        for path in paths:
            for it in items:
                if path not in it.get("paths", [path]):
                    continue
                if not first and gap:
                    time.sleep(gap)
                first = False
                t = time.time()
                status, body = ask(client, path, season["id"], it["q"], f"eval-{run_id}-{path}-{it['id']}")
                answer = body.get("answer") if status == 200 else f"<HTTP {status}: {str(body.get('detail'))[:160]}>"
                hits = body.get("sources") or body.get("citations") or []
                s = score.score_answer(it, answer or "", sv)
                row = {"id": it["id"], "path": path, "category": it["category"], "q": it["q"], "answer": answer,
                       "backend": body.get("backend"), "cached": body.get("cached"), "status": status,
                       "ms": round((time.time() - t) * 1000), "pass": s["pass"] and status == 200, "why": s["why"],
                       "retrieval_hit": score.retrieval_hit(it, hits),
                       "retrieved": [h.get("source_id") or h.get("doc_id") for h in hits]}
                out["rows"].append(row)
                if log:
                    log(row)
    finally:
        os.environ["LLM_BACKEND"] = prev if prev is not None else "mock"
    out["summary"] = summarize(out["rows"])
    return out


def summarize(rows: list[dict]) -> dict:
    by: dict[str, dict] = {}
    for r in rows:
        d = by.setdefault(r["path"], {"n": 0, "pass": 0, "model_n": 0, "model_pass": 0, "fallback": 0, "errors": 0,
                                      "ret_n": 0, "ret_hit": 0, "by_category": {}, "ms": []})
        d["n"] += 1
        d["pass"] += r["pass"]
        be = r.get("backend") or ""
        if r["status"] != 200:
            d["errors"] += 1
        elif "template used" in be:          # the real model was down or invented a number: the template answered
            d["fallback"] += 1
        elif not be.startswith("mock"):
            d["model_n"] += 1
            d["model_pass"] += r["pass"]
            d["ms"].append(r["ms"])
        c = d["by_category"].setdefault(r["category"], [0, 0])
        c[0] += r["pass"]
        c[1] += 1
        if r["retrieval_hit"] is not None:
            d["ret_n"] += 1
            d["ret_hit"] += r["retrieval_hit"]
    return by


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--backend", default="mock", choices=("mock", "gemini"))
    ap.add_argument("--path", default="both", choices=("persona", "chat", "both"))
    ap.add_argument("--set", dest="qset", default="questions", choices=("questions", "heldout"),
                    help="questions.yaml (tuned against) or heldout.yaml (never tuned on)")
    ap.add_argument("--only", default="", help="comma-separated question ids")
    ap.add_argument("--interval", type=float, default=None, help="seconds between real-model calls")
    ap.add_argument("--json", default="", help="write every answer and score here")
    a = ap.parse_args()
    if a.backend != "mock":
        os.environ.setdefault("LLM_RATE_PER_MIN", "6")
    os.environ.setdefault("REPORT_WARM", "0")
    from fastapi.testclient import TestClient

    from api import main as api_main

    def log(r):
        mark = "PASS" if r["pass"] else "FAIL"
        ret = {True: "R+", False: "R-", None: "  "}[r["retrieval_hit"]]
        print(f"{mark} {ret} {r['path']:<7} {r['id']:<18} {r['ms']:>6}ms  {(r['answer'] or '')[:110]}"
              + (f"\n      why: {'; '.join(r['why'])}" if r["why"] else ""), flush=True)

    paths = ("persona", "chat") if a.path == "both" else (a.path,)
    with TestClient(api_main.app) as client:
        out = run(client, a.backend, paths, {x for x in a.only.split(",") if x} or None, a.interval, log, a.qset)
    for path, d in out["summary"].items():
        cats = ", ".join(f"{k} {v[0]}/{v[1]}" for k, v in d["by_category"].items())
        print(f"\n[{a.backend} / {path}] answers {d['pass']}/{d['n']}  retrieval hit@k {d['ret_hit']}/{d['ret_n']}  ({cats})")
        if a.backend != "mock":
            ms = sorted(d["ms"])
            print(f"  answered by the model {d['model_pass']}/{d['model_n']} right, template fallback {d['fallback']}, "
                  f"HTTP errors {d['errors']}, median model latency {ms[len(ms) // 2] if ms else '-'} ms")
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
    sys.exit(0)


if __name__ == "__main__":
    main()
