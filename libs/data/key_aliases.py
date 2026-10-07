"""ONE KEY, ONE NAME: env-var aliases for a credential the desk reads under more than one name.

MEASURED 2026-10-06 (asia directive audit, row 31): the Bank of Korea ECOS key was read as
`ECOS_API_KEY` by `alt_proxies` and as `BOK_API_KEY` by the `bok_ecos` row of
`data/asia_sources.json`, so a box holding one name satisfied only one reader. The canonical name
is `ECOS_API_KEY` (the name `KEYS_TO_REGISTER.md` and the key catalogue in PR #201 give the
principal to set); `BOK_API_KEY` is kept as an alias so a box that already set it keeps working.

`adopt()` copies an alias's value onto the canonical name in THIS process's environment when the
canonical name is unset. It never overwrites a set canonical key, never prints or returns a value,
and returns only the NAMES it adopted, so every reader (os.environ, `status_of`, a key catalogue
reader) sees the one canonical name.
"""
from __future__ import annotations

import os
from collections.abc import MutableMapping

#: canonical name -> the alias names that hold the same credential.
KEY_ALIASES: dict[str, tuple[str, ...]] = {
    "ECOS_API_KEY": ("BOK_API_KEY",),
}


def canonical(name: str) -> str:
    """The canonical env name for `name` (itself when it is not an alias)."""
    for canon, aliases in KEY_ALIASES.items():
        if name == canon or name in aliases:
            return canon
    return name


def adopt(environ: MutableMapping[str, str] | None = None) -> list[str]:
    """Fill each unset canonical key from its first set alias. Returns the adopted NAMES only."""
    env: MutableMapping[str, str] = os.environ if environ is None else environ
    adopted: list[str] = []
    for canon, aliases in KEY_ALIASES.items():
        if env.get(canon):
            continue
        for alias in aliases:
            value = env.get(alias)
            if value:
                env[canon] = value
                adopted.append(f"{alias}->{canon}")
                break
    return adopted


__all__ = ["KEY_ALIASES", "adopt", "canonical"]
