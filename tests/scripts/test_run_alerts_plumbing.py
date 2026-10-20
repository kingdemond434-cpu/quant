"""The pager reads the plumbing watchdog and the judge's rate meter (2026-10-20).

Before this, `scripts/run_alerts.py` read none of the plumbing outputs, so a stalled judge or a
CRITICAL plumbing defect paged no one. These tests pin: CRITICAL escalated rows page, a
judge_throughput CRITICAL pages on its own key, a judge with no verdict in JUDGE_STALL_H pages,
an absent/unreadable/stale source pages UNMEASURED (never silence), and re-pages are spaced
REPAGE_H apart while the condition stands.
"""

from __future__ import annotations

import importlib.util
import json
import types
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

_ROOT = Path(__file__).resolve().parents[2]


def _load(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_M = _load("run_alerts_plumbing_under_test", _ROOT / "scripts" / "run_alerts.py")
NOW = datetime(2026, 10, 20, 18, 0, tzinfo=UTC)


def _row(check: str, severity: str, *, escalated: bool = True, organ: str = "MT5-X",
         evidence: str = "observed broken") -> dict[str, Any]:
    return {"check": check, "organ": organ, "severity": severity, "escalated": escalated,
            "evidence": evidence, "repair": "fix it", "key": f"{check}:{organ}"}


def _report(tmp: Path, rows: list[dict[str, Any]], *, at: datetime = NOW) -> Path:
    p = tmp / "PLUMBING_WATCHDOG.json"
    p.write_text(json.dumps({"at": at.isoformat(timespec="seconds"), "defects": rows,
                             "_envelope": {"artifact_id": "x"}}), "utf-8")
    return p


def _plumb(tmp: Path, json_path: Path | None = None, md_path: Path | None = None
           ) -> dict[str, str]:
    return dict(_M._plumbing_checks(NOW, json_path=json_path or tmp / "absent.json",
                                    md_path=md_path or tmp / "absent.md"))


# ------------------------------------------------------------------------------- constants
def test_named_constants_and_repage_window() -> None:
    assert _M.JUDGE_STALL_H == 6.0
    assert _M.REPAGE_H == 2.0
    for key in _M._PLUMBING_KEYS:
        assert _M._DEDUPE_OVERRIDES_S[key] == 2 * 3600


# ----------------------------------------------------------------------------- plumbing
def test_missing_plumbing_output_is_itself_an_alert(tmp_path: Path) -> None:
    out = _plumb(tmp_path)
    assert set(out) == {"plumbing_unmeasured"}
    assert "UNMEASURED" in out["plumbing_unmeasured"]


def test_unreadable_plumbing_output_is_an_alert(tmp_path: Path) -> None:
    bad = tmp_path / "PLUMBING_WATCHDOG.json"
    bad.write_text("{not json", "utf-8")
    assert set(_plumb(tmp_path, json_path=bad)) == {"plumbing_unmeasured"}


def test_critical_escalated_rows_page_and_major_or_first_pass_rows_do_not(
        tmp_path: Path) -> None:
    p = _report(tmp_path, [_row("adoption_task", "CRITICAL", organ="MT5-AdoptRelease"),
                           _row("path_pair", "MAJOR", organ="quiet-major"),
                           _row("orphan_workers", "CRITICAL", escalated=False,
                                organ="first-pass")])
    out = _plumb(tmp_path, json_path=p)
    assert set(out) == {"plumbing_critical"}
    assert "MT5-AdoptRelease" in out["plumbing_critical"]
    assert "quiet-major" not in out["plumbing_critical"]
    assert "first-pass" not in out["plumbing_critical"]


def test_healthy_fresh_report_pages_nothing(tmp_path: Path) -> None:
    assert _plumb(tmp_path, json_path=_report(tmp_path, [])) == {}


def test_judge_throughput_critical_pages_on_its_own_key(tmp_path: Path) -> None:
    p = _report(tmp_path, [_row("judge_throughput", "CRITICAL", organ="MT5-Gauntlet",
                                evidence="0 verdicts in 24h")])
    out = _plumb(tmp_path, json_path=p)
    assert set(out) == {"judge_throughput_critical"}
    assert "0 verdicts in 24h" in out["judge_throughput_critical"]


def test_stale_report_is_unmeasured_and_its_criticals_still_page(tmp_path: Path) -> None:
    p = _report(tmp_path, [_row("adoption_task", "CRITICAL")],
                at=NOW - timedelta(hours=_M.PLUMBING_MAX_AGE_H + 1))
    out = _plumb(tmp_path, json_path=p)
    assert set(out) == {"plumbing_unmeasured", "plumbing_critical"}
    assert "old" in out["plumbing_unmeasured"]


def test_unstamped_report_is_unmeasured(tmp_path: Path) -> None:
    p = tmp_path / "PLUMBING_WATCHDOG.json"
    p.write_text(json.dumps({"defects": []}), "utf-8")
    assert set(_plumb(tmp_path, json_path=p)) == {"plumbing_unmeasured"}


_MD_NEW = """# PLUMBING ALERTS

Generated {at} from `desks/mt5/reports/PLUMBING_WATCHDOG.json`.

| organ | check | severity | age | passes | evidence | repair |
|---|---|---|---|---|---|---|
| `MT5-AdoptRelease` | adoption_task | CRITICAL | 3h | 12 | a \\| piped evidence | Enable it |
| `data/x.json` | orphan_artifact_path | MAJOR | 0h | 2 | nobody writes it | write it |

## Why this page exists
"""

_MD_OLD = """# PLUMBING ALERTS

Generated {at} from `desks/mt5/reports/PLUMBING_WATCHDOG.json`.

| organ | check | age | passes | evidence | repair |
|---|---|---|---|---|---|
| `MT5-AdoptRelease` | adoption_task | 0h | 2 | Disabled | Enable it |
"""


def test_published_md_is_read_when_the_json_report_is_box_local(tmp_path: Path) -> None:
    md = tmp_path / "PLUMBING_ALERTS.md"
    md.write_text(_MD_NEW.format(at=NOW.isoformat()), "utf-8")
    out = _plumb(tmp_path, md_path=md)
    assert set(out) == {"plumbing_critical"}
    assert "a | piped evidence" in out["plumbing_critical"]
    assert "orphan_artifact_path" not in out["plumbing_critical"]


def test_md_without_severity_column_is_unmeasured_not_assumed_major(tmp_path: Path) -> None:
    md = tmp_path / "PLUMBING_ALERTS.md"
    md.write_text(_MD_OLD.format(at=NOW.isoformat()), "utf-8")
    out = _plumb(tmp_path, md_path=md)
    assert set(out) == {"plumbing_unmeasured"}
    assert "carry no severity" in out["plumbing_unmeasured"]


def test_the_newer_source_wins(tmp_path: Path) -> None:
    p = _report(tmp_path, [], at=NOW - timedelta(days=20))
    md = tmp_path / "PLUMBING_ALERTS.md"
    md.write_text(_MD_NEW.format(at=NOW.isoformat()), "utf-8")
    assert set(_plumb(tmp_path, json_path=p, md_path=md)) == {"plumbing_critical"}


def test_producer_renders_severity_the_pager_reads(tmp_path: Path) -> None:
    pw = _load("plumbing_watchdog_for_pager",
               _ROOT / "desks" / "mt5" / "research" / "plumbing_watchdog.py")
    md = tmp_path / "PLUMBING_ALERTS.md"
    pw.render_alerts({"at": NOW.isoformat(),
                      "defects": [{**_row("git_writer_lock", "CRITICAL"), "age_s": 7200,
                                   "passes": 3}]}, md)
    parsed = _M._parse_plumbing_md(md.read_text("utf-8"))
    assert parsed["at"] == NOW
    assert [(r["check"], r["severity"]) for r in parsed["rows"]] == [
        ("git_writer_lock", "CRITICAL")]


# -------------------------------------------------------------------------------- judge
def _rate(tmp: Path, *, last: datetime | None, at: datetime = NOW,
          status: str = "MEASURED", rows_total: int = 10) -> Path:
    p = tmp / "JUDGING_RATE.json"
    p.write_text(json.dumps({
        "at": at.isoformat(timespec="seconds"), "verdicts_per_hour": 0.0,
        "verdicts": {"status": status, "rows_total": rows_total,
                     "last_verdict_at": last.isoformat(timespec="seconds") if last else None}}),
        "utf-8")
    return p


def _judge(path: Path) -> dict[str, str]:
    return dict(_M._judge_checks(NOW, rate_path=path))


def test_judge_with_no_verdict_in_stall_window_pages(tmp_path: Path) -> None:
    out = _judge(_rate(tmp_path, last=NOW - timedelta(hours=_M.JUDGE_STALL_H + 1)))
    assert set(out) == {"judge_stalled"}
    assert "7.0h" in out["judge_stalled"]


def test_judge_with_a_recent_verdict_is_quiet(tmp_path: Path) -> None:
    assert _judge(_rate(tmp_path, last=NOW - timedelta(hours=1))) == {}


def test_stale_meter_with_old_verdict_pages_stall(tmp_path: Path) -> None:
    # the meter itself stopped 10h ago: its last verdict can only be older, so this is a stall
    out = _judge(_rate(tmp_path, at=NOW - timedelta(hours=10),
                       last=NOW - timedelta(hours=10.5)))
    assert set(out) == {"judge_stalled"} and "10.0h old" in out["judge_stalled"]


def test_empty_ledger_is_a_stall(tmp_path: Path) -> None:
    assert set(_judge(_rate(tmp_path, last=None, rows_total=0))) == {"judge_stalled"}


@pytest.mark.parametrize("make", [
    lambda t: t / "absent.json",
    lambda t: (t / "bad.json").write_text("[", "utf-8") and t / "bad.json",
    lambda t: _rate(t, last=NOW, status="UNMEASURED"),
    lambda t: _rate(t, last=NOW + timedelta(hours=1)),
])
def test_unreadable_or_unmeasured_meter_is_an_alert(tmp_path: Path, make: Any) -> None:
    assert set(_judge(make(tmp_path))) == {"judge_rate_unmeasured"}


def test_a_raising_check_pages_unmeasured() -> None:
    def boom() -> list[tuple[str, str]]:
        raise RuntimeError("secret-ish detail")
    out = _M._guarded("plumbing_unmeasured", boom)
    assert out[0][0] == "plumbing_unmeasured" and "secret-ish" not in out[0][1]


# ------------------------------------------------------------------ dedupe through main()
def _tick(monkeypatch: pytest.MonkeyPatch, tmp: Path, t: float,
          checks: list[tuple[str, str]]) -> list[tuple[str, str]]:
    pushes: list[tuple[str, str]] = []
    monkeypatch.chdir(tmp)
    (tmp / "data").mkdir(exist_ok=True)
    monkeypatch.setattr(_M.sys, "argv", ["run_alerts.py"])
    monkeypatch.setattr(_M, "_topic", lambda: "quant-desk-SECRETTOPIC")
    monkeypatch.setattr(_M, "_poll_replies", lambda topic: None)
    monkeypatch.setattr(_M, "_brain_watchdog", lambda state, active: None)
    monkeypatch.setattr(_M, "_checks", lambda: list(checks))
    monkeypatch.setattr(_M, "_push", lambda topic, title, body: pushes.append((title, body)))
    monkeypatch.setattr(_M, "time", types.SimpleNamespace(time=lambda: t))
    _M.main()
    return pushes


def test_repage_at_most_every_repage_h_while_failing(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    t0 = 1_800_000_000.0
    stall = [("judge_stalled", "judge STALLED")]
    assert len(_tick(monkeypatch, tmp_path, t0, stall)) == 1
    assert _tick(monkeypatch, tmp_path, t0 + 3600, stall) == []          # inside 2h
    assert len(_tick(monkeypatch, tmp_path, t0 + 2 * 3600 + 60, stall)) == 1  # re-page
    resolved = _tick(monkeypatch, tmp_path, t0 + 3 * 3600, [])
    assert [p[0] for p in resolved] == ["RESOLVED Quant desk: judge_stalled"]
    assert "SECRETTOPIC" not in capsys.readouterr().out


def test_a_future_dedupe_stamp_never_silences_the_pager(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    t0 = 1_800_000_000.0
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / ".last_alerts.json").write_text(
        json.dumps({"plumbing_critical": t0 + 86_400, "_paged": ["plumbing_critical"]}), "utf-8")
    pushes = _tick(monkeypatch, tmp_path, t0, [("plumbing_critical", "x")])
    assert len(pushes) == 1


def test_page_text_never_carries_the_topic(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    md = tmp_path / "PLUMBING_ALERTS.md"
    md.write_text(_MD_NEW.format(at=NOW.isoformat()), "utf-8")
    checks = _M._plumbing_checks(NOW, json_path=tmp_path / "absent.json", md_path=md)
    pushes = _tick(monkeypatch, tmp_path, 1_800_000_000.0, checks)
    assert pushes and all("SECRETTOPIC" not in t + b for t, b in pushes)
