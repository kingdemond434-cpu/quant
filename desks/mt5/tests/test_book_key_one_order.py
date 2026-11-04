"""One order per allocator book key (hourly pass / Auditor MUST-FIX, 2026-11-04).

`_book_key` folds every roster variant of one (symbol, family, window) cell onto the cell's single
allocator key, and each row used to take `book[key]` whole: three LIVE variants of CHFNOK carry
would have sent three times the cell's risk, with `cap_by_heat` trimming only the total. Pinned:
the first row by name carries the key's fraction, every other row is ALIAS_FOLDED at 0 (still
sized by the book, so no base-ramp fallback), and exactly one order goes out.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import decision_core as dc  # noqa: E402


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


adapter = _load("_one_order_adapter", _DESK / "tests" / "test_gateway_adapter.py")


def test_three_live_rows_on_one_book_key_send_exactly_one_order() -> None:
    book_key = adapter._exec(("_book_key",), {})["_book_key"]
    book = {"CHFNOK_carry_asia": 0.02}
    rows = [{"name": f"chfnok_carry_asia_p_{h}", "status": "LIVE", "symbol": "CHFNOK",
             "family": "carry", "selector": "asia"}
            for h in ("c3", "a1", "b2")]
    keys = {r["name"]: book_key(r, book) for r in rows}
    assert set(keys.values()) == {"CHFNOK_carry_asia"}, keys
    aliases = dc.fold_book_aliases(keys)
    assert aliases == {"chfnok_carry_asia_p_b2": "chfnok_carry_asia_p_a1",
                       "chfnok_carry_asia_p_c3": "chfnok_carry_asia_p_a1"}
    lots = []
    for r in rows:                       # the gateway's own semantics, row by row
        frac = 0.0 if r["name"] in aliases else book[keys[r["name"]]]
        lots.append(dc.promoted_lot(10_000.0, 500, dist_usd=0.005, symbol="EURUSD",
                                    risk_frac=frac, from_book=True))
    assert sum(1 for x in lots if x > 0) == 1


def test_rows_on_different_keys_or_off_the_book_are_never_folded() -> None:
    assert dc.fold_book_aliases({"a": "K1", "b": "K2", "c": None, "d": None}) == {}
    assert dc.fold_book_aliases({}) == {}


def test_the_gateway_folds_before_sizing_and_logs_alias_folded() -> None:
    src = (_DESK / "mt5desk" / "gateway.py").read_text(encoding="utf-8")
    assert "_aliases = fold_book_aliases(" in src
    i = src.index("_aliases = fold_book_aliases(")
    j = src.index('_s["risk_frac"], _s["alias_of"] = 0.0, _aliases[str(_s["name"])]')
    k = src.index('log(f"ALIAS_FOLDED')
    assert i < j < k
    # the alias stays sized by the book: allocator sovereignty sends no order at 0
    assert dc.promoted_lot(10_000.0, 500, dist_usd=0.005, symbol="EURUSD",
                           risk_frac=0.0, from_book=True) == 0.0
