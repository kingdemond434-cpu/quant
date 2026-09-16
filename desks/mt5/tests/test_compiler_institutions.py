"""An institution names its currency; a link-only capture is empty whatever its kind."""
from __future__ import annotations

import sys
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
for p in (str(_DESK), str(_DESK / "research")):
    if p not in sys.path:
        sys.path.insert(0, p)

import miner_candidate_compiler as mcc  # noqa: E402

UNIVERSE = {"AUDUSD", "AUDJPY", "EURUSD", "USDJPY", "GBPUSD", "EURGBP", "USDCHF", "XAUUSD",
            "Adobe"}


def test_a_central_bank_in_prose_yields_its_currencys_pairs() -> None:
    found = mcc.text_symbols("the rba held rates and signalled a cut next quarter", UNIVERSE)
    assert found[:2] == ["AUDUSD", "AUDJPY"]
    found = mcc.text_symbols("fomc minutes point to further easing", UNIVERSE)
    assert "EURUSD" in found and "USDJPY" in found


def test_short_english_words_are_not_institutions() -> None:
    assert mcc.text_symbols("the abs market was safe today", UNIVERSE) == []


def test_share_cfd_keeps_the_registrys_case() -> None:
    assert mcc.text_symbols("adobe earnings beat", UNIVERSE) == []      # prose alone is not enough
    assert mcc._declared_symbols({"symbols": ["ADOBE"]}, UNIVERSE) == ["Adobe"]


def test_link_only_capture_is_empty_whatever_its_kind() -> None:
    row = {"title": "FX Blue user fxpl", "url": "https://example.com/x", "kind": ""}
    cands, disp = mcc.compile_row("world_crawler", row, UNIVERSE)
    assert cands == [] and disp == "EMPTY_CAPTURE"
    row = {"title": "gold basis pressure", "testable_claim": "gold rallies into the comex "
           "settlement when the basis is wide", "symbols": ["XAUUSD"], "kind": ""}
    _cands, disp = mcc.compile_row("deepseek", row, UNIVERSE)
    assert disp != "EMPTY_CAPTURE"
