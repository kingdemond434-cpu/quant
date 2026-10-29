"""The vol archive's honesty discipline, tested as behaviour rather than as prose.

The retired organ this replaces got the discipline right in its docstring. A docstring is not a
guarantee, so every honesty claim this module makes is asserted here: forward-only always, no
promotion authority ever, no backtest until the desk's OWN vintages are long enough, an
unavailable series recorded as an absence, and -- the one that would be easiest to get wrong --
a term slope refusing to be built across mismatched as-of dates.

No test here touches the network. The source is behind a one-method interface precisely so the
logic is testable without it.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from recorders import vol_archive as va  # noqa: E402

REGISTRY = {"XAUUSD": {"digits": 2}, "EURUSD": {"digits": 5}, "US500": {"digits": 1},
            "NAS100": {"digits": 1}, "US30": {"digits": 1}}
D = "2026-09-04"


def _series(last: float, days: int = 40, day: str = D) -> dict[str, float]:
    idx = pd.date_range(end=pd.Timestamp(day), periods=days, freq="D")
    return {d.date().isoformat(): last for d in idx}


def _full_source(**over: dict[str, float]) -> va.FakeVolSource:
    data = {"^GVZ": _series(26.6), "^OVX": _series(45.0), "^VIX": _series(14.5),
            "^VIX9D": _series(12.0), "^VIX3M": _series(17.6), "^VIX6M": _series(19.9),
            "^VXN": _series(20.0), "^VXD": _series(13.2), "^EVZ": _series(7.5),
            "^SKEW": _series(151.6)}
    data.update(over)
    return va.FakeVolSource(data)


def _bars(tmp_path: Path, symbol: str, daily_sigma: float, n: int = 60) -> Path:
    """H1 bars whose daily close-to-close vol is a known number, so RV can be checked."""
    u = tmp_path / "universe"
    u.mkdir(exist_ok=True)
    rng = np.random.default_rng(3)
    idx = pd.date_range("2026-06-01", periods=n * 24, freq="h", tz="UTC")
    close = 100.0 * np.exp(np.cumsum(rng.normal(0, daily_sigma / np.sqrt(24), size=n * 24)))
    pd.DataFrame({"high": close * 1.001, "low": close * 0.999, "close": close},
                 index=idx).to_parquet(u / f"{symbol}_H1.parquet")
    return u


# --------------------------------------------------------------- the discipline --
def test_every_row_is_forward_only_and_the_archive_never_claims_promotion_authority(
        tmp_path: Path) -> None:
    """A forward-only dataset has no backtest. The retired organ said so; this enforces it."""
    obs = va.observe(_full_source(), REGISTRY, tmp_path)
    assert obs and all(o.forward_only for o in obs)
    rep = va.report([], obs)
    assert rep["promotion_authority"] is False
    assert rep["forward_only"] is True


def test_backtestable_stays_false_until_the_desks_own_vintages_are_long_enough(
        tmp_path: Path) -> None:
    """The PUBLIC history behind these series does not count. It is not what a decision would
    have seen, and it is not this desk's vintage."""
    obs = va.observe(_full_source(), REGISTRY, tmp_path)
    thin = [{"vol_ticker": "^GVZ", "implied_vol": 26.6, "value_date": f"2026-08-{d:02d}"}
            for d in range(1, 10)]
    rep = va.report(thin, obs)
    assert rep["desk_vintages_min"] < va.MIN_VINTAGES
    assert rep["backtestable"] is False

    fat = [{"vol_ticker": "^GVZ", "implied_vol": 26.6,
            "value_date": (pd.Timestamp("2026-01-01") + pd.Timedelta(days=i)).date().isoformat()}
           for i in range(va.MIN_VINTAGES + 5)]
    assert va.report(fat, obs)["backtestable"] is True


