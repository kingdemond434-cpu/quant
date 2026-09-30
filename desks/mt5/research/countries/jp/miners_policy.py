"""WHICH JAPAN MINERS MAY MINT WHAT, under the one lane router.

REBUILT IN GIT beside `countries/jp/pack.py` (see `mandate.py` for why not at
`research/japan/miners_policy.py`). One table, one door:

  * every miner declares the FAMILIES it mints and the instrument SCOPE it mints them on;
  * `may_mint` then asks `research.universe_policy.may_hypothesise(symbol, family)` -- the same
    two-lane door `merge_hypotheses` applies -- so a Japanese single name reaches the judge only
    through the news/earnings lane's own families or a cross-sectional class book, never through
    a statistical family, and an unclassified symbol reaches nothing;
  * every row a JP miner emits carries the culture provenance fields (principal, 2026-09-30):
    `source_culture`, `participant_structure`, `failure_mode_hypothesis`.

Nothing here judges, sizes or vetoes a cell the router admits; it names what each miner is FOR so
a miner minting outside its declaration is visible rather than silent.
"""
from __future__ import annotations

from typing import Any

UNMEASURED = "UNMEASURED"

#: miner -> families it mints, the instrument scope, and the culture fields its rows carry.
POLICY: dict[str, dict[str, Any]] = {
    "corporate_disclosure": {
        "families": ("event_reaction", "news_reaction", "exogenous_conditioner",
                     "exogenous_gate"),
        "scope": "JP single names (event lane) and their transmission instruments",
        "participant_structure": "retail_heavy",
        "failure_mode_hypothesis": (
            "TDnet releases land after the 15:00 JST close and Japanese retail fades them, so the "
            "reaction arrives in the next Tokyo session and fails when the Western reading of the "
            "same news is already priced")},
    "jquants": {
        "families": ("exogenous_conditioner", "exogenous_gate", "event_reaction"),
        "scope": "JPN225, USDJPY and the JP single names the broker quotes",
        "participant_structure": "retail_heavy",
        "failure_mode_hypothesis": (
            "a Japanese company's own forecast is conservative by custom, so a 'beat' against it "
            "is the norm and fails as a signal exactly when management stops sandbagging")},
    "boj_policy": {
        "families": ("event_reaction", "macro_conditional"),
        "scope": "the yen crosses and JPN225",
        "participant_structure": "policy_driven",
        "failure_mode_hypothesis": (
            "the BoJ pre-leaks through the press before a meeting, so the meeting-day reaction "
            "fails whenever the leak was complete, unlike a Fed decision")},
    "gotobi": {
        "families": ("fx_fixing_reversal", "calendar_month", "dow_effect"),
        "scope": "USDJPY and the yen crosses around the 09:55 JST Tokyo fix",
        "participant_structure": "mixed",
        "failure_mode_hypothesis": (
            "exporter settlement demand at the Tokyo fix is a domestic calendar the Western "
            "session does not share, and fails when banks pre-hedge it")},
    "carry_state": {
        "families": ("carry", "regime_transition", "drawdown_conditional"),
        "scope": "the yen crosses",
        "participant_structure": "retail_heavy",
        "failure_mode_hypothesis": (
            "retail margin carry unwinds in forced cascades at Tokyo hours, so the carry premium "
            "fails in bursts timed to Japanese margin calls rather than to US risk-off")},
}


def culture(miner: str) -> dict[str, str]:
    """The three culture fields for a row this miner emits. UNMEASURED for an undeclared miner."""
    p = POLICY.get(miner)
    if p is None:
        return {"source_culture": "JP", "participant_structure": UNMEASURED,
                "failure_mode_hypothesis": UNMEASURED}
    return {"source_culture": "JP", "participant_structure": str(p["participant_structure"]),
            "failure_mode_hypothesis": str(p["failure_mode_hypothesis"])}


def may_mint(miner: str, symbol: str, family: str) -> tuple[bool, str]:
    """(allowed, why). Declared family first, then the lane router; never a silent yes."""
    p = POLICY.get(miner)
    if p is None:
        return False, f"{miner!r} is not a declared Japan miner"
    if family not in p["families"]:
        return False, f"{miner} declares {', '.join(p['families'])}, not {family}"
    try:
        from research.universe_policy import lane, may_hypothesise
    except Exception as exc:                                   # noqa: BLE001
        return False, f"{UNMEASURED}: universe_policy unavailable ({type(exc).__name__})"
    if may_hypothesise(symbol, family):
        return True, f"universe_policy admits {family} on {symbol} (lane {lane(symbol)})"
    return False, f"universe_policy.lane({symbol!r}) = {lane(symbol)!r} refuses {family}"
