"""The MT5 universe mandate must reach the ORGANS' STANDING ORDERS, not just the query layer.

WHY THIS IS A TEST AND NOT A PROSE DUTY. On 2026-08-18 the principal made MT5/Fusion the desk's
sole traded universe and barred crypto-exchange venues from ever being hunted again. The migration
that followed retargeted the scorer and the miner QUERIES and was believed complete. Measured one
day later, NINE prompt surfaces still carried an ORDER pointing every seat at the retired book --
including a dated principal directive, superseded but never deleted, sitting in all seven regional
miner prompts with a priority ladder that ranked the desk's sole traded universe LAST. Seven daily
seats read it. A duty with no instrument is a wish (L1.46).

PRECISION OVER RECALL, DELIBERATELY. A broad token sweep is the wrong shape here and measuring it
proved so: 20 of 25 surfaces contain crypto tokens, but only 9 carried an order -- the other 11 are
HISTORICAL CITATIONS (incident forensics, graveyard entries, the WS-006 cost lesson) that must
survive untouched, because deleting the desk's own evidence to make a fence green is worse than the
defect. So this asserts on the SPECIFIC literal strings that were the orders, not on vocabulary. It
will not catch a novel rephrasing, and that is the correct trade: a fence that cries wolf gets
switched off, and a switched-off fence enforces nothing (L1.43).

WHAT IT DOES NOT DO. It does not ban the word "crypto" anywhere, and it must never be extended to.
Crypto remains legal in exactly one role -- an INFORMATION INPUT that informs an MT5 instrument
(a BTCUSD CFD call, a risk-sentiment read) -- and Fusion-executable crypto CFDs are part of the
MT5 universe. This fence only asserts that no surface ORDERS a seat to hunt crypto EXCHANGES.
"""

from __future__ import annotations

from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]

#: Surfaces that carry standing orders to an organ. Named explicitly rather than globbed: the same
#: distinction check_timidity_language draws, and for the same reason -- a coverage RECORD that
#: happens to quote an old order is not itself an order, and sweeping records into scope is how a
#: fence starts reporting defects against its own history.
_ORDER_SURFACES: tuple[str, ...] = (
    *(f"ops/frontier_{r}_prompt.txt" for r in ("en", "ru", "ar", "cn", "br", "kr", "jp")),
    "ops/brain_hunter_prompt.txt",
    "ops/litminer_dig_prompt.txt",
    "ops/prospector_dig_prompt.txt",
    "ops/dataaxis_dig_prompt.txt",
    "ops/blindrediscovery_dig_prompt.txt",
    "prompts/external_panel_prompt.txt",
    "prompts/deep_sweep_core.txt",
)

#: The literal orders removed on 2026-08-19 (commit 2c1692db), each paired with what it did. A
#: regression here means a merge resurrected a superseded principal directive -- the exact failure
#: this exists to make loud, since the last one survived a full migration unnoticed.
_BANNED_ORDERS: tuple[tuple[str, str], ...] = (
    ("BINANCE/CRYPTO PRIORITY",
     "the superseded 2026-08-07 directive block; its ladder ranked the sole traded universe LAST"),
    ("This desk trades Binance crypto",
     "states the retired book as the desk's universe"),
    ("crypto-native sources first",
     "orders seats to rank the banned universe above the traded one"),
    ("Venue: Binance spot",
     "anchored every paid panel seat to a retired venue, under a header saying violating the "
     "context constraints makes a recommendation worthless"),
    ("translate into crypto-compatible form",
     "points the extraction pipeline away from the traded book"),
)


@pytest.mark.parametrize("rel", _ORDER_SURFACES)
def test_NO_STANDING_ORDER_POINTS_A_SEAT_AT_THE_BANNED_UNIVERSE(rel: str) -> None:
    """Principal's 2026-08-18 order: crypto EXCHANGES are never a hunt target again."""
    path = _ROOT / rel
    if not path.exists():
        pytest.skip(f"{rel} absent")
    text = path.read_text("utf-8", errors="ignore")
    for needle, why in _BANNED_ORDERS:
        assert needle not in text, (
            f"{rel} carries the banned order {needle!r} -- {why}. The principal's 2026-08-18 "
            f"standing order makes MT5/Fusion the sole traded universe. Repair UPWARD: repoint "
            f"the order at the MT5 universe (see the block in ops/frontier_en_prompt.txt), never "
            f"by deleting the surface or weakening the mandate."
        )


def test_THE_MT5_ORDER_ACTUALLY_REACHES_EVERY_REGIONAL_MINER() -> None:
    """The half a ban cannot express: absence of the old order is not presence of the new one.

    Nine surfaces were repaired by DELETING a block; a later merge could drop the replacement and
    leave a prompt with no universe instruction at all, which reads clean to the check above while
    telling seven daily seats nothing about what the desk trades. UNMEASURED is not OK (L1.28a).
    """
    missing = [
        rel for rel in (f"ops/frontier_{r}_prompt.txt"
                        for r in ("en", "ru", "ar", "cn", "br", "kr", "jp"))
        if (_ROOT / rel).exists()
        and "MT5 UNIVERSE PRIORITY" not in (_ROOT / rel).read_text("utf-8", errors="ignore")
    ]
    assert not missing, (
        f"{len(missing)} regional miner prompt(s) carry NO MT5 universe order: {missing}. A seat "
        f"with no universe instruction is not neutral -- it falls back on the model's own prior, "
        f"which is crypto-shaped for this desk's corpus."
    )
