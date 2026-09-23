"""TIER-1 W0 -- the join that turns 4.6% live attribution into a measured number.

The defect this pins is a JOIN, not a missing file: MetaTrader truncates the sleeve it is handed
into the position comment, and an exact string match then declares the desk's own trades
unattributed. What is pinned here: a truncated label is recovered ONLY when it can be exactly one
roster name, an ambiguous prefix is published with its candidates rather than guessed, a bracket
print is joined on the price the terminal itself wrote, and a deal no pass reaches is
UNATTRIBUTED BY NAME -- never silently dropped and never counted as attributed.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK / "research"), str(DESK), str(DESK.parents[1])):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import attribution_reconcile as AR  # noqa: E402

ROSTER = ["chfnok_carry_asia_p_98d776f0a1b2", "audusd_discovered_asia_p_8e11", "gold_asia_v2",
          "gold_asia_v3", "xau_m15_anti_breakout"]


def _deal(label: str, symbol: str = "XAUUSD", *, tp: float | None = None,
          sl: float | None = None, deal: int = 1) -> dict[str, Any]:
    return {"time": "2026-09-07T17:04:15+00:00", "sleeve": label, "symbol": symbol,
            "account": 495044, "deal": deal, "tp": tp, "sl": sl, "volume": 0.01}


def test_a_truncated_label_is_recovered_only_when_it_can_be_one_roster_name() -> None:
    rows = AR.attribute(
        [_deal("chfnok_carry_asia_p_98d776f", "CHFNOK", deal=1),   # truncated, unique
         _deal("gold_asia", deal=2),                               # truncated, TWO candidates
         _deal("xau_m15_anti_breakout", deal=3)],                  # exact
        ROSTER)
    by_deal = {r["deal"]: r for r in rows}
    assert by_deal[1]["route"] == AR.PREFIX
    assert by_deal[1]["sleeve"] == "chfnok_carry_asia_p_98d776f0a1b2"
    assert by_deal[2]["route"] == AR.AMBIGUOUS and by_deal[2]["sleeve"] is None
    assert by_deal[2]["candidates"] == ["gold_asia_v2", "gold_asia_v3"]
    assert by_deal[3]["route"] == AR.EXACT and by_deal[3]["sleeve"] == "xau_m15_anti_breakout"


def test_a_short_label_is_never_prefix_matched() -> None:
    """A three-character label is a prefix of half the roster; matching on it would manufacture
    attribution, which is the opposite of the point."""
    hit, cands = AR.prefix_match("gol", ROSTER)
    assert hit is None and cands == []
    rows = AR.attribute([_deal("gol")], ROSTER)
    assert rows[0]["route"] == AR.UNATTRIBUTED


def test_a_bracket_print_is_joined_on_the_price_the_terminal_wrote() -> None:
    named = _deal("xau_m15_anti_breakout", tp=4360.71, sl=4461.71, deal=10)
    orphan = _deal("[tp 4360.71]", tp=4360.71, sl=4461.71, deal=11)
    rows = AR.attribute([named, orphan], ROSTER)
    assert rows[1]["route"] == AR.GEOMETRY
    assert rows[1]["sleeve"] == "xau_m15_anti_breakout"
    # a different symbol is NOT joined even at the same price -- the join carries the symbol
    other = AR.attribute([named, _deal("[tp 4360.71]", "EURCHF", deal=12)], ROSTER)
    assert other[1]["route"] == AR.UNATTRIBUTED


def test_bracket_parsing_refuses_anything_that_is_not_a_bracket_print() -> None:
    assert AR.bracket_price("[tp 4360.71]") == ("tp", 4360.71)
    assert AR.bracket_price("[sl 0.94555]") == ("sl", 0.94555)
    for bad in ("gold_asia", "[tp]", "[close 1.0]", "[tp x]", "", "[tp 1.0 2.0]"):
        assert AR.bracket_price(bad) is None


def test_an_unreachable_deal_is_published_by_name_and_never_counted_as_attributed(
        tmp_path: Path) -> None:
    ledger = tmp_path / "live_ledger.jsonl"
    ledger.write_text("".join(json.dumps(d) + "\n" for d in [
        _deal("xau_m15_anti_breakout", deal=1), _deal("[tp 999.99]", deal=2)]), "utf-8")
    doc = AR.build(ledger=ledger)
    assert doc["n_deals"] == 2
    assert doc["counts"][AR.UNATTRIBUTED] == 1
    assert doc["attributed_deals"] + doc["counts"][AR.UNATTRIBUTED] == 2
    named = {r["label"] for r in doc["unattributed"]}
    assert "[tp 999.99]" in named          # published BY NAME, not silently dropped


def test_an_absent_ledger_is_UNMEASURED_and_still_writes_a_report(tmp_path: Path) -> None:
    doc = AR.build(ledger=tmp_path / "nothing.jsonl")
    assert doc["attributed_share"] is None and doc["n_deals"] == 0
    assert any("UNMEASURED" in n for n in doc["unmeasured"])
    assert doc["inputs"]["nothing.jsonl"] == "absent"
    empty = tmp_path / "empty.jsonl"
    empty.write_text("", "utf-8")
    doc2 = AR.build(ledger=empty)
    assert doc2["attributed_share"] is None          # an empty ledger is not 100% attributed
    assert any("not 100%" in n for n in doc2["unmeasured"])


def test_the_organ_sizes_nothing_and_says_so() -> None:
    doc = AR.build(ledger=Path("nope.jsonl"))
    assert "allocates no" in doc["sizes_nothing"]
    assert doc["rule"] and doc["schema"] == "attribution-reconcile-1"


def test_the_gateway_windows_are_roster_names_in_their_own_right() -> None:
    names, where = AR.roster()
    from research.promoter import GOLD_SLEEVE_NAMES
    for window in GOLD_SLEEVE_NAMES:
        assert window in names
        assert "gateway window" in where[window]
