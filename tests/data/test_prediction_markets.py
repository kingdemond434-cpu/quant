"""PREDICTION MARKETS -- 60 statements, untested, and the one place look-ahead is FREE to commit.

Polymarket is the funds-barred, solo-advantaged information domain the desk pulls to test
calibration and favorite-longshot bias: does the de-vigged market probability match the realised
outcome frequency? The whole study depends on ONE property, and it is trivially easy to break
without anything crashing:

    ONLY PRICES STRICTLY BEFORE RESOLUTION MAY BE USED.

A market's price converges to 0 or 1 as it resolves. Reading the price at or after settlement gives
a "forecast" that is the outcome, so calibration comes back perfect and the favorite-longshot bias
comes back at zero. Both are the shapes a working study produces -- which is exactly why an
untested `implied_prob_before` is more dangerous than a crash would be.

The other half is the resolved-market filter. A market that is closed but NOT umaResolutionStatus
='resolved', or whose outcome prices are not a clean {0,1} pair, has an ambiguous outcome; letting
it through puts a fractional "truth" into a binary calibration and quietly softens every bucket.
"""

from __future__ import annotations

import json
import time
from typing import Any

import pandas as pd
import pytest

from libs.data import prediction_markets as PM


def _market(**over) -> dict[str, Any]:
    m = {
        "question": "Will X happen?",
        "outcomes": json.dumps(["Yes", "No"]),
        "outcomePrices": json.dumps(["1", "0"]),
        "clobTokenIds": json.dumps(["tok_yes", "tok_no"]),
        "umaResolutionStatus": "resolved",
        "endDate": "2026-08-01T00:00:00Z",
        "startDate": "2026-06-01T00:00:00Z",
        "volumeNum": 12_345.0,
    }
    m.update(over)
    return m


def _stub(monkeypatch, batches: list[Any]):
    calls: list[str] = []

    def fake(url: str, *, tries: int = 4):
        calls.append(url)
        if not batches:
            return []
        nxt = batches.pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        return nxt

    monkeypatch.setattr(PM, "_get", fake)
    monkeypatch.setattr(time, "sleep", lambda _s: None)
    return calls


# ============================================================ the look-ahead rail

def _history(days_before_end: list[float], end: pd.Timestamp) -> pd.DataFrame:
    return pd.DataFrame({
        "ts": [end - pd.Timedelta(days=d) for d in days_before_end],
        "p": [0.1 * (10 - d) for d in days_before_end],
    }).sort_values("ts").reset_index(drop=True)


def test_the_price_used_is_STRICTLY_BEFORE_the_lead_cutoff() -> None:
    """THE PROPERTY THE WHOLE STUDY RESTS ON. A market's price converges to 0 or 1 as it resolves,
    so reading at or after settlement gives a 'forecast' that IS the outcome -- calibration comes
    back perfect and favorite-longshot bias comes back at zero, which are the shapes a WORKING
    study produces."""
    end = pd.Timestamp("2026-08-01", tz="UTC")
    hist = pd.DataFrame({
        "ts": [end - pd.Timedelta(days=10), end - pd.Timedelta(days=7),
               end - pd.Timedelta(days=1), end],
        "p": [0.40, 0.55, 0.95, 1.00],
    })
    got = PM.implied_prob_before(hist, end, lead_days=7.0)
    assert got == pytest.approx(0.55), "the 7-day lead must not see the 1-day or settlement price"


def test_a_ZERO_lead_still_excludes_nothing_after_the_end() -> None:
    """The boundary is inclusive at the cutoff and nothing later is reachable, so even lead_days=0
    cannot read a post-settlement print."""
    end = pd.Timestamp("2026-08-01", tz="UTC")
    hist = pd.DataFrame({"ts": [end - pd.Timedelta(hours=1), end + pd.Timedelta(hours=1)],
                         "p": [0.6, 1.0]})
    assert PM.implied_prob_before(hist, end, lead_days=0.0) == pytest.approx(0.6)


def test_a_market_with_NO_PRICE_before_the_cutoff_returns_None(monkeypatch) -> None:
    """None means 'no forecast at this horizon'. Falling back to the nearest available price would
    silently substitute a shorter lead -- and the shorter the lead, the better the calibration,
    so the substitution flatters the result in exactly one direction."""
    end = pd.Timestamp("2026-08-01", tz="UTC")
    hist = pd.DataFrame({"ts": [end - pd.Timedelta(days=1)], "p": [0.9]})
    assert PM.implied_prob_before(hist, end, lead_days=30.0) is None


