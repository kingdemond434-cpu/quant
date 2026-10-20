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
    _rails(tmp, monkeypatch, now - age_min * 60)


def _rails(tmp: Path, monkeypatch: pytest.MonkeyPatch, stamp: float, *, errors: dict | None = None,
           alerts: bool = True) -> None:
    iso = datetime.fromtimestamp(stamp, tz=UTC).isoformat()
    dm, gw, sh = tmp / "fusion_deadman_state.json", tmp / "gateway_state.json", tmp / "sh.json"
    dm.write_text(json.dumps({"checked_at": iso, "mode": "DRY-RUN"}))
    gw.write_text(json.dumps({"last_reconcile": iso}))
    sh.write_text(json.dumps({"updated_at": iso, "errors": errors or {}}))
    cfg = tmp / "alert_channels.json"
    if alerts:
        cfg.write_text(json.dumps({"channels": [{"kind": "ntfy", "topic": "t"}]}))
    else:
        cfg.unlink(missing_ok=True)
    monkeypatch.setattr(hb, "DEADMAN_STAMP", dm)
    monkeypatch.setattr(hb, "GATEWAY_STATE", gw)
    monkeypatch.setattr(hb, "SHADOW_HEALTH", sh)
    monkeypatch.setattr(hb, "ALERT_CONFIGS", (cfg,))


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
    assert bad["failing"] == ["deadman", "disk", "gateway", "mt5_link", "research", "watchdog"]


