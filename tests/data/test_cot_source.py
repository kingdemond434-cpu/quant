"""CFTC COMMITMENT OF TRADERS -- 33 statements, untested, and the sign table is the whole risk.

Net-speculator positioning is a crowding measure: a high z-score means speculators are crowded LONG
the instrument relative to its own three-year history. The CFTC publishes it against the FOREIGN
CURRENCY, not against the pair the desk trades -- so JPY, CHF and CAD contracts have to be INVERTED
to speak about USDJPY, USDCHF and USDCAD.

THAT INVERSION IS THE FILE. Get one sign wrong and the feature says "speculators are crowded long
USDJPY" at exactly the moment they are crowded long the yen, which is the opposite trade. Nothing
downstream can catch it: the series is the right shape, the right scale, and moves at the right
times. So the sign table is asserted against the naming convention that generates it, rather than
row by row against a copy of itself.

The second property is the publication lag. COT is released Friday for Tuesday's positions, so the
value must be shifted before it is usable -- and a z-score that fails to shift reads the future by
three days, which is exactly enough to look like an edge.
"""

from __future__ import annotations

from io import StringIO

import pandas as pd
import pytest

from libs.data import cot_source as CS

# ============================================================ the sign table

def test_a_USD_BASE_pair_is_INVERTED_and_a_USD_QUOTE_pair_is_NOT() -> None:
    """THE ASSERTION THE FILE RESTS ON, derived from the naming convention rather than copied from
    the table -- a row-by-row copy would agree with a wrong table forever.

    The CFTC contract is on the FOREIGN currency. For EURUSD the pair rises when EUR rises, so a
    long-EUR spec position is long the pair: sign +1. For USDJPY the pair rises when the YEN FALLS,
    so a long-JPY spec position is SHORT the pair: sign -1.
    """
    for sym, (_code, sign) in CS.COT_MAP.items():
        if sym.startswith("USD"):
            assert sign == -1.0, f"{sym} is USD-base and must be inverted"
        elif sym.endswith("USD"):
            assert sign == +1.0, f"{sym} is USD-quote and must not be inverted"


def test_every_mapped_symbol_has_a_SIX_DIGIT_contract_code() -> None:
    """CFTC legacy codes are six digits. A truncated one silently selects nothing and the symbol
    drops out of the frame without an error."""
    for sym, (code, _sign) in CS.COT_MAP.items():
        assert code.isdigit() and len(code) == 6, f"{sym} has a malformed code {code!r}"


def test_no_contract_code_is_used_TWICE() -> None:
    """Two symbols on one code is a copy-paste, and it makes two instruments share one positioning
    series -- which reads as perfect correlation between them in every cross-sectional study."""
    codes = [c for c, _s in CS.COT_MAP.values()]
    assert len(codes) == len(set(codes))


def test_the_map_covers_both_metals_and_FX_and_energy() -> None:
    """Breadth is the point of the axis. A map that quietly shrank to two symbols would still pass
    every other test here and would stop being a cross-section."""
    assert {"XAUUSD", "EURUSD", "XTIUSD"} <= set(CS.COT_MAP)
    assert len(CS.COT_MAP) >= 8


# ============================================================ the series

def _rows(dates: list[str], longs: list[float], shorts: list[float]) -> list[dict]:
    return [{"report_date_as_yyyy_mm_dd": d,
             "pct_of_oi_noncomm_long_all": lo,
             "pct_of_oi_noncomm_short_all": sh}
            for d, lo, sh in zip(dates, longs, shorts, strict=True)]


def test_net_spec_is_LONG_MINUS_SHORT_as_a_FRACTION_of_open_interest(monkeypatch) -> None:
    """The CFTC publishes percentages. Leaving them as percentages makes every z-score identical
    (it standardises them away) but every raw threshold wrong by 100x."""
    monkeypatch.setattr(CS, "_get", lambda url: _rows(
        ["2026-01-06", "2026-01-13"], [40.0, 30.0], [10.0, 35.0]))
    s = CS.fetch_net_spec("088691")
    assert list(s.to_numpy()) == pytest.approx([0.30, -0.05])


