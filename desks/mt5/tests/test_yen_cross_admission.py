"""THE ONE YEN CROSS, ON BOTH BOOKS, AND THE TWO DEFECTS THAT PUT THE WRONG ONE THERE.

The principal's order of 2026-09-24 lifted the live account's gold-only restriction and added ONE
yen cross to both accounts -- "the best of the four" on MAXIMUM GROWTH, not on mean R -- because
EURJPY against GBPJPY measures +0.891 and four yen crosses are barely two independent bets, while
gold against that block is -0.117.

Each test here pins a mistake that was actually made while implementing it, not a hypothetical.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK), str(DESK / "prop"), str(DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import live_policy as lp  # noqa: E402
from prop import e8_book as bk  # noqa: E402

CHOSEN_MT5 = "usdjpy_session_range_breakout_asia_rr25_wb12"


# --------------------------------------------------------------------- the live policy's door

def _policy(tmp_path: Path, doc: dict) -> lp.Policy:
    p = tmp_path / "live_sleeve_policy.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    return lp.policy(p)


#: The E8 catalogue is the box's own artifact (written by the E8 builder from the box's bars and
#: never committed), so the four book-level checks run where it exists and say so where it
#: does not -- a skip that names the missing evidence, never a pass on nothing.
_NEEDS_CATALOGUE = pytest.mark.skipif(
    not (DESK / "data" / "e8_catalogue.json").exists(),
    reason="UNMEASURED: data/e8_catalogue.json is box-only; run this check on the trading box")


def test_symbol_allowlist_alone_would_admit_every_rr_variant(tmp_path: Path) -> None:
    """THE HOLE `live_sleeves` EXISTS TO CLOSE. Admitting the SYMBOL admits every certified
    parameter set on it -- USDJPY holds rr=1.5, rr=2.0 and rr=2.5 -- and three rr variants of one
    breakout on one instrument reproduce the concentration the order exists to avoid, one level
    down. Without the allowlist all three pass; that is the defect, asserted so it cannot return.
    """
    pol = _policy(tmp_path, {"live_symbols": ["XAUUSD", "USDJPY"]})
    for name in (CHOSEN_MT5, "usdjpy_session_range_breakout_asia_5_wb_12",
                 "usdjpy_session_range_breakout_asia_session_range_breakout"):
        assert lp.refuse({"symbol": "USDJPY", "name": name, "family": "session_range_breakout"},
                         pol) is None


def test_allowlist_admits_only_the_chosen_sleeve(tmp_path: Path) -> None:
    pol = _policy(tmp_path, {"live_symbols": ["XAUUSD", "USDJPY"],
                             "live_sleeves": {"USDJPY": [CHOSEN_MT5]}})
    row = {"symbol": "USDJPY", "name": CHOSEN_MT5, "family": "session_range_breakout"}
    assert lp.refuse(row, pol) is None
    for other in ("usdjpy_session_range_breakout_asia_5_wb_12",
                  "usdjpy_session_range_breakout_asia_session_range_breakout"):
        why = lp.refuse({**row, "name": other}, pol)
        assert why is not None and "different parameter set" in why


def test_gold_is_untouched_by_the_allowlist(tmp_path: Path) -> None:
    """A symbol ABSENT from `live_sleeves` is unrestricted. Gold's allocation is not this
    change's business and every gold row must still admit exactly as before."""
    pol = _policy(tmp_path, {"live_symbols": ["XAUUSD", "USDJPY"],
                             "live_sleeves": {"USDJPY": [CHOSEN_MT5]}})
    for name in ("gold_london_am_v2", "gold_afternoon_v4", "xau_m5_anti_breakout_overlap"):
        assert lp.refuse({"symbol": "XAUUSD", "name": name}, pol) is None


def test_an_empty_allowlist_admits_nothing_rather_than_everything(tmp_path: Path) -> None:
    """The one reading that could turn a truncated edit into an unrestricted symbol."""
    pol = _policy(tmp_path, {"live_symbols": ["XAUUSD", "USDJPY"],
                             "live_sleeves": {"USDJPY": []}})
    assert lp.refuse({"symbol": "USDJPY", "name": CHOSEN_MT5}, pol) is not None


def test_the_discovered_ban_and_the_m15_ban_still_bind(tmp_path: Path) -> None:
    """Both stand permanently and neither is this order's to relax. M15 is banned desk-wide via
    the "*" default, so it must bind on the NEW symbol too, not only on gold."""
    pol = _policy(tmp_path, {"live_symbols": ["XAUUSD", "USDJPY"],
                             "live_sleeves": {"USDJPY": [CHOSEN_MT5]}})
    assert lp.refuse({"symbol": "USDJPY", "name": CHOSEN_MT5, "family": "discovered"},
                     pol) is not None
    assert lp.refuse({"symbol": "USDJPY", "name": CHOSEN_MT5, "timeframe": "M15"},
                     pol) is not None


