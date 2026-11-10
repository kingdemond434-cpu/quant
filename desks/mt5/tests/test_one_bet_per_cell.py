"""One canonical cell on one timeframe is one bet, whether or not the allocator priced it.

The Judge, 2026-11-10: carry certificates and forward clocks exist as copies of one executable
under different names (`input_symbol=GBPJPY` and `=eBay` are the same rule) -- 43 canon
certificates across 8 pairs. #708 folds the rows that join one allocator BOOK key; a copy the
book has not priced joins no key, so each LIVE copy took the base fraction. Pinned here: such
rows fold on their own cell and timeframe, the oldest certificate (then the longest clock)
carries, and different timeframes, different cells and the gold windows are never folded.
"""
from __future__ import annotations

import sys
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import decision_core as dc  # noqa: E402


def _row(name: str, *, tf: str | None = None, gated: str | None = None, days: float = 0.0,
         symbol: str = "CHFDKK", family: str = "carry", selector: str = "asia") -> dict:
    row: dict = {"name": name, "status": "LIVE", "symbol": symbol, "family": family,
                 "selector": selector, "shadow_days": days}
    if tf:
        row["timeframe"] = tf
    if gated:
        row["certificate"] = {"gated_at": gated}
    return row


COPIES = [
    _row("CHFDKK.carry.asia#input_symbol=GBPJPY", gated="2026-09-20T00:00:00+00:00", days=30),
    _row("CHFDKK.carry.asia#input_symbol=eBay", gated="2026-09-02T00:00:00+00:00", days=41),
    _row("CHFDKK.carry.asia#input_symbol=CHFDKK", gated="2026-09-02T00:00:00+00:00", days=12),
]


def test_the_cell_key_is_the_cell_and_its_timeframe() -> None:
    assert dc.cell_key(COPIES[0]) == "cell:chfdkk|carry|asia|h1"
    assert dc.cell_key(_row("CHFDKK.carry.asia@M15#input_symbol=CHFDKK")) \
        == "cell:chfdkk|carry|asia|m15"
    assert dc.cell_key(_row("x", tf="M30")) == "cell:chfdkk|carry|asia|m30"
    assert dc.cell_key({"name": "gold_asia", "symbol": "XAUUSD"}) is None      # no family
    assert dc.cell_key({"name": "orphan"}) is None


def test_unpriced_copies_of_one_executable_send_one_order() -> None:
    rows = [*COPIES, _row("CHFDKK.carry.asia@M15#input_symbol=CHFDKK"),
            _row("nzdchf_clock_transition_asia_p_1", symbol="NZDCHF",
                 family="clock_transition")]
    keys = {r["name"]: dc.cell_key(r) for r in rows}                # none is in the book
    aliases = dc.fold_book_aliases(keys, {r["name"]: dc.carrier_rank(r) for r in rows})
    # the oldest certificate carries; between two of the same date, the longest clock
    carrier = "CHFDKK.carry.asia#input_symbol=eBay"
    assert aliases == {"CHFDKK.carry.asia#input_symbol=GBPJPY": carrier,
                       "CHFDKK.carry.asia#input_symbol=CHFDKK": carrier}
    sent = [r["name"] for r in rows if r["name"] not in aliases]
    assert sent == [carrier,
                    "CHFDKK.carry.asia@M15#input_symbol=CHFDKK",   # another timeframe: own bet
                    "nzdchf_clock_transition_asia_p_1"]            # another cell: own bet


def test_without_a_rank_the_first_name_still_carries() -> None:
    assert dc.fold_book_aliases({"b": "K", "a": "K", "c": None}) == {"b": "a"}
    assert dc.carrier_rank({"name": "x"}) == ("9999", -0.0)


def test_the_gateway_folds_priced_and_unpriced_rows_before_sizing() -> None:
    src = (_DESK / "mt5desk" / "gateway.py").read_text(encoding="utf-8")
    i = src.index("else (_book_key(_s, _book) or cell_key(_s)))")
    j = src.index("_aliases = fold_book_aliases(_fold_keys,")
    k = src.index('and str(_fold_keys.get(str(_s["name"])) or "").startswith("cell:"))]')
    m = src.index("        _key = _book_key(_s, _book)\n".replace("\n", "\r\n" if "\r\n" in src
                                                                 else "\n"))
    assert i < j < k < m, "unpriced aliases leave the roster before any row is sized"
    assert "ALIAS_FOLDED" in src[j:m]
