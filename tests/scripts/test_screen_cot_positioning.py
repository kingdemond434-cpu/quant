"""The COT screen's refusals and its trial accounting (R0562).

A screen's value is entirely in what it REFUSES to claim. These pin the two ways this one could
publish a verdict it has not earned -- an empty lake read as an empty result, and a cell scored
without a measured breadth -- plus the trial count, which is the difference between a swept axis
and a p-hacked one.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

S = importlib.import_module("scripts.screen_cot_positioning")


@pytest.fixture(autouse=True)
def _no_law_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(S, "_law_guard", lambda *a, **k: None)


def _panel(n_days: int = 900, n_sym: int = 6, seed: int = 7) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2015-01-01", periods=n_days, freq="B", tz="UTC")
    cols = [f"SYM{i}" for i in range(n_sym)]
    closes = pd.DataFrame(100.0 * np.exp(np.cumsum(rng.normal(0, 0.01, (n_days, n_sym)), axis=0)),
                          index=idx, columns=cols)
    z = pd.DataFrame(rng.normal(0, 1, (n_days, n_sym)), index=idx, columns=cols)
    return z, closes


def test_an_ABSENT_LAKE_is_a_missing_input_and_REFUSES(monkeypatch: pytest.MonkeyPatch,
                                                       tmp_path: Path) -> None:
    """L1.28a, and the worktree-blind class specifically: data/ is gitignored, so this script run
    from a worktree sees no lake. An empty frame there is NOT a screen that found nothing -- it is
    a screen that could not look, and publishing it would be a fabricated verdict."""
    monkeypatch.setattr(sys, "argv", ["screen_cot_positioning.py", "--lake", str(tmp_path),
                                      "--out", str(tmp_path / "o.json")])
    assert S.main() == 2
    assert not (tmp_path / "o.json").exists(), "a refused run must leave no artifact behind"


def test_all_declared_cells_are_reported_including_the_losers() -> None:
    """The garden-of-forking-paths rule. Reporting the best cell without counting the others is
    p-hacking, so every construction x horizon is screened and returned, winners and losers."""
    z, closes = _panel()
    out = S.cells(z, closes)

    assert len(out) == len(S.HORIZONS_D) * 2
    names = {c["cell"] for c in out}
    assert names == {f"{c}_{h}d" for h in S.HORIZONS_D for c in ("absolute", "relative")}


def test_a_cell_carries_its_MEASURED_breadth() -> None:
    """L1.62. `powered` -- the bit separating 'tested and refuted' from 'could not tell' -- is
    computed from a cross-sectional divisor, and certifying a refutation on a divisor nobody
    measured is the false-null direction no other gate catches. Sized like the real run (4,420
    bars): at 900 days the 20d grid leaves 45 rows and breadth is legitimately unmeasurable, which
    is the NEXT test rather than a reason to soften this one."""
    z, closes = _panel(n_days=4000)
    out = S.cells(z, closes)

    for c in out:
        assert c["breadth"]["measured"] is True, f"{c['cell']}: breadth was never measured"
        assert c["breadth"]["xs_neff"] > 0
        assert c["breadth_basis"] == "MEASURED", f"{c['cell']}: screened on an ASSUMED divisor"


def test_an_UNMEASURABLE_breadth_forbids_powered_and_therefore_forbids_a_refutation() -> None:
    """The load-bearing half of L1.62. A thin panel may still be SCREENED, but it may never be
    certified 'tested and refuted' -- SCREEN-WEAK is graveyard-grade and a graveyard entry bought
    with an assumed sample size is negative discovery."""
    # 900 x 6: the 20d grid leaves 45 rows -- past the screen's 200-pair floor, so the cell IS
    # screened, and under panel_breadth's per-symbol floor, so its divisor is not measurable.
    z, closes = _panel(n_days=900, n_sym=6)
    thin = [c for c in S.cells(z, closes) if c.get("breadth", {}).get("measured") is False]

    assert thin, "fixture no longer produces an unmeasurable cell -- the property is untested"
    for c in thin:
        assert c["breadth_basis"] != "MEASURED"
        assert c.get("powered") is not True, f"{c['cell']}: powered on an unmeasured divisor"
        assert c.get("verdict") != "SCREEN-WEAK", f"{c['cell']}: graveyard-grade without power"


def test_a_cell_with_too_few_pairs_is_UNMEASURABLE_not_a_verdict() -> None:
    """A short panel must not produce a screen reading at all. 'Could not tell' and 'no edge' are
    different claims and only one of them is graveyard-grade."""
    z, closes = _panel(n_days=60, n_sym=3)
    out = S.cells(z, closes)

    assert out, "the cells must still be enumerated, not silently dropped"
    assert all(c["verdict"] == "SCREEN-UNMEASURABLE" for c in out), [c["verdict"] for c in out]


def test_the_horizons_are_MECHANISM_APPROPRIATE_and_exclude_next_day() -> None:
    """Weekly data on positions accumulated over months does not predict tomorrow. Screening 1d
    anyway would spend a DSR trial on a cell the mechanism never claimed."""
    assert 1 not in S.HORIZONS_D
    assert S.HORIZONS_D == (5, 20)


def test_the_axis_is_the_MT5_universe_and_carries_no_crypto() -> None:
    """The 2026-08-18 mandate: the desk's primary universe is MT5/Fusion, and no crypto-exchange
    universe may be hunted. This screen's universe comes from COT_MAP, so the assertion belongs
    here rather than in a comment."""
    assert set(S.CLASSES) == {"fx", "metal", "energy"}
    assert not any(s.endswith("USDT") or s.startswith(("BTC", "ETH")) for s in S.COT_MAP)
