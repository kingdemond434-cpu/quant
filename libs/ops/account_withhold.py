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

`account_state.json` IS PUBLISHED UNIT-FREE (2026-11-11, Auditor ruling). Its writer
(ops/publish_account_state.py) records balance, equity, margin and today's P&L in the account
currency, and the box reads those amounts locally. The public repository gets
`unit_free_account(doc)` instead: the descriptive keys in `ACCOUNT_PUBLIC_KEYS` plus percentages
derived from the amounts (today's P&L against the day's opening equity, margin used against
equity). No currency amount leaves the box. The git history before this change still holds the
earlier copies; that residual is journalled, not rewritten.
"""
from __future__ import annotations

import argparse
import json
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
    "desks/mt5/data/account_state.json": {
        "publish_view": "unit_free",
        "dump": {"indent": 1},
        "newline": False,
        "writer": "ops/publish_account_state.py"},
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


#: The keys of account_state.json published as written: none of them is an amount.
#: `margin_level` is MetaTrader's equity / margin in percent.
ACCOUNT_PUBLIC_KEYS: frozenset[str] = frozenset({
    "updated_at", "source", "venue", "server", "login_withheld", "currency", "open_positions",
    "margin_level", "positions_file",
})

#: derived key -> (numerator amount, basis). Basis "open" is the day's opening equity
#: (equity - today_pnl); "equity" is current equity. Percent, rounded to 4 places.
ACCOUNT_DERIVED: dict[str, tuple[str, str]] = {
    "today_pnl_pct": ("today_pnl", "open"),
    "today_closed_pnl_pct": ("today_closed_pnl", "open"),
    "today_floating_pnl_pct": ("today_floating_pnl", "open"),
    "today_swap_pct": ("today_swap", "open"),
    "margin_used_pct": ("margin", "equity"),
    "margin_free_pct": ("margin_free", "equity"),
}


def _amount(doc: Mapping[str, Any], key: str) -> float | None:
    v = doc.get(key)
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    return float(v)


def unit_free_account(doc: Mapping[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """(the publishable view of account_state.json, key NAMES dropped -- never a value).

    Already-derived percentages pass through, so a published view maps to itself."""
    view: dict[str, Any] = {k: v for k, v in doc.items()
                            if k in ACCOUNT_PUBLIC_KEYS or k in ACCOUNT_DERIVED}
    dropped = sorted(str(k) for k in doc if k not in view)
    equity, pnl = _amount(doc, "equity"), _amount(doc, "today_pnl")
    bases = {"equity": equity,
             "open": (equity - pnl) if equity is not None and pnl is not None else None}
    for out, (num_key, basis) in ACCOUNT_DERIVED.items():
        num, base = _amount(doc, num_key), bases[basis]
        if num is None:
            continue
        view[out] = round(100.0 * num / base, 4) if base and base > 0 else None
    return view, dropped


def _publish_view(spec: Mapping[str, Any], data: bytes) -> tuple[bytes | None, list[str]]:
    try:
        doc = json.loads(data.decode("utf-8-sig"))
    except (UnicodeDecodeError, ValueError, RecursionError):
        return None, []
    if not isinstance(doc, dict):
        return None, []
    view, dropped = unit_free_account(doc)
    if not dropped and view == doc:
        return None, []
    tail = "\n" if spec.get("newline", True) else ""
    return (json.dumps(view, **spec["dump"]) + tail).encode("utf-8"), dropped


def scrub_for_publish(rel: str, data: bytes) -> tuple[bytes | None, list[str]]:
    """(scrubbed bytes, dropped key names) for a SCRUBBED path; (None, []) when the path is not
    scrubbed, the file is already clean, or it cannot be parsed (the login fence judges it)."""
    spec = SCRUBBED.get(rel)
    if spec is None:
        return None, []
    if spec.get("publish_view") == "unit_free":
        return _publish_view(spec, data)
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
