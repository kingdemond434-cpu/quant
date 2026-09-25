"""EVERY CLASS NAME THE DESK CAN PRODUCE MUST REACH A LANE, or the lane door is a silent hole.

THE DEFECT, measured on the trading box 2026-09-23. `universe_policy._norm` maps `_` to a space,
so `asset_class_of` returned `'fx major'`, `'fx cross'`, `'fx exotic'` -- while the literals in
`HYPOTHESIS_CLASSES` were spelled `fx_major`, `fx_cross`, `fx_exotic` and could never match. Those
three were the ONLY underscore-bearing entries in either set, so the casualty was exactly and only
FX: 96 of MetaTrader's 251 registry symbols (68 exotics, 21 crosses, 7 majors) read UNCLASSIFIED
and `may_hypothesise` was False for all of them, from the day the module landed (2026-09-07).

WHAT IT COST. `shadow_forward` asks this question before it will replay a forward clock, so 24 of
the desk's 28 ten-gate certificates -- and 92 of its 148 enrolled clocks -- sat at
REFUSED_BY_UNIVERSE_POLICY, certified and accruing nothing. FX is the first thing the MT5 universe
mandate names.

WHY THE TEST IS SHAPED THIS WAY. Asserting `lane("EURJPY") == HYPOTHESIS` would have caught this
one and nothing like it. The general property is that the two vocabularies -- what the classifier
EMITS and what the policy DECLARES -- cannot drift apart silently, so the test drives the desk's
own classifier over the desk's own registry and fails on any class that reaches no lane. The
second half keeps the equity refusal intact: this must never become a way to widen the hypothesis
universe by accident.
"""

from __future__ import annotations

import json
import pathlib
import sys

import pytest

DESK = pathlib.Path(__file__).resolve().parents[1]
for _p in (str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

REGISTRY = DESK / "data" / "universe" / "universe.json"


@pytest.fixture(scope="module")
def policy():
    return pytest.importorskip("universe_policy")


def test_every_declared_class_name_survives_the_normaliser(policy) -> None:
    """The bug in one line: a declared name that `_norm` would rewrite can never match."""
    for name in policy.HYPOTHESIS_CLASSES | policy.EVENT_DRIVEN_CLASSES:
        assert policy._norm(name) == name, (
            f"declared class {name!r} is not in normalised form, so no value can ever equal it "
            f"-- `_norm` would turn it into {policy._norm(name)!r}. Declare it through "
            f"`_norm_set`.")


def test_the_fx_spellings_the_classifier_emits_all_reach_the_hypothesis_lane(policy) -> None:
    """The three that were dead letters, by name, so a future edit cannot quietly drop them."""
    for raw in ("fx_major", "fx_cross", "fx_exotic", "FX Major", "fx  exotic"):
        assert policy._norm(raw) in policy.HYPOTHESIS_CLASSES, (
            f"{raw!r} is what `mt5desk.universe.asset_class` returns for an FX pair; if it does "
            f"not reach the hypothesis lane, every FX certificate's forward clock is refused")


def test_no_class_the_desk_classifier_emits_is_orphaned(policy) -> None:
    """Drive the desk's OWN classifier over the desk's OWN registry: nothing may fall through.

    This is the property, and the one that would have caught the defect the day it landed. It is
    deliberately not a symbol list -- a new instrument arriving tomorrow is covered by it.
    """
    if not REGISTRY.exists():
        pytest.skip("no universe registry on this host")
    pattern = pytest.importorskip("mt5desk.universe")
    registry = json.loads(REGISTRY.read_text("utf-8"))
    orphans: dict[str, str] = {}
    for symbol, row in registry.items():
        if not isinstance(row, dict):
            continue
        klass = policy._norm(row.get("asset_class") or pattern.asset_class(symbol))
        if klass and klass not in policy.HYPOTHESIS_CLASSES | policy.EVENT_DRIVEN_CLASSES:
            orphans.setdefault(klass, symbol)
    assert not orphans, (
        "these asset classes reach NEITHER lane, so every symbol carrying one is hunted by "
        f"nothing and its certificates can never accrue: {orphans}")


def test_fx_is_hunted_and_equities_are_still_not(policy) -> None:
    """Both directions, in one test, because fixing one by breaking the other is the failure mode.

    Single-name equities stay OUT of statistical discovery (principal 2026-09-06) -- this fix
    restores FX, and must not restore them.
    """
    if not REGISTRY.exists():
        pytest.skip("no universe registry on this host")
    registry = json.loads(REGISTRY.read_text("utf-8"))
    leaked = [s for s, row in registry.items()
              if isinstance(row, dict)
              and str(row.get("asset_class", "")).strip().lower().startswith("equit")
              and policy.lane(s) != policy.EVENT]
    assert not leaked, f"equities admitted to hypothesis discovery: {leaked[:10]}"
    unknown = [s for s in ("NOTREAL", "ZZZQQQ9") if policy.lane(s) != policy.UNCLASSIFIED]
    assert not unknown, "a string that is not a broker instrument must reach NEITHER lane"
