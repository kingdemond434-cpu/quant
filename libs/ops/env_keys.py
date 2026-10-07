"""Read an API key the way the box actually stores it.

``setx /M NAME value`` writes HKLM ``Session Manager\\Environment``. A process only sees that
value if it STARTED after the write, so a resident worker (and every child it launches) keeps
reporting a key missing however many times the operator sets it (10-06: FRED_API_KEY).

THIS IS THE SMALLEST SLICE OF #201 (claude/check-keys-machine-env) A READER NEEDS: ``read_key``
and its registry helper, with #201's semantics and call shape, so a caller written against this
file runs unchanged when #201 lands and its fuller ``env_keys.py`` replaces this one. ``_registry``
is #201's ``libs/ops/env_secret._registry`` verbatim; ``read_key`` performs #201's
``env_secret.lookup`` order (machine registry, user registry, process env -- the registry wins
so a key re-set after a resident started beats its stale inherited copy). #201's catalog,
refused-group guard and checkers are NOT carried here; they arrive with #201.

Values are never logged, printed or returned by anything but ``read_key``.
"""
from __future__ import annotations

import os
import sys

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


def read_key(name: str, default: str = "", *, export: bool = False) -> str:
    """The value of ``name`` wherever Windows put it (machine registry, user registry, process
    env), or ``default`` when it is set nowhere. Callers test it for truthiness, so an absent
    key is falsy here and under #201 alike.

    ``export=True`` also copies the value into ``os.environ`` for children; off by default, so a
    lookup never widens what every subprocess inherits."""
    if not name:
        return default
    value: str | None = None
    for hive in ("machine", "user"):
        value = _registry(hive, name)
        if value:
            break
    if not value:
        value = os.environ.get(name, "").strip() or None
    if not value:
        return default
    if export and os.environ.get(name, "").strip() != value:
        os.environ[name] = value
    return value
