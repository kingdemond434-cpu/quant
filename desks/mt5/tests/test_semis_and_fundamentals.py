"""The semis sector book, the point-in-time SEC fundamentals, and the books that read them.

WHAT THIS PINS, on synthetic bars and recorded (synthetic) SEC documents only -- sec.gov is never
reached from a test:
  * the semis book resolves its nine issuers and the USDKRW proxy from the broker registry, and an
    issuer the broker does not quote is REPORTED absent, never faked;
  * every semis family builds from (bars, symbol) alone, is causal against truncation of the own
    and the peer bars, and reads USDKRW inverted (the won in dollars);
  * fundamentals are POINT-IN-TIME: a value is invisible before its filing's acceptance, TTM uses
    the FY + YTD - prior-YTD identity, and a foreign-currency filer yields nothing;
  * the refresh leg runs offline from recorded documents, reports every uncovered name with its
    reason, and turns a network refusal into UNMEASURED, never zero;
  * the quantamental families and the regime operator are causal in the fundamentals, and every
    class-book family is registered, admitted for share CFDs and seeded through the one door.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from mt5desk import class_books as books  # noqa: E402
from mt5desk import families_cross_sectional as xs  # noqa: E402
from mt5desk import families_quantamental as qm  # noqa: E402
from mt5desk import families_sector as sector  # noqa: E402
from mt5desk import fundamentals_pit as fp  # noqa: E402
from mt5desk import valuation_regime as vr  # noqa: E402

SEMIS = ["NVIDIA", "AMD", "Intel", "MicronTechnology", "TSMC", "Qualcomm", "Broadcom",
         "TexasInstruments", "AppliedMaterials", "USDKRW", "JPN225"]
EQUITIES = ["EQA", "EQB", "EQC", "EQD", "EQE", "EQF"]
DAYS = 520


def _bars(seed: int, drift: float = 0.0, days: int = DAYS, level: float = 100.0,
          vol: float = 0.002) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2020-01-06", periods=days, tz="UTC")
    idx = pd.DatetimeIndex([d + pd.Timedelta(hours=h) for d in dates for h in range(24)])
    r = rng.normal(drift / 24.0, vol, len(idx))
    close = level * np.exp(np.cumsum(r))
    open_ = np.r_[close[0], close[:-1]]
    return pd.DataFrame({"open": open_, "high": np.maximum(open_, close) * 1.0005,
                         "low": np.minimum(open_, close) * 0.9995, "close": close,
                         "tick_volume": 100}, index=idx)


def _key(sigs) -> list[tuple]:
    return [(pd.Timestamp(s.time).value, s.side, round(s.stop, 8), s.tag) for s in sigs]


def _first(fam: str) -> dict:
    return {k: v[0] for k, v in books.PARAM_GRID[fam].items()}


# ------------------------------------------------------------------------------ semis book ---
@pytest.fixture()
def semis(tmp_path, monkeypatch):
    frames = {}
    for i, sym in enumerate(SEMIS):
        if sym == "USDKRW":
            # the won strengthens steadily: USDKRW falls
            frames[sym] = _bars(100, drift=-0.004, level=1300.0, vol=0.0006)
        elif sym == "JPN225":
            frames[sym] = _bars(101, level=38000.0, vol=0.001)
        else:
            frames[sym] = _bars(i + 1, drift=0.0)
        frames[sym].to_parquet(tmp_path / f"{sym}_H1.parquet")
    monkeypatch.setattr(xs, "UNIVERSE_DIR", tmp_path)
    monkeypatch.setattr(xs, "class_symbols",
                        lambda k: list(SEMIS) if k == "semis" else [])
    xs._SERIES_CACHE.clear()
    yield frames
    xs._SERIES_CACHE.clear()


def test_semis_book_resolves_from_the_registry_and_reports_absence(tmp_path, monkeypatch):
    from research import universe_policy as up
    res = up.sector_resolution("semis")
    if not res["issuers"]:
        pytest.skip("registry absent on this host -- UNMEASURED, not a pass")
    assert set(res["issuers"]) == {"NVIDIA", "AMD", "Intel", "Micron", "TSMC", "Qualcomm",
                                   "Broadcom", "Texas Instruments", "Applied Materials"}
    assert res["proxies"] == ["USDKRW", "JPN225"] and res["absent"] == []
    assert res["leaders"] == ["NVIDIA", "Broadcom", "TSMC"]
    assert sorted(up.peer_classes()["semis"]) == sorted(SEMIS)
    assert up.sector_books_of("NVIDIA") == ["semis"] and up.sector_books_of("Apple") == []
    assert up.may_hypothesise("NVIDIA", "semis_sector_momentum")
    assert not up.may_hypothesise("NVIDIA", "session_range_breakout")
    # a broker that does not quote Intel: reported, never faked
    reg = {s: {"asset_class": "Equities"} for s in SEMIS
           if s not in ("Intel", "USDKRW", "JPN225")}
    reg["USDKRW"] = {"asset_class": "Forex Exotics"}
    reg["JPN225"] = {"asset_class": "Indices"}
    path = tmp_path / "universe.json"
    path.write_text(json.dumps(reg), "utf-8")
    monkeypatch.setattr(up, "UNIVERSE", path)
    res = up.sector_resolution("semis")
    assert res["absent"] == ["Intel"] and "Intel" not in res["issuers"]


@pytest.mark.parametrize("family", sorted(sector.SECTOR_FAMILIES))
def test_semis_family_builds_from_symbol_alone_and_is_causal(semis, tmp_path_factory,
                                                             monkeypatch, family):
    fn = sector.SECTOR_FAMILIES[family]
    params = _first(family)
    full = _key(fn(semis["AMD"], symbol="AMD", **params))
    assert full, f"{family} produced no signal on the synthetic semis book"
    assert fn(semis["AMD"], symbol="Apple", **params) == []       # not a member
    with pytest.raises(TypeError):
        fn(semis["AMD"], side=1, symbol="AMD", **params)
    cut = semis["AMD"].index[int(len(semis["AMD"]) * 0.8)]
    short_dir = tmp_path_factory.mktemp("semis_cut")
    for sym, frame in semis.items():
        frame[frame.index < cut].to_parquet(short_dir / f"{sym}_H1.parquet")
    monkeypatch.setattr(xs, "UNIVERSE_DIR", short_dir)
    xs._SERIES_CACHE.clear()
    own = semis["AMD"]
    trunc = _key(fn(own[own.index < cut], symbol="AMD", **params))
    before = [k for k in full if k[0] < cut.value]
    assert before and (trunc == before or trunc == before[:-1])


def test_issuers_are_ranked_against_issuers_never_the_proxy_legs(semis, tmp_path, monkeypatch):
    """Principal's ruling 2026-09-30: issuers rank against their equity peers; USDKRW and JPN225
    are proxy legs and conditioners, never the ranking benchmark. An issuer's panel carries no
    proxy column, so rewriting the proxies' bars cannot move a single issuer signal."""
    d = xs._h1(semis["AMD"])
    panel = xs.class_panel(d, "AMD", klass="semis")
    assert panel is not None and not panel["proxy"]
    assert not {"USDKRW", "JPN225"} & {m.upper() for m in panel["members"]}
    fams = sorted(sector.SECTOR_FAMILIES)
    before = {f: _key(sector.SECTOR_FAMILIES[f](semis["AMD"], symbol="AMD", **_first(f)))
              for f in fams}
    for sym, seed in (("USDKRW", 900), ("JPN225", 901)):
        _bars(seed, drift=0.05, vol=0.02).to_parquet(tmp_path / f"{sym}_H1.parquet")
    xs._SERIES_CACHE.clear()
    after = {f: _key(sector.SECTOR_FAMILIES[f](semis["AMD"], symbol="AMD", **_first(f)))
             for f in fams}
    assert before == after


