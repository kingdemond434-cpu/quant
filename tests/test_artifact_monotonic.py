"""THE ARTIFACT-ROLLBACK FENCE, PROVEN ON THE ROLLBACK IT WAS BUILT FOR (GAP 161).

The positive control replays the exact event: `forward_reconcile.json` read at
`checked_at 2026-08-27T07:58:08Z` (enrolled 21, certified_clocks 17), then re-read minutes later
as `2026-08-26T02:02:32Z` (enrolled 19, certified_pairs 6). A fence only ever observed returning
green has not been validated -- only its silence has.

The rest pin the ways it must NOT fire, because each of them is the normal state of these files:
they are rewritten every few minutes, so forward movement, an unchanged stamp and a byte-identical
rewrite all have to stay quiet or the fence is noise within an hour.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_artifact_monotonic.py"

NEW = "2026-08-27T07:58:08+00:00"
OLD = "2026-08-26T02:02:32+00:00"
REL = "desks/mt5/data/forward_reconcile.json"


@pytest.fixture
def fence(tmp_path, monkeypatch):
    """Load the script against a scratch desk. It resolves paths from `__file__`, so patching the
    module attributes is the only isolation that works -- `cwd` would leave it rewriting the live
    artifacts it is built to protect."""
    spec = importlib.util.spec_from_file_location("artifact_monotonic_under_test", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    monkeypatch.setattr(mod, "STORE", tmp_path / "high_water")
    monkeypatch.setattr(mod, "OUT", tmp_path / "artifact_monotonic.json")
    monkeypatch.setattr(mod, "WATCHED", {REL: "which clocks are enrolled"})
    monkeypatch.setattr(mod.sys, "argv", ["check_artifact_monotonic.py"])
    (tmp_path / REL).parent.mkdir(parents=True, exist_ok=True)
    mod._path = tmp_path / REL
    return mod


def _write(mod, stamp: str, **extra) -> None:
    mod._path.write_text(json.dumps({"checked_at": stamp, **extra}), "utf-8")


def _report(mod) -> dict:
    return json.loads(mod.OUT.read_text("utf-8"))


def test_it_fires_on_gap_161s_exact_rollback(fence):
    """THE POSITIVE CONTROL, and the repair: the newer content must come back."""
    _write(fence, NEW, enrolled=21, certified_clocks=17)
    assert fence.main() == 0, "the first sighting establishes the high-water mark"

    _write(fence, OLD, enrolled=19, certified_pairs=6)
    assert fence.main() == 1, "a stamp a full day backward must exit non-zero"

    report = _report(fence)
    assert report["status"] == "BREACH"
    row = report["regressions"][0]
    assert row["action"] == "RESTORED"
    assert row["hours_backward"] == pytest.approx(29.93, abs=0.05)

    healed = json.loads(fence._path.read_text("utf-8"))
    assert healed["checked_at"] == NEW, "the restore must put the NEWER content back"
    assert healed["enrolled"] == 21, "content, not just the stamp -- the numbers are the point"


def test_a_persistent_regression_escalates_instead_of_fighting_forever(fence):
    """After ESCALATE_AFTER restores the writer upstream has proven it will not stop.

    Continuing to rewrite would hide a defect only a console session can kill, so the fence stops
    repairing and says so. This is the escalation, not the resting state.
    """
    _write(fence, NEW, enrolled=21)
    fence.main()
    for _ in range(fence.ESCALATE_AFTER):
        _write(fence, OLD, enrolled=19)
        assert fence.main() == 1
        assert json.loads(fence._path.read_text())["checked_at"] == NEW

    _write(fence, OLD, enrolled=19)
    assert fence.main() == 1
    assert _report(fence)["escalated"] == [REL]
    assert json.loads(fence._path.read_text())["checked_at"] == OLD, (
        "past the escalation bar the stale content is LEFT in place, so the defect stays visible "
        "instead of being silently papered over every two minutes")


def test_forward_movement_is_never_a_regression(fence):
    """The normal state of these files. They are rewritten every few minutes."""
    _write(fence, OLD, enrolled=19)
    fence.main()
    _write(fence, NEW, enrolled=21)
    assert fence.main() == 0
    assert _report(fence)["regressions"] == []
    assert json.loads(fence._path.read_text())["enrolled"] == 21, "a real update must survive"


def test_an_unchanged_stamp_is_quiet(fence):
    """A pull that re-copies identical bytes must not read as anything at all."""
    _write(fence, NEW, enrolled=21)
    fence.main()
    _write(fence, NEW, enrolled=21)
    assert fence.main() == 0


def test_an_artifact_with_no_stamp_is_UNMEASURABLE_not_clean(fence):
    """A file this fence cannot judge is a hole in its coverage, and must say so (L1.28a).

    Reporting it as clean is the WS-005 failure -- absence resolving to a pass -- which is the
    exact class the rollback itself belongs to.
    """
    fence._path.write_text(json.dumps({"enrolled": 21}), "utf-8")
    assert fence.main() == 1
    report = _report(fence)
    assert report["unmeasurable"][0]["file"] == REL
    assert report["regressions"] == []


def test_report_mode_never_writes_the_artifact(fence):
    """--report must be safe to run anywhere, including beside a live writer."""
    _write(fence, NEW, enrolled=21)
    fence.main()
    _write(fence, OLD, enrolled=19)
    fence.sys.argv = ["check_artifact_monotonic.py", "--report"]

    assert fence.main() == 1
    assert json.loads(fence._path.read_text())["checked_at"] == OLD, "report mode must not heal"
    assert _report(fence)["regressions"][0]["action"] == "REPORT_ONLY"


def _module():
    """The real module against the real repo -- these two tests are about the SHIPPED registry,
    not about a scratch desk, so they deliberately do not use the `fence` fixture."""
    spec = importlib.util.spec_from_file_location("artifact_monotonic_registry", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_the_artifact_the_shadow_watchdog_judges_the_book_by_is_watched() -> None:
    """MEASURED 2026-08-27, during the repair of the 5.5-hour forward-book outage.

    `shadow_health.json` is the ONE file `monitor_mt5_shadow_sync` reads to decide whether the
    whole shadow book is healthy -- freshness, aggregate status, blocked count, missing
    certificates -- and it was the only shadow artifact absent from this fence. Its `updated_at`
    was observed going 21:25:47 -> 15:31:55 -> 21:39:08: six hours BACKWARDS, carrying the
    pre-fix `KeyError: 'EURZAR'` back with it and re-reporting a repaired outage as live.

    The cause of that single rollback was never established, which is the argument FOR the fence
    rather than against it: a stamp that moves backwards is a defect whoever moved it.
    """
    assert "desks/mt5/reports/shadow/shadow_health.json" in _module().WATCHED


def test_every_watched_shadow_artifact_the_watchdog_consumes_is_covered() -> None:
    """Pinned as a RELATIONSHIP, not a list: whatever the watchdog reads, this fence watches.

    The two organs drifted apart silently once. Deriving the requirement from the watchdog's own
    source means adding a file there fails HERE rather than in production.
    """
    mod = _module()
    watchdog = (ROOT / "scripts" / "monitor_mt5_shadow_sync.py").read_text("utf-8")
    consumed = {name for name in ("shadow_health.json", "shadow_state.json")
                if name in watchdog}
    watched = {Path(rel).name for rel in mod.WATCHED}
    missing = consumed - watched
    assert not missing, f"the shadow watchdog reads {sorted(missing)} and nothing guards rollback"
