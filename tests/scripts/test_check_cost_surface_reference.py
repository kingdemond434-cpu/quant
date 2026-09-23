"""THE COST-BASIS FENCE'S RULER: the broker's quote, not the H1 spread stamp.

Both directions are pinned. An UNDERCHARGED sleeve must still fail -- that is the direction that
manufactures survivors and the whole reason the fence exists. And a sleeve charged correctly
against the QUOTE must pass where the old stamp would have failed it, because the stamp samples
the widest instant of its hour: measured 2026-09-23, XAUUSD stamps 16 pts on H1 against a broker
quoting 5 at the desk's own fill minutes, and EURUSD stamps 12 against a live 0.0.

Every fixture is in tmp_path or an in-memory dict; no tracked file is read or written.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_spec = importlib.util.spec_from_file_location(
    "check_cost_surface", ROOT / "scripts" / "check_cost_surface.py")
assert _spec and _spec.loader
CCS = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(CCS)


def _cost_truth(symbol: str, *, asia: float | None = None, pooled: float | None = None,
                p90: float | None = None, live: float | None = None) -> dict[str, Any]:
    buckets: dict[str, Any] = {}
    if asia is not None:
        buckets["asia"] = {"status": "MEASURED", "n": 13000, "p50": asia, "p90": (p90 or asia)}
    return {"rollover_hour_utc": 21, "symbols": [
        {"symbol": symbol,
         "quoted": {"tape": {"by_session": buckets}},
         "compare": {"median_reference_pts": pooled, "quoted_p90_pts": p90,
                     "quoted_live_pts": live}}]}


def _sleeves(charged_per_lot: float, symbol: str = "XAUUSD") -> dict[str, Any]:
    return {"sleeves": {f"{symbol}.family.asia": {
        "status": "LIVE",
        "identity": {"symbol": symbol, "family": "family", "params": {}},
        "cost_fields": {"spread_per_lot": charged_per_lot}}}}


def _surface(symbol: str = "XAUUSD") -> dict[str, Any]:
    # tick_size 0.01 x contract_size 100 -> one point per lot is 1.0, so charged_pts == per_lot
    return {"symbols": {symbol: {"tick_size": 0.01, "contract_size": 100.0, "hours": {}}}}


@pytest.fixture(autouse=True)
def _fill_hours(monkeypatch: pytest.MonkeyPatch) -> None:
    """The sleeve fills in the asia session. Hours still come from the tape; the SPREAD no
    longer does -- that is the whole repoint."""
    monkeypatch.setattr(CCS, "fill_bars", lambda s, f, p: ([3] * 40, [16.0] * 40))


# ----------------------------------------------------------------- the dangerous direction


def test_an_undercharged_sleeve_still_fails() -> None:
    """Charged 0.5 pts against a book quoting 20: the survivor-manufacturing direction."""
    quotes = CCS.executable_index(_cost_truth("XAUUSD", asia=20.0))
    found, unresolved = CCS.scan_sleeves(_surface(), _sleeves(0.5), quotes)
    assert len(found) == 1 and not unresolved
    assert found[0]["direction"] == "UNDERCHARGED"
    assert found[0]["ratio"] == pytest.approx(40.0)
    assert found[0]["quoted_pts"] == pytest.approx(20.0)


def test_the_thresholds_are_untouched() -> None:
    """Only the ruler moved. A gate whose threshold moves with its evidence is welded open."""
    assert CCS.MATERIAL_RATIO == 2.0
    assert CCS.MIN_FILL_OBS == 30
    assert CCS.MAX_AGE_DAYS == 14


# ------------------------------------------------- the ruler that was wrong, in both directions


def test_a_sleeve_charged_at_the_quote_passes_where_the_stamp_would_have_failed_it() -> None:
    """XAUUSD: charged 5.0, broker quotes 5.0, H1 stamps 16.0.

    Against the stamp the ratio is 3.2x and the fence fails a sleeve that is charged exactly
    what the venue quotes. Against the quote it is 1.0x and passes. The stamp reading is
    published beside it so the repoint stays auditable rather than asserted.
    """
    quotes = CCS.executable_index(_cost_truth("XAUUSD", asia=5.0))
    found, unresolved = CCS.scan_sleeves(_surface(), _sleeves(5.0), quotes)
    assert found == [] and unresolved == []
    # and the old ruler really would have failed it
    stamp_ratio = 16.0 / 5.0
    assert stamp_ratio >= CCS.MATERIAL_RATIO


def test_an_overcharged_sleeve_is_still_reported_with_equal_weight() -> None:
    quotes = CCS.executable_index(_cost_truth("XAUUSD", asia=5.0))
    found, _ = CCS.scan_sleeves(_surface(), _sleeves(40.0), quotes)
    assert len(found) == 1 and found[0]["direction"] == "OVERCHARGED"


def test_a_zero_median_falls_to_the_p90_inside_the_sleeves_own_session() -> None:
    """A zero median is a REAL reading on Fusion Zero, but it cannot be a denominator."""
    quotes = CCS.executable_index(_cost_truth("XAUUSD", asia=0.0, p90=6.0))
    got = CCS.executable_reference(quotes["XAUUSD"], [3])
    assert got is not None and got[0] == pytest.approx(6.0)


def test_the_pooled_quote_is_used_when_the_fill_session_has_no_reading() -> None:
    quotes = CCS.executable_index(_cost_truth("XAUUSD", pooled=7.0))
    got = CCS.executable_reference(quotes["XAUUSD"], [3])
    assert got is not None and got[0] == pytest.approx(7.0)
    assert "pooled" in got[1]


def test_no_quote_at_all_is_unresolved_never_a_pass() -> None:
    quotes = CCS.executable_index(_cost_truth("EURUSD", asia=1.0))   # a different symbol
    found, unresolved = CCS.scan_sleeves(_surface(), _sleeves(0.5), quotes)
    assert found == [] and len(unresolved) == 1
    assert "no broker quote" in unresolved[0]["why"]


# ------------------------------------------------------------------------------- the ratchet


def _rep(sleeves: list[str]) -> dict[str, Any]:
    return {"checked_at": "2026-09-23T00:00:00+00:00", "status": "COST-BASIS-MISMATCH",
            "mispriced_sleeves": [{"sleeve": s} for s in sleeves]}


def test_a_new_mispriced_sleeve_fails_even_when_others_are_declared() -> None:
    got = CCS.ratchet_gate(_rep(["a", "b"]), {"mispriced_sleeves": ["a"]})
    assert got["status"] == "COST-BASIS-MISMATCH"
    assert got["new_since_declaration"] == ["b"]
    assert got["status"] not in CCS._PASSING


def test_a_fully_declared_residue_passes_and_says_so() -> None:
    got = CCS.ratchet_gate(_rep(["a", "b"]), {"mispriced_sleeves": ["a", "b"]})
    assert got["status"] == "DECLARED-RESIDUE"
    assert got["status"] in CCS._PASSING


def test_the_declaration_falls_when_the_debt_falls_and_is_never_raised_here(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "ratchet.json"
    declared = {"mispriced_sleeves": ["a", "b"]}
    path.write_text(json.dumps(declared), "utf-8")
    monkeypatch.setattr(CCS, "_RATCHET", path)
    shrunk = CCS.ratchet_gate(_rep(["a"]), declared)
    assert CCS.lower_ratchet(shrunk, declared) is True
    assert json.loads(path.read_text("utf-8"))["mispriced_sleeves"] == ["a"]
    # a GROWING debt is the failure; the fence never re-declares it
    grown = CCS.ratchet_gate(_rep(["a", "c"]), {"mispriced_sleeves": ["a"]})
    assert CCS.lower_ratchet(grown, {"mispriced_sleeves": ["a"]}) is False


def test_the_fence_is_wired_into_the_law_gate() -> None:
    """UNWIRED IS A DEFECT (LAWS 7). It returned rc=2 for weeks and blocked nothing."""
    gate = (ROOT / "scripts" / "run_law_gate.py").read_text("utf-8")
    assert '("check_cost_surface.py", ())' in gate
