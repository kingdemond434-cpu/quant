"""The pager names every promotion candidate the forward-evidence hold kept over 24h -- and
pages when the file that would say so is absent, unstamped or stale (audit of #351, SF-b)."""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import run_alerts


def _doc(path: Path, last_age_h: float | None, *, doc_age_h: float | None = 0.1) -> Path:
    now = datetime.now(UTC)
    entry = {"first_held_at": (now - timedelta(hours=30)).isoformat(),
             "why": "forward evidence UNMEASURED: no bars"}
    if last_age_h is not None:
        entry["last_held_at"] = (now - timedelta(hours=last_age_h)).isoformat()
    doc: dict = {"alarm_after_h": 24, "alarm": ["EURZAR.carry"], "held": {"EURZAR.carry": entry}}
    if doc_age_h is not None:
        doc["generated_at"] = (now - timedelta(hours=doc_age_h)).isoformat()
    path.write_text(json.dumps(doc), "utf-8")
    return path


def _keys(out: list) -> list:
    return [k for k, _ in out]


def test_a_current_long_hold_pages(tmp_path: Path) -> None:
    out = run_alerts._forward_evidence_hold_alarms(_doc(tmp_path / "a.json", 0.25))
    assert _keys(out) == ["forward_evidence_hold_EURZAR.carry"]
    assert "UNMEASURED" in out[0][1]


def test_a_released_hold_in_a_fresh_document_does_not_page(tmp_path: Path) -> None:
    assert run_alerts._forward_evidence_hold_alarms(_doc(tmp_path / "a.json", 3.0)) == []


def test_an_absent_file_with_no_writer_is_a_counted_unwired_line_not_a_page(
        tmp_path: Path) -> None:
    unwired: list = []
    out = run_alerts._forward_evidence_hold_alarms(tmp_path / "missing.json", wired=False,
                                                   unwired=unwired)
    assert out == []
    assert _keys(unwired) == ["forward_evidence_hold_alarm_unwired"]
    assert "UNMEASURED" in unwired[0][1] and "UNWIRED" in unwired[0][1]


def test_an_absent_file_pages_once_a_writer_exists(tmp_path: Path) -> None:
    unwired: list = []
    out = run_alerts._forward_evidence_hold_alarms(tmp_path / "missing.json", wired=True,
                                                   unwired=unwired)
    assert _keys(out) == ["forward_evidence_hold_alarm_absent"] and "UNMEASURED" in out[0][1]
    assert unwired == []


