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
import re
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
#: an FTMO manual-follow trade the owner places and closes by hand). PER CALL SITE: (file, the
#: enclosing function or "<module>", the literal title or "*" when it is not a literal) ->
#: reason, so a NEW call in one of these files is fenced like any other.
CANON_EXEMPT = {
    ("desks/mt5/scripts/watchers/e8_window_guard.py", "<module>",
     "E8 FAIL-OPEN: pinned window placed"):
        "byte-pinned box canon; E8 fail-open order placed on a live account",
    ("desks/mt5/scripts/watchers/e8_window_guard.py", "<module>", "E8 fail-open guard: done"):
        "byte-pinned box canon; the guard's report on live orders it cancelled",
    ("desks/mt5/scripts/watchers/ftmo_follow.py", "page", "*"):
        "byte-pinned box canon; manual-follow trade the owner places and closes by hand",
}


def _tracked_py() -> list[str]:
    out = subprocess.run(["git", "ls-files", "-z", "--", "*.py"], cwd=ROOT, check=True,
                         capture_output=True).stdout.decode("utf-8", "replace")
    return [p for p in out.split("\0") if p]


def _is_test(rel: str) -> bool:
    parts = Path(rel).parts
    return "tests" in parts or Path(rel).name.startswith("test_")


_SENDERS_FENCED = frozenset({"send_all"})


def _send_all_aliases(tree: ast.AST) -> set[str]:
    """Local names bound to send_all: `from x import send_all as y`, `y = mod.send_all`,
    `y = getattr(mod, "send_all")`, `y = send_all`."""
    names = set(_SENDERS_FENCED)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for al in node.names:
                if al.name in _SENDERS_FENCED:
                    names.add(al.asname or al.name)
    changed = True
    while changed:                                  # y = x where x is already an alias
        changed = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and _is_send_all_ref(node.value, names):
                for t in node.targets:
                    if isinstance(t, ast.Name) and t.id not in names:
                        names.add(t.id)
                        changed = True
    return names


def _is_getattr_send_all(node: ast.AST) -> bool:
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id == "getattr" and len(node.args) >= 2
            and isinstance(node.args[1], ast.Constant) and node.args[1].value in _SENDERS_FENCED)


def _is_send_all_ref(node: ast.AST, names: set[str]) -> bool:
    return ((isinstance(node, ast.Name) and node.id in names)
            or (isinstance(node, ast.Attribute) and node.attr in _SENDERS_FENCED)
            or _is_getattr_send_all(node))


def _send_all_calls(tree: ast.AST) -> list[ast.Call]:
    names = _send_all_aliases(tree)
    return [n for n in ast.walk(tree)
            if isinstance(n, ast.Call) and _is_send_all_ref(n.func, names)]


def _scopes(tree: ast.AST) -> dict[int, str]:
    """id(call) -> name of the innermost enclosing def ("<module>" at top level)."""
    out: dict[int, str] = {}

    def walk(node: ast.AST, scope: str) -> None:
        for child in ast.iter_child_nodes(node):
            inner = (child.name if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
                     else scope)
            if isinstance(child, ast.Call):
                out[id(child)] = scope
            walk(child, inner)

    walk(tree, "<module>")
    return out


def _title(call: ast.Call) -> str:
    first = call.args[0] if call.args else None
    return first.value if isinstance(first, ast.Constant) and isinstance(first.value, str) else "*"


def _scan() -> tuple[list[str], set[tuple[str, str, str]]]:
    missing: list[str] = []
    exempt_seen: set[tuple[str, str, str]] = set()
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
        scopes = _scopes(tree)
        for call in _send_all_calls(tree):
            site = (rel, scopes.get(id(call), "<module>"), _title(call))
            if site in CANON_EXEMPT:
                exempt_seen.add(site)
                continue
            val = {k.arg: k.value for k in call.keywords}.get("audience")
            if not (isinstance(val, ast.Constant) and val.value in ac.AUDIENCES):
                missing.append(f"{rel}:{call.lineno}")
    return missing, exempt_seen


def test_every_send_all_call_site_names_its_audience() -> None:
    """A page whose audience nobody chose is how the phone filled with noise. Every non-test
    call names "principal" or "desk" as a literal, so the choice is reviewable at the call --
    including calls through an import alias, a module alias or getattr."""
    missing, exempt_seen = _scan()
    assert not missing, ("send_all call(s) without a literal audience=\"principal\"|\"desk\" "
                         f"(rule: libs/ops/alert_channels.py docstring): {missing}")
    # the exemption list cannot rot: each call site still exists and still calls send_all
    assert exempt_seen == set(CANON_EXEMPT), exempt_seen


