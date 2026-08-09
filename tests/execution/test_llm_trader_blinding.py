"""R0124 item (b): the BLINDING EXPERIMENT -- hide asset/exchange names behind placeholders.

"If performance collapses it was brand recognition, not reasoning. Cheapest decisive test of
whether the edge is real." (external critique, 2026-07-31)

WHY THESE TESTS ARE MOSTLY ABOUT LEAKS. A blinding experiment fails SILENTLY and in the flattering
direction: if the brand survives the mask, both arms score the same and the desk concludes the
sleeve reasons rather than recognises. The first draft of this blinder did exactly that -- masking
the collector's ticker whitelist left "Bitcoin ETFs log inflows", "Bitcoin's memory pool" and
"XBTUSD" fully legible in the first real brief. So the load-bearing tests here are the ones that
try to READ the blinded text, not the ones that check a placeholder appeared.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from itertools import pairwise

import pytest
from scripts.run_llm_trader import (
    _blind_brief,
    _unmask_symbol,
    blind_arm,
    blind_audit,
)

_BRIEF = {
    "generated": "2026-08-05T14:00:00+00:00",
    "sources": {
        "funding": ['{"symbol": "XBTUSD", "fundingRate": 9.6e-05}'],
        "announcements": [
            {"source": "cointelegraph", "title": "Bitcoin ETFs log inflows as cold wallet hack "
                                                 "reignites custody debate", "symbols": ["BTC"]},
            {"source": "coindesk", "title": "Ethereum validators exit queue hits record",
             "symbols": ["ETH"]},
            {"source": "okx", "title": "Binance to delist SOL perpetual", "symbols": ["SOL"]},
        ],
    },
}


@pytest.fixture
def blinded():
    return _blind_brief(_BRIEF)


# --- the leak tests: the whole point --------------------------------------------------------

def test_prose_asset_names_are_masked_not_only_tickers(blinded):
    """THE REGRESSION. Masking BTC while leaving 'Bitcoin' in the headline is not a blind."""
    text = json.dumps(blinded[0])
    for brand in ("bitcoin", "ethereum"):
        assert brand not in text.lower(), f"{brand!r} survived the mask -- the brief still reads"


def test_a_ticker_glued_to_its_quote_currency_is_masked(blinded):
    """XBTUSD defeated a bare \\b match: there is no word boundary between T and U."""
    assert "XBTUSD" not in json.dumps(blinded[0])


def test_venue_names_are_masked(blinded):
    text = json.dumps(blinded[0]).lower()
    for venue in ("cointelegraph", "coindesk", "okx", "binance"):
        assert venue not in text, f"{venue!r} survived -- venue brand is its own confound"


def test_the_audit_reports_a_clean_blind(blinded):
    """The falsifier runs at call time, not only here."""
    audit = blind_audit(blinded[0], blinded[1])
    assert audit["leaks"] == [], f"unexpected leaks: {audit['leaks']}"
    assert audit["clean"] is True


def test_the_audit_actually_catches_a_leak():
    """A falsifier that cannot fail is not a falsifier -- prove it fires on an unmasked brief."""
    audit = blind_audit(_BRIEF, {})
    assert audit["clean"] is False
    assert "bitcoin" in audit["leaks"] and "cointelegraph" in audit["leaks"]


# --- coherence of the anonymised brief ------------------------------------------------------

def test_one_asset_gets_exactly_one_placeholder_across_all_its_names(blinded):
    """XBT, BTC and 'Bitcoin' must collapse to the SAME placeholder. _KNOWN carries XBT as its own
    ticker while _ALIASES maps it to BTC; without the collision guard the brief would describe one
    asset as two, degrading the comparison for a reason unrelated to brand."""
    _, unmask = blinded
    assert sorted(v for v in unmask.values() if v in ("BTC", "XBT")) == ["BTC"]
    values = list(unmask.values())
    assert len(values) == len(set(values)), "no ticker may hold two placeholders"


def test_placeholders_carry_no_identity_across_windows():
    """ASSET_1 is positional, so the same asset need not keep the same number in another brief --
    that is the property that stops the model learning the code."""
    other = {"sources": {"a": ["ETH is up"]}}
    _, u1 = _blind_brief(_BRIEF)
    _, u2 = _blind_brief(other)
    assert u2["ASSET_1"] == "ETH"
    assert u1 != u2 or len(u1) == 1


# --- unmasking: the book still knows what was traded ----------------------------------------

def test_a_blinded_answer_maps_back_to_a_real_instrument(blinded):
    _, unmask = blinded
    ph = next(k for k, v in unmask.items() if v == "BTC")
    assert _unmask_symbol(ph, unmask) == "BTCUSDT"
    assert _unmask_symbol(ph + "USDT", unmask) == "BTCUSDT"


def test_an_unknown_placeholder_is_returned_unchanged_not_invented():
    """Rescuing a malformed answer by guessing a symbol is how a paper sleeve books a trade on an
    asset nobody named. Returned as-is so validate_call refuses it."""
    assert _unmask_symbol("ASSET_99", {"ASSET_1": "BTC"}) == "ASSET_99"
    assert _unmask_symbol("", {}) == ""


# --- the pre-registered arm ------------------------------------------------------------------

def test_the_arm_is_deterministic_in_the_clock_not_random_at_call_time():
    """A seed drawn with the brief in hand is a knob someone can turn after seeing the data. An
    index off the UTC window is reproducible by any later reader from the row's own timestamp."""
    t = datetime(2026, 8, 5, 12, tzinfo=UTC)
    assert blind_arm(t) == blind_arm(t), "assignment must be a pure function of the clock"


def test_the_two_arms_are_balanced_over_the_running_cadence():
    """4-hourly cron: an unbalanced split wastes half the experiment's power."""
    t0 = datetime(2026, 1, 1, tzinfo=UTC)
    arms = [blind_arm(t0 + timedelta(hours=4 * i)) for i in range(540)]
    assert arms.count("BLIND") == arms.count("CLEAR") == 270


def test_consecutive_windows_alternate_so_arms_see_the_same_news_regime():
    """Assigning in long blocks would confound the arm with the market regime it ran in."""
    t0 = datetime(2026, 3, 3, tzinfo=UTC)
    arms = [blind_arm(t0 + timedelta(hours=4 * i)) for i in range(12)]
    assert all(a != b for a, b in pairwise(arms)), arms
