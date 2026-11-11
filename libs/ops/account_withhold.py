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

The same publisher step also WITHHOLDS THE MONEY of `gateway_state.json` (2026-11-11). The
gateway's restart state carried `equity`, `day_start_equity.equity` and each open position's
`profit`, and the sync published it to a PUBLIC repository on its fifteen-minute clock, so the
live balance went out with every pass. `redact_money(doc)` keeps the top-level keys in
`GATEWAY_PUBLIC_KEYS` only (a key the gateway adds later stays on the box until someone names it
here) and, inside them, drops every money-shaped leaf (`MONEY_KEY`); a money-shaped key holding a
mapping is recursed into, so `day_start_equity` keeps its `date` and loses its amount. The box's
own file is untouched -- every reader on the box still sees the full state.

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
    "desks/mt5/data/gateway_state.json": {
        "redact": "money",
        "dump": {"indent": 2, "default": str},
        "newline": False,
        "writer": "desks/mt5/mt5desk/gateway.py save_state"},
}

#: A key name that holds an account amount. Matched on the key, never the value.
MONEY_KEY = re.compile(r"equity|balance|margin|profit|pnl|credit|swap|commission",
                       re.IGNORECASE)

#: The top-level keys of gateway_state.json that are published. Anything else stays on the box.
#: `equity` and `margin_free` are absent on purpose; `day_start_equity` is kept for its date.
GATEWAY_PUBLIC_KEYS: frozenset[str] = frozenset({
    "armed", "bracket", "bracket_cancelled", "brackets", "broker_utc_offset_h",
    "daily_loss_stood_down", "day_start_equity", "generic", "last_bracket_date",
    "last_reconcile", "lot", "netting_booked", "orig_stop_dist", "paused_snapshot_at", "pending",
    "placement_health", "placement_pass", "placement_pass_clock", "placement_tick_broker",
    "placement_tick_utc", "position", "rails_logged", "restart_reconcile", "scalp",
    "vetoed_today",
})


def _drop_money(node: Any, path: str, dropped: list[str]) -> Any:
    if isinstance(node, dict):
        out: dict[str, Any] = {}
        for key, value in node.items():
            here = f"{path}.{key}" if path else str(key)
            if MONEY_KEY.search(str(key)) and not isinstance(value, dict):
                dropped.append(here)
                continue
            out[key] = _drop_money(value, here, dropped)
        return out
    if isinstance(node, list):
        return [_drop_money(v, f"{path}[]", dropped) for v in node]
    return node


def redact_money(doc: Mapping[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """(the publishable view of gateway_state.json, the key PATHS dropped -- never a value)."""
    dropped: list[str] = []
    kept: dict[str, Any] = {}
    for key, value in doc.items():
        if key not in GATEWAY_PUBLIC_KEYS:
            dropped.append(str(key))
            continue
        if MONEY_KEY.search(str(key)) and not isinstance(value, dict):
            dropped.append(str(key))
            continue
        kept[key] = _drop_money(value, str(key), dropped)
    return kept, sorted(set(dropped))


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
    if spec.get("redact") == "money":
        if not isinstance(doc, dict):
            return None, []
        view, gone = redact_money(doc)
        if not gone:
            return None, []
        tail = "\n" if spec.get("newline", True) else ""
        return (json.dumps(view, **spec["dump"]) + tail).encode("utf-8"), gone
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
                print(f"account withhold: {rel}: dropped {', '.join(dropped[:20])}"
                      f"{' ...' if len(dropped) > 20 else ''} "
                      "(value withheld)", file=sys.stderr)
        out.append(f"{blob}\t{rel}")
    sys.stdout.write("".join(f"{x}\n" for x in out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
