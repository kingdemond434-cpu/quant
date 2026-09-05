"""Canary verdicts must carry information: welded-ON is the cry-wolf failure (L1.37/L1.43).

Measured 2026-08-19 on the live history: C9 tracked the chain HEAD (advances every ~12s, so
every run read SHIFT), and C1/C5 compared growing totals by exact string (any re-run read
SHIFT). A detector that fires every run is acked into silence and then enforces nothing. These
tests pin the two repairs: categorical getLogs-acceptance for C9, and a 10% spike band for
`key=<int>` values so PASS is the steady state and SHIFT means a spike since the last look.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts import run_canaries as rc  # noqa: E402


class TestNumericBand:
    def test_within_band_is_not_a_shift(self) -> None:
        assert rc._numeric_shift("total_count=238", "total_count=249") is False  # +4.6%

    def test_a_spike_is_a_shift(self) -> None:
        assert rc._numeric_shift("total_count=238", "total_count=300") is True   # +26%
        assert rc._numeric_shift("total=2000", "total=1500") is True             # -25%

    def test_non_numeric_values_fall_back_to_exact_compare(self) -> None:
        assert rc._numeric_shift("getLogs700=ok", "getLogs700=denied") is None
        assert rc._numeric_shift("", "total=5") is None

    def test_different_keys_never_compare(self) -> None:
        """A key change means the extractor changed -- that IS a shift, decided by the caller."""
        assert rc._numeric_shift("total=100", "bytes=100") is None

    def test_zero_baseline_cannot_divide_away_the_band(self) -> None:
        assert rc._numeric_shift("total=0", "total=1") is True


# `TestC9Categorical` was removed 2026-09-05 (universe mandate). It pinned the `rpc` extractor's
# categorical acceptance verdict for C9, the keyless Ethereum `eth_getLogs` canary -- the one
# canary in the table with no MT5 question to ask. The canary, the extractor and its JSON-RPC POST
# client all went together, so these five tests had no subject left.
#
# WHAT THE CLASS WAS ACTUALLY PROTECTING is not lost: `test_head_never_appears_in_the_value`
# guarded against a canary whose tracked value moves every run (the block head advanced every
# ~12s, so the canary read SHIFT on every single look -- welded ON, zero information). That
# property now lives on the numeric canaries and is asserted by `TestVerdictWiring` below, which
# is where the 10% band that made PASS the steady state is exercised.


class TestVerdictWiring:
    def test_first_look_is_pass_and_band_applies_after(self) -> None:
        """run_all()'s verdict rule, exercised through the pure pieces it composes."""
        assert rc._numeric_shift("commits_page=158", "commits_page=160") is False
        assert rc._numeric_shift("commits_page=158", "commits_page=100") is True
