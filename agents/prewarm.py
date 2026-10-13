"""Owner-chat cache pre-warm PLAN. Lists the prompts a pre-warm WOULD send; it never sends anything.

  python -m agents.prewarm --dry-run            # table of question x shock x action, cache key, cached?
  python -m agents.prewarm --dry-run --json     # same, with the full prompts

Sending is Keonhee's call on demo day: each listed question goes through the UI or POST /chat one request at a
time (session cap and per-minute cap apply), so a later identical question is a cache hit. A cache hit needs
the SAME question text, shock, action, hero values and RAG index as on demo day, so rerun this after any
data change; typed questions that differ by one character will not hit.

Phases match web/src/game/Game.tsx: before a choice the chat sends {shock, action: "absorb"} (runs/<shock>/
absorb.json); after a choice it sends the chosen action. The plan pairs each shock question with "absorb" and
with the owner agent's confidence-gated pick (what a player following the owner's advice would be playing).
"""
from __future__ import annotations

import argparse
import json
import sys

# 20 questions a payments-company CEO is most likely to ask the owner, most likely first (team judgment).
# None = asked before any event is drawn (context {shock: null, action: null}).
QUESTIONS: list[tuple[str, list[str] | None]] = [
    ("요즘 장사는 어떠세요?", None),
    ("한 달에 얼마 정도 남으세요?", None),
    ("돼지고기 값이 오르면 어떻게 하실 건가요?", ["SH03"]),
    ("가장 큰 비용은 뭔가요?", None),
    ("손님은 주로 어떤 분들이 오세요?", None),
    ("카드 수수료는 부담되세요?", None),
    ("고기 가격을 올리면 손님이 줄지 않을까요?", ["SH01"]),
    ("최저임금이 오르면 어떻게 버티세요?", ["SH06"]),
    ("방학이라 손님이 줄면 어떻게 하세요?", ["SH09"]),
    ("근처에 고깃집이 새로 생기면 어떻게 하실 거예요?", ["SH11"]),
    ("임대료가 오르면 어떻게 하실 건가요?", ["SH08"]),
    ("가장 바쁜 시간은 언제예요?", None),
    ("비 오는 날은 장사가 어때요?", ["SH10"]),
    ("알바를 한 명 줄이면 어떻게 될까요?", ["SH07"]),
    ("소주 가격을 올리면 어떨 것 같으세요?", ["SH04"]),
    ("술 판매가 줄면 이익에 얼마나 영향이 있나요?", ["SH05"]),
    ("가격을 내리면 손님이 더 올까요?", ["SH02"]),
    ("이번 달 결정은 왜 그렇게 하셨어요?", ["SH03", "SH09"]),
    ("임대료는 얼마나 부담되세요?", None),
    ("결제 단말기나 키오스크를 바꿀 생각이 있으세요?", None),
]


def plan(model: str | None = None) -> list[dict]:
    """Build every prompt exactly as POST /chat would (persona owner, default k). Makes no LLM call."""
    from agents import chat as chat_agent
    from agents import llm
    from agents import owner as owner_agent
    from api import game, main
    from db.session import session_factory

    model = model or llm.default_model("claude_cli")
    llm.check_model("claude_cli", model)
    rows = []
    with session_factory(main.engine())() as s:
        hero = main._hero(s)
        menu = owner_agent.action_menu()
        picks: dict[str, str] = {}

        def pick(shock: str) -> str:
            if shock not in picks:
                el, _ = owner_agent.confidence_gate(game.candidates(shock, menu), hero, menu, False)
                picks[shock] = owner_agent.rule_pick(el, menu)["action"]
            return picks[shock]

        for i, (q, shocks) in enumerate(QUESTIONS, 1):
            if shocks is None:
                contexts = [(None, None, "평소 (사건 전)")]
            elif q.startswith("이번 달 결정"):
                contexts = [(sh, pick(sh), "선택 후 (사장님 추천)") for sh in shocks]
            else:
                contexts = [c for sh in shocks for c in ((sh, "absorb", "사건 확인, 선택 전"),
                                                          (sh, pick(sh), "선택 후 (사장님 추천)"))]
            seen = set()
            for shock, action, phase in contexts:
                if (shock, action) in seen:
                    continue
                seen.add((shock, action))
                inp = main.chat_inputs(s, q, shock, action)
                prompt, _ = chat_agent.prepare("owner", q, inp["hits"], inp["hero"], inp["sim"], inp["note"],
                                               district=inp["district"])
                key = llm.cache_key(model, prompt)
                rows.append({"n": i, "question": q, "shock": shock, "action": action, "phase": phase,
                             "model": model, "prompt_chars": len(prompt), "cache_key": key,
                             "cached": (llm.cache_dir() / f"{key}.json").exists(), "prompt": prompt,
                             "request": {"persona": "owner", "message": q,
                                         "context": {"shock": shock, "action": action}}})
    return rows


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Owner-chat pre-warm plan (dry run only; never sends)")
    ap.add_argument("--dry-run", action="store_true", help="required: list what a pre-warm would send")
    ap.add_argument("--json", action="store_true", help="print the full plan as JSON (prompts included)")
    ap.add_argument("--model", default=None, help="claude_cli model the demo will use (default: opus)")
    a = ap.parse_args(argv)
    if not a.dry_run:
        print("This tool never sends. Run with --dry-run to see the plan; on demo day Keonhee sends the "
              "listed questions through the UI or POST /chat himself, one request at a time.", file=sys.stderr)
        return 2
    rows = plan(a.model)
    if a.json:
        print(json.dumps(rows, ensure_ascii=False, indent=1))
    else:
        print(f"{'#':>2}  {'shock':6} {'action':16} {'phase':18} {'chars':>5}  {'key':12}  cached  question")
        for r in rows:
            print(f"{r['n']:>2}  {r['shock'] or '-':6} {r['action'] or '-':16} {r['phase']:18} {r['prompt_chars']:>5}  "
                  f"{r['cache_key'][:12]}  {'yes' if r['cached'] else 'no ':3}     {r['question']}")
    n_cached = sum(r["cached"] for r in rows)
    print(f"\nDRY RUN: {len(rows)} prompts for {len(QUESTIONS)} questions ({n_cached} already cached for "
          f"{rows[0]['model'] if rows else '-'}). Nothing was sent.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
