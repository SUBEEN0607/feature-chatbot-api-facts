"""Owner agent: after a shock, pick ONE action from the sim's action menu, as strict JSON.

The LLM never decides numbers; it picks an action id and its arguments within the menu's bounds, and
the simulation reruns with that choice. Any output that does not parse cleanly becomes 'absorb'.
"""
from __future__ import annotations

import json
import re

from . import llm
from .ko import man_won, ro

FALLBACK_MENU = {
    "absorb": {"description_ko": "그대로 버틴다", "args": {}},
    "reprice": {"description_ko": "고기 판매가를 조정한다", "args": {"pct": [-0.15, 0.15]}},
    "cut_hours": {"description_ko": "영업·알바 시간을 줄인다", "args": {}},
    "change_mix": {"description_ko": "메뉴·주류 구성을 바꾼다", "args": {}},
}
MARKER = "RESPOND_WITH_OWNER_ACTION_JSON"
HERO_KEYS = ["prd_meat_price", "prd_alcohol_price", "sto_tables", "sto_seats_per_table", "sto_parttimers",
             "drv_rent", "drv_revenue", "drv_total_cost", "drv_operating_profit", "reg_competitors"]


def action_menu() -> dict:
    """sim/owner_actions.MENU if the simulation package provides it, else the fallback names."""
    try:
        from sim.owner_actions import MENU  # lazy: sim/ is built in parallel
        if isinstance(MENU, dict) and MENU:
            return MENU
    except Exception:  # noqa: BLE001 - any import problem means "use the fallback"
        pass
    return FALLBACK_MENU


def build_prompt(hero: dict, hits: list[dict], shock: dict | None = None, sim_result: dict | None = None,
                 menu: dict | None = None) -> str:
    menu = menu or action_menu()
    facts = "\n".join(f"- {k}: {hero[k]['base']} {hero[k].get('unit') or ''}".rstrip()
                      for k in HERO_KEYS if k in hero and hero[k].get("base") is not None)
    ctx = "\n\n".join(f"[{i + 1}] ({h.get('source_id') or h['doc_id']}) {h['text'][:600]}" for i, h in enumerate(hits))
    menu_txt = "\n".join(f"- {a}: {m.get('description_ko', '')} args={json.dumps(m.get('args', {}))}"
                         for a, m in menu.items())
    shock_txt = json.dumps(shock, ensure_ascii=False, default=str) if shock else "없음"
    sim_txt = json.dumps(sim_result, ensure_ascii=False, default=str)[:1500] if sim_result else "없음"
    return f"""당신은 서울 대학로(혜화역)에서 독립 삼겹살집을 운영하는 사장입니다 (가상의 composite 매장, 실제 상호 없음).
아래 매장 수치와 근거 자료만 사용해 판단하세요. 수치는 예시 추정치입니다.

[매장 수치]
{facts}

[발생한 충격]
{shock_txt}

[시뮬레이션 결과 (충격 전후)]
{sim_txt}

[근거 자료]
{ctx}

[선택 가능한 행동: 정확히 하나만 고르세요. args는 표시된 범위 안의 숫자만]
{menu_txt}

{MARKER}
설명 없이 JSON 객체 하나만 출력하세요. 형식:
{{"action": "<행동 id>", "args": {{<인자>: <숫자>}}, "reason": "<한국어 두세 문장, 근거 번호 인용>"}}"""


