"""THE TWO DEFECTS `heal_identity_broken_clocks.py` MINTED, pinned so they cannot come back.

Measured on the trading box 2026-09-24 against the LIVE sleeve registry (355 LIVE clocks):

  * 13 LIVE rows carried NO `cost_fields` at all -- 8 of them XAUUSD, covering the asia,
    london_am and afternoon gold windows. Every one was frozen by this script, the ONE
    `sleeve_registry.freeze()` caller that omitted the `cost_fields=` argument that
    `shadow_forward` has always passed. A null cost is not a zero cost: `shadow_forward`
    line 758 falls through to LIVE re-measured costs, so the clock's basis moves under it.

  * `XAUUSD.multi_speed_trend.continuous@D1` froze as
    `family=session_range_breakout, selector=multi_speed_trend` -- transposed. `legacy_identity`
    hardcoded the hunt16 family and read slot 1 as a window, and its guard rejected only keys
    containing `=` or `#`, so a modern `SYM.family.selector@TF` key with empty params fell
    through. 20+ RETIRED rows carry the same swap. The canonical identity is
    `symbol|family|selector`, so a transposed row joins nothing.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
for p in (DESK / "scripts", DESK / "research", DESK, DESK.parents[1]):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

heal = pytest.importorskip("heal_identity_broken_clocks")


def test_a_window_key_still_reads_as_the_hunt16_family():
    """The historic shape must not move: `SYM.window[.STATE]` is session_range_breakout."""
    ident = heal.legacy_identity("XAUUSD.asia.NORMAL_DAY", {})
    assert ident == {"symbol": "XAUUSD", "selector": "asia",
                     "family": "session_range_breakout", "side": "LONG",
                     "params": {}, "state": "NORMAL_DAY"}


def test_a_family_in_slot_one_is_a_family_and_not_a_window(monkeypatch):
    """The exact key that broke on the box. family and selector must land the right way round,
    and the `@D1` must come off the selector -- a timeframe glued to a selector breaks the same
    join the transposition broke."""
    monkeypatch.setattr(heal, "is_registered_family",
                        lambda name: name == "multi_speed_trend")
    ident = heal.legacy_identity("XAUUSD.multi_speed_trend.continuous@D1", {})
    assert ident["family"] == "multi_speed_trend"
    assert ident["selector"] == "continuous"
    assert ident["timeframe"] == "D1"
    assert ident["symbol"] == "XAUUSD"
    canonical = "|".join([ident["symbol"], ident["family"], ident["selector"]]).lower()
    assert canonical == "xauusd|multi_speed_trend|continuous"


def test_a_bare_family_key_defaults_the_selector_to_continuous(monkeypatch):
    monkeypatch.setattr(heal, "is_registered_family", lambda name: name == "carry")
    ident = heal.legacy_identity("AUDJPY.carry", {})
    assert ident["family"] == "carry" and ident["selector"] == "continuous"


def test_an_unresolvable_family_registry_keeps_the_historic_behaviour(monkeypatch):
    """`is_registered_family` reads FALSE when the resolver cannot be imported, so an import
    failure can never invent a family that is not there -- it falls back, it does not guess."""
    monkeypatch.setattr(heal, "is_registered_family", lambda name: False)
    ident = heal.legacy_identity("XAUUSD.multi_speed_trend.continuous@D1", {})
    assert ident["family"] == "session_range_breakout"


def test_the_resolver_is_the_engines_own_and_refuses_a_nonsense_name():
    """No hardcoded list: a name the engine cannot construct is not a family."""
    assert heal.is_registered_family("definitely_not_a_family_name_9f3a") is False


def test_freeze_is_called_with_a_cost_basis(monkeypatch, tmp_path):
    """THE ONE-LINE DEFECT. Every LIVE row this script minted was born unpriced because this
    call passed no `cost_fields`."""
    shadow = DESK / "reports" / "shadow" / "shadow_state.json"
    calls = []

    class _Reg:
        @staticmethod
        def freeze(key, ident, *, forward_start=None, cost_fields=None):
            calls.append({"key": key, "ident": ident, "cost_fields": cost_fields})

    monkeypatch.setattr(heal, "reg", _Reg)
    monkeypatch.setattr(heal, "cost_fields_for",
                        lambda sym: {"spread_per_lot": 3.0, "commission_per_lot": 2.0,
                                     "contract_oz": 100.0, "quote_per_account": 1.15844})
    state = tmp_path / "shadow_state.json"
    state.write_text('{"XAUUSD.asia": {"status": "ACTIVE", "forward_start": "2026-08-25"}}',
                     "utf-8")
    monkeypatch.setattr(Path, "read_text",
                        lambda self, *a, **k: state.read_text("utf-8")
                        if self == shadow else Path.read_bytes(self).decode("utf-8"))

    n = heal.freeze_unfrozen({"sleeves": {}}, apply=True)
    assert n == 1
    assert len(calls) == 1
    assert calls[0]["cost_fields"] == {"spread_per_lot": 3.0, "commission_per_lot": 2.0,
                                       "contract_oz": 100.0, "quote_per_account": 1.15844}


def test_an_unmeasurable_cost_is_passed_as_none_never_as_a_guess():
    """UNMEASURED is a real answer (L1.28a). A guessed cost basis on a LIVE clock is worse than
    an absent one, because it looks measured."""
    assert heal.cost_fields_for("NOT_A_SYMBOL_XYZ") is None
    assert heal.cost_fields_for("") is None
