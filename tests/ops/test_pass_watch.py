"""ops/pass_watch.py: flags only on change, and never reads absence as fine."""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "ops"))

import pass_watch

NOW = datetime(2026, 11, 18, 20, 0, tzinfo=UTC)


def _box(
    root: Path,
    *,
    at: datetime = NOW,
    bad: tuple[str, ...] = ("MT5-Daily",),
    attention: int = 21,
    ok: bool = False,
    running: str = "b78e2ec03fda",
    code: str = "4441809cb",
    status: str = "RED",
    queued: int = 500,
    open_prs: int = 624,
    rows: bool = True,
) -> None:
    stamp = at.isoformat()
    procs = [{"name": n, "verdict": "FAILING"} for n in bad] + [
        {"name": "E8-Gold", "verdict": "OK"}
    ]
    files = {
        "desks/mt5/reports/process_health.json": {
            "at": stamp,
            "n_needing_attention": attention,
            "counts": {"FAILING": len(bad)},
            "processes": procs if rows else [],
        },
        "desks/mt5/data/release_identity.json": {
            "at": stamp,
            "ok": ok,
            "running_sha": running,
            "release_sha": "bb527d650cfa",
        },
        "desks/mt5/reports/MERGE_PIPELINE.json": {
            "at": stamp,
            "status": status,
            "queue": {"queued_runs": queued, "oldest_queued_min": 900},
            "live": {"last_code_commit": code, "hours_since_code": 1.0},
            "coverage": {"open_prs": open_prs},
        },
    }
    for rel, data in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data), encoding="utf-8")


def _run(root: Path, now: datetime = NOW) -> dict:
    return pass_watch.run(root=root, now=now)


def test_first_run_flags_then_an_unchanged_box_is_quiet(tmp_path: Path) -> None:
    _box(tmp_path)
    first = _run(tmp_path)
    assert first["flag"] and first["reasons"][0].startswith("FIRST_RUN")
    second = _run(tmp_path, NOW + timedelta(minutes=30))
    assert second == {**second, "flag": False, "reasons": []}
    written = json.loads((tmp_path / "desks/mt5/reports/PASS_WATCH.json").read_text())
    assert (
        written["flag"] is False and written["state"]["pipeline"]["last_code_commit"] == "4441809cb"
    )


def test_a_merge_on_live_flags(tmp_path: Path) -> None:
    _box(tmp_path)
    _run(tmp_path)
    _box(tmp_path, code="deadbeef1")
    r = _run(tmp_path)
    assert r["flag"] and any(
        x.startswith("LIVE_CODE: 4441809cb -> deadbeef1") for x in r["reasons"]
    )


def test_release_flip_and_new_failure_and_attention_rise_flag(tmp_path: Path) -> None:
    _box(tmp_path)
    _run(tmp_path)
    _box(tmp_path, ok=True, running="9c1cedd08aaa", bad=("MT5-Daily", "MT5-Gateway"), attention=25)
    reasons = _run(tmp_path)["reasons"]
    assert "RELEASE: ok False -> True" in reasons
    assert any(x.startswith("RELEASE: running_sha") for x in reasons)
    assert "HEALTH_NEW: MT5-Gateway FAILING" in reasons
    assert "ATTENTION_UP: 21 -> 25" in reasons


def test_small_attention_wobble_and_a_fixed_process_stay_quiet(tmp_path: Path) -> None:
    _box(tmp_path)
    _run(tmp_path)
    _box(tmp_path, bad=(), attention=23)
    assert _run(tmp_path)["reasons"] == []


def test_queue_jump_pr_surge_and_pipeline_status_flag(tmp_path: Path) -> None:
    _box(tmp_path)
    _run(tmp_path)
    _box(tmp_path, queued=650, open_prs=640, status="GREEN")
    reasons = _run(tmp_path)["reasons"]
    assert "QUEUE_JUMP: 500 -> 650" in reasons
    assert "PR_SURGE: 624 -> 640" in reasons
    assert "PIPELINE: RED -> GREEN" in reasons