def test_the_moat_claim_separates_what_is_proprietary_from_what_is_public(
        tmp_path: Path) -> None:
    """Overclaiming would break the first rule this module carries over. The public series are
    named as public IN THE ARTIFACT, not just in a comment."""
    rep = va.report([], va.observe(_full_source(), REGISTRY, tmp_path))
    claim = rep["moat_claim"]
    assert "not_proprietary" in claim and "public" in claim["not_proprietary"]
    assert "proprietary_vintage" in claim and "proprietary_join" in claim
    assert "lower" in claim["loss_rate_vs_tick_tape"], (
        "the archive must state that it is second priority to the tape, not equal to it")


# ------------------------------------------------------------------- absences --
def test_an_unavailable_series_is_recorded_as_an_absence_with_its_reason(
        tmp_path: Path) -> None:
    """A module that quietly drops a dead series teaches its reader the series was never wanted."""
    src = _full_source()
    src.missing = {"^EVZ"}
    obs = va.observe(src, REGISTRY, tmp_path)
    row = next(o for o in obs if o.vol_ticker == "^EVZ")
    assert row.status == "UNAVAILABLE"
    assert row.implied_vol is None
    assert "absence" in row.reason
    assert "^EVZ" in va.report([], obs)["unavailable"]


def test_a_series_whose_instrument_this_account_does_not_list_says_which_names_it_tried(
        tmp_path: Path) -> None:
    """An MT5 id this desk cannot trade must never become a node. The IV is still recorded --
    without the join -- rather than dropped."""
    obs = va.observe(_full_source(), {"XAUUSD": {}}, tmp_path)
    row = next(o for o in obs if o.vol_ticker == "^OVX")
    assert row.tradeable is False and row.mt5_symbol is None
    assert row.status == "NOT_TRADEABLE_HERE"
    assert "USOIL" in row.reason and "UKOIL" in row.reason
    assert row.implied_vol == pytest.approx(45.0), "the observation is kept, only the join is not"


def test_the_symbol_is_resolved_against_the_universe_and_never_invented(
        tmp_path: Path) -> None:
    assert va.resolve_symbol(("USOIL", "WTI"), {"WTI": {}}) == "WTI"
    assert va.resolve_symbol(("US500",), {"us500": {}}) == "us500", "case-insensitive fallback"
    assert va.resolve_symbol(("NOTHING",), {"XAUUSD": {}}) is None


# ---------------------------------------------------------------- term structure --
def test_the_term_curve_refuses_to_mix_as_of_dates(tmp_path: Path) -> None:
    """MEASURED AGAINST THE LIVE ENDPOINT, 2026-09-05: the then-source returned ^VIX current and
    ^VIX9D/^VIX3M/^VIX6M seven weeks stale. A stale 9-day tenor beside a fresh 30-day one
    manufactures a term slope out of a publication lag, and a term-structure signal would fire
    on exactly that."""
    stale = _series(16.85, day="2026-07-17")
    obs = va.observe(_full_source(**{"^VIX9D": stale, "^VIX3M": stale, "^VIX6M": stale}),
                     REGISTRY, tmp_path)
    row = next(o for o in obs if o.vol_ticker == "^VIX")
    assert all(v is None for v in row.term_slopes.values()) and row.term_shape == ""
    assert set(row.term_unmeasured) == {"slope_9d_30d", "slope_30d_3m", "slope_3m_6m"}
    assert "refusing to build a slope across as-of dates" in row.term_reason
    assert "2026-07-17" in row.term_reason, "the reason must name what was stale and how stale"


def test_a_contemporaneous_curve_produces_every_named_slope_and_a_shape(tmp_path: Path) -> None:
    obs = va.observe(_full_source(), REGISTRY, tmp_path)
    row = next(o for o in obs if o.vol_ticker == "^VIX")
    assert set(row.term) == {"^VIX9D", "^VIX", "^VIX3M", "^VIX6M"}
    assert row.term_shape == "contango", "12 < 14.5 < 17.6 < 19.9 is an upward-sloping curve"
    assert set(row.term_slopes) == {"slope_9d_30d", "slope_30d_3m", "slope_3m_6m"}
    assert all(v is not None and v > 0 for v in row.term_slopes.values())
    assert row.term_unmeasured == []
    assert row.skew_proxy == pytest.approx(151.6)
    assert row.source_route == "FakeVolSource:fixture" and row.source_admitted is True


