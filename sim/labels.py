"""Korean display strings shared by sim.precompute (headlines) and the web UI (via runs/index.json)."""
from __future__ import annotations

SHOCK_LABELS = {
    "SH01": "고기 가격 10% 인상", "SH02": "고기 가격 10% 인하", "SH03": "돼지고기 도매가 8% 상승",
    "SH04": "소주 가격 1,000원 인상", "SH05": "1인당 음주량 20% 감소", "SH06": "알바 시급 5% 인상",
    "SH07": "교대당 알바 1명 감축", "SH08": "재계약 임대료 5% 인상", "SH09": "방학 수요 8% 감소",
    "SH10": "비 오는 밤이 평년만큼 (한 달 6일)", "SH10b": "한 달 내내 비 (최악의 경우)", "SH11": "근처 경쟁 고깃집 개점",
}

# Conditional clause ("...하면"); headline() turns the trailing 면 into 고 when an owner action follows.
SHOCK_IF = {
    "SH01": "고기 가격을 10% 올리면", "SH02": "고기 가격을 10% 내리면", "SH03": "돼지고기 도매가가 8% 오르면",
    "SH04": "소주 가격을 1,000원 올리면", "SH05": "손님이 술을 20% 덜 마시면", "SH06": "알바 시급이 5% 오르면",
    "SH07": "교대마다 알바를 한 명 줄이면", "SH08": "재계약 때 임대료가 5% 오르면", "SH09": "방학으로 손님이 8% 줄면",
    "SH10": "평년처럼 한 달에 6일쯤 비가 오면", "SH10b": "한 달 내내 비가 오면", "SH11": "근처에 고깃집이 하나 더 생기면",
}

SEGMENT_LABELS = {"twenties": "20대 친구 모임", "office": "직장인 회식", "family": "동네 가족"}


def man(v: float) -> str:
    return f"{'적자 ' if v < 0 else ''}{round(abs(v) / 10000):,}만원"


def headline(shock_id: str | None, action_phrase: str | None, op_before: float, op_after: float) -> str:
    """One sentence: condition(s), then monthly OP before → after (p50)."""
    parts = []
    if shock_id:
        cond = SHOCK_IF[shock_id]
        parts.append(cond[:-1] + "고" if action_phrase else cond)
    if action_phrase:
        same = shock_id and action_phrase == SHOCK_IF[shock_id]
        parts.append(action_phrase.replace("한 명", "한 명 더") if same else action_phrase)
    lead = " ".join(parts) if parts else "평소대로라면"
    if abs(op_after - op_before) < 5000:
        return f"{lead}, 한 달 영업이익은 {man(op_before)}에서 거의 변하지 않습니다"
    verb = "줄어듭니다" if op_after < op_before else "늘어납니다"
    return f"{lead}, 한 달 영업이익은 {man(op_before)}에서 {man(op_after)}으로 {verb}"
