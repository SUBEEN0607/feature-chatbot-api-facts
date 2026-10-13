"""Persona chat: RAG-grounded, numbers only from the tagged store facts (agents/store_facts.py) or the given sim result.

One LLM call per request (agents/llm.py). The mock backend answers with a deterministic Korean template built
from the same facts, so the demo works with no model at all. A real model's answer is checked with
agents.numbers: an answer with a number that is in none of its inputs is replaced by the template, and when the
backend is down the template answers too (marked in `backend`, so the web labels it a practice answer).
Measured by tests/chat_eval (python -m tests.chat_eval.run).
"""
from __future__ import annotations

import os
import re

from . import llm
from . import store_facts as SF
from .ko import eun, ga, ieyo, ira, ro
from .numbers import invented, pool

PERSONAS = {
    "owner": ("사장님", "대학로(혜화역)에서 독립 삼겹살집을 하는 사장님 (가상의 composite 매장, 실제 상호 없음). "
              "구어체 존댓말로 솔직하게 말하고, 원가·인건비·임대료·손님 흐름을 늘 걱정한다."),
    "customer_20s": ("20대 손님", "대학로에 자주 오는 20대 손님. 가격, 분위기, 후기, 친구들과의 술자리를 중시한다."),
    "customer_office": ("직장인 손님", "혜화 인근 직장인 회식 손님. 단체석, 빠른 서빙, 대기 시간을 중시한다."),
    "customer_family": ("가족 손님", "동네 가족 손님. 고기 품질, 청결, 주말 저녁 대기 시간을 중시한다."),
    "staff": ("알바생", "홀과 굽기를 맡는 아르바이트생. 피크 시간 동선, 대기 손님 응대, 근무 시간과 시급을 이야기한다."),
}

SIM_KPIS = {"op": ("월 영업이익", "원"), "revenue": ("월 매출", "원"), "covers": ("월 손님 수", "명"),
            "walkaways": ("월 대기 이탈", "팀"), "avg_wait_min": ("평균 대기", "분")}

won = SF.won


def facts(hero: dict, **kw) -> dict[str, str]:
    """label -> value text of every fact the prompt gives the model (tests check answers against these)."""
    return {f.label: f.text for f in SF.build(hero, **kw).values()}


def sim_lines(sim: dict | None) -> list[str]:
    if not sim:
        return []
    lines = []
    for k, (label, unit) in SIM_KPIS.items():
        b, a = sim.get("before", {}).get(k), sim.get("after", {}).get(k)
        if b is None or a is None:
            continue
        f = (lambda v: won(v)) if unit == "원" else (lambda v: f"{v:,.0f}{unit}")
        if f(b) == f(a):
            lines.append(f"{eun(label)} {f(b)} 그대로")
        else:
            lines.append(f"{label} {f(b)}에서 {ro(f(a))}")
    return lines


def _label(h: dict) -> str:
    if h.get("source_id"):
        return h["source_id"]
    stem = h["doc_id"].rsplit("/", 1)[-1].rsplit(".", 1)[0]
    return re.sub(r"^\d{4}-\d{2}-\d{2}-", "", stem)