def test_the_slope_is_per_log_tenor_so_a_longer_calendar_gap_is_not_more_informative() -> None:
    """Tenors are multiplicative (9d, 30d, 91d, 182d). A raw difference makes the 3M-to-6M step
    look four times more informative than the 9D-to-30D one purely because the gap is longer."""
    curve = {"^VIX9D": 10.0, "^VIX": 20.0, "^VIX3M": 30.0, "^VIX6M": 40.0}
    slopes, missing = va.term_slopes(curve)
    assert va.term_shape(curve) == "contango" and missing == []
    assert slopes["slope_9d_30d"] == pytest.approx(10.0 / np.log(30 / 9), abs=1e-3)
    assert slopes["slope_30d_3m"] == pytest.approx(10.0 / np.log(91 / 30), abs=1e-3)
    assert slopes["slope_3m_6m"] == pytest.approx(10.0 / np.log(182 / 91), abs=1e-3)


def test_a_single_point_curve_yields_no_slope_rather_than_a_zero() -> None:
    slopes, missing = va.term_slopes({"^GVZ": 26.0})
    assert all(v is None for v in slopes.values()) and len(missing) == 3
    assert va.term_shape({"^GVZ": 26.0}) == ""


def test_a_fred_only_curve_measures_30d_3m_and_never_relabels_it_9d_30d(tmp_path: Path) -> None:
    """FRED carries VIXCLS and VXVCLS (30D, 3M) and no VIX9D or VIX6M. The positional slope this
    replaced put the 30D->3M slope under the 9D->30D name on exactly this curve."""
    data = {"^VIX": _series(14.5), "^VIX3M": _series(17.6), "^GVZ": _series(26.6)}
    src = va.FakeVolSource(data, missing={"^VIX9D", "^VIX6M", "^SKEW"})
    row = next(o for o in va.observe(src, REGISTRY, tmp_path) if o.vol_ticker == "^VIX")
    assert row.term_slopes["slope_9d_30d"] is None
    assert row.term_slopes["slope_3m_6m"] is None
    assert row.term_slopes["slope_30d_3m"] == pytest.approx(3.1 / np.log(91 / 30), abs=1e-3)
    assert set(row.term_unmeasured) == {"slope_9d_30d", "slope_3m_6m"}
    assert "term_slope_short" not in va.asdict(row)


# --------------------------------------------------------------- realised vol --
def test_realised_vol_returns_both_estimators_and_says_which_bar_it_ends_on(
        tmp_path: Path) -> None:
    """Reporting one estimator and calling it 'realised vol' hides the case where a premium
    exists under one and not the other -- a property of the estimator, not of the market."""
    u = _bars(tmp_path, "XAUUSD", daily_sigma=0.01)
    cc, park, last = va.realised_vol("XAUUSD", u)
    assert cc is not None and park is not None
    # 1% daily -> ~15.9% annualised. Both estimators must land in that neighbourhood.
    assert 8.0 < cc < 30.0, cc
    assert 4.0 < park < 30.0, park
    assert last


def test_a_symbol_with_no_bars_is_unmeasured_and_not_zero(tmp_path: Path) -> None:
    assert va.realised_vol("NOTHING", tmp_path / "universe") == (None, None, "")


def test_the_variance_risk_premium_is_the_join_that_makes_this_proprietary(
        tmp_path: Path) -> None:
    """Implied vol against THIS broker's realised vol on THIS broker's bars. That join exists
    nowhere else and is the archive's actual asset."""
    u = _bars(tmp_path, "XAUUSD", daily_sigma=0.01)
    obs = va.observe(_full_source(), REGISTRY, u.parent / "universe")
    gold = next(o for o in obs if o.vol_ticker == "^GVZ")
    assert gold.mt5_symbol == "XAUUSD"
    assert gold.realised_vol_cc is not None
    assert gold.variance_risk_premium == pytest.approx(
        gold.implied_vol - gold.realised_vol_cc, abs=1e-3)
    assert gold.iv_over_rv == pytest.approx(gold.implied_vol / gold.realised_vol_cc, abs=1e-3)