def test_proxy_legs_trade_the_issuers_aggregate_not_a_rank(semis, tmp_path, monkeypatch):
    """A proxy is never ranked among the issuers: it takes the sign of the issuers' mean score.
    Every issuer rallies, so the book's momentum is positive: the won-in-dollars leg is LONG the
    won (SHORT USDKRW, the pair read inverted) and the Nikkei leg is LONG -- whatever the proxies'
    own paths did."""
    for i, sym in enumerate(SEMIS):
        if sym in ("USDKRW", "JPN225"):
            continue
        _bars(i + 1, drift=0.01).to_parquet(tmp_path / f"{sym}_H1.parquet")
    xs._SERIES_CACHE.clear()
    d = xs._h1(semis["USDKRW"])
    panel = xs.class_panel(d, "USDKRW", klass="semis")
    assert panel is not None and panel["proxy"]
    assert not {"JPN225"} & {m.upper() for m in panel["members"][1:]}
    krw = sector.family_semis_sector_momentum(semis["USDKRW"], symbol="USDKRW", lookback_d=60)
    jp = sector.family_semis_sector_momentum(semis["JPN225"], symbol="JPN225", lookback_d=60)
    assert krw and sum(s.side < 0 for s in krw) > 0.9 * len(krw)
    assert jp and sum(s.side > 0 for s in jp) > 0.9 * len(jp)
    # the reversal family fades the same aggregate
    rev = sector.family_semis_sector_reversal(semis["JPN225"], symbol="JPN225", lookback_d=5)
    assert rev and sum(s.side < 0 for s in rev) > 0.5 * len(rev)


def test_leader_catchup_needs_the_leader_basket(semis, monkeypatch):
    monkeypatch.setattr(sector, "_leaders", lambda panel: [])
    assert sector.family_semis_leader_catchup(semis["AMD"], symbol="AMD", leaders="mega") == []
    assert sector.family_semis_leader_catchup(semis["AMD"], symbol="AMD", leaders="book")


# ------------------------------------------------------------------- point-in-time facts ---
def _fact(start, end, val, accn, filed, form):
    row = {"end": end.isoformat(), "val": val, "accn": accn, "filed": filed.isoformat(),
           "form": form}
    if start is not None:
        row["start"] = start.isoformat()
    return row