def build_prompt(persona: str, message: str, hits: list[dict], F: dict[str, SF.Fact], sim: dict | None,
                 context_note: str) -> str:
    name, desc = PERSONAS[persona]
    ctx = "\n\n".join(f"[{_label(h)}] {h['text'][:700]}" for h in hits) or "(없음)"
    simtxt = "\n".join(f"- {l}" for l in sim_lines(sim))
    return f"""역할: {desc}
당신은 '{name}'입니다. 가게를 보러 온 분의 질문에 한국어 구어체 존댓말로 2~4문장으로 답합니다.

규칙:
1. 질문에 대한 답을 첫 문장에 바로 말합니다. 숫자를 물으면 숫자부터 말합니다.
2. 숫자는 아래 [가게 숫자], [시뮬레이션 결과], [근거 자료]에 적힌 것만 그대로 씁니다. 더하기, 곱하기, 12를 곱한 연간 금액처럼 계산으로 새 숫자를 만들지 않습니다.
3. 숫자를 쓴 문장 끝에는 그 숫자가 있던 줄의 대괄호 태그를 그대로 붙입니다. 예: 월 임차료는 470만원이에요 [평소 달].
4. 자료에 답이 없으면 "그건 제가 가진 자료에 없어서 모르겠어요"라고 말하고 숫자를 대지 않습니다. 날씨 예보, 투자, 다른 가게 이야기처럼 이 가게와 상관없는 질문도 같습니다.
5. '평소 달'은 외부 사건이 없는 10월을 시뮬레이션한 평균입니다. [가게 숫자]에 이번 시즌 기록이 있으면 '지난달', '요즘', '이번 달'은 시즌 기록으로 답하고, 그 밖의 질문은 평소 달 숫자로 답합니다.
6. 이 가게는 여러 자료로 만든 합성 매장이라 실제 상호가 없습니다. 실제 가게 이름, 실존 인물, 회사 이름은 말하지 않습니다.
7. '시뮬레이션', '모델', '데이터' 같은 말 대신 "계산해 보면", "평소 달이면"처럼 사장님 말투로 말합니다. 대시, 화살표, 별표 같은 기호는 쓰지 않습니다. 모든 숫자는 검토 전 추정치입니다.

[상황]
{context_note or '평상시'}

[가게 숫자]
{SF.block(F)}
{f"{chr(10)}[시뮬레이션 결과 (이번 사건, 중앙값, 사건 전에서 후)]{chr(10)}{simtxt}{chr(10)}" if simtxt else ""}
[근거 자료]
{ctx}

[질문]
{message}"""


# --- mock backend: intent-aware templates over the same facts ---

INTENTS = [  # (intent, keywords), first match wins; order puts the specific before the general
    ("name", ["가게 이름", "이름이 뭐", "상호"]),
    ("data", ["어떻게 아", "근거", "출처", "데이터", "자료", "믿을"]),
    ("why", ["왜", "이유", "결정", "그렇게 하"]),
    ("annual", ["작년", "연간", "1년", "일 년", "일년", "재작년", "올해 전체"]),
    ("delivery", ["배달"]),
    ("tech", ["단말기", "키오스크", "포스", "태블릿", "기계", "테이블링", "웨이팅 앱", "줄서기 앱", "원격 줄서기"]),
    ("payment", ["수수료", "카드", "결제"]),
    ("survival", ["생존", "폐업", "문 닫", "문을 닫", "망하", "살아남"]),
    ("weather", ["비 ", "비가", "비 오", "날씨", "장마", "야장"]),
    ("competitors", ["몇 곳", "몇 군데", "몇 개나 있", "고깃집이 몇", "구이집이 몇"]),
    ("competitor", ["경쟁", "새로 생기", "근처에", "옆 가게"]),
    ("rent", ["임대료", "월세", "임차", "건물주"]),
    ("labor_cost", ["인건비"]),
    ("staff", ["알바", "최저임금", "시급", "직원", "사람을", "인력"]),
    ("alcohol", ["소주", "술", "주류", "맥주"]),
    ("drivers", ["좌우", "제일 크게", "가장 크게", "영향이 큰", "영향이 제일", "레버", "핵심", "무엇이 이익", "뭐가 이익",
                 "이익을 올리", "이익을 늘리", "이익을 높이"]),
    ("margin", ["이익률", "마진", "퍼센트", "몇 프로", "%"]),
    ("ticket", ["객단가", "한 명당", "한 분당", "인당", "얼마 쓰"]),
    ("food_cost", ["식재료비", "재료비"]),
    ("cost_mix", ["큰 비용", "부담되는 비용", "제일 부담", "가장 부담", "비용은", "비용이 뭐", "어디에 돈", "돈이 많이"]),
    ("cost", ["원가", "도매가", "돼지고기 값", "고기 값", "고기값", "재료", "비용"]),
    ("price", ["가격", "올리", "내리", "인상", "인하", "할인"]),
    ("hours", ["몇 시부터", "몇 시까지", "영업시간", "영업 시간", "문 열", "문을 열", "몇 시에", "마감", "쉬는 날", "휴무"]),
    ("busy", ["바쁜", "시간대", "몇 시", "저녁", "피크", "웨이팅", "대기"]),
    ("tables", ["테이블", "좌석", "몇 석", "평수", "몇 평"]),
    ("party", ["몇 명이서", "몇 분이서", "일행", "한 팀"]),
    ("covers", ["손님이 몇", "손님 수", "몇 명 와", "몇 명이나 와", "몇 분이 오", "몇 분 오", "몇 명 오"]),
    ("customers", ["손님", "고객", "누가", "어떤 분", "방학", "학생", "직장인", "가족"]),
    ("season", ["지난달", "지난 달", "이번 달", "요즘", "운영자금", "현금", "잔고", "통장"]),
    ("profit", ["남으", "남아", "남는", "이익", "벌", "수익", "매출"]),
]
# words that make an unmatched question still about the store (answered with the overview, not "모르겠어요")
DOMAIN = ["가게", "장사", "사장", "고기", "삼겹", "메뉴", "대학로", "혜화", "식당", "음식", "맛", "운영", "어떠세요", "어때요"]
OFFTOPIC = re.compile(r"(내일|오늘|모레|이번 ?주|주말).{0,8}날씨|날씨.{0,6}(알려|예보)|비트코인|코인|주식|부동산 투자|로또|대통령|선거|"
                      r"축구|야구|연애|영화 추천|숙제")


