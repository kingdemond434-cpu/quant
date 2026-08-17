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
"""

from __future__ import annotations

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


def row_account(row: dict) -> tuple:
    """The account key of a ledger row. Rows predating provenance key as fully unknown."""
    return (row.get("account"), row.get("server"), row.get("account_kind", UNKNOWN))


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
    login, server, kind = row_account(row)
    if kind == UNKNOWN or login is None:
        return False
    return (login == acc.get("login") and server == acc.get("server")
            and kind == acc.get("kind"))


def split_by_account(rows: list[dict]) -> dict[tuple, list[dict]]:
    """Group rows by account. Segregation, not deletion -- a demo run is still evidence."""
    out: dict[tuple, list[dict]] = defaultdict(list)
    for r in rows:
        out[row_account(r)].append(r)
    return dict(out)


def stamp(acc: dict) -> dict:
    """The provenance fields to merge into a ledger row."""
    return {"account": acc.get("login"), "server": acc.get("server"),
            "account_kind": acc.get("kind", UNKNOWN)}
