"""L0009, graduated: campaign WIDTH buys nothing, LENGTH buys everything.

MEASURED (docs/research/gate_power_audit.md): power was identical at N=420/100/30/5 — sample
LENGTH T was the only lever that moved it. The lesson recurred on 2026-08-04 as a live
regression: an expanded-universe run silently used the fetcher's 2023-08 default start, trading
√-time for symbol count at a net loss (1.5x elapsed-time evidence lost vs 1.13x pooling gained).
It was caught, declared, and corrected to a 2020-12 start (T≈5.6y) with 21 symbols — which
strictly dominates both prior configurations.

This pins the DEPTH so the trade cannot be made again by accident. It does not fix the symbol
list: adding symbols is free and welcome, as long as nobody pays for them in years.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

_CAMPAIGN = Path(__file__).resolve().parents[2] / "scripts" / "run_real_campaign.py"


def test_the_binance_panel_keeps_its_elapsed_time() -> None:
    """t = SR·√years, so a shorter panel costs evidence no number of extra symbols repays."""
    src = _CAMPAIGN.read_text("utf-8")
    starts = re.findall(r'load_or_fetch\([^)]*?"(\d{4})-\d{2}"', src, re.S)
    assert starts, "campaign no longer calls load_or_fetch with an explicit start"
    for year in starts:
        assert int(year) <= 2021, (
            f"campaign panel starts at {year} — elapsed time is the only lever measured to move "
            "power (L0009). Widening the universe must never be paid for in years.")


def test_the_pooled_path_still_exists_to_spend_that_length_on() -> None:
    """Depth only pays through the pooled-by-mechanism view; if that path is deleted the
    lesson's premise goes with it."""
    src = _CAMPAIGN.read_text("utf-8")
    assert "pooled_by_mechanism" in src and "campaign_gate_stats" in src
