"""THE LOGIN IS WITHHELD, ONE RULE FOR THE WRITER AND THE PUBLISHER. Never places an order.

`desks/mt5/research/cost_truth.py` writes `cost_truth_quotes.json` on the trading box and
`desks/mt5/scripts/sync_shadow_to_git.ps1` publishes it. The writer was fixed to withhold the
login, but a box running older code -- or a file the writer never rewrites again (its terminal
read fails, so the cached copy just sits there) -- keeps the old login-bearing copy on disk, and
measured 2026-10-21 the branch still carried the 2026-09-23 copy with `account.login`. Fixing the
writer only ever cleared the NEXT write. So the same rule now runs twice:

  * `account_block(acct)` -- what the writer stamps from `mt5.account_info()`: every field it
    publishes, the login replaced by `login_withheld: <the login was present>`;
  * `withhold_login(account)` -- the same rule applied to an already-written `account` mapping:
    every login-shaped key (libs/ops/login_fence.py `is_login_key`) carrying a non-null value is
    dropped and `login_withheld` is set true;
  * `scrub_for_publish(rel, data)` -- the publisher's step, on the BLOB bytes about to be
    committed, for the paths in `SCRUBBED`: the file is re-serialised exactly as its writer
    serialises it, so a file that is already clean comes back as None (unchanged blob).

The CLI is the publisher's: stdin `<blob>\\t<rel>` lines, stdout the same lines with a scrubbed
path's blob replaced by the scrubbed blob (written with `git hash-object -w`). It runs BEFORE the
login fence, so the fence still judges the final bytes -- a file this could not scrub (not JSON,
an `account` that is not a mapping) passes through unchanged and the fence refuses it. Any
failure exits non-zero and the publisher publishes nothing. Nothing here prints a value.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

#: The account fields the quotes writer publishes, in the writer's order (sort_keys reorders them
#: on disk anyway). The login is never one of them.
ACCOUNT_FIELDS = ("currency", "company", "server", "margin_mode", "leverage")

#: published path -> the key path of the account mapping inside it, and how its writer dumps it.
SCRUBBED: dict[str, dict[str, Any]] = {
    "desks/mt5/data/cost_truth_quotes.json": {
        "account_at": ("account",),
        "dump": {"indent": 1, "sort_keys": True},
        "writer": "desks/mt5/research/cost_truth.py"},
}


def _is_login_key(key: str) -> bool:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from libs.ops.login_fence import is_login_key
    return is_login_key(key)


def account_block(acct: Any, fields: tuple[str, ...] = ACCOUNT_FIELDS) -> dict[str, Any]:
    """The published account block for an `mt5.account_info()`-like object: `login_withheld`
    (was a login present) and `fields`, never the login itself."""
    out: dict[str, Any] = {"login_withheld": getattr(acct, "login", None) is not None}
    for name in fields:
        out[name] = getattr(acct, name, None)
    return out


def withhold_login(account: Mapping[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """(account without any login-shaped key, the key NAMES dropped). A dropped key with a
    non-null value sets `login_withheld` true; an existing true is never lowered."""
    kept: dict[str, Any] = {}
    dropped: list[str] = []
    present = bool(account.get("login_withheld") is True)
    for key, value in account.items():
        if key != "login_withheld" and _is_login_key(str(key)):
            dropped.append(str(key))
            present = present or value is not None
            continue
        kept[key] = value
    if dropped or "login_withheld" in account:
        kept["login_withheld"] = present
    return kept, dropped


def scrub_for_publish(rel: str, data: bytes) -> tuple[bytes | None, list[str]]:
    """(scrubbed bytes, dropped key names) for a SCRUBBED path; (None, []) when the path is not
    scrubbed, the file is already clean, or it cannot be parsed (the login fence judges it)."""
    spec = SCRUBBED.get(rel)
    if spec is None:
        return None, []
    try:
        doc = json.loads(data.decode("utf-8-sig"))
    except (UnicodeDecodeError, ValueError, RecursionError):
        return None, []
    node: Any = doc
    *parents, last = spec["account_at"]
    for key in parents:
        node = node.get(key) if isinstance(node, dict) else None
    if not isinstance(node, dict) or not isinstance(node.get(last), Mapping):
        return None, []
    clean, dropped = withhold_login(node[last])
    if not dropped:
        return None, []
    node[last] = clean
    return (json.dumps(doc, **spec["dump"]) + "\n").encode("utf-8"), [f"{last}.{k}"
                                                                       for k in dropped]


#: FREE TEXT THAT IS PUBLISHED HOURLY (Auditor, 2026-11-11). The CRO cycle ledger's rows carry an
#: agent's own words (binding constraints, work items, blockers), which can quote an account
#: figure or a trade server. Each string value is scrubbed of money figures, hosts and
#: addresses, and `server=`-style pairs; counts, shas, dates and file names are left as written so
#: the ledger stays readable. Only lines that change are re-serialised; every other line keeps
#: its exact bytes.
TEXT_SCRUBBED: frozenset[str] = frozenset({"desks/mt5/data/cro_cycle_ledger.jsonl"})

_MONEY_KV = re.compile(r"(?i)\b(balance|equity|margin|free_margin|profit|pnl|p&l|nav)"
                       r"(\s*[=:]?\s*)[-+]?[$£€]?\s?\d[\d,]*(?:\.\d+)?")
_CURRENCY = re.compile(r"(?:[$£€]|\b(?:USD|GBP|EUR)\s?)[-+]?\d[\d,]*(?:\.\d+)?(?:\s?[kKmM]\b)?")
_SERVER_KV = re.compile(r"(?i)\b(server|login|host)(\s*[=:]\s*)\S+")
_IPLIKE = re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}(?::\d+)?\b")
_HOSTLIKE = re.compile(r"\b[A-Za-z][A-Za-z0-9-]*(?:\.[A-Za-z0-9-]+)*\.(?:com|net|org|io|co|uk|"
                       r"xyz|ai|dev|cloud|app|host|server|ltd|biz|info)(?::\d+)?\b", re.I)


def public_text(text: str) -> str:
    """`text` with money figures, `server=`/`login=`/`host=` values, IP addresses and host
    names replaced. Counts, shas, dates and file names are untouched. Never raises."""
    s = _SERVER_KV.sub(lambda m: f"{m.group(1)}{m.group(2)}[withheld]", text)
    s = _MONEY_KV.sub(lambda m: f"{m.group(1)}{m.group(2)}[money]", s)
    s = _CURRENCY.sub("[money]", s)
    s = _IPLIKE.sub("[addr]", s)
    return _HOSTLIKE.sub("[host]", s)


def _scrub_values(node: Any) -> Any:
    if isinstance(node, str):
        return public_text(node)
    if isinstance(node, list):
        return [_scrub_values(v) for v in node]
    if isinstance(node, dict):
        return {k: _scrub_values(v) for k, v in node.items()}
    return node


def scrub_text_for_publish(rel: str, data: bytes) -> tuple[bytes | None, int]:
    """(scrubbed bytes, lines changed) for a TEXT_SCRUBBED JSONL path; (None, 0) when the path
    is not scrubbed or nothing changed. A line that is not JSON keeps its bytes (the login fence
    judges it)."""
    if rel not in TEXT_SCRUBBED:
        return None, 0
    out: list[bytes] = []
    changed = 0
    for raw in data.splitlines(keepends=True):
        body = raw.rstrip(b"\r\n")
        try:
            row = json.loads(body.decode("utf-8-sig"))
        except (UnicodeDecodeError, ValueError, RecursionError):
            out.append(raw)
            continue
        clean = _scrub_values(row)
        if clean == row:
            out.append(raw)
            continue
        changed += 1
        out.append(json.dumps(clean, ensure_ascii=False).encode("utf-8") + raw[len(body):])
    return (b"".join(out), changed) if changed else (None, 0)


def _git(repo: Path, *args: str, data: bytes | None = None) -> bytes:
    return subprocess.run(["git", "-C", str(repo), *args], input=data, capture_output=True,
                          check=True, timeout=120).stdout


def main(argv: list[str] | None = None) -> int:
    """stdin: `<blob>\\t<rel>` per line; stdout: the same, scrubbed paths re-blobbed. stderr
    names each scrubbed path and the dropped key names, never a value. rc 0 = done."""
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", type=Path, default=ROOT)
    args = ap.parse_args(argv)
    out: list[str] = []
    for ln in sys.stdin.read().splitlines():
        blob, sep, rel = ln.partition("\t")
        if not sep:
            continue
        blob, rel = blob.strip(), rel.strip().replace("\\", "/")
        if rel in TEXT_SCRUBBED:
            text, n = scrub_text_for_publish(rel, _git(args.repo, "cat-file", "blob", blob))
            if text is not None:
                blob = _git(args.repo, "hash-object", "-w", "--stdin", data=text).decode().strip()
                print(f"text scrub: {rel}: {n} line(s) scrubbed (values withheld)",
                      file=sys.stderr)
        if rel in SCRUBBED:
            new, dropped = scrub_for_publish(rel, _git(args.repo, "cat-file", "blob", blob))
            if new is not None:
                blob = _git(args.repo, "hash-object", "-w", "--stdin", data=new).decode().strip()
                print(f"account withhold: {rel}: dropped {', '.join(dropped)} "
                      "(value withheld)", file=sys.stderr)
        out.append(f"{blob}\t{rel}")
    sys.stdout.write("".join(f"{x}\n" for x in out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
