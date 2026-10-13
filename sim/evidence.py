"""Which mechanisms each shock and owner action relies on, and how well each mechanism is evidenced.

Decision 2.1 (flag game.l_mechanism_badge): a choice or event whose effect rests on a confidence-L mechanism
shows "인터뷰로 확인 필요" with the one-line reason below. Nothing is hidden. The confidence of a mechanism is the
weakest input it uses (HeroStore confidence or SIM_ASSUMPTIONS, which are all L).
"""
from __future__ import annotations

MECHANISMS = {
    "staff_service": {
        "confidence": "L",
        "reason": "직원 한 명이 주문·계산·정리에 쓰는 시간이 가정값이라, 인력을 줄였을 때 대기와 이탈이 얼마나 늘지 확실하지 않습니다",
    },
    "staff_hours": {
        "confidence": "L",
        "reason": "근무시간을 줄여도 저녁 서비스가 그대로라고 가정합니다 (교대 시간과 바쁜 시간의 관계는 출처 없음)",
    },
    "price_elasticity": {
        "confidence": "L",
        "reason": "가격탄력성 −0.81은 외식 전체(범주) 메타분석 값입니다. 근처 고깃집 27곳 중 한 매장은 손님이 더 쉽게 옮겨 가므로 실제 반응은 더 클 수 있습니다",
    },
    "alcohol_elasticity": {
        "confidence": "L",
        "reason": "소주 가격에 대한 반응을 외식 전체 가격탄력성으로 대신했습니다 (소주 자료 없음)",
    },
    "upsell": {
        "confidence": "L",
        "reason": "권하면 1인당 주류·식사 주문이 10% 는다는 가정입니다 (출처 없음)",
    },
    "rain_demand": {
        "confidence": "L",
        "reason": "비 오는 밤 손님이 10% 준다는 가정입니다. 비 오는 날 수는 기상청 평년값입니다",
    },
    "competitor_split": {
        "confidence": "L",
        "reason": "경쟁점이 생겼을 때 손님이 얼마나 나뉘는지는 가정값입니다",
    },
    "dwell_alcohol": {
        "confidence": "L",
        "reason": "술을 덜 마시면 덜 오래 머문다는 연결의 크기는 가정입니다",
    },
}

SHOCK_MECHANISMS = {
    "SH01": ["price_elasticity"], "SH02": ["price_elasticity"], "SH03": [], "SH04": ["alcohol_elasticity"],
    "SH05": ["dwell_alcohol"], "SH06": [], "SH07": ["staff_service"], "SH08": [], "SH09": [],
    "SH10": ["rain_demand"], "SH10b": ["rain_demand"], "SH11": ["competitor_split"],
}

ACTION_MECHANISMS = {
    "absorb": [], "reprice": ["price_elasticity"], "discount": ["price_elasticity"],
    "reprice_alcohol": ["alcohol_elasticity"], "cut_staff_hours": ["staff_hours"], "cut_staff": ["staff_service"],
    "change_mix": ["upsell"],
}


def evidence(ids: list[str]) -> dict:
    """{'needs_interview': bool, 'weakest': H/M/L or None, 'reasons': [...]} for a list of mechanism ids."""
    mechs = [MECHANISMS[m] for m in ids]
    rank = {"H": 0, "M": 1, "L": 2}
    weakest = max((m["confidence"] for m in mechs), key=rank.get, default=None)
    return {"needs_interview": weakest == "L", "weakest": weakest, "mechanisms": ids,
            "reasons": [m["reason"] for m in mechs if m["confidence"] == "L"]}
