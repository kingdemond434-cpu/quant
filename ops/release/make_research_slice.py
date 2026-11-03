#!/usr/bin/env python3
"""Writes ops/release/research_slice/: the pinned tape replay-shadow's research reach runs on.

The slice is a fixed daily-R matrix (one column per sleeve, one row per trading day) in the
allocator's own cache file, so `pf_allocator.run("fast")` solves a book from it without the box's
hunt reports. It is deterministic in SEED. It is not a forecast and nothing trades on it: both trees
see the same bytes, so any difference in the book they solve comes from the code.

Regenerating it changes SLICE.sha256, which research_reach.SLICE_SHA256 pins. Both live under
ops/release/ and are PROTECTED: a new slice is a reviewed change, and a PR's run always uses the
base's slice and the base's pin.

    python ops/release/make_research_slice.py && sha256sum ops/release/research_slice/SLICE.sha256
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
SLICE = HERE / "research_slice"
CACHE = "desks/mt5/data/pf_allocator_cache/daily_r.parquet"
SEED = 20261103
#: Live-shaped sleeve names, so name-keyed research code (families, mechanisms, clusters) engages.
SLEEVES = {
    "gold_asia": (0.05, 0.9),
    "gold_london": (0.03, 1.0),
    "AUDCHF_overnight_gap_decay_asia": (0.04, 0.7),
    "xauusd_session_range_breakout_asia_0_wb_12": (0.02, 0.8),
    "EURJPY_session_range_breakout_asia": (0.015, 0.6),
    "USDJPY_carry_asia": (0.01, 0.5),
    "EURUSD_cross_sectional_class_momentum": (0.012, 0.6),
    "GBPUSD_turn_of_month": (0.008, 0.5),
}
DAYS = pd.bdate_range("2025-01-02", "2026-10-30")


def build() -> pd.DataFrame:
    rng = np.random.default_rng(SEED)
    common = rng.standard_normal(len(DAYS)) * 0.3
    cols = {}
    for name, (mu, sd) in SLEEVES.items():
        cols[name] = np.round(mu + sd * (0.8 * rng.standard_normal(len(DAYS)) + common), 6)
    return pd.DataFrame(cols, index=[str(d.date()) for d in DAYS])


def main() -> int:
    out = SLICE / CACHE
    out.parent.mkdir(parents=True, exist_ok=True)
    build().to_parquet(out)
    rows = [f"{hashlib.sha256(out.read_bytes()).hexdigest()}  {CACHE}"]
    (SLICE / "SLICE.sha256").write_text("\n".join(rows) + "\n", "utf-8")
    print(hashlib.sha256((SLICE / "SLICE.sha256").read_bytes()).hexdigest())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
