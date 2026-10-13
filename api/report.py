"""End-of-season improvement report (GAME-V2-SPEC §14): JSON, CSV, printable HTML and Q&A over the season's
own rows. The numbers come from sim.report (season_table, improvements, good_decisions, luck_months,
season_summary); this module only shapes, formats and answers from them. Built once per (season, months played,
review counts) and memoised, since the counterfactuals re-run the season.
"""
from __future__ import annotations

import csv
import html
import io
import json
import re
import threading
from collections import OrderedDict

from agents import llm
from agents.ko import eul, eun, ieyo, man_won, ro, won_ko, yeosseoyo
from agents.numbers import invented, pool

from . import season_engine

KPI_COLS = [  # key, Korean header, kind (table on the page and the first CSV columns)
    ("month_label", "월", "text"), ("events", "사건", "text"), ("levers_changed", "바꾼 운영", "text"),
    ("decisions", "밤 결정", "text"), ("revenue", "매출", "won"), ("op", "영업이익", "won"),
    ("shadow_op", "평소대로였다면 영업이익", "won"), ("net_vs_shadow", "평소 대비", "won"), ("covers", "손님 수", "int"),
    ("walkaways", "돌아간 팀", "int"), ("rating_after", "월말 평점", "float2"), ("cash_after", "월말 현금", "won"),
    ("p10_op", "예상 범위 하단 (p10)", "won"), ("p90_op", "예상 범위 상단 (p90)", "won"),
    ("band_position", "운 (예상 범위 안 위치, 0~1)", "float2"), ("prediction", "내 예측 영업이익", "won"),
    ("prediction_error_pct", "예측 오차 %", "float1"),
]
SHORT_HEAD = {"shadow_op": "평소대로였다면", "p10_op": "범위 p10", "p90_op": "범위 p90", "band_position": "운 위치 (0~1)",
              "prediction": "내 예측", "prediction_error_pct": "예측 오차 %"}   # printed table only; CSV keeps the long names
EXTRA_CSV = [("regular_share", "단골 비율", "float2"), ("fatigue", "직원 피로", "float1")]

LEVER_KO = {"meat_price": "삼겹살 가격", "soju_price": "소주 가격", "meat_grade": "원육", "menu_extras": "메뉴 추가",
            "banchan": "반찬 가짓수", "staff_grilling": "직원이 구워 주기", "staff_per_shift": "교대당 알바 수",
            "close_hour": "마감 시간", "lunch": "점심 영업", "terrace": "야장", "marketing_budget": "SNS 협찬 예산",
            "review_event": "리뷰 이벤트", "group_reservations": "단체 예약", "hygiene": "청결 관리"}


def csv_cols() -> list[tuple[str, str, str]]:
    """All CSV columns: the KPI columns, then every lever (운영: ...), then the slower-moving state."""
    return KPI_COLS + [(f"lever_{k}", f"운영: {v}", "text") for k, v in LEVER_KO.items()] + EXTRA_CSV


def won(v) -> str:
    if v is None:
        return "-"
    v = float(v)
    return man_won(v) if abs(v) >= 1e5 else won_ko(v)


def signed(v) -> str:
    """'184만원 적자' / '64만원 흑자' style for profit-like numbers."""
    if v is None:
        return "-"
    return f"{won(abs(v))} 적자" if v < 0 else f"{won(v)} 흑자"


def plus_minus(v) -> str:
    if v is None:
        return "-"
    return f"{won(abs(v))} 덜" if v < 0 else f"{won(v)} 더"


def _top_loss(row: dict) -> dict:
    neg = [w for w in row.get("waterfall") or [] if w.get("kind", "step") == "step" and (w.get("delta") or 0) < 0]
    w = min(neg, key=lambda w: w["delta"], default=None)
    return {"top_loss_driver": w and w.get("driver"), "top_loss": w and round(w["delta"])}


_MEMO: OrderedDict = OrderedDict()
_MEMO_LOCK = threading.Lock()
_BUILDING: dict[tuple, threading.Event] = {}     # key -> set when that build finishes (a warm in flight)