def test_an_unreadable_policy_still_falls_back_to_gold_only(tmp_path: Path) -> None:
    """FAIL-CLOSED is unchanged: a truncated file must not put the wider universe into a live
    account at 3am, and adding `live_sleeves` must not have opened that path."""
    p = tmp_path / "live_sleeve_policy.json"
    p.write_text("{not json", encoding="utf-8")
    pol = lp.policy(p)
    assert pol.live_symbols == lp.DEFAULT_LIVE_SYMBOLS
    assert lp.refuse({"symbol": "USDJPY", "name": CHOSEN_MT5}, pol) is not None


def test_the_shipped_policy_file_admits_the_authorized_universe_with_mechanism_fences() -> None:
    """The artifact itself, as it will be read on the box."""
    f = DESK / "data" / "live_sleeve_policy.json"
    if not f.exists():                      # the box writes its own; absent on a fresh clone
        pytest.skip("no live_sleeve_policy.json in this checkout")
    pol = lp.policy(f)
    assert pol.live_symbols == frozenset({"*"})
    assert "discovered" in pol.banned_families
    assert lp.refuse({"symbol": "USDJPY", "name": CHOSEN_MT5}, pol) is None
    assert lp.refuse({"symbol": "EURJPY", "name": "eurjpy_session_range_breakout_asia_0_wb_12"},
                     pol) is None
    assert lp.refuse({"symbol": "EURJPY", "family": "discovered"}, pol) is not None


# ------------------------------------------------------------------- E8's correlation block

def test_block_of_matches_a_currency_leg_not_a_substring() -> None:
    """An index whose ticker merely contains the letters must not be swept into a currency
    block it has nothing to do with."""
    assert bk.block_of("USDJPY") == "JPY"
    assert bk.block_of("AUDJPY") == "JPY"
    assert bk.block_of("XAUUSD") is None
    assert bk.block_of("JPYINDEX") is None


def test_growth_score_uses_the_measured_distribution_not_a_fixed_r_bet() -> None:
    """THE MODEL THIS REPLACED WAS WRONG AND WOULD HAVE RANKED ON FICTION. The first version
    assumed a session_range_breakout resolves at its rr target or its -1R stop and backed the win
    rate out as (e+1)/(rr+1), giving USDJPY rr=2.0 a 36.0% hit rate. The trades exit on a TTL
    clock at arbitrary R and the MEASURED rate is 53.66%. Pin that the score now tracks the
    measured file: a cell with no row there is unscorable, never scored zero.
    """
    m = bk._measured()
    assert m[("USDJPY", "session_range_breakout", 2.0, 12.0)]["win_rate"] == pytest.approx(0.5366)
    unparameterised = {"symbol": "USDJPY", "family": "session_range_breakout",
                       "params": {}, "ev": 0.1641, "exp_x3": 0.0853}
    assert bk.growth_score(unparameterised) is None


def test_growth_ranks_usdjpy_first_and_cadjpy_last_of_the_four() -> None:
    """THE HONEST RANKING IS NOT THE RAW ONE, and this is the assertion that says so. On raw
    shadow mean R the order was USDJPY +0.7327, CADJPY +0.4103, EURJPY +0.2650, GBPJPY +0.1624 --
    CADJPY second. Under the 3x cost stress CADJPY is LAST: it gives up 62% of its expectancy
    against USDJPY's 48%, which is the caution about a twice-corrected cost model doing work
    rather than being noted.
    """
    rows = {r["key"]: r for r in bk._load_survivors()}
    scored = {sym: bk.growth_score(rows[f"external.{sym}.session_range_breakout.rr={rr}_wb=12"])
              for sym, rr in (("USDJPY", 2.5), ("EURJPY", 2.0),
                              ("GBPJPY", 2.5), ("CADJPY", 2.0))}
    assert all(v is not None for v in scored.values())
    assert max(scored, key=lambda k: scored[k]) == "USDJPY"
    assert min(scored, key=lambda k: scored[k]) == "CADJPY"