def classify(message: str) -> str:
    m = f"{message} "
    if OFFTOPIC.search(m) and not any(k in m for k in ("장사", "손님", "매출", "야장")):
        return "unknown"
    for intent, kws in INTENTS:
        if any(k in m for k in kws):
            return intent
    return "general" if any(k in m for k in DOMAIN) else "unknown"


def _lever(F: dict, lever: str, up: bool) -> str:
    """'삼겹살 1인분을 1,000원 올리면 한 달 영업이익이 24만원 늘고 손님은 37명 줄어요' from the sim step."""
    f = F.get(f"sens_{lever}")
    r = f.value if f else None
    d = (r or {}).get("up" if up else "down")
    if not d:
        return ""
    verb = r["up_ko" if up else "down_ko"]
    op, c = d["op"], round(d.get("covers") or 0)
    who = "손님 수는 그대로예요" if c == 0 else f"손님은 {abs(c)}명 {'늘어요' if c > 0 else '줄어요'}"
    return f"평소 달 기준으로 {r['name']} {verb} 한 달 영업이익이 {won(abs(op))} {'늘고' if op > 0 else '줄고'} {who}{SF.cite(F, f'sens_{lever}')}."


def mock_answer(persona: str, message: str, hits: list[dict], F: dict[str, SF.Fact], sim: dict | None,
                context_note: str) -> str:
    t = lambda k: SF.text(F, k)  # noqa: E731
    s = lambda k: SF.short(F, k)  # noqa: E731
    c = lambda *k: SF.cite(F, *k)  # noqa: E731
    intent = classify(message)
    sl = sim_lines(sim)
    sim_by = {line.split(" ", 2)[0] + " " + line.split(" ", 2)[1] if line.startswith("월 ") else line.split(" ")[0]: line
              for line in sl}
    pick = lambda *names: [sim_by[n] for n in names if n in sim_by]  # noqa: E731
    note = (context_note or "").strip()
    situation = (f" {note}" if note.endswith(("요.", "다.")) else f" 지금은 {note}입니다.") if note else ""
    top = _label(hits[0]) if hits else None

    def sim_sentence(*names) -> str:
        lines = [x for x in (pick(*names) or sl[:2]) if not x.endswith(" 그대로")]
        return (" 이번 일로 계산해 보면 " + ", ".join(lines) + " 바뀌어요.") if lines else ""

    season = "season_op" in F
    up = not any(k in message for k in ("내리", "인하", "할인", "줄이", "빼", "낮추"))

    if persona == "owner":
        if intent == "season" and not season:
            intent = "general"          # no season played (the v1 chat): the store overview and its 평소 달
        body = {
            "unknown": "그건 제가 가진 가게 자료에는 없는 내용이라 모르겠어요. 매출, 비용, 손님, 가격처럼 가게 이야기라면 "
                       "숫자로 말씀드릴 수 있어요.",
            "name": "가게 이름은 따로 없어요. 대학로(혜화역) 상권의 평범한 개인 삼겹살집을 공공데이터와 추정치로 만든 "
                    "합성 매장이라 실제 상호가 없어요.",
            "annual": f"연간 실적은 자료가 없어서 모르겠어요. 제가 가진 건 한 달 숫자예요. 외부 사건이 없는 평소 달이면 "
                      f"한 달 매출 {s('revenue')}, 영업이익 {s('op')} 정도예요{c('revenue')}.",
            "delivery": f"배달은 안 해요. {t('tech')}인 기술 도입 전 매장이에요{c('tech')}.",
            "tech": (f"테이블링 같은 웨이팅 앱도 키오스크나 결제 단말기처럼 이번 분석에서 일부러 뺀 기술 도입 주제예요{c('tech')}. "
                     f"지금은 테이블 {s('tables')}로 저녁 피크를 받는데, 줄이 길어지면 기다리다 그냥 가시는 손님이 생겨요."
                     f"{sim_sentence('월 대기', '월 손님')}"
                     if any(k in message for k in ("테이블링", "웨이팅", "줄서기")) else
                     f"키오스크나 결제 단말기를 바꾸는 건 이번 분석에서 일부러 뺀 주제예요{c('tech')}. 지금은 원가, 가격, 사람, "
                     "임대료 같은 기본 손익부터 버틸 수 있는지가 먼저라서요."),
            "payment": f"카드는 {t('card')}예요{c('card')}. 평소 달 카드 수수료는 한 달 {s('cost_fees')} 정도라 "
                       f"비용 중에선 작은 편이에요{c('cost_fees')}.",
            "survival": (f"{eun(F['survival_pork'].label)} {ieyo(t('survival_pork'))}{c('survival_pork')}. "
                         f"{eun(F['survival_area'].label)} {ieyo(t('survival_area'))}{c('survival_area')}. "
                         f"대학로에만 돼지고기 구이집이 {s('competitors')} 있어서 버티는 게 쉽지 않아요{c('competitors')}."
                         if "survival_pork" in F and "survival_area" in F else
                         "생존율 자료는 지금 불러오지 못해서 모르겠어요."),
            "weather": f"야장 좌석이 있는데 비가 오면 그 자리가 통째로 빠져요. 테이블은 {ieyo(t('tables'))}{c('tables')}."
                       f"{sim_sentence('월 손님', '월 매출')}",
            "competitors": f"대학로(혜화역) 상권에만 돼지고기 구이집이 {s('competitors')} 있어요{c('competitors')}. "
                           "그래서 저녁 손님을 서로 나눠 가져요.",
            "competitor": f"이 상권에만 돼지고기 구이집이 {s('competitors')} 있어요{c('competitors')}. 한 곳이 더 생기면 저녁 "
                          f"손님이 나눠지는 게 제일 걱정이에요.{sim_sentence('월 손님', '월 영업이익')}",
            "rent": f"월 임차료는 {ieyo(s('cost_rent'))}, {SF.paren(F, 'cost_rent')}{c('cost_rent')}. 매출이 줄어도 그대로 나가는 "
                    "고정비라 제일 무서워요."
                    + (f" 혜화동 1층 상가 임대료는 ㎡당 월 {t('rent_compare')}예요{c('rent_compare')}." if "rent_compare" in F else "")
                    + sim_sentence("월 영업이익"),
            "labor_cost": f"평소 달 인건비가 한 달 {ieyo(s('cost_labor'))}, {SF.paren(F, 'cost_labor')}{c('cost_labor')}. "
                          f"직원은 {ieyo(t('staff'))}{c('staff')}.{sim_sentence('월 영업이익', '월 대기')}",
            "staff": (_lever(F, "staff_per_shift", True) + f" 지금은 {t('staff')}로 돌리고 있어요{c('staff')}."
                      if any(k in message for k in ("더 뽑", "더 쓰", "늘리", "한 명 더", "추가")) else
                      _lever(F, "staff_per_shift", False) + " 사람을 줄이면 피크에 서빙이 밀릴까 봐 걱정이에요."
                      + sim_sentence("월 영업이익", "월 대기")
                      if any(k in message for k in ("줄이", "빼", "덜 쓰")) else
                      f"직원은 {ieyo(t('staff'))}{c('staff')}. 알바 시급은 {ieyo(t('wage'))}{c('wage')}."
                      + sim_sentence("월 영업이익", "월 대기")),
            "alcohol": (_lever(F, "soju_price", up) + f" 지금 소주는 한 병 {t('soju_price')}에 팔아요{c('soju_price')}."
                        + sim_sentence("월 영업이익", "월 매출")
                        if any(k in message for k in ("가격", "올리", "내리", "인상", "인하", "값")) else
                        f"소주는 병당 {t('soju_price')}에 팔고 원가는 {ieyo(t('soju_cost'))}{c('soju_price', 'soju_cost')}. 손님 한 분이 "
                        f"평균 {t('soju_per_cover')} 정도 드셔서 매출의 {ga(t('alcohol_share'))} 술이에요{c('alcohol_share')}."
                        + sim_sentence("월 영업이익", "월 매출")),
            "drivers": f"영업이익을 가장 크게 움직이는 건 {t('sens_top')} 순이에요{c('sens_top')}. "
                       + _lever(F, "staff_per_shift", True),
            "margin": f"평소 달 영업이익률은 {ieyo(t('margin'))}{c('margin')}. 한 달 매출 {s('revenue')}에서 "
                      f"{s('op')}이 남는 거예요.",
            "ticket": f"손님 한 분이 한 번에 쓰시는 객단가는 {ieyo(s('ticket'))}{c('ticket')}. {ro(SF.paren(F, 'ticket'))} 이루어져요.",
            "food_cost": f"평소 달 식재료비는 한 달 {ieyo(s('cost_cogs'))}, {SF.paren(F, 'cost_cogs')}{c('cost_cogs')}. "
                         f"고기 1인분 원가가 {ira(t('meat_cost'))} 고기값이 제일 커요{c('meat_cost')}.",
            "cost_mix": (f"제일 부담되는 건 {ieyo(F['cost_top'].value[0][0])}. 평소 달 기준으로 {t('cost_top')} 순이에요{c('cost_top')}."
                         + sim_sentence("월 영업이익") if "cost_top" in F else "비용 자료를 지금 불러오지 못해서 모르겠어요."),
            "cost": f"고기 1인분 원가가 {t('meat_cost')}이고 판매가는 {ieyo(s('meat_price'))}{c('meat_cost', 'meat_price')}. "
                    f"도매가가 오르면 남는 몫이 먼저 줄어요.{sim_sentence('월 영업이익')}",
            "price": f"고기 1인분은 {s('meat_price')} 받고 있어요{c('meat_price')}. " + _lever(F, "meat_price", up)
                     + sim_sentence("월 손님", "월 매출"),
            "hours": f"{ieyo(t('hours'))}{c('hours')}.",
            "busy": f"제일 바쁜 시간은 {ieyo(s('peak'))}{c('peak')}. 매출의 {ga(t('evening_share'))} 저녁에 나오고{c('evening_share')}, "
                    f"테이블 {ga(s('tables'))} 이때 거의 다 차요.{sim_sentence('월 손님', '월 대기')}",
            "tables": f"테이블은 {ieyo(t('tables'))}{c('tables')}.",
            "party": f"한 팀은 평균 {ieyo(t('party'))}{c('party')}.",
            "covers": f"평소 달이면 한 달에 손님이 {s('covers')} 정도 앉으세요{c('covers')}. {SF.paren(F, 'covers')} 기준이에요."
                      + (f" 이번 시즌 {F['season_covers'].label}는 {ieyo(t('season_covers'))}{c('season_covers')}."
                         if "season_covers" in F else ""),
            "customers": f"상권 한식 매출의 {ga(t('twenties'))} 20대에서 나오고{c('twenties')}, 직장인 회식과 동네 가족 손님이 "
                         f"나머지를 채워요. 한 팀은 평균 {ieyo(t('party'))}{c('party')}.{sim_sentence('월 손님')}",
            "season": (f"{note} " if note else "") + (
                f"{F['season_revenue'].label}은 {ieyo(t('season_revenue'))}{c('season_revenue')}. " if "season_revenue" in F else "")
                + f"지금 고기 1인분은 {s('meat_price')} 받고 있고{c('meat_price')}, 외부 사건이 없는 평소 달이면 영업이익이 "
                f"{s('op')} 정도예요{c('op')}.",
            "profit": f"외부 사건이 없는 평소 달이면 한 달 매출은 {s('revenue')}, 영업이익은 {t('op')} 정도예요{c('revenue')}."
                      + (f" 이번 시즌 {eun(F['season_op'].label)} {ieyo(t('season_op'))}{c('season_op')}." if season else "")
                      + sim_sentence("월 영업이익", "월 매출"),
            "why": f"선택지마다 시뮬레이션 결과를 비교해 보고, 손님과 이익이 어떻게 움직이는지 확인한 다음 정했어요."
                   f"{sim_sentence('월 영업이익', '월 손님')}",
            "data": "가게 숫자는 공공데이터(상권분석 매출, 점포, 인허가 기록)와 출처를 단 추정치로 만든 거예요. "
                    "추정치는 팀원이 검토하기 전까지 예시 값이에요.",
            "general": f"테이블 {s('tables')}에 삼겹살 1인분 {s('meat_price')}, 소주 한 병 {t('soju_price')}을 받고 있어요"
                       f"{c('tables', 'meat_price', 'soju_price')}. 평소 달이면 한 달에 {s('op')} 정도 남아요{c('op')}."
                       f"{sim_sentence('월 영업이익', '월 매출')}",
        }[intent]
        # the situation line (season so far, or this month's event) goes with the answers it is about
        keep = intent in ("general", "why") or bool(sl) and intent not in ("unknown", "name")
        text = body + (situation if keep and intent != "season" else "")
    elif persona == "staff":
        text = (f"홀이랑 고기 굽기 맡고 있는 알바예요. 직원은 {ieyo(t('staff'))}{c('staff')}. 시급은 {ieyo(t('wage'))}{c('wage')}."
                f"{situation}{sim_sentence('월 대기', '월 손님')}")
    else:
        who = {"customer_20s": "대학로 자주 오는 20대", "customer_office": "근처 회사 다니는 직장인",
               "customer_family": "동네 사는 가족 손님"}[persona]
        text = (f"{ieyo(who)}. 이 집은 삼겹살 1인분 {s('meat_price')}, 소주 {t('soju_price')}이고{c('meat_price', 'soju_price')}, "
                f"상권에 돼지고기 구이집이 {s('competitors')} 있어서 비교하면서 와요{c('competitors')}.{situation}{sim_sentence('월 손님')}")
    if "[" not in text and top and intent not in ("unknown", "name"):
        text += f" 참고한 자료는 [{top}] 이에요."
    return text


