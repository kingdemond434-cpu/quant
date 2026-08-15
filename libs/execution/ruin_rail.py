"""THE RUIN RAILS, ASKED IN ONE PLACE -- because a freeze that only some order paths honour is not
a freeze.

WHAT THIS FIXES. `data/CASHCARRY_KILL` has been latched since 2026-08-01 ("pager ladder at 4h
rung"). Eight modules read it -- the cashcarry executor, the deadman switch, the live guard,
gate-0, the alerts, the growth audit, the idle-cost fence, the change window -- and each declares
its own `_KILL = Path("data/CASHCARRY_KILL")`. That worked while there was exactly ONE order path.

Then a second order path was built (`run_spot_executor`) and it inherited none of them, because
inheriting a rail requires somebody to remember it exists. Its arming contract -- keyfile,
LIVE_ENABLE, VPS_VERIFIED -- says only "may this box place orders at all", which is a different
question from "is the book currently frozen". So the desk's own preflight could print
``ruin rail (CASHCARRY_KILL): BLOCKED -- the executor is FROZEN and places no orders`` on the same
box, in the same minute, that the spot executor would happily have spent the whole $200.

**A RAIL IS ONLY A RAIL IF EVERY PATH THAT SPENDS MONEY ASKS IT.** One reader, imported by every
order path, is the only structure where adding a ninth path cannot silently skip the check. The
per-module `_KILL` constants stay where they are: rewriting eight working call sites to prove a
point is how a safety change becomes the outage. New paths use this.

**THE LATCH IS THE ANSWER, THE CONTENTS ARE THE EXPLANATION.** Presence alone freezes. The file's
text is read only to say WHY in the refusal, and an unreadable or empty file still freezes -- a rail
whose reason cannot be parsed is a rail that fired, not a rail that did not.

**NOTHING HERE CLEARS ANYTHING.** No function in this module deletes, truncates or moves a rail
file, and none ever will. Clearing a fired rail is a Tier-3 act reserved to the principal (`rm
data/CASHCARRY_KILL`), for a stated reason, never on a timer -- an idle book satisfies every
"N hours clean" test trivially, forever (GAP 91).
"""

from __future__ import annotations

from pathlib import Path

__all__ = ["RAILS", "frozen", "latched"]

#: Every file whose PRESENCE means "this book does not open new risk", with what each one says.
#: Ordered most-specific first so the refusal names the trading freeze before the harness latch.
RAILS: tuple[tuple[str, str], ...] = (
    ("data/CASHCARRY_KILL",
     "trading freeze -- the executor is flatten-only and opens nothing"),
    ("data/DEADMAN_FIRED",
     "the deadman switch FIRED and latched; the equity rail tripped"),
    ("data/FREEZE",
     "a manual freeze is in place"),
)

#: How much of a rail file's text is quoted back in a refusal. Enough for a timestamp and a reason;
#: short enough that a rail file somebody pasted a stack trace into cannot flood a journal line.
_REASON_CHARS = 300


def _reason(p: Path) -> str:
    """The rail's stated reason, or an explicit note that it has none. NEVER an empty string: a
    blank reason renders as `frozen ()` and reads like a formatting bug rather than a live latch."""
    try:
        txt = p.read_text("utf-8").strip()
    except OSError as exc:
        return f"unreadable ({type(exc).__name__}) -- the latch still counts"
    return txt[:_REASON_CHARS] if txt else "no reason recorded in the file"


def latched(root: Path | None = None) -> list[tuple[str, str, str]]:
    """Every rail currently latched as (path, what_it_means, stated_reason). Empty when clear.

    Returns ALL of them rather than short-circuiting on the first: an operator clearing a freeze
    needs to know there are two, or they will clear one, retry, and be refused again by the other
    with no idea why.
    """
    base = Path(root) if root is not None else Path()
    out: list[tuple[str, str, str]] = []
    for rel, means in RAILS:
        p = base / rel
        if p.exists():
            out.append((rel, means, _reason(p)))
    return out


def frozen(root: Path | None = None) -> tuple[bool, str]:
    """``(is_frozen, why)`` -- the one question an order path asks before it spends money.

    The ``why`` is written to be pasted into a journal and understood a month later, so it names
    the file, what the file means, and what the file says. When clear it states which rails were
    CHECKED, because "no rail latched" and "no rail consulted" are the same sentence otherwise and
    only one of them is evidence.
    """
    hits = latched(root)
    if not hits:
        return False, ("no ruin rail latched (checked " +
                       ", ".join(rel for rel, _ in RAILS) + ")")
    return True, "; ".join(f"{rel} PRESENT -- {means}. Contents: {reason!r}"
                           for rel, means, reason in hits)
