"""Season mode v1 (kept for the v1 game at #/ and its runs/season grid): lasting choices carry into the next month.

State = five levers the owner menu can move, each kept for the rest of the season:
  P price step (-1 = 고기 5% 인하, 0, +1 = 고기 5% 인상)   A 소주 +₩500   H 알바 근무 −1h   S 교대당 알바 −1   X 술·식사 권유
"그대로 버티기" keeps the state. Choosing a lever that is already at its limit changes nothing.
A month's outcome depends only on (state after the choice, this month's shock), so 48 states × shocks covers every
season path. sim.precompute --season writes that grid for the offline game.
"""
from __future__ import annotations

from itertools import product

from sim.owner_actions import MENU, apply_action

LEVERS = ["P", "A", "H", "S", "X"]
PRICE_CHAR = {-1: "D", 0: "0", 1: "U"}
CHAR_PRICE = {v: k for k, v in PRICE_CHAR.items()}
BASE_STATE = {"P": 0, "A": 0, "H": 0, "S": 0, "X": 0}

LEVER_LABELS = {
    "P": {-1: "고기 가격 5% 인하 유지", 1: "고기 가격 5% 인상 유지"},
    "A": {1: "소주 500원 인상 유지"}, "H": {1: "알바 근무 1시간 단축 유지"},
    "S": {1: "교대당 알바 1명 감축 유지"}, "X": {1: "술·식사 권유 유지"},
}


def key(state: dict) -> str:
    return "".join(f"{lv}{PRICE_CHAR[state[lv]] if lv == 'P' else state[lv]}" for lv in LEVERS)


def parse(k: str) -> dict:
    out = {}
    for i, lv in enumerate(LEVERS):
        c = k[2 * i + 1]
        out[lv] = CHAR_PRICE[c] if lv == "P" else int(c)
    return out


LEVER_ACTION = {"A": "reprice_alcohol", "H": "cut_staff_hours", "S": "cut_staff", "X": "change_mix"}


def all_states(excluded_actions: set | frozenset = frozenset()) -> list[dict]:
    """Every reachable state. A lever whose action is excluded from the game (industry game.exclude) stays 0."""
    fixed = {lv for lv, a in LEVER_ACTION.items() if a in excluded_actions}
    opts = [[-1, 0, 1]] + [[0] if lv in fixed else [0, 1] for lv in LEVERS[1:]]
    return [dict(zip(LEVERS, v)) for v in product(*opts)]


def transition(state: dict, action: str) -> dict:
    s = dict(state)
    if action == "reprice":
        s["P"] = min(1, s["P"] + 1)
    elif action == "discount":
        s["P"] = max(-1, s["P"] - 1)
    elif action == "reprice_alcohol":
        s["A"] = 1
    elif action == "cut_staff_hours":
        s["H"] = 1
    elif action == "cut_staff":
        s["S"] = 1
    elif action == "change_mix":
        s["X"] = 1
    elif action != "absorb":
        raise ValueError(action)
    return s


def apply_state(params: dict, state: dict) -> dict:
    """Base parameters with the lasting levers applied (owner_actions default arguments)."""
    p = params
    if state["P"] == 1:
        p = apply_action(p, "reprice", **MENU["reprice"]["default_args"])
    elif state["P"] == -1:
        p = apply_action(p, "discount", **MENU["discount"]["default_args"])
    for lv, action in (("A", "reprice_alcohol"), ("H", "cut_staff_hours"), ("S", "cut_staff"), ("X", "change_mix")):
        if state[lv]:
            p = apply_action(p, action, **MENU[action]["default_args"])
    return p


def describe(state: dict) -> list[str]:
    return [LEVER_LABELS[lv][state[lv]] for lv in LEVERS if state[lv] in LEVER_LABELS[lv]]
