"""Regime sizing FULL on the prop accounts: newcomers drawn from the forward regime mix, and the
regime every solve sized on reported in FTMO_ALLOCATOR.json."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

DESK = Path(__file__).resolve().parents[1]
for p in (str(DESK.parent.parent), str(DESK / "research"), str(DESK)):
    if p not in sys.path:
        sys.path.insert(0, p)

import kelly_survival as ks  # noqa: E402
import prop_challenge_allocator as pca  # noqa: E402


def test_regime_block_reports_the_worlds_mix(tmp_path):
    p = tmp_path / "pf_allocation.json"
    p.write_text(json.dumps({"at": "2026-11-24T18:00:00+00:00", "regime": {
        "probabilities": {"trend": 0.7, "range": 0.3}, "conditioned": True}}), encoding="utf-8")
    b = pca.regime_block("2 joined; newcomers regime-conditioned", p)
    assert b["status"] == "CONDITIONED" and b["forward_mix"] == {"trend": 0.7, "range": 0.3}
    assert "regime-conditioned" in b["newcomers"]


def test_regime_block_is_unmeasured_without_the_allocator(tmp_path):
    assert pca.regime_block(None, tmp_path / "absent.json")["status"] == "UNMEASURED"


def test_newcomers_fall_back_to_unconditional_and_say_so(monkeypatch: Any):
    import pf_allocator

    def boom(df: Any) -> Any:
        raise ValueError("no closes")
    monkeypatch.setattr(pf_allocator, "regime_state", boom)
    labels, probs, why = ks._regime_for(pd.DataFrame({"a": [0.1, 0.2]}))
    assert labels == () and probs == () and "unconditional" in why


def test_newcomers_are_drawn_from_the_forward_mix(monkeypatch: Any):
    import pf_allocator
    idx = [f"2026-01-{d:02d}" for d in range(1, 29)] * 5
    df = pd.DataFrame({"X": np.r_[np.full(70, 1.0), np.full(70, -1.0)]}, index=idx[:140])
    labels = tuple(["bull"] * 70 + ["bear"] * 70)
    monkeypatch.setattr(pf_allocator, "regime_state",
                        lambda d: (labels, (("bull", 1.0), ("bear", 0.0)), {}))
    lab, probs, why = ks._regime_for(df)
    assert lab == labels and dict(probs) == {"bull": 1.0, "bear": 0.0}
    assert "regime-conditioned" in why and "bull 1.00" in why
