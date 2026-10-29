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
                audience="desk", key="brain_down", source="run_alerts", public_title=True)
    first = ac.load_desk_alerts(path)["brain_down"]
    ac.send_all("WARNING Quant desk: brain_down", "m2", config=cfg, ledger=led,
                audience="desk", key="brain_down", source="run_alerts", public_title=True)
    row = ac.load_desk_alerts(path)["brain_down"]
    assert row["first_seen"] == first["first_seen"]
    assert set(row) == {"key", "source", "title", "title_sha", "first_seen", "last_seen"}
    assert row["title"] == "WARNING Quant desk: brain_down"
    assert [r["key"] for r in ac.fresh_desk_alerts(path=path)] == ["brain_down"]
    ac.send_all("RESOLVED Quant desk: brain_down", "cleared", config=cfg, ledger=led,
                audience="desk", key="brain_down", resolved=True)
    assert ac.load_desk_alerts(path) == {}


def test_the_published_row_never_holds_the_body_or_a_value_title(
        tmp_path: Path, quiet: list[tuple[str, bool]]) -> None:
    """DESK_ALERTS.json is published: no body ever, the title only as its sha unless the caller
    declares it value-free, and the key -- by default the calling file:function -- is what a
    thread follows back to the source."""
    led = tmp_path / "data" / "alert_delivery.jsonl"
    ac.send_all("gold leg 2.37 lots @ 2411.5 unprotected", "equity 10423.17 on acct 5551234",
                config=_cfg(tmp_path, ["hc"]), ledger=led, audience="desk")
    text = ac.desk_alerts_path(led).read_text("utf-8")
    for leak in ("2.37", "2411", "10423", "5551234", "unprotected"):
        assert leak not in text, leak
    (row,) = ac.load_desk_alerts(ac.desk_alerts_path(led)).values()
    here = "tests/ops/test_desk_alerts.py"
    assert row["key"] == f"{here}:test_the_published_row_never_holds_the_body_or_a_value_title"
    assert row["source"] == here and "title" not in row and len(row["title_sha"]) == 12


def test_principal_and_canary_sends_write_no_desk_row(tmp_path: Path,
                                                      quiet: list[tuple[str, bool]]) -> None:
    led = tmp_path / "l.jsonl"
    cfg = _cfg(tmp_path, ["hc"])
    ac.send_all("deadman", "b", config=cfg, ledger=led, audience="principal")
    ac.send_all("canary", "b", config=cfg, ledger=led, audience="desk", canary=True)
    assert not ac.desk_alerts_path(led).exists()


