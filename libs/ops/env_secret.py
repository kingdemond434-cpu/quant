"""A key the principal set on the box, found wherever Windows actually put it.

THE DEFECT (2026-10-06). The principal set FRED_API_KEY with `setx /M` "many times", and every
ALFRED pass still read BLOCKED_AUTH. `setx /M` writes the MACHINE environment in the registry
(HKLM\\SYSTEM\\CurrentControlSet\\Control\\Session Manager\\Environment); it never reaches a
process that is ALREADY running, nor the children that process starts. The desk's residents are
long-lived scheduled tasks, so `os.environ` in them is the environment of the day they started,
and a key set after that is invisible to every organ they launch until the box reboots.

So a key is looked up in this order, and the caller learns WHERE it came from (never what it is):

    machine   HKLM Session Manager Environment (what `setx /M` writes): the newest setting wins
              over a stale copy a long-running process inherited
    user      HKCU\\Environment (what a plain `setx` writes)
    process   os.environ (off Windows, and keys a launcher injected)
    file      the secrets files the caller names

Names are tried exactly as given, then case-insensitively in the registry (Windows environment
names are case-insensitive). No value is ever printed, logged or returned by `presence`.

    python -m libs.ops.env_secret FRED_API_KEY      # prints origin and length only
"""
from __future__ import annotations

import json
import os
import sys
from collections.abc import Iterable, Sequence
from pathlib import Path

MACHINE_KEY = r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"
USER_KEY = "Environment"


def _registry(hive: str, name: str) -> str | None:
    """One value from the Windows registry environment, or None. Never raises."""
    if not sys.platform.startswith("win"):
        return None
    try:
        import winreg
        root = winreg.HKEY_LOCAL_MACHINE if hive == "machine" else winreg.HKEY_CURRENT_USER
        path = MACHINE_KEY if hive == "machine" else USER_KEY
        flags = winreg.KEY_READ | getattr(winreg, "KEY_WOW64_64KEY", 0)
        with winreg.OpenKey(root, path, 0, flags) as k:
            try:
                value = winreg.QueryValueEx(k, name)[0]
            except OSError:
                value = None
                i = 0
                while True:
                    try:
                        n, v, _t = winreg.EnumValue(k, i)
                    except OSError:
                        break
                    if str(n).lower() == name.lower():
                        value = v
                        break
                    i += 1
        text = str(value or "").strip()
        return os.path.expandvars(text) if text else None
    except Exception:
        return None


def _from_file(path: Path) -> str | None:
    try:
        text = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not text:
        return None
    if text.startswith("{"):
        try:
            doc = json.loads(text)
        except ValueError:
            return None
        if isinstance(doc, dict):
            for k in ("key", "api_key", "value"):
                if str(doc.get(k) or "").strip():
                    return str(doc[k]).strip()
        return None
    return text


def lookup(names: Sequence[str], files: Iterable[Path] = ()) -> tuple[str | None, str]:
    """(value, origin). origin is machine | user | process | file:<name> | absent."""
    for hive in ("machine", "user"):
        for n in names:
            r = _registry(hive, n)
            if r:
                return r, hive
    for n in names:
        v = os.environ.get(n, "").strip()
        if v:
            return v, "process"
    for p in files:
        f = _from_file(Path(p))
        if f:
            return f, f"file:{Path(p).name}"
    return None, "absent"


SECRET_SUFFIXES = ("_KEY", "_TOKEN", "_SECRET", "_HASH", "_PASS", "_PASSWORD", "_USER",
                   "_USERNAME", "_EMAIL", "_MAILADDRESS", "_UA", "_APP_ID")
#: The key inventory (libs/ops/env_keys_catalog.json): every credential the code reads, by name
#: and alias. A name it lists is carried even when its suffix is unusual; a name in a refused
#: group (paid data, banned sources) is never carried, whatever its suffix.
CATALOG = Path(__file__).with_name("env_keys_catalog.json")
REFUSED_GROUPS = frozenset({"paid_blocked", "banned"})


def _catalog_names() -> tuple[set[str], set[str]]:
    """(allowed, refused) upper-cased names from the catalog; both empty when it is absent."""
    allowed: set[str] = set()
    refused: set[str] = set()
    try:
        rows = json.loads(CATALOG.read_text(encoding="utf-8")).get("keys", [])
    except (OSError, ValueError, AttributeError):
        return allowed, refused
    for r in rows if isinstance(rows, list) else []:
        if not isinstance(r, dict):
            continue
        names = {str(n).upper() for n in [r.get("name"), *(r.get("aliases") or [])] if n}
        (refused if r.get("group") in REFUSED_GROUPS else allowed).update(names)
    return allowed, refused


def is_secret_name(name: str, catalog: tuple[set[str], set[str]] | None = None) -> bool:
    """A variable a resident should carry to its children: a catalogued credential or a
    credential-shaped name, and never one the catalog refuses."""
    allowed, refused = _catalog_names() if catalog is None else catalog
    up = name.upper()
    if up in refused:
        return False
    return up in allowed or up.endswith(SECRET_SUFFIXES)


def _registry_all(hive: str) -> dict[str, str]:
    """Every value of one registry environment hive, or {}. Never raises, never logs."""
    if not sys.platform.startswith("win"):
        return {}
    out: dict[str, str] = {}
    try:
        import winreg
        root = winreg.HKEY_LOCAL_MACHINE if hive == "machine" else winreg.HKEY_CURRENT_USER
        path = MACHINE_KEY if hive == "machine" else USER_KEY
        flags = winreg.KEY_READ | getattr(winreg, "KEY_WOW64_64KEY", 0)
        with winreg.OpenKey(root, path, 0, flags) as k:
            i = 0
            while True:
                try:
                    n, v, _t = winreg.EnumValue(k, i)
                except OSError:
                    break
                out[str(n)] = str(v or "")
                i += 1
    except Exception:
        return {}
    return out


def fresh_secrets(existing: dict[str, str] | None = None) -> dict[str, str]:
    """Credential variables (`is_secret_name`: catalogued, or credential-shaped like `*_KEY`,
    `*_TOKEN`, `*_PASSWORD`, `*_USER`) that the registry holds and the given environment lacks:
    the keys a `setx /M` added after this process started. A resident merges them into each
    child's environment, so a key the principal sets reaches the next pass without a reboot.
    Only fills ABSENT names; never overrides what the process already has."""
    env = os.environ if existing is None else existing
    have = {k.upper() for k, v in env.items() if str(v).strip()}
    out: dict[str, str] = {}
    cat = _catalog_names()
    for hive in ("machine", "user"):
        for name, value in _registry_all(hive).items():
            if (is_secret_name(name, cat) and value.strip()
                    and name.upper() not in have and name not in out):
                out[name] = os.path.expandvars(value.strip())
    return out


def presence(names: Sequence[str], files: Iterable[Path] = ()) -> dict[str, object]:
    """Where the key is and how long it is. The value never leaves this function."""
    value, origin = lookup(names, files)
    return {"present": value is not None, "origin": origin,
            "length": len(value) if value else 0, "names": list(names)}


def main(argv: list[str] | None = None) -> int:
    names = (argv if argv is not None else sys.argv[1:]) or ["FRED_API_KEY"]
    print(json.dumps(presence(names)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