def test_missing_stale_or_empty_inputs_are_unmeasured_never_fine(tmp_path: Path) -> None:
    _box(tmp_path)
    _run(tmp_path)
    (tmp_path / "desks/mt5/data/release_identity.json").unlink()
    r = _run(tmp_path)
    assert r["flag"] and any(
        "UNMEASURED" in x and "release_identity.json missing" in x for x in r["reasons"]
    )
    # the last good reading is kept, so the next good read does not look like a change
    assert r["state"]["release"]["running_sha"] == "b78e2ec03fda"

    _box(tmp_path, at=NOW - timedelta(hours=5))
    r = _run(tmp_path)
    assert sum("UNMEASURED" in x for x in r["reasons"]) == 3

    _box(tmp_path, rows=False)
    r = _run(tmp_path)
    assert any("has no process rows" in x for x in r["reasons"])


def test_unreadable_previous_report_is_a_first_run(tmp_path: Path) -> None:
    _box(tmp_path)
    out = tmp_path / "desks/mt5/reports/PASS_WATCH.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("{not json", encoding="utf-8")
    assert _run(tmp_path)["reasons"][0].startswith("FIRST_RUN")


def test_print_mode_writes_nothing(tmp_path: Path) -> None:
    _box(tmp_path)
    pass_watch.run(root=tmp_path, now=NOW, write=False)
    assert not (tmp_path / "desks/mt5/reports/PASS_WATCH.json").exists()


def test_no_network_or_llm_imports() -> None:
    src = (Path(pass_watch.__file__)).read_text(encoding="utf-8")
    for banned in (
        "import requests",
        "urllib",
        "http.client",
        "subprocess",
        "socket",
        "openai",
        "anthropic",
        "ollama",
    ):
        assert banned not in src, banned


def _fills(root: Path, alarms: list[dict], at: datetime = NOW) -> None:
    p = root / "desks/mt5/reports/DAILY_FILLS.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps({"at": at.isoformat(), "status": "ALARM" if alarms else "OK", "alarms": alarms}),
        encoding="utf-8",
    )


def test_an_account_with_no_fill_on_a_market_day_flags_once(tmp_path: Path) -> None:
    _box(tmp_path)
    first = _run(tmp_path)
    assert first["state"]["fills"] == {"status": "NOT_ON_BOX"}  # #1314 not adopted: no flag
    assert _run(tmp_path, NOW + timedelta(minutes=30))["reasons"] == []
    dry = {
        "key": "daily_fills:ftmo",
        "date": "2026-11-18",
        "verdict": "ZERO_FILLS",
        "last_error": "ftmo: no entry on market day 2026-11-18",
    }
    _fills(tmp_path, [dry], NOW + timedelta(minutes=60))
    r = _run(tmp_path, NOW + timedelta(minutes=60))
    assert r["flag"] and "NO_FILL: daily_fills:ftmo@2026-11-18" in r["reasons"]
    assert r["state"]["fills"]["why"] == ["ftmo: no entry on market day 2026-11-18"]
    _box(tmp_path, at=NOW + timedelta(minutes=90))
    _fills(tmp_path, [dry], NOW + timedelta(minutes=90))
    assert _run(tmp_path, NOW + timedelta(minutes=90))["reasons"] == []  # same alarm: quiet
    # the next market day with no fill is a new alarm
    _box(tmp_path, at=NOW + timedelta(hours=24))
    _fills(tmp_path, [{**dry, "date": "2026-11-19"}], NOW + timedelta(hours=24))
    assert (
        "NO_FILL: daily_fills:ftmo@2026-11-19"
        in _run(tmp_path, NOW + timedelta(hours=24))["reasons"]
    )
    # once seen, a vanished or stale fills report is UNMEASURED, never "no alarms"
    (tmp_path / "desks/mt5/reports/DAILY_FILLS.json").unlink()
    _box(tmp_path, at=NOW + timedelta(hours=25))
    r = _run(tmp_path, NOW + timedelta(hours=25))
    assert any("DAILY_FILLS.json missing" in x for x in r["reasons"])
    _fills(tmp_path, [], NOW)
    r = _run(tmp_path, NOW + timedelta(hours=25))
    assert any("UNMEASURED" in x and "DAILY_FILLS.json is" in x for x in r["reasons"])


