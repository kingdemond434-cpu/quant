"""EXECUTABLE_BOOK.json: what the pass will actually send, per book key (CRO row 111 Q4)."""
from __future__ import annotations

import sys
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import decision_core as dc  # noqa: E402


def test_each_key_names_its_carrier_its_senders_and_why_the_rest_send_nothing() -> None:
    sleeves = [
        {"name": "a1", "symbol": "CHFNOK", "book_key": "K", "risk_frac": 0.04, "q_charge": 0.04,
         "sized_by": "allocator_book", "exec": "family_market",
         "pending_order": {"ok": True, "lot": 0.03}},
        {"name": "b2", "symbol": "CHFNOK", "book_key": "K", "risk_frac": 0.0, "alias_of": "a1",
         "sized_by": "allocator_book"},
        {"name": "c3", "symbol": "EURUSD", "book_key": "E", "risk_frac": 0.0,
         "decay_zero": "roll-20 <= 0R"},
        {"name": "gold_x", "symbol": "XAUUSD", "risk_frac": 0.01},
    ]
    doc = dc.executable_book(sleeves, {"K": 0.04, "E": 0.02})
    assert doc["n_keys"] == 2 and doc["n_sending_keys"] == 1 and doc["n_unkeyed"] == 1
    k = doc["keys"]["K"]
    assert k["allocator_fraction"] == 0.04 and k["sending"] == ["a1"]
    assert k["rows"][0]["lot"] == 0.03 and k["rows"][1]["why_zero"] == "alias of a1"
    assert doc["keys"]["E"]["sending"] == []
    assert doc["keys"]["E"]["rows"][0]["why_zero"] == "roll-20 <= 0R"
    assert dc.executable_book([], None) == {"keys": {}, "unkeyed": [], "n_keys": 0,
                                           "n_sending_keys": 0, "n_unkeyed": 0}


def test_the_gateway_writes_it_after_the_heat_cap_and_never_raises() -> None:
    src = (_DESK / "mt5desk" / "gateway.py").read_text(encoding="utf-8")
    i = src.index("sleeves, heat_note = cap_by_heat(sleeves, equity, k_eff=k_eff)")
    j = src.index("_exe = executable_book(sleeves, _book)")
    assert i < j < src.index("run_family_sleeves(st, sleeves, equity)")
    assert 'BASE / "reports" / "EXECUTABLE_BOOK.json"' in src
    assert 'log(f"EXECUTABLE_BOOK not written' in src
