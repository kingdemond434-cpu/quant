"""R0344: the degraded fallback must be proven alive BEFORE the outage that needs it.

Measured 2026-08-01T16:58Z: OpenRouter unfunded (-$0.59), the panel dropped to its 4 free seats,
and ALL FOUR failed (tencent 404, cohere 400, nvidia-nano 400, nvidia KeyError('choices')). 0/4
substantive -- the desk had no independent-review capability at all, and nothing anywhere would
have said so until the next outage asked.

WHAT EACH TEST PINS. The verdict must separate four states that all look like "no answers":
UNCONFIGURED (this box cannot see the roster), EMPTY (a roster with no seats -- a vacuous
denominator, L1.57), NOT-PROBED (read but not contacted) and DEAD (contacted and silent). Only
the last is a broken fallback; the others demand different repairs, and collapsing them is how a
desk debugs the wrong organ. NONE of them may exit 0 -- "we could not look" is never good news.
"""
from __future__ import annotations

import json
from typing import Any

import pytest

from scripts import build_audit_coverage as bac
from scripts import check_free_roster as fr
from scripts import run_external_panel as panel


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    """No live stores, no network, no waiting. bac.MANIFEST is an ABSOLUTE path, so chdir does
    not isolate it -- the canary reads the live seat tally and a test must not depend on it."""
    monkeypatch.setattr(fr, "OUT", tmp_path / "free_roster_canary.json")
    monkeypatch.setattr(bac, "MANIFEST", tmp_path / "audit_coverage.json")
    monkeypatch.setattr(panel._time, "sleep", lambda s: None)


def _roster(tmp_path, monkeypatch, n: int) -> None:
    p = tmp_path / "llm_panel_free.json"
    p.write_text(json.dumps({"providers": [
        {"name": f"free{i}", "model": f"lab/m{i}:free", "base_url": "https://x", "key": "k"}
        for i in range(n)]}), "utf-8")
    monkeypatch.setattr(fr, "ROSTER", p)


def test_all_seats_dead_is_a_breach(tmp_path, monkeypatch):
    """THE 2026-08-01 STATE. Every seat refuses -> DEAD, non-zero, and every seat's error is
    named, because a 404, a 400 and a KeyError are three causes with three repairs."""
    _roster(tmp_path, monkeypatch, 4)
    monkeypatch.setattr(panel, "_ask", lambda *a, **k: (_ for _ in ()).throw(
        RuntimeError("HTTP Error 404: Not Found")))
    rep = fr.build_report()
    assert rep["status"] == "DEAD"
    assert rep["n_alive"] == 0
    assert len(rep["breaches"]) == 4
    assert fr.fence_exit(rep["status"], fr._PASSING, scanned=rep["n_seats"], of="s") != 0


def test_one_live_seat_is_a_live_fallback(tmp_path, monkeypatch):
    """A fallback with one working seat is DEGRADED, not DOWN. The canary asks whether the desk
    retains any independent review at all -- grading its depth is the panel's job, not this."""
    _roster(tmp_path, monkeypatch, 4)
    calls = {"n": 0}

    def _one_alive(*a: Any, **k: Any) -> str:
        calls["n"] += 1
        if calls["n"] == 1:
            return "READY"
        raise RuntimeError("HTTP Error 400: Bad Request")

    monkeypatch.setattr(panel, "_ask", _one_alive)
    rep = fr.build_report()
    assert rep["status"] == "OK"
    assert rep["n_alive"] == 1
    assert fr.fence_exit(rep["status"], fr._PASSING, scanned=rep["n_seats"], of="s") == 0


def test_a_seat_that_answers_nothing_is_not_alive(tmp_path, monkeypatch):
    """An empty 200 is the nvidia KeyError('choices') class one layer on: the call succeeded and
    the seat still said nothing. A canary counting HTTP status would call this healthy."""
    _roster(tmp_path, monkeypatch, 2)
    monkeypatch.setattr(panel, "_ask", lambda *a, **k: "   \n  ")
    rep = fr.build_report()
    assert rep["status"] == "DEAD"
    assert rep["n_alive"] == 0


def test_empty_roster_is_vacuous_not_healthy(tmp_path, monkeypatch):
    """Zero answers over ZERO seats measures nothing (L1.57). fence_exit must refuse it even if
    the status string were ever mistakenly moved into _PASSING."""
    _roster(tmp_path, monkeypatch, 0)
    rep = fr.build_report()
    assert rep["status"] == "EMPTY"
    assert rep["n_seats"] == 0
    assert fr.fence_exit("OK", ("OK",), scanned=rep["n_seats"], of="s") != 0


def test_absent_roster_is_unmeasured_never_ok(tmp_path, monkeypatch):
    """A box that cannot see the roster knows nothing about the fallback. WS-005: absence must
    not resolve to a clean verdict."""
    monkeypatch.setattr(fr, "ROSTER", tmp_path / "nope.json")
    rep = fr.build_report()
    assert rep["status"] == "UNCONFIGURED"
    assert fr.fence_exit(rep["status"], fr._PASSING, scanned=rep["n_seats"], of="s") != 0
    assert rep["measured"] is False                  # L1.55 sibling flag, not just prose
    assert any(r["status"] == "ABSENT" for r in rep["provenance"])


def test_no_probe_never_passes(tmp_path, monkeypatch):
    """Reporting mode reads the roster and contacts nobody, so liveness is UNMEASURED. If this
    ever exits 0 the canary can be silenced by passing a flag."""
    _roster(tmp_path, monkeypatch, 4)
    rep = fr.build_report(probe=False)
    assert rep["status"] == "NOT-PROBED"
    assert fr.fence_exit(rep["status"], fr._PASSING, scanned=rep["n_seats"], of="s") != 0


def test_probe_shares_the_panels_retry_policy(tmp_path, monkeypatch):
    """The canary calls panel._ask, NOT _ask_once, so free-tier 400/429 flap is retried exactly
    as the panel retries it. A single-shot probe would report DEAD on transient pool saturation
    -- the measured 2026-08-12 failure -- cry wolf, and get switched off (L1.43)."""
    _roster(tmp_path, monkeypatch, 1)
    attempts = {"n": 0}

    def _flaky(*a: Any, **k: Any) -> str:
        attempts["n"] += 1
        if attempts["n"] <= panel._FREE_RETRIES:
            raise __import__("urllib.error", fromlist=["error"]).HTTPError(
                "u", 429, "rate", hdrs=None, fp=None)
        return "READY"

    monkeypatch.setattr(panel, "_ask_once", _flaky)     # patch BELOW _ask: the retry must be used
    rep = fr.build_report()
    assert rep["status"] == "OK"
    assert attempts["n"] == 1 + panel._FREE_RETRIES
