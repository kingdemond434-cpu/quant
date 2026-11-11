"""DESK ALERTS: the box's alarm, delivered to ONE GitHub issue with no new secret.

WHY (BACKLOG 2026-09-30, unblocked 2026-11-11). `box_heartbeat.py` and the silent-organ fence
(N14) already KNEW when the box was unhealthy, and paged through `alert_channels.send_all`, which
has had nothing armed since it was written: it waits on `data/secrets/alert_channels.json`, and
the off-box dead-man waits on `data/secrets/box_heartbeat_url.json`. Both are files only the
principal can create, so every page since 2026-09-30 went nowhere. The principal's rule now is
zero routine human involvement, so this delivers through a credential the box ALREADY holds.

THE ROUTE. One issue in the repo, titled `ISSUE_TITLE`, found by title (or created once, pinned
best-effort), and one comment on it per alert TRANSITION. Two transports, tried in order, both
pre-existing on the box:

    token   GITHUB_TOKEN, read exactly where `GitBoxEnv.ps1` reads it: the process environment,
            then the Machine and User environment in the registry (`setx /M`). Sent only as an
            Authorization header to api.github.com; never printed, logged or written.
    gh      the gh CLI's own stored login, with GITHUB_TOKEN/GH_TOKEN removed from its
            environment so it answers as that login and not as the token that just failed.

The optional channels stay optional: when `alert_channels.json` holds armed channels, every
comment is also sent there through `send_all`. Their absence is recorded, never fatal.

DEDUPE: TRANSITIONS ONLY, A DIGEST AT MOST DAILY. A pager that nags gets muted, and a muted pager
is no pager. Each failing check (and each NEW silent organ, by name) is a key:

  * a key turns RED after `CONFIRM_FAIL` consecutive failing heartbeats (5 minutes apart), so a
    reading that flickers once never posts; a silent organ is already a confirmed hourly census
    transition and turns RED at once;
  * it RECOVERS after `CONFIRM_OK` consecutive clean heartbeats (hysteresis); a silent organ
    recovers only when the census no longer lists it, and an unreadable census never recovers
    one (UNMEASURED is never clean);
  * a comment is posted only when the RED set differs from the set the issue was last told, and
    never sooner than `MIN_GAP_MIN` after the previous comment -- changes inside the gap are
    COALESCED into the next one, never dropped;
  * while anything stays RED, one digest per `DIGEST_EVERY_H` hours; when all is clear, silence.

A failed delivery leaves the told set unchanged, so the transition is retried (no sooner than
`MIN_GAP_MIN`) rather than lost.

WHO GETS NOTIFIED -- READ THIS BEFORE CALLING THE ROUTE ARMED. GitHub never notifies an account
of its own activity. The box's GITHUB_TOKEN pushes as the repository owner (measured 2026-11-11:
every box-state push is by the owner's account), so a comment it writes is RECORDED on the issue
but notifies nobody who is that account. The artifact says so (`github.notifies_owner`) instead of
calling that delivery "sent to the principal". The notifying fix is a comment authored by another
identity -- github-actions[bot] relaying `outbox`, which is why every message is kept there with
a stable id.

THE REPO IS PUBLIC. A comment carries check names, ages, disk free space and organ names only:
never account, position, order or book state, and never a secret or a path under secrets/.

Writes `desks/mt5/reports/DESK_ALERTS.json`: the policy, the RED set, what the issue was last
told, the last alert sent and every route's state. Stdlib only.
"""
from __future__ import annotations

import contextlib
import json
import os
import shutil
import stat
import subprocess
import sys
import urllib.error
import urllib.request
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "desks" / "mt5" / "reports" / "DESK_ALERTS.json"
SILENT_ORGANS = ROOT / "desks" / "mt5" / "reports" / "SILENT_ORGANS.json"
REPO = "kingdemond434-cpu/quant"
OWNER = REPO.split("/", 1)[0]
ISSUE_TITLE = "Desk alerts"
API = "https://api.github.com"
GH_CANDIDATES = (r"C:\Users\Administrator\tools\gh\bin\gh.exe",)
TOKEN_VARS = ("GITHUB_TOKEN",)
STRIP_FOR_GH = ("GITHUB_TOKEN", "GH_TOKEN", "GH_ENTERPRISE_TOKEN", "GITHUB_ENTERPRISE_TOKEN")
TIMEOUT_S = 20.0

