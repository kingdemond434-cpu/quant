"""R0148 -- the conviction trader may never open a position blind because box cron idled.

The live incident: the chart organ (build_chart_context.py) was scheduled but not running, the
context file was absent, and every spawn degraded straight to "CHARTS UNAVAILABLE ... trading
BLIND" -- a leveraged directional sleeve reasoning with no price structure at all. The closure
under test: a MISSING or STALE chart file triggers exactly one bounded inline build and a
re-read; only a FAILED build may reach the blind path, and the failure is named in the brief.

The tests plant a fake scripts/build_chart_context.py under tmp_path, because the fallback
resolves the builder relative to the root it is asked to trade from -- proving the subprocess is
really spawned, not merely that some flag was flipped.
"""
from __future__ import annotations

import json
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from scripts.run_conviction_trader import _build_charts_inline, _chart_brief

#: The fake builders write this marker relative to their cwd, proving they actually ran.
_MARKER = "builder_ran.txt"

_GOOD_BUILDER = '''\
import json
from datetime import UTC, datetime
from pathlib import Path

Path("builder_ran.txt").write_text("ran", "utf-8")
Path("data").mkdir(exist_ok=True)
Path("data/chart_context.json").write_text(json.dumps(
    {"generated": datetime.now(tz=UTC).isoformat(), "status": "OK", "detail": "1/1",
     "charts": {"BTCUSDT": {"state": "OK"}}}), "utf-8")
'''

_FAILING_BUILDER = '''\
import sys
from pathlib import Path

Path("builder_ran.txt").write_text("ran", "utf-8")
print("venue unreachable", file=sys.stderr)
sys.exit(7)
'''

_SLOW_BUILDER = '''\
import time

time.sleep(30)
'''


def _plant_builder(root: Path, body: str) -> None:
    (root / "scripts").mkdir(parents=True, exist_ok=True)
    (root / "scripts/build_chart_context.py").write_text(body, "utf-8")


def _write_stale_context(root: Path, hours_old: float) -> None:
    (root / "data").mkdir(exist_ok=True)
    old = (datetime.now(tz=UTC) - timedelta(hours=hours_old)).isoformat()
    (root / "data/chart_context.json").write_text(json.dumps(
        {"generated": old, "status": "OK", "detail": "1/1",
         "charts": {"ETHUSDT": {"state": "OK"}}}), "utf-8")


# ------------------------------------------------------------------ missing file -> inline build

def test_missing_chart_file_triggers_the_inline_build(tmp_path):
    _plant_builder(tmp_path, _GOOD_BUILDER)
    txt = _chart_brief(tmp_path)
    assert (tmp_path / _MARKER).exists(), "the builder subprocess was never spawned"
    # the trader is NOT blind: it reads the chart the fallback just built
    assert "UNAVAILABLE" not in txt and "BLIND" not in txt
    assert "BTCUSDT" in txt
    # and the degradation-of-schedule is stated, not silently papered over
    assert "MISSING at spawn" in txt and "rebuilt inline" in txt


def test_builder_failure_still_degrades_loudly_not_crash(tmp_path):
    _plant_builder(tmp_path, _FAILING_BUILDER)
    txt = _chart_brief(tmp_path)                     # must not raise
    assert (tmp_path / _MARKER).exists(), "the inline build was never even attempted"
    # the pre-R0148 degraded-but-labelled path survives: blind is stated and PASS is instructed
    assert "CHARTS UNAVAILABLE" in txt and "BLIND" in txt and "PASS" in txt
    # and the build failure itself is recorded in the brief, with the builder's own words
    assert "inline rebuild failed" in txt
    assert "exit 7" in txt and "venue unreachable" in txt


def test_no_builder_script_at_all_still_degrades_not_crash(tmp_path):
    # worst case: even the fallback's own tool is missing on the host
    txt = _chart_brief(tmp_path)                     # must not raise
    assert "CHARTS UNAVAILABLE" in txt and "BLIND" in txt and "PASS" in txt
    assert "inline rebuild failed" in txt


# ---------------------------------------------------------------- stale file -> inline refresh

def test_stale_chart_context_is_rebuilt_inline(tmp_path):
    _write_stale_context(tmp_path, hours_old=9)
    _plant_builder(tmp_path, _GOOD_BUILDER)
    txt = _chart_brief(tmp_path)
    assert (tmp_path / _MARKER).exists()
    assert "STALE at spawn" in txt and "rebuilt inline" in txt
    assert "MAY BE STALE" not in txt                 # the refresh actually cleared the warning
    assert "BTCUSDT" in txt                          # fresh structure, not the 9h-old snapshot


def test_stale_refresh_failure_keeps_the_stale_warning(tmp_path):
    _write_stale_context(tmp_path, hours_old=9)
    _plant_builder(tmp_path, _FAILING_BUILDER)
    txt = _chart_brief(tmp_path)                     # must not raise
    assert (tmp_path / _MARKER).exists()
    # tighten-only: the stale copy is still served WITH its warning -- the existing gate holds
    assert "MAY BE STALE" in txt and "ETHUSDT" in txt


def test_fresh_chart_context_spawns_no_build(tmp_path):
    _write_stale_context(tmp_path, hours_old=0)      # fresh, despite the helper's name
    _plant_builder(tmp_path, _GOOD_BUILDER)
    txt = _chart_brief(tmp_path)
    assert not (tmp_path / _MARKER).exists(), "a fresh chart must not trigger a rebuild"
    assert "ETHUSDT" in txt and "rebuilt inline" not in txt


# ------------------------------------------------------------------------- the timeout is real

def test_inline_build_timeout_is_bounded(tmp_path):
    _plant_builder(tmp_path, _SLOW_BUILDER)
    t0 = time.monotonic()
    err = _build_charts_inline(tmp_path, timeout=1)
    elapsed = time.monotonic() - t0
    assert err is not None and "TimeoutExpired" in err
    assert elapsed < 15, f"timeout did not bound the build ({elapsed:.1f}s)"
