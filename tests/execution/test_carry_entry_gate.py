"""Tests for the carry entry gate's two evidence channels -- the funding floor and the
structural-bleed denylist.

BOTH PIN A MEASURED 2026-08-05 DEFECT, not a hypothetical:

1. THE DENYLIST FORGOT ITS EVIDENCE. `_structurally_bleeding` read `worst_symbols`, which
   run_trade_forensics computes over a 14-DAY ROLLING window. That window is correct for the
   pager and exactly wrong for a fence: on 2026-08-05 it held 42 of 253 all-time closes and
   named ONE bleeder, while six qualified all-time. BNBUSDT -- named as a proven loser in the
   executor's own source comment, -65.8 bps over 13 closes -- was rehabilitated by nothing but
   the calendar and re-opened 2026-07-31 and 2026-08-01. The fence now reads `bleeding_symbols`
   (all-time, same bar). An exclusion whose path back is the passage of time is not evidence.

2. THE REGRESSION DETECTOR UNDER-COUNTED. run_trade_forensics matched funding EXACTLY at the
   venue default (1e-4), so it saw opens sitting ON the default and missed every open BELOW it:
   BNBUSDT went on at 3.0e-05 and 6.6e-05, both further under the bar than the two it reported.
   It now compares against the executor's actual floor, and this file asserts the mirrored
   constant cannot drift -- the mirror exists because importing the executor opens venue
   connections, so the coupling has to be enforced by a test rather than by an import.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, _ROOT / rel)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_EXEC = _load("run_cashcarry_executor_gate", "scripts/run_cashcarry_executor.py")
_FOR = _load("run_trade_forensics_gate", "scripts/run_trade_forensics.py")


def test_funding_floor_constant_is_mirrored_not_drifted() -> None:
    """The forensics detector must measure the bar the executor actually enforces."""
    assert _FOR._MIN_FUNDING == _EXEC._MIN_FUNDING, (
        "run_trade_forensics._MIN_FUNDING mirrors the executor's funding floor; they have "
        "drifted, so the entry-gate regression check is now measuring a bar nobody enforces"
    )


def test_denylist_bar_is_mirrored_not_drifted() -> None:
    assert _FOR._DENY_BPS == _EXEC._BLEED_BPS
    assert _FOR._DENY_MIN_N == _EXEC._BLEED_MIN_N


@pytest.fixture
def forensics(tmp_path, monkeypatch):
    """Point the executor's fence at a throwaway forensics artifact."""
    p = tmp_path / "trade_forensics.json"
    monkeypatch.setattr(_EXEC, "_FORENSICS", p)
    return p


def test_fence_reads_all_time_key_not_the_rolling_one(forensics) -> None:
    """THE REGRESSION ITSELF: a bleeder absent from the 14d window is still blocked."""
    forensics.write_text(json.dumps({
        # BNBUSDT has aged out of the rolling window entirely -- this is the exact shape of
        # web/trade_forensics.json on 2026-08-05, which named only 1000CATUSDT.
        "worst_symbols": [{"symbol": "1000CATUSDT", "n": 5, "net": -43.32, "bps": -74.6}],
        "bleeding_symbols": [{"symbol": "BNBUSDT", "n": 13, "net": -23.46, "bps": -65.8},
                             {"symbol": "1000CATUSDT", "n": 5, "net": -43.32, "bps": -74.6}],
    }), "utf-8")
    assert _EXEC._structurally_bleeding("BNBUSDT") is True
    assert _EXEC._structurally_bleeding("1000CATUSDT") is True
    assert _EXEC._structurally_bleeding("ETHUSDT") is False


def test_fence_falls_back_to_worst_symbols_when_key_absent(forensics) -> None:
    """An artifact written before this change must still fence, not silently open the gate."""
    forensics.write_text(json.dumps({
        "worst_symbols": [{"symbol": "NOMUSDT", "n": 5, "net": -78.85, "bps": -149.4}],
    }), "utf-8")
    assert _EXEC._structurally_bleeding("NOMUSDT") is True


def test_empty_all_time_list_still_honours_the_rolling_one(forensics) -> None:
    """PINS THE `or` IN THE FENCE, which is deliberate rather than incidental.

    An EMPTY bleeding_symbols is falsy, so the read falls through to worst_symbols. A symbol can
    bleed inside the last 14d without yet clearing the all-time bar (n < 5 all-time), and the
    fence's stated invariant is strictly RESTRICTIVE -- so falling through blocks MORE, never
    less. Choosing `in doc` instead would unblock that symbol, which is the wrong direction.
    """
    forensics.write_text(json.dumps({
        "bleeding_symbols": [],
        "worst_symbols": [{"symbol": "FRESHUSDT", "n": 5, "net": -40.0, "bps": -80.0}],
    }), "utf-8")
    assert _EXEC._structurally_bleeding("FRESHUSDT") is True


