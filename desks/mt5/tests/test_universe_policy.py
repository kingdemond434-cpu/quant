"""Single-name equities never enter statistical hypothesis discovery, and nothing else is lost.

PRINCIPAL'S ORDER, 2026-09-06: US shares are traded on news, financial reports and earnings
reaction; forex, metals, energy, softs, indices, bonds and Fusion's crypto CFDs are the
hypothesis-discovery universe.

The two halves of this file pull against each other on purpose. One asserts that equities are
routed OUT; the other asserts that everything else is routed IN and that unknown strings are
routed NOWHERE. A change that satisfies only the first would look like compliance while quietly
starving the desk -- which is the shape of every over-eager filter this repo has had to undo.
"""
from __future__ import annotations

import json
import pathlib
import sys

import pytest

DESK = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DESK))
sys.path.insert(0, str(DESK / "research"))
sys.path.insert(0, str(DESK / "side_channels"))

REGISTRY = DESK / "data" / "universe" / "universe.json"


@pytest.fixture(scope="module")
def policy():
    return pytest.importorskip("universe_policy")


@pytest.fixture(scope="module")
def registry() -> dict:
    if not REGISTRY.exists():
        pytest.skip("no universe registry on this host")
    return json.loads(REGISTRY.read_text("utf-8"))


def test_every_registry_equity_is_routed_to_the_event_lane(policy, registry) -> None:
    leaked = [s for s, row in registry.items()
              if isinstance(row, dict)
              and str(row.get("asset_class", "")).strip().lower().startswith("equit")
              and policy.lane(s) != policy.EVENT]
    assert not leaked, f"equities still admitted to hypothesis discovery: {leaked[:10]}"


@pytest.mark.parametrize("klass_prefix", ["forex", "commodit", "soft", "indices", "crypto",
                                          "bond", "energy", "metal"])
def test_every_other_class_stays_in_hypothesis_discovery(policy, registry, klass_prefix) -> None:
    """THE HALF THAT PREVENTS OVER-FILTERING. Routing equities out must not cost the desk the
    classes the method actually suits -- an exclusion that quietly widens is worse than none."""
    members = [s for s, row in registry.items()
               if isinstance(row, dict)
               and str(row.get("asset_class", "")).strip().lower().startswith(klass_prefix)]
    if not members:
        pytest.skip(f"this registry carries no {klass_prefix}* symbols")
    dropped = [s for s in members if policy.lane(s) != policy.HYPOTHESIS]
    assert not dropped, f"{klass_prefix}* symbols wrongly withheld from discovery: {dropped[:10]}"


def test_an_unregistered_string_is_routed_nowhere(policy) -> None:
    """Absence is not a permission, in either direction.

    The desk's pattern classifier ends with `\\d?[A-Z]{1,12} -> equity`, a deliberate catch-all
    for its own purpose. Trusting it here made `NOTREAL` an equity and sent it to the news desk.
    Routing is a decision about a REAL instrument; anything else must reach UNCLASSIFIED, where
    it is reported rather than silently assigned.
    """
    for junk in ("NOTREAL", "ZZZZZZ", "", "AAPL.24H"):
        assert policy.lane(junk) == policy.UNCLASSIFIED, f"{junk!r} was routed somewhere"


def test_unclassified_is_not_hypothesis(policy) -> None:
    assert not policy.may_hypothesise("NOT_A_REAL_SYMBOL_XYZ")


def test_the_gauntlet_actually_applies_the_policy(policy) -> None:
    """The policy is only worth having where it is enforced."""
    runner = pytest.importorskip("run_external_backtest")
    assert hasattr(runner, "route_by_lane"), "the gauntlet has no lane routing"
    grid = [
        {"symbol": "EURUSD", "family": "f", "params": {}},
        {"symbol": "APPLE", "family": "f", "params": {}},
        {"symbol": "Apple", "family": "f", "params": {}},
        {"symbol": "NOTREAL", "family": "f", "params": {}},
    ]
    kept, info = runner.route_by_lane(grid)
    if info.get("status") != "MEASURED":
        pytest.skip(f"routing unavailable here: {info.get('status')}")
    kept_syms = {str(c["symbol"]) for c in kept}
    assert "EURUSD" in kept_syms
    assert not {"APPLE", "Apple"} & kept_syms, "an equity reached hypothesis discovery"
    assert "NOTREAL" not in kept_syms


def test_routing_is_reported_not_silent(policy) -> None:
    """A cell that vanishes between the docket and the runner is indistinguishable from one that
    was tested and failed -- the confusion this stage has already paid for twice."""
    runner = pytest.importorskip("run_external_backtest")
    _, info = runner.route_by_lane([{"symbol": "Apple", "family": "f", "params": {}}])
    if info.get("status") != "MEASURED":
        pytest.skip("routing unavailable here")
    assert info["routed_event"] >= 1
    assert info.get("symbols_event"), "the report does not name what it set aside"
    assert info.get("policy", "").endswith("universe_policy.py")
