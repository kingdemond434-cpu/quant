"""A credential the box holds at MACHINE scope, read fresh, for the LLM seats only.

WHY THE BOX SEAT CANNOT SEE ITS OWN KEY. The keys guide sets every credential with
`[Environment]::SetEnvironmentVariable(NAME, value, 'Machine')`, which writes the registry and
nothing else. A process copies its environment block once, when it starts. So every resident
process (the research supervisor, the deepening worker, an hourly leg started by one of them)
that was already running when the key was set keeps an environment that does not contain it,
and reports "no seat" until something restarts it. `setx` without `/M` has the same effect from
the other side: it writes the USER hive, and the SYSTEM tasks never read that hive at all.
`deepening_worked.jsonl` recorded 28,686 rows of "no seat: export OPENROUTER_API_KEY" this way.

So a name missing from `os.environ` is looked up in the registry, machine scope first and then
the running account's own user scope, at the moment it is needed. Nothing is cached and nothing
is written back into the process environment, so a child process never inherits a key it was
not given.

FOUR FENCES, because a helper that finds keys is a helper that can hand them out:
  * only the names in `SEAT_KEYS` are ever looked up here, so a broker credential or a data key
    cannot be reached through it;
  * J-Quants is refused by name even if it is added to that list later, because its licence
    keeps its data away from every model;
  * under pytest (collection included) the registry is never read either, so a test that
    deletes a key on the box sees no key rather than the box's real one;
  * when `QUANT_SANDBOX=1` the registry is never read. `libs.research.sandbox.scrub_env` sets
    it, and so do the desk's two model-code runners (llm_lab_roles' code lab and
    collector_author). This guards a sandboxed process that imports this module; it is not a
    sandbox itself -- those runners also refuse `winreg` and run isolated (`python -I`).
"""

from __future__ import annotations

import os
import sys

#: The only names this module will look up in the registry: the LLM seats' keys.
SEAT_KEYS: frozenset[str] = frozenset(
    {
        "OPENROUTER_API_KEY",
        "OPENAI_API_KEY",
        "DEEPSEEK_API_KEY",
        "XAI_API_KEY",
    }
)

#: J-Quants data never reaches a model (its licence), so its key is never resolved here.
_NEVER = ("JQUANTS",)

_MACHINE = r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"
_USER = "Environment"


def _registry(name: str) -> str:
    if sys.platform != "win32":
        return ""
    try:
        import winreg
    except ImportError:
        return ""
    for hive, path in ((winreg.HKEY_LOCAL_MACHINE, _MACHINE), (winreg.HKEY_CURRENT_USER, _USER)):
        try:
            with winreg.OpenKey(hive, path, 0, winreg.KEY_READ) as k:
                raw, _kind = winreg.QueryValueEx(k, name)
        except OSError:
            continue
        val = os.path.expandvars(str(raw or "")).strip()
        if val:
            return val
    return ""


def value(name: str) -> str:
    """The process environment's value, else the registry's, else "". Never raises."""
    got = os.environ.get(name, "").strip()
    if got:
        return got
    upper = name.upper()
    if upper not in SEAT_KEYS or any(n in upper for n in _NEVER):
        return ""
    if os.environ.get("QUANT_SANDBOX") == "1" or os.environ.get("QUANT_MACHINE_ENV") == "0":
        return ""
    if _under_test():
        return ""  # a test that clears a key must not find the box's real one
    return _registry(name)


def _under_test() -> bool:
    """Inside a pytest run, collection included (PYTEST_CURRENT_TEST is unset while collecting)."""
    return "PYTEST_CURRENT_TEST" in os.environ or "pytest" in sys.modules