def test_the_fence_sees_a_missing_audience(tmp_path: Path) -> None:
    tree = ast.parse("from x import send_all\nsend_all('t', 'b')\n"
                     "alert_channels.send_all('t', 'b', audience='desk')\n")
    calls = _send_all_calls(tree)
    assert len(calls) == 2
    assert [any(k.arg == "audience" for k in c.keywords) for c in calls] == [False, True]


def test_the_fence_sees_through_aliases() -> None:
    src = ("from libs.ops.alert_channels import send_all as page\n"
           "import libs.ops.alert_channels as chan\n"
           "page('t', 'b')\n"
           "chan.send_all('t', 'b')\n"
           "getattr(chan, 'send_all')('t', 'b')\n"
           "fire = getattr(chan, 'send_all')\n"
           "fire('t', 'b')\n"
           "again = chan.send_all\n"
           "twice = again\n"
           "twice('t', 'b', audience='desk')\n"
           "print('t')\n")
    calls = _send_all_calls(ast.parse(src))
    assert sorted(c.lineno for c in calls) == [3, 4, 5, 7, 10]
    tree = ast.parse("def f():\n    send_all('t')\nsend_all('u')\n")
    scopes = _scopes(tree)
    assert sorted(scopes[id(c)] for c in _send_all_calls(tree)) == ["<module>", "f"]


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
    assert ra.audience_for("auth_broken") == "principal"       # only he can `claude setup-token`
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
    second: list[str] = []
    monkeypatch.setattr(ra, "_second_channel",
                        lambda _t, **k: second.append(k.get("audience", "principal")))
    seen: list[Any] = []

    def fake(t: str, b: str, **k: Any) -> dict[str, Any]:
        seen.append(k.get("audience"))
        return {}

    monkeypatch.setattr(ac, "send_all", fake)
    ra._push("topic", "WARNING Quant desk: brain_down", "x", audience="desk")
    assert opened == [] and seen == ["desk"] and second == ["desk"]
    assert rows == [("routed: desk audience", "desk")]


# --- THE DIRECT-POST FENCE (no page reaches ntfy.sh around send_all) ------------------------------

#: Files allowed to hold an ntfy.sh URL literal, each with WHY. Every other non-test file must page
#: through `alert_channels.send_all(..., audience=...)` / `page_principal`, so the audience rule is
#: applied in one place and the phone only rings for "principal".
NTFY_DIRECT_EXEMPT = {
    "libs/ops/alert_channels.py":
        "THE sanctioned sender (_send_ntfy); send_all only reaches it for audience principal",
    "scripts/run_alerts.py":
        "the VPS pager: its principal path keeps the direct push (429 backoff, ntfy.json topic) "
        "and the reply poll; desk keys skip it (test_run_alerts_pushes_ntfy_only_for_keys...)",
    "scripts/run_deadman_switch.py":
        "TIER-3 ruin rail, hash-locked in scripts/check_risk_kernel.KERNEL and isolated from libs/ "
        "by design (tests/scripts/test_deadman_atomic_state.py); every page it sends -- fired, "
        "feed stale with open positions, disarmed on a live book -- is PRINCIPAL anyway",
    "scripts/_retired/publish_dashboard_url.py":
        "retired: not in ops/crontab.manifest, not imported; kept for history only",
}

#: an ntfy.sh URL or bare host as a STRING LITERAL (a URL being built), not prose that mentions it
_NTFY_URL = re.compile(r"^\s*(?:https?://)?ntfy\.sh(?:[/:]|$)")
#: an ntfy.sh host ANYWHERE in a string that is a shell COMMAND (audit SF6, a072c7d7b): the
#: anchored rule above misses f"curl -d {m} https://ntfy.sh/{t}" and os.system("curl ... ntfy.sh")
_NTFY_HOST = r"(?<![\w./-])(?:https?://)?ntfy\.sh(?![\w-])"
_NTFY_CMD = re.compile(r"(?:^|[\s;&|(\"'`])(?:curl|wget|http|Invoke-RestMethod|Invoke-WebRequest|"
                       r"irm|iwr)\b.*?" + _NTFY_HOST)
#: an ntfy host held in a VARIABLE (audit SF4, 7cb207290): `H = "ntfy.sh."`, `f"{p}://ntfy.sh"`,
#: `"//www.NTFY.sh"` -- a URL piece with no whitespace, later joined into a urllib post. Prose
#: assigned to a variable (a HELP line) has spaces and is not a host.
_NTFY_BARE = re.compile(r"(?<![\w-])ntfy\.sh(?![\w-])", re.IGNORECASE)
#: calls that run a STRING as a shell command: any ntfy.sh host in such a string argument is a post
_SHELL_CALLS = frozenset({"system", "popen", "run", "call", "check_call", "check_output",
                          "Popen", "getoutput", "getstatusoutput"})