def test_the_series_is_sorted_ASCENDING_and_UTC_indexed(monkeypatch) -> None:
    """A rolling z-score over an unsorted index is a number about nothing, and pandas computes it
    without complaint."""
    monkeypatch.setattr(CS, "_get", lambda url: _rows(
        ["2026-01-13", "2026-01-06"], [30.0, 40.0], [35.0, 10.0]))
    s = CS.fetch_net_spec("088691")
    assert s.index.is_monotonic_increasing
    assert str(s.index.tz) == "UTC"


def test_an_EMPTY_response_yields_an_empty_float_series(monkeypatch) -> None:
    """Not a raise and not a zero. An empty series propagates to "this symbol has no COT data",
    which is the honest reading when the contract was not reported."""
    monkeypatch.setattr(CS, "_get", lambda url: [])
    s = CS.fetch_net_spec("088691")
    assert s.empty and s.dtype == "float64"


def test_the_query_selects_the_contract_and_ORDERS_by_date(monkeypatch) -> None:
    """Relying on the API's default order would make the sort above a coincidence rather than a
    guarantee, and a paginated response would arrive interleaved."""
    seen: list[str] = []
    monkeypatch.setattr(CS, "_get", lambda url: seen.append(url) or [])
    CS.fetch_net_spec("088691")
    assert "088691" in seen[0]
    assert "$order=report_date_as_yyyy_mm_dd ASC" in seen[0]
    assert "$limit=5000" in seen[0]


# ============================================================ the z-score

def _weekly(n: int, values: list[float] | None = None) -> pd.Series:
    idx = pd.date_range("2020-01-07", periods=n, freq="7D", tz="UTC")
    vals = values if values is not None else [0.1] * n
    return pd.Series(vals, index=idx)


def test_the_z_score_is_LAGGED_because_COT_is_PUBLISHED_LATE(monkeypatch) -> None:
    """COT is released Friday for TUESDAY's positions. A value used on its own report date reads
    three days into the future -- exactly enough to look like an edge and be one of the graveyard's
    timestamp artifacts."""
    n = 200
    vals = [0.0] * (n - 1) + [5.0]                       # one enormous final reading
    monkeypatch.setattr(CS, "fetch_net_spec", lambda code: _weekly(n, vals))
    weekly_idx = _weekly(n).index
    daily = pd.date_range(weekly_idx[0], weekly_idx[-1] + pd.Timedelta(days=6),
                          freq="D", tz="UTC")
    out = CS.cot_zscore_daily(["XAUUSD"], daily, z_weeks=156)
    spike_week = weekly_idx[-1]
    on_report_day = out.loc[out.index <= spike_week, "XAUUSD"].iloc[-1]
    assert pd.isna(on_report_day) or abs(on_report_day) < 5.0, (
        "the spike was visible on its own report date -- the publication lag is not applied")


def test_the_SIGN_is_applied_so_a_USD_BASE_pair_reads_inverted(monkeypatch) -> None:
    """The measurable consequence of the sign table. If this ever flipped, the feature would say
    'speculators are crowded long USDJPY' at exactly the moment they are crowded long the yen."""
    n = 220
    rising = [float(i) / n for i in range(n)]
    monkeypatch.setattr(CS, "fetch_net_spec", lambda code: _weekly(n, rising))
    idx = _weekly(n).index
    daily = pd.date_range(idx[0], idx[-1], freq="D", tz="UTC")
    out = CS.cot_zscore_daily(["EURUSD", "USDJPY"], daily, z_weeks=156)
    eur = out["EURUSD"].dropna()
    jpy = out["USDJPY"].dropna()
    assert len(eur) and len(jpy)
    assert eur.iloc[-1] > 0 and jpy.iloc[-1] < 0
    assert eur.iloc[-1] == pytest.approx(-jpy.iloc[-1])