def test_a_stale_row_ages_out_of_the_red(tmp_path: Path) -> None:
    path = tmp_path / "DESK_ALERTS.json"
    ac.record_desk_alert("k", "t", path=path)
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
    ac.record_desk_alert("box_heartbeat:unhealthy", "MT5 box unhealthy: disk",
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

def test_personal_channel_is_stale_only_when_a_real_send_failed(tmp_path: Path) -> None:
    """Silence is not staleness: a quiet week (or a routed-only ledger) is the normal state."""
    led = _ledger(tmp_path, ROUTED_ONLY)
    assert not ac.personal_channel_health(ledger=led)["stale"]
    led = _ledger(tmp_path, [{"ts": _now_iso(days=30), "channel": "ntfy", "ok": True}])
    assert not ac.personal_channel_health(ledger=led)["stale"]          # a quiet month
    led = _ledger(tmp_path, [{"ts": _now_iso(days=1), "channel": "ntfy", "ok": True},
                             {"ts": _now_iso(hours=1), "channel": "ntfy", "ok": False}])
    h = ac.personal_channel_health(ledger=led)
    assert h["stale"] and h["failed_since"]
    led = _ledger(tmp_path, [{"ts": _now_iso(hours=2), "channel": "ntfy", "ok": False},
                             *ROUTED_ONLY,
                             {"ts": _now_iso(hours=1), "channel": "ntfy", "ok": True}])
    assert not ac.personal_channel_health(ledger=led)["stale"]          # recovered
    led = _ledger(tmp_path, [{"ts": _now_iso(hours=1), "channel": "ntfy", "ok": False}])
    assert ac.personal_channel_health(ledger=led)["stale"]              # never succeeded


def test_the_canary_raises_and_clears_the_personal_channel_red(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    canary = _load("scripts/run_alert_canary.py", "run_alert_canary_personal")
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "desks" / "mt5" / "reports" / "DESK_ALERTS.json"
    _ledger(tmp_path, ROUTED_ONLY)
    canary.check_personal_channel(ntfy_known=True)
    assert not path.exists()                                # quiet is not a RED
    _ledger(tmp_path, [{"ts": _now_iso(hours=1), "channel": "ntfy", "ok": False}])
    canary.check_personal_channel(ntfy_known=True)
    assert canary.PERSONAL_STALE_KEY in ac.load_desk_alerts(path)
    _ledger(tmp_path, [{"ts": _now_iso(hours=1), "channel": "ntfy", "ok": True}])
    canary.check_personal_channel(ntfy_known=True)
    assert ac.load_desk_alerts(path) == {}
    _ledger(tmp_path, [{"ts": _now_iso(hours=1), "channel": "ntfy", "ok": False}])
    assert not canary.check_personal_channel(ntfy_known=False)["stale"]   # no ntfy here at all
    assert ac.load_desk_alerts(path) == {}


def test_page_principal_reaches_the_ntfy_json_topic_when_the_registry_has_none(
        tmp_path: Path, quiet: list[tuple[str, bool]]) -> None:
    secret = tmp_path / "ntfy.json"
    secret.write_text(json.dumps({"topic": "quant-x"}), "utf-8")
    led = tmp_path / "l.jsonl"
    res = ac.page_principal("needs you", "b", config=_cfg(tmp_path, ["hc"]), ledger=led,
                            ntfy_secret=secret, heartbeat=tmp_path / "no_hb.json")
    assert quiet == [("hc", False), ("ntfy", False)] and res["delivered"] == 2
    quiet.clear()
    ac.page_principal("needs you", "b", config=_cfg(tmp_path, ["ntfy"]), ledger=led,
                      ntfy_secret=secret, heartbeat=tmp_path / "no_hb.json")
    assert quiet == [("ntfy", False)]                      # armed in the registry: sent once


def test_page_principal_never_echoes_the_topic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                               capsys: pytest.CaptureFixture[str]) -> None:
    secret = tmp_path / "ntfy.json"
    secret.write_text(json.dumps({"topic": "quant-s3cret"}), "utf-8")

    def boom(_c: dict[str, Any], _t: str, _b: str) -> str:
        raise OSError(f"cannot reach https://ntfy.sh/{_c['topic']}")

    monkeypatch.setitem(ac._SENDERS, "ntfy", boom)
    led = tmp_path / "l.jsonl"
    res = ac.page_principal("needs you", "b", config=tmp_path / "absent.json", ledger=led,
                            ntfy_secret=secret, heartbeat=tmp_path / "no_hb.json")
    out = capsys.readouterr()
    for blob in (json.dumps(res), led.read_text("utf-8"), out.out, out.err):
        assert "s3cret" not in blob
    assert res["results"][-1]["detail"].endswith("<topic>")


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
    assert '_what="BRAIN AUTH DOWN, cycle aborted"' in be and '"$_aud"' in be


# --- SF6: the watchdog limit cannot drift below the manifest's cadence ---------------------------

def test_watchdog_limit_covers_the_manifest_cadence() -> None:
    sys.path.insert(0, str(ROOT / "desks" / "mt5" / "scripts"))
    import box_heartbeat as hb
    assert hb.WATCHDOG_CADENCE_MIN == 60.0 / len(hb.STALL_WATCH_TRIGGER_MINUTES) == 30.0
    text = (ROOT / "desks" / "mt5" / "ops" / "box_tasks.manifest").read_text("utf-8")
    m = re.search(r'TASK name="MT5-StallWatch"\s+trigger="every (\d+) minutes"', text)
    assert m, "MT5-StallWatch's trigger is no longer parseable from box_tasks.manifest"
    assert 2 * float(m.group(1)) + 5.0 <= hb.WATCHDOG_MAX_MIN


# --- AUDIT HOLD on a072c7d7b ---------------------------------------------------------------------
# MF: secret hygiene -- redact FIRST, then cut, then strip a prefix left at the cut edge.

_TOPIC = "quant-Zq7Xv3kPw9Rt2LmNb8Yc4Hd6"


def _leaks(blob: str, secret: str = _TOPIC, floor: int = 3) -> list[str]:
    """Every prefix of the secret (>= floor chars) found anywhere in the blob."""
    return [secret[:n] for n in range(floor, len(secret) + 1) if secret[:n] in blob]


@pytest.mark.parametrize("offset", [150, 165, 170, 175, 180, 185, 190, 195, 199, 205])
def test_page_principal_never_leaks_a_partial_topic_at_the_cut(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, offset: int) -> None:
    """The probe that held a072c7d7b: the topic placed so it STRADDLES the 200-char cut. The old
    code cut first and replaced second, so `replace` never matched and the prefix landed in the
    returned detail and the ledger (offsets 170/175/180 leaked 30/25/20 characters)."""
    secret = tmp_path / "ntfy.json"
    secret.write_text(json.dumps({"topic": _TOPIC}), "utf-8")
    pad = "x" * (offset - len("OSError: "))

    def boom(_c: dict[str, Any], _t: str, _b: str) -> str:
        raise OSError(pad + _c["topic"] + "/tail of the url and more")

    monkeypatch.setitem(ac._SENDERS, "ntfy", boom)
    led = tmp_path / "l.jsonl"
    res = ac.page_principal("needs you", "b", config=tmp_path / "absent.json", ledger=led,
                            ntfy_secret=secret, heartbeat=tmp_path / "no_hb.json")
    detail = res["results"][-1]["detail"]
    for blob in (detail, json.dumps(res), led.read_text("utf-8")):
        assert not _leaks(blob), (offset, _leaks(blob))
    assert len(detail) <= 200 + len("<topic>")


@pytest.mark.parametrize("offset", [170, 175, 180, 195])
def test_send_all_never_leaks_a_registry_credential_at_the_cut(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, offset: int) -> None:
    """The same cut-then-replace shape, on the registry path: a channel's own topic/token/url
    never survives into the detail, whole or as a prefix at the edge."""
    def boom(c: dict[str, Any], _t: str, _b: str) -> str:
        raise OSError("y" * (offset - len("OSError: ")) + str(c["topic"]) + "/more")

    monkeypatch.setitem(ac._SENDERS, "ntfy", boom)
    cfg = tmp_path / "ac.json"
    cfg.write_text(json.dumps({"channels": [{"kind": "ntfy", "topic": _TOPIC}]}), "utf-8")
    led = tmp_path / "l.jsonl"
    res = ac.send_all("t", "b", config=cfg, ledger=led, audience="principal")
    for blob in (json.dumps(res), led.read_text("utf-8")):
        assert not _leaks(blob), (offset, _leaks(blob))


def test_redact_orders_replace_before_cut_and_strips_an_edge_prefix() -> None:
    s = "a" * 190 + _TOPIC + "b" * 40
    out = ac._redact(s, _TOPIC, mask="<T>")
    assert out == ("a" * 190 + "<T>" + "b" * 40)[:200] and not _leaks(out)
    # an upstream that ALREADY cut mid-secret: the trailing prefix is still removed
    pre = ("c" * 50 + _TOPIC)[:60]
    assert ac._redact(pre, _TOPIC, mask="<T>") == "c" * 50 + "<T>"
    assert ac._redact("plain detail", _TOPIC) == "plain detail"
    assert ac._redact("x" * 500)[:200] == "x" * 200 and len(ac._redact("x" * 500)) == 200


# --- SF1: the DESK_ALERTS upsert is locked, uniquely-tmp'd, retried, and its failure surfaced ----

def _mp_writer(args: tuple[str, int, int]) -> None:
    path, proc, n = args
    from libs.ops import alert_channels as acm
    for i in range(n):
        assert acm.record_desk_alert(f"p{proc}:k{i}", "t", path=Path(path)) is None


def test_concurrent_writers_keep_every_row(tmp_path: Path) -> None:
    """The probe: 8 processes x 25 keys left 60/200 rows under the unlocked read-modify-write."""
    import multiprocessing as mp
    path = tmp_path / "DESK_ALERTS.json"
    ctx = mp.get_context("spawn")
    with ctx.Pool(8) as pool:
        pool.map(_mp_writer, [(str(path), p, 25) for p in range(8)])
    rows = ac.load_desk_alerts(path)
    assert len(rows) == 200, len(rows)
    assert not list(tmp_path.glob("*.tmp")), "a temp file was left behind"


def _mp_clear_after(args: tuple[str, int]) -> None:
    path, n = args
    from libs.ops import alert_channels as acm
    for i in range(n):
        acm.record_desk_alert(f"other{i}", "t", path=Path(path))


def test_a_clear_is_not_revived_by_a_concurrent_writer(tmp_path: Path) -> None:
    """A late writer that read before a clear must not write the cleared row back: every
    read-modify-write runs under the lock, so the clear is never overwritten by a stale read."""
    import multiprocessing as mp
    path = tmp_path / "DESK_ALERTS.json"
    ac.record_desk_alert("victim", "t", path=path)
    ctx = mp.get_context("spawn")
    with ctx.Pool(4) as pool:
        res = pool.map_async(_mp_clear_after, [(str(path), 30) for _ in range(4)])
        assert ac.clear_desk_alert("victim", path=path) is None
        res.get(timeout=120)
    rows = ac.load_desk_alerts(path)
    assert "victim" not in rows and len(rows) == 30


def test_replace_is_retried_then_a_persistent_failure_is_surfaced(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        quiet: list[tuple[str, bool]]) -> None:
    path = tmp_path / "DESK_ALERTS.json"
    import os
    real = os.replace
    fails = {"n": 2}

    def flaky(a: Any, b: Any) -> None:
        if fails["n"] > 0:
            fails["n"] -= 1
            raise PermissionError("target open in a reader (Windows)")
        real(a, b)

    monkeypatch.setattr(os, "replace", flaky)
    monkeypatch.setattr(ac, "_REPLACE_PAUSE_S", 0.0)
    assert ac.record_desk_alert("k", "t", path=path) is None      # two refusals, then written
    assert "k" in ac.load_desk_alerts(path)

    def never(a: Any, b: Any) -> None:
        raise PermissionError("still open")

    monkeypatch.setattr(os, "replace", never)
    err = ac.record_desk_alert("k2", "t", path=path)
    assert err and "PermissionError" in err and "k2" not in ac.load_desk_alerts(path)
    assert not list(tmp_path.glob("*.tmp"))
    # through send_all: ledgered as a failed desk_alerts row and returned, never silent
    led = tmp_path / "data" / "alert_delivery.jsonl"
    monkeypatch.setattr(ac, "desk_alerts_path", lambda _l: path)
    res = ac.send_all("t", "b", config=_cfg(tmp_path, ["hc"]), ledger=led, audience="desk",
                      key="k3")
    assert "PermissionError" in res["desk_alert_error"]
    rows = [json.loads(ln) for ln in led.read_text("utf-8").splitlines()]
    assert any(r["channel"] == "desk_alerts" and r["ok"] is False for r in rows)
    assert ac.all_silent_since(24.0, ledger=led) is False         # the hc delivery still counts


# --- SF2: the VPS brain reads the desk rows ------------------------------------------------------

def test_the_vps_brain_brief_carries_fresh_desk_alerts_as_red(tmp_path: Path) -> None:
    sys.path.insert(0, str(ROOT))
    import scripts.carryover_brief as cb
    path = tmp_path / "DESK_ALERTS.json"
    assert "RED 0" in cb.desk_alerts_block(path)                   # absent: nothing recorded
    ac.record_desk_alert("brain_down", "WARNING Quant desk: brain_down", source="run_alerts",
                         public_title=True, path=path)
    ac.record_desk_alert("ops/backup_state.py:send", "Restore drill STALE on box", path=path)
    out = cb.desk_alerts_block(path)
    assert "RED 2" in out and "[RED] brain_down" in out and "ops/backup_state.py:send" in out
    assert "Restore drill" not in out                              # no public title: sha only
    path.write_text("not json", "utf-8")
    assert "UNMEASURED" in cb.desk_alerts_block(path)
    src = (ROOT / "scripts" / "carryover_brief.py").read_text("utf-8")
    assert "print(desk_alerts_block())" in src.split("def main(", 1)[1]
    assert "carryover_brief.py --record" in (ROOT / "ops" / "run_cro_ai.sh").read_text("utf-8")


# --- SF3: recoveries CLEAR the row; information writes none --------------------------------------

def test_recovery_senders_clear_the_desk_row(tmp_path: Path,
                                             monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[dict[str, Any]] = []
    def fake_send(t: str, b: str, **k: Any) -> dict[str, Any]:
        seen.append(k)
        return {"delivered": 1}

    monkeypatch.setattr(ac, "send_all", fake_send)
    sys.path.insert(0, str(ROOT))
    from libs.ops import login_fence as lf
    bs = _load("ops/backup_state.py", "backup_state_resolved")
    cjc = _load("scripts/check_judge_coverage.py", "check_judge_coverage_resolved")
    for make in (lambda r: bs._default_sender(resolved=r),
                 lambda r: lf._default_sender(tmp_path, resolved=r),
                 lambda r: cjc._default_page_sender(tmp_path, resolved=r)):
        make(False)("t", "b")
        make(True)("t", "b")
    assert [(k["audience"], k["resolved"]) for k in seen] == [("desk", False), ("desk", True)] * 3
    # and each page() picks resolved for the recovery verdict only
    assert "_default_sender(resolved=not open_)" in (ROOT / "ops/backup_state.py").read_text()
    assert ('_default_sender(base, resolved=status == "OK")'
            in (ROOT / "libs/ops/login_fence.py").read_text())
    assert ("_default_page_sender(root, resolved=not now_open)"
            in (ROOT / "scripts/check_judge_coverage.py").read_text())


def test_login_fence_recovery_page_clears(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from libs.ops import login_fence as lf
    picked: list[bool] = []

    def fake(_root: Path, *, resolved: bool = False) -> Any:
        picked.append(resolved)
        return lambda t, b: {"delivered": 1}

    monkeypatch.setattr(lf, "_default_sender", fake)
    lf.page({"status": "UNMEASURED"}, tmp_path)
    lf.page({"status": "OK"}, tmp_path)
    assert picked == [False, True]


def test_information_desk_sends_write_no_row_but_still_ledger(
        tmp_path: Path, quiet: list[tuple[str, bool]]) -> None:
    led = tmp_path / "data" / "alert_delivery.jsonl"
    res = ac.send_all("Quant desk: daily digest", "b", config=_cfg(tmp_path, ["hc", "ntfy"]),
                      ledger=led, audience="desk", desk_row=False)
    assert res["delivered"] == 2 and not ac.desk_alerts_path(led).exists()
    assert led.read_text("utf-8").count("\n") == 2
    for rel, needle in (("scripts/page_digest.py", 'audience="desk", desk_row=False'),
                        ("scripts/run_model_upgrade.py", 'audience="desk", desk_row=False')):
        assert needle in (ROOT / rel).read_text("utf-8"), rel
    be = (ROOT / "ops" / "brain_env.sh").read_text("utf-8")
    assert 'desk_row=aud != "info"' in be
    for msg in ("model fallback ACTIVE: primary starved, organs running on $m\" info",
                "cycles continue on metered spend\" info",
                "then ONE retry\" info"):
        assert msg in be, msg


# --- SF4: a box failing for more than a day stays RED --------------------------------------------

def test_box_heartbeat_refreshes_the_row_on_every_failing_run(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sys.path.insert(0, str(ROOT / "desks" / "mt5" / "scripts"))
    import box_heartbeat as hb
    sent: list[str] = []
    refreshed: list[tuple[str, str]] = []
    cleared: list[str] = []
    def fake_send(t: str, b: str, **k: Any) -> dict[str, Any]:
        sent.append(t)
        return {"delivered": 1}

    def fake_record(k: str, t: str, **kw: Any) -> None:
        refreshed.append((k, t))

    def fake_clear(k: str, **kw: Any) -> None:
        cleared.append(k)

    monkeypatch.setattr(ac, "send_all", fake_send)
    monkeypatch.setattr(ac, "record_desk_alert", fake_record)
    monkeypatch.setattr(ac, "clear_desk_alert", fake_clear)
    out = tmp_path / "BOX_HEARTBEAT.json"
    fail = {"at": "x", "checks": {"disk": {"fail": True}}, "failing": ["disk"], "verdict": "FAIL"}
    for _ in range(3):
        hb.run(out=out, secrets=(tmp_path / "absent.json",), reading=dict(fail))
    assert sent == ["MT5 box unhealthy: disk"]                      # paged once
    assert refreshed == [(hb.DESK_ALERT_KEY, "MT5 box unhealthy: disk")] * 2   # row kept fresh
    hb.run(out=out, secrets=(tmp_path / "absent.json",),
           reading={"at": "y", "checks": {}, "failing": [], "verdict": "OK"})
    assert cleared == [hb.DESK_ALERT_KEY]


# --- SF5: credits are principal under their own name; R0360 is a one-time PRINCIPAL_ACTION -------

def test_brain_credit_exhaustion_is_principal_with_an_accurate_title() -> None:
    be = (ROOT / "ops" / "brain_env.sh").read_text("utf-8")
    tail = be.split("# PRINCIPAL: an auth failure is fixed only", 1)[1].split("return 1", 1)[0]
    code = "\n".join(ln for ln in tail.splitlines() if not ln.lstrip().startswith("#"))
    assert '_aud=principal _what="BRAIN AUTH DOWN, cycle aborted"' in code
    credit = code.split('"credit balance is too low|usage credits"', 1)[1].split("elif", 1)[0]
    assert "CREDITS EXHAUSTED (top-up needed)" in credit and "_aud=desk" not in credit
    assert '_aud=desk _what="BRAIN QUOTA LIMIT' in code.split("elif", 1)[1]
    assert '_brain_page "$_what: ' in code and '"$_aud"' in code


def _pa_snippet() -> str:
    be = (ROOT / "ops" / "brain_env.sh").read_text("utf-8")
    fn = be.split("brain_principal_action_once() {", 1)[1].split("\n}\n", 1)[0]
    return fn.split("python3 -c '", 1)[1].split("\n')", 1)[0]


def test_r0360_is_a_one_time_principal_action_entry(tmp_path: Path) -> None:
    import os
    import subprocess
    be = (ROOT / "ops" / "brain_env.sh").read_text("utf-8")
    assert 'brain_principal_action_once "R0360 METERED FALLBACK MISSING:"' in be
    pa = tmp_path / "data" / "PRINCIPAL_ACTION.md"
    pa.parent.mkdir(parents=True)
    pa.write_text("URGENT TIER-3 ASK: something else\n", "utf-8")
    env = {**os.environ, "PYTHONPATH": str(ROOT), "PA_MARKER": "R0360 X:",
           "PA_MSG": "R0360 X: drop the key"}
    for _ in range(3):
        subprocess.run([sys.executable, "-c", _pa_snippet()], cwd=tmp_path, env=env,
                       check=True, timeout=60)
    text = pa.read_text("utf-8")
    assert text.count("R0360 X:") == 1 and text.startswith("URGENT TIER-3 ASK")


# --- SF7: page_principal mirrors to hc /fail when the registry has no hc -------------------------

def test_page_principal_mirrors_to_hc_fail_from_the_heartbeat_url(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, quiet: list[tuple[str, bool]]) -> None:
    hb = tmp_path / "heartbeat_url.json"
    hb.write_text(json.dumps({"url": "https://hc-ping.com/sekrit-uuid-1234"}), "utf-8")
    got: list[dict[str, Any]] = []

    def hc(c: dict[str, Any], _t: str, _b: str) -> str:
        got.append(c)
        raise OSError(f"cannot reach {c['url']}/fail")

    monkeypatch.setitem(ac._SENDERS, "hc", hc)
    led = tmp_path / "l.jsonl"
    res = ac.page_principal("needs you", "b", config=_cfg(tmp_path, ["ntfy"]), ledger=led,
                            ntfy_secret=tmp_path / "no_ntfy.json", heartbeat=hb)
    assert got == [{"kind": "hc", "url": "https://hc-ping.com/sekrit-uuid-1234"}]
    assert [r["channel"] for r in res["results"]] == ["ntfy", "hc"]
    for blob in (json.dumps(res), led.read_text("utf-8")):
        assert "sekrit" not in blob
    got.clear()
    ac.page_principal("needs you", "b", config=_cfg(tmp_path, ["ntfy", "hc"]), ledger=led,
                      ntfy_secret=tmp_path / "no_ntfy.json", heartbeat=hb)
    assert got == [] and ("hc", False) in quiet                    # registry hc: /fail, once
