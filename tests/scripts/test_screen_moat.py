"""THE MOAT SURVIVOR HUNT, AND THE FOUR ALIGNMENT BUGS IT TOOK TO GET RIGHT.

`moat_mine` reconstructs seven proprietary features from the desk's self-recorded L2 tape and
`mine_moat` records which cells have been measured. Nothing ever asked whether any of them
PREDICTS anything -- the one asset a competitor cannot buy produced descriptive statistics and no
verdict, at asymmetry depth 2 of 5.

Getting the harness honest took four corrections, every one of which would have manufactured edge:

  1. ENTRY PRICE WAS A TIME MACHINE. The last print at or before the signal landed 14 SECONDS
     BEFORE it, so the return window spanned the very move the feature was measured during.
  2. THE TARGET WAS DOUBLE-SHIFTED. `stage_a_screen` takes CONTEMPORANEOUS returns and predicts
     t+1 itself; being handed pre-forwarded returns made its own misalignment rail fire on 14 of
     19 hypotheses.
  3. THE SHARPE RAIL IS DAILY-CALIBRATED. The screen annualises, so at 60s the factor is ~725 and
     noise reported sharpe_reversal=53.4 against a ceiling of 6.
  4. HORIZONS HAD TO BECOME STRIDES over the snapshot grid, so one screen period equals one
     horizon rather than one 15-second snapshot.

The controls matter more than any of it: a contemporaneous-only planted structure must yield NO
survivors, and a genuinely predictive one MUST yield some. A harness that never finds anything is
indistinguishable from a broken one.
"""

from __future__ import annotations

import gzip
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import scripts.screen_moat as S  # noqa: E402


def _tape(root: Path, *, predictive: bool, n: int = 4000, seed: int = 11,
          strength: float = 0.0010, noise: float = 0.0004) -> None:
    """Book imbalance drives the NEXT period (predictive) or the CURRENT one (contemporaneous)."""
    d = root / "binance" / "BTCUSDT"
    d.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)
    mid, t0 = 30000.0, 1767225600000
    imb = rng.normal(0, 1, n)
    rows = []
    for i in range(n):
        if not predictive:
            mid *= np.exp(strength * imb[i] + rng.normal(0, noise))   # move happens FIRST
        ts = t0 + i * 15000
        b = [max(0.01, 1.0 + 0.5 * imb[i] + rng.normal(0, 0.15)) for _ in range(20)]
        a = [max(0.01, 1.0 - 0.5 * imb[i] + rng.normal(0, 0.15)) for _ in range(20)]
        rows.append({"t": ts, "k": "d", "u": i,
                     "b": [[f"{mid - 0.5 - j * 0.5:.2f}", f"{b[j]:.4f}"] for j in range(20)],
                     "a": [[f"{mid + 0.5 + j * 0.5:.2f}", f"{a[j]:.4f}"] for j in range(20)]})
        rows.append({"t": ts + 1000, "k": "t", "a": i, "p": f"{mid:.2f}", "q": "0.5"})
        if predictive:
            mid *= np.exp(strength * imb[i] + rng.normal(0, noise))   # move happens AFTER
    with gzip.open(d / "20260101_00.jsonl.gz", "wt") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


def _run(tmp: Path, root: Path) -> dict:
    S.MOAT, S.REPORT, S.HISTORY = root, tmp / "r.json", tmp / "h.jsonl"
    sys.argv = ["screen_moat.py"]
    assert S.main() == 0
    return json.loads((tmp / "r.json").read_text("utf-8"))


# --------------------------------------------------------------------- alignment

def test_entry_is_the_first_print_after_the_signal_not_before_it(tmp_path) -> None:
    """BUG 1, AND IT IS A TIME MACHINE. Pricing entry at the last print BEFORE the signal put the
    fill 14 seconds in the past, so the return window contained the move the feature described."""
    rows = [{"t": 1000, "k": "t", "a": 0, "p": "100", "q": "1"},
            {"t": 3000, "k": "t", "a": 1, "p": "110", "q": "1"},
            {"t": 5000, "k": "t", "a": 2, "p": "121", "q": "1"}]
    snaps = np.array([2000, 4000], dtype="int64")
    r = S.period_returns(rows, snaps)
    # snapshot @2000 -> first print after = 110 ; snapshot @4000 -> 121. Return = 121/110 - 1.
    assert np.isnan(r[0]), "the first period has no prior entry and must be unmeasured"
    assert r[1] == np.float64(121) / 110 - 1


def test_a_period_with_no_print_is_nan_not_zero(tmp_path) -> None:
    """No trade means no return. A zero tells the screen nothing happened when nothing was seen."""
    rows = [{"t": 1000, "k": "t", "a": 0, "p": "100", "q": "1"}]
    assert np.isnan(S.period_returns(rows, np.array([5000, 9000], dtype="int64"))).all()


