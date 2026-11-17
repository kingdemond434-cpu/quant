"""Apply merged, Auditor-CLEARed box installers as SYSTEM, so nobody runs them by hand.

zuck (2026-11-17 19:56Z) does not want to do one-time admin installs on the box any more. The
SYSTEM adopter (MT5-AdoptRelease -> Adopt-And-Seal.ps1) already dot-sources
ops/box/box_selfheal.ps1 on every adoption; its INSTALLER APPLY step runs this file on the tree it
just adopted, which is a sealed release of Auditor-CLEARed code.

What it runs, and only that:
  - rows of ops/box/auto_installers.json, a reviewed list; an installer not listed never runs;
  - each row once per installer VERSION: the sha256 of its bytes is recorded in an append-only
    ledger, and a version that already exited 0 is never run again;
  - `.ps1` files under the allowed roots, tracked by git, with switch-only arguments;
  - never a credential or auth installer: a row whose installer text names auto-logon, gh auth,
    credentials, secure strings, passwords, LSA secrets, the authority key or data\\secrets is
    refused (those stay zuck's);
  - `desk_user` rows only when the installer declares a -User parameter; the account is the
    auto-logon account, read from Winlogon, never typed and never a password.

A refused or failed row is logged in the ledger and never stops the seal. --plan prints what
--apply would do and runs nothing.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "ops" / "box" / "auto_installers.json"
ALLOWED_ROOTS = ("desks/mt5/scripts/", "ops/box/", "ops/bridge/")
PRINCIPALS = frozenset({"system", "desk_user"})
TIMEOUT_S = 300
_SWITCH = re.compile(r"^-[A-Za-z][A-Za-z0-9]*$")
#: Credential and auth work stays zuck's (2026-11-17 19:56Z: "codes and passwords ... i dont want
#: these too" is about new keys; the applier never touches them).
CREDENTIAL = re.compile(
    r"autologon|gh\s+auth|get-credential|convertto-securestring|-password\b|lsastoreprivatedata"
    r"|credential\s*manager|cmdkey|authority\\key|data[\\/]secrets|\.key\b",
    re.IGNORECASE,
)
_USER_PARAM = re.compile(r"param\s*\((?:[^()]|\([^()]*\))*\$User\b", re.IGNORECASE | re.DOTALL)


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _tracked(rel: str) -> bool:
    r = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "--error-unmatch", "--", rel],
        capture_output=True,
        check=False,
    )
    return r.returncode == 0


def load_rows(manifest: Path = MANIFEST) -> list[dict[str, Any]]:
    try:
        doc = json.loads(manifest.read_text("utf-8"))
    except (OSError, ValueError):
        return []
    rows = doc.get("installers") if isinstance(doc, dict) else None
    return [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else []


def refusal(row: dict[str, Any], root: Path = ROOT, *, tracked: bool | None = None) -> str | None:
    """Why `row` may not run, or None."""
    rel = row.get("path")
    if not isinstance(rel, str) or not rel.endswith(".ps1") or ".." in rel.split("/"):
        return "path is not a repo-relative .ps1"
    if not rel.startswith(ALLOWED_ROOTS):
        return f"path is outside {', '.join(ALLOWED_ROOTS)}"
    args = row.get("args", [])
    if not isinstance(args, list) or not all(isinstance(a, str) and _SWITCH.match(a) for a in args):
        return "args must be switches only (-Name)"
    principal = row.get("principal")
    if principal not in PRINCIPALS:
        return f"principal must be one of {sorted(PRINCIPALS)}"
    f = root / rel
    if not f.is_file():
        return "installer is absent"
    if not (tracked if tracked is not None else _tracked(rel)):
        return "installer is not tracked by git"
    text = f.read_text("utf-8", errors="replace")
    hit = CREDENTIAL.search(text)
    if hit:
        return f"names credential or auth work ({hit.group(0)!r}); that stays zuck's"
    if principal == "desk_user" and not _USER_PARAM.search(text):
        return "desk_user installer declares no -User parameter"
    return None


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def applied(ledger: Path) -> set[tuple[str, str]]:
    """(path, sha) pairs that already exited 0."""
    done: set[tuple[str, str]] = set()
    try:
        lines = ledger.read_text("utf-8", errors="replace").splitlines()
    except OSError:
        return done
    for line in lines:
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if isinstance(r, dict) and r.get("action") == "applied" and r.get("rc") == 0:
            done.add((str(r.get("path")), str(r.get("sha256"))))
    return done


def desk_user() -> str | None:
    """The auto-logon account (DOMAIN\\name) from Winlogon; None off Windows or when unset."""
    if sys.platform != "win32":
        return None
    try:
        import winreg

        key = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon"
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key) as k:
            name = str(winreg.QueryValueEx(k, "DefaultUserName")[0]).strip()
            try:
                dom = str(winreg.QueryValueEx(k, "DefaultDomainName")[0]).strip()
            except OSError:
                dom = ""
    except OSError:
        return None
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,64}", name or ""):
        return None
    if dom and not re.fullmatch(r"[A-Za-z0-9._-]{1,64}", dom):
        return None
    return f"{dom}\\{name}" if dom else name


def plan(ledger: Path, root: Path = ROOT, manifest: Path = MANIFEST) -> list[dict[str, Any]]:
    """One decision per manifest row: run, skip (already applied) or refuse."""
    done = applied(ledger)
    out: list[dict[str, Any]] = []
    for row in load_rows(manifest):
        rel = str(row.get("path"))
        why = refusal(row, root)
        if why:
            out.append({"path": rel, "action": "refused", "why": why})
            continue
        digest = sha256(root / rel)
        if (rel, digest) in done:
            out.append({"path": rel, "action": "skip", "sha256": digest, "why": "applied"})
            continue
        out.append(
            {
                "path": rel,
                "action": "run",
                "sha256": digest,
                "args": list(row.get("args", [])),
                "principal": row["principal"],
            }
        )
    return out


def _append(ledger: Path, row: dict[str, Any]) -> None:
    row = {"at": _now(), **row}
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with ledger.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, sort_keys=True) + "\n")


def apply(ledger: Path, root: Path = ROOT, manifest: Path = MANIFEST) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for step in plan(ledger, root, manifest):
        if step["action"] == "skip":
            results.append(step)
            continue
        if step["action"] == "refused":
            _append(ledger, step)
            results.append(step)
            continue
        argv = [
            "powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
            "-File", str(root / step["path"]), *step["args"],
        ]  # fmt: skip
        if step["principal"] == "desk_user":
            user = desk_user()
            if not user:
                row = {**step, "action": "refused", "why": "no auto-logon account to install for"}
                _append(ledger, row)
                results.append(row)
                continue
            argv += ["-User", user]
        t0 = time.monotonic()
        try:
            r = subprocess.run(argv, capture_output=True, text=True, timeout=TIMEOUT_S, check=False)
            rc: int | None = r.returncode
            tail = ((r.stdout or "") + (r.stderr or "")).strip()[-1500:]
        except (OSError, subprocess.TimeoutExpired) as exc:
            rc, tail = None, type(exc).__name__
        row = {**step, "action": "applied", "rc": rc, "secs": round(time.monotonic() - t0, 1),
               "out": tail}  # fmt: skip
        _append(ledger, row)
        results.append(row)
    return results


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--plan", action="store_true")
    mode.add_argument("--apply", action="store_true")
    ap.add_argument("--ledger", required=True, type=Path)
    a = ap.parse_args(argv)
    res = apply(a.ledger) if a.apply else plan(a.ledger)
    for r in res:
        print(
            f"{r['action']}: {r['path']}"
            + (f" rc={r.get('rc')}" if "rc" in r else "")
            + (f" ({r['why']})" if r.get("why") else "")
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
