"""The second alert channel (gap #38) must be ARMED, and its canary must not cry wolf.

ntfy has been the desk's only page route twice over a fatal window: quota exhaustion 07-11 -> 07-16
and a latin-1 header encode on 07-19 that killed 39/39 pushes for 29h across a live dead-man fire.
The registry that was built to fix that has sat unarmed ever since, "owed to a human step", while
healthchecks.io -- an independent provider needing no new credential -- was already configured on
the box for the liveness heartbeat.

Two things these tests pin down, because both are ways the fix could be worse than the gap:
  * a REAL alert must hit /fail (which notifies) and a CANARY must hit /log (which does not). A
    synthetic probe every 6h that reads as "the box is dead" trains the principal to ignore the
    one signal that means the machine is gone.
  * a channel that cannot resolve its URL must be recorded as a FAILED delivery, never raise into
    the alert path and never silently look like success.
"""

from __future__ import annotations

import json
from pathlib import Path

from libs.ops import alert_channels as ac


class _Resp:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _capture(monkeypatch) -> list[str]:
    """Record the URL every send would hit, without touching the network."""
    seen: list[str] = []

    def fake(req, timeout=None):
        seen.append(req.full_url)
        return _Resp()

    monkeypatch.setattr(ac.urllib.request, "urlopen", fake)
    return seen


def _armed(tmp_path: Path, channels: list[dict]) -> Path:
    cfg = tmp_path / "alert_channels.json"
    cfg.write_text(json.dumps({"channels": channels}), "utf-8")
    return cfg


def test_a_real_alert_hits_the_notifying_endpoint(tmp_path, monkeypatch) -> None:
    seen = _capture(monkeypatch)
    hb = tmp_path / "heartbeat_url.json"
    hb.write_text(json.dumps({"url": "https://hc-ping.com/abc"}), "utf-8")
    monkeypatch.setattr(ac, "_HEARTBEAT", hb)
    out = ac.send_all("t", "b", config=_armed(tmp_path, [{"kind": "hc"}]),
                      ledger=tmp_path / "led.jsonl")
    assert out["armed"] == 1 and out["delivered"] == 1
    assert seen == ["https://hc-ping.com/abc/fail"]


def test_the_canary_uses_the_non_notifying_endpoint(tmp_path, monkeypatch) -> None:
    seen = _capture(monkeypatch)
    hb = tmp_path / "heartbeat_url.json"
    hb.write_text(json.dumps({"url": "https://hc-ping.com/abc"}), "utf-8")
    monkeypatch.setattr(ac, "_HEARTBEAT", hb)
    ac.send_all("t", "b", config=_armed(tmp_path, [{"kind": "hc"}]),
                ledger=tmp_path / "led.jsonl", canary=True)
    assert seen == ["https://hc-ping.com/abc/log"]


def test_explicit_url_beats_the_heartbeat_file(tmp_path, monkeypatch) -> None:
    seen = _capture(monkeypatch)
    monkeypatch.setattr(ac, "_HEARTBEAT", tmp_path / "absent.json")
    ac.send_all("t", "b",
                config=_armed(tmp_path, [{"kind": "hc", "url": "https://hc-ping.com/zzz/"}]),
                ledger=tmp_path / "led.jsonl")
    assert seen == ["https://hc-ping.com/zzz/fail"]


def test_delivery_is_written_to_the_ledger(tmp_path, monkeypatch) -> None:
    # all_silent_since() is the only instrument that can say "nothing got out anywhere"; it is
    # blind to any channel that does not record.
    _capture(monkeypatch)
    hb = tmp_path / "heartbeat_url.json"
    hb.write_text(json.dumps({"url": "https://hc-ping.com/abc"}), "utf-8")
    monkeypatch.setattr(ac, "_HEARTBEAT", hb)
    led = tmp_path / "led.jsonl"
    ac.send_all("t", "b", config=_armed(tmp_path, [{"kind": "hc"}]), ledger=led)
    rows = [json.loads(x) for x in led.read_text("utf-8").splitlines()]
    assert [r["channel"] for r in rows] == ["hc"] and rows[0]["ok"] is True
    assert not ac.all_silent_since(24.0, ledger=led)


def test_unresolvable_url_is_a_recorded_failure_not_an_exception(tmp_path, monkeypatch) -> None:
    _capture(monkeypatch)
    monkeypatch.setattr(ac, "_HEARTBEAT", tmp_path / "absent.json")
    led = tmp_path / "led.jsonl"
    out = ac.send_all("t", "b", config=_armed(tmp_path, [{"kind": "hc"}]), ledger=led)
    assert out["armed"] == 1 and out["delivered"] == 0
    rows = [json.loads(x) for x in led.read_text("utf-8").splitlines()]
    assert rows[0]["ok"] is False
    assert ac.all_silent_since(24.0, ledger=led)


def test_a_corrupt_heartbeat_file_does_not_escape_send_all(tmp_path, monkeypatch) -> None:
    _capture(monkeypatch)
    hb = tmp_path / "heartbeat_url.json"
    hb.write_text("{not json", "utf-8")
    monkeypatch.setattr(ac, "_HEARTBEAT", hb)
    out = ac.send_all("t", "b", config=_armed(tmp_path, [{"kind": "hc"}]),
                      ledger=tmp_path / "led.jsonl")
    assert out["delivered"] == 0


def test_canary_flag_does_not_break_channels_that_ignore_it(tmp_path, monkeypatch) -> None:
    # Only canary-aware kinds take the kwarg; passing it to the rest would be a TypeError.
    seen = _capture(monkeypatch)
    ac.send_all("t", "b",
                config=_armed(tmp_path, [{"kind": "webhook", "url": "https://example.invalid/h"}]),
                ledger=tmp_path / "led.jsonl", canary=True)
    assert seen == ["https://example.invalid/h"]


def test_the_shipped_config_arms_at_least_one_channel() -> None:
    """The point of the row: an unarmed registry is a no-op dressed as a safety net."""
    cfg = Path("data/secrets/alert_channels.json")
    if not cfg.exists():
        return                                 # gitignored; absent in a fresh clone / CI
    assert ac.load_channels(cfg), "alert_channels.json present but arms nothing"