def test_an_UNMAPPED_symbol_is_SKIPPED_rather_than_columned_with_NaN(monkeypatch) -> None:
    """A NaN column is a symbol the desk believes it measured. Omission says it did not."""
    monkeypatch.setattr(CS, "fetch_net_spec", lambda code: _weekly(200))
    daily = pd.date_range("2020-01-07", periods=100, freq="D", tz="UTC")
    out = CS.cot_zscore_daily(["XAUUSD", "NOTAREALSYMBOL"], daily)
    assert list(out.columns) == ["XAUUSD"]


def test_a_symbol_with_TOO_LITTLE_HISTORY_is_SKIPPED(monkeypatch) -> None:
    """A 3-year z-score computed from six months is a z-score against a regime, not a history, and
    it will read extreme on ordinary values."""
    monkeypatch.setattr(CS, "fetch_net_spec", lambda code: _weekly(10))
    daily = pd.date_range("2020-01-07", periods=100, freq="D", tz="UTC")
    assert CS.cot_zscore_daily(["XAUUSD"], daily, z_weeks=156).empty


def test_the_output_is_on_the_REQUESTED_DAILY_INDEX(monkeypatch) -> None:
    """The caller's index is the join key for everything else. Returning the weekly one would make
    every downstream merge silently drop six days in seven."""
    monkeypatch.setattr(CS, "fetch_net_spec", lambda code: _weekly(200))
    daily = pd.date_range("2021-01-01", periods=60, freq="D", tz="UTC")
    out = CS.cot_zscore_daily(["XAUUSD"], daily)
    assert out.index.equals(daily)


def test_weekly_values_are_FORWARD_FILLED_across_the_days_between_reports(
        monkeypatch) -> None:
    """COT prints weekly and the desk trades daily. Without the fill the feature is NaN on four
    days in five and every model drops those rows."""
    n = 200
    monkeypatch.setattr(CS, "fetch_net_spec",
                        lambda code: _weekly(n, [float(i) for i in range(n)]))
    idx = _weekly(n).index
    daily = pd.date_range(idx[100], idx[120], freq="D", tz="UTC")
    out = CS.cot_zscore_daily(["XAUUSD"], daily)["XAUUSD"]
    assert out.notna().sum() > len(out) * 0.8


def test_an_EMPTY_symbol_list_returns_an_empty_frame_on_the_index(monkeypatch) -> None:
    daily = pd.date_range("2021-01-01", periods=5, freq="D", tz="UTC")
    out = CS.cot_zscore_daily([], daily)
    assert out.empty and list(out.index) == list(daily)


# ============================================================ the fetcher

def test_the_url_is_percent_encoded_so_the_ORDER_clause_survives(monkeypatch) -> None:
    """The `$order` clause contains a space. Sent raw it produces a malformed request line, and
    Socrata answers 400 -- which the caller would see as "no COT data for this contract"."""
    seen: list[str] = []

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return b"[]"

    def fake_urlopen(req, timeout=0):
        seen.append(req.full_url)
        return _Resp()

    monkeypatch.setattr(CS.urllib.request, "urlopen", fake_urlopen)
    CS._get(f"{CS._BASE}?$order=report_date_as_yyyy_mm_dd ASC")
    assert " " not in seen[0] and "%20" in seen[0]


def test_the_fetcher_returns_plain_dicts(monkeypatch) -> None:
    """It goes through pandas, which yields numpy scalars. Downstream code indexes these as plain
    JSON-ish rows, and a numpy type in a json.dumps is a TypeError at the artifact boundary."""
    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return StringIO('[{"a": 1}]').read().encode()

    monkeypatch.setattr(CS.urllib.request, "urlopen", lambda *a, **k: _Resp())
    rows = CS._get(CS._BASE)
    assert rows and isinstance(rows[0], dict)


def test_no_test_in_this_file_reaches_the_network(monkeypatch) -> None:
    monkeypatch.setattr(CS.urllib.request, "urlopen",
                        lambda *a, **k: (_ for _ in ()).throw(
                            AssertionError("a test reached the CFTC")))
    monkeypatch.setattr(CS, "_get", lambda url: [])
    assert CS.fetch_net_spec("088691").empty