CONFIRM_FAIL = 2
CONFIRM_OK = 3
MIN_GAP_MIN = 30.0
DIGEST_EVERY_H = 24.0
OUTBOX_KEEP = 20
SCHEMA = "desk_alerts/1"

#: (status, parsed JSON or None). status 0 = transport failure.
Transport = Callable[[str, str, dict[str, Any] | None], tuple[int, Any]]


# ------------------------------------------------------------------ writing, atomically
def write_json_atomic(out: Path, doc: Any) -> None:
    """Temp file then `os.replace`, so the publisher never copies torn JSON. On Windows a
    READ-ONLY destination refuses the replace (WinError 5) where POSIX would not: clear the bit
    and retry once; a second refusal removes the temp file and raises."""
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.name + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    try:
        os.replace(tmp, out)
    except PermissionError:
        try:
            os.chmod(out, stat.S_IWRITE | stat.S_IREAD)
            os.replace(tmp, out)
        except OSError:
            with contextlib.suppress(OSError):
                tmp.unlink()
            raise


def _load(p: Path) -> dict[str, Any]:
    with contextlib.suppress(OSError, ValueError):
        d = json.loads(p.read_text("utf-8"))
        if isinstance(d, dict):
            return d
    return {}


def _ts(x: Any) -> datetime | None:
    with contextlib.suppress(TypeError, ValueError):
        t = datetime.fromisoformat(str(x))
        return t if t.tzinfo else t.replace(tzinfo=UTC)
    return None


# ------------------------------------------------------------------ the credential
def read_token(env: dict[str, str] | None = None, *, registry: bool = True) -> str | None:
    """GITHUB_TOKEN where the box keeps it (GitBoxEnv.ps1's order). Returned to the caller only."""
    e = os.environ if env is None else env
    for name in TOKEN_VARS:
        v = str(e.get(name) or "").strip()
        if v:
            return v
    if registry and sys.platform == "win32":
        import winreg
        for hive, sub in ((winreg.HKEY_LOCAL_MACHINE,
                           r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"),
                          (winreg.HKEY_CURRENT_USER, "Environment")):
            for name in TOKEN_VARS:
                with contextlib.suppress(OSError), winreg.OpenKey(hive, sub) as k:
                    v = str(winreg.QueryValueEx(k, name)[0] or "").strip()
                    if v:
                        return v
    return None


def token_transport(token: str) -> Transport:
    def call(method: str, path: str, payload: dict[str, Any] | None) -> tuple[int, Any]:
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{API}/{path.lstrip('/')}", data=data, method=method,
            headers={"Authorization": f"Bearer {token}", "User-Agent": "quant-desk-alerts",
                     "Accept": "application/vnd.github+json",
                     "X-GitHub-Api-Version": "2022-11-28",
                     **({"Content-Type": "application/json"} if data else {})})
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
                body = r.read()
                return r.status, (json.loads(body) if body else None)
        except urllib.error.HTTPError as exc:
            return exc.code, None
        except (urllib.error.URLError, OSError, ValueError):
            return 0, None
    return call


def gh_binary() -> str | None:
    return shutil.which("gh") or next((c for c in GH_CANDIDATES if Path(c).exists()), None)


def gh_transport(exe: str) -> Transport:
    env = {k: v for k, v in os.environ.items() if k not in STRIP_FOR_GH}

    def call(method: str, path: str, payload: dict[str, Any] | None) -> tuple[int, Any]:
        cmd = [exe, "api", "-X", method, path.lstrip("/")]
        if payload is not None:
            cmd += ["--input", "-"]
        try:
            r = subprocess.run(cmd, input=None if payload is None else json.dumps(payload),
                               capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=TIMEOUT_S * 2, env=env, check=False)
        except (OSError, subprocess.SubprocessError):
            return 0, None
        if r.returncode != 0:
            return 1, None
        try:
            return 200, (json.loads(r.stdout) if r.stdout.strip() else None)
        except ValueError:
            return 200, None
    return call


def default_routes() -> list[tuple[str, Transport]]:
    routes: list[tuple[str, Transport]] = []
    tok = read_token()
    if tok:
        routes.append(("token", token_transport(tok)))
    exe = gh_binary()
    if exe:
        routes.append(("gh", gh_transport(exe)))
    return routes