#: the same, in shell/PowerShell/batch source (comment lines are prose and are skipped). The bare
#: host as a TOKEN, so a variable-held host -- `N=https://ntfy.sh; curl "$N/$t"` -- is caught too.
_NTFY_URL_SHELL = re.compile(_NTFY_HOST)
_SHELL_GLOBS = ("*.sh", "*.bash", "*.ps1", "*.psm1", "*.bat", "*.cmd")


def _tracked(*globs: str) -> list[str]:
    out = subprocess.run(["git", "ls-files", "-z", "--", *globs], cwd=ROOT, check=True,
                         capture_output=True).stdout.decode("utf-8", "replace")
    return [p for p in out.split("\0") if p]


def _ntfy_literals(tree: ast.AST) -> list[int]:
    """Line numbers of string literals that ARE an ntfy.sh URL (f-strings included); docstrings
    are prose and skipped."""
    docs: set[int] = set()
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if isinstance(body, list) and body and isinstance(body[0], ast.Expr) and isinstance(
                body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
            docs.add(id(body[0].value))
    hits: list[int] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.JoinedStr):
            text = "".join(v.value if isinstance(v, ast.Constant) and isinstance(v.value, str)
                           else "\0" for v in node.values)
        elif (isinstance(node, ast.Constant) and isinstance(node.value, str)
              and id(node) not in docs):
            text = node.value
        else:
            continue
        if _NTFY_URL.search(text) or _NTFY_CMD.search(text):
            hits.append(node.lineno)
    for node in ast.walk(tree):                 # a host or URL piece held in a variable
        if not isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign, ast.NamedExpr,
                                 ast.keyword)):
            continue
        value = node.value
        for sub in ast.walk(value) if value is not None else ():
            if isinstance(sub, ast.JoinedStr):
                piece = "".join(v.value if isinstance(v, ast.Constant)
                                and isinstance(v.value, str) else "\0" for v in sub.values)
            elif isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                piece = sub.value
            else:
                continue
            piece = piece.strip()
            if piece and not re.search(r"\s", piece) and _NTFY_BARE.search(piece):
                hits.append(sub.lineno)
    for node in ast.walk(tree):                 # os.system / subprocess(..., shell) strings
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
        if name not in _SHELL_CALLS:
            continue
        for arg in node.args:
            for sub in ast.walk(arg):
                if (isinstance(sub, ast.Constant) and isinstance(sub.value, str)
                        and re.search(_NTFY_HOST, sub.value)):
                    hits.append(node.lineno)
    return sorted(set(hits))


def _shell_hits(src: str) -> list[int]:
    return [i for i, ln in enumerate(src.splitlines(), 1)
            if not ln.lstrip().startswith(("#", "REM ", "rem ", "::"))
            and _NTFY_URL_SHELL.search(ln)]


def _scan_direct() -> tuple[list[str], set[str]]:
    bad: list[str] = []
    exempt_seen: set[str] = set()
    for rel in _tracked_py():
        if _is_test(rel) or not (ROOT / rel).is_file():
            continue
        src = (ROOT / rel).read_text("utf-8", "replace")
        if "ntfy" not in src:
            continue
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue
        lines = _ntfy_literals(tree)
        if lines and rel in NTFY_DIRECT_EXEMPT:
            exempt_seen.add(rel)
        elif lines:
            bad += [f"{rel}:{n}" for n in lines]
    for rel in _tracked(*_SHELL_GLOBS):
        if _is_test(rel) or not (ROOT / rel).is_file():
            continue
        lines = _shell_hits((ROOT / rel).read_text("utf-8", "replace"))
        if lines and rel in NTFY_DIRECT_EXEMPT:
            exempt_seen.add(rel)
        elif lines:
            bad += [f"{rel}:{n}" for n in lines]
    return bad, exempt_seen


def test_nothing_posts_to_ntfy_sh_around_send_all() -> None:
    """A direct ntfy.sh post bypasses the audience rule entirely -- that is how the phone filled
    with digests, model-chain notes and brain plumbing. Page through send_all(audience=...) or
    page_principal; a file that truly cannot goes on NTFY_DIRECT_EXEMPT with its reason."""
    bad, exempt_seen = _scan_direct()
    assert not bad, ("direct ntfy.sh post(s) outside alert_channels.send_all -- route them "
                     f"through send_all(..., audience=\"principal\"|\"desk\"): {bad}")
    # the exemption list cannot rot: each entry still exists and still holds an ntfy.sh URL
    assert exempt_seen == set(NTFY_DIRECT_EXEMPT), exempt_seen
    for rel, why in NTFY_DIRECT_EXEMPT.items():
        assert len(why) > 30, f"{rel}: an exemption needs a reason"


