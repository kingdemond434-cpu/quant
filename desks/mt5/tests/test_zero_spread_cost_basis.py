"""A 0.0 median spread is a measurement on Fusion ZERO only when the TAPE observed it (v2).

Principal, 2026-08-29 (`mt5desk/universe.py`, `usable`): "ZERO SPREAD IS REAL ON THIS ACCOUNT ...
Fusion ZERO is commission-only". `external_gauntlet.registry_cost_basis` refused every spread not
above 0, so every major the account quotes at zero failed swap_cost as UNMEASURED on a cost the
engine had charged in full.

v1 (1aa4b33f) accepted an UNSTAMPED zero too. The v1 audit (HOLD) showed why that is unsafe: an
unstamped registry zero cannot be told from a `symbol_info.spread` read before any tick arrived,
which is a stub. v2 accepts a zero ONLY on positive evidence, meaning the tape's observed-zero
stamp (`fusion_spread_tape.observed_zero`, written by `repair_universe_spreads`). It also fails
closed and never raises on a `_provenance` that is not a map.

These tests skip until the v2 sealed patch is applied (marker `_zero_spread_stamp`), then pin
it.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DESK))
eg = pytest.importorskip("scripts.external_gauntlet")
pytestmark = pytest.mark.skipif(
    not hasattr(eg, "_zero_spread_stamp"),
    reason="zero_spread_cost_basis v2 sealed patch not applied",
)

#: EURUSD as origin's registry carries it (2026-09-30), commission-only.
MAJOR = {
    "median_spread_pts": 0.0,
    "tick_size": 1e-05,
    "tick_value": 0.8620689655172415,
    "contract_size": 100000.0,
    "swap_long": -6.35,
    "swap_short": 2.59,
}
#: The tape's stamp, as `repair_universe_spreads` writes it for an observed zero.
STAMP = {
    "_provenance": {
        "median_spread_pts": {
            "source": "fusion_zero_m1_tape",
            "zero_spread": True,
            "zero_evidence": {"stamp": "observed_zero", "days_full": 20, "days_zero_median": 20},
        }
    }
}


def _meta(**row):
    return {"EURUSD": {**MAJOR, **row}}


def test_a_tape_stamped_zero_is_measured_and_charged_commission() -> None:
    r = eg.registry_cost_basis("EURUSD", _meta(**STAMP))
    assert r["measured"] is True and r.get("zero_spread") is True
    assert "commission" in r["why"] and "observed" in r["why"]
    c = eg.costs_for("EURUSD", _meta(**STAMP))
    commission = c.commission_per_lot * 2.0 * float(c.quote_per_account)
    assert commission > 0 and c.per_oz_roundtrip() >= commission


def test_an_unstamped_zero_is_unmeasured_it_may_be_a_no_tick_stub() -> None:
    r = eg.registry_cost_basis("EURUSD", _meta())
    assert r["measured"] is False and "median_spread_pts" in r["why"]
    assert "stub" in r["why"]
    # provenance on OTHER fields only is still no stamp for the zero
    other_field = {"_provenance": {"tick_value": {"source": "broker_reported"}}}
    assert eg.registry_cost_basis("EURUSD", _meta(**other_field))["measured"] is False


@pytest.mark.parametrize(
    "prov",
    [
        ["legacy"],
        "a string",
        7,
        {"median_spread_pts": ["x"]},
        {"median_spread_pts": "fusion_zero_m1_tape"},
    ],
)
def test_a_provenance_that_is_not_a_map_fails_closed_and_never_raises(prov) -> None:
    r = eg.registry_cost_basis("EURUSD", _meta(_provenance=prov))
    assert r["measured"] is False and "median_spread_pts" in r["why"]


def test_only_the_tapes_observed_zero_stamp_counts() -> None:
    h1 = {"_provenance": {"median_spread_pts": {"source": "h1_spread_median", "zero_spread": True}}}
    r = eg.registry_cost_basis("EURUSD", _meta(**h1))
    assert r["measured"] is False and "h1_spread_median" in r["why"]
    # the tape's source WITHOUT the observed-zero flag: e.g. a stamp from a positive reading
    no_flag = {"_provenance": {"median_spread_pts": {"source": "fusion_zero_m1_tape"}}}
    r = eg.registry_cost_basis("EURUSD", _meta(**no_flag))
    assert r["measured"] is False and "zero_spread" in r["why"]
    truthy = {
        "_provenance": {
            "median_spread_pts": {"source": "fusion_zero_m1_tape", "zero_spread": "yes"}
        }
    }
    assert eg.registry_cost_basis("EURUSD", _meta(**truthy))["measured"] is False


def test_the_sources_match_the_tapes_own_stamp() -> None:
    sys.path.insert(0, str(DESK / "research"))
    import fusion_spread_tape as fst

    assert frozenset({fst.SOURCE}) == eg.ZERO_SPREAD_SOURCES


def test_the_cells_cost_is_the_engines_round_trip() -> None:
    from mt5desk.engine import Costs

    for row in ({**MAJOR, **STAMP}, {**MAJOR, "median_spread_pts": 3.0}):
        meta = {"EURUSD": row}
        assert eg.costs_for("EURUSD", meta).per_oz_roundtrip() == pytest.approx(
            Costs.from_symbol(row).per_oz_roundtrip()
        )


@pytest.mark.parametrize("bad", [-1.0, None, "n/a", True])
def test_a_negative_or_missing_spread_is_still_unmeasured(bad) -> None:
    meta = _meta(median_spread_pts=bad, **STAMP)
    if bad is None:
        meta["EURUSD"].pop("median_spread_pts")
    r = eg.registry_cost_basis("EURUSD", meta)
    assert r["measured"] is False and "median_spread_pts" in r["why"]


@pytest.mark.parametrize("field", ["tick_value", "tick_size", "contract_size"])
def test_a_stamped_zero_with_no_way_to_charge_commission_is_unmeasured(field) -> None:
    r = eg.registry_cost_basis("EURUSD", _meta(**{field: 0.0}, **STAMP))
    assert r["measured"] is False and "median_spread_pts" in r["why"] and field in r["why"]


def test_a_positive_spread_reads_exactly_as_before() -> None:
    r = eg.registry_cost_basis("EURUSD", _meta(median_spread_pts=12.0))
    assert r == {
        "measured": True,
        "why": "spread, commission conversion and swap from the registry",
    }
    assert eg.registry_cost_basis("X", {"X": {"tick_size": 0.0}})["measured"] is False


def test_the_basis_reaches_swap_cost_only_and_no_trial_count() -> None:
    """Trial counts are unchanged: the basis is read in exactly one place, the swap_cost stage,
    and no trial census or charge reads it."""
    src = (DESK / "scripts" / "external_gauntlet.py").read_text("utf-8")
    calls = [
        ln
        for ln in src.splitlines()
        if "registry_cost_basis(" in ln and not ln.lstrip().startswith("def ")
    ]
    assert len(calls) == 1 and "_basis = registry_cost_basis(" in calls[0]
    trial_fns = re.findall(r"^def (\w*trial\w*)\(", src, flags=re.M)
    assert trial_fns  # the census and charge functions exist
    for fn in trial_fns:
        start = src.index(f"\ndef {fn}(")
        nxt = src.find("\ndef ", start + 1)
        body = src[start : nxt if nxt > 0 else None]
        assert "registry_cost_basis" not in body and "_zero_spread_stamp" not in body, fn