@_NEEDS_CATALOGUE
def test_the_e8_book_holds_exactly_one_yen_cross_and_it_is_usdjpy() -> None:
    """Measured 2026-09-24 BEFORE this rule: the book held USDJPY, CADJPY, EURJPY and GBPJPY on
    `session_range_breakout` at once -- four of eight slots on about 1.1 independent bets."""
    cat = json.loads((DESK / "data" / "e8_catalogue.json").read_text(encoding="utf-8"))
    doc = bk.select(tradeable=set(cat["instruments"]))
    jpy = [s for s in doc["sleeves"] if bk.block_of(s["symbol"]) == "JPY"]
    assert len(jpy) == 1, [s["symbol"] for s in jpy]
    assert jpy[0]["symbol"] == "USDJPY"
    assert doc["n_blocked_by_correlation"] == 3


@_NEEDS_CATALOGUE
def test_the_block_survivor_is_a_parameterised_cell_not_the_unsuffixed_one() -> None:
    """THE DEFECT THAT PUT EURJPY IN THE BOOK. The dedup ranked on `ev`, so USDJPY resolved to
    its unsuffixed certificate -- the highest `ev` of the five, carrying no rr and no wait_bars,
    therefore unscorable for growth. The correlation rule could not rank it and handed the JPY
    slot to EURJPY, the third-best cross. Params are part of the identity; assert the survivor
    carries them.
    """
    cat = json.loads((DESK / "data" / "e8_catalogue.json").read_text(encoding="utf-8"))
    doc = bk.select(tradeable=set(cat["instruments"]))
    jpy = next(s for s in doc["sleeves"] if bk.block_of(s["symbol"]) == "JPY")
    assert (jpy["params"].get("params") or {}).get("rr") is not None
    assert bk.growth_score(jpy) is not None


@_NEEDS_CATALOGUE
def test_the_new_symbol_carries_exactly_one_sleeve_on_each_book() -> None:
    """WHAT THE NO-HEDGE-COLLISION PROTECTION ACTUALLY RESTS ON FOR THIS SLEEVE, and it is not
    the agreeing/opposing rule.

    That rule (`prop/e8_gold.OPPOSING_LEG`) guards a TWO-SIDED stop bracket and lives inside the
    gold-only lane; it does not run on MT5 at all and does not cover a non-gold symbol on E8.
    A yen cross is not exposed to it because it cannot self-hedge in the first place: MT5 enforces
    single-position discipline PER SLEEVE (`gateway._sleeve_positions`), E8 places one market
    order per signal, so two opposing positions on one symbol require TWO sleeves on that symbol.
    The allowlist and the correlation rule each guarantee exactly one. THAT is the invariant the
    protection reduces to here, so it is the one pinned -- if a second USDJPY sleeve is ever
    admitted, this fails and the directional rule genuinely has to be generalised first.
    """
    f = DESK / "data" / "live_sleeve_policy.json"
    if f.exists():
        pol = lp.policy(f)
        for sym in pol.live_symbols:
            if sym == "XAUUSD":
                continue
            allowed = pol.live_sleeves.get(sym)
            assert allowed is not None and len(allowed) == 1, (
                f"{sym} may hold more than one sleeve; the no-hedge-collision argument for a "
                f"non-gold symbol depends on there being exactly one")
    cat = json.loads((DESK / "data" / "e8_catalogue.json").read_text(encoding="utf-8"))
    doc = bk.select(tradeable=set(cat["instruments"]))
    per_symbol: dict[str, int] = {}
    for s in doc["sleeves"]:
        per_symbol[s["symbol"]] = per_symbol.get(s["symbol"], 0) + 1
    assert per_symbol.get("USDJPY", 0) == 1


def test_the_give_back_protections_are_symbol_neutral_on_a_jpy_price_scale() -> None:
    """THE PROTECTIONS WERE WRITTEN AGAINST GOLD'S OWN PATH, so exercise them where gold's
    numbers would hide a defect: a JPY cross quotes 3 digits around 157, not 2 digits around 4280,
    and its round-trip cost per price unit is a different order of magnitude. Both the 0.85R
    costed floor and the stop-side guard must behave identically on that scale.
    """
    from mt5desk import position_manager as pm

    entry, dist, cost = 157.250, 0.420, 0.004      # long USDJPY, 42-pip stop, real round trip
    # Below 0.85R NET of the round trip the floor must NOT arm; above it, it must.
    assert not pm.breakeven_armed(entry=entry, extreme=entry + 0.85 * dist - 0.02,
                                  stop_distance=dist, side=1, cost_per_unit=cost, spread=0.012)
    assert pm.breakeven_armed(entry=entry, extreme=entry + 1.10 * dist, stop_distance=dist,
                              side=1, cost_per_unit=cost, spread=0.012)
    # COSTED, NOT "BREAK EVEN MEANS ENTRY": a long's floor sits ABOVE entry by the round trip,
    # which is the whole difference between a scratch and a small loss on every scratch.
    level = pm.breakeven_level(entry=entry, side=1, cost_per_unit=cost)
    assert level > entry
    assert level == pytest.approx(entry + cost)
    assert pm.breakeven_level(entry=entry, side=-1, cost_per_unit=cost) < entry


