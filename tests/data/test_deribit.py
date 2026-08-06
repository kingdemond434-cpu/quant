"""DERIBIT OPTIONS -- 55 statements, untested, and the only forward-looking family the desk has.

DVOL is crypto's VIX. The volatility risk premium -- implied minus subsequently realised -- is
structurally orthogonal to every perp, funding and flow signal the desk trades, which is exactly
why it is worth having and exactly why a parse error here is expensive: it would be the one axis
nobody can cross-check against another.

THE SKEW SIGN IS THE FILE'S ONE IRREVERSIBLE MISTAKE. Skew is OTM-put IV minus OTM-call IV, and
POSITIVE MEANS CRASH FEAR. Inverted, the desk reads maximum complacency at the moment the market
is paying most for downside protection -- and it reads it as a plausible number of a plausible
size, in the one family it has nothing to check against.

The second is the DTE filter. Options expiring inside a day have wild marks driven by pin risk and
near-zero time value; letting them set the ATM level makes the whole surface twitch on the expiry
cycle rather than on the market.
"""

from __future__ import annotations

import time

import pandas as pd
import pytest

from libs.data import deribit as DB

_T0 = 1_767_225_600_000


def _stub(monkeypatch, payload):
    seen: list[str] = []
    monkeypatch.setattr(DB, "_get", lambda url: seen.append(url) or payload)
    return seen


def _opt(exp: str, strike: float, kind: str, iv: float, spot: float = 100_000.0) -> dict:
    return {"instrument_name": f"BTC-{exp}-{int(strike)}-{kind}",
            "mark_iv": iv, "underlying_price": spot}


def _future_exp(days: int) -> str:
    return (pd.Timestamp.now(tz="UTC") + pd.Timedelta(days=days)).strftime("%d%b%y").upper()


# ============================================================ DVOL

def test_dvol_takes_the_CLOSE_of_each_candle(monkeypatch) -> None:
    """The row is [ts, open, high, low, close]. Taking the open would lag the index by one bar and
    taking the high would report a permanent upward bias in implied vol."""
    _stub(monkeypatch, {"result": {"data": [
        [_T0, 40.0, 60.0, 35.0, 50.0],
        [_T0 + 43_200_000, 50.0, 70.0, 45.0, 55.0],
    ]}})
    df = DB.fetch_dvol()
    assert list(df["dvol"]) == pytest.approx([50.0, 55.0])


def test_dvol_timestamps_are_UTC(monkeypatch) -> None:
    _stub(monkeypatch, {"result": {"data": [[_T0, 1, 2, 3, 50.0]]}})
    df = DB.fetch_dvol()
    assert str(df["timestamp"].dt.tz) == "UTC"
    assert df["timestamp"].iloc[0] == pd.Timestamp(_T0, unit="ms", tz="UTC")


def test_string_values_from_the_venue_are_coerced(monkeypatch) -> None:
    """Deribit returns numbers as numbers, but a JSON reader upstream can stringify them and the
    failure would be a TypeError deep in a study rather than here."""
    _stub(monkeypatch, {"result": {"data": [[str(_T0), "1", "2", "3", "50.5"]]}})
    assert DB.fetch_dvol()["dvol"].iloc[0] == pytest.approx(50.5)


@pytest.mark.parametrize("payload", [
    {}, {"result": None}, {"result": {}}, {"result": {"data": []}},
    {"result": {"data": "unexpected"}}, {"result": []},
])
def test_dvol_degrades_to_an_EMPTY_FRAME(monkeypatch, payload) -> None:
    """An empty frame says NOT MEASURED. A fabricated row would put an invented implied vol into
    the one family with nothing to cross-check it against."""
    _stub(monkeypatch, payload)
    assert DB.fetch_dvol().empty


