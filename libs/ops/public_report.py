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
    withheld whole (`[withheld]`) unless it is a count (`n_token: 3`), and so is a string shaped
    like a credential (`ghp_...`, `sk-...`, a PEM block), wherever it sits;
  * inside free text -- exception messages above all -- every URL query VALUE, any
    `user:pass@` in a URL, and the value of any secret-named pair (`{"token": "..."}`,
    `password=...`, `Authorization: Bearer ...`) are withheld; the names stay readable.

Research numbers (pnl in R, Sharpe, counts, seconds, cells) are left exactly as written: the
fence is the host and the account, never the measurement. Never raises; never prints a value.
"""
from __future__ import annotations

import contextlib
import re
import sys
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
#: Every query-string value in a URL (`?api_key=...&registrationkey=...`): a request error quotes
#: the URL it failed on, and a query value is where an API key travels. Names stay, values go.
_QUERY_VALUE = re.compile(r"([?&;][A-Za-z0-9_.\-\[\]]+=)[^&\s\"'#<>)\]}]+")
#: `user:password@` in a URL.
_USERINFO = re.compile(r"(?i)\b([a-z][a-z0-9+.\-]*://)[^/\s@\"']+@")
#: A secret-named pair inside free text, quoted or not: `{"token": "abc"}`, `{'api_key': 'x'}`,
#: `password=hunter2`, `Authorization: Bearer abc`. The NAME stays so the error stays readable.
_SECRET_PAIR = re.compile(
    r"(?i)([\"']?[A-Za-z0-9_\-]*(?:token|secret|passw(?:or)?d|passwd|pwd|api_?key|apikey|"
    r"access_?key|private_?key|registration_?key|client_?secret|credential|authorization|auth|"
    r"cookie|session_?id|signature|sig)[A-Za-z0-9_\-]*[\"']?\s*[:=]\s*)"
    r"(?:(?:bearer|basic|token)\s+)?([\"']?)(?!\[withheld\])[^\s\"',;&}\]]+\2")
#: A COUNT is never a secret, whatever its key says (`n_token`, `token_count`).
_COUNT_KEY = re.compile(r"(?i)^(?:n|num|count|max|min|total)_|_(?:count|n|total|len)$")
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
    s = _USERINFO.sub(lambda m: f"{m.group(1)}{WITHHELD}@", s)
    s = _QUERY_VALUE.sub(lambda m: f"{m.group(1)}{WITHHELD}", s)
    s = _SECRET_PAIR.sub(lambda m: f"{m.group(1)}{m.group(2)}{WITHHELD}{m.group(2)}", s)
    s = _UNC.sub(PATH, s)
    s = _WIN_ABS.sub(PATH, s)
    s = _POSIX_ABS.sub(PATH, s)
    s = _EXC_MSG.sub(lambda m: f"{m.group(1)} [message withheld on the box]", s)
    from libs.ops.account_withhold import public_text
    return public_text(s)


def exc_text(exc: BaseException, where: str = "") -> str:
    """What a PUBLISHED field may say about an exception: its type name, nothing else (Audit
    HOLD 2, 2026-11-17). An exception's message is free text from a library, a URL or a server --
    a key in a URL path, an `X-Api-Key` header, a URL-encoded query -- and no denylist fences
    free text. The full message goes to this process's stderr, which is the task's own log on
    the box, and never into a report."""
    name = type(exc).__name__
    with contextlib.suppress(Exception):  # logging must never turn into the failure
        print(f"[{where or 'error'}] {name}: {exc}", file=sys.stderr)
    return name


#: Strings shaped `SomeError: message` (or `...Exception:`/`...Exit:`) anywhere in a published
#: value lose their message: the backstop for a writer this file was never told about.
_EXC_MSG = re.compile(r"\b([A-Z][A-Za-z0-9_]*(?:Error|Exception|Exit|Interrupt|Expired|Timeout))"
                      r"(?::\s*|\(\s*)[^\n]*")
#: Keys whose values are a subprocess's own output or an exception's text.
_OUTPUT_KEY = re.compile(r"(?i)(?:^|_)(stdout|stderr|stdout_tail|stderr_tail|tail|traceback)$")
#: Keys that name an error: they may carry an exception TYPE (optionally after a fixed label such
#: as `EURUSD/momentum: `), never its message.
_ERROR_KEY = re.compile(r"(?i)(?:^|_)(rejected|exception|exc|error|errors)$")
#: The one thing an error field may still say: an exception's type name (`exc_text`'s output).
_BARE_TYPE = re.compile(r"(?:[A-Za-z0-9_./|\-]{1,120}: )?[A-Za-z_][A-Za-z0-9_.]{0,80}")


def _output(v: Any) -> Any:
    if isinstance(v, str):
        return v if _BARE_TYPE.fullmatch(v) else WITHHELD_OUTPUT
    if isinstance(v, (list, tuple)):
        return [_output(x) for x in v]
    return WITHHELD_OUTPUT
WITHHELD_OUTPUT = "[output withheld on the box]"


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
            counted = isinstance(v, (int, float)) and _COUNT_KEY.search(key)
            if _OUTPUT_KEY.search(key) and isinstance(v, (str, list, tuple)) and v:
                out[k] = WITHHELD_OUTPUT
            elif _ERROR_KEY.search(key) and isinstance(v, (str, list, tuple)) and v:
                out[k] = _output(v)
            elif (_SECRET_KEY.search(key) and v is not None and not counted
                    and not isinstance(v, (bool, dict, list))):
                out[k] = WITHHELD
            else:
                out[k] = redact(v, root)
        return out
    return node