# ------------------------------------------------------------------ the issue
def _issue_body() -> str:
    return (f"@{OWNER} this issue is the desk's alarm. The trading box comments here when a "
            "health check turns RED or recovers, and at most once a day while something stays "
            "RED. Nothing else posts here.\n\n"
            "Source: `desks/mt5/scripts/box_heartbeat.py` (every 5 minutes) through "
            "`libs/ops/desk_alerts.py`; state in `desks/mt5/reports/DESK_ALERTS.json`.\n"
            "To quieten it, fix the check; to stop notifications, unsubscribe from this issue.")


def find_or_create_issue(call: Transport, known: dict[str, Any]) -> dict[str, Any]:
    """The issue's number and url. A remembered number is reused; otherwise search by exact
    title (open first), otherwise create it once and try to pin it."""
    if isinstance(known.get("number"), int):
        return known
    st, res = call("GET", f"search/issues?q=repo:{REPO}+is:issue+in:title+%22Desk+alerts%22"
                          "&per_page=20", None)
    if st == 200 and isinstance(res, dict):
        hits = [i for i in (res.get("items") or []) if i.get("title") == ISSUE_TITLE]
        hits.sort(key=lambda i: (i.get("state") != "open", i.get("number") or 0))
        if hits:
            return {"number": hits[0]["number"], "url": hits[0].get("html_url"),
                    "node_id": hits[0].get("node_id"), "pinned": known.get("pinned")}
    st, res = call("POST", f"repos/{REPO}/issues", {"title": ISSUE_TITLE, "body": _issue_body()})
    if st not in (200, 201) or not isinstance(res, dict) or "number" not in res:
        raise RuntimeError(f"issue create refused (http {st})")
    issue = {"number": res["number"], "url": res.get("html_url"), "node_id": res.get("node_id"),
             "pinned": False}
    if issue["node_id"]:
        q = "mutation($id:ID!){pinIssue(input:{issueId:$id}){issue{number}}}"
        pst, pres = call("POST", "graphql", {"query": q, "variables": {"id": issue["node_id"]}})
        issue["pinned"] = bool(pst == 200 and isinstance(pres, dict) and not pres.get("errors"))
    return issue


def _whoami(call: Transport) -> str | None:
    st, res = call("GET", "user", None)
    return str(res.get("login")) if st == 200 and isinstance(res, dict) else None


def post_github(message: dict[str, Any], issue: dict[str, Any],
                routes: list[tuple[str, Transport]]) -> dict[str, Any]:
    """Try each route until one comments. Never raises; never puts a credential in the result."""
    tried: list[dict[str, Any]] = []
    for name, call in routes:
        try:
            iss = find_or_create_issue(call, issue)
            st, res = call("POST", f"repos/{REPO}/issues/{iss['number']}/comments",
                           {"body": message["body"]})
            if st in (200, 201):
                who = _whoami(call)
                return {"ok": True, "route": name, "issue": iss,
                        "comment_url": res.get("html_url") if isinstance(res, dict) else None,
                        "posted_as": who,
                        "notifies_owner": None if who is None else who.lower() != OWNER.lower(),
                        "tried": tried}
            tried.append({"route": name, "http": st})
        except Exception as exc:     # one route's failure never stops the next
            tried.append({"route": name, "error": type(exc).__name__})
    return {"ok": False, "route": None, "issue": issue, "tried": tried,
            "why": "no route" if not routes else "every route refused"}


# ------------------------------------------------------------------ what is RED
def alert_keys(reading: dict[str, Any]) -> dict[str, str]:
    """The heartbeat's failing checks as alert keys with a one-line public detail. A RED silent
    fence is keyed per NEW organ; an unreadable or stale census is its own key."""
    checks = reading.get("checks") or {}
    keys: dict[str, str] = {}
    for k in reading.get("failing") or []:
        c = checks.get(k) or {}
        if k == "silent":
            new = [str(n) for n in (c.get("new_silent") or [])]
            if c.get("fence") == "RED" and new:
                for n in new:
                    keys[f"silent:{n}"] = "organ went silent (N14 census)"
                continue
        detail = {a: b for a, b in c.items() if a not in ("fail", "new_silent")}
        keys[k] = json.dumps(detail, separators=(",", ":"), default=str)[:240]
    return keys


def silent_now(path: Path = SILENT_ORGANS) -> set[str] | None:
    """Every organ the census lists as silent now; None when the census cannot be read."""
    d = _load(path)
    rows = d.get("organs")
    if not isinstance(rows, list):
        return None
    return {str(r.get("organ")) for r in rows if isinstance(r, dict) and r.get("organ")}