def test_the_direct_post_fence_sees_each_shape() -> None:
    src = ('"""Docstring naming https://ntfy.sh/topic is prose."""\n'
           'import urllib.request\n'
           'urllib.request.Request(f"https://ntfy.sh/{t}", data=b"x")\n'
           'URL = "https://ntfy.sh/" + t\n'
           'HOST = "ntfy.sh"\n'
           'subprocess.run(["curl", "-d", m, f"ntfy.sh/{t}"])\n'
           'print(f"subscribe at: https://ntfy.sh/{t}")\n'
           'HELP = "subscribe in the ntfy app or at https://ntfy.sh/<topic>"\n')
    assert _ntfy_literals(ast.parse(src)) == [3, 4, 5, 6]
    sh = ('# page via ntfy.sh/topic -- a comment is prose\n'
          'curl -d "$1" "https://ntfy.sh/$topic"\n'
          'Invoke-RestMethod -Uri "https://ntfy.sh/$t" -Method Post\n'
          'echo "see docs/send_ntfy.sh.md"\n')
    assert _shell_hits(sh) == [2, 3]


def test_the_direct_post_fence_sees_commands_and_variable_held_hosts() -> None:
    """Audit SF6 (a072c7d7b): the anchored literal rule missed a URL inside a COMMAND string and a
    host held in a shell variable. Each line below is a real post and must be caught."""
    src = ('import os, subprocess\n'
           'os.system(f"curl -d {m} https://ntfy.sh/{t}")\n'                       # 2
           'subprocess.run(f"curl -s -d x https://ntfy.sh/{t}", shell=True)\n'      # 3
           'cmd = f"curl -H Title:x -d {m} ntfy.sh/{t}"\n'                          # 4
           'os.system("wget -q --post-data=x " + "https://ntfy.sh/" + t)\n'         # 5
           'os.popen("N=https://ntfy.sh; curl -d x $N/" + t)\n'                     # 6
           'print(f"subscribe at: https://ntfy.sh/{t}")\n'                          # prose
           'LOG = f"posted via curl earlier; see https://example.com/{t}"\n')       # no host
    assert _ntfy_literals(ast.parse(src)) == [2, 3, 4, 5, 6]
    sh = ('N=https://ntfy.sh; curl -d "$m" "$N/$t"\n'                                # 1
          'NTFY_HOST=ntfy.sh\n'                                                     # 2
          'curl -d "$m" "https://$NTFY_HOST/$t"\n'                         # host in a var
          '$u = "https://ntfy.sh"; Invoke-RestMethod -Uri "$u/$t" -Method Post\n'   # 4
          '# N=https://ntfy.sh  -- a comment is prose\n'
          'source ops/send_ntfy.sh\n')                                              # a filename
    assert _shell_hits(sh) == [1, 2, 4]


# --- THE FORMER DIRECT POSTERS, NOW DESK ---------------------------------------------------------

def _load(rel: str, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    import urllib.request

    def urlopen(*_a: Any, **_k: Any) -> Any:
        pytest.fail("a desk page reached the network directly")

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)


def _fake_send_all(monkeypatch: pytest.MonkeyPatch, result: dict[str, Any] | None = None,
                   exc: Exception | None = None) -> list[tuple[str, str, Any]]:
    seen: list[tuple[str, str, Any]] = []

    def fake(t: str, b: str, **k: Any) -> dict[str, Any]:
        seen.append((t, b, k.get("audience")))
        if exc:
            raise exc
        return result if result is not None else {"armed": 1, "delivered": 1, "routed": 1}

    monkeypatch.setattr(ac, "send_all", fake)
    return seen


def test_the_digest_is_desk_stamps_once_and_never_raises(tmp_path: Path,
                                                        monkeypatch: pytest.MonkeyPatch) -> None:
    pd = _load("scripts/page_digest.py", "page_digest_audience")
    digest = tmp_path / "desk_digest.md"
    digest.write_text("## Book\n- flat\n## Open\n- one item\n", "utf-8")
    monkeypatch.setattr(pd, "DIGEST", digest)
    monkeypatch.setattr(pd, "STAMP", tmp_path / ".last_digest_page")
    monkeypatch.setattr(pd.time, "sleep", lambda _s: None)
    _no_network(monkeypatch)
    seen = _fake_send_all(monkeypatch)
    pd.main()
    pd.main()                                            # same UTC day: a no-op
    assert [(t, a) for t, _b, a in seen] == [("Quant desk: daily digest", "desk")]
    assert "DESK DIGEST" in seen[0][1] and pd.STAMP.exists()


