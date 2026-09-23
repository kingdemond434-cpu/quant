from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

DESK = Path(__file__).resolve().parents[1]
for path in (DESK, DESK / "research", DESK.parent.parent):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from research.full_hunt import candidate_key  # noqa: E402
from research.hunt_deflate import (  # noqa: E402
    FORWARD_POLICY,
    SCREEN_VERSION,
    build_candidates,
    normalize_existing,
)
# Canon's sequential-sufficiency rework (RESEARCH 6d) renamed MIN_VERDICT_TRADES to
# SEQ_MIN_TRADES -- same constant, same meaning: never a verdict below this many trades.
from research.shadow_forward import (  # noqa: E402
    SEQ_MIN_TRADES,
    VERDICT_MIN_DAYS,
    VERDICT_MIN_TRADES,
)

FORBIDDEN = ("effective", "deflated", "harsher", "clears_effective_bar")


def test_discovery_screen_cannot_admit_shadow() -> None:
    rng = np.random.default_rng(11)
    frame = pd.DataFrame({
        "strong": rng.normal(0.01, 0.02, 300),
        "weak": rng.normal(-0.01, 0.02, 300),
    })
    rows = build_candidates(frame, 3_168)
    assert [row["cell"] for row in rows] == ["strong"]
    row = rows[0]
    assert row["original_screen"]["version"] == SCREEN_VERSION
    assert row["original_screen"]["psr_threshold"] == 0.95
    assert row["original_screen"]["sr_benchmark"] == 0.0
    assert row["shadow_status"] == "PENDING_UNIVERSAL_10_GATE"
    assert row["promotion_authority"] is False
    assert row["forward_policy"] == FORWARD_POLICY
    assert not any(token in key.lower() for key in row for token in FORBIDDEN)


def test_existing_candidates_are_migrated_without_harsh_bar_exclusion() -> None:
    old = [{
        "cell": "XAUUSD|family|rr=2",
        "in_sample_sharpe": 1.2,
        "psr_raw": 0.97,
        "n_trials_searched": 3_168,
        "clears_effective_bar": False,
        "effective_bar_sr0": 1.5,
        "dsr_deflated": None,
    }]
    rows = normalize_existing(old)
    assert len(rows) == 1
    assert rows[0]["cell"] == old[0]["cell"]
    assert rows[0]["original_psr"] == 0.97
    assert not any(token in key.lower() for key in rows[0] for token in FORBIDDEN)


def test_candidate_identity_contains_every_parameter() -> None:
    base = candidate_key("XAUUSD", "failed_breakout", {
        "rr": 2.0, "level": "pdh", "min_pierce_atr": 0.1,
    })
    changed = candidate_key("XAUUSD", "failed_breakout", {
        "rr": 2.0, "level": "pdh", "min_pierce_atr": 0.25,
    })
    assert base != changed
    assert "min_pierce_atr=0.1" in base
    assert candidate_key("X", "f", {"b": 2, "a": 1}) == candidate_key(
        "X", "f", {"a": 1, "b": 2}
    )


def test_canonical_candidate_policy_matches_the_live_shadow_clock() -> None:
    assert FORWARD_POLICY == {
        "evaluate_after_trades": VERDICT_MIN_TRADES,
        "evaluate_after_days": VERDICT_MIN_DAYS,
        "minimum_trades_for_verdict": SEQ_MIN_TRADES,
    }
