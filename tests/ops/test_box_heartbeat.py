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


def _beats(tmp: Path, monkeypatch: pytest.MonkeyPatch, age_min: float, now: float) -> None:
    g, w = tmp / "DESK_STALE.json", tmp / "stall_watch.json"
    for p in (g, w):
        p.write_text("{}")
        os.utime(p, (now - age_min * 60, now - age_min * 60))
    monkeypatch.setattr(hb, "GATEWAY_BEAT", g)
    monkeypatch.setattr(hb, "WATCHDOG_BEAT", w)


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
    sat = datetime(2026, 10, 3, 12, tzinfo=UTC).timestamp()
    r = hb.measure(sat, research={"age_days": None}, disk_free_gb=None)
    assert r["failing"] == ["disk", "research", "watchdog"]


def test_unarmed_is_recorded_and_page_fires_once(tmp_path: Path,
                                                 monkeypatch: pytest.MonkeyPatch) -> None:
    out = tmp_path / "BOX_HEARTBEAT.json"
    reading = {"at": "x", "checks": {"disk": {"free_gb": 1, "fail": True}},
               "failing": ["disk"], "verdict": "FAIL"}
    sent: list[str] = []
    import libs.ops.alert_channels as ac
    monkeypatch.setattr(ac, "send_all", lambda t, b, **k: sent.append(b) or {"status": "ok"})
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