def parse_decision(text: str, menu: dict | None = None) -> dict:
    """Strict: a bare JSON object (or one ```json fence around it); known action; args in bounds."""
    menu = menu or action_menu()

    def fallback(why: str) -> dict:
        return {"action": "absorb", "args": {}, "reason": f"fallback: {why}", "fallback": True}

    t = (text or "").strip()
    m = re.fullmatch(r"```(?:json)?\s*(\{.*\})\s*```", t, re.S)
    if m:
        t = m.group(1)
    try:
        d = json.loads(t)
    except json.JSONDecodeError:
        return fallback("output is not a single JSON object")
    if not isinstance(d, dict) or set(d) - {"action", "args", "reason"} or "action" not in d:
        return fallback("JSON has missing or unexpected keys")
    action, args, reason = d.get("action"), d.get("args", {}) or {}, d.get("reason")
    if action not in menu:
        return fallback(f"unknown action {action!r}")
    if not isinstance(reason, str) or not reason.strip():
        return fallback("reason missing")
    if not isinstance(args, dict):
        return fallback("args is not an object")
    spec = menu[action].get("args", {})
    for k, v in args.items():
        if k not in spec:
            return fallback(f"unknown argument {k!r} for {action}")
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            return fallback(f"argument {k!r} is not a number")
        bounds = spec[k]
        if isinstance(bounds, (list, tuple)) and len(bounds) == 2 and not bounds[0] <= v <= bounds[1]:
            return fallback(f"argument {k}={v} outside {bounds}")
    return {"action": action, "args": args, "reason": reason.strip(), "fallback": False}


def decide(ctx: llm.RequestContext, hero: dict, hits: list[dict], shock: dict | None = None,
           sim_result: dict | None = None) -> dict:
    menu = action_menu()
    prompt = build_prompt(hero, hits, shock, sim_result, menu)
    res = llm.complete(prompt, ctx=ctx)
    out = parse_decision(res.text, menu)
    out.update({"backend": res.backend, "model": res.model, "cached": res.cached,
                "citations": [h.get("source_id") or h["doc_id"] for h in hits]})
    return out


def _won(v) -> str:
    return "?" if v is None else man_won(float(v))


def rule_pick(cands: list[dict], menu: dict) -> dict:
    """Deterministic pick: highest p50 operating profit after shock + action (ties keep menu order)."""
    scored = [c for c in cands if c.get("op_p50") is not None]
    if not scored:
        return {"action": "absorb", "args": {}, "reason": "fallback: no simulated outcomes", "fallback": True}
    best = max(scored, key=lambda c: c["op_p50"])
    absorb = next((c for c in scored if c["action"] == "absorb"), None)
    spec = menu.get(best["action"], {})
    desc = spec.get("label") or spec.get("description_ko") or best["action"]
    reason = (f"시뮬레이션한 {len(scored)}개 대응 가운데 '{desc}'의 월 영업이익 중앙값이 {ro(_won(best['op_p50']))} 가장 높습니다"
              + (f" (그대로 버티면 {_won(absorb['op_p50'])})." if absorb and absorb is not best else ".")
              + (f" 이때 월 손님 수 중앙값은 {best['covers_p50']:,.0f}명, 대기 이탈은 {best['walkaways_p50']:,.0f}팀입니다."
                 if best.get("covers_p50") is not None and best.get("walkaways_p50") is not None else ""))
    return {"action": best["action"], "args": best.get("args") or {}, "reason": reason, "fallback": False}


# Which mechanism decides whether each action's benefit is real. Criterion ids resolve to the hero
# attribute's confidence; "sim:" ids are sim/params.SIM_ASSUMPTIONS constants with no criterion row and no
# source (sim/params.py marks them all confidence L). An action missing from this map is treated as
# unmapped and excluded by the confidence gate (conservative).
ACTION_MECHANISMS = {
    "absorb": [],
    "reprice": [("mkt_price_elasticity", "가격을 올리면 손님이 얼마나 덜 오는지 (가격탄력성)")],
    "discount": [("mkt_price_elasticity", "가격을 내리면 손님이 얼마나 더 오는지 (가격탄력성)")],
    "reprice_alcohol": [("mkt_price_elasticity", "소주 가격에 따라 1인당 병수가 얼마나 줄어드는지 (같은 탄력성)")],
    "cut_staff_hours": [("sim:svc_service_minutes", "알바가 줄어도 서빙이 버티는지 (응대 시간 상수, 근거 없음)")],
    "cut_staff": [("sim:svc_service_minutes", "알바가 줄어도 서빙이 버티는지 (응대 시간 상수, 근거 없음)")],
    "change_mix": [("sim:upsell_response", "권유하면 주류와 식사 주문이 실제로 늘어난다는 가정")],
}
SIM_MECHANISM_CONFIDENCE = {"sim:svc_service_minutes": "L", "sim:upsell_response": "L"}


