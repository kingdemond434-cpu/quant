"""GAP #49 -- idempotent order submission. Prerequisite for the no-naked-position invariant.

THE FAILURE THIS PREVENTS. The live order path posted symbol/side/type/quantity and no client
order ID, while `execution/retry.py` documented the opposite guarantee. On an ambiguous timeout
the desk cannot tell "not placed" from "placed, reply lost" -- and on a delta-neutral book a
duplicated leg is not a slightly-too-big position, it is an UNHEDGED DIRECTIONAL POSITION. That
is the ruin-class shape: the book stops being market-neutral without anyone deciding it should.

A deterministic client order ID makes the venue itself the deduplicator. Re-sending the same
logical order inside its time bucket reproduces the same ID, and Binance rejects it as a
duplicate rather than filling it twice. No local state, no lock, nothing to lose on restart --
which matters, because restart-and-reconcile is precisely when the re-place happens.

THREE DESIGN POINTS THAT ARE EASY TO GET WRONG, AND EXPENSIVE:

  CHUNK INDEX IS PART OF THE ID. `place_market` splits an order across MARKET_LOT_SIZE chunks.
  If every chunk shared one ID the venue would accept chunk 1 and reject the rest as duplicates,
  silently under-filling the leg -- turning an idempotency fix into a fresh source of unhedged
  exposure. The exact class of bug this module exists to stop.

  BUCKET COLLISIONS FAIL SAFE, AND THAT ASYMMETRY IS THE WHOLE DESIGN. Two genuinely distinct
  orders sharing symbol+side+intent inside one bucket would collide, and the second is rejected.
  That is a missed order -- visible, logged, retryable on the next pass. The alternative failure,
  a duplicated unhedged leg, is silent and directional. Given one of the two must be possible,
  the desk takes the loud one.

  UNKNOWN IS NOT ABSENT. `is_duplicate_error` returns True only on a recognised duplicate signal.
  An unrecognised error must never be read as "already placed", because that would let a genuine
  failure masquerade as success -- the fail-open branch this desk's own history lists first.

Stdlib only: this sits on the live order path, where an import is a dependency on someone else's
release schedule.
"""

from __future__ import annotations

import hashlib
import re
import time

__all__ = ["BUCKET_S", "MAX_ID_LEN", "client_order_id", "is_duplicate_error"]

#: Binance accepts ^[\.A-Z\:/a-z0-9_-]{1,36}$ for clientOrderId. Stay well inside it.
MAX_ID_LEN = 36
_SAFE = re.compile(r"[^A-Za-z0-9_-]")

#: Retry window. A resend inside this many seconds is treated as the SAME logical order.
#:
#: 90s is chosen against the actual failure: an ambiguous HTTP timeout plus the retry that
#: follows it, and a restart-and-reconcile pass. Both land inside a minute and a half. Longer
#: would start merging genuinely separate rebalances into one ID; shorter would let a slow retry
#: escape the dedupe and place the duplicate leg this module exists to prevent.
BUCKET_S = 90.0

#: Duplicate-order signals. Binance returns -2010 with "Duplicate order sent"; the text form is
#: matched too because error surfaces differ between the REST body, the SDK wrapper and the
#: retry layer, and relying on one representation is how a guard quietly stops matching.
_DUP_CODES = (-2010, -4015)
_DUP_TEXT = ("duplicate order", "duplicate clientorderid", "order already exists")


def client_order_id(symbol: str, side: str, intent: str, *, chunk: int = 0,
                    cycle: str | None = None, now: float | None = None,
                    bucket_s: float = BUCKET_S) -> str:
    """Deterministic ID for one logical order chunk.

    `cycle` IS THE CORRECT WAY TO CALL THIS, and the time bucket is a fallback that is weaker in
    a way worth stating plainly. A fixed time grid has boundaries: an order placed 1 second
    before a bucket rolls has a 1-second retry window, after which the retry hashes to a new ID
    and the venue happily places the duplicate. The window is arbitrary and unobservable from the
    call site, so the guarantee it offers is "usually" -- which for an unhedged-leg risk is not a
    guarantee at all. (Found by this module's own tests on the first run, not reasoned about
    afterwards.)

    Passing `cycle` -- any token stable across the retries of ONE logical operation, e.g. the
    rebalance pass that produced the order -- removes the clock from the identity entirely. Same
    cycle, same order, same ID, no matter how long the retry took or where the wall clock is.
    """
    if cycle is None:
        t = time.time() if now is None else float(now)
        b = max(1e-9, float(bucket_s))
        cycle = f"t{int(t // b)}"
    raw = f"{symbol}|{side}|{intent}|{chunk}|{cycle}".upper()
    digest = hashlib.sha256(raw.encode()).hexdigest()[:16]
    # A readable prefix so a human reading venue order history can tell whose order it is; the
    # digest carries the uniqueness. Truncated hard to stay inside the venue's 36-char limit.
    prefix = _SAFE.sub("", f"q{symbol}{side[:1]}{intent[:1]}")[:MAX_ID_LEN - 17].lower()
    return f"{prefix}-{digest}"[:MAX_ID_LEN]


def is_duplicate_error(err: object) -> bool:
    """True ONLY when the venue positively said 'this order already exists'.

    Fail-closed on ambiguity: an unrecognised error returns False, so the caller treats the order
    as NOT placed and verifies rather than assuming success. Reading an unknown error as
    'already placed' would silently drop a real order and leave a leg naked.
    """
    if isinstance(err, dict):
        code = err.get("code")
        if isinstance(code, (int, float)) and int(code) in _DUP_CODES:
            return True
        text = str(err.get("msg", "") or err.get("message", ""))
    else:
        text = str(err)
    low = text.lower()
    if any(t in low for t in _DUP_TEXT):
        return True
    return any(str(c) in low for c in _DUP_CODES) and "duplicate" in low
