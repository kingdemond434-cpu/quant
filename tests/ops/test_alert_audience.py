"""WHO A PAGE IS FOR: only a "principal" page reaches the owner's phone (2026-10-29).

The owner, verbatim: "only notify me on things which need me or else it's confusing; handle rest
n don't tell me". `libs.ops.alert_channels.send_all` therefore takes an `audience`: "principal"
(a human action only he can take) reaches every armed channel; "desk" (ops noise the threads fix)
skips the personal push channels -- ntfy, telegram, email -- and leaves a visible, ok `routed`
ledger row in their place. These tests pin the routing, the ledger row, that a routed row never
counts as a delivery for the silence check, the call-site fence (every `send_all` in the repo
names its audience), and the box heartbeat's page (desk, titled by check, sane watchdog limit).
"""
from __future__ import annotations

import ast
import importlib.util
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from libs.ops import alert_channels as ac

ROOT = Path(__file__).resolve().parents[2]


def _cfg(tmp_path: Path, kinds: list[str]) -> Path:
    chans = {"ntfy": {"kind": "ntfy", "topic": "t"},
             "telegram": {"kind": "telegram", "token": "x", "chat_id": "1"},
             "email": {"kind": "email", "host": "h", "to": "a@b"},
             "webhook": {"kind": "webhook", "url": "https://w"},
             "hc": {"kind": "hc", "url": "https://hc"}}
    p = tmp_path / "alert_channels.json"
    p.write_text(json.dumps({"channels": [chans[k] for k in kinds]}), "utf-8")
    return p


