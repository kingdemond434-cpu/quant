"""The decision core's fail-closed and bookkeeping edges, each driven and each asserted.

These are the branches the money path takes only when something upstream is malformed or
unusual: an override file that reads zero or NaN, a sovereignty file that does not disable,
a cert book that cannot load, an unpriceable instrument, a sleeves file that cannot be read,
a naive or garbled deadman timestamp, a fallback book solved above the heat it is deployed at,
an allocator zero list that is not a list, a feed or constraints table of the wrong shape, and
a closed trade whose stop priced to no money. Every test asserts the decision the core takes
on that edge -- the answer and, where the core gives one, the reason -- never just that the
line ran. Imported, like `test_decision_core.py`, so coverage attributes every branch.
"""
from __future__ import annotations

import importlib.util
import json
import math
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from mt5desk import decision_core as dc  # noqa: E402
from mt5desk import kelly_sizing  # noqa: E402

USDNOK = "usdnok_carry_asia_p_ff35bb7c8427d66f"
_FX_INFO = SimpleNamespace(volume_min=0.01, volume_step=0.01, volume_max=100.0,
                           trade_tick_size=0.00001, trade_tick_value=1.0)


# =========================================================================== the import guard

def test_the_core_puts_the_desk_root_on_sys_path_when_it_is_absent(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """`state_allows` imports `research.run_hunt12` the way the gateway does, so the core must
    put the desk root on sys.path itself when its importer did not. A fresh copy of the module
    is executed with the root removed; it must insert it at the front, exactly once."""
    desk = str(Path(dc.__file__).resolve().parent.parent)
    monkeypatch.setattr(sys, "path", [p for p in sys.path if p != desk])
    spec = importlib.util.spec_from_file_location("_dc_import_guard_copy", dc.__file__)
    assert spec is not None and spec.loader is not None
    copy = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, "_dc_import_guard_copy", copy)
    spec.loader.exec_module(copy)
    assert sys.path[0] == desk
    assert sys.path.count(desk) == 1
    assert Path(desk) == copy._DESK


# =========================================================================== override files

@pytest.mark.parametrize("body", ['{"lot": 0}', '{"lot": -0.05}', '{"lot": NaN}', "0"])
def test_a_gold_min_lot_file_reading_zero_negative_or_nan_is_the_constant(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, body: str) -> None:
    f = tmp_path / "GOLD_MIN_LOT.json"
    f.write_text(body, encoding="utf-8")
    monkeypatch.setattr(dc, "GOLD_MIN_LOT_FILE", f)
    assert dc.gold_min_lot() == float(dc.GOLD_MIN_LOT)


