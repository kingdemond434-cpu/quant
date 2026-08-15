"""Live mechanism sleeves running under a DECLARED SUSPENSION of the two-stage law.

These sleeves take capital on backtest evidence alone, which L1.6 forbids. The principal suspended
that requirement explicitly and the suspension is on record in docs/research/LIVE_EXCEPTION_LEDGER
.json. Everything here pins the two properties that keep a lawful exception from decaying into a
silent default: it FAILS CLOSED without its ledger row, and its kill terms were fixed before the
first fill rather than after the first month's returns.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import scripts.run_mechanism_sleeves as M

_LEDGER = Path(__file__).resolve().parents[2] / "docs/research/LIVE_EXCEPTION_LEDGER.json"


def _row() -> dict[str, Any]:
    doc = json.loads(_LEDGER.read_text("utf-8"))
    return next(r for r in doc["exceptions"] if r["id"] == "live-mechanism-sleeves")


def test_THE_SUSPENSION_IS_ON_RECORD_WITH_ITS_ATTRIBUTION() -> None:
    """A boolean in a config says a rule is off. It does not say who turned it off, when, for what,
    or on what terms -- and six weeks later it is indistinguishable from a default."""
    r = _row()
    assert r["active"] is True
    assert r["law_suspended"].startswith("L1.6")
    assert r["granted"] and "principal" in r["granted_by"]
    assert r["principals_words"], "the instruction is quoted, not paraphrased into agreement"
    assert "weak evidence" in r["concern_stated_before_granting"], \
        "the cost must be on record as having been stated BEFORE the grant, not discovered after"


def test_IT_FAILS_CLOSED_WITHOUT_THE_LEDGER(monkeypatch: pytest.MonkeyPatch,
                                            tmp_path: Path) -> None:
    """THE PROPERTY THAT MAKES THIS AN EXCEPTION RATHER THAN A REPEAL. This module exists only
    because a standing law was suspended; an unrecorded suspension is indistinguishable from the
    law never having applied, which is how an exception becomes the default with nobody deciding."""
    monkeypatch.setattr(M, "_LEDGER", tmp_path / "absent.json")
    ok, why = M._exception_recorded()
    assert not ok and "SUSPENSION" in why
    rep = M.build()
    assert rep["exception_active"] is False
    assert rep["target_weights"] == {}, "no ledger, no capital"


def test_AN_INACTIVE_ROW_REVOKES_IT(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Revocation must be one field, and must bind on the next cycle without a code change."""
    doc = {"exceptions": [{"id": "live-mechanism-sleeves", "active": False,
                           "granted": "2026-08-15", "granted_by": "principal"}]}
    p = tmp_path / "ledger.json"
    p.write_text(json.dumps(doc), "utf-8")
    monkeypatch.setattr(M, "_LEDGER", p)
    assert not M._exception_recorded()[0]


def test_THE_KILL_RULE_PREDATES_THE_RETURNS_IT_JUDGES() -> None:
    """'If they earn they stay', decided AFTER seeing the returns, is not a rule -- it is a garden
    of forking paths with money in it: whichever sleeve looks best gets kept for a reason invented
    afterwards. A threshold is only a threshold if it predates the number it judges."""
    r = _row()["terms_fixed_before_the_first_fill"]
    assert r["kill_drawdown"] == M.KILL_DRAWDOWN < 0
    assert r["review_days"] == M.REVIEW_DAYS > 0
    assert r["clip_frac"] == M.EQUAL_CLIP_FRAC
    assert "predates" in r["why_fixed_now"]
    assert "not finish it" in r["survival_is_not_validation"], \
        "surviving a month must not be recorded as validation"


def test_THE_BACKTEST_DOES_NOT_GET_TO_ALLOCATE() -> None:
    """The principal suspended the requirement for forward evidence before going live. They did
    NOT suspend the rule against letting a gauntlet decide position SIZE -- so clips are equal and
    fixed, and no sleeve is ever sized up for performing well (III.15)."""
    assert "no sleeve is sized up" in _row()["terms_fixed_before_the_first_fill"]["equal_and_fixed"]
    assert all(s[3] for s in M.SLEEVES), "each sleeve carries declared params"
    # every sleeve gets the SAME clip; nothing in the module varies it
    src = Path(M.__file__).read_text("utf-8")
    assert "EQUAL_CLIP_FRAC" in src and "sharpe" not in src.lower().split("kill_rule")[0][-400:]


def test_THE_RAILS_WERE_NOT_SUSPENDED() -> None:
    """A suspension is scoped or it is a repeal. These are named as still binding, in the record,
    so the scope cannot quietly widen later."""
    kept = " ".join(_row()["what_was_NOT_suspended"]).lower()
    for must in ("ruin rail", "gross cap", "daily loss cap", "deadman", "auto_promotion"):
        assert must in kept, f"{must} must be named as still binding"


def test_A_GENERATOR_WITHOUT_ITS_INPUT_IS_FLAT_AND_SAYS_SO() -> None:
    """funding_stress_reversal returns zeros without funding data; intermarket_difference returns
    zeros without the reference's RANGE. 'No data' and 'no signal' are the same number and must
    never be the same report -- publishing the first as the second is WS-005 with capital behind
    it."""
    from libs.autodiscovery.generators import MarketSeries

    n = 400
    c = 100 + np.cumsum(np.random.default_rng(7).normal(0, 1, n))
    bare = MarketSeries(close=c, high=c * 1.01, low=c * 0.99, volume=np.full(n, 1e6),
                        hour=np.arange(n) % 24, ref_close=None, ref_high=None, ref_low=None,
                        funding=None)
    for _cls, subtype, _why, params in M.SLEEVES:
        pos = M._positions(subtype, bare, params)
        assert pos is not None, f"{subtype} must exist in this repo"
        assert not np.any(pos), f"{subtype} must degrade to FLAT without its input"


def test_EVERY_DECLARED_SLEEVE_HAS_A_GENERATOR_IN_THIS_REPO() -> None:
    """The four-strategy plan named `taker_flow`, which does not exist here. Shipping a sleeve
    whose generator is absent would publish an empty weight set as a market view."""
    from libs.autodiscovery.generators import GENERATORS

    have = {g.subtype for g in GENERATORS}
    for _cls, subtype, _why, _p in M.SLEEVES:
        assert subtype in have, f"{subtype} is declared live and has no generator"


def test_THE_CENSUS_CLASS_IS_THE_ONE_THE_CENSUS_ASSIGNS() -> None:
    """`funding_stress_reversal` is filed under the LIQUIDITY search family while testing
    positioning/crowding. Naming sleeves by the search family would report two mechanisms the desk
    is not running and miss the one it is."""
    from libs.research.mechanism_census import CONSTRUCTION_CLASS

    for census_class, subtype, _why, _p in M.SLEEVES:
        declared = CONSTRUCTION_CLASS.get(subtype)
        if declared is not None:
            assert declared == census_class, f"{subtype}: census says {declared}"