def step(state: dict[str, Any], keys: dict[str, str], now: datetime,
         census: set[str] | None) -> dict[str, Any]:
    """Advance the per-key streaks and return the new RED set. Pure."""
    streak: dict[str, dict[str, int]] = {k: dict(v) for k, v in
                                          (state.get("streak") or {}).items()}
    active: dict[str, dict[str, Any]] = {k: dict(v) for k, v in
                                          (state.get("active") or {}).items()}
    at = now.isoformat(timespec="seconds")
    present = dict(keys)
    for k in list(active):
        if k.startswith("silent:") and k not in present:
            organ = k.split(":", 1)[1]
            if census is None or organ in census:     # unread census never clears one
                present[k] = active[k].get("detail", "")
    for k, detail in present.items():
        s = streak.setdefault(k, {"fail": 0, "ok": 0})
        s["fail"], s["ok"] = s["fail"] + 1, 0
        if k in active:
            active[k]["detail"] = detail
        elif s["fail"] >= (1 if k.startswith("silent:") else CONFIRM_FAIL):
            active[k] = {"since": at, "detail": detail}
    for k in list(streak):
        if k in present:
            continue
        if k in active:
            streak[k]["fail"], streak[k]["ok"] = 0, streak[k]["ok"] + 1
            if streak[k]["ok"] >= CONFIRM_OK or k.startswith("silent:"):
                active.pop(k)
                streak.pop(k)
        else:
            streak.pop(k)
    return {"streak": streak, "active": active}


def compose(kind: str, active: dict[str, dict[str, Any]], told: set[str], now: datetime,
            reading: dict[str, Any]) -> dict[str, Any]:
    new = sorted(set(active) - told)
    gone = sorted(told - set(active))
    still = sorted(set(active) & told)
    head = {"RED": "RED", "RECOVERED": "RECOVERED", "ALL_CLEAR": "ALL CLEAR",
            "DIGEST": "Daily digest, still RED"}[kind]
    lines = [f"**{head}** -- MT5 box, {now.strftime('%Y-%m-%d %H:%M')} UTC", ""]
    if new:
        lines.append("New:")
        lines += [f"- `{k}` {active[k].get('detail', '')}" for k in new]
    if gone:
        lines.append("Recovered:")
        lines += [f"- `{k}`" for k in gone]
    if still:
        lines.append("Still RED:" if kind != "DIGEST" else "RED:")
        lines += [f"- `{k}` since {active[k].get('since')}" for k in still]
    ping = (reading.get("ping") or {}).get("status")
    lines += ["", f"<sub>box_heartbeat verdict {reading.get('verdict')}, outside ping {ping}. "
                  f"Transitions only (confirmed {CONFIRM_FAIL} beats RED / {CONFIRM_OK} clean), "
                  f"at most one digest per {DIGEST_EVERY_H:.0f}h.</sub>"]
    body = "\n".join(lines)
    mid = sha256(f"{now.isoformat()}|{kind}|{body}".encode()).hexdigest()[:12]
    return {"id": mid, "at": now.isoformat(timespec="seconds"), "kind": kind,
            "new": new, "recovered": gone, "still": still, "body": body}


def _extra_channels(message: dict[str, Any]) -> dict[str, Any]:
    try:
        from libs.ops import alert_channels as ac
        if not ac.load_channels():
            return {"state": "NOT_ARMED", "why": "no data/secrets/alert_channels.json"}
        res = ac.send_all(f"MT5 box {message['kind']}", message["body"])
        return {"state": "SENT" if res.get("delivered") else "ERROR",
                "armed": res.get("armed"), "delivered": res.get("delivered")}
    except Exception as exc:
        return {"state": "ERROR", "detail": type(exc).__name__}


