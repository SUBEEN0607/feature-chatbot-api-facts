"""make warm: with the season cache built, a fresh API process answers its first preview in under 1 s."""
import json
import os
import subprocess
import sys

from sim import warm
from sim.params import ROOT

PROBE = r"""
import json, time
from fastapi.testclient import TestClient
from api.main import app
with TestClient(app) as c:
    sid = c.post("/season", json={"mode": "free", "seed": 7}).json()["id"]
    t = time.time()
    r = c.post(f"/season/{sid}/preview", json={"plan": {"meat_grade": "aged", "menu_extras": ["minari"]}})
    print(json.dumps({"status": r.status_code, "seconds": time.time() - t, "op": r.json()["expected"]["op"]}))
"""


def first_preview_seconds(tmp_path) -> dict:
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{tmp_path / 'warm.db'}", "LLM_BACKEND": "mock", "RAG_EMBEDDER": "hash"}
    out = subprocess.run([sys.executable, "-c", PROBE], cwd=ROOT, env=env, capture_output=True, text=True, timeout=600)
    assert out.returncode == 0, out.stderr[-2000:]
    return json.loads(out.stdout.strip().splitlines()[-1])


def test_warm_cache_makes_the_first_preview_fast(tmp_path):
    assert warm.main.__module__ == "sim.warm"
    sys.argv = ["sim.warm"]
    assert warm.main() == 0 and warm.stale() == []
    r = first_preview_seconds(tmp_path)
    assert r["status"] == 200 and r["seconds"] < 1.0, r
