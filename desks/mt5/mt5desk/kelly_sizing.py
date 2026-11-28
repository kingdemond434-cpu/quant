"""The gold book's sizes from the survival-constrained growth solve, read for both venues.

`research/kelly_survival.py` writes `reports/KELLY_SURVIVAL.json` hourly (principal 2026-09-30:
"maximum aggressiveness within survival"). `prop/e8_gold.py` reads its `e8` block; the Fusion
gateway reads its `fusion` block. Kept out of `decision_core` so the gateway's re-export surface
does not grow a name only the sizing readers use.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

#: How old `reports/KELLY_SURVIVAL.json` may be before the gold book stops obeying it. Two hours:
#: the solve runs on the hourly cycle, so this is one missed run plus the run in flight.
KELLY_SURVIVAL_MAX_AGE_S = 7200


def load_kelly_survival(path: Path, venue: str, now: datetime | None = None,
                        max_age_s: float = KELLY_SURVIVAL_MAX_AGE_S) -> dict[str, float] | None:
    """Per gold window, the size the survival-constrained Kelly solve chose for `venue`, or None.

    `research/kelly_survival.py` writes it (principal 2026-09-30: "maximum aggressiveness within
    survival"). Fusion values are LOTS, E8 values are RISK FRACTIONS of equity; 0 means the
    window stands aside because trading it lowers growth or breaks survival at any size the
    venue can send.

    NONE -- TODAY'S SIZING, UNCHANGED -- when the file is absent, unreadable, older than
    `max_age_s`, or the venue's solve did not reach an OK status. A stale solve is a claim about
    an equity and a posterior that have moved, and the fallback is the book the desk ran before
    this organ existed, never a flat account.
    """
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(doc, dict):
        return None
    try:
        made = datetime.fromisoformat(str(doc.get("generated_at")))
    except ValueError:
        return None
    if made.tzinfo is None:
        made = made.replace(tzinfo=UTC)
    age = ((now or datetime.now(tz=UTC)) - made).total_seconds()
    if not (0 <= age <= max_age_s):
        return None
    block = doc.get(venue)
    if not isinstance(block, dict) or block.get("status") != "OK":
        return None
    key = "lots" if venue == "fusion" else "risk_frac"
    out: dict[str, float] = {}
    for w, row in (block.get("windows") or {}).items():
        try:
            v = float(row[key])
        except (KeyError, TypeError, ValueError):
            return None
        if v != v or v < 0:
            return None
        out[str(w)] = v
    return out or None


#: The principal-set certified sleeve book (principal 2026-10-06/07: "put the max-growth sleeve
#: books live"). Data with an author and a date, read by the Fusion gateway and the E8 lanes.
CERT_BOOK_FILE = Path(__file__).resolve().parents[1] / "data" / "CERT_BOOK_LIVE.json"

#: KEYS THE CODE OPENS OVER THE BOX'S BOOK (2026-11-18, zuck: "this strat is fr everyday ... fr
#: all" -- E8, FTMO and Fusion are meant to trade every market day; the E8 calendar showed 7 of 12
#: November market days traded, one gold trade a day at most). CERT_BOOK_LIVE.json is box state
#: (libs/ops/release.STATE_PREFIXES): an origin edit to it is reverted by the box's next push, and
#: no organ writes its `e8` block, so the opening lives here, in code, where adoption carries it.
#:
#: E8 USDJPY session_range_breakout (asia, rr=2.5 wait_bars=12) at 0.004: the principal's approved
#: target (CERT_BOOK_LIVE `e8_pending`, decision card 2026-10-14 "Add USDJPY"), held at 0.0 only
#: until its lineage cleared -- the Reddit-origin ban was lifted 2026-10-13 and built 2026-11-11
#: (live_sleeve_policy `reddit_origin_lifted`), which left the explicit 0.0 as the last door.
#: Evidence: forward clock USDJPY.asia#rr=2.5 n=40 since 2026-09-18, +0.061R/trade, +2.43R cum
#: (reports/shadow/shadow_state.json, 2026-11-18); certified 2,107-day backtest under 3x costs,
#: CPCV OOS Sharpe 0.163, DSR 1.00, forward t 2.6 at promotion; gold vs the yen block -0.117, so
#: it is a second independent bet, not more gold. It fires on 40 of the ~43 market days since
#: 2026-09-18, which is what makes E8 trade daily. Worst day with gold_asia: 0.006 + 0.004 = 1.0%
#: of equity against E8's 2.5% daily limit. Every other door still binds (principal exclusions,
#: replication, the Tier S door, E8_CERT_CEILING, the daily guard). Journal D-20261118-001.
#:
#: FTMO, the same sleeve at the same 0.004 CAP (coordinator 2026-11-18, on zuck's "fr all": FTMO's
#: follower copies only E8's gold_asia fill and its sleeve executor had nothing funded). This is a
#: CEILING, not a size: prop/ftmo_executor.book_sleeves sends min(block, the FTMO allocator's own
#: solve this pass) and nothing without the allocator's published spec and a fresh deployable
#: report, so the allocator still decides whether and how much; the overlay only stops the box's
#: unarmed or stale `ftmo` block from standing the sleeve down. Worst FTMO day with the gold copy:
#: 0.009 + 0.004 = 1.3% against the 2-Step 5% daily / 10% max (the executor re-tests both rails
#: on the whole book before every send). Tier S door on the committed state: block() -> None.
#: Removing a key here closes it again; a positive value in the file always wins.
CODE_BOOK_OPEN: dict[str, dict[str, float]] = {
    "e8": {"USDJPY_session_range_breakout_asia": 0.004},
    "ftmo": {"USDJPY_session_range_breakout_asia": 0.004},
}


def load_cert_book(path: Path, venue: str) -> dict[str, float] | None:
    """{book key: risk fraction of equity} for `venue` ("fusion" or "e8") from the certified
    sleeve book, or None.

    The keys are the allocator's own (`SYMBOL_family_selector`, or a gold window `gold_asia`), so
    the gateway lays them over the allocator's book with no translation. A key the file does not
    name keeps whatever the allocator set.

    NONE -- TODAY'S SIZING, UNCHANGED -- when the file is absent, unreadable, `enabled` is not
    true, the venue block is missing, or ANY value is not a number in [0, MAX_RISK_FRAC]. One bad
    entry voids the whole block: a half-read book would size some legs from the principal's
    table and their siblings from the allocator, which is neither.
    """
    from mt5desk.sizing import MAX_RISK_FRAC
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(doc, dict) or doc.get("enabled") is not True:
        return None
    block = doc.get(venue)
    if not isinstance(block, dict) or not block:
        return None
    out: dict[str, float] = {}
    for key, raw in block.items():
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            return None
        v = float(raw)
        if v != v or not 0.0 <= v <= MAX_RISK_FRAC:
            return None
        out[str(key)] = v
    # THE CODE-SIDE OPENINGS (CODE_BOOK_OPEN, above). Laid over a VALID block only: a void book
    # stays void, so this can never open a venue the file has stood down. It only lifts a key
    # the file holds at 0.0 or does not name -- a positive file value always stands.
    for key, v in CODE_BOOK_OPEN.get(venue, {}).items():
        if out.get(key, 0.0) == 0.0 and 0.0 < v <= MAX_RISK_FRAC:
            out[key] = v
    return out