# --- real backend output ---

_DASH = re.compile(r"\s*[—–]\s*")


_TAG = re.compile(r"\s*\[([^\]\n]{1,40})\]")


def tidy(text: str, tags: set[str] | None = None) -> str:
    """House style for model text (Korean UI): no em/en dashes, arrows or markdown emphasis. With `tags`, a bracketed
    tag that is not one of them (a prompt section name such as [상황], [근거 자료], [가게 숫자]) is removed."""
    t = text.replace("**", "").replace("→", "에서 ").replace("->", "에서 ")
    if tags is not None:
        t = _TAG.sub(lambda m: m.group(0) if m.group(1).strip() in tags else "", t)
        t = re.sub(r",(\s*[.!?]|\s*$)", r"\1", t)        # '[S36], [상황].' leaves no dangling comma
    return _DASH.sub(", ", t).strip()


def citations(text: str, hits: list[dict], F: dict[str, SF.Fact], titles: dict[str, str] | None = None) -> list[dict]:
    """The facts' sources the answer cites in brackets (first), then the retrieved chunks."""
    hit_rows = [{"source_id": h.get("source_id"), "doc_id": h["doc_id"], "label": _label(h), "title": h.get("title"),
                 "section": h.get("section"), "score": h["score"]} for h in hits]
    have = {r["label"] for r in hit_rows}
    tags = {f.tag for f in F.values() if f.tag}
    out = []
    for tag in dict.fromkeys(re.findall(r"\[([^\]]+)\]", text)):
        if tag in tags and tag not in have:
            is_src = bool(re.fullmatch(r"[SD]\d+", tag))
            out.append({"source_id": tag if is_src else None, "doc_id": f"facts#{tag}", "label": tag,
                        "title": (titles or {}).get(tag) or SF.TAG_TITLES.get(tag) or tag, "section": "가게 숫자",
                        "score": None})
    return out + hit_rows