def synthetic_company(revenue_q: dict[tuple[int, int], float], *, unit: str = "USD",
                      eps_scale: float = 0.01, shares: float = 1_000.0, book: float = 5_000.0):
    """companyfacts + submissions for a calendar-year filer: 10-Qs for Q1-Q3 (with YTD and
    prior-year comparatives) accepted 40 days after quarter end, 10-Ks 60 days after year end."""
    facts: dict[str, list] = {"Revenues": [], "GrossProfit": [], "NetIncomeLoss": [],
                              "EarningsPerShareDiluted": [], "StockholdersEquity": []}
    dei: list = []
    accns, accepted = [], []
    years = sorted({y for y, _ in revenue_q})

    def qstart(y, q):
        return datetime(y, 3 * q - 2, 1, tzinfo=UTC).date()

    def qend(y, q):
        return (datetime(y + (q == 4), (3 * q) % 12 + 1, 1, tzinfo=UTC)
                - timedelta(days=1)).date()

    def add(start, end, val, accn, filed, form):
        for concept, mult in (("Revenues", 1.0), ("GrossProfit", 0.5), ("NetIncomeLoss", 0.2),
                              ("EarningsPerShareDiluted", 0.2 * eps_scale)):
            facts[concept].append(_fact(start, end, val * mult, accn, filed, form))

    for y in years:
        for q in (1, 2, 3, 4):
            if (y, q) not in revenue_q:
                continue
            end = qend(y, q)
            if q < 4:
                filed, form, accn = end + timedelta(days=40), "10-Q", f"{y}-Q{q}"
                add(qstart(y, q), end, revenue_q[(y, q)], accn, filed, form)
                ytd = sum(revenue_q.get((y, k), 0.0) for k in range(1, q + 1))
                if q > 1:
                    add(qstart(y, 1), end, ytd, accn, filed, form)
                if (y - 1, q) in revenue_q:
                    pend = qend(y - 1, q)
                    add(qstart(y - 1, q), pend, revenue_q[(y - 1, q)], accn, filed, form)
                    pytd = sum(revenue_q.get((y - 1, k), 0.0) for k in range(1, q + 1))
                    if q > 1:
                        add(qstart(y - 1, 1), pend, pytd, accn, filed, form)
            else:
                filed, form, accn = end + timedelta(days=60), "10-K", f"{y}-K"
                fy = sum(revenue_q.get((y, k), 0.0) for k in range(1, 5))
                add(qstart(y, 1), end, fy, accn, filed, form)
            facts["StockholdersEquity"].append(_fact(None, end, book, accn, filed, form))
            dei.append(_fact(None, filed, shares, accn, filed, form))
            accns.append(accn)
            accepted.append(f"{filed.isoformat()}T18:00:00.000Z")
    units = {c: {("USD/shares" if c.startswith("Earnings") else unit): v}
             for c, v in facts.items()}
    doc = {"entityName": "Synthetic", "facts": {
        "us-gaap": {c: {"units": u} for c, u in units.items()},
        "dei": {"EntityCommonStockSharesOutstanding": {"units": {"shares": dei}}}}}
    subs = {"filings": {"recent": {"accessionNumber": accns[::-1], "form": [
        "10-K" if a.endswith("K") else "10-Q" for a in accns[::-1]],
        "acceptanceDateTime": accepted[::-1]}}}
    return doc, subs


REV = {(y, q): 100.0 + 10 * (y - 2019) + q for y in (2019, 2020, 2021) for q in (1, 2, 3, 4)}


def test_snapshots_are_point_in_time_and_use_the_ttm_identity():
    facts, subs = synthetic_company(REV)
    snaps = fp.build_snapshots(facts, subs)
    assert len(snaps)
    q3_2021_accept = datetime(2021, 11, 9, 18, tzinfo=UTC) + timedelta(hours=5)
    after = snaps[snaps["available"] >= q3_2021_accept].iloc[0]
    assert after["available"] == q3_2021_accept           # the acceptance, read at +5h
    want = REV[(2020, 4)] + REV[(2021, 1)] + REV[(2021, 2)] + REV[(2021, 3)]
    assert after["revenue_ttm"] == pytest.approx(want)
    assert after["gross_margin"] == pytest.approx(0.5)
    before = snaps[snaps["available"] < q3_2021_accept].iloc[-1]
    assert before["revenue_ttm"] == pytest.approx(
        REV[(2020, 3)] + REV[(2020, 4)] + REV[(2021, 1)] + REV[(2021, 2)])
    # nothing is known before the first acceptance, and no row predates its own filing
    first = pd.Timestamp(snaps["available"].min())
    assert first > pd.Timestamp("2019-05-10", tz="UTC")
    assert (pd.to_datetime(snaps["available"], utc=True)
            > pd.to_datetime(snaps["period_end"], utc=True)).all()


def test_a_restatement_replaces_only_from_its_own_acceptance():
    s, e = datetime(2020, 1, 1, tzinfo=UTC), datetime(2020, 12, 31, tzinfo=UTC)
    t1, t2 = datetime(2021, 3, 1, tzinfo=UTC), datetime(2022, 3, 1, tzinfo=UTC)
    recs = [(0, s, e, t1, 100.0, "a"), (0, s, e, t2, 90.0, "b")]
    assert fp.ttm(fp._asof(recs, t1 + timedelta(days=1), True))[0] == 100.0
    assert fp.ttm(fp._asof(recs, t2 + timedelta(days=1), True))[0] == 90.0
    assert np.isnan(fp.ttm(fp._asof(recs, t1 - timedelta(days=1), True))[0])


