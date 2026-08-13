"""dash.quanttt.xyz's Discovery panel (#disc) was empty because its sole producer never ran.

MEASURED 2026-08-12, answering "why is #disc empty, no 10 candidates showing": web/index.html's
#disc section reads web/discovery.json, written only by run_discovery.py, which had a direct grep
of zero cron/systemd lines -- genuinely unscheduled, not merely hard to find. It ALSO carried none
of the sys.path preamble every scheduled organ on this desk needs, so even a manual invocation in
exactly the form a cron line would use (`python scripts/run_discovery.py`, no PYTHONPATH, no -m)
died on ModuleNotFoundError before main() ever ran.

check_orphan_organs.py's first pass falsely read this organ as HEALTHY via a bogus transitive
parent (run_daily_research.py) -- itself only ever mentioned in a manifest COMMENT, never
actually scheduled. That was a separate, deeper bug in check_build_standard.py's scheduling
detector (see tests/governance/test_build_standard.py), fixed at the source; this file only pins
run_discovery.py's own defects.

A third, environment-specific failure surfaced on re-run: _panels()'s universe-discovery call
(list_liquid_perps -> fapi.binance.com/fapi/v1/exchangeInfo) returns HTTP 451 in this container,
the same failure collect_binance_metrics.py hit earlier and already fixed with a clean refusal.
This organ had the identical unwrapped call; fixed the same way.
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
        "run_discovery", _REPO / "scripts/run_discovery.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


# ------------------------------------------------------------------ the running organ
def test_the_script_runs_as_a_cron_line_would_invoke_it() -> None:
    """`python scripts/run_discovery.py` -- no PYTHONPATH, no -m -- is exactly how a manifest
    line invokes it. Before the preamble fix this died on ModuleNotFoundError before main() ever
    ran, which is why #disc has shown nothing since the panel existed."""
    r = subprocess.run([sys.executable, str(_REPO / "scripts/run_discovery.py")],
                       cwd=_REPO, capture_output=True, text=True, timeout=120)
    assert "ModuleNotFoundError" not in r.stderr


def test_the_organ_calls_the_lawful_guard(mod) -> None:
    src = (_REPO / "scripts/run_discovery.py").read_text("utf-8")
    assert "from libs.ops.lawful import guard as _law_guard" in src
    assert "_law_guard()" in src


# ------------------------------------------------------------------ the universe-discovery refusal
def test_refuses_cleanly_when_the_universe_call_fails(mod, monkeypatch) -> None:
    """THE THIRD BUG. list_liquid_perps() was unwrapped inside _panels() -- a failure (observed
    in this container as HTTP 451 on fapi.binance.com/fapi/v1/exchangeInfo) produced a bare
    traceback instead of the desk's standard fail-visible refusal. Matches the exact fix already
    applied to collect_binance_metrics.py's identical call."""
    def _boom(*a, **k):
        raise RuntimeError("GET failed after 4: exchangeInfo :: HTTP Error 451")
    monkeypatch.setattr(mod, "list_liquid_perps", _boom)
    with pytest.raises(SystemExit) as exc:
        mod._panels()
    assert "REFUSED" in str(exc.value)
    assert "could not list the tradeable universe" in str(exc.value)


def test_the_refusal_names_the_underlying_exception(mod, monkeypatch) -> None:
    def _boom(*a, **k):
        raise RuntimeError("HTTP Error 451")
    monkeypatch.setattr(mod, "list_liquid_perps", _boom)
    with pytest.raises(SystemExit) as exc:
        mod._panels()
    assert "RuntimeError" in str(exc.value) and "451" in str(exc.value)


# ------------------------------------------------------------------ dashboard-feed schema
def test_writes_the_exact_file_the_disc_panel_reads(mod) -> None:
    """web/index.html's #disc section fetches discovery.json by this exact name and path --
    a differently-named or differently-located output would leave the panel empty even with a
    fully working organ behind it."""
    assert Path("web/discovery.json") == mod._WEB


def test_pending_entries_carry_the_data_gated_clocks(mod) -> None:
    """oi_divergence and ls_contrarian are named in the data-gated list -- #disc must show them
    as PENDING (absent a completed OOS verdict) with real accrued-day counts, never silently
    omit them or claim they are live."""
    names = {n for n, _ds, _d in mod._PENDING}
    assert {"oi_divergence", "ls_contrarian"} <= names


# ------------------------------------------------------- R0130: PENDING must not outlive a verdict
def test_oos_verdicts_reads_a_completed_frozen_holdout_result(mod, tmp_path: Path) -> None:
    """R0130 (disposed 2026-08-05, commit f7cc022): oi_divergence/ls_contrarian already ran a
    pre-registered, embargoed OOS backtest and FAILED. #disc showed them as perpetual
    'PENDING (Nd/40d archived)' even after that verdict existed -- found 2026-08-13 investigating
    whether the desk's data-gated candidates were genuinely idle. They were not idle; the
    dashboard was just not reading what already existed."""
    out = tmp_path / "reports/reconstructed_oos/oi_ls_cross_sectional.json"
    out.parent.mkdir(parents=True)
    out.write_text(json.dumps({"results": [
        {"sleeve": "oi_divergence", "verdict": "OOS-FAILS",
         "ann_sharpe_net": -2.815, "nw_t_net": -5.74},
        {"sleeve": "ls_contrarian", "verdict": "OOS-FAILS",
         "ann_sharpe_net": 0.207, "nw_t_net": 0.42},
    ]}), "utf-8")
    verdicts = mod._oos_verdicts()
    assert verdicts["oi_divergence"]["verdict"] == "OOS-FAILS"
    assert verdicts["oi_divergence"]["ann_sharpe_net"] == -2.815
    assert verdicts["ls_contrarian"]["nw_t_net"] == 0.42


def test_oos_verdicts_absent_file_is_not_a_crash(mod) -> None:
    """No artifact yet (this container, or liquidation_reversal which has never been tested)
    means no verdict -- an empty dict, never a fabricated one and never a traceback."""
    assert mod._oos_verdicts() == {}


def test_oos_verdicts_unparseable_file_is_not_a_crash(mod, tmp_path: Path) -> None:
    out = tmp_path / "reports/reconstructed_oos/oi_ls_cross_sectional.json"
    out.parent.mkdir(parents=True)
    out.write_text("not json", "utf-8")
    assert mod._oos_verdicts() == {}


def test_oos_verdicts_wrong_shape_is_not_a_crash(mod, tmp_path: Path) -> None:
    out = tmp_path / "reports/reconstructed_oos/oi_ls_cross_sectional.json"
    out.parent.mkdir(parents=True)
    out.write_text(json.dumps({"results": "not-a-list"}), "utf-8")
    assert mod._oos_verdicts() == {}


# ------------------------------------------------------------------ the live desk
def test_the_organ_is_actually_scheduled() -> None:
    """THE POINT OF THIS WHOLE FIX. A working, tested script with no cron line is exactly the
    ORPHAN class check_orphan_organs.py exists to name -- fixing the code without wiring it back
    in would leave #disc exactly as empty as it was found."""
    man = (_REPO / "ops/crontab.manifest").read_text("utf-8")
    scheduled = any("run_discovery.py" in ln and ln[:1] in "0123456789*"
                    for ln in man.splitlines())
    assert scheduled, "run_discovery.py -- the #disc producer -- has no real cron line"
