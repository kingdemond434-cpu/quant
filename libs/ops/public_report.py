"""WHAT A BOX REPORT MAY SAY ON A PUBLIC BRANCH, APPLIED BY THE ORGAN THAT WRITES IT.

The sandbox and census reports cross `sync_shadow_to_git.ps1`'s `$reportPaths` wire onto a
public repository (Governance ruling 2026-11-17). Their writers stamp what was convenient on the
box: `sys.executable`, the sandbox root, an adapter's exception text, `COMPUTERNAME`. None of that
is research evidence, and all of it is the host's layout. So each writer passes its document
through `redact()` before the bytes reach disk, and the publisher never has to guess.

`redact(doc)` returns a copy in which:

  * a string holding this repository's absolute root is rewritten repo-relative (forward
    slashes), so a path a reader resolves against the checkout still resolves;
  * any OTHER absolute path (a drive letter, a UNC share, or a POSIX home/system root) becomes
    `[path]`;
  * money figures with a currency mark, IP addresses, host names and `server=`/`login=`/`host=`
    pairs inside free text are withheld by `libs.ops.account_withhold.public_text`;
  * a value under a host, server, login, account, password, token, secret or key-shaped KEY is
    withheld whole (`[withheld]`), and so is a string shaped like a credential (`ghp_...`,
    `sk-...`, a PEM block), wherever it sits.

Research numbers (pnl in R, Sharpe, counts, seconds, cells) are left exactly as written: the
fence is the host and the account, never the measurement. Never raises; never prints a value.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

WITHHELD = "[withheld]"
PATH = "[path]"

#: A key whose value is withheld whole. Matched on the key's last `_`/`-` separated word(s).
_SECRET_KEY = re.compile(
    r"(?i)(?:^|[_\-.])(host|hostname|computername|server|login|account|account_id|"
    r"password|passwd|pwd|token|secret|api_?key|apikey|private_?key|credential|"
    r"credentials|auth)$")
#: Credential-shaped strings, wherever they appear.
_TOKEN = re.compile(r"(?:\bgh[pousr]_[A-Za-z0-9]{20,}|\bgithub_pat_[A-Za-z0-9_]{20,}|"
                    r"\bsk-[A-Za-z0-9_\-]{16,}|\bxox[abpr]-[A-Za-z0-9\-]{10,}|"
                    r"\bAKIA[0-9A-Z]{16}\b|-----BEGIN [A-Z ]*PRIVATE KEY-----)")
#: An absolute path that is not under this repository.
#: A space continues the path only when the next word carries a separator (`Program Files\\x`).
_WIN_ABS = re.compile(r"(?i)(?<![A-Za-z0-9])[A-Z]:[\\/]"
                      r"(?:[^\s\"'<>|,;]|\s(?=[^\s\"'<>|,;]*[\\/]))*")
_UNC = re.compile(r"\\\\[A-Za-z0-9._$-]+\\[^\s\"'<>|,;]*")
_POSIX_ABS = re.compile(r"(?<![\w.~/-])/(?:home|root|Users|tmp|opt|mnt|var|srv|etc|usr|private|"
                        r"Volumes|media|run)(?:/[^\s\"'<>|,;]*)?")


def _roots(root: Path) -> list[str]:
    raw = str(root)
    forms = {raw, raw.replace("\\", "/"), raw.replace("/", "\\")}
    return sorted((f.rstrip("\\/") for f in forms if f.strip("\\/")), key=len, reverse=True)


def public_string(text: str, root: Path = ROOT) -> str:
    """`text` with host layout, credentials and account identity withheld (see the module)."""
    s = text
    for r in _roots(root):
        if r and r in s:
            s = re.sub(re.escape(r) + r"[\\/]?([^\s\"'<>|,;]*)",
                       lambda m: m.group(1).replace("\\", "/") or ".", s)
    s = _TOKEN.sub(WITHHELD, s)
    s = _UNC.sub(PATH, s)
    s = _WIN_ABS.sub(PATH, s)
    s = _POSIX_ABS.sub(PATH, s)
    from libs.ops.account_withhold import public_text
    return public_text(s)


def redact(node: Any, root: Path = ROOT) -> Any:
    """A copy of a JSON-shaped `node` that is safe to publish (see the module docstring)."""
    if isinstance(node, str):
        return public_string(node, root)
    if isinstance(node, Path):
        return public_string(str(node), root)
    if isinstance(node, (list, tuple)):
        return [redact(v, root) for v in node]
    if isinstance(node, dict):
        out: dict[Any, Any] = {}
        for k, v in node.items():
            key = str(k)
            if _SECRET_KEY.search(key) and v is not None and not isinstance(v, (bool, dict, list)):
                out[k] = WITHHELD
            else:
                out[k] = redact(v, root)
        return out
    return node
