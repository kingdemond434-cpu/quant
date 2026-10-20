"""Which account produced a trade. Without this, every trade looks alike.

WHY THIS EXISTS

This desk switches brokers by editing one line in `data/terminal_path.txt`. That is a good design
-- moving the execution surface should not require a code change -- but it means the account under
the gateway can change between two runs with nothing in the record noticing.

The moment that file points at a Fusion DEMO terminal, demo fills append to
`data/live_ledger.jsonl`. That is the file `promoter.sleeve_forward_stats` reads to RETIRE a live
sleeve, the file `armed_forward_exp` reads to judge gold challengers against the armed book, and
the file markout calls execution evidence. Nothing in a ledger row said which account produced it,
so from the first demo fill onward the two were indistinguishable -- and when the live account is
funded, its sleeves would be judged partly on demo history that happens to sit above them in the
same file.

DEMO FILLS ARE NOT A CONSERVATIVE APPROXIMATION OF LIVE ONES

They are optimistic in exactly the dimension that matters. A demo server has no real liquidity
behind it and typically fills a stop order at its trigger price with no slippage and no reject.
That is precisely the assumption every return figure on this desk already makes and that
`markout` was built to test. A clean markout on demo is therefore not evidence of good execution;
it is the null result a server that cannot slip will always produce.

Demo IS good evidence for the things that break loudly: contract sizes, stop and freeze levels,
symbol suffixes, session hours, margin maths, whether an order is even accepted. Those are real
bugs worth finding without real money. So demo trades are SEGREGATED, never discarded, and never
averaged together with live ones.

THE STAMP IS A KEYED HASH, NOT THE LOGIN (2026-10-20, audits v3 and v4 of publish_sync_schtasks).
Both files this stamps are tracked and published from the box, and on LIVE `live_ledger.jsonl`
carried the live login 257 times and `order_intents.jsonl` 44 times, under `account`. A row now
carries `account_key` = "sha256:" + HMAC-SHA256(box key, "<login>@<server>")[:16 hex].

WHY KEYED (audit v4). The v4 key was a bare truncated SHA-256 of "<login>@<server>", and the
server rides the same row in clear: a single core inverts an 8-digit login in about a minute. The
HMAC key is box-held -- `data/secrets/account_key.hmac` (gitignored with all of data/secrets/,
never printed, never logged), or the file `QUANT_ACCOUNT_KEY_FILE` names -- so without it the
key is not invertible. The FORMAT is unchanged ("sha256:" + 16 lowercase hex), which is what
Fusion r5's book check validates, but the VALUE is no longer r4/r5's bare hash: a reader that
recomputes keys must use this function and the box key, never a bare sha256.

NO KEY, NO HASH. The writer (`stamp`, the gateway's intent stamp) creates the key once, on the box,
the first time it needs one (O_EXCL, so two processes cannot race two keys). If it cannot, the row
keeps the old raw `account` -- the money path keeps its evidence -- and the publish fence
(libs/ops/login_fence.py) refuses that file, which pages. A reader never creates a key: with none,
a hashed row matches nothing (UNMEASURED), exactly as a row with no provenance always has.
LOSING THE KEY ORPHANS EVERY HASHED ROW for `same_account` (they read as no provenance, never as
another account); back it up with the box's other secrets.

LEGACY ROWS STILL CARRY THE RAW LOGIN and are not rewritten (live_ledger's prefix is sealed in
IMMUTABLE_MANIFEST.json and libs/ops/live_ledger_view.py raises on a changed prefix). For any row
without a valid `account_key`, `same_account` runs the original raw comparison VERBATIM -- so
N.0 logins, empty servers and every other legacy edge decide exactly as before -- and `row_key`
hashes it on read for grouping, so a ledger holding both shapes is one account to markout.
"""

from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

#: MT5 account trade modes, inlined so this imports on a research box with no MetaTrader5.
#: Fixed by the platform, not by the broker.
_MODE_DEMO = 0
_MODE_CONTEST = 1
_MODE_REAL = 2

DEMO = "demo"
LIVE = "live"
UNKNOWN = "unknown"


