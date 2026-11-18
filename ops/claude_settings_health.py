#!/usr/bin/env python
"""IS THE BOX'S CLAUDE CODE SETTINGS FILE EVEN BEING READ? -- a read-only check (2026-11-13).

THE FAILURE THIS EXISTS FOR. On 2026-11-13 the box's
`C:\\Users\\Administrator\\.claude\\settings.json`
was found missing its leading `{`. Claude Code could not parse it, so the permission mode zuck had
set there (the "no prompt" setting) was never loaded, and every Remote Control session on the box
kept asking for approvals. Nothing reported it: the file existed, looked right at a glance, and
only a human reading it character by character found the missing brace.

WHAT THIS DOES. For every Claude Code settings file that can shape a session on this host -- each
user profile's `.claude\\settings.json` and `settings.local.json`, the machine-wide managed
settings,
and the bridge checkout's project `.claude\\settings*.json` -- it reports:

  OK            parses as a JSON object; also reports `permissions.defaultMode` (a mode name, not
                a secret), how many allow / deny / ask rules there are, and the top-level KEY NAMES
  INVALID_JSON  does not parse: line, column, the parser's message, and a DIAGNOSIS when one exact
                repair would make it parse (MISSING_LEADING_BRACE, MISSING_TRAILING_BRACE,
                UTF8_BOM, TRAILING_COMMA); UNKNOWN otherwise
  NOT_OBJECT    parses, but is not a JSON object (Claude Code ignores it)
  UNREADABLE    exists but cannot be read by this process
  (absent files are listed under `absent`, never as a fault: most of them are optional)

and, when the bridge watchdog's heartbeat says when the Remote Control server started, whether a
settings file changed AFTER that start (NEEDS_RC_RESTART): a permission mode is fixed when a
session starts, so a repaired file only takes effect for sessions started after the repair.

WHAT IT NEVER DOES. It never writes, moves or repairs a settings file -- an AI never edits its own
permission settings (project hard rule); the repair is
`ops\\bridge\\Repair-ClaudeSettings.ps1`, which
only a person runs. It never prints a VALUE from a settings file other than the permission mode
name and rule counts: an `env` block or an `apiKeyHelper` may hold something sensitive, so only
key names leave this process.

WHAT IS PUBLISHED. The full report (paths, positions, parser messages) is written to root
`data/` (gitignored), on the box only. `ops/process_health.py` (published in box state, and the
repository is public) carries only `publishable()`: status, count, and per broken file its scope
category, file name, verdict and diagnosis -- no path, user name, line, column or message.

WIRED INTO `ops/process_health.py` (the box's process board, published in box state): an
INVALID_JSON / NOT_OBJECT / UNREADABLE user or managed file makes the board ATTENTION, so a broken
settings file is seen within one process-health pass instead of by a human, and the request
"fix the box settings.json" never has to recur silently.

    python ops/claude_settings_health.py            # one line per file
    python ops/claude_settings_health.py --json     # the report
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
#: The FULL report (paths, positions, parser messages) stays on this host: root data/ is
#: gitignored, so it is never published. Only `publishable()` leaves the box.
OUT = ROOT / "data" / "claude_settings_health.json"
#: The only keys the published projection carries (pinned by a test; audit 2026-11-13 MF1/MF2).
PUBLISHED_KEYS = ("status", "n_files", "faults", "repair")
PUBLISHED_FAULT_KEYS = ("scope", "file", "verdict", "diagnosis")

#: Files Claude Code reads per user profile (user scope).
USER_FILES = ("settings.json", "settings.local.json")
#: Machine-wide managed settings on Windows (both locations Claude Code has used).
MANAGED_FILES = (
    Path("C:/Program Files/ClaudeCode/managed-settings.json"),
    Path("C:/ProgramData/ClaudeCode/managed-settings.json"),
)
#: The bridge checkout whose project settings the Remote Control sessions load.
BRIDGE_CHECKOUT = Path("C:/opt/bridge/quant")
BRIDGE_HEARTBEAT = Path("C:/ProgramData/ClaudeBridge/logs/bridge_watchdog.json")

#: Verdicts that are a definite fault on a file that shapes every session (user or managed scope).
FAULTS = frozenset({"INVALID_JSON", "NOT_OBJECT", "UNREADABLE"})


def _loads_object(text: str) -> Any:
    return json.loads(text)


def diagnose(text: str) -> str:
    """The ONE exact repair that would make `text` parse as a JSON object, else UNKNOWN.

    Each candidate changes the bytes in exactly one way; it is reported only if that alone yields
    a JSON object. The repair script applies only these same named repairs."""
    stripped = text.lstrip("\ufeff")
    if stripped != text:
        try:
            if isinstance(json.loads(stripped), dict):
                return "UTF8_BOM"
        except ValueError:
            pass
    body = stripped.strip()
    candidates = (
        ("MISSING_LEADING_BRACE", "{" + body),
        ("MISSING_TRAILING_BRACE", body + "}"),
    )
    for name, cand in candidates:
        try:
            if isinstance(json.loads(cand), dict):
                return name
        except ValueError:
            continue
    # a single trailing comma before the closing brace / bracket
    import re

    fixed, n = re.subn(r",(\s*[}\]])", r"\1", body)
    if n == 1:
        try:
            if isinstance(json.loads(fixed), dict):
                return "TRAILING_COMMA"
        except ValueError:
            pass
    return "UNKNOWN"


def inspect_file(path: Path, scope: str) -> dict[str, Any]:
    """One settings file's verdict. Never returns a value from the file except the permission
    mode name and rule counts."""
    row: dict[str, Any] = {"path": str(path), "scope": scope}
    try:
        st = path.stat()
        raw = path.read_bytes()
    except OSError as exc:
        row.update(verdict="UNREADABLE", why=type(exc).__name__)
        return row
    row["size"] = st.st_size
    row["modified_at"] = datetime.fromtimestamp(st.st_mtime, UTC).isoformat(timespec="seconds")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        row.update(
            verdict="INVALID_JSON", why=f"not UTF-8 at byte {exc.start}", diagnosis="UNKNOWN"
        )
        return row
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        row.update(
            verdict="INVALID_JSON",
            line=exc.lineno,
            column=exc.colno,
            why=exc.msg,
            diagnosis=diagnose(text),
        )
        return row
    if not isinstance(doc, dict):
        row.update(verdict="NOT_OBJECT", why=f"top level is {type(doc).__name__}")
        return row
    raw_perms = doc.get("permissions")
    perms: dict[str, Any] = raw_perms if isinstance(raw_perms, dict) else {}
    mode = perms.get("defaultMode")

    def _n(key: str) -> int:
        v = perms.get(key)
        return len(v) if isinstance(v, list) else 0

    row.update(
        verdict="OK",
        keys=sorted(str(k) for k in doc),
        default_mode=mode if isinstance(mode, str) else None,
        n_allow=_n("allow"),
        n_deny=_n("deny"),
        n_ask=_n("ask"),
    )
    return row


def candidate_files(
    users_root: Path, managed: tuple[Path, ...], checkout: Path
) -> list[tuple[Path, str]]:
    out: list[tuple[Path, str]] = []
    try:
        profiles = sorted(p for p in users_root.iterdir() if p.is_dir())
    except OSError:
        profiles = []
    for prof in profiles:
        for name in USER_FILES:
            out.append((prof / ".claude" / name, f"user:{prof.name}"))
    for m in managed:
        out.append((m, "managed"))
    for name in USER_FILES:
        out.append((checkout / ".claude" / name, "project:bridge"))
    return out


def _server_started_at(heartbeat: Path) -> datetime | None:
    try:
        hb = json.loads(heartbeat.read_text(encoding="utf-8-sig"))
        s = hb.get("server_started_at")
        return datetime.fromisoformat(str(s).replace("Z", "+00:00")) if s else None
    except (OSError, ValueError, AttributeError):
        return None


def check(
    users_root: Path | None = None,
    managed: tuple[Path, ...] = MANAGED_FILES,
    checkout: Path = BRIDGE_CHECKOUT,
    heartbeat: Path = BRIDGE_HEARTBEAT,
) -> dict[str, Any]:
    if users_root is None:
        users_root = (
            Path(os.environ.get("SYSTEMDRIVE", "C:") + "/Users")
            if os.name == "nt"
            else Path.home().parent
        )
    rows: list[dict[str, Any]] = []
    absent: list[str] = []
    for path, scope in candidate_files(users_root, managed, checkout):
        if not path.exists():
            absent.append(str(path))
            continue
        rows.append(inspect_file(path, scope))
    started = _server_started_at(heartbeat)
    if started is not None:
        for r in rows:
            m = r.get("modified_at")
            if m and datetime.fromisoformat(m) > started:
                r["changed_after_rc_start"] = True
    faults = [r for r in rows if r["verdict"] in FAULTS and not r["scope"].startswith("project")]
    project_faults = [
        r for r in rows if r["verdict"] in FAULTS and r["scope"].startswith("project")
    ]
    restart = [r for r in rows if r.get("changed_after_rc_start") and r["verdict"] == "OK"]
    if faults or project_faults:
        status = "BROKEN"
    elif restart:
        status = "NEEDS_RC_RESTART"
    elif not rows:
        status = "NO_SETTINGS"
    else:
        status = "OK"
    return {
        "at": datetime.now(UTC).isoformat(timespec="seconds"),
        "status": status,
        "n_files": len(rows),
        "faults": [r["path"] for r in faults + project_faults],
        "rc_server_started_at": started.isoformat() if started else None,
        "repair": (
            "a person runs ops\\bridge\\Repair-ClaudeSettings.ps1 (it applies only the "
            "diagnosed repair, keeps a backup), then restarts Remote Control"
            if faults or project_faults
            else None
        ),
        "files": rows,
        "absent": absent,
    }


def publishable(rep: dict[str, Any]) -> dict[str, Any]:
    """What may leave the box (process_health.json is published, and the repository is public):
    the status, the count, and per broken file only its scope CATEGORY (user / managed / project,
    never the profile name), its file name, verdict and diagnosis. Never a path, a user name, a
    line, a column or a parser message (audit 2026-11-13 MF1, MF2): kept in OUT, on the box."""
    faults = [
        {
            "scope": str(r.get("scope") or "").split(":", 1)[0],
            "file": Path(str(r.get("path") or "")).name,
            "verdict": r.get("verdict"),
            "diagnosis": r.get("diagnosis"),
        }
        for r in rep.get("files") or []
        if r.get("verdict") in FAULTS
    ]
    return {
        "status": rep.get("status"),
        "n_files": rep.get("n_files"),
        "faults": faults,
        "repair": rep.get("repair"),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--no-write", action="store_true", help="do not write the report artifact")
    a = ap.parse_args(argv)
    rep = check()
    if not a.no_write:
        try:
            OUT.parent.mkdir(parents=True, exist_ok=True)
            OUT.write_text(json.dumps(rep, indent=1), encoding="utf-8")
        except OSError:
            pass
    if a.json:
        print(json.dumps(rep, indent=1))
    else:
        print(f"claude settings: {rep['status']} ({rep['n_files']} files)")
        for r in rep["files"]:
            extra = (
                f" mode={r.get('default_mode')} allow={r.get('n_allow')}"
                if r["verdict"] == "OK"
                else f" line={r.get('line')} col={r.get('column')} diagnosis={r.get('diagnosis')}"
            )
            print(f"  {r['verdict']:<13} {r['scope']:<22} {r['path']}{extra}")
    return 0 if rep["status"] in ("OK", "NO_SETTINGS") else 1


if __name__ == "__main__":
    sys.exit(main())