def test_an_EMPTY_history_returns_None_rather_than_a_default() -> None:
    assert PM.implied_prob_before(pd.DataFrame(), pd.Timestamp("2026-08-01", tz="UTC"),
                                  lead_days=7.0) is None


def test_the_LAST_price_before_the_cutoff_is_taken_not_the_first() -> None:
    """The most recent forecast available at that horizon is the forecast. Taking the first would
    use a price from the market's opening, which is a different (and much worse) forecast."""
    end = pd.Timestamp("2026-08-01", tz="UTC")
    hist = _history([30.0, 20.0, 8.0, 2.0], end)
    got = PM.implied_prob_before(hist, end, lead_days=7.0)
    assert got == pytest.approx(float(hist[hist["ts"] <= end - pd.Timedelta(days=7)]["p"].iloc[-1]))


def test_a_LONGER_lead_can_only_move_the_price_EARLIER() -> None:
    """Monotonic by construction, and worth pinning: if a longer lead ever returned a later price
    the horizon axis of the study would be meaningless."""
    end = pd.Timestamp("2026-08-01", tz="UTC")
    hist = _history([30.0, 20.0, 10.0, 3.0, 1.0], end)
    seen = [PM.implied_prob_before(hist, end, lead_days=d) for d in (1.0, 5.0, 15.0, 25.0)]
    finite = [v for v in seen if v is not None]
    assert finite == sorted(finite, reverse=True), (
        "prices rise toward resolution here, so longer leads must return LOWER values")


# ============================================================ the resolved filter

def test_only_CLEANLY_RESOLVED_binary_markets_are_returned(monkeypatch) -> None:
    """A closed-but-unresolved market has an AMBIGUOUS outcome. Letting it through puts a
    fractional truth into a binary calibration and softens every bucket."""
    _stub(monkeypatch, [[
        _market(question="clean yes"),
        _market(question="clean no", outcomePrices=json.dumps(["0", "1"])),
        _market(question="unresolved", umaResolutionStatus="pending"),
        _market(question="ambiguous prices", outcomePrices=json.dumps(["0.5", "0.5"])),
        _market(question="not binary", outcomes=json.dumps(["A", "B", "C"])),
        _market(question="one token", clobTokenIds=json.dumps(["only_one"])),
    ], []])
    got = {m["question"] for m in PM.fetch_resolved_markets()}
    assert got == {"clean yes", "clean no"}


def test_the_OUTCOME_is_1_when_YES_won_and_0_when_NO_won(monkeypatch) -> None:
    """The single most invertible field in the file. Flipping it turns a well-calibrated market
    into a perfectly anti-calibrated one, and the study would report a huge exploitable bias."""
    _stub(monkeypatch, [[
        _market(question="yes won", outcomePrices=json.dumps(["1", "0"])),
        _market(question="no won", outcomePrices=json.dumps(["0", "1"])),
    ], []])
    by_q = {m["question"]: m["outcome"] for m in PM.fetch_resolved_markets()}
    assert by_q == {"yes won": 1.0, "no won": 0.0}


def test_the_YES_TOKEN_is_the_FIRST_clob_id(monkeypatch) -> None:
    """It must pair with the YES outcome above. Taking the second would fetch the NO-token history
    and compare a NO price against a YES outcome -- perfectly anti-calibrated, silently."""
    _stub(monkeypatch, [[_market()], []])
    assert PM.fetch_resolved_markets()[0]["yes_token"] == "tok_yes"


@pytest.mark.parametrize("field", ["outcomes", "outcomePrices", "clobTokenIds"])
def test_an_UNPARSEABLE_json_field_skips_the_market_not_the_batch(monkeypatch, field) -> None:
    """These arrive as JSON-encoded strings inside JSON. One malformed market must not cost the
    other 499 in the page."""
    _stub(monkeypatch, [[_market(**{field: "{not json"}), _market(question="fine")], []])
    assert [m["question"] for m in PM.fetch_resolved_markets()] == ["fine"]


def test_a_MISSING_field_skips_the_market(monkeypatch) -> None:
    _stub(monkeypatch, [[_market(outcomes=None), _market(question="fine")], []])
    assert [m["question"] for m in PM.fetch_resolved_markets()] == ["fine"]