def test_absence_fails_and_closed_market_excuses_only_gateway(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(hb, "GATEWAY_BEAT", tmp_path / "none.json")
    monkeypatch.setattr(hb, "WATCHDOG_BEAT", tmp_path / "none2.json")
    monkeypatch.setattr(hb, "SILENT_ORGANS", tmp_path / "none6.json")
    monkeypatch.setattr(hb, "DEADMAN_STAMP", tmp_path / "none3.json")
    monkeypatch.setattr(hb, "GATEWAY_STATE", tmp_path / "none4.json")
    monkeypatch.setattr(hb, "SHADOW_HEALTH", tmp_path / "none5.json")
    sat = datetime(2026, 10, 3, 12, tzinfo=UTC).timestamp()
    r = hb.measure(sat, research={"age_days": None}, disk_free_gb=50, alert_kinds=["ntfy"])
    # a closed market excuses the gateway pass and the broker link, never the rail or the clocks
    assert r["failing"] == ["deadman", "forward", "research", "silent", "watchdog"]


def test_unarmed_is_recorded_and_page_fires_once(tmp_path: Path,
                                                 monkeypatch: pytest.MonkeyPatch) -> None:
    out = tmp_path / "BOX_HEARTBEAT.json"
    reading = {"at": "x", "checks": {"disk": {"free_gb": 1, "fail": True}},
               "failing": ["disk"], "verdict": "FAIL"}
    sent: list[str] = []
    import libs.ops.alert_channels as ac
    monkeypatch.setattr(ac, "send_all",
                        lambda t, b, **k: sent.append(b) or {"armed": 1, "delivered": 1})
    d1 = hb.run(out=out, secrets=(tmp_path / "absent.json",), reading=dict(reading))
    assert d1["ping"]["status"] == "NOT_ARMED" and len(sent) == 1
    hb.run(out=out, secrets=(tmp_path / "absent.json",), reading=dict(reading))
    assert len(sent) == 1
    assert json.loads(out.read_text())["since"] == d1["since"]


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


def test_red_fence_pages_even_when_the_box_was_already_failing(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """disk already failing, then the fence turns RED: a page. Same RED, same organs: no page.
    A NEW organ on the still-RED fence: another page."""
    out = tmp_path / "BOX_HEARTBEAT.json"
    sent: list[str] = []
    import libs.ops.alert_channels as ac
    monkeypatch.setattr(ac, "send_all", lambda t, b, **k: sent.append(b) or {"status": "ok"})

    def reading(failing: list[str], new: list[str]) -> dict:
        checks = {"disk": {"fail": "disk" in failing},
                  "silent": {"fail": "silent" in failing, "fence": "RED", "new_silent": new}}
        return {"at": "x", "checks": checks, "failing": failing, "verdict": "FAIL"}

    sec = (tmp_path / "absent.json",)
    hb.run(out=out, secrets=sec, reading=reading(["disk"], []))
    assert len(sent) == 1
    hb.run(out=out, secrets=sec, reading=reading(["disk", "silent"], ["leg:x"]))
    assert len(sent) == 2
    hb.run(out=out, secrets=sec, reading=reading(["disk", "silent"], ["leg:x"]))
    assert len(sent) == 2
    hb.run(out=out, secrets=sec, reading=reading(["disk", "silent"], ["leg:y"]))
    assert len(sent) == 3
def test_desk_health_2026_10_20_is_four_failures(tmp_path: Path,
                                                monkeypatch: pytest.MonkeyPatch) -> None:
    """The reading that went unpaged: rail stamp five weeks old, reconcile two days old, the
    forward lane failing on MT5 IPC, no channel armed -- with the old four checks all fresh."""
    now = datetime(2026, 10, 20, 15, tzinfo=UTC).timestamp()
    _beats(tmp_path, monkeypatch, 2, now)
    _rails(tmp_path, monkeypatch, now - 2 * 86400, alerts=False,
           errors={"scalp_bar_refresh": "initialize failed: (-10004, 'No IPC connection')"})
    r = hb.measure(now, research={"age_days": 0.05}, disk_free_gb=50)
    assert r["failing"] == ["alerts", "deadman", "forward", "mt5_link"]
    _rails(tmp_path, monkeypatch, now - 60)
    assert hb.measure(now, research={"age_days": 0.05}, disk_free_gb=50)["verdict"] == "OK"


def test_forward_ipc_error_fails_even_when_fresh(tmp_path: Path,
                                                 monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime(2026, 10, 20, 15, tzinfo=UTC).timestamp()
    _beats(tmp_path, monkeypatch, 2, now)
    _rails(tmp_path, monkeypatch, now - 60, errors={"x": "initialize failed: (-10004, 'No IPC')"})
    r = hb.measure(now, research={"age_days": 0.05}, disk_free_gb=50)
    assert r["failing"] == ["forward"] and r["checks"]["forward"]["mt5_errors"] == ["x"]


def test_still_failing_repages_after_repage_h(tmp_path: Path,
                                              monkeypatch: pytest.MonkeyPatch) -> None:
    out = tmp_path / "BOX_HEARTBEAT.json"
    reading = {"at": "x", "checks": {"deadman": {"age_min": 999, "fail": True}},
               "failing": ["deadman"], "verdict": "FAIL"}
    sent: list[str] = []
    import libs.ops.alert_channels as ac
    monkeypatch.setattr(ac, "send_all",
                        lambda t, b, **k: sent.append(b) or {"armed": 1, "delivered": 1})
    absent = (tmp_path / "absent.json",)
    hb.run(out=out, secrets=absent, reading=dict(reading))
    hb.run(out=out, secrets=absent, reading=dict(reading))
    assert len(sent) == 1
    doc = json.loads(out.read_text())
    doc["last_paged_at"] = "2026-01-01T00:00:00+00:00"
    out.write_text(json.dumps(doc))
    hb.run(out=out, secrets=absent, reading=dict(reading))
    assert len(sent) == 2
    hb.run(out=out, secrets=absent, reading={"at": "x", "checks": {}, "failing": [],
                                             "verdict": "OK"})
    assert json.loads(out.read_text())["last_paged_at"] is None


def test_failed_send_and_bad_stamp_retry_next_pass(tmp_path: Path,
                                                   monkeypatch: pytest.MonkeyPatch) -> None:
    out = tmp_path / "BOX_HEARTBEAT.json"
    reading = {"at": "x", "checks": {"deadman": {"age_min": 999, "fail": True}},
               "failing": ["deadman"], "verdict": "FAIL"}
    sent: list[str] = []
    import libs.ops.alert_channels as ac
    monkeypatch.setattr(ac, "send_all", lambda t, b, **k: sent.append(b) or {"armed": 1,
                                                                              "delivered": 0})
    absent = (tmp_path / "absent.json",)
    hb.run(out=out, secrets=absent, reading=dict(reading))
    hb.run(out=out, secrets=absent, reading=dict(reading))
    assert len(sent) == 2                     # undelivered: retried on the very next pass
    monkeypatch.setattr(ac, "send_all", lambda t, b, **k: sent.append(b) or {"armed": 1,
                                                                              "delivered": 1})
    for stamp in ("garbage", "2999-01-01T00:00:00+00:00"):
        doc = json.loads(out.read_text())
        doc["last_paged_at"] = stamp
        out.write_text(json.dumps(doc))
        n = len(sent)
        hb.run(out=out, secrets=absent, reading=dict(reading))
        assert len(sent) == n + 1