def test_foreign_currency_filer_yields_nothing():
    facts, subs = synthetic_company(REV, unit="TWD")
    body = facts["facts"]
    body["us-gaap"]["EarningsPerShareDiluted"]["units"] = {
        "TWD/shares": body["us-gaap"]["EarningsPerShareDiluted"]["units"]["USD/shares"]}
    del body["dei"]
    assert len(fp.build_snapshots(facts, subs)) == 0


def test_acceptance_without_submissions_falls_back_after_the_filed_day():
    facts, _subs = synthetic_company(REV)
    snaps = fp.build_snapshots(facts, None)
    first = pd.Timestamp(snaps["available"].min())
    assert first == pd.Timestamp("2019-05-11 06:00", tz="UTC")   # filed 2019-05-10, +1d 06:00


# -------------------------------------------------------------------------- the refresh leg ---
@pytest.fixture()
def lake(tmp_path, monkeypatch):
    from research import sec_fundamentals as sec
    monkeypatch.setattr(fp, "PIT_PATH", tmp_path / "lake" / "sec_pit.parquet")
    monkeypatch.setattr(fp, "_CACHE", {"key": None, "by_symbol": {}})
    monkeypatch.setattr(sec, "LAKE", tmp_path / "lake")
    monkeypatch.setattr(sec, "STATE", tmp_path / "lake" / "sec_state.json")
    monkeypatch.setattr(sec, "TICKERS_CACHE", tmp_path / "lake" / "company_tickers.json")
    monkeypatch.setattr(sec, "OUT", tmp_path / "FUNDAMENTALS_COVERAGE.json")
    monkeypatch.setattr(sec, "VALUATION_STATE", tmp_path / "SECTOR_VALUATION_STATE.json")
    monkeypatch.setattr(sec, "UNIVERSE_DIR", tmp_path / "bars")
    vr._LEVEL_CACHE.clear()
    return sec


def test_refresh_leg_runs_from_recorded_documents(lake, tmp_path, monkeypatch):
    sec = lake
    fx = tmp_path / "fixtures"
    fx.mkdir()
    (fx / "company_tickers.json").write_text(json.dumps({
        "0": {"cik_str": 1045810, "ticker": "NVDA", "title": "NVIDIA CORP"},
        "1": {"cik_str": 50863, "ticker": "INTC", "title": "INTEL CORP"}}), "utf-8")
    facts, subs = synthetic_company(REV)
    (fx / "submissions_CIK0001045810.json").write_text(json.dumps(subs), "utf-8")
    (fx / "companyfacts_CIK0001045810.json").write_text(json.dumps(facts), "utf-8")
    (fx / "submissions_CIK0000050863.json").write_text(json.dumps(subs), "utf-8")
    # Intel's companyfacts is missing: the fixture answers 404, as a refusing proxy would
    (tmp_path / "bars").mkdir()
    bars = _bars(7, level=50.0)
    bars.index = bars.index + (pd.Timestamp("2022-01-03", tz="UTC") - bars.index[0])
    bars.to_parquet(tmp_path / "bars" / "NVIDIA_H1.parquet")
    names = ["NVIDIA", "Intel", "Unmapped"]
    monkeypatch.setattr(sec, "registry_equities", lambda: list(names))
    doc = sec.run(fetch=sec.fixture_fetcher(fx), budget_s=60, symbols=names)
    assert doc["names_in_registry"] == 3 and doc["names_covered"] == 1
    reasons = doc["uncovered_by_reason"]
    assert reasons["no_ticker_mapping"] == ["Unmapped"]
    assert reasons["UNMEASURED: companyfacts HTTP 404"] == ["Intel"]
    nv = doc["per_name"]["NVIDIA"]
    assert nv["status"] == "covered" and nv["snapshots"] > 5
    assert "eps_ttm" in nv["fields_present"] and "revenue_ttm" in nv["fields_present"]
    val = nv["valuation_now"]
    assert val["pe"] and val["pe"] > 0 and val["book_to_price"] > 0 and val["ev_sales"] > 0
    assert (tmp_path / "lake" / "sec_pit.parquet").exists()
    state = json.loads((tmp_path / "SECTOR_VALUATION_STATE.json").read_text("utf-8"))
    assert set(state["uses"]) == {"direct", "indirect", "allocation"}
    # one covered name is not a cross-section: UNMEASURED, never a neutral 0.5
    assert state["regimes"]["market_value"]["status"] == "UNMEASURED"
    # a second pass inside the recheck window fetches nothing
    calls: list[str] = []
    inner = sec.fixture_fetcher(fx)

    def counting(url):
        calls.append(url)
        return inner(url)
    sec.run(fetch=counting, budget_s=60, symbols=names)
    assert not [u for u in calls if "companyfacts" in u or "submissions" in u]


def test_refresh_leg_refusal_is_unmeasured(lake, tmp_path, monkeypatch):
    sec = lake
    monkeypatch.setattr(sec, "registry_equities", lambda: ["NVIDIA"])
    doc = sec.run(fetch=lambda url: (403, None), budget_s=10, symbols=["NVIDIA"])
    assert doc["names_covered"] == 0
    assert list(doc["uncovered_by_reason"]) == [
        "UNMEASURED: SEC ticker list unavailable (fetch failed (403); no cache)"]


