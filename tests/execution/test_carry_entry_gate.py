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

2. THE ENTRY-GATE DETECTOR MUST MEASURE THE BAR THE EXECUTOR ENFORCES. It originally matched
   funding EXACTLY at the venue default and missed every open BELOW it; the 2026-08-05 fix
   mirrored a flat floor, and R0057 then replaced that floor with a PER-SYMBOL contract (funding
   over the minimum hold must beat that symbol's modelled round-trip). The coupling asserted here
   moved with it -- the shared hold horizon, not a retired constant. The mirror exists at all
   because importing the executor opens venue connections, so it has to be enforced by a test.

AND THIS FILE IS ITSELF THE EVIDENCE FOR A THIRD DEFECT (2026-08-13). Merge 8b981a50 kept these
tests and dropped the producer and reader that made them true, so the fence silently reverted to
the rolling window while the suite went red and STAYED red for eight days -- read as ordinary
environment noise. Two of the reds were genuine staleness (a 1-arg `_rt_bps` stub, a flat floor
that no longer exists) and one was this file reading the LIVE cost model, which moved under it.
A test that fails for reasons unrelated to its subject trains readers to discount red, which is
what let a money-path regression hide in plain sight; the cost model is now injected.
"""
from __future__ import annotations

import importlib.util
import json
from datetime import UTC, datetime, timedelta
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


def test_the_detector_measures_the_bar_the_executor_actually_enforces() -> None:
    """The floor this file used to mirror NO LONGER EXISTS, and that is the correct outcome.

    `_MIN_FUNDING` was a single desk-wide funding floor mirrored into the detector (2026-08-05).
    R0057 replaced it with a PER-SYMBOL contract -- an open is a regression iff its funding could
    not beat that symbol's modelled round-trip over the minimum hold -- so a flat constant is no
    longer the bar anyone enforces and mirroring one would re-blind the check it was added to
    sharpen. What must still hold is the coupling itself: the detector reads the executor's own
    cost model and hold horizon rather than a number of its own.
    """
    assert not hasattr(_EXEC, "_MIN_FUNDING"), (
        "a flat funding floor is back in the executor -- if it governs opens the detector must "
        "mirror it again; if it does not, delete it"
    )
    assert max(1.0, _EXEC._MIN_HOLD_H / 8.0) == _FOR._GATE_PERIODS, (
        "the detector prices funding over a different number of 8h settlement periods than the "
        "executor requires a carry to hold, so it is judging opens against a horizon nobody "
        "enforces"
    )


def test_denylist_bar_is_mirrored_not_drifted() -> None:
    assert _FOR._DENY_BPS == _EXEC._BLEED_BPS
    assert _FOR._DENY_MIN_N == _EXEC._BLEED_MIN_N


@pytest.fixture
def forensics(tmp_path, monkeypatch):
    """Point the executor's fence at a throwaway forensics artifact.

    `_BLEED_CACHE` too: the fence writes every non-empty read through to a last-good cache the
    live executor consults when forensics is unreadable, so an un-redirected fixture would leave
    synthetic bleeders in a money-path file. conftest covers this suite-wide; pinning it here as
    well keeps the isolation visible to anyone reading only this file.
    """
    p = tmp_path / "trade_forensics.json"
    monkeypatch.setattr(_EXEC, "_FORENSICS", p)
    monkeypatch.setattr(_EXEC, "_BLEED_CACHE", tmp_path / "last_good.json")
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


def test_entry_gate_prices_each_symbol_against_its_own_round_trip(forensics, monkeypatch) -> None:
    """End-to-end on the gate the open loop actually calls, under the R0057 contract.

    This asserted a FLAT floor (`funding >= 1.5e-4`), so it read baseline funding as a refusal
    everywhere. R0057 replaced that with a per-symbol test -- funding over the minimum hold must
    beat THAT symbol's round-trip -- under which baseline funding on a tight measured major
    legitimately passes and the same rate on a thin book cannot. Pinning the retired constant
    would have re-imposed a bar the desk deliberately removed, so the contract is pinned instead:
    the same funding rate must flip on the BOOK, and the denylist must outrank both.
    """
    forensics.write_text(json.dumps({
        "bleeding_symbols": [{"symbol": "BNBUSDT", "n": 13, "net": -23.46, "bps": -65.8}],
    }), "utf-8")
    # `_n` absorbs R0247's `notional` argument -- a 1-arg stub silently drifted into a TypeError
    # when the gate started sizing its cost lookup.
    books = {"BTCUSDT": 1.0, "FILUSDT": 25.0, "BNBUSDT": 1.0, "ETHUSDT": 1.0}
    monkeypatch.setattr(_EXEC, "_rt_bps", lambda s, _n=None: books.get(s, 39.5))

    # 0.0001 over 3 periods = 3 bps. Beats a 1 bps major, cannot pay for a 25 bps book.
    assert _EXEC._entry_gate("BTCUSDT", 0.0001) is True
    assert _EXEC._entry_gate("FILUSDT", 0.0001) is False
    # DENYLIST OUTRANKS THE ARITHMETIC: BNBUSDT's book is stubbed as cheap as BTCUSDT's, so it
    # would pass on cost alone. The proven-loser veto is what refuses it -- at every rate.
    assert _EXEC._entry_gate("BNBUSDT", 3.0e-05) is False
    assert _EXEC._entry_gate("BNBUSDT", 0.0001) is False
    # and the fence is not a blanket veto
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


def test_forensics_flags_opens_that_could_not_beat_their_own_round_trip(
    tmp_path, monkeypatch
) -> None:
    """The detector half, on the R0057 per-symbol contract that replaced the flat floor.

    An open is a regression iff its funding could not beat THAT SYMBOL's modelled round-trip over
    the minimum hold -- so the cost model is an input to the verdict and must be injected. It used
    to be read from `data/cost_model.json` inside main(), which made this test a reader of live
    desk state: the measured BNBUSDT book got cheaper (0.344 bps), 0.9 bps of funding beat it,
    and the test went red without the detector changing at all.
    """
    recent = (datetime.now(tz=UTC) - timedelta(days=1)).isoformat()   # inside the rolling window
    trades = [
        # 3.0e-05 over 3 periods = 0.9 bps against a 12 bps book -> cannot pay for itself
        {"event": "open", "symbol": "THINUSDT", "opened": recent,
         "funding_rate": 3.0e-05, "notional": 47.36},
        # 40 bps of funding against the same book -> legitimately passes; the flag is not blanket
        {"event": "open", "symbol": "THINUSDT", "opened": recent,
         "funding_rate": 1.5e-03, "notional": 47.36},
    ]
    cost = tmp_path / "cost_model.json"
    cost.write_text(json.dumps({"symbols": {"THINUSDT": {"pair": {
        "500": {"pair_roundtrip_bps": 12.0}}}}}), "utf-8")
    monkeypatch.setattr(_FOR, "_TRADES", tmp_path / "t.json")
    monkeypatch.setattr(_FOR, "_OUT", tmp_path / "out.json")
    monkeypatch.setattr(_FOR, "_TRACKED", tmp_path / "tracked.json")
    monkeypatch.setattr(_FOR, "_COST_MODEL", cost)
    _FOR._TRADES.write_text(json.dumps(trades), "utf-8")
    _FOR.main()

    out = json.loads((tmp_path / "out.json").read_text("utf-8"))
    assert out["post_gate_opens_examined"] == 2
    assert out["post_gate_baseline_opens"] == 1, (
        "the sub-contract open must be counted and the paying one must not -- a detector that "
        "under-counts the defect it exists to catch reads as bounded"
    )
    assert any("ENTRY-GATE REGRESSION" in f for f in out["flags"])