@pytest.fixture
def calls(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    seen: list[str] = []

    def rec(kind: str) -> Any:
        def send(_cfg: dict[str, Any], _t: str, _b: str, **_k: Any) -> str:
            seen.append(kind)
            return "http 200"
        return send

    for kind in ("ntfy", "telegram", "email", "webhook"):
        monkeypatch.setitem(ac._SENDERS, kind, rec(kind))
    monkeypatch.setitem(ac._CANARY_SENDERS, "hc", rec("hc"))
    return seen


ALL = ["ntfy", "telegram", "email", "webhook", "hc"]


def _rows(led: Path) -> list[dict[str, Any]]:
    return [json.loads(x) for x in led.read_text("utf-8").splitlines()]


def test_principal_reaches_every_channel_including_ntfy(tmp_path: Path,
                                                        calls: list[str]) -> None:
    res = ac.send_all("t", "b", config=_cfg(tmp_path, ALL), ledger=tmp_path / "l.jsonl",
                      audience="principal")
    assert calls == ALL
    assert res["delivered"] == 5 and res["routed"] == 0 and res["audience"] == "principal"


def test_desk_never_calls_a_personal_channel(tmp_path: Path, calls: list[str]) -> None:
    res = ac.send_all("t", "b", config=_cfg(tmp_path, ALL), ledger=tmp_path / "l.jsonl",
                      audience="desk")
    assert calls == ["webhook", "hc"]                 # ntfy/telegram/email never called
    assert res["routed"] == 3 and res["audience"] == "desk"
    assert {r["channel"] for r in res["results"] if r.get("routed")} == {
        "ntfy", "telegram", "email"}


def test_a_routed_away_send_leaves_a_visible_ok_ledger_row(tmp_path: Path,
                                                           calls: list[str]) -> None:
    led = tmp_path / "l.jsonl"
    ac.send_all("t", "b", config=_cfg(tmp_path, ["ntfy"]), ledger=led, audience="desk")
    assert calls == []
    (row,) = _rows(led)
    assert row["channel"] == "ntfy" and row["ok"] is True
    assert row["detail"] == "routed: desk audience" and row["routed"] == "desk"


def test_a_routed_row_is_never_counted_as_a_delivery(tmp_path: Path, calls: list[str]) -> None:
    """Otherwise a week of desk pages would hide a dead phone channel from all_silent_since."""
    led = tmp_path / "l.jsonl"
    ac.send_all("t", "b", config=_cfg(tmp_path, ["ntfy"]), ledger=led, audience="desk")
    assert ac.last_success_per_channel(ledger=led) == {}
    assert ac.all_silent_since(24.0, ledger=led)
    ac.send_all("t", "b", config=_cfg(tmp_path, ["ntfy"]), ledger=led, audience="principal")
    assert "ntfy" in ac.last_success_per_channel(ledger=led)


def test_the_default_and_an_unknown_audience_are_principal(tmp_path: Path,
                                                           calls: list[str]) -> None:
    """The safe direction for money: a forgotten or mistyped audience over-pages, never drops."""
    ac.send_all("t", "b", config=_cfg(tmp_path, ["ntfy"]), ledger=tmp_path / "l.jsonl")
    ac.send_all("t", "b", config=_cfg(tmp_path, ["ntfy"]), ledger=tmp_path / "l.jsonl",
                audience="Desk ")
    assert calls == ["ntfy", "ntfy"]


def test_page_principal_is_the_needs_zuck_path(tmp_path: Path, calls: list[str]) -> None:
    res = ac.page_principal("needs you", "b", config=_cfg(tmp_path, ALL),
                            ledger=tmp_path / "l.jsonl")
    assert "ntfy" in calls and res["audience"] == "principal"


def test_desk_failure_semantics_hold(tmp_path: Path, calls: list[str],
                                     monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_a: object, **_k: object) -> str:
        raise OSError("down")

    monkeypatch.setitem(ac._SENDERS, "webhook", boom)
    led = tmp_path / "l.jsonl"
    res = ac.send_all("t", "b", config=_cfg(tmp_path, ["webhook", "ntfy", "hc"]), ledger=led,
                      audience="desk")
    assert calls == ["hc"]                      # the webhook failure stopped nothing
    assert [r["channel"] for r in _rows(led)] == ["webhook", "ntfy", "hc"]
    assert [r["ok"] for r in res["results"]] == [False, True, True]


def test_the_canary_is_desk_and_still_exercises_hc_log(tmp_path: Path,
                                                       monkeypatch: pytest.MonkeyPatch) -> None:
    hc: list[bool] = []
    monkeypatch.setitem(ac._SENDERS, "ntfy", lambda *_a, **_k: pytest.fail("canary hit ntfy"))

    def hc_send(_c: dict[str, Any], _t: str, _b: str, *, canary: bool = False) -> str:
        hc.append(canary)
        return "http 200 log"

    monkeypatch.setitem(ac._CANARY_SENDERS, "hc", hc_send)
    src = (ROOT / "scripts" / "run_alert_canary.py").read_text("utf-8")
    assert 'audience="desk"' in src and "canary=True" in src
    ac.send_all("quant canary", "b", config=_cfg(tmp_path, ["ntfy", "hc"]),
                ledger=tmp_path / "l.jsonl", canary=True, audience="desk")
    assert hc == [True]


# --- THE CALL-SITE FENCE ------------------------------------------------------------------------

#: Byte-pinned canon copies of box watchers (desks/mt5/tests/test_box_watchers_canon.py holds
#: them to the sha256 the box reported). They cannot gain an argument without a re-port from the
#: box, so they ride the PRINCIPAL default: both page about a LIVE account (an E8 fail-open order,
#: an FTMO manual-follow trade the owner places and closes by hand).
CANON_EXEMPT = {
    "desks/mt5/scripts/watchers/e8_window_guard.py": "byte-pinned box canon; live-order guard",
    "desks/mt5/scripts/watchers/ftmo_follow.py": "byte-pinned box canon; owner follows by hand",
}


def _tracked_py() -> list[str]:
    out = subprocess.run(["git", "ls-files", "-z", "--", "*.py"], cwd=ROOT, check=True,
                         capture_output=True).stdout.decode("utf-8", "replace")
    return [p for p in out.split("\0") if p]


def _is_test(rel: str) -> bool:
    parts = Path(rel).parts
    return "tests" in parts or Path(rel).name.startswith("test_")


def _send_all_calls(tree: ast.AST) -> list[ast.Call]:
    return [n for n in ast.walk(tree) if isinstance(n, ast.Call) and (
        (isinstance(n.func, ast.Name) and n.func.id == "send_all")
        or (isinstance(n.func, ast.Attribute) and n.func.attr == "send_all"))]


def _scan() -> tuple[list[str], dict[str, int]]:
    missing: list[str] = []
    exempt_seen: dict[str, int] = {}
    for rel in _tracked_py():
        if _is_test(rel) or not (ROOT / rel).is_file():
            continue
        src = (ROOT / rel).read_text("utf-8", "replace")
        if "send_all" not in src:
            continue
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue
        for call in _send_all_calls(tree):
            kw = {k.arg: k.value for k in call.keywords}
            if rel in CANON_EXEMPT:
                exempt_seen[rel] = exempt_seen.get(rel, 0) + 1
                continue
            val = kw.get("audience")
            if not (isinstance(val, ast.Constant) and val.value in ac.AUDIENCES):
                missing.append(f"{rel}:{call.lineno}")
    return missing, exempt_seen


def test_every_send_all_call_site_names_its_audience() -> None:
    """A page whose audience nobody chose is how the phone filled with noise. Every non-test
    call names "principal" or "desk" as a literal, so the choice is reviewable at the call."""
    missing, exempt_seen = _scan()
    assert not missing, ("send_all call(s) without a literal audience=\"principal\"|\"desk\" "
                         f"(rule: libs/ops/alert_channels.py docstring): {missing}")
    # the exemption list cannot rot: each entry still exists and still calls send_all
    assert set(exempt_seen) == set(CANON_EXEMPT), exempt_seen


def test_the_fence_sees_a_missing_audience(tmp_path: Path) -> None:
    tree = ast.parse("from x import send_all\nsend_all('t', 'b')\n"
                     "alert_channels.send_all('t', 'b', audience='desk')\n")
    calls = _send_all_calls(tree)
    assert len(calls) == 2
    assert [any(k.arg == "audience" for k in c.keywords) for c in calls] == [False, True]


# --- BOX HEARTBEAT ------------------------------------------------------------------------------

sys.path.insert(0, str(ROOT / "desks" / "mt5" / "scripts"))
import box_heartbeat as hb  # noqa: E402


@pytest.mark.parametrize("failing", [["gateway"], ["disk"], ["watchdog"], ["research"],
                                     ["disk", "gateway", "watchdog"]])
def test_box_health_pages_desk_titled_by_check(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                               failing: list[str]) -> None:
    """Box health never needs the owner -- not the gateway, not the disk: a RED a thread fixes.
    The title says WHICH check, so the ledger and the hc page name the organ."""
    sent: list[tuple[str, Any]] = []

    def fake(t: str, b: str, **k: Any) -> dict[str, Any]:
        sent.append((t, k.get("audience")))
        return {"armed": 1, "delivered": 1}

    monkeypatch.setattr(ac, "send_all", fake)
    reading = {"at": "x", "checks": {k: {"fail": True} for k in failing},
               "failing": failing, "verdict": "FAIL"}
    hb.run(out=tmp_path / "o.json", secrets=(tmp_path / "absent.json",), reading=reading)
    assert sent == [(f"MT5 box unhealthy: {', '.join(failing)}", "desk")]


def test_watchdog_limit_is_cadence_plus_a_run_plus_margin(tmp_path: Path,
                                                          monkeypatch: pytest.MonkeyPatch) -> None:
    """stall_watch writes at the END of a 1-28 min run every 30 min, so 30.7 min is healthy."""
    assert hb.WATCHDOG_CADENCE_MIN == 30.0 and hb.WATCHDOG_MAX_MIN == 65.0
    now = datetime(2026, 9, 30, 12, tzinfo=UTC).timestamp()
    w = tmp_path / "stall_watch.json"
    w.write_text("{}")
    monkeypatch.setattr(hb, "WATCHDOG_BEAT", w)
    for age, fails in ((30.7, False), (64.0, False), (66.0, True)):
        os.utime(w, (now - age * 60, now - age * 60))
        r = hb.measure(now, research={"age_days": 0.01}, disk_free_gb=50)
        assert r["checks"]["watchdog"]["fail"] is fails, age


# --- THE VPS PAGER (scripts/run_alerts.py) ------------------------------------------------------

def _run_alerts() -> Any:
    spec = importlib.util.spec_from_file_location("run_alerts_audience",
                                                  ROOT / "scripts" / "run_alerts.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_run_alerts_pushes_ntfy_only_for_keys_that_need_him(monkeypatch: pytest.MonkeyPatch,
                                                            tmp_path: Path) -> None:
    ra = _run_alerts()
    assert ra.audience_for("deadman_latched") == "principal"
    assert ra.audience_for("principal_action_needed") == "principal"
    for key in ("heartbeat_dead", "brain_down", "clock_slots_idle", "recorder_stale",
                "digger_blocked_dataaxis", "research_chain_failed"):
        assert ra.audience_for(key) == "desk", key
    monkeypatch.chdir(tmp_path)
    opened: list[Any] = []

    def urlopen(req: Any, **_k: Any) -> Any:
        opened.append(req)
        pytest.fail("desk page reached the network")

    monkeypatch.setattr(ra.urllib.request, "urlopen", urlopen)
    rows: list[tuple[str, str | None]] = []

    def ledger_ok(_ch: str, d: str, _t: str, *, ok: bool = True,
                  routed: str | None = None) -> None:
        rows.append((d, routed))

    monkeypatch.setattr(ra, "_ledger_ok", ledger_ok)
    monkeypatch.setattr(ra, "_second_channel", lambda _t: None)
    seen: list[Any] = []

    def fake(t: str, b: str, **k: Any) -> dict[str, Any]:
        seen.append(k.get("audience"))
        return {}

    monkeypatch.setattr(ac, "send_all", fake)
    ra._push("topic", "WARNING Quant desk: brain_down", "x", audience="desk")
    assert opened == [] and seen == ["desk"]
    assert rows == [("routed: desk audience", "desk")]