def test_horizons_are_strides_so_one_period_equals_one_horizon() -> None:
    """BUG 4. The screen predicts ONE PERIOD ahead; if a period is a 15s snapshot then a '900s
    horizon' was never actually tested."""
    assert S.SNAPSHOT_S == 15
    assert all(h % S.SNAPSHOT_S == 0 for h in S.HORIZONS_S)


def test_the_sharpe_ceiling_is_rescaled_for_the_horizon() -> None:
    """BUG 3. The screen annualises, so a ceiling of 6.0 calibrated at horizon_days=1 becomes a
    725-fold tighter bar at 60s -- and pure noise reported sharpe_reversal=53.4 against it."""
    import inspect
    src = inspect.getsource(S.screen_symbol)
    assert "sharpe_ceiling" in src
    assert "np.sqrt(1.0 / hd)" in src


def test_the_target_is_contemporaneous_because_the_screen_shifts_it_itself() -> None:
    """BUG 2. stage_a_screen's contract: target_ret[t] is the return over period t, and it
    predicts t+1 from signal[t]. Handing it pre-forwarded returns shifts twice."""
    assert "CONTEMPORANEOUS" in S.period_returns.__doc__
    assert not hasattr(S, "forward_returns"), "the double-shifting version must be gone"


# ---------------------------------------------------------------------- controls

def test_a_contemporaneous_only_edge_yields_no_survivors(tmp_path) -> None:
    """THE NEGATIVE CONTROL. Imbalance that reflects the move which just happened is not a
    prediction, however strong the relationship looks."""
    root = tmp_path / "moat_c"
    _tape(root, predictive=False)
    rep = _run(tmp_path, root)
    assert rep["survivors"] == [], f"survivors on a non-predictive tape: {rep['survivors']}"


def test_a_genuinely_predictive_edge_IS_found(tmp_path) -> None:
    """THE POSITIVE CONTROL, AND THE MORE IMPORTANT ONE. A harness that never finds anything is
    indistinguishable from a broken harness, and 'no survivors' from it means nothing."""
    root = tmp_path / "moat_p"
    # STRONG enough to be detectable across a family of 19 after Romano-Wolf. A weak planted edge
    # (t ~ 1.4) correctly fails the stepdown, so testing detection with one proves nothing about
    # the harness -- only that the edge was small.
    _tape(root, predictive=True, strength=0.0035, noise=0.0004)
    rep = _run(tmp_path, root)
    assert rep["survivors"], "a planted forward edge must be found"
    assert all(s["rw_p_adjusted"] <= 0.05 for s in rep["survivors"])


def test_romano_wolf_runs_per_horizon_not_across_all_of_them() -> None:
    """BUG 5, AND IT WAS DATA DESTRUCTION DRESSED AS STRICTNESS. Candidates at different horizons
    live on different period grids -- 60s has 978 observations, 900s has 45. Stacking them into
    one matrix truncated every column to the SHORTEST, cutting a t = +4.49 candidate to its last
    45 points and returning p_adjusted = 1.0. A horizon is the natural family: within it every
    mechanism shares one grid and one length."""
    import inspect
    src = inspect.getsource(S.main)
    assert "for h in HORIZONS_S:" in src
    assert "rw_family" in src


def test_survivors_must_clear_family_wise_error_not_just_stage_a(tmp_path) -> None:
    """Seven mechanisms x three horizons is a family, and the best of a family looks good by
    construction. A SCREEN-INTERESTING that fails Romano-Wolf is NOT a survivor."""
    root = tmp_path / "moat_c2"
    _tape(root, predictive=False)
    rep = _run(tmp_path, root)
    interesting = rep["tally"].get("SCREEN-INTERESTING", 0)
    assert len(rep["survivors"]) <= interesting


# ----------------------------------------------------------------------- hygiene

def test_a_scalar_mechanism_is_skipped_not_broadcast(tmp_path) -> None:
    """replenishment_halflife is one number per file. Broadcasting it to a constant would hand a
    degenerate feature a verdict."""
    root = tmp_path / "moat_s"
    _tape(root, predictive=True, n=800)
    rep = _run(tmp_path, root)
    assert rep["tally"].get("SCALAR-NOT-SCREENABLE", 0) >= 1


def test_absent_tape_is_reported_not_synthesised(tmp_path) -> None:
    rep = _run(tmp_path, tmp_path / "nope")
    assert rep["state"] == "NO TAPE"
    assert "NOT synthesised" in rep["note"]


def test_every_hypothesis_is_logged_win_or_lose(tmp_path) -> None:
    """Reporting only the printer is p-hacking. Zero survivors is a publishable outcome."""
    root = tmp_path / "moat_l"
    _tape(root, predictive=False)
    rep = _run(tmp_path, root)
    assert sum(rep["tally"].values()) == rep["hypotheses"]
    assert rep["authority"].startswith("NONE")
