"""The box's outside alarm: absent beats fail, a closed market excuses only the gateway, an
unarmed box is recorded NOT_ARMED, and the page fires once on the transition, not every 5 min."""
from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desks" / "mt5" / "scripts"))

import box_heartbeat as hb  # noqa: E402


def _beats(tmp: Path, monkeypatch: pytest.MonkeyPatch, age_min: float, now: float,
           fence: str = "GREEN") -> None:
    g, w, s = tmp / "DESK_STALE.json", tmp / "stall_watch.json", tmp / "SILENT_ORGANS.json"
    s.write_text(json.dumps({"fence": fence, "status": fence, "new_silent": []}))
    os.utime(s, (now - 5 * 60, now - 5 * 60))
    for p in (g, w):
        p.write_text("{}")
        os.utime(p, (now - age_min * 60, now - age_min * 60))
    monkeypatch.setattr(hb, "GATEWAY_BEAT", g)
    monkeypatch.setattr(hb, "WATCHDOG_BEAT", w)
    monkeypatch.setattr(hb, "SILENT_ORGANS", s)


def test_fx_week() -> None:
    assert hb.fx_open(datetime(2026, 9, 30, 12, tzinfo=UTC))          # Wednesday
    assert not hb.fx_open(datetime(2026, 10, 3, 12, tzinfo=UTC))      # Saturday
    assert not hb.fx_open(datetime(2026, 10, 2, 21, 30, tzinfo=UTC))  # Friday after close
    assert hb.fx_open(datetime(2026, 10, 4, 22, 30, tzinfo=UTC))      # Sunday reopen


