"""Read an API key the way the box actually stores it.

``setx /M NAME value`` writes HKLM ``Session Manager\\Environment``. A process only sees that
value if it STARTED after the write, so every resident worker, every task the scheduler launched
from a stale environment block, and every child of one of those keeps reporting the key missing
however many times the operator sets it (10-06: FRED_API_KEY, "I did this so many times"). A
plain ``setx`` without ``/M`` lands in one user's HKCU, which a task running as another account
never reads either.

``read_key`` closes both: process environment first, then on Windows the machine environment,
the current user's, and finally any other loaded user's hive. A hit from the registry is copied
into ``os.environ`` so the children the caller spawns inherit it. Values are never logged.

The key list itself is data, in ``env_keys_catalog.json`` next to this file, so the Python and
PowerShell checkers (scripts/check_keys.py, scripts/check_keys.ps1) and the operator guide read
one list.
"""

from __future__ import annotations

import json
import os
import sys
from functools import cache
from pathlib import Path
from typing import Any

CATALOG_PATH = Path(__file__).with_name("env_keys_catalog.json")
_MACHINE_ENV = r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"


def _reg_value(hive: Any, subkey: str, name: str) -> str:
    import winreg  # type: ignore[import-not-found,unused-ignore]

    try:
        with winreg.OpenKey(hive, subkey) as k:
            value, kind = winreg.QueryValueEx(k, name)
    except OSError:
        return ""
    text = str(value or "").strip()
    if kind == winreg.REG_EXPAND_SZ:
        text = os.path.expandvars(text)
    return text


def registry_sources(name: str) -> list[tuple[str, str]]:
    """Every registry scope holding ``name`` as (scope, value). Empty off Windows."""
    if sys.platform != "win32":
        return []
    import winreg  # type: ignore[import-not-found,unused-ignore]

    out: list[tuple[str, str]] = []
    v = _reg_value(winreg.HKEY_LOCAL_MACHINE, _MACHINE_ENV, name)
    if v:
        out.append(("machine", v))
    v = _reg_value(winreg.HKEY_CURRENT_USER, "Environment", name)
    if v:
        out.append(("user", v))
    try:
        with winreg.OpenKey(winreg.HKEY_USERS, "") as users:
            i = 0
            while True:
                try:
                    sid = winreg.EnumKey(users, i)
                except OSError:
                    break
                i += 1
                if not sid.startswith("S-1-5-21-") or sid.endswith("_Classes"):
                    continue
                v = _reg_value(winreg.HKEY_USERS, sid + r"\Environment", name)
                if v:
                    out.append((f"user:{sid}", v))
    except OSError:
        pass
    return out


def read_key(name: str, default: str = "") -> str:
    """The value of ``name``: process env, else the Windows registry (machine, user, any user)."""
    if not name:
        return default
    v = (os.environ.get(name) or "").strip()
    if v:
        return v
    for _scope, value in registry_sources(name):
        os.environ[name] = value
        return value
    return default


@cache
def catalog() -> tuple[dict[str, Any], ...]:
    data = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    return tuple(data["keys"])


def key_names() -> list[str]:
    return [str(row["name"]) for row in catalog()]