def test_every_equity_in_the_registry_has_a_ticker():
    from research import sec_fundamentals as sec
    names = sec.registry_equities()
    if not names:
        pytest.skip("registry absent on this host -- UNMEASURED, not a pass")
    assert [n for n in names if n not in sec.ISSUER_TICKERS] == []


# ------------------------------------------------------------------ the quantamental books ---
@pytest.fixture()
def equity(tmp_path, monkeypatch):
    frames = {}
    for i, sym in enumerate(EQUITIES):
        frames[sym] = _bars(20 + i)
        frames[sym].to_parquet(tmp_path / f"{sym}_H1.parquet")
    monkeypatch.setattr(xs, "UNIVERSE_DIR", tmp_path)
    monkeypatch.setattr(xs, "class_of", lambda s: "equity" if s in EQUITIES else None)
    monkeypatch.setattr(xs, "class_symbols", lambda k: list(EQUITIES) if k == "equity" else [])
    xs._SERIES_CACHE.clear()
    vr._LEVEL_CACHE.clear()
    snaps = []
    start = pd.Timestamp("2020-02-10 12:00", tz="UTC")
    for i, sym in enumerate(EQUITIES):
        for q in range(9):
            av = start + pd.Timedelta(days=91 * q + i)
            eps = (6 - i) * 1.0 + 0.1 * q          # EQA has the highest earnings yield
            snaps.append({"symbol": sym, "available": av,
                          "period_end": av - pd.Timedelta(days=40),
                          "revenue_ttm": 1_000.0 * (i + 1), "gross_profit_ttm": 100.0 * (6 - i),
                          "operating_income_ttm": 50.0, "net_income_ttm": 20.0 * (6 - i),
                          "eps_ttm": eps, "gross_margin": 0.1 * (6 - i),
                          "operating_margin": 0.05, "net_margin": 0.02 * (6 - i),
                          "book_value": 500.0, "shares": 10.0, "debt": 10.0, "cash": 5.0,
                          "roe": 0.04 * (6 - i)})
    path = tmp_path / "sec_pit.parquet"
    pd.DataFrame(snaps).to_parquet(path, index=False)
    monkeypatch.setattr(fp, "PIT_PATH", path)
    monkeypatch.setattr(fp, "_CACHE", {"key": None, "by_symbol": {}})
    yield frames, pd.DataFrame(snaps)
    xs._SERIES_CACHE.clear()
    vr._LEVEL_CACHE.clear()


@pytest.mark.parametrize("family", sorted(qm.QUANTAMENTAL_FAMILIES))
def test_quantamental_family_builds_and_waits_for_the_filing(equity, family):
    frames, snaps = equity
    fn = qm.QUANTAMENTAL_FAMILIES[family]
    sigs = fn(frames["EQA"], symbol="EQA", **_first(family))
    assert sigs, f"{family} produced no signal"
    first_known = pd.Timestamp(snaps["available"].min())
    assert all(pd.Timestamp(s.time) >= first_known for s in sigs)
    assert fn(frames["EQA"], symbol="NOTCOVERED", **_first(family)) == []


def test_highest_earnings_yield_is_long(equity):
    frames, _ = equity
    sigs = qm.family_quantamental_earnings_yield(frames["EQA"], symbol="EQA")
    assert sigs and sum(s.side > 0 for s in sigs) > 0.9 * len(sigs)
    sigs = qm.family_quantamental_earnings_yield(frames["EQF"], symbol="EQF")
    assert sigs and sum(s.side < 0 for s in sigs) > 0.9 * len(sigs)


def test_quantamental_is_causal_in_the_fundamentals(equity, tmp_path, monkeypatch):
    frames, snaps = equity
    full = _key(qm.family_quantamental_value(frames["EQC"], symbol="EQC"))
    cut = pd.Timestamp("2021-03-01", tz="UTC")
    path = tmp_path / "cut.parquet"
    snaps[pd.to_datetime(snaps["available"], utc=True) < cut].to_parquet(path, index=False)
    monkeypatch.setattr(fp, "PIT_PATH", path)
    trunc = _key(qm.family_quantamental_value(frames["EQC"], symbol="EQC"))
    assert [k for k in full if k[0] < cut.value] == [k for k in trunc if k[0] < cut.value]


def test_regime_operator_partitions_its_base(equity):
    frames, _ = equity
    base = {"hold_d": 20, "quantile": 0.2}
    all_sigs = _key(qm.family_quantamental_earnings_yield(frames["EQA"], symbol="EQA", **base))
    got = {}
    for st in ("cheap", "rich"):
        got[st] = _key(vr.family_valuation_regime_conditioned(
            frames["EQA"], symbol="EQA", base_family="quantamental_earnings_yield",
            base_params=base, regime="market_value", state=st))
    assert got["cheap"] or got["rich"]
    assert not set(got["cheap"]) & set(got["rich"])
    assert set(got["cheap"]) | set(got["rich"]) <= set(all_sigs)
    # refuses what it may not wrap or read
    for bad in ({"base_family": "session_range_breakout"},
                {"base_family": "valuation_regime_conditioned"},
                {"base_family": "quantamental_value", "regime": "semis_value", "state": "cheap"},
                {"base_family": "quantamental_value", "state": "wide"}):
        kw = {"regime": "market_value", "state": "cheap", **bad}
        assert vr.family_valuation_regime_conditioned(frames["EQA"], symbol="EQA", **kw) == []


