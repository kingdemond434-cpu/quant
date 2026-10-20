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

THE STAMP IS A HASH, NOT THE LOGIN (2026-10-20, audit v3 of publish_sync_schtasks). Both files
this stamps are tracked and published from the box, and on LIVE `live_ledger.jsonl` carried the
live login 257 times and `order_intents.jsonl` 44 times, under `account`. A row now carries
`account_key` = `account_key(login, server)`, a truncated SHA-256 of "<login>@<server>" -- the
SAME key Fusion r4's `mt5desk/cross_account.py` stamps on its books (that module is not on this
base, so the function is mirrored here, byte for byte in what it computes). Comparing two keys
is comparing the (login, server) pairs they hash, so `same_account` decides exactly what it did.

LEGACY ROWS STILL CARRY THE RAW LOGIN and cannot be rewritten (the ledger's prefix is sealed in
IMMUTABLE_MANIFEST.json and libs/ops/live_ledger_view.py raises on a changed prefix). `row_account`
therefore HASHES a legacy row's `account`+`server` on read, so a ledger holding both shapes is one
account to every reader -- markout's MIXED check, the promoter's admission, independence's k_eff.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict
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


def account_key(login: object, server: object) -> str | None:
    """A truncated SHA-256 of "<login>@<server>": names the account without carrying the login.

    Mirrors `mt5desk.cross_account.account_key` (Fusion r4) in what it computes. That one
    RAISES on an unreadable login or server; this returns None instead, because here an
    unreadable pair means "row with no provenance", which every caller already treats as
    matching nothing -- the same verdict the raw comparison gave a row with no login."""
    if login in (None, "") or isinstance(login, bool) or server in (None, ""):
        return None
    return "sha256:" + hashlib.sha256(f"{login}@{server}".encode()).hexdigest()[:16]


def row_key(row: dict) -> str | None:
    """The row's account identity as a key: its `account_key`, or a legacy row's raw
    `account`+`server` hashed on read. None when the row names no account."""
    key = row.get("account_key")
    if isinstance(key, str) and key.startswith("sha256:"):
        return key
    return account_key(row.get("account"), row.get("server"))


def row_account(row: dict) -> tuple:
    """The account identity of a ledger row: (key, server, kind). Rows predating provenance
    key as fully unknown. The key replaces the raw login that used to stand first here; for a
    legacy row it is that login, hashed (see `row_key`)."""
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
    key, server, kind = row_account(row)
    if kind == UNKNOWN or key is None:
        return False
    # The key hashes (login, server), so key equality is login AND server equality; server is
    # still compared on its own for a row whose key came from the writer, not from this file.
    return (key == account_key(acc.get("login"), acc.get("server"))
            and server == acc.get("server") and kind == acc.get("kind"))


def split_by_account(rows: list[dict]) -> dict[tuple, list[dict]]:
    """Group rows by account. Segregation, not deletion -- a demo run is still evidence."""
    out: dict[tuple, list[dict]] = defaultdict(list)
    for r in rows:
        out[row_account(r)].append(r)
    return dict(out)


def stamp(acc: dict) -> dict:
    """The provenance fields to merge into a ledger row. `account_key`, never the raw login: the
    ledger is tracked and published (see the module docstring)."""
    return {"account_key": account_key(acc.get("login"), acc.get("server")),
            "server": acc.get("server"), "account_kind": acc.get("kind", UNKNOWN)}
