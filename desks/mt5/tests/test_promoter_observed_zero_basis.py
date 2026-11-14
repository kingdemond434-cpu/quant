"""The promoter's cost basis takes the same zero the gate takes, and no other (2026-10-21).

The v1 audit flagged `promoter.cost_basis_of` (`:324`) as incoherent with the new gate: it still
required spread > 0. A cell certified on the tape's observed zero would reach LIVE and then be
demoted to STANDBY for "registry cost fields incomplete". The sealed promoter patch
`promoter_cost_basis_observed_zero_on_bb9c0e74.patch` accepts exactly the stamped zero. These
tests skip until that patch is applied.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK), str(DESK / "research"), str(DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import promoter  # noqa: E402

pytestmark = pytest.mark.skipif(
    not hasattr(promoter, "_observed_zero"), reason="promoter observed-zero patch not applied"
)

_ROW = {
    "median_spread_pts": 0.0,
    "tick_size": 1e-05,
    "tick_value": 0.86,
    "contract_size": 100000.0,
    "swap_long": -6.35,
    "swap_short": 2.59,
}
_STAMP = {"median_spread_pts": {"source": "fusion_zero_m1_tape", "zero_spread": True}}


def _basis(**meta):
    return promoter.cost_basis_of({"name": "x", "symbol": "EURUSD"}, {"EURUSD": {**_ROW, **meta}})


def test_a_tape_stamped_zero_is_a_basis() -> None:
    h, src = _basis(_provenance=_STAMP)
    assert h and src == "universe registry EURUSD"


@pytest.mark.parametrize(
    "prov",
    [
        None,
        ["x"],
        "s",
        {"median_spread_pts": "fusion_zero_m1_tape"},
        {"median_spread_pts": {"source": "h1_spread_median", "zero_spread": True}},
        {"median_spread_pts": {"source": "fusion_zero_m1_tape"}},
    ],
)
def test_any_other_zero_is_still_no_basis_and_never_raises(prov) -> None:
    h, why = _basis(_provenance=prov) if prov is not None else _basis()
    assert h is None and "incomplete" in why


def test_a_positive_spread_hashes_exactly_as_before() -> None:
    a = _basis(median_spread_pts=3.0)
    b = _basis(median_spread_pts=3.0, _provenance=_STAMP)
    assert a == b and a[0]


def test_the_promoter_and_the_gate_name_the_same_source() -> None:
    eg = pytest.importorskip("scripts.external_gauntlet")
    if not hasattr(eg, "ZERO_SPREAD_SOURCES"):
        pytest.skip("the gate's zero-spread patch is not applied")
    assert promoter._ZERO_SPREAD_SOURCES == eg.ZERO_SPREAD_SOURCES
