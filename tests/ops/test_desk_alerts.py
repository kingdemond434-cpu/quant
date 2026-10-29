"""WHERE A DESK PAGE GOES, AND WHAT STILL PROVES THE PHONE WORKS (2026-10-29 audit follow-up).

A desk page no longer reaches the owner's phone, so it must reach something that acts: a row in
desks/mt5/reports/DESK_ALERTS.json that check_desk_health turns into a PROBLEM while it is fresh,
and hc /log (recorded, notifies nobody) instead of /fail. Routed rows must never read as
deliveries anywhere -- not in the ratchets, not in the canary's sent count -- and the personal
channel's own liveness becomes a desk RED rather than a buzz.
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from libs.ops import alert_channels as ac

ROOT = Path(__file__).resolve().parents[2]


def _load(rel: str, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _ledger(tmp_path: Path, rows: list[dict[str, Any]]) -> Path:
    p = tmp_path / "data" / "alert_delivery.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("".join(json.dumps(r) + "\n" for r in rows), "utf-8")
    return p


def _now_iso(**delta: float) -> str:
    return (datetime.now(tz=UTC) - timedelta(**delta)).isoformat()


ROUTED_ONLY = [{"ts": _now_iso(minutes=5), "channel": "ntfy", "ok": True,
                "detail": "routed: desk audience", "routed": "desk"}] * 10


# --- MF1: routed rows are not deliveries in the pager-health readers -----------------------------

def test_check_ratchets_does_not_count_a_routed_row_as_delivered(tmp_path: Path) -> None:
    sys.path.insert(0, str(ROOT))
    import scripts.check_ratchets as cr
    led = _ledger(tmp_path, ROUTED_ONLY)
    assert ac.all_silent_since(24.0, ledger=led)
    assert cr._alert_delivery(led) == 0.0
    real = [*ROUTED_ONLY, {"ts": _now_iso(minutes=1), "channel": "hc", "ok": True}]
    assert cr._alert_delivery(_ledger(tmp_path, real)) == 1.0


def test_capability_ratchet_does_not_read_routed_rows_as_10_of_10(tmp_path: Path) -> None:
    from libs.research import capability_ratchet as cap
    _ledger(tmp_path, ROUTED_ONLY)
    comp = next(c for c in cap._alerting(tmp_path, datetime.now(tz=UTC))
                if c.key == "pager_deliveries_ok")
    assert "10/10" not in comp.detail and comp.score != 10.0
    _ledger(tmp_path, [*ROUTED_ONLY, {"ts": _now_iso(minutes=1), "channel": "hc", "ok": True},
                       {"ts": _now_iso(minutes=1), "channel": "ntfy", "ok": False}])
    comp = next(c for c in cap._alerting(tmp_path, datetime.now(tz=UTC))
                if c.key == "pager_deliveries_ok")
    assert comp.detail.startswith("1/2 ")


def test_the_canary_sent_count_excludes_routed() -> None:
    canary = _load("scripts/run_alert_canary.py", "run_alert_canary_sent")
    assert canary.sent_count({"delivered": 3, "routed": 3}) == 0
    assert canary.sent_count({"delivered": 3, "routed": 1}) == 2
    assert canary.sent_count(None) == "throttled"


# --- SF1: desk pages land in DESK_ALERTS.json, which check_desk_health reads ---------------------

@pytest.fixture
def quiet(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, bool]]:
    """Every sender recorded, none reaching the network. hc records whether it was canary/log."""
    seen: list[tuple[str, bool]] = []
    def rec(kind: str) -> Any:
        def send(_c: dict[str, Any], _t: str, _b: str) -> str:
            seen.append((kind, False))
            return "http 200"
        return send

    for kind in ("ntfy", "telegram", "email", "webhook"):
        monkeypatch.setitem(ac._SENDERS, kind, rec(kind))

    def hc(_c: dict[str, Any], _t: str, _b: str, *, canary: bool = False) -> str:
        seen.append(("hc", canary))
        return "http 200"

    monkeypatch.setitem(ac._CANARY_SENDERS, "hc", hc)
    return seen


def _cfg(tmp_path: Path, kinds: list[str]) -> Path:
    p = tmp_path / "ac.json"
    p.write_text(json.dumps({"channels": [{"kind": k, "topic": "t", "url": "https://h",
                                           "token": "x", "chat_id": "1", "host": "h",
                                           "to": "a@b"} for k in kinds]}), "utf-8")
    return p


def test_a_desk_page_upserts_one_row_and_resolving_clears_it(tmp_path: Path,
                                                             quiet: list[tuple[str, bool]]) -> None:
    led = tmp_path / "data" / "alert_delivery.jsonl"
    path = ac.desk_alerts_path(led)
    assert path == tmp_path / "desks" / "mt5" / "reports" / "DESK_ALERTS.json"
    cfg = _cfg(tmp_path, ["hc"])
    ac.send_all("WARNING Quant desk: brain_down", "m1", config=cfg, ledger=led,
                audience="desk", key="brain_down", source="run_alerts")
    first = ac.load_desk_alerts(path)["brain_down"]
    ac.send_all("WARNING Quant desk: brain_down", "m2", config=cfg, ledger=led,
                audience="desk", key="brain_down", source="run_alerts")
    row = ac.load_desk_alerts(path)["brain_down"]
    assert row["first_seen"] == first["first_seen"] and row["msg"] == "m2"
    assert set(row) == {"key", "title", "msg", "first_seen", "last_seen", "source"}
    assert [r["key"] for r in ac.fresh_desk_alerts(path=path)] == ["brain_down"]
    ac.send_all("RESOLVED Quant desk: brain_down", "cleared", config=cfg, ledger=led,
                audience="desk", key="brain_down", resolved=True)
    assert ac.load_desk_alerts(path) == {}


def test_principal_and_canary_sends_write_no_desk_row(tmp_path: Path,
                                                      quiet: list[tuple[str, bool]]) -> None:
    led = tmp_path / "l.jsonl"
    cfg = _cfg(tmp_path, ["hc"])
    ac.send_all("deadman", "b", config=cfg, ledger=led, audience="principal")
    ac.send_all("canary", "b", config=cfg, ledger=led, audience="desk", canary=True)
    assert not ac.desk_alerts_path(led).exists()


def test_a_stale_row_ages_out_of_the_red(tmp_path: Path) -> None:
    path = tmp_path / "DESK_ALERTS.json"
    ac.record_desk_alert("k", "t", "m", path=path)
    later = datetime.now(tz=UTC) + timedelta(hours=ac.DESK_ALERT_FRESH_H + 1)
    assert ac.fresh_desk_alerts(path=path, now=later) == []
    assert len(ac.fresh_desk_alerts(path=path)) == 1


def test_check_desk_health_goes_red_on_a_fresh_desk_alert(tmp_path: Path) -> None:
    sys.path.insert(0, str(ROOT / "desks" / "mt5" / "scripts"))
    cdh = _load("desks/mt5/scripts/check_desk_health.py", "check_desk_health_alerts")
    path = tmp_path / "DESK_ALERTS.json"

    def run(now: datetime | None = None) -> dict[str, Any]:
        cdh._FINDINGS.clear()
        cdh.check_desk_alerts(path, now)
        rep: dict[str, Any] = cdh.report("x")
        return rep

    assert run()["verdict"] == "OK"                       # absent: nothing recorded
    ac.record_desk_alert("box_heartbeat:unhealthy", "MT5 box unhealthy: disk", "free 1GB",
                         source="box_heartbeat", path=path)
    rep = run()
    assert rep["verdict"] == "PROBLEM"
    assert "box_heartbeat:unhealthy" in rep["findings"][0]["message"]
    assert run(datetime.now(tz=UTC) + timedelta(hours=30))["verdict"] == "OK"
    path.write_text("not json", "utf-8")
    assert run()["verdict"] == "UNMEASURED"


# --- SF2: hc /log for desk, /fail only for principal ---------------------------------------------

def test_send_all_uses_hc_log_for_desk_and_fail_for_principal(
        tmp_path: Path, quiet: list[tuple[str, bool]]) -> None:
    cfg = _cfg(tmp_path, ["hc"])
    ac.send_all("t", "b", config=cfg, ledger=tmp_path / "l.jsonl", audience="desk")
    ac.send_all("t", "b", config=cfg, ledger=tmp_path / "l.jsonl", audience="principal")
    assert quiet == [("hc", True), ("hc", False)]          # canary=True is the /log endpoint


def _capture_urls(monkeypatch: pytest.MonkeyPatch, mod: Any) -> list[str]:
    urls: list[str] = []

    class _R:
        status = 200

        def __enter__(self) -> _R:
            return self

        def __exit__(self, *_a: object) -> None:
            return None

    def urlopen(req: Any, **_k: Any) -> _R:
        urls.append(req.full_url)
        return _R()

    monkeypatch.setattr(mod.urllib.request, "urlopen", urlopen)
    return urls


def test_run_alerts_second_channel_logs_desk_and_fails_principal(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ra = _load("scripts/run_alerts.py", "run_alerts_hc")
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data" / "secrets").mkdir(parents=True)
    (tmp_path / "data" / "secrets" / "heartbeat_url.json").write_text(
        json.dumps({"url": "https://hc-ping.com/u"}), "utf-8")
    urls = _capture_urls(monkeypatch, ra)
    ra._second_channel("x", audience="desk")
    ra._second_channel("x")
    assert urls == ["https://hc-ping.com/u/log", "https://hc-ping.com/u/fail"]


def test_box_heartbeat_keeps_pinging_alive_and_logs_desk_failures(
        monkeypatch: pytest.MonkeyPatch) -> None:
    sys.path.insert(0, str(ROOT / "desks" / "mt5" / "scripts"))
    import box_heartbeat as hb
    urls = _capture_urls(monkeypatch, hb)
    hb._ping("https://hc-ping.com/b", "box OK", False)
    hb._ping("https://hc-ping.com/b", "box FAIL: disk", True)              # desk: alive + log
    hb._ping("https://hc-ping.com/b", "box FAIL: x", True, audience="principal")
    assert urls == ["https://hc-ping.com/b", "https://hc-ping.com/b", "https://hc-ping.com/b/log",
                    "https://hc-ping.com/b/fail"]
    assert frozenset() == hb.PRINCIPAL_CHECKS


# --- SF3: the personal channel's liveness is a desk RED, never a buzz ----------------------------

def test_personal_channel_health_reads_only_real_rows(tmp_path: Path) -> None:
    led = _ledger(tmp_path, ROUTED_ONLY)
    assert ac.personal_channel_health(ledger=led)["stale"]               # routed proves nothing
    led = _ledger(tmp_path, [{"ts": _now_iso(days=1), "channel": "ntfy", "ok": True}])
    assert not ac.personal_channel_health(ledger=led)["stale"]
    led = _ledger(tmp_path, [{"ts": _now_iso(days=8), "channel": "ntfy", "ok": True}])
    assert ac.personal_channel_health(ledger=led)["stale"]
    led = _ledger(tmp_path, [{"ts": _now_iso(days=1), "channel": "ntfy", "ok": True},
                             {"ts": _now_iso(hours=1), "channel": "ntfy", "ok": False}])
    h = ac.personal_channel_health(ledger=led)
    assert h["stale"] and h["failed_since"]


def test_the_canary_raises_and_clears_the_personal_channel_red(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    canary = _load("scripts/run_alert_canary.py", "run_alert_canary_personal")
    monkeypatch.chdir(tmp_path)
    _ledger(tmp_path, ROUTED_ONLY)
    canary.check_personal_channel(ntfy_known=True)
    path = tmp_path / "desks" / "mt5" / "reports" / "DESK_ALERTS.json"
    assert canary.PERSONAL_STALE_KEY in ac.load_desk_alerts(path)
    _ledger(tmp_path, [{"ts": _now_iso(hours=1), "channel": "ntfy", "ok": True}])
    canary.check_personal_channel(ntfy_known=True)
    assert ac.load_desk_alerts(path) == {}
    _ledger(tmp_path, ROUTED_ONLY)
    assert not canary.check_personal_channel(ntfy_known=False)["stale"]   # no ntfy here at all
    assert ac.load_desk_alerts(path) == {}


def test_page_principal_reaches_the_ntfy_json_topic_when_the_registry_has_none(
        tmp_path: Path, quiet: list[tuple[str, bool]]) -> None:
    secret = tmp_path / "ntfy.json"
    secret.write_text(json.dumps({"topic": "quant-x"}), "utf-8")
    led = tmp_path / "l.jsonl"
    res = ac.page_principal("needs you", "b", config=_cfg(tmp_path, ["hc"]), ledger=led,
                            ntfy_secret=secret)
    assert quiet == [("hc", False), ("ntfy", False)] and res["delivered"] == 2
    quiet.clear()
    ac.page_principal("needs you", "b", config=_cfg(tmp_path, ["ntfy"]), ledger=led,
                      ntfy_secret=secret)
    assert quiet == [("ntfy", False)]                      # armed in the registry: sent once


# --- SF4: the dedupe key carries the audience ----------------------------------------------------

def test_run_alerts_dedupe_key_carries_the_audience() -> None:
    ra = _load("scripts/run_alerts.py", "run_alerts_dedupe")
    assert ra._dedupe_key("auth_broken") == "auth_broken@principal"
    assert ra._dedupe_key("brain_down") == "brain_down@desk"
    src = (ROOT / "scripts" / "run_alerts.py").read_text("utf-8")
    assert "state.get(dk, 0)" in src and 'state[key] = now' in src   # ladder clock unchanged


def test_brain_page_stamp_separates_principal_from_desk() -> None:
    be = (ROOT / "ops" / "brain_env.sh").read_text("utf-8")
    fn = be.split("_brain_page() {", 1)[1].split("\n}\n", 1)[0]
    assert "printf 'principal|%s'" in fn and "page_principal(" in fn
    # desk keeps the bare-message hash that libs/ops/lawful._page computes before spawning bash
    assert "stamp=\"$stampdir/$(printf '%s' \"$1\" | sha1sum | cut -c1-16)\"" in fn
    assert '"BRAIN AUTH DOWN, cycle aborted:' in be and '"$_aud"' in be


# --- SF6: the watchdog limit cannot drift below the manifest's cadence ---------------------------

def test_watchdog_limit_covers_the_manifest_cadence() -> None:
    sys.path.insert(0, str(ROOT / "desks" / "mt5" / "scripts"))
    import box_heartbeat as hb
    assert hb.WATCHDOG_CADENCE_MIN == 60.0 / len(hb.STALL_WATCH_TRIGGER_MINUTES) == 30.0
    text = (ROOT / "desks" / "mt5" / "ops" / "box_tasks.manifest").read_text("utf-8")
    m = re.search(r'TASK name="MT5-StallWatch"\s+trigger="every (\d+) minutes"', text)
    assert m, "MT5-StallWatch's trigger is no longer parseable from box_tasks.manifest"
    assert 2 * float(m.group(1)) + 5.0 <= hb.WATCHDOG_MAX_MIN