def answer(ctx: llm.RequestContext, persona: str, message: str, hits: list[dict], hero: dict,
           sim: dict | None = None, context_note: str = "", numbers_from: list[str] | None = None,
           district: dict | None = None, season: dict | None = None) -> dict:
    if persona not in PERSONAS:
        raise ValueError(f"unknown persona {persona!r}; choose from {sorted(PERSONAS)}")
    F = SF.build(hero, district=district, season=season)
    prompt, mock = _prepare(persona, message, hits, F, sim, context_note)
    try:
        res = llm.complete(prompt, ctx=ctx, mock_text=mock)
    except llm.LLMBackendError as e:   # model down or overloaded: the template answers, marked as such
        res = llm.LLMResult(mock, f"{os.environ.get('LLM_BACKEND', 'mock')} (unavailable: template used)",
                            f"template ({str(e)[:120]})", False, 0, llm.session_cap())
    text, backend = res.text, res.backend
    if not backend.startswith("mock") and "template used" not in backend:
        text = tidy(text, {f.tag for f in F.values() if f.tag} | {_label(h) for h in hits})
        bad = invented(text, pool(SF.block(F), sim_lines(sim), context_note, message,
                                  [h["text"] for h in hits], ["2~4", "12"]))
        if bad:
            text, backend = mock, f"{backend} (invented a number {bad[0]}: template used)"
    cites = citations(text, hits, F)
    return {"persona": persona, "answer": text, "backend": backend, "model": res.model,
            "cached": res.cached, "calls_used": res.calls_used, "cap": res.cap,
            "sources": cites[len(cites) - len(hits):] if hits else [],   # the retrieved chunks
            "citations": cites,                                           # + the fact sources the answer cites
            "numbers_from": numbers_from or ["research/hero_base.yaml"]}


def _prepare(persona, message, hits, F, sim, context_note) -> tuple[str, str]:
    return (build_prompt(persona, message, hits, F, sim, context_note),
            mock_answer(persona, message, hits, F, sim, context_note))


def prepare(persona: str, message: str, hits: list[dict], hero: dict, sim: dict | None = None,
            context_note: str = "", district: dict | None = None, season: dict | None = None) -> tuple[str, str]:
    """(prompt, mock answer) exactly as answer() sends them; agents/prewarm.py uses this to list cache keys."""
    return _prepare(persona, message, hits, SF.build(hero, district=district, season=season), sim, context_note)