def test_PAGINATION_advances_and_stops_on_an_empty_page(monkeypatch) -> None:
    calls = _stub(monkeypatch, [[_market(question="p1")], [_market(question="p2")], []])
    got = PM.fetch_resolved_markets()
    assert [m["question"] for m in got] == ["p1", "p2"]
    assert "offset=0" in calls[0] and "offset=500" in calls[1]


def test_the_API_PAGINATION_CAP_returns_what_was_collected(monkeypatch) -> None:
    """Polymarket answers 422 past its cap. Raising there would discard a complete first page
    because the second one did not exist."""
    _stub(monkeypatch, [[_market(question="p1")], RuntimeError("GET failed: 422")])
    assert [m["question"] for m in PM.fetch_resolved_markets()] == ["p1"]


def test_max_markets_is_HONOURED_as_a_hard_cap(monkeypatch) -> None:
    _stub(monkeypatch, [[_market(question=f"q{i}") for i in range(10)], []])
    assert len(PM.fetch_resolved_markets(max_markets=3)) == 3


def test_markets_are_requested_HIGHEST_VOLUME_FIRST(monkeypatch) -> None:
    """A calibration study on the thinnest markets measures the spread, not the forecast. The
    ordering is part of the sample definition."""
    calls = _stub(monkeypatch, [[], []])
    PM.fetch_resolved_markets()
    assert "order=volumeNum" in calls[0] and "ascending=false" in calls[0]
    assert "closed=true" in calls[0]


def test_an_unparseable_VOLUME_defaults_to_zero_rather_than_dropping_the_market(
        monkeypatch) -> None:
    """Volume is a weight, not a validity condition. Dropping the market would remove a clean
    resolved outcome for a cosmetic field."""
    _stub(monkeypatch, [[_market(volumeNum=None)], []])
    got = PM.fetch_resolved_markets()
    assert len(got) == 1 and got[0]["volume"] == 0.0


# ============================================================ price history

def test_price_history_parses_epoch_seconds_into_UTC(monkeypatch) -> None:
    monkeypatch.setattr(PM, "_get", lambda url, tries=4: {
        "history": [{"t": 1767225600, "p": "0.42"}, {"t": 1767312000, "p": "0.55"}]})
    df = PM.fetch_price_history("tok")
    assert list(df["p"]) == [0.42, 0.55]
    assert str(df["ts"].dt.tz) == "UTC"


@pytest.mark.parametrize("payload", [{}, {"history": []}, [], None, "unexpected"])
def test_price_history_returns_an_EMPTY_FRAME_on_a_degraded_payload(monkeypatch,
                                                                    payload) -> None:
    """An empty frame flows into `implied_prob_before` and returns None -- 'no forecast'. A
    fabricated row would become a forecast nobody made."""
    monkeypatch.setattr(PM, "_get", lambda url, tries=4: payload)
    assert PM.fetch_price_history("tok").empty


def test_the_history_request_names_the_token_and_the_fidelity(monkeypatch) -> None:
    seen: list[str] = []
    monkeypatch.setattr(PM, "_get", lambda url, tries=4: seen.append(url) or {"history": []})
    PM.fetch_price_history("tok_yes", fidelity=60)
    assert "market=tok_yes" in seen[0] and "fidelity=60" in seen[0]
    assert "interval=max" in seen[0]


# ============================================================ the fetcher

def test_the_fetcher_retries_then_raises_with_the_url(monkeypatch) -> None:
    monkeypatch.setattr(PM.urllib.request, "urlopen",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("down")))
    monkeypatch.setattr(time, "sleep", lambda _s: None)
    with pytest.raises(RuntimeError, match="GET failed"):
        PM._get("https://example.test/x")


def test_no_test_in_this_file_reaches_the_network(monkeypatch) -> None:
    """A calibration suite that hit Polymarket would be rate-limited, flaky, and would start
    passing for the wrong reason the day the venue changed a field."""
    def forbidden(*a, **k):
        raise AssertionError("a test reached the network")

    monkeypatch.setattr(PM.urllib.request, "urlopen", forbidden)
    monkeypatch.setattr(PM, "_get", lambda url, tries=4: {"history": []})
    assert PM.fetch_price_history("tok").empty
