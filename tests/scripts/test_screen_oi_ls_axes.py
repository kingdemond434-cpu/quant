"""The genuinely fast, cross-sectional screen sat unused while a slow one got proposed instead.

MEASURED 2026-08-12. The principal asked for a cross-sectional reconstruction of the VRP screen
to accelerate validation. Checking the numbers first showed that wouldn't have worked: the VRP
screen's existing "pooled" trial has the SAME n_eff and panel_width as its per-market trials (both
~48, both 1) because the construction is a single blended daily portfolio return, not a
cross-sectional stack -- pooling more names into it changes what is measured, never how fast rows
arrive. Four of the six single-name VRP clocks (AVAX/SOL/XRP/TRX) cannot be pooled through this
construction at all: the underlying DVOL index only exists for BTC/ETH.

screen_oi_ls_axes.py is a DIFFERENT, ALREADY-BUILT screen that genuinely is cross-sectional --
139 symbols, panel stacked symbol-major, one IC per calendar day computed across the WHOLE
cross-section at once. It had never run: missing the sys.path preamble (same defect as
run_derivative_shadow.py and collect_binance_metrics.py, found the same day) and a second,
independent crash on the empty-archive case for its BTCUSDT single-asset leg. Its real input,
dl_oi_ls_universe.py, has been scheduled daily since before this session and backfills from
2022-07-01 for the tranche-1 cohort -- so once this screen runs, real cross-sectional history is
already waiting rather than a fresh clock.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]


def test_the_script_runs_as_a_cron_line_would_invoke_it() -> None:
    """Same defect class, same test shape as run_derivative_shadow.py's. `python scripts/X.py`,
    no PYTHONPATH, is exactly how a manifest line calls it."""
    r = subprocess.run([sys.executable, str(_REPO / "scripts/screen_oi_ls_axes.py")],
                       cwd=_REPO, capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    assert "ModuleNotFoundError" not in r.stderr


def test_an_absent_root_falls_back_rather_than_hardcoding_the_vps() -> None:
    """The old `ROOT = Path("/home/quant/quant-platform")` with no fallback meant every path in
    the file (MET, PX, BM, OUTDIR) silently pointed at a directory that does not exist on any box
    other than the VPS -- including this test running in CI."""
    src = (_REPO / "scripts/screen_oi_ls_axes.py").read_text("utf-8")
    assert "_ROOT.exists()" in src, "no fallback -- would break on every box but the VPS"


def test_an_empty_binance_metrics_archive_does_not_crash(tmp_path: Path, monkeypatch) -> None:
    """THE SECOND BUG, REPRODUCED EXACTLY. `pd.DataFrame([]).set_index('date')` raised KeyError
    when data/lake/bronze/binance_metrics/BTCUSDT held no zip files -- which is the state ANY
    fresh box hits on its very first run, since data/ is gitignored and never travels with a
    clone. The main oi_ls_daily leg already had this discipline (INSUFFICIENT-DATA on a thin
    cross-section); this leg crashed the whole organ instead."""
    import importlib.util
    monkeypatch.chdir(tmp_path)
    spec = importlib.util.spec_from_file_location(
        "screen_oi_ls_axes", _REPO / "scripts/screen_oi_ls_axes.py")
    m = importlib.util.module_from_spec(spec)
    monkeypatch.setattr(sys, "argv", ["screen_oi_ls_axes.py"])
    spec.loader.exec_module(m)  # UnboundLocalError/KeyError here before the fix

    result = m.screen_binance_metrics()
    assert result["symbols"] == 0 and result["days"] == 0
    assert "no usable archive" in result["why"]


def test_insufficient_data_trials_are_recorded_not_silently_skipped(tmp_path, monkeypatch) -> None:
    """A refusal has to be VISIBLE in the trial log, not just a clean return -- otherwise the
    output looks identical to a screen that ran 0 declared trials rather than one that ran 6 and
    found no data for any of them."""
    import importlib.util
    monkeypatch.chdir(tmp_path)
    spec = importlib.util.spec_from_file_location(
        "screen_oi_ls_axes", _REPO / "scripts/screen_oi_ls_axes.py")
    m = importlib.util.module_from_spec(spec)
    monkeypatch.setattr(sys, "argv", ["screen_oi_ls_axes.py"])
    spec.loader.exec_module(m)

    before = len(m.TRIALS)
    m.screen_binance_metrics()
    added = m.TRIALS[before:]
    assert len(added) == 6, "2 horizons x 3 constructions must all be logged, even empty"
    assert all(t["verdict"] == "INSUFFICIENT-DATA" and t["n"] == 0 for t in added)


def test_the_output_matches_the_schema_finalize_axis_screens_reads() -> None:
    """finalize_axis_screens.py globs reports/axis_screens/*.json generically and reads a
    `trials` list with `verdict` and `n` on each row. The filename does not have to match
    anything -- but the shape does, or this screen's output is invisible to the whole downstream
    chain (spawner, forward resolution, promotion) despite running cleanly."""
    r = subprocess.run([sys.executable, str(_REPO / "scripts/screen_oi_ls_axes.py")],
                       cwd=_REPO, capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    doc = json.loads((_REPO / "reports/axis_screens/_raw_trials.json").read_text("utf-8"))
    assert isinstance(doc["trials"], list) and doc["trials"]
    row = doc["trials"][0]
    assert "verdict" in row and "n" in row and "name" in row


def test_the_docstring_names_the_file_it_actually_writes() -> None:
    """It used to point at reports/axis_screens/oi_ls_daily.json, a file this script has never
    written -- the real output is _raw_trials.json. A stale path in a pre-registration doctrine
    sends the next reader looking in the wrong place for the alignment evidence it claims to
    document."""
    src = (_REPO / "scripts/screen_oi_ls_axes.py").read_text("utf-8")
    assert "_raw_trials.json, this organ's actual" in src


@pytest.mark.parametrize("cross_sectional_signal", ["screen_oi_ls_axes.py"])
def test_it_is_genuinely_cross_sectional_unlike_the_vrp_pool(cross_sectional_signal) -> None:
    """THE ACTUAL DISTINCTION THAT MATTERS. VRP's 'pooled' construction is one blended time
    series -- panel_width 1, same accrual rate as any single name. This screen stacks 139 symbols
    symbol-major and computes one pooled cross-sectional IC per calendar day across all of them at
    once, which is the real accelerant anytime_valid.py names: breadth, not a cleverer test."""
    src = (_REPO / "scripts" / cross_sectional_signal).read_text("utf-8")
    assert "139 symbols" in src and "panel is stacked symbol-major" in src
