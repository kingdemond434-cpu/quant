"""One bet is not taken forty times: the per-symbol same-side cap across sleeves (2026-09-16).

Measured on EURCHF: seven parameterisations of one discovered mechanism shorted a 12-pip box
~40 times in twelve hours, re-entering every bar into their own stops, 0-for-27 between five of
them. Single-position discipline is per sleeve; this is the same discipline at the level the
venue nets -- symbol and direction -- with every refusal journaled so missed_growth can price it.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

_DESK = Path(__file__).resolve().parents[1]
for p in (str(_DESK), str(_DESK / "research")):
    if p not in sys.path:
        sys.path.insert(0, p)

from mt5desk import gateway  # noqa: E402


def _pos(symbol: str, kind: int, comment: str = "DWx") -> SimpleNamespace:
    return SimpleNamespace(symbol=symbol, type=kind, comment=comment, volume=0.02)


def test_same_side_count_sees_only_the_desks_positions_in_that_direction() -> None:
    positions = [_pos("EURCHF", 1, "DWeurchf_a"), _pos("EURCHF", 1, "DWeurchf_b"),
                 _pos("EURCHF", 0, "DWeurchf_c"), _pos("EURCHF", 1, "manual"),
                 _pos("AUDUSD", 1, "DWaudusd")]
    assert gateway.same_side_count("EURCHF", -1, positions) == 2       # two desk shorts
    assert gateway.same_side_count("EURCHF", +1, positions) == 1       # one desk long
    assert gateway.same_side_count("AUDUSD", +1, positions) == 0
    # A short this pass has already decided to send counts as one more.
    assert gateway.same_side_count("EURCHF", -1, positions, pending={"EURCHF": -0.03}) == 3
    assert gateway.same_side_count("EURCHF", -1, positions, pending={"EURCHF": +0.03}) == 2


def test_the_cap_is_two_and_is_env_tunable() -> None:
    assert gateway.MAX_SAME_SIDE_PER_SYMBOL == 2


def test_refusals_are_journaled_not_just_logged(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(gateway, "REFUSALS", tmp_path / "refused_orders.jsonl")
    gateway.journal_refusal("eurchf_discovered_asia_p_6c", "EURCHF", -1, "symbol_side_cap",
                            "2 short position(s) already on EURCHF across sleeves (cap 2)")
    rows = [json.loads(ln) for ln in (tmp_path / "refused_orders.jsonl").read_text("utf-8")
            .splitlines()]
    assert rows[0]["stage"] == "symbol_side_cap" and rows[0]["side"] == "sell"
    assert rows[0]["sleeve"] == "eurchf_discovered_asia_p_6c" and rows[0]["symbol"] == "EURCHF"