def mechanism_confidence(mid: str, hero: dict) -> str:
    if mid.startswith("sim:"):
        return SIM_MECHANISM_CONFIDENCE.get(mid, "L")
    return (hero.get(mid) or {}).get("confidence") or "L"


def confidence_gate(cands: list[dict], hero: dict, menu: dict, allow_low_confidence: bool) -> tuple[list, list]:
    """Split candidates into (eligible, excluded). Excluded = the action's benefit relies on a confidence-L
    (or unmapped) mechanism, unless allow_low_confidence. Excluded rows keep their outcome for display."""
    eligible, excluded = [], []
    for c in cands:
        a = c["action"]
        mechs = ACTION_MECHANISMS.get(a)
        if mechs is None:
            info = [{"id": None, "label_ko": "메커니즘 매핑 없음", "confidence": "L"}]
        else:
            info = [{"id": m, "label_ko": lbl, "confidence": mechanism_confidence(m, hero)} for m, lbl in mechs]
        weak = [m for m in info if m["confidence"] == "L"]
        if weak and not allow_low_confidence:
            spec = menu.get(a, {})
            excluded.append({**c, "label": spec.get("label", a), "mechanisms": info,
                             "reason": "근거 신뢰도가 낮은(L) 가정에 의존합니다: "
                                       + "; ".join(m["label_ko"] for m in weak) + ". 인터뷰로 확인 필요"})
        else:
            eligible.append({**c, "mechanisms": info})
    return eligible, excluded


def decide_from_candidates(ctx: llm.RequestContext, hero: dict, hits: list[dict], shock: dict | None,
                           cands: list[dict], allow_low_confidence: bool = False) -> dict:
    """One LLM call. Only confidence-gated candidates are offered (the model never sees excluded actions in
    its menu). Mock backend returns the rule pick; a real model sees every eligible candidate's outcome and
    must answer strict JSON. Invalid model output falls back to the rule pick, not to a blind default."""
    full_menu = action_menu()
    eligible, excluded = confidence_gate(cands, hero, full_menu, allow_low_confidence)
    menu = {a: full_menu[a] for a in full_menu if any(c["action"] == a for c in eligible)} or \
        {"absorb": full_menu.get("absorb", FALLBACK_MENU["absorb"])}
    rule = rule_pick(eligible, menu)
    if excluded and len(eligible) == 1:
        only = eligible[0]
        rule["reason"] = (f"근거가 확인된 대응은 '{menu.get(only['action'], {}).get('label', only['action'])}' 하나뿐이라 "
                          f"이 대응을 고릅니다 (월 영업이익 중앙값 {_won(only.get('op_p50'))}). 다른 대응 {len(excluded)}개는 "
                          f"신뢰도 낮은 가정에 기대고 있어 인터뷰로 확인이 필요합니다.")
    table = [{k: c.get(k) for k in ("action", "args", "op_p50", "revenue_p50", "covers_p50", "walkaways_p50")}
             for c in eligible]
    prompt = build_prompt(hero, hits, shock, {"candidate_outcomes_p50": table}, menu)
    mock = json.dumps({k: rule[k] for k in ("action", "args", "reason")}, ensure_ascii=False)
    res = llm.complete(prompt, ctx=ctx, mock_text=mock)
    d = parse_decision(res.text, menu)
    if res.backend == "mock":
        method = "rule"
    elif d["fallback"]:
        method, d = "llm_invalid_rule_fallback", {**rule, "llm_error": d["reason"]}
    else:
        method = "llm"
    d.update({"method": method, "backend": res.backend, "model": res.model, "cached": res.cached,
              "allow_low_confidence": allow_low_confidence, "candidates": eligible, "excluded": excluded,
              "sources": [h.get("source_id") or h["doc_id"] for h in hits]})
    return d
