"""A LEG THAT FAILS SAYS WHERE IT WAS.

Measured on the trading box 2026-11-11: five hourly legs (graveyard_resurrection, axis_registry,
qd_frontier, math_lab, residual_search) ended FAILED TIMEOUT at their wall caps for days, and the
box could not say where any of them stalled -- `_producer_impl` dropped the killed child's
captured stdout and stderr on `TimeoutExpired`. These tests pin that the last ~2000 characters of
both survive into the leg's result, its compute-ledger row and its LEG_FAILED event, for a
timeout and for a nonzero exit alike, and that a leg that succeeded carries none of it.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import hourly_cycle  # noqa: E402

from libs.ops import compute_ledger, events  # noqa: E402

MARK_OUT = "STALLED_IN_PHASE_THREE"
MARK_ERR = "LAST_TRACEBACK_LINE"


@pytest.fixture
def leg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """A real script path, a fixed budget, and every side effect of `_costed` captured."""
    script = tmp_path / "probe_leg.py"
    script.write_text("pass\n", "utf-8")
    monkeypatch.setattr(hourly_cycle, "_priced_budget", lambda n, b: (b, {}))
    monkeypatch.setattr(hourly_cycle, "HOURLY_PLAN", "all", raising=False)
    monkeypatch.setattr(hourly_cycle, "_rotation", lambda: None, raising=False)
    monkeypatch.setattr(hourly_cycle, "_woe_before", lambda name: {})
    monkeypatch.setattr(hourly_cycle, "_woe_after", lambda *a, **k: None)
    monkeypatch.setattr(hourly_cycle, "_advance_watermark", lambda *a, **k: None)
    seen: dict[str, Any] = {"closed": [], "events": []}
    monkeypatch.setattr(compute_ledger, "open_run", lambda name, **kw: object())
    monkeypatch.setattr(compute_ledger, "close_run",
                        lambda run, **kw: seen["closed"].append(kw) or {})
    monkeypatch.setattr(events, "leg_events",
                        lambda name, outcome, **kw: seen["events"].append(
                            {"leg": name, "outcome": outcome, **kw}) or [])
    seen["script"] = str(script)
    return seen


def _timeout(argv, **kw):
    raise subprocess.TimeoutExpired(argv, kw.get("timeout") or 0,
                                    output="x" * 5000 + MARK_OUT,
                                    stderr=("warn\n" * 1000 + MARK_ERR).encode())


def test_a_timed_out_leg_keeps_the_tail_of_what_it_printed(leg, monkeypatch) -> None:
    monkeypatch.setattr(hourly_cycle, "_run_tree", _timeout)
    out = hourly_cycle._producer_impl("probe_leg", leg["script"])
    assert out["exit_code"] is None and out["timeout_s"]
    assert out["stdout_tail"].endswith(MARK_OUT) and len(out["stdout_tail"]) == 2000
    assert out["stderr_tail"].endswith(MARK_ERR) and len(out["stderr_tail"]) <= 2000


def test_the_tail_reaches_the_ledger_row_and_the_leg_failed_event(leg, monkeypatch) -> None:
    monkeypatch.setattr(hourly_cycle, "_run_tree", _timeout)
    hourly_cycle._costed("probe_leg",
                         lambda: hourly_cycle._producer_impl("probe_leg", leg["script"]))
    row, = leg["closed"]
    assert row["outcome"] == "TIMEOUT"
    assert row["stdout_tail"].endswith(MARK_OUT) and row["stderr_tail"].endswith(MARK_ERR)
    ev, = leg["events"]
    assert ev["outcome"] == "TIMEOUT" and ev["stdout_tail"].endswith(MARK_OUT)
    assert ev["stderr_tail"].endswith(MARK_ERR)


def test_a_nonzero_exit_keeps_both_tails_and_a_clean_exit_carries_none(leg, monkeypatch) -> None:
    def _fails(argv, **kw):
        return subprocess.CompletedProcess(argv, 1, stdout="y" * 3000 + MARK_OUT,
                                           stderr="z" * 3000 + MARK_ERR)

    monkeypatch.setattr(hourly_cycle, "_run_tree", _fails)
    hourly_cycle._costed("probe_leg",
                         lambda: hourly_cycle._producer_impl("probe_leg", leg["script"]))
    row, = leg["closed"]
    assert row["stdout_tail"].endswith(MARK_OUT) and len(row["stdout_tail"]) == 2000
    assert row["stderr_tail"].endswith(MARK_ERR) and len(row["stderr_tail"]) == 2000
    assert leg["events"][0]["stderr_tail"].endswith(MARK_ERR)

    def _ok(argv, **kw):
        return subprocess.CompletedProcess(argv, 0, stdout="fine", stderr="")

    monkeypatch.setattr(hourly_cycle, "_run_tree", _ok)
    hourly_cycle._costed("probe_leg",
                         lambda: hourly_cycle._producer_impl("probe_leg", leg["script"]))
    assert "stdout_tail" not in leg["closed"][-1] and "stderr_tail" not in leg["events"][-1]


def test_a_timeout_with_nothing_captured_is_an_empty_tail_not_a_crash() -> None:
    assert hourly_cycle._text_tail(None) == ""
    assert hourly_cycle._text_tail(b"\xff\xfeabc").endswith("abc")
    assert hourly_cycle._fail_tails("not a dict") == {}