def test_a_gold_min_lot_file_can_raise_the_floor_but_never_lower_it(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    f = tmp_path / "GOLD_MIN_LOT.json"
    monkeypatch.setattr(dc, "GOLD_MIN_LOT_FILE", f)
    f.write_text('{"lot": 0.03}', encoding="utf-8")
    assert dc.gold_min_lot() == 0.03
    f.write_text('{"lot": 0.001}', encoding="utf-8")
    assert dc.gold_min_lot() == float(dc.GOLD_MIN_LOT)


@pytest.mark.parametrize("body,expected", [
    ('{"enabled": true}', True),
    ('{"note": "no switch here"}', True),
    ('["enabled", false]', True),
    ('{"enabled": false}', False),
])
def test_sovereignty_is_disabled_only_by_an_explicit_false(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, body: str, expected: bool) -> None:
    f = tmp_path / "ALLOCATOR_SOVEREIGN.json"
    f.write_text(body, encoding="utf-8")
    monkeypatch.setattr(dc, "ALLOCATOR_SOVEREIGN_FILE", f)
    assert dc.allocator_sovereign() is expected


# =========================================================================== the cert book

def test_an_unloadable_cert_book_zeroes_nothing_but_the_principal_zeros_still_bind(
        monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(path: object, venue: str) -> dict[str, float]:
        raise RuntimeError("cert book unreadable")

    monkeypatch.setattr(kelly_sizing, "load_cert_book", _boom)
    assert dc.cert_book_zero("eurusd_some_sleeve") is False
    # The code half reads no file, so it holds when the file half cannot.
    assert dc.cert_book_zero("gold_london_am") is True
    # And with a readable book the same name IS zeroed by it -- the False above is the load.
    monkeypatch.setattr(kelly_sizing, "load_cert_book",
                        lambda path, venue: {"EURUSD_Some_Sleeve": 0.0})
    assert dc.cert_book_zero("eurusd_some_sleeve") is True


# =========================================================================== the min-lot book

def test_an_unpriceable_instrument_sends_no_book_order_and_says_why(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dc, "ALLOCATOR_SOVEREIGN_FILE", tmp_path / "absent.json")
    monkeypatch.setattr(kelly_sizing, "load_cert_book", lambda path, venue: None)
    s = {"name": USDNOK, "minlot_override": True}
    lot, target, why = dc.minlot_override_size(s, "NOPE_NOT_A_SYMBOL", None, 485.0, 0.02)
    assert (lot, target) == (0.0, 0.0)
    assert "risk unpriceable" in why and "RiskUnitUnmeasured" in why and "no order" in why
    # Unparseable equity is the same refusal, never a default size.
    lot, target, why = dc.minlot_override_size(s, "USDNOK", _FX_INFO, "not-a-number", 0.02)
    assert (lot, target) == (0.0, 0.0) and "risk unpriceable (ValueError" in why


def test_the_floor_risk_bill_is_none_when_the_instrument_cannot_be_priced() -> None:
    assert dc.minlot_floor_risk_frac("NOPE_NOT_A_SYMBOL", None, 485.0, 0.02) is None
    assert dc.minlot_floor_risk_frac("USDNOK", _FX_INFO, "x", 0.02) is None
    frac = dc.minlot_floor_risk_frac("USDNOK", _FX_INFO, 485.0, 0.02)
    assert frac is not None and frac > 0.0


def test_a_boolean_allocator_fraction_is_not_a_number(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`True` is 1.0 to `float()`, and reading it so would fund a sleeve at 100% of equity."""
    assert math.isnan(dc._num_or_nan(True)) and math.isnan(dc._num_or_nan(False))
    assert math.isnan(dc._num_or_nan("x")) and dc._num_or_nan("0.25") == 0.25
    monkeypatch.setattr(dc, "ALLOCATOR_SOVEREIGN_FILE", tmp_path / "absent.json")
    monkeypatch.setattr(kelly_sizing, "load_cert_book", lambda path, venue: None)
    lot, target, why = dc.minlot_override_size(
        {"name": USDNOK, "minlot_override": True, "sized_by": "allocator_book",
         "risk_frac": True}, "USDNOK", _FX_INFO, 485.0, 0.02)
    assert (lot, target) == (0.0, 0.0) and "pins this sleeve at 0" in why


def _sleeves_file(tmp_path: Path, rows: list[dict]) -> Path:
    p = tmp_path / "sleeves.json"
    p.write_text(json.dumps({"sleeves": rows}), encoding="utf-8")
    return p


def test_override_rows_with_no_wanted_name_read_nothing(tmp_path: Path) -> None:
    # The path does not even exist: with nothing wanted it is never opened.
    assert dc.minlot_override_rows(tmp_path / "absent.json",
                                   frozenset({"eurusd_not_pinned", "gold_asia"})) == ([], [])


def test_an_unreadable_sleeves_file_admits_no_override_and_says_so(tmp_path: Path) -> None:
    bad = tmp_path / "sleeves.json"
    bad.write_text("{not json", encoding="utf-8")
    rows, notes = dc.minlot_override_rows(bad, frozenset({USDNOK}))
    assert rows == []
    assert notes == ["OVERRIDE_ROW_MISSING: sleeves file unreadable (JSONDecodeError)"]
    rows, notes = dc.minlot_override_rows(tmp_path / "absent.json", frozenset({USDNOK}))
    assert rows == [] and notes == ["OVERRIDE_ROW_MISSING: sleeves file unreadable "
                                    "(FileNotFoundError)"]


def test_an_already_admitted_name_is_not_read_twice(tmp_path: Path) -> None:
    """A name `load_sleeves_verbose` already admitted is skipped silently, even when its row
    would otherwise be refused -- the roster carries it once, from its own path."""
    row = {"name": USDNOK, "status": "KILL", "exec": "family_market",
           "certificate": {"cell": dc.MINLOT_OVERRIDE_PINS[USDNOK]}}
    path = _sleeves_file(tmp_path, [row])
    rows, notes = dc.minlot_override_rows(path, frozenset({USDNOK}), admitted={USDNOK})
    assert rows == [] and notes == []
    rows, notes = dc.minlot_override_rows(path, frozenset({USDNOK}), admitted=set())
    assert rows == [] and len(notes) == 1 and notes[0].startswith("OVERRIDE_STATUS_REFUSED")


# =========================================================================== the deadman gate

def _live_stamp(tmp_path: Path, checked_at: str) -> Path:
    p = tmp_path / "stamp.json"
    p.write_text(json.dumps({"mode": "LIVE", "checked_at": checked_at,
                             "broker_day": "2026-10-21",
                             "ledger": {"ok": True, "why": "test"}}), "utf-8")
    return p


@pytest.mark.parametrize("checked_at", ["2026-10-20T10:00:00", "yesterday-ish", "None"])
def test_a_naive_or_garbled_deadman_timestamp_refuses_new_risk(
        tmp_path: Path, checked_at: str) -> None:
    ok, why = dc.fusion_deadman_armed(_live_stamp(tmp_path, checked_at))
    assert ok is False
    assert why == "fusion deadman: checked_at unreadable; no new Fusion risk"


def test_the_same_stamp_with_an_aware_current_timestamp_is_armed(tmp_path: Path) -> None:
    """The control for the test above: the refusal is the timestamp, not the rest of the stamp."""
    at = (datetime.now(tz=UTC) - timedelta(seconds=30)).isoformat()
    ok, why = dc.fusion_deadman_armed(_live_stamp(tmp_path, at))
    assert ok is True and why.startswith("fusion deadman LIVE")


# =========================================================================== the allocator book

def test_a_fallback_book_solved_above_the_heat_is_scaled_down_to_it() -> None:
    book, why = dc.book_from_allocation(
        0.20, None, {"name": "risk_parity", "book": {"A": 0.30, "B": 0.10}},
        certified=False, why="proof stale")
    assert book is not None
    assert sum(book.values()) == pytest.approx(0.20)
    assert book["A"] == pytest.approx(0.15) and book["B"] == pytest.approx(0.05)
    assert book["A"] / book["B"] == pytest.approx(3.0)             # relative weights intact
    assert why == ("floor deployed with baseline risk_parity (2 sleeve(s)); "
                   "dynamic weights withheld: proof stale")


def test_a_fallback_book_below_the_heat_is_never_scaled_up() -> None:
    book, why = dc.book_from_allocation(
        0.20, None, {"name": "rp", "book": {"A": 0.05}}, certified=False, why="stale")
    assert book is None and why == "fallback book sums to 0.0500, heat says 0.2000"


def test_the_fallback_path_ignores_an_unreadable_zero_list_and_never_zeroes_a_funded_name() -> None:
    fb = {"name": "rp", "book": {"A": 0.10, "B": 0.10}}
    expected = ({"A": 0.10, "B": 0.10},
                "floor deployed with baseline rp (2 sleeve(s)); dynamic weights withheld: stale")
    # Not iterable: the book stands exactly as it was.
    assert dc.book_from_allocation(0.20, None, fb, certified=False, why="stale",
                                   zeroed=5) == expected
    # Every zeroed name is one the baseline funds: nothing is added, nothing is zeroed.
    assert dc.book_from_allocation(0.20, None, fb, certified=False, why="stale",
                                   zeroed=["A", "B"]) == expected
    # A mix: the funded name keeps its weight, the unfunded one is held at zero.
    book, why = dc.book_from_allocation(0.20, None, fb, certified=False, why="stale",
                                        zeroed=["A", "C"])
    assert book == {"A": 0.10, "B": 0.10, "C": 0.0}
    assert "(2 funded, 1 held at zero by this solve)" in why


def test_the_authoritative_book_ignores_an_unreadable_zero_list_and_keeps_funded_names() -> None:
    bk = {"A": 0.10, "B": 0.10}
    book, why = dc.book_from_allocation(0.20, bk, None, certified=True, why="ok", zeroed=5)
    assert book == bk and why == "allocator book authoritative (2 sleeve(s)); ok"
    book, why = dc.book_from_allocation(0.20, bk, None, certified=True, why="ok",
                                        zeroed=["A", "C"])
    assert book == {"A": 0.10, "B": 0.10, "C": 0.0}                # A keeps its 10%
    assert why == ("allocator book authoritative (2 sleeve(s), 1 held at zero by this "
                   "solve); ok")


# =========================================================================== the heat cap

def test_a_capped_book_left_under_the_floor_is_filled_and_the_note_names_the_fill() -> None:
    """Derived budget (no allocator verdict): limit = floor + slide. A 15% leg is admitted, the
    10% leg overshoots the limit and is deferred, the 20% leg too; the book is then short of the
    20% floor, so the fill takes the 10% leg (inside the ceiling) and stops at the floor. The
    20% leg stays deferred, and the note says both what was deferred and what the fill bought."""
    assert dc.heat_budget(None) == pytest.approx(dc.HEAT_TARGET)
    sleeves = [{"name": "A", "q_charge": 0.15}, {"name": "B", "q_charge": 0.10},
               {"name": "C", "q_charge": 0.20}]
    admitted, note = dc.cap_by_heat(sleeves, 1000.0)
    assert [s["name"] for s in admitted] == ["A", "B"]
    assert note is not None
    assert "deferring ['C']" in note and "admitting 2 at 25.0%" in note
    assert note.endswith(f"; filled to the {dc.HEAT_TARGET:.0%} floor with ['B'] "
                         f"(ceiling {max(dc.MAX_HEAT_CEILING, dc.HEAT_TARGET):.0%})")


# =========================================================================== the stampers

@pytest.mark.parametrize("doc", [{"instruments": ["XAUUSD"]}, {"instruments": None}, ["x"]])
def test_a_shapeless_feed_health_table_stamps_nothing(tmp_path: Path, doc: object) -> None:
    p = tmp_path / "feed_health.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    sleeves = [{"name": "a", "symbol": "XAUUSD"}]
    assert dc.stamp_feed_health(sleeves, p) == 0
    assert "feed_health" not in sleeves[0]


@pytest.mark.parametrize("doc", [{"symbols": "XAUUSD"}, {"symbols": []}, 7])
def test_a_shapeless_constraints_table_stamps_nothing(tmp_path: Path, doc: object) -> None:
    p = tmp_path / "market_constraints.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    sleeves = [{"name": "a", "symbol": "XAUUSD"}]
    assert dc.stamp_market_constraints(sleeves, p) == 0
    assert "constraints" not in sleeves[0]


# =========================================================================== closed-trade R

def test_a_stop_that_prices_to_no_money_has_no_r_multiple() -> None:
    """No tick value, and a zero contract size: the stop risked nothing measurable, so R is
    unreconstructible (0.0, 0.0) rather than a division by zero or an infinite R."""
    assert dc.closed_trade_r(100.0, 99.0, True, 0.0, 5.0) == (0.0, 0.0)
    assert dc.closed_trade_r(100.0, 99.0, True, -1.0, 5.0, volume=1.0) == (0.0, 0.0)
    # The control: a positive contract size gives the real ratio.
    risk, r = dc.closed_trade_r(100.0, 99.0, True, 100.0, 50.0, volume=0.5)
    assert risk == pytest.approx(50.0) and r == pytest.approx(1.0)
