"""Offline 개선 리포트 for 시연 모드: web/public/guided/report.json, the same JSON as GET /season/{id}/report, built by
api/report.py (the code the API serves) from the guided story path, plus precomputed answers to the four preset
questions (api/report.mock_answer, no model call). Rerun after the guided files change; sim.report plugs in
behind api.report.build automatically.

Usage (repo root): PYTHONPATH=. .venv/bin/python web/scripts/make_guided_report.py
"""
from __future__ import annotations

import json
from pathlib import Path

from api import report

GUIDED = Path(__file__).resolve().parents[1] / "public" / "guided"
PRESETS = ["가장 큰 실수는 뭐였어?", "운이 좋았던 달은?", "다음 시즌에 하나만 바꾼다면?", "잘한 결정은?"]


def main() -> None:
    index = json.loads((GUIDED / "index.json").read_text(encoding="utf-8"))
    months = []
    for st in index["story"]:
        opt = next(o for o in st["decision"]["options"] if o["id"] == st["story_choice"])
        nd = st.get("night_decision")
        file = opt["file"]
        if nd:  # the story's night choice
            br = next((b for b in nd["branches"] if b["option_id"] == nd["story_option"]), None)
            file = br["file"] if br else file
        months.append(json.loads((GUIDED / file).read_text(encoding="utf-8")))
    sess = {"id": "guided", "mode": "guided", "seed": index.get("seed", 0), "engine": index.get("engine", "sim.season"),
            "state": months[-1]["state_after"], "months": months}
    # 검토 N/82 offline too: the same count the HUD chip shows (web/public/data/hero.json, from the workbook)
    hero = json.loads((GUIDED.parent / "data" / "hero.json").read_text(encoding="utf-8"))
    rep = report.build(sess, hero.get("review"))
    rep["asks"] = [{"q": q, "a": a, "sources": src} for q in PRESETS for a, src in [report.mock_answer(q, rep)]]
    rep["offline_note"] = "시연 모드 이야기 경로의 리포트입니다. 미리 계산했고, 묻기는 네 가지 질문에만 답합니다."
    (GUIDED / "report.json").write_text(json.dumps(rep, ensure_ascii=False, default=float))
    print("wrote", GUIDED / "report.json", len(rep["table"]), "months,", len(rep["improvements"]), "improvements")


if __name__ == "__main__":
    main()