def test_wired_means_a_writer_marker_or_a_file_seen_once(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(run_alerts, "_STATE", tmp_path / "state.json")
    monkeypatch.setattr(run_alerts, "_FE_HOLD_WRITER_MARKER", tmp_path / "writer")
    monkeypatch.setattr(run_alerts, "_UNWIRED", [])
    missing = tmp_path / "missing.json"
    assert run_alerts._fe_hold_wired() is False
    assert run_alerts._forward_evidence_hold_alarms(missing) == []
    assert _keys(run_alerts._UNWIRED) == ["forward_evidence_hold_alarm_unwired"]
    (tmp_path / "state.json").write_text(json.dumps({"other": 1}), "utf-8")
    assert run_alerts._fe_hold_wired() is False
    (tmp_path / "state.json").write_text(
        json.dumps({run_alerts._FE_HOLD_SEEN_KEY: 1.0}), "utf-8")
    assert _keys(run_alerts._forward_evidence_hold_alarms(missing)) == [
        "forward_evidence_hold_alarm_absent"]
    (tmp_path / "state.json").unlink()
    (tmp_path / "writer").write_text("", "utf-8")
    assert _keys(run_alerts._forward_evidence_hold_alarms(missing)) == [
        "forward_evidence_hold_alarm_absent"]


def test_the_marker_and_the_alarm_resolve_from_the_repo_root_not_the_cwd(
        tmp_path: Path, monkeypatch) -> None:
    """A pager started from another directory must find the same marker: a cwd-relative path
    there reads a registered writer as unwired, and its dead alarm file stops paging."""
    scripts = Path(run_alerts.__file__).resolve().parent
    data = scripts.parent / "desks" / "mt5" / "data"
    alarm, marker = run_alerts._FE_HOLD_ALARM, run_alerts._FE_HOLD_WRITER_MARKER
    assert alarm == data / "forward_evidence_hold_alarm.json"
    assert marker == data / "forward_evidence_hold_alarm.writer"
    assert alarm.is_absolute() and marker.is_absolute()
    # a fresh interpreter started in a directory that holds no desks/ at all gets the same two
    code = ("import sys; sys.path.insert(0, sys.argv[1]); import run_alerts as r; "
            "print(r._FE_HOLD_ALARM); print(r._FE_HOLD_WRITER_MARKER)")
    out = subprocess.run([sys.executable, "-c", code, str(scripts)], cwd=tmp_path,
                         capture_output=True, text=True, check=True).stdout.split()
    assert [Path(x) for x in out] == [alarm, marker]
    # and the wired reading itself does not move with the current directory
    here = tmp_path / "repo" / "desks" / "mt5" / "data" / "forward_evidence_hold_alarm.writer"
    here.parent.mkdir(parents=True)
    here.write_text("", "utf-8")
    monkeypatch.setattr(run_alerts, "_STATE", tmp_path / "no_state.json")
    monkeypatch.setattr(run_alerts, "_FE_HOLD_WRITER_MARKER", here)
    monkeypatch.chdir(tmp_path)
    assert run_alerts._fe_hold_wired() is True


def test_a_file_that_exists_is_held_to_the_full_standard_with_no_writer_registered(
        tmp_path: Path) -> None:
    unwired: list = []
    stale = run_alerts._forward_evidence_hold_alarms(
        _doc(tmp_path / "a.json", 3.0, doc_age_h=3.0), wired=False, unwired=unwired)
    assert _keys(stale) == ["forward_evidence_hold_alarm_stale"] and unwired == []
    (tmp_path / "b.json").write_text("{not json", "utf-8")
    assert _keys(run_alerts._forward_evidence_hold_alarms(
        tmp_path / "b.json", wired=False, unwired=unwired)) == [
        "forward_evidence_hold_alarm_unreadable"] and unwired == []


def test_the_pager_remembers_the_file_and_reports_the_unwired_count() -> None:
    src = Path(run_alerts.__file__).read_text("utf-8")
    assert "state.setdefault(_FE_HOLD_SEEN_KEY, now)" in src
    assert 'state["_unwired"] = dict(_UNWIRED)' in src
    assert "{len(_UNWIRED)} UNWIRED (not paged)" in src


def test_a_stale_document_pages_instead_of_reading_as_released(tmp_path: Path) -> None:
    """The writer died three hours ago holding a candidate: every stamp is old, and the first
    version read that as a released hold and paged nothing."""
    out = run_alerts._forward_evidence_hold_alarms(
        _doc(tmp_path / "a.json", 3.0, doc_age_h=3.0))
    assert _keys(out) == ["forward_evidence_hold_alarm_stale"]


def test_an_unstamped_document_pages(tmp_path: Path) -> None:
    out = run_alerts._forward_evidence_hold_alarms(
        _doc(tmp_path / "a.json", 0.25, doc_age_h=None))
    assert _keys(out) == ["forward_evidence_hold_alarm_stale"]


def test_an_alarmed_name_with_no_last_held_at_pages(tmp_path: Path) -> None:
    out = run_alerts._forward_evidence_hold_alarms(_doc(tmp_path / "a.json", None))
    assert _keys(out) == ["forward_evidence_hold_EURZAR.carry"] and "UNMEASURED" in out[0][1]


def test_an_unreadable_file_pages(tmp_path: Path) -> None:
    (tmp_path / "a.json").write_text("{not json", "utf-8")
    assert _keys(run_alerts._forward_evidence_hold_alarms(tmp_path / "a.json")) == [
        "forward_evidence_hold_alarm_unreadable"]
    (tmp_path / "a.json").write_text("[]", "utf-8")
    assert _keys(run_alerts._forward_evidence_hold_alarms(tmp_path / "a.json")) == [
        "forward_evidence_hold_alarm_unreadable"]


def test_the_alarm_is_wired_into_the_pager() -> None:
    src = Path(run_alerts.__file__).read_text("utf-8")
    assert "out.extend(_forward_evidence_hold_alarms())" in src
    assert "out.extend(_remint_pending_alarms())" in src


def _liveness(path: Path, cert: dict | None) -> Path:
    path.write_text(json.dumps({"certificate": cert} if cert is not None else {}), "utf-8")
    return path


def test_an_overdue_remint_wait_pages(tmp_path: Path) -> None:
    out = run_alerts._remint_pending_alarms(_liveness(tmp_path / "c.json", {
        "remint_pending": 3, "remint_pending_overdue": 2,
        "remint_pending_oldest_age_s": 30 * 3600.0, "remint_pending_alarm_s": 24 * 3600.0}))
    assert _keys(out) == ["clock_remint_pending_overdue"]
    assert "2 forward clock(s)" in out[0][1] and "30.0h" in out[0][1] and "24h" in out[0][1]


def test_a_remint_wait_inside_the_bound_does_not_page(tmp_path: Path) -> None:
    for cert in ({"remint_pending": 3, "remint_pending_overdue": 0}, {}, None):
        assert run_alerts._remint_pending_alarms(_liveness(tmp_path / "c.json", cert)) == []
    assert run_alerts._remint_pending_alarms(tmp_path / "missing.json") == []
