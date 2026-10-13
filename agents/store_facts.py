"""The numbers the owner chat may quote, as one tagged list: the prompt's [가게 숫자] block, the mock templates and
the no-invented-number check all read it, so a model and the offline mock say the same numbers as the game.

Each fact carries the tag an answer cites in brackets:
  S.. / D0930   a row of ontology/sources.csv (the hero value's first source id)
  평소 달        sim.season: the declared 평소 달 (baseline_month = the welcome tour's P&L) and one-lever steps from it
                (preview sensitivity = the tour's 1,000원 올리면 cards)
  시즌 기록      the season being played (last month's result and the cash left)
  가정           an assumption with no source (confidence L, to be replaced by the owner interview)
Ground truth for tests/chat_eval/questions.yaml.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from .ko import MINUS, eul, man_won, won_ko

REPO = Path(__file__).resolve().parents[1]
SIM_TAG, SEASON_TAG, ASSUME_TAG = "평소 달", "시즌 기록", "가정"
TAG_TITLES = {SIM_TAG: "시뮬레이션 평소 달: 외부 사건이 없는 10월, 기본 계획의 평균과 한 가지씩 바꿨을 때의 변화",
              SEASON_TAG: "이번 시즌 기록 (방금 끝난 달의 결과)",
              ASSUME_TAG: "팀 가정 (출처 없음, 사장님 인터뷰로 확인 예정)"}

# lever order and wording as the welcome tour cards say them (sim/tour.py LEVER_KO, STEP_VERB, STEP_UNIT)
LEVERS = ["meat_price", "soju_price", "staff_per_shift", "meat_grade", "close_hour", "banchan", "terrace", "lunch",
          "menu_extras", "marketing_budget", "review_event", "group_reservations", "hygiene", "staff_grilling"]


@dataclass(frozen=True)
class Fact:
    key: str
    label: str
    text: str
    tag: str = ""
    group: str = "store"
    value: object = field(default=None, compare=False)   # raw numbers the mock templates build sentences from

    def line(self) -> str:
        return f"- {self.label}: {self.text}" + (f" [{self.tag}]" if self.tag else "")


def won(v: float) -> str:
    """Money as every screen prints it: 10만원 and up in 만원, below that in 원."""
    v = float(v)
    return man_won(v) if abs(v) >= 1e5 else won_ko(v)


def signed_won(v: float) -> str:
    return man_won(v, plus=True) if abs(v) >= 1e4 else f"{'+' if v > 0 else MINUS if v < 0 else ''}{abs(round(v)):,}원"


def pct(x: float, d: int = 1) -> str:
    s = f"{x * 100:.{d}f}"
    return (s.rstrip("0").rstrip(".") if d else s) + "%"


def _num(h: dict | None):
    if not h:
        return None
    v = h.get("base_num") if h.get("base_num") is not None else h.get("base")
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _tag(h: dict | None) -> str:
    sid = (h or {}).get("source_id") or ""
    return sid.split(";")[0].strip() or ASSUME_TAG


def _n(v: float) -> str:
    return f"{v:,.0f}" if float(v).is_integer() else f"{v:,.2f}".rstrip("0").rstrip(".")


# --- defaults read from the sim and the processed public data (cached; the API may pass its own) ---

def _sim():
    try:
        import sim.season as S
        return S if callable(getattr(S, "baseline_month", None)) else None
    except Exception:  # noqa: BLE001 - sim/ unavailable: the P&L block is left out, never invented
        return None


def default_baseline() -> dict | None:
    S = _sim()
    return S.baseline_month() if S else None


@lru_cache(maxsize=1)
def default_sensitivity() -> dict:
    """One step up / down of every lever from the 평소 달 plan (op and covers), as on the tour cards."""
    S = _sim()
    if not S or not callable(getattr(S, "baseline_inputs", None)):
        return {}
    try:
        return S.preview(*S.baseline_inputs(), sensitivity=True, baseline=False).get("sensitivity") or {}
    except Exception:  # noqa: BLE001
        return {}


@lru_cache(maxsize=1)
def default_district() -> dict:
    """Pork-grill store count and survival tables from data/processed (what db.load puts in the district rows)."""
    out: dict = {}
    try:
        prof = json.loads((REPO / "data" / "processed" / "district_profile.json").read_text(encoding="utf-8"))
        t = prof["trdar"]["3120012"]
        out["pork_stores"] = t["sbiz_stores"]["I20107"]["stores"]
        out["pork_snapshot"] = t["sbiz_stores"].get("snapshot")
        out["narrow_all"] = (prof.get("survival") or {}).get("all_uptae_primary")
        wide = json.loads((REPO / "data" / "processed" / "survival_wide.json").read_text(encoding="utf-8"))
        out["wide_pork"] = wide.get("pork_name_only")
        out["wide_areas"] = wide.get("areas")
    except (OSError, KeyError, ValueError):
        pass
    return out


def _surv(table: dict | None, month: int) -> float | None:
    for r in (table or {}).get("table") or []:
        if r["month"] == month:
            return r["survival"]
    return None


def sensitivity_lines(sens: dict) -> list[dict]:
    """One row per lever whose step moves the profit, in the tour's wording: lever, name, line, big (|op| of the
    bigger step), step, up/down ({op, covers} or None), up_ko/down_ko ('1,000원 올리면')."""
    try:
        from sim.tour import LEVER_KO, STEP_UNIT, STEP_VERB
    except Exception:  # noqa: BLE001
        LEVER_KO, STEP_UNIT, STEP_VERB = {}, {}, {}
    out = []
    for lever in LEVERS:
        s = sens.get(lever)
        if not s or not (s.get("up") or s.get("down")):
            continue
        step = str(s.get("step") or "")
        digits = "".join(c for c in step if c.isdigit() or c == ",")
        if lever == "marketing_budget" and digits:
            step_ko = man_won(int(digits.replace(",", "")))
        elif digits:
            step_ko = f"{digits}{STEP_UNIT.get(lever, '')}"
        else:
            step_ko = "한 단계" if "단계" in step else ""
        if not step_ko:
            v_up, v_down = "켜면", "끄면"
        else:
            vu, vd = STEP_VERB.get(lever, ("올리면", "내리면"))
            v_up, v_down = f"{step_ko} {vu}", f"{step_ko} {vd}"
        parts, big = [], 0.0
        for verb, d in ((v_up, s.get("up")), (v_down, s.get("down"))):
            if not d:
                continue
            c = round(d.get("covers") or 0)
            who = "손님 변화 없음" if c == 0 else f"손님 {'+' if c > 0 else MINUS}{abs(c)}명"
            parts.append(f"{verb} 영업이익 {signed_won(d['op'])}, {who}")
            big = max(big, abs(d["op"]))
        if big >= 1:
            out.append({"lever": lever, "name": LEVER_KO.get(lever, lever), "line": " / ".join(parts), "big": big,
                        "step": step_ko or "켜고 끄기", "up": s.get("up"), "down": s.get("down"), "up_ko": v_up, "down_ko": v_down})
    return out


def build(hero: dict, baseline: dict | None = None, sens: dict | None = None, district: dict | None = None,
          season: dict | None = None) -> dict[str, Fact]:
    """key -> Fact. hero = hero_attribute rows by criterion_id (base/base_num/unit/source_id), with the season's
    current prices on top when a season is played. baseline/sens/district default to the sim and data/processed;
    season = {label, op, revenue, covers, cash, rating} of the month just played (None before any month)."""
    F: dict[str, Fact] = {}

    def add(key, label, text, tag="", group="store", value=None):
        F[key] = Fact(key, label, text, tag, group, value)

    h = lambda cid: hero.get(cid) or {}  # noqa: E731
    v = lambda cid: _num(hero.get(cid))  # noqa: E731
    b = baseline if baseline is not None else default_baseline()
    sens = sens if sens is not None else default_sensitivity()
    dist = district if district is not None else default_district()

    if b:
        rev, op = b["revenue"], b["op"]
        add("revenue", "평소 달 월 매출", won(rev), SIM_TAG, "pnl")
        owner_wage = v("cst_owner_imputed_wage")
        add("op", "평소 달 월 영업이익", f"{won(op)} (영업이익률 {pct(op / rev)}"
            + (f", 사장 몫 인건비 {eul(won(owner_wage))} 비용에 넣은 뒤)" if owner_wage else ")"), SIM_TAG, "pnl")
        add("margin", "평소 달 영업이익률", pct(op / rev), SIM_TAG, "pnl")
        days = v("sto_open_days")
        add("covers", "평소 달 월 손님 수", f"{b['covers']:,}명" + (f" (한 달 {days:.0f}일 영업)" if days else ""), SIM_TAG, "pnl")
        ticket = b.get("ticket")
        if ticket:
            parts = [(v("prd_meat_price"), v("prd_portions_per_cover"), "고기"), (v("prd_alcohol_price"), v("prd_alcohol_per_cover"), "소주")]
            formula = ""
            if all(p and q for p, q, _ in parts) and v("prd_side_spend_per_cover"):
                formula = (f" (고기 {_n(parts[0][1])}인분 {won_ko(parts[0][0])} + 소주 {_n(parts[1][1])}병 × {won_ko(parts[1][0])}"
                           f" + 식사·사이드 {won_ko(v('prd_side_spend_per_cover'))})")
            add("ticket", "객단가 (손님 한 명이 한 번에 쓰는 돈)", f"{won_ko(ticket)}{formula}", SIM_TAG, "pnl")
            if v("prd_alcohol_price") and v("prd_alcohol_per_cover"):
                add("alcohol_share", "매출 중 술 비중", pct(v("prd_alcohol_price") * v("prd_alcohol_per_cover") / ticket), SIM_TAG, "pnl")
        lines = [("labor", "인건비", ""), ("cogs", "식재료비", ""), ("rent", "임차료", ""),
                 ("mgmt", "관리비", "공과금·가스·숯·기타경비"), ("fees", "카드 수수료", "")]
        lines = sorted([(k, n, note, b[k]) for k, n, note in lines if b.get(k) is not None], key=lambda x: -x[3])
        for k, n, note, x in lines:
            extra = f", 사장 몫 {won(owner_wage)} 포함" if k == "labor" and owner_wage else f", {note}" if note else ""
            add(f"cost_{k}", f"평소 달 월 {n}", f"{won(x)} (매출의 {pct(x / rev)}{extra})", SIM_TAG, "pnl")
        if lines:
            add("cost_top", "가장 큰 비용", f"{lines[0][1]} {won(lines[0][3])}, 다음은 "
                + ", ".join(f"{n} {won(x)}" for _, n, _, x in lines[1:3]), SIM_TAG, "pnl", [(n, x) for _, n, _, x in lines])

    if v("prd_meat_price"):
        g = v("prd_portion_grams")
        add("meat_price", "삼겹살 1인분 판매가", won_ko(v("prd_meat_price")) + (f" ({g:.0f}g)" if g else ""), _tag(h("prd_meat_price")), "menu")
    if v("cst_meat_cost_per_portion"):
        add("meat_cost", "삼겹살 1인분 고기 원가", won_ko(v("cst_meat_cost_per_portion")), _tag(h("cst_meat_cost_per_portion")), "menu")
    if v("prd_alcohol_price"):
        add("soju_price", "소주 1병 판매가", won_ko(v("prd_alcohol_price")), _tag(h("prd_alcohol_price")), "menu")
    if v("cst_alcohol_cost_per_bottle"):
        add("soju_cost", "소주 1병 원가", won_ko(v("cst_alcohol_cost_per_bottle")), _tag(h("cst_alcohol_cost_per_bottle")), "menu")
    if v("prd_alcohol_per_cover"):
        add("soju_per_cover", "손님 한 명당 소주", f"{_n(v('prd_alcohol_per_cover'))}병", _tag(h("prd_alcohol_per_cover")), "menu")
    if v("prd_side_spend_per_cover"):
        add("side_spend", "손님 한 명당 식사·사이드 매출", won_ko(v("prd_side_spend_per_cover")), _tag(h("prd_side_spend_per_cover")), "menu")

    hours = v("drv_open_hours")
    try:
        from sim.params import SIM_ASSUMPTIONS as A
    except Exception:  # noqa: BLE001
        A = {}
    if hours:
        start = int(A.get("open_clock_min", 17 * 60) // 60)
        closed = {"mon": "월요일", "tue": "화요일", "sun": "일요일"}.get(A.get("closed_weekday"), "")
        add("hours", "영업시간", f"{start}시 개점, 하루 {hours:.0f}시간 영업 ({start + hours:.0f}시 마감)"
            + (f", {closed} 휴무" if closed else ""), _tag(h("drv_open_hours")), "ops")
    w = A.get("peak_hour_weights_17_21")
    if w and len(w) == 4:
        add("peak", "가장 바쁜 시간", f"저녁 19시~21시 (17시~21시 손님의 {pct(w[2] + w[3], 0)}가 이때 옴, 시간별 분포는 가정)", ASSUME_TAG, "ops")
    if v("reg_evening_share"):
        add("evening_share", "저녁(17시~24시) 매출 비중 (상권 한식 카드매출)", pct(v("reg_evening_share")), _tag(h("reg_evening_share")), "ops")
    if v("sto_tables"):
        seats = v("sto_seats_per_table")
        terr, avail, area = v("sto_terrace"), v("sto_terrace_availability"), v("sto_area_pyeong")
        add("tables", "테이블", f"{v('sto_tables'):.0f}개" + (f" (테이블당 {seats:.0f}석)" if seats else "")
            + (f", 야장 {terr:.0f}석 (펼 수 있는 날 {pct(avail, 0)})" if terr and avail else "")
            + (f", 매장 {area:.0f}평" if area else ""), _tag(h("sto_tables")), "ops")
    if v("sto_parttimers") is not None:
        txt = f"교대당 알바 {v('sto_parttimers'):.0f}명"
        if v("sto_parttime_shift_hours"):
            txt += f" (하루 {v('sto_parttime_shift_hours'):.0f}시간)"
        if v("sto_employees"):
            txt += f", 정직원 {v('sto_employees'):.0f}명" + (f" (월급 {won(v('cst_employee_wage'))})" if v("cst_employee_wage") else "")
        if A.get("owner_on_floor"):
            txt += f", 홀에서 같이 일하는 사장 {A['owner_on_floor']}명"
        add("staff", "직원", txt, _tag(h("sto_parttimers")), "ops")
    if v("sto_parttime_wage"):
        add("wage", "알바 시급", won_ko(v("sto_parttime_wage")), _tag(h("sto_parttime_wage")), "ops")
    if v("mkt_party_size"):
        add("party", "한 팀 평균 인원", f"{_n(v('mkt_party_size'))}명", _tag(h("mkt_party_size")), "customers")
    if v("reg_age_mix"):
        add("twenties", "20대 매출 비중 (상권 한식 카드매출)", pct(v("reg_age_mix")), _tag(h("reg_age_mix")), "customers")
    if v("mkt_price_elasticity"):
        e = v("mkt_price_elasticity")
        add("elasticity", "가격탄력성", f"{MINUS if e < 0 else ''}{_n(abs(e))} (가격을 10% 올리면 찾아오는 손님이 약 {_n(abs(e) * 10)}% 줄어듦)",
            _tag(h("mkt_price_elasticity")), "customers")
    if v("cst_card_fee_rate"):
        add("card", "카드", f"수수료율 {pct(v('cst_card_fee_rate'), 2)}"
            + (f", 손님 결제의 {pct(v('cst_card_share'), 0)}가 카드" if v("cst_card_share") else ""), _tag(h("cst_card_fee_rate")), "payment")
    tech = [n for cid, n in (("svc_qr_kiosk", "QR·키오스크"), ("mkt_waitlist_app", "웨이팅 앱"), ("mkt_delivery", "배달"))
            if (h(cid).get("base") or "").upper() == "N"]
    if tech:
        add("tech", "기술 도입 전 매장", f"{', '.join(tech)} 모두 안 함", _tag(h("mkt_delivery")), "ops")
    add("identity", "가게", "대학로(혜화역) 상권의 평범한 개인 삼겹살집을 공공데이터와 추정치로 만든 합성 매장, 실제 상호 없음")

    if dist.get("pork_stores"):
        add("competitors", "대학로(혜화역) 상권 돼지고기 구이집 수", f"{dist['pork_stores']}곳 (소상공인 상가정보)", "S20", "district")
    wp = dist.get("wide_pork")
    if wp and _surv(wp, 60) is not None:
        add("survival_pork", "고깃집 생존율 (종로구 전체와 신촌역 상권, 2015년 이후 문 연 고깃집 "
            f"{wp['n']}곳, 이름 기준)", f"2년 {pct(_surv(wp, 24))}, 3년 {pct(_surv(wp, 36))}, 5년 {pct(_surv(wp, 60))}"
            + (f", 24개월 안에 폐업 {pct(wp['share_closed_within_24m'])}" if wp.get("share_closed_within_24m") is not None else ""),
            "S21", "district")
    na = dist.get("narrow_all")
    if na and _surv(na, 60) is not None:
        add("survival_area", f"대학로 음식점 전체 생존율 (2015년 이후 인허가 {na['n']}곳)",
            f"5년 {pct(_surv(na, 60))}" + (f", 24개월 안에 폐업 {pct(na['share_closed_within_24m'])}" if na.get("share_closed_within_24m") is not None else ""),
            "S21", "district")
    rent = dist.get("rent") or {}
    if rent.get("hyehwa_per_m2") and rent.get("national_per_m2"):
        add("rent_compare", "혜화동 1층 소규모 상가 임대료 (㎡당 월)", f"{won_ko(rent['hyehwa_per_m2'])}, 전국 {won_ko(rent['national_per_m2'])}의 "
            f"{rent['hyehwa_per_m2'] / rent['national_per_m2']:.1f}배", "S52", "district")

    sl = sensitivity_lines(sens or {})
    for r in sl:
        add(f"sens_{r['lever']}", r["name"], r["line"], SIM_TAG, "levers", r)
    if sl:
        rank = sorted(sl, key=lambda r: -r["big"])
        add("sens_top", "영업이익을 가장 크게 움직이는 것", ", ".join(f"{r['name']} ({r['step']}에 {won(r['big'])})" for r in rank[:3]),
            SIM_TAG, "levers", rank)

    if season:
        lab = season.get("label") or "지난달"
        if season.get("op") is not None:
            add("season_op", f"{lab} 영업이익", ("적자 " + won(abs(season["op"]))) if season["op"] < 0 else won(season["op"]), SEASON_TAG, "season")
        if season.get("revenue") is not None:
            add("season_revenue", f"{lab} 매출", won(season["revenue"]), SEASON_TAG, "season")
        if season.get("covers") is not None:
            add("season_covers", f"{lab} 손님 수", f"{round(season['covers']):,}명", SEASON_TAG, "season")
        if season.get("cash") is not None:
            add("season_cash", "지금 운영자금", won(season["cash"]), SEASON_TAG, "season")
        if season.get("rating") is not None:
            add("season_rating", "지금 평점", f"{float(season['rating']):.2f}", SEASON_TAG, "season")
    return F


GROUPS = [("season", "이번 시즌 (방금 끝난 달)"), ("pnl", "평소 달 손익 (외부 사건이 없는 10월, 기본 계획, 시뮬레이션 평균)"),
          ("menu", "메뉴와 원가"), ("ops", "영업과 직원"), ("customers", "손님"), ("payment", "결제"),
          ("district", "상권 (대학로)"), ("levers", "평소 달에서 하나만 바꿀 때 영업이익과 손님 변화 (시뮬레이션)"), ("store", "가게")]


def block(F: dict[str, Fact]) -> str:
    """The [가게 숫자] prompt block, grouped."""
    out = []
    for g, title in GROUPS:
        rows = [f.line() for f in F.values() if f.group == g]
        if rows:
            out.append(f"== {title} ==\n" + "\n".join(rows))
    return "\n".join(out)


def text(F: dict[str, Fact], key: str, default: str = "?") -> str:
    return F[key].text if key in F else default


def cite(F: dict[str, Fact], *keys: str) -> str:
    """' [S52]' style tag(s) for the facts a sentence used (deduplicated, in order)."""
    tags = []
    for k in keys:
        t = F[k].tag if k in F else ""
        if t and t not in tags:
            tags.append(t)
    return "".join(f" [{t}]" for t in tags)


def short(F: dict[str, Fact], key: str, default: str = "?") -> str:
    """The fact's value without its parenthesised note: '470만원 (매출의 18%)' -> '470만원'."""
    return F[key].text.split(" (")[0] if key in F else default


def paren(F: dict[str, Fact], key: str) -> str:
    """The first parenthesised note of the fact ('' when none): '470만원 (매출의 18%)' -> '매출의 18%'."""
    t = F[key].text if key in F else ""
    if " (" not in t:
        return ""
    inner, depth = [], 0
    for ch in t.split(" (", 1)[1]:
        if ch == "(":
            depth += 1
        elif ch == ")":
            if depth == 0:
                break
            depth -= 1
        inner.append(ch)
    return "".join(inner)