def test_the_value_date_is_distinct_from_the_observation_time(tmp_path: Path) -> None:
    """A close published today describes today; a stale index republishing yesterday describes
    yesterday. Collapsing the two is the point-in-time violation this desk refuses everywhere
    else."""
    import datetime as dt
    now = dt.datetime(2026, 9, 8, tzinfo=dt.UTC)
    obs = va.observe(_full_source(), REGISTRY, tmp_path, now=now)
    row = obs[0]
    assert row.value_date == D
    assert row.observed_at.startswith("2026-09-08")
    assert row.value_age_days == 4


# ------------------------------------------------------------------ the archive --
def test_the_archive_is_append_only_and_keeps_the_failures_too(tmp_path: Path) -> None:
    """An archive that only records its successes cannot tell a quiet week from a broken
    collector -- the same reason the tick tape records its gaps."""
    path = tmp_path / "observations.jsonl"
    src = _full_source()
    src.missing = {"^OVX"}
    first = va.observe(src, REGISTRY, tmp_path)
    assert va.append(first, path) == len(first)
    second = va.observe(src, REGISTRY, tmp_path)
    va.append(second, path)

    rows = va.read_archive(path)
    assert len(rows) == 2 * len(first), "a second cycle appends; it never rewrites"
    assert any(r["status"] == "UNAVAILABLE" for r in rows), (
        "the failure must be in the archive, not only in the log")
    assert all(r["schema"] == va.SCHEMA for r in rows)


def test_a_malformed_line_is_skipped_rather_than_taking_the_whole_archive_down(
        tmp_path: Path) -> None:
    path = tmp_path / "observations.jsonl"
    va.append(va.observe(_full_source(), REGISTRY, tmp_path), path)
    with path.open("a", encoding="utf-8") as fh:
        fh.write("{not json at all\n")
    assert len(va.read_archive(path)) > 0


def test_the_report_counts_the_desks_own_vintages_per_ticker(tmp_path: Path) -> None:
    path = tmp_path / "observations.jsonl"
    for day in ("2026-09-01", "2026-09-02", "2026-09-03"):
        src = _full_source(**{"^GVZ": _series(26.0, day=day)})
        va.append(va.observe(src, REGISTRY, tmp_path), path)
    rep = va.report(va.read_archive(path), [])
    assert rep["desk_vintages_per_ticker"]["^GVZ"] == 3
    assert rep["desk_vintages_per_ticker"]["^VIX"] == 1, (
        "a series that did not move contributes one vintage, not three")


# ------------------------------------------------------------------ the fence --
def test_no_crypto_exchange_venue_appears_anywhere_in_this_module() -> None:
    """The 2026-08-18 mandate. The ground moved from a crypto-exchange options venue to CBOE
    indices on MT5-tradeable underlyings, and this is the check that it stays moved."""
    src = (_DESK / "recorders" / "vol_archive.py").read_text("utf-8").casefold()
    for host in ("binance.com", "bybit.com", "okx.com", "hyperliquid", "deribit", "upbit"):
        assert host not in src, host


def test_the_ground_only_names_instruments_this_desk_could_trade() -> None:
    """A vol series with no MT5 analogue has no business in GROUND: it would be a hunted
    universe of its own, which is exactly what the mandate forbids."""
    for g in va.GROUND:
        assert g.mt5_candidates, g.vol_ticker
        assert g.what and g.vol_ticker.startswith("^")
        for tenor in g.term:
            assert tenor in va.TENOR_DAYS, f"{tenor} has no declared tenor"