def _key(sess: dict, review: dict | None) -> tuple:
    return (sess["id"], len(sess["months"]), json.dumps(review, sort_keys=True))


def build(sess: dict, review: dict | None = None) -> dict:
    """The report for a session. `sess` is passed to sim.report AS IS: sim.report memoises per season object and
    months played, so the live session object (season_store keeps it in memory) is what makes warm() pay off.
    A build already running for the same key (the end-of-season warm) is waited for, not repeated."""
    key = _key(sess, review)
    with _MEMO_LOCK:
        if key in _MEMO:
            _MEMO.move_to_end(key)
            return _MEMO[key]
        ev = _BUILDING.get(key)
        mine = ev is None
        if mine:
            ev = _BUILDING[key] = threading.Event()
    if not mine:
        ev.wait(timeout=60)
        with _MEMO_LOCK:
            if key in _MEMO:
                return _MEMO[key]
    try:
        rep = _build(sess, review)
        with _MEMO_LOCK:
            _MEMO[key] = rep
            while len(_MEMO) > 64:
                _MEMO.popitem(last=False)
        return rep
    finally:
        if mine:
            with _MEMO_LOCK:
                _BUILDING.pop(key, None)
            ev.set()


def _build(sess: dict, review: dict | None) -> dict:
    import sim.report as R

    def opt(name):     # parts the sim may not have yet
        fn = getattr(R, name, None)
        return season_engine.to_json(fn(sess)) if callable(fn) else []

    table = season_engine.to_json(R.season_table(sess))
    rep = {"season_id": sess["id"], "source": "sim.report",
           "summary": season_engine.to_json(R.season_summary(sess, review)),
           "improvements": season_engine.to_json(R.improvements(sess)),
           "uncertain": opt("uncertain"), "cash_only": opt("cash_only"),
           "good_decisions": season_engine.to_json(R.good_decisions(sess)),
           "luck_months": season_engine.to_json(R.luck_months(sess)),
           "table": [{k: v for k, v in r.items() if k != "waterfall"} | _top_loss(r) for r in table]}
    rep["data_limits"] = review or rep["summary"].get("review") or {}
    return rep


def warm(sess: dict, review: dict | None = None) -> None:
    """End of season: run sim.report.warm (the slow DES re-scoring) and build this module's report, so the end
    screen's GET /report is instant. Meant for a background thread; errors are swallowed (the GET recomputes)."""
    try:
        import sim.report as R
        if callable(getattr(R, "warm", None)):
            R.warm(sess)
        build(sess, review)
    except Exception:  # noqa: BLE001 - a failed warm only means the first GET is slow
        pass


# --- CSV ---------------------------------------------------------------------------------------------------

def cell(v) -> str:
    """CSV cell: blank for missing, lists joined with |, booleans as 예/아니오."""
    if v is None:
        return ""
    if isinstance(v, bool):
        return "예" if v else "아니오"
    if isinstance(v, (list, tuple)):
        return "|".join(cell(x) for x in v)
    return str(v)


def to_csv(report: dict) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    cols = csv_cols()
    w.writerow([h for _, h, _ in cols])
    for r in report["table"]:
        w.writerow([cell(r.get(k)) for k, _, _ in cols])
    return "\ufeff" + buf.getvalue()    # BOM: Excel opens Korean correctly


def from_csv(text: str) -> list[dict]:
    rows = list(csv.reader(io.StringIO(text.lstrip("\ufeff"))))
    keys = {h: k for k, h, _ in csv_cols()}
    return [{keys[h]: v for h, v in zip(rows[0], r)} for r in rows[1:]]


# --- HTML --------------------------------------------------------------------------------------------------

def _fmt(v, kind):
    if v is None or v == "":
        return "-"
    if kind == "won":
        return won(v)
    if kind == "int":
        return f"{float(v):,.0f}"
    if kind == "float2":
        return f"{float(v):.2f}"
    if kind == "float1":
        return f"{float(v):.1f}"
    return html.escape(str(v))


def _what(i: dict) -> str:
    return i.get("lever_ko") or i.get("decision_ko") or i.get("lever") or i.get("decision") or "운영"