def test_regime_state_is_lagged(equity):
    stamps = (pd.bdate_range("2020-01-06", periods=DAYS, tz="UTC")
              + pd.Timedelta(hours=22)).as_unit("ns").asi8
    level = vr.regime_level("market_value", stamps)
    st = vr.regime_state("market_value", stamps)
    assert np.isfinite(level).sum() > 250 and (st != 0).any()
    # changing today's level cannot change today's state
    k = int(np.flatnonzero(st != 0)[-1])
    bumped = level.copy()
    bumped[k] = 1e9
    high = xs._lagged_high(bumped, vr.HISTORY_D, None)
    assert bool(high[k]) == (st[k] == 1)


# ------------------------------------------------------------------------ the one door ---
def test_every_class_book_family_is_registered_and_admitted():
    from mt5desk import families
    from mt5desk import families_orthogonal as fo
    from research.axis_registry import FAMILY_TABLE
    from research.miner_candidate_compiler import _registered_family

    from libs.research.alpha_clusters import classify_family
    from libs.research.mechanism_census import CONSTRUCTION_CLASS
    from research import universe_policy as up
    assert set(books.FAMILIES) == set(up.CROSS_SECTIONAL_FAMILIES)
    for fam, fn in books.FAMILIES.items():
        assert fo.ORTHOGONAL_FAMILIES[fam] is fn and families.get_family_func(fam) is fn
        assert fo.timeframe_domain(fam) == ("H1",) and fam in fo.FAMILY_INPUTS
        assert fam in FAMILY_TABLE and FAMILY_TABLE[fam][0] != "UNKNOWN"
        assert classify_family(fam) == books.TARGETS[fam]["cluster"]
        assert fam in CONSTRUCTION_CLASS and _registered_family(fam)
    assert books.families_for("semis").keys() == {*sector.SECTOR_FAMILIES,
                                                  books.OPERATOR}
    assert set(qm.QUANTAMENTAL_FAMILIES) <= set(books.families_for("equity"))
    assert not set(sector.SECTOR_FAMILIES) & set(books.families_for("equity"))
    assert books.grid(books.OPERATOR, "fx_usd") == []
    assert all(c["base_family"] in xs.CROSS_SECTIONAL_FAMILIES
               for c in books.grid(books.OPERATOR, "index"))


def test_sealed_gauntlet_rebuilds_the_new_books(semis, monkeypatch):
    sys.path.insert(0, str(_DESK / "scripts"))
    import external_gauntlet as eg
    from research.family_policy import family_banned
    monkeypatch.setattr(eg, "_bars_for", lambda sym, tf="H1": semis.get(sym))
    for fam in sector.SECTOR_FAMILIES:
        assert not family_banned(fam)
        cell = eg.build_cell("AMD", fam, {"symbol": "AMD", **_first(fam)}, {})
        assert cell is not None and cell["sigs"], f"{fam}: {eg.LAST_BUILD_FAILURE}"