def test_the_dvol_request_carries_the_window_and_the_resolution(monkeypatch) -> None:
    """43200 seconds is 12h -- the native resolution of the free history. A dropped parameter
    returns the venue default and silently changes the sampling of every downstream vol study."""
    seen = _stub(monkeypatch, {"result": {"data": []}})
    DB.fetch_dvol("ETH", days=30, resolution=43_200)
    assert "currency=ETH" in seen[0] and "resolution=43200" in seen[0]
    start = int(seen[0].split("start_timestamp=")[1].split("&")[0])
    end = int(seen[0].split("end_timestamp=")[1].split("&")[0])
    assert (end - start) == 30 * 86_400 * 1000


# ============================================================ the surface

def test_POSITIVE_SKEW_MEANS_CRASH_FEAR(monkeypatch) -> None:
    """THE FILE'S ONE IRREVERSIBLE MISTAKE. Inverted, the desk reads maximum complacency at exactly
    the moment the market is paying most for downside protection -- as a plausible number, of a
    plausible size, in the one family it cannot cross-check."""
    exp = _future_exp(30)
    _stub(monkeypatch, {"result": [
        _opt(exp, 100_000, "C", 50.0), _opt(exp, 100_000, "P", 50.0),
        _opt(exp, 90_000, "P", 70.0),          # the OTM put is bid up -- crash fear
        _opt(exp, 110_000, "C", 45.0),
    ]})
    s = DB.vol_surface()
    assert s["skew"] > 0
    assert s["skew"] == pytest.approx(70.0 - 45.0)


def test_NEGATIVE_SKEW_when_calls_are_bid_over_puts(monkeypatch) -> None:
    """The other half. A one-sided test would pass on a detector that always returned positive."""
    exp = _future_exp(30)
    _stub(monkeypatch, {"result": [
        _opt(exp, 100_000, "C", 50.0), _opt(exp, 90_000, "P", 40.0),
        _opt(exp, 110_000, "C", 80.0),
    ]})
    assert DB.vol_surface()["skew"] < 0


def test_the_ATM_iv_is_the_strike_NEAREST_SPOT(monkeypatch) -> None:
    """Not the first strike, and not a mean across the smile -- a mean is pulled up by the wings
    and would report an ATM level no option trades at."""
    exp = _future_exp(30)
    _stub(monkeypatch, {"result": [
        _opt(exp, 60_000, "P", 90.0), _opt(exp, 99_000, "C", 50.0),
        _opt(exp, 160_000, "C", 95.0),
    ]})
    assert DB.vol_surface()["atm_iv"] == pytest.approx(50.0)


def test_OPTIONS_EXPIRING_INSIDE_A_DAY_are_EXCLUDED(monkeypatch) -> None:
    """Their marks are driven by pin risk and near-zero time value. Letting them set the ATM level
    makes the surface twitch on the expiry cycle rather than on the market."""
    near, far = _future_exp(0), _future_exp(30)
    _stub(monkeypatch, {"result": [
        _opt(near, 100_000, "C", 500.0),        # an absurd same-day mark
        _opt(far, 100_000, "C", 50.0),
    ]})
    s = DB.vol_surface()
    assert s and s["atm_iv"] == pytest.approx(50.0)


def test_a_surface_of_ONLY_expiring_options_returns_EMPTY(monkeypatch) -> None:
    _stub(monkeypatch, {"result": [_opt(_future_exp(0), 100_000, "C", 50.0)]})
    assert DB.vol_surface() == {}


def test_the_TERM_SLOPE_is_FRONT_minus_THIRTY_DAY(monkeypatch) -> None:
    """Positive means the front is bid over the belly -- near-term stress. The sign convention has
    to be stated or a reader takes backwardated vol for a calm curve."""
    front, far = _future_exp(3), _future_exp(30)
    _stub(monkeypatch, {"result": [
        _opt(front, 100_000, "C", 90.0),
        _opt(far, 100_000, "C", 50.0),
    ]})
    assert DB.vol_surface()["term"] == pytest.approx(40.0)


