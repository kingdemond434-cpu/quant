"""MACRO & EVENT INTELLIGENCE -- arriving information becomes a forecast update, or it becomes
a recorded reason not to act. Nothing here trades; nothing here is a lookup table.

THE ORDER (principal, 2026-09-05): react to material public information the same minute it
arrives, across the whole MT5 universe -- "all world intelligence data news etc" -- and
"it should be with all current data and future macro gained added to this etc always so
intelligence grows not just hardcoded data."

WHAT THAT SENTENCE FORBIDS, CONCRETELY. A table mapping a headline class to an asset direction
is exactly what must not exist here, because it can only ever encode what was known the day it
was written. So four things that a news bot hardcodes are LEARNED in this package, each from the
desk's own accumulating ledger:

    the taxonomy          `taxonomy.py`    categories are discovered by clustering the record;
                                           an unrecognised event is RECORDED with wide
                                           uncertainty, never dropped, and becomes a category
                                           once instances accumulate
    source credibility    `credibility.py` a Beta hierarchy whose tier hyper-parameters are
                                           re-fit from member sources' measured verification
                                           record; the prior ordering is a starting point, not
                                           the answer
    what an event touches `factors.py`     category -> latent-factor loadings estimated from
                                           measured cross-asset reactions, admitted only past a
                                           multiplicity charge that never shrinks
    how it reaches us     `expression.py`  each tradeable instrument's measured sensitivity to
                                           each commodity/driver the desk quotes -- the
                                           terms-of-trade vector -- so a commodity event
                                           propagates through links that were measured rather
                                           than through links someone wrote down

THE FIFTH THING, WHICH IS THE ONE THAT SEPARATES THIS FROM A NEWS BOT. `priced.py` asks how much
of the information is ALREADY IN THE PRICE. A perfectly credible headline whose unpriced fraction
is zero must produce no allocation change at all; importance is multiplied by the unpriced
fraction, so that outcome is arithmetic rather than a rule someone remembered to write.

THE DIRECTION IS AN OBSERVATION, NEVER A SIGN TABLE. `surprise.py` computes the standardised
surprise against consensus, but the surprise sets the MAGNITUDE of the information only. The
SIGN comes from the measured cross-asset factor response. A hot CPI where real yields barely move
and the dollar sells off therefore does not produce a mechanical short-gold -- the measurement
says what the market is doing with the number, and the measurement wins. That case is pinned in
`desks/mt5/tests/test_macro_surprise_and_priced.py`.

NOTHING HERE DECIDES A WEIGHT. The package's output is a forecast delta per tradeable instrument
plus an honest uncertainty. The allocator's joint solve decides what that means for the book --
which is why there is deliberately NO "boost the opposite side" rule anywhere in this package: an
event that impairs one exposure may well impair its naive opposite too, and only the joint solve
can know. `interrupt.py` may ask the allocator to solve SOONER; it may never say what the answer
is, and it refuses to ask when the move it would buy is worth less than the turnover it costs.

CAPITAL AUTHORITY IS EARNED, NOT ASSUMED. Every assessment carries `capital_authority`, and it is
False until the event's category has survived point-in-time replay (`replay.py`) with n at or
above the floor. Until then the layer records, scores and reports -- which is the whole point,
because the record is what makes the rest learnable.

LAWFUL INFORMATION ONLY. Every ledger row carries its source, retrieval method, licence and the
robots/ToS verdict under which it was fetched. Material non-public information has no path into
this package: there is no field for it and no reader that would produce it.

Layout:

    schema.py       the event object; the ledger's on-disk contract
    ledger.py       append-only JSONL store, dedupe, novelty, category statistics
    sources.py      pluggable readers + the coverage map that NAMES the desk's blind spots
    taxonomy.py     open, discoverable categories (no closed enum, ever)
    credibility.py  hierarchical Bayesian source model, independence discount, contested branches
    prices.py       the thin price interface, its parquet implementation and its offline fake
    priced.py       priced versus unpriced
    surprise.py     standardised surprise, and interpretation from measurement not from sign
    factors.py      the learned factor basis and the learned category -> factor loadings
    expression.py   factor -> the instruments THIS desk can actually reach
    assess.py       the one call that turns a raw item into a scored, ledgered assessment
    interrupt.py    the allocator-interrupt contract (request only; the supervisor hook is spec'd)
    replay.py       point-in-time replay with a reader that RAISES on a future read
    attribution.py  the post-event loop that feeds every learned thing above
    run_macro_intel.py  the organ: one pass, or perpetual under the supervisor
"""

from __future__ import annotations

__all__ = ["SCHEMA_VERSION"]

SCHEMA_VERSION = 1