def to_html(report: dict) -> str:
    s = report["summary"] or {}

    def e(x: str) -> str:            # text nodes only, so quotes stay readable (no &#x27;)
        return html.escape(x, quote=False)

    imp = "".join(
        f"<li><b>{e(str(i.get('month_label')))} {e(_what(i))}</b>: {e(str(i.get('takeaway_ko', '')))}"
        f" <span class='tag'>{e(str(i.get('tag', '가정')))}</span>"
        + (f"<br><span class='sub'>대가: {e(str(i['downside_ko']))}"
           + (f", 그달 추가 비용 {won(i['cost'])}" if (i.get("cost") or 0) >= 10_000 else "") + "</span>" if i.get("downside_ko") else "")
        + (f"<br><span class='sub'>{e(str(i['basis']))}</span>" if i.get("basis") else "") + "</li>"   # basis names the DES check
        for i in report["improvements"]) or "<li>지금 계획에서 시즌 끝 현금을 늘리는 대안을 찾지 못했어요</li>"
    good = "".join(f"<li>{e(str(g.get('why_ko') or g.get('what_ko')))}</li>" for g in report["good_decisions"]) \
        or "<li>평소 계획이나 다른 선택보다 확실히 나았던 결정은 없었어요</li>"
    cash = "".join(f"<li>{e(str(x.get('warning_ko', '')))} <span class='tag'>{e(str(x.get('tag', '가정')))}</span></li>"
                   for x in report.get("cash_only") or [])
    cash_sec = (f"<h2>현금만 늘리는 선택 (주의)</h2><p class=\"sub\">시즌 끝 현금은 늘지만 가게 가치(손님, 평판, 단골)는 줄어드는 대안이라 "
                f"개선안에서 뺐습니다</p><ul>{cash}</ul>") if cash else ""
    unc = "".join(f"<li><b>{e(str(x.get('month_label')))} {e(_what(x))}</b>: {e(str(x.get('note_ko', '')))}</li>"
                  for x in report.get("uncertain") or [])
    unc_sec = (f"<h2>결과가 엇갈린 대안</h2><p class=\"sub\">빠른 추정과 시뮬레이션 재실행의 방향이나 크기가 달라 개선안 순위에서 뺐습니다</p>"
               f"<ul>{unc}</ul>") if unc else ""
    luck = "".join(f"<li>{e(str(x.get('luck_ko') or x.get('luck')))} <span class='sub'>(예상 범위 {won(x.get('p10_op'))}에서 "
                   f"{won(x.get('p90_op'))}, 실제 {won(x.get('op'))})</span></li>" for x in report["luck_months"]) \
        or "<li>운이 결과를 뒤집은 달은 없었어요. 계획의 효과가 운보다 컸어요</li>"
    head = "".join(f"<th>{e(SHORT_HEAD.get(k, h))}</th>" for k, h, _ in KPI_COLS)
    wide = {"events", "levers_changed", "decisions"}
    body = "".join("<tr>" + "".join(f"<td class='{kind}{' wide' if k in wide else ''}'>{_fmt(r.get(k), kind)}</td>"
                                    for k, _, kind in KPI_COLS) + "</tr>"
                   for r in report["table"])
    dl = report.get("data_limits") or {}
    pred = s.get("prediction_mean_abs_error_pct")
    closed = f"폐업 ({e(str(s.get('closed_reason_ko') or ''))})" if s.get("closed") else "영업 중"
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>시즌 개선 리포트</title><style>
:root {{ color-scheme: light; }}
body {{ font-family: "Pretendard", "Apple SD Gothic Neo", "Malgun Gothic", sans-serif; color: #1d1d1f; background: #fff; margin: 32px; line-height: 1.55; }}
h1 {{ font-size: 22px; margin: 0 0 4px; }} h2 {{ font-size: 16px; margin: 28px 0 8px; border-bottom: 1px solid #ddd; padding-bottom: 4px; }}
.meta, .sub {{ color: #666; font-size: 12px; }} .kpis {{ display: flex; gap: 24px; flex-wrap: wrap; margin-top: 12px; }}
.kpis div {{ min-width: 120px; }} .kpis b {{ display: block; font-size: 18px; }} li {{ margin-bottom: 6px; }}
table {{ border-collapse: collapse; width: 100%; font-size: 11px; }} th, td {{ border: 1px solid #ddd; padding: 4px 6px; }}
th {{ background: #f5f5f7; text-align: left; }} td:first-child, th:first-child {{ white-space: nowrap; }} td.won, td.int, td.float1, td.float2 {{ text-align: right; white-space: nowrap; }}
.tag {{ font-size: 11px; color: #555; border: 1px solid #ccc; border-radius: 4px; padding: 0 4px; }}
td, th {{ word-break: keep-all; }} th {{ white-space: nowrap; }} td.wide {{ min-width: 150px; }}
@page {{ size: A4 landscape; margin: 10mm; }}
@media print {{ body {{ margin: 0; }} h2 {{ break-after: avoid; }} table {{ font-size: 9px; page-break-inside: auto; }}
  thead {{ display: table-header-group; }} tr, li {{ break-inside: avoid; }} }}
</style></head><body>
<h1>시즌 개선 리포트</h1><p class="meta">대학로 삼겹살집 디지털 트윈 · 시즌 {e(report['season_id'])} · 모든 수치는 검토 전 예시 추정치</p>
<h2>요약</h2><div class="kpis">
<div>운영한 달<b>{s.get('months_played', '-')}</b></div><div>시즌 영업이익<b>{won(s.get('total_op'))}</b></div>
<div>평소 계획 대비<b>{won(s.get('total_vs_shadow'))}</b></div><div>시즌 끝 현금<b>{won(s.get('ending_cash'))}</b></div>
<div>가게 가치<b>{won(s.get('store_value'))}</b></div>
<div>평점<b>{'-' if s.get('ending_rating') is None else f"{float(s['ending_rating']):.2f}"}</b></div>
<div>상태<b>{closed}</b></div>
<div>예측 평균 오차<b>{'-' if pred is None else f"{float(pred):.1f}%"}</b></div></div>
<h2>개선할 점 top 5</h2><p class="sub">각 달의 운영 값과 밤 결정을 하나씩 바꿔, 같은 사건과 이후 계획으로 시즌 끝까지 다시 계산한 결과입니다</p><ol>{imp}</ol>
{unc_sec}
{cash_sec}
<h2>잘한 결정</h2><ul>{good}</ul>
<h2>운이 작용한 달</h2><ul>{luck}</ul>
<h2>월별 표</h2><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>
<h2>데이터 한계</h2><ul>
<li>{e(str(s.get('caveat_ko') or f"검토 {dl.get('reviewed', '-')}/{dl.get('total', '-')}"))}</li>
<li>개선안 옆 표시: 근거 = 그 운영의 메커니즘 값 절반 이상에 출처가 있음, 가정 = 그렇지 않음</li>
<li>한 시즌은 한 번의 추첨이에요. 같은 계획도 운에 따라 결과가 달라져요</li></ul>
</body></html>"""


# --- Q&A over the report -------------------------------------------------------------------------------------

def _docs(report: dict) -> list[dict]:
    docs = []
    for r in report["table"]:
        docs.append({"cite": f"{r['month_label']} 행", "kind": "month", "row": r,
                     "text": f"{r['month_label']} 사건 {r.get('events') or '없음'} 바꾼 운영 {r.get('levers_changed') or '없음'} "
                             f"밤 결정 {r.get('decisions') or '없음'} 영업이익 매출 손님 평소 대비 손해 적자 흑자"})
    for i, imp in enumerate(report["improvements"], 1):
        docs.append({"cite": f"개선 {i}", "kind": "improvement", "row": imp,
                     "text": f"실수 개선 다음 시즌 바꿔 {imp.get('month_label')} {_what(imp)} {imp.get('takeaway_ko', '')}"})
    for n, x in enumerate(report.get("uncertain") or [], 1):
        docs.append({"cite": f"엇갈림 {n}", "kind": "uncertain", "row": x,
                     "text": f"불확실 엇갈린 확실하지 않은 {x.get('month_label')} {_what(x)} {x.get('note_ko', '')}"})
    for n, x in enumerate(report.get("cash_only") or [], 1):
        docs.append({"cite": f"현금만 {n}", "kind": "cash_only", "row": x,
                     "text": f"현금만 당장 돈 주의 가게 가치 {x.get('month_label')} {_what(x)} {x.get('warning_ko', '')}"})
    for g in report["good_decisions"]:
        docs.append({"cite": f"잘한 결정 {g.get('month_label')}", "kind": "good", "row": g,
                     "text": f"잘한 결정 좋았던 {g.get('what_ko', '')} {g.get('month_label')}"})
    for x in report["luck_months"]:
        docs.append({"cite": f"운 {x.get('month_label')}", "kind": "luck", "row": x,
                     "text": f"운 행운 불운 {x.get('luck_ko', x.get('luck'))} {x.get('month_label')}"})
    docs.append({"cite": "요약", "kind": "summary", "row": report["summary"], "text": "요약 시즌 전체 합계 현금 가게 가치 평점"})
    return docs


INTENTS = (   # checked in order; luck first so "운이 좋았던 달" is not read as 잘한 결정 ("운" but never "운영")
    ("luck", r"행운|불운|운(?!영)"),
    ("cash_only", r"현금만|당장|돈만|단기"),
    ("why_month", r"왜|손해|적자|안 좋|망했"),
    ("mistake", r"실수|잘못|아쉬|가장 큰"),
    ("next", r"다음|바꿔|바꾼다면|고칠|개선"),
    ("good", r"잘한|좋았던|칭찬|잘했"),
)


def _intent(q: str) -> str:
    for intent, pat in INTENTS:
        if re.search(pat, q):
            return intent
    return "summary"


def _month_in(q: str, report: dict) -> dict | None:
    for r in report["table"]:
        if r["month_label"] and r["month_label"] in q:
            return r
    return None


def mock_answer(q: str, report: dict) -> tuple[str, list[str]]:
    intent = _intent(q)
    s = report["summary"] or {}
    imps = report["improvements"]
    if intent == "why_month":
        r = _month_in(q, report) or min(report["table"], key=lambda r: r["op"] or 0, default=None)
        if not r:
            return "아직 정산한 달이 없어요.", []
        cites = [f"{r['month_label']} 행"]
        why = (f"{eun(r['month_label'])} {yeosseoyo(signed(r['op']))}"
               + (f". 평소 계획이었다면 {signed(r['shadow_op'])}였을 거예요" if r.get("shadow_op") is not None else "") + ".")
        if r.get("events"):
            why += f" 그달엔 {r['events']} 같은 일이 있었어요."
        if r.get("top_loss_driver"):
            why += f" 가장 크게 깎인 건 {ro(r['top_loss_driver'])} {yeosseoyo(won(abs(r['top_loss'])))}."
        fix = next(((n, i) for n, i in enumerate(imps, 1) if i.get("month_label") == r["month_label"]), None)
        if fix:
            why += f" {fix[1]['takeaway_ko']}."
            cites.append(f"개선 {fix[0]}")
        luck = next((x for x in report["luck_months"] if x.get("month_label") == r["month_label"]), None)
        if luck:
            why += f" {luck['luck_ko']}."
            cites.append(f"운 {r['month_label']}")
        return why, cites
    if intent in ("mistake", "next"):
        if not imps:
            return "지금 계획에서 시즌 끝 현금을 늘리는 대안을 찾지 못했어요.", []
        top = imps[0]
        if intent == "mistake":
            return (f"가장 아까운 건 {top['month_label']}의 {ieyo(_what(top))}. {top['takeaway_ko']} ({top.get('tag', '가정')}).",
                    ["개선 1"])
        picks, seen = [], set()
        for n, i in enumerate(imps, 1):
            if _what(i) not in seen:
                seen.add(_what(i))
                picks.append((n, i))
        picks = picks[:3]
        first = picks[0][1]
        return ("다음 시즌엔 " + ", ".join(_what(i) for _, i in picks) + " 순서로 먼저 손보세요. "
                + f"가장 큰 건 {first['month_label']} {eul(_what(first))} {first.get('from_ko', '')}에서 "
                + f"{ro(str(first.get('to_ko', '')))} 바꾸는 거예요 ({first.get('tag', '가정')}).",
                [f"개선 {n}" for n, _ in picks])
    if intent == "cash_only":
        C = report.get("cash_only") or []
        if not C:
            return "현금만 늘리고 가게 가치를 깎는 대안은 없었어요.", []
        return (" ".join(f"{x['warning_ko']}." for x in C[:2]) + " 그래서 개선안에서는 뺐어요.",
                [f"현금만 {n}" for n in range(1, min(2, len(C)) + 1)])
    if intent == "good":
        g = report["good_decisions"]
        if not g:
            return "평소 계획이나 다른 선택보다 확실히 나았던 결정은 없었어요.", []
        return f"{g[0]['why_ko']}.", [f"잘한 결정 {g[0]['month_label']}"]
    if intent == "luck":
        L = report["luck_months"]
        want = "좋았" if re.search(r"좋|행운", q) else "나빴" if re.search(r"나쁘|나빴|불운", q) else None
        hit = [x for x in L if not want or want in str(x.get("luck", ""))]
        if not L:
            return "운이 결과를 뒤집은 달은 없었어요. 계획의 효과가 운보다 컸어요.", []
        if not hit:     # asked about good luck, only bad-luck months (or the other way): say so, then show those
            other = "운이 나빴던" if want == "좋았" else "운이 좋았던"
            return (f"운이 {want}던 달은 없었어요. {other} 달은 있었어요: " + " ".join(f"{x['luck_ko']}." for x in L),
                    [f"운 {x['month_label']}" for x in L])
        return (" ".join(f"{x['luck_ko']}." for x in hit), [f"운 {x['month_label']}" for x in hit])
    return (f"{s.get('months_played', 0)}달 동안 {yeosseoyo(signed(s.get('total_op')))}. 평소 계획보다 {plus_minus(s.get('total_vs_shadow'))} 벌었어요."
            + (f" 결국 문을 닫았어요 ({s.get('closed_reason_ko')})." if s.get("closed") else "")
            + (f" {s['caveat_ko']}" if s.get("caveat_ko") else ""), ["요약"])


def _rank(docs: list[dict], question: str, k: int = 6) -> list[dict]:
    """Retrieval over the season's own rows with the same local embedder as the RAG corpus."""
    try:
        import numpy as np

        from rag.embed import get_embedder
        emb = get_embedder()
        m = np.asarray(emb.passages([d["text"] for d in docs]), dtype="float32")
        q = np.asarray(emb.query(question), dtype="float32")
        scores = m @ q / ((np.linalg.norm(m, axis=1) + 1e-9) * (np.linalg.norm(q) + 1e-9))
        return [docs[i] for i in np.argsort(-scores)[:k]]
    except Exception:  # noqa: BLE001 - the table is tiny; without an embedder send it all
        return docs


def ask(report: dict, question: str, ctx: llm.RequestContext) -> dict:
    mock, cites = mock_answer(question, report)
    docs = _rank(_docs(report), question)
    prompt = ("아래는 한 시즌 리포트의 행들입니다. 이 행들에 있는 사실과 숫자만으로 한국어 두세 문장으로 답하고, "
              "근거로 쓴 행을 [11월 행], [개선 1]처럼 적으세요.\n"
              + "\n".join(f"[{d['cite']}] {json.dumps(d['row'], ensure_ascii=False, default=str)}" for d in docs)
              + f"\n\n질문: {question}")
    res = llm.complete(prompt, ctx=ctx, mock_text=mock + (" " + " ".join(f"[{c}]" for c in cites) if cites else ""))
    text, backend = res.text, res.backend
    allowed = pool(report, question)
    if res.backend != "mock" and invented(text, allowed):
        text, backend = mock + (" " + " ".join(f"[{c}]" for c in cites) if cites else ""), f"{res.backend} (invented a number: template used)"
    return {"question": question, "answer": text, "citations": cites, "backend": backend, "cached": res.cached}