def account_kind(trade_mode: Any) -> str:
    """Classify an MT5 `account_info().trade_mode`. Unrecognised input is UNKNOWN, never a guess.

    FAILS CLOSED, and the asymmetry is the reason. Guessing DEMO would let an unclassifiable real
    account be treated as practice and sized accordingly; guessing LIVE would let demo results
    retire a live sleeve. Neither default is safe, so the desk declines to classify and the caller
    has to handle it -- which, in every consumer here, means the row counts as evidence for
    nothing.
    """
    if trade_mode is True or trade_mode is False or not isinstance(trade_mode, int):
        return UNKNOWN
    if trade_mode in (_MODE_DEMO, _MODE_CONTEST):
        return DEMO
    if trade_mode == _MODE_REAL:
        return LIVE
    return UNKNOWN


def current_account(acc: Any) -> dict:
    """The identity of the account now under the terminal, from an `mt5.account_info()` object.

    `acc is None` means the terminal is not reachable. That is an UNKNOWN account, not an absent
    one: something may well be trading, this process simply cannot see what.
    """
    if acc is None:
        return {"login": None, "server": None, "kind": UNKNOWN}
    return {"login": getattr(acc, "login", None),
            "server": getattr(acc, "server", None),
            "kind": account_kind(getattr(acc, "trade_mode", None))}


#: The keyed account hash lives in ONE place, libs/ops/provenance.py (stable public signature
#: `account_key(login, server, *, create=False) -> str | None`; None is the fail-closed sentinel,
#: never a bare sha256). The repo root is put on sys.path, guarded, for the box's entry points.
_REPO = Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.append(str(_REPO))
from libs.ops.provenance import KEY_ENV, KEY_REL, account_key, is_key, key_path  # noqa: E402

__all__ = ["DEMO", "LIVE", "UNKNOWN", "KEY_ENV", "KEY_REL", "account_key", "account_kind",
           "current_account", "is_key", "key_path", "row_account", "row_key", "same_account",
           "split_by_account", "stamp"]


def row_key(row: dict) -> str | None:
    """The row's account identity as a key: its `account_key`, or a legacy row's raw
    `account`+`server` keyed on read (None on a host without the box key). None when the row
    names no account."""
    key = row.get("account_key")
    if is_key(key):
        return key  # type: ignore[no-any-return]
    return account_key(row.get("account"), row.get("server"))


def row_account(row: dict) -> tuple:
    """The account identity of a ledger row: (key, server, kind). Rows predating provenance
    key as fully unknown. The key replaces the raw login that used to stand first here."""
    return (row_key(row), row.get("server"), row.get("account_kind", UNKNOWN))


def same_account(row: dict, acc: dict) -> bool:
    """Is this ledger row evidence about `acc`?

    Requires login, server AND kind to match. Login alone is not enough -- Fusion demo and Fusion
    live differ by login, but a broker that reuses logins across servers would collide -- and kind
    is checked separately so a row whose kind is UNKNOWN can never satisfy a live account.

    A row with no provenance matches NOTHING, including an unknown account. It is a real trade on
    some account and the desk cannot say which, so it is never counted as evidence for the account
    in hand. That is a deliberate loss of history: the alternative is silently treating pre-switch
    trades as belonging to whatever account is connected today.
    """
    kind = row.get("account_kind", UNKNOWN)
    key = row.get("account_key")
    if not is_key(key):
        # A LEGACY ROW: the original comparison, verbatim (2026-09 .. 2026-10-20).
        login, server = row.get("account"), row.get("server")
        if kind == UNKNOWN or login is None:
            return False
        return (login == acc.get("login") and server == acc.get("server")
                and kind == acc.get("kind"))
    if kind == UNKNOWN:
        return False
    want = account_key(acc.get("login"), acc.get("server"))
    return (want is not None and key == want and row.get("server") == acc.get("server")
            and kind == acc.get("kind"))


def split_by_account(rows: list[dict]) -> dict[tuple, list[dict]]:
    """Group rows by account. Segregation, not deletion -- a demo run is still evidence."""
    out: dict[tuple, list[dict]] = defaultdict(list)
    for r in rows:
        out[row_account(r)].append(r)
    return dict(out)


def stamp(acc: dict) -> dict:
    """The provenance fields to merge into a ledger row: the keyed `account_key`, never the raw
    login. If no box key can be held, the row keeps the raw `account` (the evidence survives)
    and the publish fence refuses the file (see the module docstring)."""
    key = account_key(acc.get("login"), acc.get("server"), create=True)
    out: dict[str, Any] = {"account_key": key, "server": acc.get("server"),
                           "account_kind": acc.get("kind", UNKNOWN)}
    if key is None and acc.get("login") is not None:
        out["account"] = acc.get("login")
    return out