def test_attention_over_24h_flags_once_when_it_crosses(tmp_path: Path) -> None:
    _box(tmp_path)
    _run(tmp_path)
    for h in (6, 12, 23):
        _box(tmp_path, at=NOW + timedelta(hours=h))
        r = _run(tmp_path, NOW + timedelta(hours=h))
        assert r["reasons"] == [] and r["state"]["health"]["over_24h"] == []
    _box(tmp_path, at=NOW + timedelta(hours=24, minutes=30))
    r = _run(tmp_path, NOW + timedelta(hours=24, minutes=30))
    assert r["reasons"] == ["ATTENTION_24H: MT5-Daily"]
    _box(tmp_path, at=NOW + timedelta(hours=25))
    r = _run(tmp_path, NOW + timedelta(hours=25))
    assert r["reasons"] == [] and r["state"]["health"]["over_24h"] == ["MT5-Daily"]
    # fixed, then failing again: the clock restarts
    _box(tmp_path, bad=(), at=NOW + timedelta(hours=26))
    _run(tmp_path, NOW + timedelta(hours=26))
    _box(tmp_path, at=NOW + timedelta(hours=27))
    r = _run(tmp_path, NOW + timedelta(hours=27))
    assert (
        r["reasons"] == ["HEALTH_NEW: MT5-Daily FAILING"] and r["state"]["health"]["over_24h"] == []
    )


def test_stale_feed_and_missed_task_are_health_flags(tmp_path: Path) -> None:
    _box(tmp_path)
    _run(tmp_path)
    health = tmp_path / "desks/mt5/reports/process_health.json"
    doc = json.loads(health.read_text())
    doc["processes"] += [
        {"name": "MT5-Universe", "verdict": "STALE"},
        {"name": "MT5-CertHygiene", "verdict": "NOT_SCHEDULED"},
        {"name": "MT5-FrontierAudit (x)", "verdict": "NO_ARTIFACT"},
    ]
    health.write_text(json.dumps(doc))
    (reason,) = _run(tmp_path)["reasons"]
    assert reason == (
        "HEALTH_NEW: MT5-CertHygiene NOT_SCHEDULED, MT5-FrontierAudit (x) NO_ARTIFACT, "
        "MT5-Universe STALE"
    )


def test_process_health_carries_the_verdict_off_box(tmp_path: Path, monkeypatch) -> None:
    """PASS_WATCH.json stays on the box; process_health.json (already published) carries it."""
    import process_health

    out = tmp_path / "desks/mt5/reports/process_health.json"
    monkeypatch.setattr(process_health, "OUT", out)
    assert process_health._pass_watch()["status"] == "UNMEASURED"
    now = datetime.now(UTC)
    _box(tmp_path, at=now)
    pass_watch.run(root=tmp_path, now=now)
    carried = process_health._pass_watch()
    assert carried["status"] == "OK" and carried["flag"] is True
    assert carried["reasons"][0].startswith("FIRST_RUN")
    assert carried["at"] == now.isoformat(timespec="seconds")


def test_a_stopped_watcher_reads_stale_and_flagged(tmp_path: Path, monkeypatch) -> None:
    """An old or unreadable `at` never reads as "nothing changed"."""
    import process_health

    out = tmp_path / "desks/mt5/reports/process_health.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(process_health, "OUT", out)
    watch = out.parent / "PASS_WATCH.json"
    now = datetime.now(UTC)
    for at in ((now - timedelta(days=300)).isoformat(), "not a time", None):
        watch.write_text(json.dumps({"at": at, "flag": False, "reasons": []}), encoding="utf-8")
        got = process_health._pass_watch()
        assert got["status"] == "STALE" and got["flag"] is True, at
        assert got["reasons"][0].startswith("STALE: PASS_WATCH.json")
    fresh = (now - timedelta(minutes=30)).isoformat()
    watch.write_text(json.dumps({"at": fresh, "flag": False, "reasons": []}), encoding="utf-8")
    assert process_health._pass_watch() == {
        "status": "OK",
        "at": fresh,
        "flag": False,
        "reasons": [],
    }