def test_options_with_NO_MARK_IV_are_skipped(monkeypatch) -> None:
    """An illiquid strike with no mark is not an option at zero vol. Including it as 0.0 would
    drag both the ATM level and the skew toward zero."""
    exp = _future_exp(30)
    _stub(monkeypatch, {"result": [
        _opt(exp, 100_000, "C", 0.0), {"instrument_name": f"BTC-{exp}-100000-P",
                                       "underlying_price": 100_000.0},
        _opt(exp, 99_000, "C", 55.0),
    ]})
    assert DB.vol_surface()["atm_iv"] == pytest.approx(55.0)


def test_a_MALFORMED_instrument_name_is_skipped(monkeypatch) -> None:
    """`BTC-30AUG26-100000-C` has four parts. Anything else is a different product -- a future, a
    combo -- and parsing it as an option puts a nonsense strike into the surface."""
    exp = _future_exp(30)
    _stub(monkeypatch, {"result": [
        {"instrument_name": "BTC-PERPETUAL", "mark_iv": 99.0, "underlying_price": 100_000.0},
        {"instrument_name": "garbage", "mark_iv": 99.0, "underlying_price": 100_000.0},
        _opt(exp, 100_000, "C", 50.0),
    ]})
    assert DB.vol_surface()["atm_iv"] == pytest.approx(50.0)


@pytest.mark.parametrize("payload", [{}, {"result": None}, {"result": []}, {"result": "x"}])
def test_the_surface_degrades_to_EMPTY_on_a_bad_payload(monkeypatch, payload) -> None:
    _stub(monkeypatch, payload)
    assert DB.vol_surface() == {}


def test_a_book_with_no_parseable_options_returns_EMPTY(monkeypatch) -> None:
    _stub(monkeypatch, {"result": [{"instrument_name": "BTC-PERPETUAL", "mark_iv": 50.0,
                                    "underlying_price": 1.0}]})
    assert DB.vol_surface() == {}


def test_the_surface_request_asks_for_OPTIONS_only(monkeypatch) -> None:
    """Without `kind=option` the response includes futures and perpetuals, whose instrument names
    have a different arity and would all be silently skipped -- producing an empty surface from a
    successful call."""
    seen = _stub(monkeypatch, {"result": []})
    DB.vol_surface("ETH")
    assert "kind=option" in seen[0] and "currency=ETH" in seen[0]


def test_the_SPOT_is_taken_as_a_MEDIAN_across_the_book(monkeypatch) -> None:
    """One stale `underlying_price` on an illiquid strike would move a mean and put the ATM search
    on the wrong strike. The median ignores it."""
    exp = _future_exp(30)
    _stub(monkeypatch, {"result": [
        _opt(exp, 100_000, "C", 50.0, spot=100_000.0),
        _opt(exp, 100_000, "P", 51.0, spot=100_000.0),
        _opt(exp, 50_000, "P", 80.0, spot=1.0),          # a stale/broken underlying
    ]})
    s = DB.vol_surface()
    assert s["atm_iv"] == pytest.approx(50.0) or s["atm_iv"] == pytest.approx(51.0)


# ============================================================ the fetcher

def test_the_fetcher_wraps_a_NON_DICT_response(monkeypatch) -> None:
    """Deribit answers with a JSON object, but an error page or a proxy can return a list. The
    wrapper keeps `.get("result")` from raising AttributeError on the whole desk."""
    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return b"[1, 2, 3]"

    monkeypatch.setattr(DB.urllib.request, "urlopen", lambda *a, **k: _Resp())
    assert DB._get("https://example.test/x") == {"_": [1, 2, 3]}


def test_no_test_in_this_file_reaches_the_network(monkeypatch) -> None:
    monkeypatch.setattr(DB.urllib.request, "urlopen",
                        lambda *a, **k: (_ for _ in ()).throw(
                            AssertionError("a test reached Deribit")))
    _stub(monkeypatch, {"result": {"data": []}})
    assert DB.fetch_dvol().empty
    assert isinstance(time.time(), float)
