"""THE CROSS-SECTIONAL RUNNER MUST PRINT THE COST BEFORE THE BREADTH.

Breadth is the encouraging number and cost is the deciding one: on the control panel hedging buys
about 1.35x in IR while a fully-invested book pays 100-270% of capital a year in fees at
15-minute frequency. Anyone reading only the breadth figure draws the opposite conclusion from the
one the numbers support, so the order they appear in is not a cosmetic choice.

It must also refuse a one-symbol directory rather than quietly running a directional book and
labelling the result market-neutral.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import scripts.run_ict_cross_sectional as X  # noqa: E402

REPORT = ROOT / "data/ict_cross_sectional.json"


def _write_panel(d: Path, k: int = 6, n: int = 3000, seed: int = 0) -> None:
    d.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)
    common = rng.normal(0, 0.0035, n)
    for i in range(k):
        r = np.sqrt(0.8) * common + np.sqrt(0.2) * rng.normal(0, 0.0035, n)
        c = 100 * np.exp(np.cumsum(r))
        o = np.concatenate(([100.0], c[:-1]))
        w = np.abs(rng.normal(0, 0.0035, n)) * c
        pd.DataFrame({"open": o, "high": np.maximum(o, c) + w,
                      "low": np.minimum(o, c) - w, "close": c}).to_csv(d / f"S{i}.csv", index=False)


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts/run_ict_cross_sectional.py"), *args],
        capture_output=True, text=True, cwd=ROOT, timeout=900, check=False)


def test_cost_is_printed_before_breadth(tmp_path: Path) -> None:
    """Order is the message. The cost decides and the breadth encourages."""
    _write_panel(tmp_path / "p")
    r = _run("--bars-dir", str(tmp_path / "p"))
    assert r.returncode == 0, r.stderr
    out = r.stdout
    assert out.index("COST") < out.index("breadth"), out


def test_a_single_symbol_directory_is_refused(tmp_path: Path) -> None:
    """One symbol has no cross-section. Running it anyway would report a market-neutral result for
    a directional bet."""
    _write_panel(tmp_path / "one", k=1)
    r = _run("--bars-dir", str(tmp_path / "one"))
    assert r.returncode == 0
    assert "NO PANEL" in r.stdout
    assert "at least 2" in json.loads(REPORT.read_text("utf-8"))["reason"]


def test_a_missing_directory_is_reported_not_synthesised(tmp_path: Path) -> None:
    r = _run("--bars-dir", str(tmp_path / "nope"))
    assert r.returncode == 0
    assert "NO PANEL" in r.stdout
    assert "NOT synthesised" in json.loads(REPORT.read_text("utf-8"))["note"]


def test_the_report_carries_measured_breadth_both_ways(tmp_path: Path) -> None:
    """Both the directional and the residual figure, so the GAIN is visible rather than only the
    flattering half.

    IT DOES NOT ASSERT THAT HEDGING ALWAYS WINS, because on a single small panel it does not. A
    6-symbol seed measured 5.91 residual against 6.06 directional: the beta estimate carries its
    own error, and at small N that noise can cost more than removing the common factor buys.
    Averaged over seeds the gain is real and grows with N (1.19x at 4 symbols, 2.20x at 20), but
    pinning a one-sample inequality would have made this test a coin flip dressed as a law.
    """
    _write_panel(tmp_path / "p")
    assert _run("--bars-dir", str(tmp_path / "p")).returncode == 0
    b = json.loads(REPORT.read_text("utf-8"))["breadth"]
    for k in ("n_eff_directional", "n_eff_residual", "gain_from_hedging"):
        assert k in b and np.isfinite(b[k])
    # The MECHANISM is what must hold every time: the hedge removes common-factor exposure.
    assert abs(b["mean_corr_residual"]) < abs(b["mean_corr_directional"])


def test_the_report_declares_its_cost_estimate_incomplete(tmp_path: Path) -> None:
    """Perp funding on the short leg is not modelled. A cost figure that does not say what it
    omits gets quoted as complete -- and this one is already the binding constraint."""
    _write_panel(tmp_path / "p")
    assert _run("--bars-dir", str(tmp_path / "p")).returncode == 0
    assert "LOWER BOUND" in json.loads(REPORT.read_text("utf-8"))["note"]


def test_load_panel_skips_files_without_ohlc(tmp_path: Path) -> None:
    _write_panel(tmp_path / "p", k=3)
    pd.DataFrame({"close": [1.0] * 500}).to_csv(tmp_path / "p" / "bad.csv", index=False)
    panel, why = X.load_panel(tmp_path / "p")
    assert "bad" not in panel
    assert len(panel) == 3, why