def test_fence_fails_open_only_when_the_artifact_is_unreadable(forensics) -> None:
    """No artifact at all cannot block every symbol -- but it must not be reachable silently."""
    assert _EXEC._structurally_bleeding("BTCUSDT") is False
    forensics.write_text("{not json", "utf-8")
    assert _EXEC._structurally_bleeding("BTCUSDT") is False


def test_entry_gate_refuses_below_floor_and_denylisted(forensics, monkeypatch) -> None:
    """End-to-end on the gate the open loop actually calls."""
    forensics.write_text(json.dumps({
        "bleeding_symbols": [{"symbol": "BNBUSDT", "n": 13, "net": -23.46, "bps": -65.8}],
    }), "utf-8")
    monkeypatch.setattr(_EXEC, "_rt_bps", lambda _s: 1.0)   # cheap book: isolate the two vetoes

    # the four real sub-floor opens of 2026-07-31/08-01, replayed against current code
    assert _EXEC._entry_gate("BTCUSDT", 0.0001) is False      # at the venue default
    assert _EXEC._entry_gate("FILUSDT", 0.0001) is False
    assert _EXEC._entry_gate("BNBUSDT", 3.0e-05) is False     # below it AND denylisted
    assert _EXEC._entry_gate("BNBUSDT", 6.6e-05) is False
    # a clean symbol comfortably over the floor still passes -- the fence is not a blanket veto
    assert _EXEC._entry_gate("ETHUSDT", 0.0004) is True


def test_denylist_veto_survives_a_high_funding_rate(forensics, monkeypatch) -> None:
    """Funding is the compensation for illiquidity, so a proven loser often looks ATTRACTIVE on
    rate alone. The denylist must outrank it or it buys the bleed back at a better headline."""
    forensics.write_text(json.dumps({
        "bleeding_symbols": [{"symbol": "NOMUSDT", "n": 5, "net": -78.85, "bps": -149.4}],
    }), "utf-8")
    monkeypatch.setattr(_EXEC, "_rt_bps", lambda _s: 1.0)
    assert _EXEC._entry_gate("NOMUSDT", 0.01) is False


def test_forensics_emits_all_time_bleeders_over_the_full_record(tmp_path, monkeypatch) -> None:
    """The producer half: `bleeding_symbols` must ignore the rolling cutoff `worst_symbols` uses."""
    old = "2020-01-01T00:00:00+00:00"          # far outside any rolling window
    trades = [{"event": "close", "symbol": "OLDUSDT", "held_hours": 30.0, "closed": old,
               "notional": 100.0, "net": -1.0} for _ in range(_FOR._DENY_MIN_N)]
    monkeypatch.setattr(_FOR, "_TRADES", tmp_path / "t.json")
    monkeypatch.setattr(_FOR, "_OUT", tmp_path / "out.json")
    _FOR._TRADES.write_text(json.dumps(trades), "utf-8")
    _FOR.main()

    out = json.loads((tmp_path / "out.json").read_text("utf-8"))
    assert out["worst_symbols"] == []                       # rolling window: correctly empty
    syms = [r["symbol"] for r in out["bleeding_symbols"]]    # all-time: -100 bps, still counted
    assert syms == ["OLDUSDT"], "the denylist's evidence must not expire with the calendar"
    assert out["bleeding_basis"]["window"] == "all-time"


def test_forensics_flags_sub_floor_opens_not_just_baseline_ones(tmp_path, monkeypatch) -> None:
    """The detector half: an open BELOW the floor is a bypass even if it is not AT the default."""
    after = "2026-07-31T07:15:45+00:00"                      # after _GATE_DATE
    trades = [{"event": "open", "symbol": "BNBUSDT", "opened": after,
               "funding_rate": 3.0e-05, "notional": 47.36}]
    monkeypatch.setattr(_FOR, "_TRADES", tmp_path / "t.json")
    monkeypatch.setattr(_FOR, "_OUT", tmp_path / "out.json")
    _FOR._TRADES.write_text(json.dumps(trades), "utf-8")
    _FOR.main()

    out = json.loads((tmp_path / "out.json").read_text("utf-8"))
    assert out["post_gate_baseline_opens"] == 1, (
        "3.0e-05 is further below the floor than the 1e-4 opens the old exact-match check "
        "reported; under-counting a bypass reads as a bounded problem"
    )
    assert any("ENTRY-GATE REGRESSION" in f for f in out["flags"])
