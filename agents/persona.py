"""Persona layer for the v2 season (docs/GAME-V2-SPEC.md §8).

1. owner reaction lines per month and per event
2. review text: structured reviews[] (segment, stars, reason codes, what happened) -> short Korean reviews in
   each segment's voice
3. ask a specific reviewer (customer persona grounded in that party's actual experience)
4. 트윈 인터뷰: the owner twin answers the interview-guide survey from its state, item by item

Mock backend = template banks with variety (deterministic per id), using only numbers from the inputs.
A real backend goes through agents/llm.py (one call per request); its text is checked with
agents.numbers and replaced by the template if it invents a number or breaks the JSON shape.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from . import llm
from .ko import eun, ieyo, ira, man_won, myeon, ro, won_ko
from .numbers import invented, pool

REPO = Path(__file__).resolve().parents[1]
GUIDE = REPO / "research" / "interview" / "owner_interview_guide.md"
SHEET = REPO / "research" / "interview" / "answer_sheet_template.csv"

SEGMENTS = {"twenties": "20대 친구 모임", "office": "직장인 회식", "family": "동네 가족"}
# Fixed wording that contains digits but is not data (segment names, the 0-100 fatigue scale, 월 이름,
# the guide's rent-band cards). The number check allows these alongside the inputs.
VOCAB = [*SEGMENTS.values(), "100 중에", "10월 11월 12월 1월 2월 3월", "200만 300만 400만 500만원 ① ② ③ ④ ⑤"]


def _pick(key: str, options: list[str]) -> str:
    return options[int(hashlib.sha256(key.encode()).hexdigest(), 16) % len(options)]


def won(v) -> str:
    v = float(v)
    return man_won(v) if abs(v) >= 1e5 else won_ko(v)


# --- 2. reviews ---------------------------------------------------------------------------------------

from . import decision_bank as DB  # noqa: E402
from . import review_bank as RB  # noqa: E402


def _facts(r: dict, plan: dict | None = None) -> dict:
    d, plan = r.get("drivers") or {}, plan or r.get("plan") or {}
    meat = d.get("meat_price") if isinstance(d.get("meat_price"), (int, float)) and d.get("meat_price", 0) > 100 \
        else plan.get("meat_price")
    soju = d.get("soju_price") if isinstance(d.get("soju_price"), (int, float)) and d.get("soju_price", 0) > 100 \
        else plan.get("soju_price")
    return {"wait": int(round(r.get("wait_min", d.get("wait_min", 0)) or 0)),
            "price": won(meat) if meat else "이 가격", "soju": won(soju) if soju else "이 가격",
            "size": r.get("party_size") or d.get("party_size") or "여러"}


def _choose(key: str, options: list[str], used: set[str], fmt: dict) -> str | None:
    """First option (in a per-review rotation) whose filled-in sentence is not used yet this month.
    "" is a valid pick (= leave this part out). None = every option already used."""
    start = int(hashlib.sha256(key.encode()).hexdigest(), 16) % len(options)
    for k in range(len(options)):
        o = options[(start + k) % len(options)]
        if o == "":
            return ""
        sent = o.format(**fmt)
        if sent not in used:
            used.add(sent)
            return sent
    return None


def compose_review(r: dict, plan: dict | None, used: set[str], lead: str | None = None,
                   tail: str | None = None) -> tuple[str, dict]:
    """(text, meta). Star-consistent: 5 stars = what went right only (an event review may add one mild caveat);
    4 stars = what went right + at most one mild caveat; 3 = main complaint + one good point; <= 2 = complaints."""
    seg = r.get("segment") if r.get("segment") in SEGMENTS else "twenties"
    stars = int(max(1, min(5, round(float(r.get("stars", 4))))))
    f = _facts(r, plan)
    codes = list(dict.fromkeys(RB.ALIASES.get(c, c) for c in r.get("reason_codes") or []))
    pos = [c for c in codes if c in RB.POSITIVE and c in RB.MAIN]
    neg = [c for c in codes if c in RB.COMPLAINT and c in RB.MAIN]
    if f["wait"] < 1:
        neg = [c for c in neg if c != "long_wait"]
    rid = r["id"]
    parts, meta = [], {"main": None, "caveats": 0, "complaints": 0}

    def add(key, options):
        got = _choose(f"{rid}-{key}", options, used, f)
        if got:
            parts.append(got)
        return got

    add("open", RB.OPENERS[stars])
    if lead:                       # the visit's own context (e.g. invited, came as a walk-in group) right after the opener
        parts.append(lead)
    if stars >= 4:
        n = sum(bool(add(c, RB.MAIN[c][seg])) for c in pos[:2])
        if not n:
            add("good", RB.GOOD[seg])
        meta["main"] = "positive"
        caveat_ok = neg and (stars == 4 or r.get("incentivized"))
        if caveat_ok:
            cv = _choose(f"{rid}-cav", RB.CAVEATS.get(neg[0], []) or [""], used, f)
            if cv:
                parts.append("다만 " + cv)
                meta["caveats"] = 1
    elif stars == 3:
        if neg and add(neg[0], RB.MAIN[neg[0]][seg]):
            meta["complaints"] = 1
        if pos:
            add(pos[0], RB.MAIN[pos[0]][seg])
        if not neg and not pos:
            add("neutral", RB.NEUTRAL[seg])
        meta["main"] = "complaint" if meta["complaints"] else "neutral"
    else:
        meta["complaints"] = sum(bool(add(c, RB.MAIN[c][seg])) for c in neg[:2])
        if not meta["complaints"]:
            add("bad", RB.BAD[seg])
        meta["main"] = "complaint"
    if "comped" in codes:          # said once, near the end, never the lead
        add("comped", RB.COMPED[seg])
    if tail:                       # what another table's decision did to this party, before the sign-off
        parts.append(tail)
    mood = "pos" if stars >= 4 else "neg" if stars <= 2 else "mid"
    add("close", RB.CLOSERS[seg][mood])
    if len(parts) == 0 or (len(parts) == 1 and stars >= 4 and meta["main"] == "positive" and parts[0] in RB.OPENERS[stars]):
        parts.append(f"{f['size']}명이서 다녀왔어요" if isinstance(f["size"], int) else "다녀왔어요")
    out = ""
    for part in (x.rstrip(".") for x in parts if x):
        out += part if not out else (" " if out[-1] in "!?" else ". ") + part
    return out, meta


def review_template(r: dict, plan: dict | None = None) -> str:
    """One review on its own (no month context)."""
    return compose_review(r, plan, set())[0]


def review_texts(reviews: list[dict], plan: dict | None = None, month: dict | None = None) -> dict[str, str]:
    """All reviews of a month together, so no sentence is reused within the month."""
    used: set[str] = set()
    out = {}
    for r in reviews:
        dl, own = decision_review_line(r, month, used) if month is not None else (None, False)
        text, meta = compose_review(r, plan, used, lead=dl if own else None, tail=None if own else dl)
        if dl:
            meta["decision"] = True
        out[r["id"]] = text
        r["text_meta"] = meta
        r["shown_codes"] = shown_codes(r)
        if r.get("incentivized"):
            r["event_label"] = "이벤트 참여"
    return out


def shown_codes(r: dict) -> list[str]:
    """Reason codes a review card should display, consistent with its stars (no complaint chips on 5 stars
    unless it is an event review's single caveat; at most one complaint chip on 4 stars)."""
    stars = int(round(float(r.get("stars", 4))))
    codes = list(dict.fromkeys(RB.ALIASES.get(c, c) for c in r.get("reason_codes") or []))
    orig = {RB.ALIASES.get(c, c): c for c in r.get("reason_codes") or []}
    pos = [c for c in codes if c in RB.POSITIVE]
    neg = [c for c in codes if c in RB.COMPLAINT]
    if stars >= 5:
        keep = pos + (neg[:1] if r.get("incentivized") else [])
    elif stars == 4:
        keep = pos + neg[:1]
    else:
        keep = neg + pos[:1]
    return [orig[c] for c in keep]


# --- 1. owner lines -----------------------------------------------------------------------------------

EVENT_LINES = {
    "pork_up": ["도매가가 또 올랐대요. 가격을 건드릴지 이번 달은 버틸지 고민이에요",
                "고기값이 오르면 제일 먼저 남는 게 줄어요. 마진부터 다시 계산해 봐야겠어요"],
    "rain_week": ["비 오는 주간이라 야장을 접어야겠네요", "비 오면 대학로 저녁 손님이 확 줄어요"],
    "competitor_open": ["길 건너에 고깃집이 새로 생겼어요. 처음 몇 달은 손님을 나눠 가질 거예요",
                        "새 가게가 오픈 이벤트를 하네요. 우리 단골을 지켜야죠"],
    "viral_blog": ["블로거가 다녀갔대요. 이번 주에 손님이 몰릴 수도 있어요", "후기가 퍼지면 웨이팅이 생길 거예요"],
    "staff_quit": ["알바 한 명이 갑자기 그만뒀어요. 당분간 제가 더 뛰어야겠네요", "사람 구할 때까지 서빙이 밀릴까 걱정이에요"],
}


DANGER_WORDS = ("위험", "바닥", "접어야", "문을 닫", "못 버텨")


def owner_state(result: dict) -> dict:
    """Mood, runway, net vs 평소 and the top driver each way: the sim's owner_line fields when present (so the
    owner never contradicts the HUD), else the same rules computed from the MonthResult."""
    ol = result.get("owner_line") or {}
    op = (result.get("draw") or {}).get("kpis", {}).get("op")
    st = result.get("state_after") or {}
    cash = st.get("cash")
    shadow_op = ((result.get("shadow") or {}).get("kpis") or {}).get("op")
    runway = ol.get("runway_months")
    if runway is None and op is not None and cash is not None:
        runway = cash / -op if op < 0 and cash > 0 else (0.0 if cash <= 0 else None)
    mood = ol.get("mood")
    if mood not in ("great", "ok", "worried", "desperate") or "runway_months" not in ol:
        if cash is not None and (cash <= 0 or (runway is not None and runway < 3)):
            mood = "desperate"
        elif runway is not None and runway < 12:
            mood = "worried"
        elif op is not None and op > 0 and shadow_op is not None and op > max(shadow_op, 0) * 1.3:
            mood = "great"
        else:
            mood = "ok"
    net = ol.get("net_vs_shadow", (op - shadow_op) if op is not None and shadow_op is not None else None)
    if mood in ("ok", "great") and below_usual(net, shadow_op):
        mood = "worried"           # well below 평소 is never a 무난/좋았 month, even in the black
    steps = [w for w in result.get("waterfall") or [] if w.get("kind", "step") == "step" and w.get("delta")]
    pos = ol.get("top_positive") or next((w for w in sorted(steps, key=lambda w: -w["delta"]) if w["delta"] > 0), None)
    neg = ol.get("top_negative") or next((w for w in sorted(steps, key=lambda w: w["delta"]) if w["delta"] < 0), None)
    return {"mood": mood, "op": op, "cash": cash, "runway": runway, "net": net, "pos": pos, "neg": neg,
            "closed": bool(st.get("closed"))}


def below_usual(net, shadow_op) -> bool:
    """The month came in well below 평소대로였다면: more than 30만원 and 20% of 평소 OP short (sim/season.py
    _owner_line uses the same rule for the mood)."""
    return net is not None and net <= -max(300_000, 0.2 * abs(shadow_op or 0))


def money(v) -> str:
    """Amounts in the owner's line as the screens print them: 1만원 and up in 만원 (87,650 -> 9만원), the UI minus."""
    v = float(v)
    return man_won(v) if abs(v) >= 1e4 else won_ko(v)


def runway_shown(runway: float) -> int:
    """Months the cash lasts, as every screen says it: whole months, at least 1 (the HUD's runwayMonths, sim/season.py)."""
    return max(1, int(runway))


def owner_template(result: dict) -> dict:
    o = owner_state(result)
    op, cash, runway, mood = o["op"], o["cash"], o["runway"], o["mood"]
    cal = (result.get("calendar") or {}).get("label", "이번 달")
    key = f"{result.get('month')}-{op}"
    months = f"{runway_shown(runway)}개월" if runway else None
    if op is None:
        lead = _pick(key, ["이번 달도 열심히 해 봐야죠", "손님들 반응을 보면서 조정해 볼게요"])
    elif o["closed"]:
        lead = _pick(key, ["결국 문을 닫게 됐어요. 운영자금이 바닥난 채로 두 달을 버티지 못했어요",
                           "가게를 접기로 했어요. 운영자금이 바닥나서 더는 못 버텨요"])
    elif mood == "desperate":
        lead = (_pick(key, ["운영자금이 바닥났어요. 이대로 한 달 더 가면 문을 닫아야 해요",
                            "통장이 바닥이에요. 이번 달을 못 넘기면 정말 접어야 해요"]) if cash is not None and cash <= 0 else
                _pick(key, [f"{eun(cal)} {money(abs(op))} 적자예요. 이 속도면 운영자금이 {months}도 못 버텨요, 정말 위험해요",
                            f"{cal} 장사가 너무 힘들었어요. 지금 속도면 {months} 안에 운영자금이 바닥나요"]))
    elif mood == "worried" and (runway is None or runway >= 12):   # in the black (or a long runway) but well below 평소
        lead = _pick(key, [f"{eun(cal)} {money(abs(op))} {'남았지만' if op >= 0 else '적자인데'} 평소만 못했어요. 계획을 다시 봐야겠어요",
                           f"{cal} 장사는 기대보다 못했어요. 이대로 가면 안 되겠어요"])
    elif mood == "worried":
        lead = _pick(key, [f"{eun(cal)} {money(abs(op))} 적자예요. 지금 속도면 운영자금이 {months}쯤 버텨요, 계획을 바꿔야겠어요",
                           f"{cal}은 손해를 봤어요. 이대로면 {months} 정도 버틸 수 있어서 마음이 급해요"])
    elif mood == "great":
        lead = _pick(key, [f"{eun(cal)} {money(op)} 남았어요. 이번 달은 장사가 잘됐어요",
                           f"{cal} 장사 정말 좋았어요. 영업이익이 {ieyo(money(op))}"])
    elif op < 0:
        lead = _pick(key, [f"{eun(cal)} {money(abs(op))} 적자긴 한데, 운영자금이 넉넉해서 아직 여유는 있어요",
                           f"{cal}은 조금 손해를 봤지만 당장 걱정할 정도는 아니에요"])
    else:
        lead = _pick(key, [f"{eun(cal)} {money(op)} 남았어요", f"{cal} 장사는 무난했어요. 영업이익이 {ieyo(money(op))}"])
    parts = [lead]
    if o["net"] is not None:
        parts.append("평소대로 했을 때랑 거의 같아요" if abs(o["net"]) < 50_000 else
                     f"평소대로 했으면 이번 달보다 {money(abs(o['net']))} " + ("덜 벌었을 거예요" if o["net"] > 0 else "더 벌었을 거예요"))
    pos, neg = o["pos"], o["neg"]
    if pos and neg:
        parts.append(f"{pos['driver']}에서 {money(pos['delta'])} 벌고, {neg['driver']}에서 {money(abs(neg['delta']))} 잃었어요")
    elif pos:
        parts.append(f"{pos['driver']} 덕에 {money(pos['delta'])} 더 벌었어요")
    elif neg:
        parts.append(f"{neg['driver']}에서 {money(abs(neg['delta']))} 손해를 봤어요")
    line = ". ".join(parts)
    events = {}
    for e in result.get("events") or []:
        eid = e.get("id") if isinstance(e, dict) else str(e)
        label = e.get("label", eid) if isinstance(e, dict) else eid
        mech = e.get("mechanism") if isinstance(e, dict) else None
        bank = EVENT_LINES.get(eid) or [f"이번 달엔 {label} 소식이 있었어요" + (f". {mech}" if mech else ""),
                                        f"{ira(label)} 신경이 쓰이네요" + (f". {mech}" if mech else "")]
        events[eid] = _pick(f"{key}-{eid}", bank)
    return {"text": line, "event_lines": events, "mood": mood, "runway_months": runway}


# --- in-night decisions (GAME-V2-SPEC §12.1) -----------------------------------------------------------

def decision_prompt_lines(month_start: dict) -> None:
    """Add owner voice to each decision point of a /start_month result: `owner_prompt` and, per option,
    `owner_foresight`. Mutates `month_start`. No numbers beyond the decision point's own text."""
    for dp in month_start.get("decision_points") or []:
        kind = dp.get("kind")
        dp["owner_prompt"] = _pick(f"{dp.get('id')}-prompt", DB.PROMPT.get(kind) or [dp.get("prompt_ko") or "어떻게 할까요?"])
        for o in dp.get("options") or []:
            line = DB.FORESIGHT.get((kind, o.get("id")))
            if not line:
                hint, down = o.get("effect_hint_ko"), o.get("downside_ko")
                line = f"{o.get('label_ko', o.get('id'))} 하면 {hint or '괜찮을 것 같은데'}" + (f", 대신 {down}" if down else "")
            o["owner_foresight"] = line


def decision_aftermath(result: dict, avoid: set[str] | frozenset = frozenset()) -> dict[str, str]:
    """dp id -> what happened, in the owner's voice, from that month's night_decisions.
    `avoid`: lines already said in earlier months of the season (skipped while the bank has others)."""
    out = {}
    labels = {d.get("id"): d for d in result.get("decision_points") or []}
    for nd in result.get("night_decisions") or []:
        kind, opt = nd.get("kind"), nd.get("option_id")
        nd_ = nd.get("night_delta") or {}
        walk = abs(round(nd_.get("walkaways") or 0))
        mop = nd.get("vs_default_op") or 0     # month OP: the chosen option vs the default handling
        bank = list(DB.AFTERMATH.get((kind, opt)) or [])
        # lines that quote a number only when that number is meaningful this month
        bank = [b for b in bank if ("{walk}" not in b or walk >= 1) and ("{op}" not in b or abs(mop) >= 10_000)]
        if not bank:
            dp = labels.get(nd.get("id"), {})
            o = next((x for x in dp.get("options") or [] if x.get("id") == opt), {})
            bank = [f"{dp.get('title_ko', '그 일')} 때 {o.get('label_ko', opt)} 했어요"]
        bank = [b.format(walk=walk, covers=abs(round(nd_.get("covers") or 0)), op=won(abs(mop)), updown="늘었어요" if mop > 0 else "줄었어요",
                         count=nd.get("monthly_count")) for b in bank]
        fresh = [b for b in bank if b not in avoid and b not in out.values()]
        out[nd.get("id")] = _pick(f"{nd.get('id')}-{opt}", fresh or bank)
    return out


def decision_review_line(r: dict, result: dict, used: set[str]) -> tuple[str | None, bool]:
    """(sentence, is_own_party) about an in-night decision, only for a party the sim links to one
    (review.decision_party = the decision's own party; review.cause_decisions = parties it touched).
    The sim's decision flag on the party (meat_swapped, noisy_group, ...) picks the line when present;
    otherwise the (kind, option) line. Tone follows the stars."""
    dps = list(r.get("cause_decisions") or [])
    own = r.get("decision_party")
    if not dps and not own:
        return None, False
    chosen = {nd.get("id"): nd for nd in result.get("night_decisions") or []}
    stars = int(round(float(r.get("stars", 4))))
    flags = [c for c in r.get("reason_codes") or [] if c in DB.REVIEW_FLAG]
    def rank(dp_id):   # own party first, then a decision whose flag is on the party, a comped blogger's table last
        nd = chosen.get(dp_id) or {}
        flagged = any(DB.FLAG_KIND[c] == nd.get("kind") for c in flags)
        return (dp_id != own, not flagged, (nd.get("kind"), nd.get("option_id")) == ("blogger", "comp"))

    for dp_id in sorted(dict.fromkeys(([own] if own else []) + dps), key=rank):
        nd = chosen.get(dp_id)
        if not nd:
            continue
        key = (nd.get("kind"), nd.get("option_id"))
        if dp_id == own and key in DB.REVIEW_PARTY:
            got = _choose(f"{r['id']}-dp", DB.REVIEW_PARTY[key], used, {})
            if got:
                return got, True
            continue
        flag = next((c for c in flags if DB.FLAG_KIND[c] == key[0]), None)
        pair = DB.REVIEW_FLAG[flag] if flag else DB.REVIEW_AFFECTED.get(key)
        if pair:
            got = _choose(f"{r['id']}-dp", [pair[1] if stars >= 4 else pair[0]], used, {})
            if got:
                return got, False
    return None, False


# --- render a month (one LLM call on a real backend, templates otherwise) -----------------------------

def _runway_said(result: dict) -> int | None:
    r = (result.get("owner_line") or {}).get("runway_months")
    return runway_shown(r) if r else None


def _month_pool(result: dict) -> set[str]:
    return pool(VOCAB, result.get("night_decisions"), result.get("decision_points"), result.get("owner_line", {}).get("runway_months"), _runway_said(result), result.get("owner_line", {}).get("net_vs_shadow"),
                (result.get("shadow") or {}).get("kpis"), result.get("draw"), result.get("state_after", {}).get("cash"), result.get("reviews"),
                result.get("plan"), result.get("calendar"), result.get("events"), result.get("waterfall"))


def render_month(result: dict, ctx: llm.RequestContext | None = None, said: set[str] | frozenset = frozenset()) -> dict:
    """Fill owner_line.text / event_lines and reviews[].text. Mutates and returns `result`."""
    owner = owner_template(result)
    texts = review_texts(result.get("reviews") or [], result.get("plan"), result)
    backend = "template"
    if ctx is not None:
        prompt = ("대학로 삼겹살집(가상) 시즌 게임의 한 달 결과입니다. 아래 JSON의 사실만 써서 한국어로 짧게 쓰세요. "
                  "숫자는 JSON에 있는 것만 씁니다. RESPOND_WITH_PERSONA_JSON\n"
                  '형식: {"owner_line": "...", "event_lines": {"<event id>": "..."}, "reviews": {"<review id>": "..."}}\n'
                  + json.dumps({k: result.get(k) for k in ("month", "calendar", "events", "plan", "draw", "reviews")},
                               ensure_ascii=False, default=str))
        mock = json.dumps({"owner_line": owner["text"], "event_lines": owner["event_lines"], "reviews": texts},
                          ensure_ascii=False)
        res = llm.complete(prompt, ctx=ctx, mock_text=mock)
        backend = res.backend
        if res.backend != "mock":
            try:
                d = json.loads(res.text)
                allowed = _month_pool(result)
                ok = (set(d) == {"owner_line", "event_lines", "reviews"} and set(d["reviews"]) == set(texts)
                      and not invented(d["owner_line"], allowed)
                      and not any(invented(t, allowed) for t in list(d["reviews"].values()) + list(d["event_lines"].values())))
                if ok:
                    owner = {"text": d["owner_line"], "event_lines": {k: v for k, v in d["event_lines"].items()
                                                                      if k in owner["event_lines"]}}
                    texts = d["reviews"]
                else:
                    backend += " (invalid output: templates used)"
            except (json.JSONDecodeError, TypeError, AttributeError):
                backend += " (invalid output: templates used)"
    result.setdefault("owner_line", {})
    result["owner_line"].update(owner)
    result["owner_line"]["decision_lines"] = decision_aftermath(result, said)
    for r in result.get("reviews") or []:
        r["text"] = texts.get(r["id"], review_template(r, result.get("plan")))
    result["persona_backend"] = backend
    return result


# --- 3. ask a reviewer ---------------------------------------------------------------------------------

def _reviewer_intent(q: str) -> str:
    for intent, kws in (("wait", ["기다", "대기", "웨이팅", "줄"]), ("price", ["가격", "비싸", "비용", "얼마"]),
                        ("meat", ["고기", "맛", "질", "품질"]), ("service", ["직원", "서비스", "친절", "구워"]),
                        ("revisit", ["다시", "또", "재방문", "추천"])):
        if any(k in q for k in kws):
            return intent
    return "general"


def reviewer_template(r: dict, question: str, plan: dict | None = None) -> str:
    """Answer in that party's voice from what happened to it. Follows the card (shown_codes and stars): a code
    the card does not show is never voiced as a complaint, and prices come from the month's plan."""
    seg = SEGMENTS.get(r.get("segment"), "손님")
    f = _facts(r, plan)
    stars = int(round(float(r.get("stars", 4))))
    codes = {RB.ALIASES.get(c, c) for c in (r.get("shown_codes") if r.get("shown_codes") is not None else shown_codes(r))}
    intent = _reviewer_intent(question)
    who = f"{ro(seg)} {f['size']}명이 왔던 손님이에요." if isinstance(f["size"], int) else f"{ro(seg)} 왔던 손님이에요."
    price = f"1인분 {f['price']}이었는데" if f["price"] != "이 가격" else "가격은"
    if "price_high" in codes:
        price_view = "저희한테는 조금 비싸게 느껴졌어요." if stars >= 4 else "저희한테는 비싸게 느껴졌어요."
    elif "good_value" in codes:
        price_view = "가격 대비 만족스러웠어요."
    else:
        price_view = "그 정도면 괜찮다고 생각했어요." if stars >= 3 else "가격보다는 다른 게 아쉬웠어요."
    waited = f["wait"] >= 1
    body = {
        "wait": ((f"그날 {f['wait']}분 정도 기다렸어요. " + ("솔직히 길었어요." if "long_wait" in codes else "그 정도면 참을 만했어요."))
                 if waited else "거의 안 기다리고 바로 앉았어요."),
        "price": f"{price} {price_view}",
        "meat": ("고기는 정말 좋았어요." if "meat_good" in codes else
                 "고기는 좀 아쉬웠어요." if "meat_poor" in codes else
                 "고기는 맛있게 먹었어요." if stars >= 4 else "고기는 무난했어요."),
        "service": ("직원분이 구워 주셔서 편했어요." if "staff_grilled" in codes else
                    ("바쁠 때 직원 부르기가 조금 어려웠어요." if stars >= 4 else "서빙이 좀 늦었어요.") if "slow_service" in codes else
                    "친절하셨어요." if "friendly" in codes else
                    "서비스도 괜찮았어요." if stars >= 4 else "서비스는 보통이었어요."),
        "revisit": (f"별점은 {stars}점 줬어요. " + ("다시 올 거예요." if stars >= 4 else
                                                "다시 올지는 잘 모르겠어요." if stars == 3 else "다시 오진 않을 것 같아요.")),
        "general": f"별점 {stars}점 남겼어요. " + (r.get("text") or review_template(r, plan)) + ".",
    }[intent]
    return f"{who} {body}"


def ask_reviewer(r: dict, question: str, ctx: llm.RequestContext, plan: dict | None = None) -> dict:
    mock = reviewer_template(r, question, plan)
    prompt = (f"당신은 대학로 삼겹살집(가상)에 다녀간 손님입니다. 아래는 그날 실제로 겪은 일입니다. 이 사실만으로 "
              f"한국어 두세 문장으로 답하세요. 숫자는 아래에 있는 것만 씁니다. 별점과 어긋나는 불만은 말하지 마세요.\n"
              f"{json.dumps({**r, 'plan_prices': {k: (plan or {}).get(k) for k in ('meat_price', 'soju_price')}}, ensure_ascii=False)}\n\n"
              f"질문: {question}")
    res = llm.complete(prompt, ctx=ctx, mock_text=mock)
    text, backend = res.text, res.backend
    if res.backend != "mock" and invented(text, pool(r, question, VOCAB, plan)):
        text, backend = mock, f"{res.backend} (invented a number: template used)"
    return {"who": r["id"], "segment": r.get("segment"), "answer": text, "backend": backend, "cached": res.cached,
            "grounded_in": r}


# --- 4. 트윈 인터뷰 (survey) ---------------------------------------------------------------------------

def guide_questions() -> dict[int, str]:
    text = GUIDE.read_text(encoding="utf-8")
    return {int(n): q.strip() for n, q in re.findall(r"\*\*Q(\d+)\.\s*(.+?)\*\*", text)}


def sheet_rows() -> set[tuple[str, int]]:
    import csv
    with open(SHEET, encoding="utf-8-sig") as fh:
        return {(r["criterion_id"], int(r["question_no"])) for r in csv.DictReader(fh)}


RENT_BANDS = [(2_000_000, "① 200만원 미만"), (3_000_000, "② 200만~300만원"), (4_000_000, "③ 300만~400만원"),
              (5_000_000, "④ 400만~500만원"), (float("inf"), "⑤ 500만원 이상")]
BAND_SPOKEN = {"① 200만원 미만": "200만원이 안 되는", "② 200만~300만원": "200만에서 300만원 사이",
               "③ 300만~400만원": "300만에서 400만원 사이", "④ 400만~500만원": "400만에서 500만원 사이",
               "⑤ 500만원 이상": "500만원이 넘는"}
SURVEY_Q = [1, 3, 4, 7, 9, 10, 13, 14, 16, 17, 20, 22, 23, 24, 25]   # 15 of the guide's 25 questions


def _num(h: dict, k: str, part: str = "base_num"):
    return (h.get(k) or {}).get(part)


NATIVE = {1: "한", 2: "두", 3: "세", 4: "네", 5: "다섯", 6: "여섯", 7: "일곱", 8: "여덟", 9: "아홉", 10: "열"}
NATIVE_N = {1: "하나", 2: "둘", 3: "셋", 4: "넷", 5: "다섯", 6: "여섯", 7: "일곱", 8: "여덟", 9: "아홉", 10: "열"}
MONTHS_KO = {1: "한 달", 2: "두 달", 3: "석 달", 4: "넉 달", 5: "다섯 달", 6: "여섯 달"}
CLOSE_KO = {23: "밤 11시", 24: "자정", 25: "새벽 1시"}


def _round5(v: float) -> int:
    """How a person says minutes or percent: to the nearest 5, at least 5."""
    return max(5, int(5 * round(float(v) / 5)))


def _round_won(v: float, unit: int = 1000) -> int:
    return int(unit * round(float(v) / unit))


def survey(season: dict, hero: dict, reactions: dict[str, dict] | None = None) -> list[dict]:
    """The owner twin answers 15 interview-guide questions from its state. Each item carries answer-sheet rows
    (criterion_id, question_no, low/typical/high, unit) so a real interview can be compared row by row."""
    st = season.get("state") or {}
    plan = st.get("plan") or {}
    months = season.get("months") or []
    q = guide_questions()
    items = []

    def src(k):
        return (hero.get(k) or {}).get("source_id") or "가정"

    def item(n, text, rows, used):
        items.append({"guide_q": n, "question": q.get(n), "answer": text, "rows": rows, "used": used})

    def row(cid, n, typ, unit, low=None, high=None, conf="L"):
        return {"criterion_id": cid, "question_no": n, "answer_low": low, "answer_typical": typ, "answer_high": high,
                "unit": unit, "confidence": conf, "interviewer": "twin"}

    played = len(months)
    item(1, "개인으로 하는 가게예요. " + (f"이번 시즌 시작하고 {MONTHS_KO.get(played, '여러 달')}째 장사하고 있어요."
                                       if played else "이번 시즌은 이제 막 시작했어요."),
         [row("sto_franchise", 1, "개인", "범주(개인/프랜차이즈)", conf="H"), row("lbl_survival_months", 1, played, "개월")],
         [{"key": "sto_franchise", "value": (hero.get("sto_franchise") or {}).get("base"), "source": src("sto_franchise")},
          {"key": "months_played", "value": played, "source": "season state"}])

    days, hours = _num(hero, "sto_open_days"), _num(hero, "drv_open_hours")
    close = plan.get("close_hour")
    item(3, f"한 달에 {days:g}일쯤 열고, 저녁 {hours:g}시간 장사해요."
         + (f" 요즘은 {CLOSE_KO.get(close, '늦게')}에 닫아요." if close else "") + " 월요일은 쉬어요.",
         [row("sto_open_days", 3, days, "일/월", _num(hero, "sto_open_days", "low_num"), _num(hero, "sto_open_days", "high_num")),
          row("drv_open_hours", 3, hours, "시간/일", _num(hero, "drv_open_hours", "low_num"), _num(hero, "drv_open_hours", "high_num"))],
         [{"key": "sto_open_days", "value": days, "source": src("sto_open_days")},
          {"key": "drv_open_hours", "value": hours, "source": src("drv_open_hours")},
          {"key": "plan.close_hour", "value": close, "source": "season plan"}])

    party = _num(hero, "mkt_party_size")
    covers = [m["draw"]["kpis"].get("covers") for m in months if m.get("draw", {}).get("kpis", {}).get("covers")]
    if covers and days and party:
        teams = [round(c / days / party) for c in covers]
        t_typ, t_lo, t_hi = round(sum(teams) / len(teams)), min(teams), max(teams)
        txt = (f"보통 하루 저녁에 {t_typ}팀 정도 와요." + (f" 적을 땐 {t_lo}팀, 많을 땐 {t_hi}팀까지 와요." if t_hi > t_lo else "")
               + f" 한 팀은 {NATIVE.get(round(party), '두세')} 명이 제일 많아요.")
    else:
        t_typ = t_lo = t_hi = None
        txt = f"이번 시즌은 아직 한 달도 안 돼서 팀 수는 말씀드리기 어려워요. 한 팀은 {NATIVE.get(round(party), '두세')} 명이 제일 많아요."
    item(4, txt, [row("teams_per_night", 4, t_typ, "팀/일", t_lo, t_hi), row("mkt_party_size", 6, party, "명/팀")],
         [{"key": "month covers", "value": covers, "source": "season month results"},
          {"key": "sto_open_days", "value": days, "source": src("sto_open_days")},
          {"key": "mkt_party_size", "value": party, "source": src("mkt_party_size")}])

    seg_n = {s: 0 for s in SEGMENTS}
    for m in months:
        for r in m.get("reviews") or []:
            if r.get("segment") in seg_n:
                seg_n[r["segment"]] += 1
    tot = sum(seg_n.values())
    age20 = _num(hero, "reg_age_mix")
    who = {"twenties": "학생이나 20대 모임", "office": "직장인 회식", "family": "동네 가족"}
    tenth = NATIVE.get(max(1, round(age20 * 10)), "몇")
    if tot:
        mix = ":".join(str(seg_n[s]) for s in SEGMENTS)
        ranked = sorted(SEGMENTS, key=lambda k: -seg_n[k])
        if seg_n[ranked[0]] - seg_n[ranked[-1]] <= max(1, tot // 5):
            txt = "학생, 직장인, 가족 손님이 골고루 와요."
        else:
            txt = f"{who[ranked[0]]} 손님이 제일 많고, 그다음이 {who[ranked[1]]}이에요."
        txt += f" 이 동네는 손님 열 명 중 {tenth} 명 정도가 20대예요."
    else:
        mix = None
        txt = f"이 동네는 손님 열 명 중 {tenth} 명 정도가 20대고, 나머지는 직장인 회식이랑 동네 가족이에요."
    item(7, txt, [row("segment_mix", 7, mix, "학생:직장인:가족 비율 (raw)")],
         [{"key": "review segments", "value": seg_n, "source": "season reviews"},
          {"key": "reg_age_mix", "value": age20, "source": src("reg_age_mix")}])

    patience = _num(hero, "mkt_patience")
    waits = [r.get("wait_min") for m in months for r in (m.get("reviews") or []) if r.get("wait_min") is not None]
    walk = [m["draw"]["kpis"].get("walkaways") for m in months if m.get("draw", {}).get("kpis", {}).get("walkaways") is not None]
    said = {"patience": _round5(patience)}
    txt = f"손님들은 {said['patience']}분 정도 기다리다 안 되면 그냥 가세요."
    long_wait = max(waits) if waits else 0
    if long_wait >= 1:
        said["longest_wait"] = _round5(long_wait)
        txt += f" 이번 시즌엔 길어야 {said['longest_wait']}분 정도 기다리게 했어요."
    elif waits:
        txt += " 이번 시즌엔 거의 안 기다리고 바로 앉았어요."
    if walk:
        avg = sum(walk) / len(walk)
        txt += (" 그냥 돌아가는 팀은 거의 없어요." if avg < 1 else " 한 달에 한두 팀은 그냥 돌아가요." if avg < 3
                else " 한 달에 몇 팀은 자리가 없어서 그냥 돌아가요.")
    item(9, txt, [row("mkt_patience", 9, patience, "분", _num(hero, "mkt_patience", "low_num"), _num(hero, "mkt_patience", "high_num")),
                  row("walkaways_per_month", 9, round(sum(walk) / len(walk)) if walk else None, "팀/월")],
         [{"key": "mkt_patience", "value": patience, "source": src("mkt_patience")},
          {"key": "minutes as said (rounded to 5)", "value": said, "source": "계산"},
          {"key": "review wait_min", "value": waits, "source": "season reviews"},
          {"key": "month walkaways", "value": walk, "source": "season month results"}])

    idx = {m.get("calendar", {}).get("label"): m.get("calendar", {}).get("demand_index") for m in months
           if m.get("calendar", {}).get("demand_index")}
    vac = [v for k, v in idx.items() if k and (k.startswith("1월") or k.startswith("2월"))]
    peak = max(idx.items(), key=lambda kv: kv[1]) if idx else None
    pct_said = {}
    if idx:
        if vac:
            pct_said["vacation_drop_pct"] = _round5((1 - min(vac)) * 100)
            txt = f"방학 땐 평소보다 손님이 {pct_said['vacation_drop_pct']}% 정도 줄어요. "
        else:
            txt = "방학은 아직 안 지나 봐서 모르겠어요. "
        if peak[1] > 1.02:
            pct_said["peak_up_pct"] = _round5((peak[1] - 1) * 100)
            txt += f"제일 잘되는 건 {peak[0]}이고, 평소보다 {pct_said['peak_up_pct']}% 정도 더 와요."
        else:
            txt += f"지금까지는 {peak[0]}이 제일 나았어요."
    else:
        txt = "아직 지나 본 달이 없어서 달별 차이는 말씀드리기 어려워요."
    item(10, txt, [row("vacation_index", 10, round(min(vac) * 100) if vac else None, "평소=100 기준 방학 달 지수 (raw; becomes SH09)"),
                   row("peak_month_index", 10, round(peak[1] * 100) if peak else None, "평소=100 기준 최고 달 지수 (raw)")],
         [{"key": "calendar demand_index", "value": idx, "source": "season calendar (가정 unless sourced)"},
          {"key": "percent as said (rounded to 5)", "value": pct_said, "source": "계산"}])

    price = plan.get("meat_price", _num(hero, "prd_meat_price"))
    grams = _num(hero, "prd_portion_grams")
    item(13, f"삼겹살 1인분은 {grams:g}g에 {won(price)} 받고 있어요.",
         [row("prd_portion_grams", 13, grams, "g", conf="M"), row("prd_meat_price", 13, price, "₩/인분", conf="H")],
         [{"key": "plan.meat_price", "value": price, "source": "season plan"},
          {"key": "prd_portion_grams", "value": grams, "source": src("prd_portion_grams")}])

    soju = plan.get("soju_price", _num(hero, "prd_alcohol_price"))
    per = _num(hero, "prd_alcohol_per_cover")
    item(14, f"소주는 한 병 {won(soju)} 받아요. " + ("손님 한 분이 한 병 가까이 드세요." if 0.7 <= per < 1.2 else
                                                 "손님 한 분이 한 병은 넘게 드세요." if per >= 1.2 else "술은 생각보다 적게 드세요."),
         [row("prd_alcohol_price", 14, soju, "₩/병", conf="H"),
          row("prd_alcohol_per_cover", 14, per, "병/인", _num(hero, "prd_alcohol_per_cover", "low_num"), _num(hero, "prd_alcohol_per_cover", "high_num"))],
         [{"key": "plan.soju_price", "value": soju, "source": "season plan"},
          {"key": "prd_alcohol_per_cover", "value": per, "source": src("prd_alcohol_per_cover")}])

    tables, seats, area = _num(hero, "sto_tables"), _num(hero, "sto_seats_per_table"), _num(hero, "sto_area_pyeong")
    item(16, f"테이블 {tables:g}개에 다 {seats:g}인석이고, 가게는 {area:g}평쯤 돼요.",
         [row("sto_tables", 16, tables, "개"), row("sto_seats_per_table", 16, seats, "석/테이블"), row("sto_area_pyeong", 16, area, "평")],
         [{"key": k, "value": _num(hero, k), "source": src(k)} for k in ("sto_tables", "sto_seats_per_table", "sto_area_pyeong")])

    staff = plan.get("staff_per_shift", _num(hero, "sto_parttimers"))
    wage, shift = _num(hero, "sto_parttime_wage"), _num(hero, "sto_parttime_shift_hours")
    fatigue = st.get("fatigue")
    item(17, (f"저녁에 알바 {NATIVE.get(staff, staff)} 명이 {shift:g}시간씩 일하고, 시급은 {won(wage)} 줘요. " if staff
              else "요즘은 알바 없이 제가 혼자 해요. ") + "저도 홀에 계속 나가요."
             + ((" 요즘 애들이 많이 지쳐 보여서 걱정이에요." if fatigue >= 60 else " 아직은 다들 버틸 만해요.")
                if fatigue is not None else ""),
         [row("sto_parttimers", 17, staff, "명/교대", conf="H"), row("sto_parttime_shift_hours", 17, shift, "시간/일"),
          row("sto_parttime_wage", 17, wage, "₩/시간", conf="H")],
         [{"key": "plan.staff_per_shift", "value": staff, "source": "season plan"},
          {"key": "sto_parttime_wage", "value": wage, "source": src("sto_parttime_wage")},
          {"key": "state.fatigue", "value": fatigue, "source": "season state (가정)"}])

    cpp = _num(hero, "cst_meat_cost_per_portion")
    per_kg = round(cpp / grams * 1000) if cpp and grams else None
    grade = {"imported": "수입 냉동", "domestic": "국내산", "aged": "숙성"}.get(plan.get("meat_grade"), plan.get("meat_grade"))
    kg_said = _round_won(per_kg) if per_kg else None
    item(20, f"{grade or '국내산'} 삼겹살 받아 쓰는데, kg에 {won(kg_said)} 정도 해요. 1인분으로 치면 {won(_round_won(cpp, 100))}쯤이에요.",
         [row("meat_cost_per_kg", 20, per_kg, "₩/kg (raw; becomes cst_meat_cost_per_portion)")],
         [{"key": "cst_meat_cost_per_portion", "value": cpp, "source": src("cst_meat_cost_per_portion")},
          {"key": "prd_portion_grams", "value": grams, "source": src("prd_portion_grams")},
          {"key": "plan.meat_grade", "value": plan.get("meat_grade"), "source": "season plan"},
          {"key": "won as said (rounded)", "value": [kg_said, _round_won(cpp, 100)], "source": "계산"}])

    rent = _num(hero, "drv_rent")
    band = next(label for limit, label in RENT_BANDS if rent < limit)
    item(22, f"월세는 {BAND_SPOKEN[band]} 정도예요. 1층이라 비싸요. 장사가 안 돼도 그대로 나가는 돈이라 제일 무서워요.",
         [row("drv_rent", 22, rent, "₩/월 (구간 카드 번호도 quote에)", conf="M")],
         [{"key": "drv_rent", "value": rent, "source": src("drv_rent")}, {"key": "band", "value": band, "source": "guide Q22 card"}])

    card = _num(hero, "cst_card_share")
    item(23, f"열 명 중 {NATIVE_N.get(round(card * 10), '대부분')}은 카드로 내세요. 현금 내시는 분은 거의 없어요.",
         [row("cst_card_share", 23, card, "비율")],
         [{"key": "cst_card_share", "value": card, "source": src("cst_card_share")},
          {"key": "card payers per 10 customers", "value": round(card * 10), "source": "계산 (cst_card_share × 10)"}])

    reac = reactions or {}
    groups: dict[str, list[str]] = {}
    rows24 = []
    for sh in ("SH03", "SH08", "SH06", "SH09", "SH05", "SH11"):
        d = reac.get(sh)
        if d:
            groups.setdefault(d.get("label", d["action"]), []).append(d.get("shock_label", sh))
            rows24.append(row(f"owner_reaction.{sh}", 24, d["action"], "action id + 숫자"))
    if len(groups) == 1:
        (act, shocks), = groups.items()
        lines = [f"{', '.join(shocks[:-1])}, {shocks[-1]} 같은 일이 생겨도 일단은 {ro(act)} 갈 것 같아요"
                 if len(shocks) > 1 else f"{myeon(shocks[0])} {ro(act)} 갈 것 같아요"]
    else:
        lines = [f"{myeon(', '.join(sh))} {ro(act)} 갈 것 같아요" for act, sh in groups.items()]
    item(24, (". ".join(lines) + ".") if lines
         else "그런 일이 생기면 그때 가서 숫자를 보고 정할 것 같아요.", rows24,
         [{"key": "owner decide (confidence-gated rule pick)", "value": {k: v["action"] for k, v in reac.items()},
           "source": "web/public/runs + agents.owner"}])

    worst = min(months, key=lambda m: m.get("draw", {}).get("kpis", {}).get("op", 0)) if months else None
    worry = []
    if st.get("cash") is not None and st["cash"] < 5_000_000:
        worry.append("운영자금이 바닥나는 것")
    if fatigue is not None and fatigue >= 60:
        worry.append("직원들이 지쳐서 그만두는 것")
    if worst and worst["draw"]["kpis"].get("op", 0) < 0:
        worry.append(f"{worst.get('calendar', {}).get('label', '어느 달')} 같은 적자 달이 또 오는 것")
    if not worry:
        worry.append("임대료와 고기값이 계속 오르는 것")
    item(25, "요즘 제일 걱정되는 건 " + ", ".join(worry) + "이에요.", [row("owner_concern", 25, ", ".join(worry), "정성 메모")],
         [{"key": "state.cash", "value": st.get("cash"), "source": "season state"},
          {"key": "state.fatigue", "value": fatigue, "source": "season state (가정)"}])
    return items


def compare(items: list[dict], answer_sheet: Path) -> list[dict]:
    """Row-by-row comparison of a filled interview answer sheet (real owner) with the twin's survey rows."""
    import csv
    with open(answer_sheet, encoding="utf-8-sig") as fh:
        real = {(r["criterion_id"], int(r["question_no"])): r for r in csv.DictReader(fh) if r.get("question_no")}
    out = []
    for it in items:
        for r in it["rows"]:
            k = (r["criterion_id"], r["question_no"])
            rr = real.get(k, {})
            out.append({"criterion_id": k[0], "question_no": k[1], "twin_typical": r["answer_typical"],
                        "twin_low": r["answer_low"], "twin_high": r["answer_high"], "unit": r["unit"],
                        "real_typical": rr.get("answer_typical") or None, "real_low": rr.get("answer_low") or None,
                        "real_high": rr.get("answer_high") or None, "real_confidence": rr.get("confidence") or None,
                        "in_sheet": k in real})
    return out