# ------------------------------------------- the per-source register (ruling 2026-10-13) --
FRED_FIXTURE = "observation_date,GVZCLS\n2026-10-01,18.20\n2026-10-02,.\n2026-10-05,19.05\n"
POLICIES = {"API_PERMITTED", "NEEDS_KEY", "PUBLIC_PAGE", "IDEAS_ONLY", "METHOD_BLOCKED"}


def test_every_register_row_is_a_view_of_its_terms_fence_row() -> None:
    """#234 audit MF: ONE register. Each vol source row is read off libs/data/terms_fence."""
    from libs.data import terms_fence as tf
    keys = {"yahoo": "yahoo", "fred": "fred_cboe", "cboe": "cboe_vol_indices"}
    for name, row in va.TERMS_EVIDENCE.items():
        fence = tf.SOURCE_POLICY[keys[name]]
        assert row["fence_key"] == keys[name]
        assert row["policy"] == tf.live_input_status(keys[name]) in POLICIES, name
        assert row["why"] == fence["why"]
        assert row["quotes"] == list(fence["terms"]["clauses"].values()), name
        assert row["permits_use"] is False, f"{name}: the quotes grant no permission; say so"
        assert row["route_kept"] is False and row["status"] == va.UNMEASURED_TERMS
    assert va.TERMS_EVIDENCE["yahoo"]["policy"] == "IDEAS_ONLY"
    assert "robots, spiders, scrapers" in va.TERMS_EVIDENCE["yahoo"]["quotes"][0]
    assert va.TERMS_EVIDENCE["fred"]["policy"] == "IDEAS_ONLY"
    assert va.TERMS_EVIDENCE["cboe"]["policy"] == "IDEAS_ONLY"
    src = (_DESK / "recorders" / "vol_archive.py").read_text("utf-8")
    assert '"policy": "PUBLIC_PAGE"' not in src and '"route_kept": True' not in src, \
        "vol_archive keeps no register of its own"


def test_route_admitted_needs_a_live_fence_status_and_a_permitting_quote() -> None:
    assert not va.route_admitted(va.YAHOO_TERMS) and not va.route_admitted(va.FRED_TERMS)
    assert not va.route_admitted(va.CBOE_TERMS)
    assert not va.route_admitted({**va.YAHOO_TERMS, "route_kept": True}), \
        "a kept route is not a permission"
    for held in ("METHOD_BLOCKED", "NEEDS_KEY", "IDEAS_ONLY", "UNREAD"):
        assert not va.route_admitted({"policy": held, "permits_use": True, "quotes": ["c"]})
    assert not va.route_admitted(None) and not va.route_admitted({})
    assert not va.route_admitted({"policy": "PUBLIC_PAGE", "permits_use": True, "quotes": []}), \
        "a permission with no quoted clause is not a permission"
    assert va.route_admitted({"policy": "PUBLIC_PAGE", "permits_use": True, "quotes": ["c"]})
    assert va.route_admitted({"policy": "API_PERMITTED", "permits_use": True, "quotes": ["c"]})


_PERMITTED = {"policy": "PUBLIC_PAGE", "permits_use": True, "quotes": ["fixture clause"],
              "why": "fixture"}


def test_an_admitted_fred_route_parses_and_routes() -> None:
    asked: list[str] = []

    def fetch(url: str, timeout: int) -> str:
        asked.append(url)
        return FRED_FIXTURE

    src = va.FredVolSource(fetch=fetch, evidence=_PERMITTED)
    assert src.admitted
    assert src.series("^GVZ") == {"2026-10-01": 18.2, "2026-10-05": 19.05}
    assert src.series("^VIX9D") is None
    assert asked == ["https://fred.stlouisfed.org/graph/fredgraph.csv?id=GVZCLS"]
    assert src.routes["^VIX9D"]["status"] == "UNMEASURED"