def test_stop_rests_at_venue_refuses_the_wrong_side_on_a_jpy_cross() -> None:
    """THE DEFECT THAT COST 0.78R. A level behind the market is not a tight stop, it is a market
    exit -- MetaTrader answers 10016 and changes nothing, TradeLocker FILLS it (E8 position
    360287970193246861, 386.08 USD). One predicate answers both halves on both venues, and it
    must do so on a JPY quote as readily as on gold's.
    """
    from mt5desk import position_manager as pm

    bid, ask = 157.402, 157.416
    assert pm.stop_rests_at_venue(stop=157.200, side=1, bid=bid, ask=ask)[0]
    assert not pm.stop_rests_at_venue(stop=157.600, side=1, bid=bid, ask=ask)[0]
    assert pm.stop_rests_at_venue(stop=157.600, side=-1, bid=bid, ask=ask)[0]
    assert not pm.stop_rests_at_venue(stop=157.200, side=-1, bid=bid, ask=ask)[0]
    # The venue's own minimum distance still binds on top of the side test.
    assert not pm.stop_rests_at_venue(stop=157.399, side=1, bid=bid, ask=ask,
                                      min_distance=0.050)[0]


def test_both_venues_reach_the_same_two_guards() -> None:
    """ONE CODE PATH HAS REPEATEDLY FAILED TO COVER BOTH ACCOUNTS, so assert the call sites exist
    rather than assuming. MetaTrader is `mt5desk/gateway.py`; TradeLocker is `prop/e8_executor.py`
    (all symbols) and `prop/e8_gold.py` (the gold windows)."""
    gw = (DESK / "mt5desk" / "gateway.py").read_text(encoding="utf-8")
    ex = (DESK / "prop" / "e8_executor.py").read_text(encoding="utf-8")
    gold = (DESK / "prop" / "e8_gold.py").read_text(encoding="utf-8")
    for src, who in ((gw, "MT5 gateway"), (ex, "E8 executor"), (gold, "E8 gold")):
        assert "stop_rests_at_venue" in src, f"{who} does not reach the stop-side guard"
    # The break-even floor: the gateway ratchets with a costed floor, the E8 executor runs the
    # floor alone. Both must name the shared trigger rather than carrying a private copy.
    assert "cost_per_unit=cost_unit" in gw or "cost_per_unit=" in gw
    assert "BREAKEVEN_TRIGGER_R" in ex
    # The MT5 floor must iterate the ROSTER's symbols, not a gold literal alone, or a promoted
    # non-gold sleeve would be placed and then never stop-managed.
    assert 's["symbol"] for s in sleeves' in gw


@_NEEDS_CATALOGUE
def test_an_unmeasured_concentration_is_published_not_acted_on() -> None:
    """The book also holds three CHF crosses on one mechanism. The desk has MEASURED the yen
    correlation and has NOT measured that one, and cutting on an assumed correlation would be the
    un-evidenced shrink Growth Governance Rule 1 refuses. It must be visible instead."""
    cat = json.loads((DESK / "data" / "e8_catalogue.json").read_text(encoding="utf-8"))
    doc = bk.select(tradeable=set(cat["instruments"]))
    chf = [s for s in doc["sleeves"]
           if len(s["symbol"]) == 6 and s["symbol"][3:] == "CHF"]
    if len(chf) > 1:
        assert any("CHF" in b for b in doc["unmeasured_blocks"])


def test_the_clock_key_the_promoter_writes_is_admitted() -> None:
    """The promoter names a LIVE row by its forward clock's key; rr=2.5/wb=12 on asia is
    `USDJPY.asia#rr=2.5` (wait_bars 12 is the window default). Admitting only an alias no
    writer produces would keep the approved sleeve off the live account forever."""
    pol = lp.policy(DESK / "data" / "live_sleeve_policy.json")
    row = {"name": "USDJPY.asia#rr=2.5", "symbol": "USDJPY", "family": "session_range_breakout"}
    assert lp.refuse(row, pol) is None
    other = {**row, "name": "USDJPY.asia#rr=1.5"}
    assert lp.refuse(other, pol), "a different rr on the same instrument stays refused"