def test_leg_is_wired_and_the_dataset_rows_record_their_uses():
    text = (_DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert '_costed("sec_fundamentals"' in text
    assert (text.index('_costed("sec_fundamentals"')
            < text.index('_costed("cross_sectional_breadth"'))
    from libs.research.layers import LEG_LAYER
    assert LEG_LAYER["sec_fundamentals"] == "information"
    import importlib
    hc = importlib.import_module("research.hourly_cycle")
    assert hc.department_of("sec_fundamentals") == "data"
    assert hc.LEG_BUDGET_SEC["sec_fundamentals"] > 600
    reg = json.loads((_DESK / "data" / "data_registry.json").read_text("utf-8"))["datasets"]
    for row in ("sec_fundamentals_pit", "semis_sector_book"):
        uses = reg[row]["uses"]
        assert set(uses) == {"direct", "indirect", "allocation"} and all(uses.values())
        assert set(reg[row]["consumers"]) == {"direct", "indirect", "allocation"}


def test_every_donated_row_carries_its_culture(semis, tmp_path, monkeypatch):
    """Principal 2026-09-30 14:18: source_culture, participant_structure and
    failure_mode_hypothesis on every donated row -- TW, KR and JP where the leg is local."""
    from research import cross_sectional_breadth as csb
    from research import proposer_common as pc
    monkeypatch.setattr(csb, "STATE", tmp_path / "state.json")
    monkeypatch.setattr(csb, "OUT", tmp_path / "out.json")
    monkeypatch.setattr(csb, "TRIALS_LEDGER", tmp_path / "screen_trials.jsonl")
    for name in ("BREADTH", "BREADTH_LEDGER", "CANON", "VERDICTS"):
        monkeypatch.setattr(csb, name, tmp_path / f"absent_{name}")
    real = xs._policy()

    class _P:
        SECTOR_BOOKS = real.SECTOR_BOOKS
        ORIENTED_CLASSES = real.ORIENTED_CLASSES

        @staticmethod
        def peer_classes():
            return {"semis": list(SEMIS)}

        sector_resolution = staticmethod(real.sector_resolution)
        sector_books_of = staticmethod(real.sector_books_of)
    monkeypatch.setattr(xs, "_policy", lambda: _P())
    donated: list[list[dict]] = []

    def fake_donate(source, rows, tests_run):
        donated.append(list(rows))
        return tmp_path / "d.json"
    monkeypatch.setattr(pc, "donate", fake_donate)
    monkeypatch.setattr(pc, "donation_counts", lambda: {"donated": len(donated[-1])})
    csb.run(budget_s=600, symbols=["TSMC", "USDKRW", "JPN225", "AMD"])
    rows = donated[0]
    assert rows
    keys = ("source_culture", "participant_structure", "failure_mode_hypothesis")
    assert all(all(r.get(k) for k in keys) for r in rows)
    by_sym = {r["symbol"]: r["source_culture"] for r in rows}
    assert by_sym.get("TSMC") == "TW" and by_sym.get("USDKRW") == "KR"
    assert by_sym.get("JPN225") == "JP" and by_sym.get("AMD", "US") == "US"
    assert {r["family"] for r in rows} <= set(books.families_for("semis"))
    # the generic rule, off the sector book
    assert csb.culture("USDJPY", "fx_usd", "x")["source_culture"] == "JP"
    assert csb.culture("USDCNH", "fx_usd", "x")["participant_structure"] == "policy_driven"
    assert csb.culture("NOTREAL", "index", "x")["source_culture"] == "UNMEASURED"


# ------------------------------------------------------------- the EDGAR user agent (item 6) ---
_UA_VARS = ("QUANT_EDGAR_UA", "SEC_EDGAR_USER_AGENT", "SEC_EDGAR_UA")


def test_edgar_ua_reads_three_names_in_order(monkeypatch):
    from research import sec_fundamentals as sec
    assert sec.UA_ENV_VARS == _UA_VARS
    for v in _UA_VARS:
        monkeypatch.delenv(v, raising=False)
    assert sec.edgar_user_agent() == (None, None)
    monkeypatch.setenv("SEC_EDGAR_UA", "c")
    assert sec.edgar_user_agent() == ("c", "SEC_EDGAR_UA")
    monkeypatch.setenv("SEC_EDGAR_USER_AGENT", "b")
    assert sec.edgar_user_agent() == ("b", "SEC_EDGAR_USER_AGENT")
    monkeypatch.setenv("QUANT_EDGAR_UA", "a")
    assert sec.edgar_user_agent() == ("a", "QUANT_EDGAR_UA")
    assert not hasattr(sec, "DEFAULT_UA"), "the placeholder identity is back"


def test_no_edgar_ua_is_blocked_and_sends_nothing(lake, monkeypatch):
    sec = lake
    for v in _UA_VARS:
        monkeypatch.delenv(v, raising=False)

    def no_network(*a, **k):
        raise AssertionError("a request left without a User-Agent")
    monkeypatch.setattr(sec, "urlopen", no_network)
    monkeypatch.setattr(sec, "registry_equities", lambda: ["NVIDIA"])
    doc = sec.run(budget_s=10, symbols=["NVIDIA"])
    assert doc["pass"]["status"] == "UNMEASURED" and doc["pass"]["blocked"] is True
    assert all(v in doc["pass"]["why"] for v in _UA_VARS)


def test_the_ua_value_is_never_written(lake, monkeypatch):
    sec = lake
    probe = "Probe Person probe-ua-value@example.invalid"
    monkeypatch.setenv("SEC_EDGAR_USER_AGENT", probe)
    monkeypatch.delenv("QUANT_EDGAR_UA", raising=False)
    monkeypatch.setattr(sec, "http_fetcher", lambda ua: (lambda url: (403, None)))
    monkeypatch.setattr(sec, "http_lines", lambda ua: (lambda url: (403, [])))
    monkeypatch.setattr(sec, "registry_equities", lambda: ["NVIDIA"])
    doc = sec.run(budget_s=10, symbols=["NVIDIA"])
    assert doc["pass"]["user_agent_source"] == "SEC_EDGAR_USER_AGENT"
    assert probe not in json.dumps(doc, default=str)


# ------------------------------------------------------------------ survivorship (item 5) ---
def test_delisted_issuers_are_resolved_from_edgar_and_never_tradable(lake, tmp_path,
                                                                     monkeypatch):
    """A delisted issuer's CIK comes from EDGAR's entity list (unique match or reported), its
    Form 25 dates the delisting, its fundamentals are built, and it is never a cell."""
    from research import universe_policy as up
    sec = lake
    fx = tmp_path / "fx"
    fx.mkdir()
    # SYNTHETIC fixture CIKs, not real ones: the test pins the mechanism, not EDGAR's numbers
    (fx / "cik-lookup-data.txt").write_text(
        "XILINX INC:0000999001:\nVMWARE INC:0000999002:\nVMWARE, INC.:0000999003:\n"
        "SOMETHING ELSE:0000999004:\n", "latin-1")
    (fx / "company_tickers.json").write_text(json.dumps({
        "0": {"cik_str": 1045810, "ticker": "NVDA", "title": "NVIDIA CORP"}}), "utf-8")
    facts, subs = synthetic_company(REV)
    subs = json.loads(json.dumps(subs))
    subs["filings"]["recent"]["form"].insert(0, "25-NSE")
    subs["filings"]["recent"]["accessionNumber"].insert(0, "delist-1")
    subs["filings"]["recent"]["acceptanceDateTime"].insert(0, "2022-02-14T16:00:00.000Z")
    subs["filings"]["recent"]["filingDate"] = (
        ["2022-02-14"] + ["2021-01-01"] * (len(subs["filings"]["recent"]["form"]) - 1))
    (fx / "submissions_CIK0000999001.json").write_text(json.dumps(subs), "utf-8")
    (fx / "companyfacts_CIK0000999001.json").write_text(json.dumps(facts), "utf-8")
    monkeypatch.setattr(sec, "registry_equities", lambda: [])
    doc = sec.run(fetch=sec.fixture_fetcher(fx), lines=sec.fixture_lines(fx), budget_s=60,
                  symbols=["NVIDIA"])
    surv = doc["survivorship"]["issuers"]
    x = surv["Xilinx"]
    assert x["cik"] == 999001 and x["tradable_now"] is False
    assert x["delisting_filed"] == "2022-02-14" and x["snapshots"] > 5
    assert x["in_ranking_history"]["price_free_ranks"] is True
    assert str(x["in_ranking_history"]["price_ranks"]).startswith("UNMEASURED")
    assert surv["VMware"]["status"].startswith("cik_unresolved: ambiguous")
    assert surv["Altera"]["status"].startswith("cik_unresolved: absent")
    assert "XILINX" in fp.covered_symbols()
    # untradable now, by every door
    assert up.is_delisted("Xilinx") and up.peer_class("Xilinx") is None
    assert not up.may_hypothesise("Xilinx", "quantamental_quality")
    semis_hist = up.delisted_members("semis")
    assert "Xilinx" in semis_hist and "Twitter" not in semis_hist
    reg = up._registry()
    assert not {k.upper() for k in up.DELISTED_ISSUERS} & {k.upper() for k in reg}


def test_a_registry_ticker_that_left_the_sec_list_still_resolves(lake, tmp_path, monkeypatch):
    sec = lake
    now = datetime(2026, 9, 30, tzinfo=UTC)
    sec._remember_tickers({"WBA": 999010}, now)
    assert sec.ticker_history()["WBA"] == 999010
    assert sec._norm_name("MONSANTO CO /NEW/") == "MONSANTO CO"
    assert sec._norm_name("Twitter, Inc.") == "TWITTER INC"


def test_delisted_issuers_join_the_ranking_history_and_are_never_placed(equity, tmp_path,
                                                                        monkeypatch):
    """EQE is the fifth of six on gross margin: short. While a WORSE delisted peer still files,
    EQE is fifth of seven and out of the bottom third; when the peer stops filing it leaves the
    cross-section by itself and EQE is short again. A delisted name never gets a signal."""
    frames, snaps = equity
    hist = []
    start = pd.Timestamp("2020-02-10 12:00", tz="UTC")
    for q in range(3):
        av = start + pd.Timedelta(days=91 * q)
        hist.append({**snaps.iloc[0].to_dict(), "symbol": "Xilinx", "available": av,
                     "period_end": av - pd.Timedelta(days=40), "gross_margin": 0.01})
    path = tmp_path / "with_hist.parquet"
    pd.concat([snaps, pd.DataFrame(hist)], ignore_index=True).to_parquet(path, index=False)
    base = _key(qm.family_quantamental_quality(frames["EQE"], symbol="EQE"))
    monkeypatch.setattr(fp, "PIT_PATH", path)
    monkeypatch.setattr(fp, "_CACHE", {"key": None, "by_symbol": {}})
    monkeypatch.setattr(xs, "history_members", lambda k: ["Xilinx"] if k == "equity" else [])
    monkeypatch.setattr(xs, "is_delisted", lambda s: str(s).upper() == "XILINX")
    d = xs._h1(frames["EQE"])
    panel = xs.class_panel(d, "EQE", klass="equity", fundamentals_history=True)
    assert panel is not None and panel["delisted"] == ["Xilinx"]
    assert xs.class_panel(d, "EQE", klass="equity")["delisted"] == []   # price books: bars only
    got = _key(qm.family_quantamental_quality(frames["EQE"], symbol="EQE"))
    life_end = (start + pd.Timedelta(days=91 * 2 - 40 + 200)).value
    assert [k for k in base if k[0] >= life_end + 86_400e9 * 2] == \
        [k for k in got if k[0] >= life_end + 86_400e9 * 2]
    # from the day all six live names file (EQF is first known at start + 5d) to 150 days on
    lo, hi = (start + pd.Timedelta(days=6)).value, (start + pd.Timedelta(days=150)).value
    assert [k for k in base if lo <= k[0] < hi]
    assert not [k for k in got if lo <= k[0] < hi]
    assert xs.class_panel(d, "Xilinx", klass="equity", fundamentals_history=True) is None
    assert qm.family_quantamental_quality(frames["EQE"], symbol="Xilinx") == []
