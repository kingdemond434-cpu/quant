"""`organ-stale` must not page about an organ that is running right now (2026-08-12).

WHAT FIRED, AND WHY IT WAS WRONG BOTH WAYS. At 14:54 max_audit reported
`organ-stale-brain-cycle: last SUCCESSFUL run 13h ago -- silently degraded`. The cycle was
RUNNING at that moment and exited 0 at 15:26. Two independent instrument faults produced it:

  1. No liveness test. `_producer_running` already encodes this rule for products -- "a monitor
     that cries wolf on healthy work is how a desk learns to ignore its own pager" -- and
     check_organs never consulted it. A claude organ writes deliverables via file tools, so its
     log stays tiny until exit and every healthy long run looks dead to a size-and-mtime rule.
  2. A SHARED artifact in the liveness table. The reported age is min(log_age, artifact_age), and
     `data/decision_ledger.json` is written by every commit and several organs -- so it made the
     number OPTIMISTIC (13h reported against 17.9h of genuine death through four consecutive
     failures). libs/ops/organ_catchup.py dropped both brain artifacts for exactly this reason on
     2026-07-26; this table kept them, and the two drifted apart in silence.

The forgiveness is BOUNDED on purpose: past 2x the cadence window a still-running producer is a
HUNG run, which is the failure this check exists to catch.
"""

from __future__ import annotations

import time

import pytest

from libs.ops import organ_catchup
from scripts import max_audit


@pytest.fixture
def logs(tmp_path, monkeypatch):
    d = tmp_path / "cro_ai_logs"
    d.mkdir(parents=True)
    monkeypatch.setattr(max_audit, "LOGS", d)
    monkeypatch.setattr(max_audit, "ROOT", tmp_path)
    return d


def _stale_brain_log(logs, hours: float) -> None:
    """A substantial brain log last touched `hours` ago -- i.e. the organ is that stale."""
    import os
    p = logs / "20260812_0245.log"
    p.write_text("x" * 2500, "utf-8")
    now = time.time()
    os.utime(p, (now - hours * 3600, now - hours * 3600))
    return None


def _run(monkeypatch, running: bool) -> dict[str, str]:
    monkeypatch.setattr(max_audit, "NOW", time.time())
    monkeypatch.setattr(max_audit, "_organ_running", lambda organ: running)
    monkeypatch.setattr(max_audit, "ORGANS", {"brain-cycle": ("2026*_*.log", 2000, 8.0)})
    defects: list[tuple[str, str]] = []
    max_audit.check_organs(defects)
    return dict(defects)


def test_a_running_organ_inside_2x_the_window_is_not_called_silently_degraded(logs, monkeypatch):
    """THE REGRESSION. 13h stale, cadence 8h, producer alive -> in flight, not degraded."""
    _stale_brain_log(logs, hours=13.0)
    assert _run(monkeypatch, running=True) == {}


def test_the_same_state_with_a_dead_producer_still_fires(logs, monkeypatch):
    """The liveness test must not become a blanket excuse -- nothing running, defect stands."""
    _stale_brain_log(logs, hours=13.0)
    ids = _run(monkeypatch, running=False)
    assert "organ-stale-brain-cycle" in ids
    assert "silently degraded" in ids["organ-stale-brain-cycle"]


def test_a_producer_running_past_2x_the_window_is_reported_as_HUNG(logs, monkeypatch):
    """Forgiving an in-flight run forever would hide the exact failure this check exists for."""
    _stale_brain_log(logs, hours=20.0)          # > 2 * 8h
    ids = _run(monkeypatch, running=True)
    assert "organ-stale-brain-cycle" in ids
    assert "HUNG run, not a missed one" in ids["organ-stale-brain-cycle"]


def test_a_fresh_organ_never_fires(logs, monkeypatch):
    _stale_brain_log(logs, hours=0.3)
    assert _run(monkeypatch, running=False) == {}


def test_brain_liveness_artifacts_match_organ_catchup_exactly():
    """THE DRIFT ITSELF. Both tables claim to mirror each other; only one dropped the shared
    artifacts, and the disagreement made a dead cycle read 5h younger than it was."""
    brain = next(o for o in organ_catchup.ORGANS if o.name == "brain")
    assert max_audit.ORGAN_ARTIFACTS["brain-cycle"] == brain.artifacts == (), (
        "the decision ledger and cadence_duties are written by many organs, so neither is "
        "evidence THIS organ ran -- and because the reported age is min(log, artifact) a shared "
        "artifact makes a dead cycle look YOUNGER than it is")


def test_liveness_is_unprovable_means_report_not_excuse(monkeypatch):
    """An organ with no known pgrep pattern must not be silently forgiven (L1.28a)."""
    monkeypatch.setattr(max_audit, "_ORGAN_PGREP", {})
    assert max_audit._organ_running("no-such-organ") is False