def dispatch(reading: dict[str, Any], *, out: Path = OUT, census_path: Path = SILENT_ORGANS,
             now: datetime | None = None,
             routes: list[tuple[str, Transport]] | None = None,
             extra: Callable[[dict[str, Any]], dict[str, Any]] = _extra_channels
             ) -> dict[str, Any]:
    """One heartbeat's alerting: advance, maybe post, write the artifact. NEVER RAISES."""
    now = now or datetime.now(UTC)
    prev = _load(out)
    try:
        census = silent_now(census_path)
        st = step(prev, alert_keys(reading), now, census)
        active, told = st["active"], set(prev.get("told") or [])
        last_comment = _ts(prev.get("last_comment_at"))
        last_attempt = _ts(prev.get("last_attempt_at"))
        gap_ok = all(t is None or now - t >= timedelta(minutes=MIN_GAP_MIN)
                     for t in (last_comment, last_attempt))
        kind = None
        if set(active) != told:
            kind = ("RED" if set(active) - told else
                    "ALL_CLEAR" if not active else "RECOVERED")
        elif active and (last_comment is None
                         or now - last_comment >= timedelta(hours=DIGEST_EVERY_H)):
            kind = "DIGEST"
        doc: dict[str, Any] = {
            "schema": SCHEMA, "at": now.isoformat(timespec="seconds"),
            "heartbeat_verdict": reading.get("verdict"), "census_read": census is not None,
            "streak": st["streak"], "active": active, "told": sorted(told),
            "issue": prev.get("issue") or {}, "last_alert": prev.get("last_alert"),
            "last_comment_at": prev.get("last_comment_at"),
            "last_attempt_at": prev.get("last_attempt_at"),
            "github": prev.get("github") or {"state": "UNMEASURED", "why": "nothing sent yet"},
            "extra_channels": prev.get("extra_channels") or {"state": "UNMEASURED"},
            "outbox": list(prev.get("outbox") or [])[-OUTBOX_KEEP:],
            "deadman_ping": (reading.get("ping") or {}).get("status"),
            "policy": {"confirm_fail": CONFIRM_FAIL, "confirm_ok": CONFIRM_OK,
                       "min_gap_min": MIN_GAP_MIN, "digest_every_h": DIGEST_EVERY_H,
                       "issue_title": ISSUE_TITLE, "repo": REPO},
        }
        action = "QUIET" if kind is None else ("DEFERRED" if not gap_ok else "SENT")
        if kind and gap_ok:
            msg = compose(kind, active, told, now, reading)
            doc["last_attempt_at"] = doc["at"]
            # A TEST NEVER POSTS TO THE PUBLIC ISSUE: under pytest the default routes are none.
            rs = (routes if routes is not None else
                  [] if "PYTEST_CURRENT_TEST" in os.environ else default_routes())
            gh = post_github(msg, doc["issue"], rs)
            ex = extra(msg)
            doc["extra_channels"] = ex
            delivered = bool(gh.get("ok")) or ex.get("state") == "SENT"
            doc["github"] = {
                "state": ("SENT" if gh.get("ok") else "UNMEASURED" if not rs else "ERROR"),
                "route": gh.get("route"), "posted_as": gh.get("posted_as"),
                "notifies_owner": gh.get("notifies_owner"), "tried": gh.get("tried"),
                "why": gh.get("why"), "at": doc["at"]}
            if gh.get("issue"):
                doc["issue"] = {k: v for k, v in gh["issue"].items() if k != "node_id"}
            msg["delivered"] = {"github": gh.get("ok"), "comment_url": gh.get("comment_url"),
                                "extra": ex.get("state")}
            doc["outbox"] = (doc["outbox"] + [msg])[-OUTBOX_KEEP:]
            if delivered:
                doc["told"] = sorted(active)
                doc["last_comment_at"] = doc["at"]
                doc["last_alert"] = {k: msg[k] for k in ("id", "at", "kind", "new", "recovered",
                                                         "still")}
                doc["last_alert"]["comment_url"] = gh.get("comment_url")
            else:
                action = "FAILED"
        doc["action"] = action
        doc["pending"] = kind if action in ("DEFERRED", "FAILED") else None
        doc["verdict"] = _verdict(doc)
        write_json_atomic(out, doc)
        return {"status": action, "kind": kind, "verdict": doc["verdict"],
                "issue": (doc["issue"] or {}).get("number")}
    except Exception as exc:
        return {"status": "ERROR", "detail": type(exc).__name__}


def _verdict(doc: dict[str, Any]) -> str:
    """ARMED only when a route has actually delivered and notifies someone other than the
    account that posted; RECORDED when it posted as the owner; UNMEASURED with no route proven."""
    gh = doc.get("github") or {}
    ex = doc.get("extra_channels") or {}
    if ex.get("state") == "SENT" or (gh.get("state") == "SENT" and gh.get("notifies_owner")):
        return "ARMED"
    if gh.get("state") == "SENT":
        return "RECORDED_NOT_NOTIFIED"
    if gh.get("state") == "ERROR":
        return "ERROR"
    return "UNMEASURED"