def test_the_fence_held_register_sends_no_request_and_every_ground_reads_unmeasured_terms(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def no_network(*_a: object, **_k: object) -> None:
        raise AssertionError("a fenced route opened a connection")

    monkeypatch.setattr(va.urllib.request, "urlopen", no_network)
    asked: list[str] = []
    for src in (va.FredVolSource(fetch=lambda u, t: asked.append(u) or FRED_FIXTURE),
                va.YahooVolSource()):
        assert src.admitted is False
        obs = va.observe(src, REGISTRY, tmp_path)
        assert asked == [] and {o.status for o in obs} == {va.UNMEASURED_TERMS}
        assert all(o.implied_vol is None and o.source_admitted is False for o in obs), \
            "UNMEASURED-terms is never a zero"
        rep = va.report([], obs, sources=src.provenance())
        tickers = {g.vol_ticker for g in va.GROUND}
        assert set(rep["unmeasured_terms"]) == tickers
        assert set(rep["held_by_source_policy"]) == tickers
        assert set(rep["terms_hold"]["held"]) == tickers


def test_the_fenced_cycle_keeps_the_archives_history(tmp_path: Path,
                                                     monkeypatch: pytest.MonkeyPatch) -> None:
    arc = tmp_path / "obs.jsonl"
    old = va.observe(_full_source(), REGISTRY, tmp_path)
    va.append(old, arc)
    monkeypatch.setattr(va.urllib.request, "urlopen",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("network")))
    held = va.observe(va.YahooVolSource(), REGISTRY, tmp_path)
    va.append(held, arc)
    rows = va.read_archive(arc)
    assert len(rows) == len(old) + len(held)
    rep = va.report(rows, held)
    assert rep["desk_vintages_per_ticker"], "earlier vintages survive the hold"


def test_an_admitted_yahoo_route_merges_history_with_the_fresh_tail(
        monkeypatch: pytest.MonkeyPatch) -> None:
    import contextlib
    import io as _io
    import json

    asked: list[str] = []

    def fake_urlopen(req: object, timeout: int = 0) -> object:
        url = req.full_url  # type: ignore[attr-defined]
        asked.append(url)
        if "range=10y" in url:
            stamps, closes = [1759276800, 1759363200], [16.0, 16.2]      # 2025-10-01, -02
        else:
            stamps, closes = [1759363200, 1759449600], [16.4, 16.8]      # -02 restated, -03
        body = json.dumps({"chart": {"result": [{"timestamp": stamps, "indicators": {
            "quote": [{"close": closes}]}}]}}).encode()
        return contextlib.closing(_io.BytesIO(body))

    monkeypatch.setattr(va.urllib.request, "urlopen", fake_urlopen)
    y = va.YahooVolSource(evidence=_PERMITTED, fred_evidence=va.FRED_TERMS)
    got = y.series("^VIX")
    assert got == {"2025-10-01": 16.0, "2025-10-02": 16.4, "2025-10-03": 16.8}
    assert len(asked) == 2 and all("finance.yahoo.com/v8/finance/chart/" in u for u in asked)
    assert y.routes["^VIX"]["route"] == "yahoo_chart" and y.admitted
    src = (_DESK / "recorders" / "vol_archive.py").read_text("utf-8")
    assert "daily_prices/{" not in src, "no request template for CBOE's IDEAS_ONLY files"


def test_a_held_yahoo_row_sends_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    def no_network(*_a: object, **_k: object) -> None:
        raise AssertionError("a held route opened a connection")

    monkeypatch.setattr(va.urllib.request, "urlopen", no_network)
    y = va.YahooVolSource(evidence={**va.YAHOO_TERMS, "policy": "METHOD_BLOCKED"},
                          fred_evidence={**va.FRED_TERMS, "policy": "NEEDS_KEY"})
    assert y.series("^VIX") is None and y.routes["^VIX"]["status"] == va.UNMEASURED_TERMS
    assert y.admitted is False


def test_the_user_agent_names_the_desk_and_claims_no_browser() -> None:
    assert not va.UA.startswith("Mozilla") and "research-desk" in va.UA


