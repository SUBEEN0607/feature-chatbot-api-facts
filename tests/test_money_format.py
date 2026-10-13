"""Korean money text everywhere uses agents.ko.man_won / won_ko: rounded before the sign, UI minus, 만원 (N19)."""
import json
import re
from pathlib import Path

from agents import chat, owner, persona

ASCII_MINUS_MONEY = re.compile(r"-\d[\d,]*(?:\.\d+)?\s*만\s?원|-\d[\d,]*원|[-+\u2212]0만")


def test_agent_formatters_round_first_and_use_the_ui_minus():
    for won in (persona.won, chat.won):
        assert won(-0.4) == "0원" and won(-3_000) == "\u22123,000원" and won(-1_234_567) == "\u2212123만원"
        assert won(1_234_567) == "123만원"
    assert owner._won(-3_000) == "0만원" and owner._won(-1_430_000) == "\u2212143만원" and owner._won(None) == "?"


def test_guided_precompute_has_no_ascii_minus_money():
    guided = Path(__file__).resolve().parents[1] / "web" / "public" / "guided"
    index = (guided / "index.json").read_text(encoding="utf-8")
    served = {"index.json", "report.json", *re.findall(r'"([^"/]+\.json)"', index)}   # files the demo loads
    for f in sorted(guided / n for n in served):
        hits = ASCII_MINUS_MONEY.findall(f.read_text(encoding="utf-8"))
        assert not hits, (f.name, hits[:5])
        assert "만 원" not in f.read_text(encoding="utf-8"), f.name   # the game writes 만원
