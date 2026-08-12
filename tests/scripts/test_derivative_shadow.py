"""oi_divergence and ls_contrarian could never complete a single scheduled run.

MEASURED 2026-08-12, answering a direct question about why these two pre-registered forward
clocks had not moved in the ~40 days since they were built: `run_derivative_shadow.py` crashed
with `UnboundLocalError: cannot access local variable 'series'` on the exact state a fresh archive
starts in -- `data/crypto_metrics.parquet` absent, which is precisely what the module's own
docstring says to expect ("no backtest fabricated" before real history exists). `series` was only
ever assigned inside the branch that runs when the archive DOES exist, but the peek/e-value line
read it unconditionally.

Separately, neither this script nor its sole data source (`collect_binance_metrics.py`) carried
the `sys.path` preamble every other scheduled organ on this desk has, so `python scripts/X.py` --
the exact form a cron line uses -- died on `ModuleNotFoundError: No module named 'libs'` before
either bug above ever had a chance to run. Both defects were invisible to `check_build_standard.py`
because neither script was in its governed set, and invisible to a human because nobody had
actually run them: they were called only as library imports inside an unscheduled batch script.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]


@pytest.fixture
def mod(tmp_path: Path, monkeypatch):
    import importlib.util
    monkeypatch.chdir(tmp_path)
    spec = importlib.util.spec_from_file_location(
        "run_derivative_shadow", _REPO / "scripts/run_derivative_shadow.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


# ------------------------------------------------------------------ the concrete regression
def test_an_absent_archive_does_not_crash(mod, tmp_path: Path) -> None:
    """THE BUG, REPRODUCED EXACTLY. No data/crypto_metrics.parquet -- the state this box, and
    apparently the VPS, has been in the whole time these clocks existed. This must never raise."""
    assert not (tmp_path / "data/crypto_metrics.parquet").exists()
    mod.main()  # UnboundLocalError here before the fix
    out = json.loads((tmp_path / "web/derivative_shadow.json").read_text("utf-8"))
    assert out["days_accumulated"] == 0
    assert out["status"] == "ACCUMULATING (no backtest fabricated)"
    assert out["forward_sharpe"] == {}
    assert out["anytime_peek"] == {}, "no series exists yet, so no peek can be computed either"


def test_an_absent_archive_reports_the_right_reason(mod, tmp_path: Path) -> None:
    mod.main()
    out = json.loads((tmp_path / "web/derivative_shadow.json").read_text("utf-8"))
    assert out["data_quality"] == "no archive yet"


# ------------------------------------------------------------------ the running organ
def test_the_script_runs_as_a_cron_line_would_invoke_it() -> None:
    """THE SECOND BUG. `python scripts/run_derivative_shadow.py` -- no PYTHONPATH, no `-m` --
    is exactly how every manifest line on this desk invokes a script. This organ died on
    ModuleNotFoundError before ever reaching main(), which is why the UnboundLocalError above was
    never seen in the wild: the script never got that far."""
    r = subprocess.run([sys.executable, str(_REPO / "scripts/run_derivative_shadow.py")],
                       cwd=_REPO, capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    assert "ModuleNotFoundError" not in r.stderr


def test_the_archiver_also_runs_as_a_cron_line_would_invoke_it() -> None:
    r = subprocess.run([sys.executable, str(_REPO / "scripts/collect_binance_metrics.py")],
                       cwd=_REPO, capture_output=True, text=True, timeout=120)
    assert "ModuleNotFoundError" not in r.stderr


def test_the_archiver_refuses_cleanly_when_the_universe_call_fails(monkeypatch,
                                                                     tmp_path: Path) -> None:
    """A failure discovering the tradeable universe used to be UNCAUGHT -- the per-symbol
    try/except only ever wrapped the metric fetches, never this call. A bare traceback in a cron
    log is not a refusal; SystemExit with a named reason is."""
    import importlib.util
    monkeypatch.chdir(tmp_path)
    spec = importlib.util.spec_from_file_location(
        "collect_binance_metrics", _REPO / "scripts/collect_binance_metrics.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)

    def _boom(*a, **k):
        raise RuntimeError("GET failed after 4: exchangeInfo :: HTTP Error 451")
    monkeypatch.setattr(m, "list_liquid_perps", _boom)
    with pytest.raises(SystemExit) as exc:
        m.main()
    assert "REFUSED" in str(exc.value) and "could not list the tradeable universe" in str(exc.value)


# ------------------------------------------------------------------ the honest docstring
def test_the_docstring_no_longer_claims_an_actuator_that_does_not_exist() -> None:
    """It used to say the CPCV/DSR/PBO gauntlet 'takes over' once MIN_DAYS is reached, stated as
    a plain fact. Nothing does. A false claim in a docstring is worse than silence -- it tells
    the next reader the gap is closed.

    MATCHED ON THE CORRECTIVE SENTENCE, not on the absence of the old phrase -- the phrase is
    quoted verbatim INSIDE the correction, to explain what was wrong, and a naive substring check
    would fail on its own fix. Same string-marker trap this desk has hit twice already this
    session (seat_preflight matching "seats" in a comment, publish_pipeline matching "subprocess"
    in the docstring explaining why it must not import it)."""
    src = (_REPO / "scripts/run_derivative_shadow.py").read_text("utf-8")
    assert 'takes over. Writes' not in src, "the old unqualified claim must not come back"
    assert "NO ACTUATOR EXISTS YET" in src
    assert "as though\nthat were wired" in src, "the corrective sentence must name it as false"
