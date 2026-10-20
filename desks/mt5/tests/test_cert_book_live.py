"""The principal's certified sleeve book (data/CERT_BOOK_LIVE.json, 2026-10-07) and the live
policy rows that go with it: the sizes reach both venues at the keys they name, every other key
keeps the allocator's fraction, and a bad file changes nothing."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
for p in (str(_DESK), str(_DESK / "research")):
    if p not in sys.path:
        sys.path.insert(0, p)

from mt5desk import live_policy  # noqa: E402
from mt5desk.kelly_sizing import CERT_BOOK_FILE, load_cert_book  # noqa: E402
from mt5desk.sizing import MAX_RISK_FRAC  # noqa: E402

#: BOOKS_PATCH v5 (principal zuck, 2026-10-13): the three gap_decay keys held at 0.0 -- never an
#: empty block, since load_cert_book returns None on {} -- and gold_asia's 0.082 removed. gold_asia
#: and the three FX book sleeves trade at 0.01 through decision_core.MINLOT_OVERRIDE_SLEEVES.
FUSION = {"EURZAR_overnight_gap_decay_asia": 0.0, "USDZAR_overnight_gap_decay_asia": 0.0,
          "AUDCHF_overnight_gap_decay_asia": 0.0}
#: The E8 book (patches/e8_book_79 v6): gold_asia 0.0075, every other window and sleeve 0.0.
E8 = {"gold_asia": 0.0075, "gold_london_am": 0.0, "gold_afternoon": 0.0,
      "USDJPY_session_range_breakout_asia": 0.0, "NZDJPY_clock_transition_asia": 0.0,
      "AUDCHF_overnight_gap_decay_asia": 0.0}


def _write(tmp_path: Path, doc: dict) -> Path:
    p = tmp_path / "CERT_BOOK_LIVE.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    return p


def test_committed_book_carries_the_principals_sizes() -> None:
    assert load_cert_book(CERT_BOOK_FILE, "fusion") == FUSION
    assert load_cert_book(CERT_BOOK_FILE, "e8") == E8
    assert not any(k.startswith(("USDJPY", "CHFNOK", "gold_")) for k in FUSION)
    assert all(v == 0.0 for k, v in E8.items() if k != "gold_asia")
    doc = json.loads(CERT_BOOK_FILE.read_text(encoding="utf-8"))
    assert doc["e8_pending"] == {"USDJPY_session_range_breakout_asia": 0.004}
    assert set(doc["e8_pins"]) == {"gold_asia", "USDJPY_session_range_breakout_asia"}
    assert doc["e8_by"].startswith("principal zuck")


@pytest.mark.parametrize("doc", [
    {"enabled": False, "fusion": {"gold_asia": 0.05}},
    {"fusion": {"gold_asia": 0.05}},
    {"enabled": True},
    {"enabled": True, "fusion": {}},
    {"enabled": True, "fusion": {"gold_asia": "0.05"}},
    {"enabled": True, "fusion": {"gold_asia": True}},
    {"enabled": True, "fusion": {"gold_asia": -0.01}},
    {"enabled": True, "fusion": {"gold_asia": 0.05, "x": MAX_RISK_FRAC + 0.01}},
])
def test_any_doubt_returns_none_so_sizing_is_unchanged(tmp_path: Path, doc: dict) -> None:
    assert load_cert_book(_write(tmp_path, doc), "fusion") is None


def test_absent_file_is_none(tmp_path: Path) -> None:
    assert load_cert_book(tmp_path / "missing.json", "fusion") is None


def test_e8_gold_maps_book_keys_to_window_names() -> None:
    pytest.importorskip("MetaTrader5")
    from prop import e8_gold
    windows = e8_gold.cert_gold_windows(E8)
    assert windows == {"asia": 0.0075, "london_am": 0.0, "afternoon": 0.0}
    assert e8_gold.window_risk("asia", windows) == (0.0075, "kelly_survival")
    # The explicit 0.0 keys stand the two windows aside on E8 (the placement loop skips frac 0).
    assert e8_gold.window_risk("london_am", windows) == (0.0, "kelly_survival")
    assert e8_gold.window_risk("afternoon", windows) == (0.0, "kelly_survival")


def test_gateway_overlays_only_the_named_keys(monkeypatch: pytest.MonkeyPatch,
                                              tmp_path: Path) -> None:
    pytest.importorskip("MetaTrader5")
    from mt5desk import gateway, kelly_sizing
    alloc = {"gold_asia": 0.03, "gold_afternoon": 0.04, "EURCHF_carry_asia": 0.0}
    monkeypatch.setattr(gateway, "_allocator_book", lambda: (dict(alloc), "proof ok"))
    monkeypatch.setattr(kelly_sizing, "CERT_BOOK_FILE",
                        _write(tmp_path, {"enabled": True, "fusion": FUSION}))
    book, why = gateway.allocator_book()
    assert book == {**alloc, **FUSION}
    assert book["gold_afternoon"] == 0.04 and book["EURCHF_carry_asia"] == 0.0
    assert why.endswith("cert book sets 3")
    monkeypatch.setattr(kelly_sizing, "CERT_BOOK_FILE",
                        _write(tmp_path, {"enabled": False, "fusion": FUSION}))
    assert gateway.allocator_book() == (alloc, "proof ok")


def test_gateway_key_join_reaches_the_cert_rows() -> None:
    pytest.importorskip("MetaTrader5")
    from mt5desk import gateway
    row = {"name": "eurzar_overnight_gap_decay_asia_p_44136fa3", "symbol": "EURZAR",
           "family": "overnight_gap_decay", "selector": "asia"}
    assert gateway._book_key(row, FUSION) == "EURZAR_overnight_gap_decay_asia"
    # gold_asia left the fusion block (v5); the version-suffix join is pinned on the e8 keys.
    assert gateway._book_key({"name": "gold_asia_v3", "symbol": "XAUUSD"}, E8) == "gold_asia"


def test_live_policy_admits_the_book_and_quarantines_usdjpy_and_chfnok() -> None:
    pol = live_policy.policy()
    assert pol.live_symbols == {"XAUUSD", "USDJPY", "EURZAR", "USDNOK", "EURILS"}
    assert "discovered" in pol.banned_families
    assert "M15" in pol.banned_timeframes["XAUUSD"]
    # The three gap_decay principals are refused at the door (BOOKS_PATCH v5).
    for sym in ("AUDCHF", "EURZAR", "USDZAR"):
        name = f"{sym.lower()}_overnight_gap_decay_asia_p_44136fa355b3678a_principal_20261007"
        row = {"symbol": sym, "family": "overnight_gap_decay", "exec": "family_market",
               "name": name}
        assert live_policy.refuse(row, pol)
    for name in ("USDJPY.asia#rr=2.5", "usdjpy_session_range_breakout_asia_rr25_wb12"):
        assert live_policy.refuse({"symbol": "USDJPY", "name": name}, pol)
    for name in ("chfnok_carry_asia_p_98d776f3e210d3e2", "CHFNOK.carry.asia#input_symbol=CHFNOK"):
        assert live_policy.refuse({"symbol": "CHFNOK", "family": "carry", "name": name}, pol)
    doc = json.loads(live_policy.POLICY_FILE.read_text(encoding="utf-8"))
    assert doc["live_sleeves"] == {
        "USDJPY": [], "CHFNOK": [],
        "EURZAR": ["eurzar_carry_asia_p_8339edce23032d21"],
        "USDNOK": ["usdnok_carry_asia_p_ff35bb7c8427d66f"],
        "EURILS": ["eurils_formula_asia_p_673857a649d3c271"]}
    assert "reddit_lineage_quarantine" in doc and "carry_lookahead_quarantine" in doc
