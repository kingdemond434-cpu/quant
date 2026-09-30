"""The shared metric fence: an impossible number is refused with a counted reason before it
becomes a cell or a claim (committee dry run on PR #160: an MQL5 record with a 2,296% win rate)."""
from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.research import mechanism_claims as mc  # noqa: E402
from libs.research.metric_fence import FenceTally, fence_row, reason_class  # noqa: E402

GOOD = {"growth_pct": 180.0, "weeks": 150.0, "pf": 1.6, "max_dd_pct": 18.0, "trades": 900.0,
        "win_pct": 58.0, "sharpe": 1.4}


@pytest.mark.parametrize(("patch", "reason"), [
    ({"win_pct": 2296.0}, "win_rate_out_of_bounds"),
    ({"win_pct": "2,296%"}, "win_rate_out_of_bounds"),
    ({"win_pct": -1.0}, "win_rate_out_of_bounds"),
    ({"pf": -0.4}, "profit_factor_negative"),
    ({"max_dd_pct": 140.0}, "drawdown_out_of_bounds"),
    ({"max_dd_pct": -101.0}, "drawdown_out_of_bounds"),
    ({"trades": -3}, "trades_negative"),
    ({"sharpe": 25.0}, "sharpe_out_of_band"),
    ({"sharpe": -12.0}, "sharpe_out_of_band"),
    ({"win_pct": math.nan}, "win_rate_non_finite"),
    ({"pf": math.inf}, "profit_factor_non_finite"),
])
def test_an_impossible_metric_is_refused_with_its_reason(patch: dict, reason: str) -> None:
    bad = fence_row(GOOD | patch)
    assert [reason_class(b) for b in bad] == [reason]


@pytest.mark.parametrize("patch", [
    {}, {"win_pct": 100.0}, {"win_pct": 0.0}, {"win_rate": 0.62}, {"pf": 0.0},
    {"max_dd_pct": -35.0}, {"max_dd_pct": 99.0}, {"trades": 0}, {"sharpe": -9.9},
    {"growth_pct": 22000.0},                               # possible, if implausible: passes
])
def test_a_possible_metric_passes(patch: dict) -> None:
    assert fence_row(GOOD | patch) == []


def test_absent_metrics_are_unmeasured_never_a_defect() -> None:
    assert fence_row({"title": "EURUSD idea", "text": "no numbers here"}) == []
    assert fence_row({"win_pct": None, "pf": "n/a", "trades": ""}) == []


def test_nested_metric_blocks_are_fenced_too() -> None:
    bad = fence_row({"title": "x", "claimed_performance": {"win_rate_pct": 2296.0}})
    assert bad and bad[0].startswith("claimed_performance.win_rate_out_of_bounds")


def test_the_tally_counts_every_refusal_by_reason_and_source() -> None:
    t = FenceTally()
    t.add("mql5_survivors", fence_row(GOOD | {"win_pct": 2296.0}), "u1")
    t.add("mql5_survivors", fence_row(GOOD), "u2")
    t.add("regional", fence_row(GOOD | {"pf": -1, "sharpe": 40}), "u3")
    d = t.to_dict()
    assert (d["checked"], d["refused"]) == (3, 2)
    assert d["by_reason"] == {"win_rate_out_of_bounds": 1, "profit_factor_negative": 1,
                              "sharpe_out_of_band": 1}
    assert d["by_source"] == {"mql5_survivors": 1, "regional": 1}


def test_the_claim_extractor_refuses_an_impossible_stated_number_and_counts_it() -> None:
    text = ("Buying EURUSD at the London open after the Asia range breaks gives a win rate of "
            "2296% over the next 4 hours. "
            "Selling XAUUSD at the New York close when the day ran up gives a win rate of 62% "
            "over the next day.")
    out = mc.extract(text)
    assert out["dropped_impossible_metric"] == 1
    assert out["impossible_metric_reasons"] == {"win_rate_out_of_bounds": 1}
    assert all(c["claimed_performance"].get("win_rate_pct", 0) <= 100 for c in out["claims"])
