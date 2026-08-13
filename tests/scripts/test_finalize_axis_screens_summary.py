"""The 2026-08-12 crash class: the per-trial summary print dereferenced `t['ic']` while the
sort key beside it used `.get` -- one event-study-shaped trial (no `ic`) aborted the finalizer
mid-loop, and every axis after it never received `verdict_adjusted`. The line formatter must be
TOTAL: any trial shape prints, missing metrics print as `?`, nothing raises.
"""
from __future__ import annotations

from scripts.finalize_axis_screens import _trial_line


def test_full_trial_prints_all_metrics():
    line = _trial_line({"name": "n", "ic": 0.0123, "ic_t_stat": 2.5,
                        "sharpe_best_reported": 1.5, "sharpe_best_corrected": 0.7,
                        "verdict_adjusted": "SCREEN-INTERESTING: x"})
    assert "IC=+0.0123" in line and "t=2.50" in line and "Sh 1.50->0.70" in line


def test_event_study_shaped_trial_does_not_raise():
    line = _trial_line({"name": "listing_event", "verdict_adjusted": "KILLED: y"})
    assert "IC=?" in line and "t=?" in line and "Sh ?" in line
    assert "KILLED" in line


def test_empty_trial_does_not_raise():
    assert "?" in _trial_line({})