def test_fresh_box_is_ok_and_stale_names_what(tmp_path: Path,
                                               monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime(2026, 9, 30, 12, tzinfo=UTC).timestamp()
    _beats(tmp_path, monkeypatch, 2, now)
    ok = hb.measure(now, research={"age_days": 0.05}, disk_free_gb=50)
    assert ok["verdict"] == "OK" and ok["failing"] == []
    _beats(tmp_path, monkeypatch, 90, now)
    bad = hb.measure(now, research={"age_days": 0.5}, disk_free_gb=2)
    assert bad["failing"] == ["disk", "gateway", "research", "watchdog"]


def test_absence_fails_and_closed_market_excuses_only_gateway(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(hb, "GATEWAY_BEAT", tmp_path / "none.json")
    monkeypatch.setattr(hb, "WATCHDOG_BEAT", tmp_path / "none2.json")
    monkeypatch.setattr(hb, "SILENT_ORGANS", tmp_path / "none3.json")
    sat = datetime(2026, 10, 3, 12, tzinfo=UTC).timestamp()
    r = hb.measure(sat, research={"age_days": None}, disk_free_gb=50)
    assert r["failing"] == ["research", "silent", "watchdog"]


def test_unarmed_is_recorded_and_alerts_go_through_desk_alerts(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The ping is NOT_ARMED without the secret; every non-dry run hands the reading to
    desk_alerts (which owns dedupe), and a dry run alerts nothing."""
    out = tmp_path / "BOX_HEARTBEAT.json"
    reading = {"at": "x", "checks": {"disk": {"free_gb": 1, "fail": True}},
               "failing": ["disk"], "verdict": "FAIL"}
    seen: list[tuple[list[str], Path]] = []
    import libs.ops.desk_alerts as da
    monkeypatch.setattr(da, "dispatch", lambda doc, **k: seen.append(
        (doc["failing"], k["out"])) or {"status": "QUIET"})
    d1 = hb.run(out=out, secrets=(tmp_path / "absent.json",), reading=dict(reading))
    assert d1["ping"]["status"] == "NOT_ARMED" and d1["paged"] == {"status": "QUIET"}
    assert seen == [(["disk"], tmp_path / "DESK_ALERTS.json")]
    hb.run(out=out, secrets=(tmp_path / "absent.json",), reading=dict(reading), dry_run=True)
    assert len(seen) == 1
    assert json.loads(out.read_text())["since"] == d1["since"]


def test_a_crashing_alert_path_never_breaks_the_heartbeat(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import libs.ops.desk_alerts as da

    def boom(doc: dict, **k: object) -> dict:
        raise RuntimeError("x")
    monkeypatch.setattr(da, "dispatch", boom)
    d = hb.run(out=tmp_path / "o.json", secrets=(tmp_path / "absent.json",),
               reading={"at": "x", "checks": {}, "failing": [], "verdict": "OK"})
    assert d["paged"] == {"status": "ERROR", "detail": "RuntimeError"}


def test_url_is_read_but_never_written(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sec = tmp_path / "box_heartbeat_url.json"
    sec.write_text(json.dumps({"url": "https://hc-ping.com/secret-uuid"}))
    calls: list[tuple[str, bool]] = []
    monkeypatch.setattr(hb, "_ping", lambda u, b, f: calls.append((u, f)) or "http 200")
    out = tmp_path / "o.json"
    hb.run(out=out, secrets=(sec,), reading={"at": "x", "checks": {}, "failing": [],
                                             "verdict": "OK"})
    assert calls == [("https://hc-ping.com/secret-uuid", False)]
    assert "secret-uuid" not in out.read_text()


# ------------------------------------------------ audit R2 (2026-09-30): the fence pages someone
@pytest.mark.parametrize("fence", ["RED", "UNMEASURED"])
def test_a_red_or_unmeasured_silent_fence_fails_the_heartbeat(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fence: str) -> None:
    now = datetime(2026, 9, 30, 12, tzinfo=UTC).timestamp()
    _beats(tmp_path, monkeypatch, 2, now, fence=fence)
    r = hb.measure(now, research={"age_days": 0.05}, disk_free_gb=50)
    assert r["failing"] == ["silent"] and r["checks"]["silent"]["fence"] == fence


def test_a_stale_green_census_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime(2026, 9, 30, 12, tzinfo=UTC).timestamp()
    _beats(tmp_path, monkeypatch, 2, now)
    os.utime(hb.SILENT_ORGANS, (now - 14 * 86400, now - 14 * 86400))
    r = hb.measure(now, research={"age_days": 0.05}, disk_free_gb=50)
    assert r["failing"] == ["silent"]


def test_red_fence_alerts_per_new_organ_even_when_the_box_was_already_failing(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """disk already RED, then the fence names an organ: a post. Same organs: no post. A NEW
    organ on the still-RED fence: another post. Real desk_alerts, fake route, gap disabled."""
    import libs.ops.desk_alerts as da
    out = tmp_path / "BOX_HEARTBEAT.json"
    posts: list[dict] = []

    def route(method: str, path: str, payload: dict | None) -> tuple[int, object]:
        if path.startswith("search/"):
            return 200, {"items": [{"title": da.ISSUE_TITLE, "number": 7, "state": "open"}]}
        if path.endswith("/comments"):
            posts.append(payload or {})
            return 201, {"html_url": "u"}
        return 200, {"login": "someone-else"}

    real = da.dispatch
    monkeypatch.setattr(da, "MIN_GAP_MIN", 0.0)
    monkeypatch.setattr(da, "dispatch", lambda doc, **k: real(
        doc, routes=[("token", route)], extra=lambda m: {"state": "NOT_ARMED"}, **k))
    census = tmp_path / "SILENT_ORGANS.json"
    monkeypatch.setattr(hb, "SILENT_ORGANS", census)

    def reading(failing: list[str], new: list[str]) -> dict:
        census.write_text(json.dumps({"organs": [{"organ": n} for n in ("leg:x", "leg:y")
                                                 if n in new or "silent" in failing]}))
        checks = {"disk": {"fail": "disk" in failing},
                  "silent": {"fail": "silent" in failing, "fence": "RED", "new_silent": new}}
        return {"at": "x", "checks": checks, "failing": failing, "verdict": "FAIL"}

    sec = (tmp_path / "absent.json",)
    hb.run(out=out, secrets=sec, reading=reading(["disk"], []))
    assert posts == []                                     # one beat is not yet confirmed
    hb.run(out=out, secrets=sec, reading=reading(["disk"], []))
    assert len(posts) == 1 and "`disk`" in posts[0]["body"]
    hb.run(out=out, secrets=sec, reading=reading(["disk", "silent"], ["leg:x"]))
    assert len(posts) == 2 and "silent:leg:x" in posts[1]["body"]
    hb.run(out=out, secrets=sec, reading=reading(["disk", "silent"], ["leg:x"]))
    assert len(posts) == 2
    hb.run(out=out, secrets=sec, reading=reading(["disk", "silent"], ["leg:y"]))
    assert len(posts) == 3 and "silent:leg:y" in posts[2]["body"]


def test_the_heartbeat_and_alert_reports_are_published_off_the_box() -> None:
    """2026-10-13 (#361): whether the box's outside alarm is ARMED could not be read off the box;
    BOX_HEARTBEAT.json was written and never published. DESK_ALERTS.json (the last alert sent)
    rides the same wire. Neither ever carries a URL or a token."""
    sys.path.insert(0, str(ROOT / "desks" / "mt5"))
    from mt5desk import release_identity

    from libs.ops import release
    assert hb.OUT.as_posix().endswith("desks/mt5/reports/BOX_HEARTBEAT.json")
    ignore = (ROOT / ".gitignore").read_text("utf-8").splitlines()
    sync = (ROOT / "desks/mt5/scripts/sync_shadow_to_git.ps1").read_text("utf-8", errors="ignore")
    block = sync.split("$relPaths = @(", 1)[1].split("\n)", 1)[0]
    for rel in ("desks/mt5/reports/BOX_HEARTBEAT.json", "desks/mt5/reports/DESK_ALERTS.json",
                "desks/mt5/reports/JUDGING_BURNDOWN.json", "desks/mt5/reports/WORLD_LAB.json",
                "desks/mt5/reports/EXPRESSION_FACTORY.json",
                "desks/mt5/reports/RELEASE_GATE.json",
                "desks/mt5/reports/ADOPTION_HEARTBEAT.json",
                "desks/mt5/reports/ADOPTION_STATE.json", "desks/mt5/data/stall_watch.json",
                "desks/mt5/data/world_causal_graph.json"):
        assert rel.startswith("desks/mt5/data/") or f"!{rel}" in ignore, rel
        assert f'"{rel}"' in block, rel
        assert rel in release.NON_CODE and rel in release_identity.NON_CODE, rel


def test_the_heartbeat_and_backup_are_contracted_and_the_backup_self_registers() -> None:
    from ops.organ_contract import CONTRACTS
    assert CONTRACTS["MT5-BoxHeartbeat"][0] == "desks/mt5/reports/DESK_ALERTS.json"
    assert CONTRACTS["MT5-OffsiteBackup"][0] == "desks/mt5/reports/OFFSITE_BACKUP.json"
    adopt = (ROOT / "desks/mt5/scripts/Adopt-And-Seal.ps1").read_text("utf-8", errors="ignore")
    assert 'Task = "MT5-OffsiteBackup"; Installer = "install_offsite_backup_task.ps1"' in adopt
    inst = (ROOT / "desks/mt5/scripts/install_offsite_backup_task.ps1").read_text("utf-8")
    assert "[switch]$IfMissing" in inst