def test_a_failing_digest_retries_once_and_does_not_stamp(tmp_path: Path,
                                                          monkeypatch: pytest.MonkeyPatch) -> None:
    pd = _load("scripts/page_digest.py", "page_digest_audience_fail")
    digest = tmp_path / "desk_digest.md"
    digest.write_text("- something\n", "utf-8")
    monkeypatch.setattr(pd, "DIGEST", digest)
    monkeypatch.setattr(pd, "STAMP", tmp_path / ".last_digest_page")
    monkeypatch.setattr(pd.time, "sleep", lambda _s: None)
    seen = _fake_send_all(monkeypatch, exc=OSError("down"))
    pd.main()                                            # never raises
    assert len(seen) == 2 and not pd.STAMP.exists()
    seen2 = _fake_send_all(monkeypatch, result={"armed": 1, "delivered": 0, "results": []})
    pd.main()
    assert len(seen2) == 2 and not pd.STAMP.exists()
    seen3 = _fake_send_all(monkeypatch, result={"armed": 0, "delivered": 0, "results": []})
    pd.main()                                            # unarmed: one ledgered try, no retry
    assert len(seen3) == 1 and not pd.STAMP.exists()


def test_model_upgrade_and_seats_page_desk_and_swallow_errors(
        monkeypatch: pytest.MonkeyPatch) -> None:
    sys.path.insert(0, str(ROOT))
    rmu = _load("scripts/run_model_upgrade.py", "run_model_upgrade_audience")
    seats = _load("scripts/seats.py", "seats_audience")
    _no_network(monkeypatch)
    seen = _fake_send_all(monkeypatch)
    rmu._page("MODEL CHAIN: 1 rung(s) NOT served")
    seats._page("seat LOST in audit: a -> LOST (no substitute)")
    assert [(t, a) for t, _b, a in seen] == [("MODEL UPGRADE", "desk"), ("SEATS", "desk")]
    _fake_send_all(monkeypatch, exc=RuntimeError("boom"))
    rmu._page("x")                                       # never raises into the caller
    seats._page("x")


def test_panel_spend_line_and_brain_page_are_desk() -> None:
    """Source pins: the panel's alert-line notice and ops/brain_env.sh's _brain_page go through
    send_all as desk (the panel's BUDGET/PURCHASE DECISION still reaches him via
    data/PRINCIPAL_ACTION.md -> run_alerts principal_action_needed)."""
    panel = (ROOT / "scripts" / "run_external_panel.py").read_text("utf-8")
    assert 'send_all("PANEL SPEND"' in panel and 'audience="desk"' in panel
    assert "_principal_page(" in panel and 'marker="BUDGET DECISION:"' in panel
    be = (ROOT / "ops" / "brain_env.sh").read_text("utf-8")
    fn = be.split("_brain_page() {", 1)[1].split("\n}\n", 1)[0]
    code = "\n".join(ln for ln in fn.splitlines() if not ln.lstrip().startswith("#"))
    assert 'audience="desk"' in code and "curl " not in code and "ntfy" not in code
    assert ".brain_page_stamps" in code and "return 0" in code


def test_the_direct_post_fence_sees_a_bare_host_held_in_a_python_variable() -> None:
    """Audit SF4 (7cb207290): a variable holding the bare host (no slash), later joined into a
    urllib post, slipped past the anchored literal rule. Each assignment below is caught; prose
    assigned to a variable (it has spaces) is not."""
    src = ('import urllib.request\n'
           'H = "ntfy.sh."\n'                                                         # 2
           'BASE = f"{scheme}://ntfy.sh"\n'                                           # 3
           'MIRROR: str = "//www.NTFY.sh"\n'                                          # 4
           'cfg = dict(host="ntfy.sh?x=1")\n'                                         # 5
           'urllib.request.Request("https://" + H + "/" + t, data=b"x")\n'
           'HELP = "subscribe in the ntfy app or at ntfy.sh"\n'                       # prose
           'OTHER = "send_ntfy.sh"\n')                                                # a filename
    assert _ntfy_literals(ast.parse(src)) == [2, 3, 4, 5]
    old = re.compile(r"^\s*(?:https?://)?ntfy\.sh(?:[/:]|$)")                  # the v3 rule
    assert not any(old.search(x) for x in ("ntfy.sh.", "\0://ntfy.sh", "//www.NTFY.sh",
                                           "ntfy.sh?x=1"))