def test_terms_note_rides_on_every_row_and_the_report(tmp_path: Path) -> None:
    obs = va.observe(_full_source(), REGISTRY, tmp_path)
    assert all(o.terms_note == va.TERMS_NOTE for o in obs)
    rep = va.report([], obs, sources=va.FredVolSource(fetch=lambda u, t: "").provenance())
    assert rep["terms_note"] == va.TERMS_NOTE
    assert set(rep["sources"]["register"]) == {"fred", "cboe"}
    assert va.report([], obs)["sources"]["admitted"] is False


def test_the_terms_hold_carries_its_missed_growth_line(tmp_path: Path,
                                                       monkeypatch: pytest.MonkeyPatch) -> None:
    """A restriction carries a missed-growth line, published on the artifact: one UNMEASURED
    row per held series (never a free zero), and a NOT_BINDING measured zero when none is held."""
    monkeypatch.setattr(va.urllib.request, "urlopen",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("network")))
    obs = va.observe(va.YahooVolSource(), REGISTRY, tmp_path)
    lines = va.report([], obs)["missed_growth_lines"]
    assert {ln["rail"] for ln in lines} == {f"source_terms_hold:{g.vol_ticker}"
                                            for g in va.GROUND}
    assert all(ln["verdict"] == "UNMEASURED" and ln["value"] is None for ln in lines)
    ok = va.report([], va.observe(_full_source(), REGISTRY, tmp_path))["missed_growth_lines"]
    assert [ln["verdict"] for ln in ok] == ["NOT_BINDING"] and ok[0]["value"] == 0.0


def test_the_terms_hold_lines_are_carried_into_missed_growth(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """#234 SF: the hold's lines are carried into MISSED_GROWTH.json beside the stop-geometry
    gate's (missed_growth.published_gate_lines pattern), never appended to the ledger. An absent
    or stale report is UNMEASURED, never a clean zero."""
    import json

    if str(_DESK / "research") not in sys.path:
        sys.path.insert(0, str(_DESK / "research"))
    import missed_growth as mg
    monkeypatch.setattr(va.urllib.request, "urlopen",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("network")))
    path = tmp_path / "VOL_ARCHIVE.json"
    monkeypatch.setattr(mg, "VOL_ARCHIVE", path)
    assert mg.published_terms_hold_lines()["verdict"] == mg.UNMEASURED      # absent
    doc = va.report([], va.observe(va.YahooVolSource(), REGISTRY, tmp_path))
    path.write_text(json.dumps(doc), encoding="utf-8")
    got = mg.published_terms_hold_lines()
    assert got["verdict"] == mg.UNMEASURED and got["n_held"] == len(va.GROUND)
    assert got["lines"] == doc["missed_growth_lines"]
    path.write_text(json.dumps({**doc, "generated_utc": "2020-01-01T00:00:00+00:00"}),
                    encoding="utf-8")
    stale = mg.published_terms_hold_lines()
    assert stale["verdict"] == mg.UNMEASURED and stale["lines"] == []
    src = (_DESK / "research" / "missed_growth.py").read_text("utf-8")
    assert '"vol_archive_terms_hold": published_terms_hold_lines()' in src


def test_permits_live_input_is_documented_and_validated() -> None:
    """#234 SF: terms_fence documents `permits_live_input` and refuses a row that claims it
    without its own terms page, a verbatim clause and a live-input status."""
    from libs.data import terms_fence as tf
    src = Path(tf.__file__).read_text("utf-8")
    assert "`permits_live_input`" in src
    tf.validate_permits_live_input()                    # the real table is valid
    good = {"status": tf.PUBLIC_PAGE, "permits_live_input": True,
            "terms": {"url": "https://example.org/terms", "clauses": {"a": "quoted"}}}
    tf.validate_permits_live_input({"ok": good})
    for bad in ({**good, "status": tf.IDEAS_ONLY}, {**good, "terms": {"url": "u"}},
                {**good, "permits_live_input": "yes"}):
        with pytest.raises(ValueError):
            tf.validate_permits_live_input({"bad": bad})
    assert tf.permits_live_input("yahoo") is False
    assert va.register_row("yahoo")["permits_use"] is False
