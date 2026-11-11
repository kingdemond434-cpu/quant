"""The futures-state factory: causal features, honest access, PIT stamps, and cells minted once.

Tested on the properties that make the organ worth having: a feature never reads the future, a
refusal is a hard stop that is never retried, the options book is combined minus futures-only,
a transmission sees only what both legs had published, and a second pass mints nothing new.
"""

from __future__ import annotations

import sys
import urllib.parse
from pathlib import Path
from typing import Any

import pytest

pd = pytest.importorskip("pandas")
np = pytest.importorskip("numpy")

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import futures_state as fs  # noqa: E402


def _cot_rows(n: int, seed: int, name: str) -> list[dict[str, Any]]:
    rng = np.random.default_rng(seed)
    days = pd.date_range("2022-01-04", periods=n, freq="7D", tz="UTC")
    rows = []
    for i, d in enumerate(days):
        oi = 400000 + 1000 * i
        rows.append(
            {
                "report_date_as_yyyy_mm_dd": d.strftime("%Y-%m-%dT00:00:00.000"),
                "market_and_exchange_names": name,
                "open_interest_all": str(oi),
                "m_money_positions_long_all": str(int(150000 + rng.integers(-9000, 9000))),
                "m_money_positions_short_all": str(int(20000 + rng.integers(-3000, 3000))),
                "swap_positions_long_all": str(int(20000 + rng.integers(-2000, 2000))),
                "swap__positions_short_all": str(int(240000 + rng.integers(-9000, 9000))),
            }
        )
    return rows


def _fake_get(markets: dict[str, list[dict]], refuse: set[str] | None = None):
    calls: list[str] = []

    def get(url: str) -> Any:
        calls.append(url)
        if refuse and any(r in url for r in refuse):
            raise fs.HardStop(429, url)
        q = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
        where = (q.get("$where") or [""])[0]
        for like, rows in markets.items():
            if like.upper().rstrip("%") in where:
                bump = 500 if "kh3c-gbw2" in url else 0  # the combined set carries options
                return [
                    dict(
                        r,
                        m_money_positions_long_all=str(int(r["m_money_positions_long_all"]) + bump),
                    )
                    for r in rows
                ]
        return []

    get.calls = calls  # type: ignore[attr-defined]
    return get


@pytest.fixture()
def tmp_desk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(fs, "RAW", tmp_path / "raw")
    monkeypatch.setattr(fs, "SERIES", tmp_path / "series")
    monkeypatch.setattr(fs, "CALENDAR_BACKFILL", tmp_path / "calendar_backfill")
    return tmp_path


def test_dynamics_never_read_the_future() -> None:
    s = pd.Series(np.random.default_rng(1).normal(size=200)).cumsum()
    a = fs.dynamics(pd.DataFrame({"x": s}), ["x"])
    s2 = s.copy()
    s2.iloc[150:] += 50.0
    b = fs.dynamics(pd.DataFrame({"x": s2}), ["x"])
    pd.testing.assert_frame_equal(a.iloc[:150], b.iloc[:150])
    assert a["x_pct"].dropna().between(0, 1).all()


def test_positioning_reads_every_cftc_naming_shape() -> None:
    df = pd.DataFrame(
        {
            "open_interest_all": [100.0, 120.0],
            "m_money_positions_long_all": [50.0, 60.0],
            "m_money_positions_short_all": [10.0, 20.0],
            "swap_positions_long_all": [5.0, 5.0],
            "swap__positions_short_all": [30.0, 40.0],
            "lev_money_positions_long": [7.0, 8.0],
            "lev_money_positions_short": [1.0, 1.0],
            "pct_of_oi_m_money_long_all": [50.0, 50.0],
        }
    )
    p = fs.positioning(df)
    assert list(p["m_money_net"]) == [40.0, 40.0]
    assert list(p["swap_net"]) == [-25.0, -35.0]
    assert list(p["lev_money_net"]) == [6.0, 7.0]
    assert not any(c.startswith("pct_of") for c in p.columns)
    assert p["m_money_net_oi"].iloc[1] == pytest.approx(40.0 / 120.0)


def test_cftc_rows_become_available_the_friday_after() -> None:
    at = fs.cftc_available(pd.Series(pd.to_datetime(["2026-08-11"], utc=True))).iloc[0]
    assert at == pd.Timestamp("2026-08-14 21:00", tz="UTC")


def test_curve_features_sign_contango_and_backwardation() -> None:
    contango = pd.DataFrame({"c1": [70.0], "c2": [71.0], "c3": [72.5]})
    f = fs.curve_features(contango, [1 / 12, 2 / 12, 3 / 12])
    assert f["slope"].iloc[0] > 0 and f["roll_yield_12"].iloc[0] < 0
    assert f["contango"].iloc[0] == 1.0
    back = fs.curve_features(
        contango[["c3", "c2", "c1"]].set_axis(["c1", "c2", "c3"], axis=1), [1 / 12, 2 / 12, 3 / 12]
    )
    assert back["slope"].iloc[0] < 0 and back["contango"].iloc[0] == 0.0


def test_hard_stop_is_recorded_and_never_retried(tmp_desk: Path) -> None:
    reg = {
        "sources": [
            {"id": "cftc_disagg_futonly", "terms": "OPEN", "url": "https://x/72hh-3qpy.json"}
        ],
        "cftc_markets": [
            {"id": "gold", "like": "GOLD - COMMODITY EXCHANGE%", "targets": ["XAUUSD"]}
        ],
    }
    state: dict[str, Any] = {}
    get = _fake_get({}, refuse={"72hh"})
    fs.build_market_series(reg, get=get, state=state, bars=lambda s: None)
    assert state["hard_stops"]["cftc_disagg_futonly"]["code"] == 429
    n = len(get.calls)  # type: ignore[attr-defined]
    fs.build_market_series(reg, get=get, state=state, bars=lambda s: None)
    assert len(get.calls) == n  # type: ignore[attr-defined]


def test_held_venues_are_never_fetched_and_are_named(tmp_desk: Path) -> None:
    reg = {
        "sources": [
            {"id": "cftc_disagg_futonly", "terms": "HELD", "url": "https://x/72hh-3qpy.json"},
            {"id": "cme_settlements", "terms": "HELD"},
        ],
        "cftc_markets": [{"id": "gold", "like": "GOLD%", "targets": ["XAUUSD"]}],
    }
    get = _fake_get({"GOLD": _cot_rows(80, 1, "GOLD - COMMODITY EXCHANGE INC.")})
    built, _f, notes = fs.build_market_series(reg, get=get, state={}, bars=lambda s: None)
    assert get.calls == []  # type: ignore[attr-defined]
    g = fs.gaps(reg, built, notes)
    assert "gold" in g["markets_without_series"]
    assert {h["id"] for h in g["held_or_unconfirmed_venues"]} == {
        "cftc_disagg_futonly",
        "cme_settlements",
    }


def _registry() -> dict[str, Any]:
    return {
        "sources": [
            {"id": "cftc_disagg_futonly", "terms": "OPEN", "url": "https://x/72hh-3qpy.json"},
            {"id": "cftc_disagg_combined", "terms": "OPEN", "url": "https://x/kh3c-gbw2.json"},
        ],
        "cftc_markets": [
            {
                "id": "gold",
                "like": "GOLD - COMMODITY EXCHANGE%",
                "targets": ["XAUUSD", "NOTQUOTED"],
            },
            {"id": "silver", "like": "SILVER - COMMODITY EXCHANGE%", "targets": ["XAGUSD"]},
        ],
        "transmissions": [
            {
                "id": "gs",
                "a": "cot_gold",
                "b": "cot_silver",
                "column": "disagg_m_money_net_oi",
                "op": "spread",
                "targets": ["XAGUSD"],
            }
        ],
    }


def test_options_book_flow_price_and_transmission(tmp_desk: Path) -> None:
    get = _fake_get(
        {
            "GOLD - COMMODITY EXCHANGE": _cot_rows(120, 1, "GOLD - COMMODITY EXCHANGE INC."),
            "SILVER - COMMODITY EXCHANGE": _cot_rows(120, 2, "SILVER - COMMODITY EXCHANGE INC."),
        }
    )
    idx = pd.date_range("2022-01-01", "2024-06-30", freq="1h", tz="UTC")
    close = pd.Series(
        np.exp(np.random.default_rng(3).normal(0, 1e-3, len(idx)).cumsum()) * 1800, idx
    )
    bars = {"XAUUSD": pd.DataFrame({"close": close})}
    built, frames, _n = fs.build_market_series(_registry(), get=get, state={}, bars=bars.get)
    assert {"cot_gold", "cot_silver", "xfer_gs"} <= set(built)
    g = frames["cot_gold"]
    # combined carries +500 managed-money longs, so the options book is +500/OI every week
    assert "disagg_m_money_net_oi_opt" in g.columns
    oi = 400000 + 1000 * np.arange(120)
    assert np.allclose(g["disagg_m_money_net_oi_opt"], 500.0 / oi)
    assert "oi" in g.columns and not any(c.endswith("disagg_oi") for c in g.columns)
    assert "flow_price_disagree" in g.columns and g["flow_price_disagree"].notna().sum() > 30
    assert set(g["oi_price_quadrant"].dropna().unique()) <= {-2.0, -1.0, 1.0, 2.0}
    assert (pd.to_datetime(g["available_time"]) > pd.to_datetime(g["event_time"])).all()
    x = frames["xfer_gs"]
    assert x["x"].notna().sum() >= fs.MIN_ROWS


def test_cells_are_minted_once_and_only_on_quoted_targets(tmp_desk: Path) -> None:
    get = _fake_get(
        {
            "GOLD - COMMODITY EXCHANGE": _cot_rows(120, 1, "GOLD - COMMODITY EXCHANGE INC."),
            "SILVER - COMMODITY EXCHANGE": _cot_rows(120, 2, "SILVER - COMMODITY EXCHANGE INC."),
        }
    )
    built, frames, _n = fs.build_market_series(_registry(), get=get, state={}, bars=lambda s: None)
    seen: list[dict[str, Any]] = []

    def enqueue(**kw: Any) -> tuple[str, bool]:
        seen.append(kw)
        return f"c{len(seen)}", True

    state: dict[str, Any] = {}
    uni = frozenset({"XAUUSD", "XAGUSD"})
    first = fs.mint(built, frames, uni, state, dry_run=False, enqueue=enqueue)
    assert first["cells_minted_this_pass"] == len(seen) > 0
    assert {k["symbol"] for k in seen} == {"XAUUSD", "XAGUSD"}
    assert all(k["family"] == "exogenous_conditioner" for k in seen)
    assert first["unquoted_targets"] == {"cot_gold": ["NOTQUOTED"]}
    assert first["cells_queued"] == 0
    second = fs.mint(built, frames, uni, state, dry_run=False, enqueue=enqueue)
    assert second["cells_minted_this_pass"] == 0
    assert second["cells_minted_total"] == first["cells_minted_total"]


def test_the_conditioner_family_reads_what_the_factory_writes(tmp_desk: Path) -> None:
    get = _fake_get(
        {"GOLD - COMMODITY EXCHANGE": _cot_rows(120, 1, "GOLD - COMMODITY EXCHANGE INC.")}
    )
    reg = _registry()
    reg["cftc_markets"] = reg["cftc_markets"][:1]
    _built, frames, _n = fs.build_market_series(reg, get=get, state={}, bars=lambda s: None)
    p = fs._write_series("cot_gold", frames["cot_gold"])
    from mt5desk.family_exogenous_conditioner import conditioner

    s = conditioner("cot_gold", "disagg_m_money_net_oi", "level_z", root=p.parent)
    assert s is not None and len(s) > 30


def test_derived_columns_are_asked_once_and_the_cap_queues_the_rest(tmp_desk: Path) -> None:
    get = _fake_get(
        {"GOLD - COMMODITY EXCHANGE": _cot_rows(120, 1, "GOLD - COMMODITY EXCHANGE INC.")}
    )
    reg = _registry()
    reg["cftc_markets"] = reg["cftc_markets"][:1]
    built, frames, _n = fs.build_market_series(reg, get=get, state={}, bars=lambda s: None)
    plan = fs.cell_plan(built, frames, frozenset({"XAUUSD"}))
    assert all(
        tf == "level_z" for _s, c, tf, _y, _h in plan if c.endswith(("_chg", "_acc", "_pct"))
    )
    assert len(set(plan)) == len(plan)
    assert "m_money" in plan[0][1]
    state: dict[str, Any] = {}
    first = fs.mint(
        built,
        frames,
        frozenset({"XAUUSD"}),
        state,
        dry_run=False,
        enqueue=lambda **k: ("c", True),
        limit=10,
    )
    assert first["cells_minted_this_pass"] == 10
    assert first["cells_queued"] == len(plan) - 10


def test_fred_pairs_and_levels_make_one_series_per_pair_with_its_own_targets() -> None:
    idx = pd.date_range("2018-01-01", periods=80, freq="MS", tz="UTC")
    rng = np.random.default_rng(5)
    yc = pd.DataFrame({"EZ": rng.normal(1, 0.1, 80), "US": rng.normal(3, 0.1, 80),
                       "RES": np.linspace(100.0, 180.0, 80)}, index=idx)
    pairs = {"id": "rd", "mode": "pairs", "window": 24,
             "pairs": [{"id": "EURUSD", "base": "EZ", "quote": "US", "targets": ["EURUSD"]},
                       {"id": "MISSING", "base": "EZ", "quote": "XX", "targets": ["X"]}]}
    out = fs.fred_outputs(pairs, yc)
    assert [o[0] for o in out] == ["fred_rd_eurusd"]
    assert np.allclose(out[0][1]["diff"], yc["EZ"] - yc["US"])
    assert out[0][3] == ["EURUSD"]
    lv = fs.fred_outputs({"id": "res", "mode": "levels", "targets_by_series": {"RES": ["USDCNH"]}},
                         yc)
    assert lv[0][0] == "fred_res_res" and "log_chg" in lv[0][1].columns


def test_registry_names_every_unmeasured_fx_input() -> None:
    import json

    reg = json.loads(fs.REGISTRY.read_text(encoding="utf-8"))
    g = fs.gaps(reg, {}, [])
    assert "fx_options_risk_reversals" in g["missed_growth_unmeasured"]
    held = {h["id"] for h in g["held_or_unconfirmed_venues"]}
    assert {"cls_fx_volumes", "mt5_fx_tick_tape"} <= held
    assert "mof_japan_intervention" not in held, "the MoF collector is built"
    for m in reg["cftc_markets"]:
        assert bool(m.get("names")) != bool(m.get("like")), m["id"]
        assert "/" not in str(m.get("like", "")), "a cross must be named, never patterned"


def _mof_csv(n_quarters: int = 40) -> str:
    """The MoF historical CSV's shape: day rows (year only on a quarter's first row) and one
    total row per quarter, including quarters with no intervention."""
    lines = ["財務省,,,,,,,,", "Foreign Exchange Intervention Operations,,,,,,,,",
             "年,月,日,Year,Month,Day,金額(amount),売買通貨,Currency pairs"]
    mon = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    q_start = pd.Timestamp("2000-01-01")
    for i in range(n_quarters):
        qs = q_start + pd.DateOffset(months=3 * i)
        qe = qs + pd.offsets.QuarterEnd(0)
        if i % 3 == 0:
            sold = "the US dollar (bought) the Japanese yen (sold)"
            bought = "the US dollar (sold) the Japanese yen (bought)"
            lines.append(f"x,,,{qs.year},{mon[qs.month - 1]},5,\"1,{i:03d}\",x,{sold}")
            lines.append(f",,,,{mon[qs.month]},{6 + i % 20},{100 + 7 * i},x,{bought}")
        label = f"{qs.strftime('%B')} - {qe.strftime('%B')} {qe.year}"
        lines.append(f"x,,,{label},,,0,,")
    lines += ["", "(note2) As the figures in each days are rounded off, they do not add up."]
    return "\n".join(lines)


def test_mof_csv_is_signed_by_direction_and_every_quarter_is_measured() -> None:
    days, quarters = fs.mof_days(_mof_csv(40))
    assert len(quarters) == 40 and quarters[0] == pd.Timestamp("2000-03-31")
    first = days.iloc[0]
    assert first["day"] == pd.Timestamp("2000-01-05") and first["amount"] == 1000.0
    assert first["sign"] == -1.0 and days.iloc[1]["sign"] == 1.0
    q = fs.mof_quarterly(days, quarters)
    assert len(q) == 40
    assert q.loc["2000-03-31", "mof_q_net"] == -1000.0 + 100.0
    assert q.loc["2000-06-30", "mof_q_gross"] == 0.0
    assert q.loc["2000-09-30", "mof_q_since_last"] == 2
    assert fs.mof_sign("the euro (bought) the US dollar (sold)") == 0.0


def test_mof_monthly_page_amounts_and_periods() -> None:
    pe, amt = fs.mof_monthly_page("<p>Total amount ... for the period from April 26, 2024 "
                                  "through May 29, 2024</p><p>¥\u3000 9,788.5 billion</p>")
    assert pe == pd.Timestamp("2024-05-29") and amt == pytest.approx(97885.0)
    assert fs.mof_monthly_page("January 30, 2024 through February 27, 2024 ¥ 0")[1] == 0.0
    assert fs.mof_monthly_page("<html>maintenance</html>") is None


def test_mof_rows_are_stamped_at_disclosure_never_at_intervention(tmp_desk: Path) -> None:
    import urllib.error

    csv = _mof_csv(40)
    page = "from x through December 27, 2009 ¥ 1,234 billion"

    def get_text(url: str) -> str:
        if url.endswith("robots.txt"):
            raise urllib.error.HTTPError(url, 404, "nf", None, None)  # type: ignore[arg-type]
        if url.endswith(".csv"):
            return csv
        if url.endswith("monthly/index.html"):
            return '<a href="https://h/feio/monthly/20091230e.html">x</a>'
        return page

    reg = {"sources": [{"id": "mof_japan_intervention", "adapter": "mof_feio", "terms": "OPEN",
                        "csv_url": "https://h/feio/x.csv",
                        "monthly_index_url": "https://h/feio/monthly/index.html",
                        "targets": ["USDJPY"]}]}
    built, frames, _n = fs.build_market_series(reg, get=None, state={}, bars=lambda s: None,
                                               get_text=get_text)
    q, m = frames["mof_jpy_q"], frames["mof_jpy_m"]
    lag = pd.to_datetime(q["available_time"]) - pd.to_datetime(q["event_time"])
    assert (lag >= pd.Timedelta(days=fs.MOF_QUARTER_LAG_DAYS)).all()
    # Months before the first readable release come from the CSV, stamped at disclosure; the
    # release month is stamped at its publication date.
    rel = m[pd.to_datetime(m["event_time"]) == pd.Timestamp("2009-12-27", tz="UTC")]
    assert len(rel) == 1 and str(rel["available_time"].iloc[0]).startswith("2009-12-30 23:00")
    assert rel["mof_m_gross"].iloc[0] == pytest.approx(12340.0)
    early = m[pd.to_datetime(m["event_time"]) < pd.Timestamp("2009-12-01", tz="UTC")]
    assert ((pd.to_datetime(early["available_time"]) - pd.to_datetime(early["event_time"]))
            >= pd.Timedelta(days=fs.MOF_QUARTER_LAG_DAYS)).all()
    assert built["mof_jpy_q"]["targets"] == ["USDJPY"]
    assert "mof_q_net" in fs._feature_cols(q)


def test_mof_is_not_fetched_when_robots_disallows(tmp_desk: Path) -> None:
    calls: list[str] = []

    def get_text(url: str) -> str:
        calls.append(url)
        return "User-agent: *\nDisallow: /\n"

    notes: list = []
    fs.mof_collect({"id": "mof_japan_intervention", "terms": "OPEN", "csv_url": "https://h/a.csv",
                    "monthly_index_url": "https://h/m/index.html"}, get_text, {}, notes)
    assert calls == ["https://h/robots.txt"]
    assert notes[0]["why"] == "robots disallows"


def _registry_calendar() -> dict:
    import json

    return json.loads(fs.REGISTRY.read_text(encoding="utf-8"))["cftc_release_calendar"]


@pytest.mark.parametrize(
    ("as_of", "published"),
    [
        ("2026-08-11", "2026-08-14"),  # an ordinary week: the Friday after
        ("2026-11-24", "2026-11-30"),  # Thanksgiving: CFTC's 2026 schedule says Monday 11/30
        ("2026-06-16", "2026-06-22"),  # Juneteenth on the Friday
        ("2026-11-10", "2026-11-16"),  # Veterans Day on the Wednesday
        ("2025-12-30", "2026-01-05"),  # New Year's Day on the Thursday
        ("2025-01-07", "2025-01-13"),  # the 2025-01-09 closure (National Day of Mourning)
        ("2025-10-21", "2025-12-02"),  # the 2025 lapse: CFTC's catch-up table, not a guess
        ("2019-01-15", "2019-03-08"),  # the 2018-19 lapse: held to the end of the catch-up
    ],
)
def test_cot_rows_are_stamped_at_the_day_cftc_actually_published(as_of: str,
                                                                 published: str) -> None:
    at = fs.cftc_available(pd.Series(pd.to_datetime([as_of], utc=True)),
                           _registry_calendar()).iloc[0]
    assert at == pd.Timestamp(f"{published} 21:00", tz="UTC")


def test_weekly_reports_are_fetched_once_after_release_and_incrementally(
        tmp_desk: Path) -> None:
    rows = _cot_rows(60, 3, "GOLD - COMMODITY EXCHANGE INC.")
    get = _fake_get({"GOLD - COMMODITY EXCHANGE": rows})
    src = {"cftc_disagg_futonly": {"terms": "OPEN", "url": "https://h/72hh-3qpy.json"}}
    mkt = {"id": "gold", "names": ["GOLD - COMMODITY EXCHANGE INC."]}
    last = pd.Timestamp(rows[-1]["report_date_as_yyyy_mm_dd"][:10])
    pos, _ = fs.cftc_market(mkt, src, get, {}, now=last.tz_localize("UTC"))
    assert len(pos) == 60 and len(get.calls) == 1
    # Before the next report is out: nothing is asked for, the held rows serve.
    before = (last + pd.Timedelta(days=9)).tz_localize("UTC")
    pos, info = fs.cftc_market(mkt, src, get, {}, now=before)
    assert len(get.calls) == 1 and len(pos) == 60
    assert info["sets"]["cftc_disagg_futonly"].startswith("HELD")
    # After it is out: one call, asking only for weeks past the newest held one.
    after = (last + pd.Timedelta(days=10, hours=22)).tz_localize("UTC")
    fs.cftc_market(mkt, src, get, {}, now=after)
    assert len(get.calls) == 2
    q = urllib.parse.parse_qs(urllib.parse.urlsplit(get.calls[1]).query)["$where"][0]
    assert f"> '{last.date()}" in q


def test_a_shared_week_across_a_rename_keeps_the_newest_name(tmp_desk: Path) -> None:
    old = _cot_rows(40, 4, "CRUDE OIL, LIGHT SWEET - NEW YORK MERCANTILE EXCHANGE")
    new = [dict(r, market_and_exchange_names="WTI-PHYSICAL - NEW YORK MERCANTILE EXCHANGE",
                open_interest_all="999") for r in old[-5:]]

    def get(url: str) -> list:
        return new + old  # the API's order must not decide

    src = {"cftc_disagg_futonly": {"terms": "OPEN", "url": "https://h/72hh-3qpy.json"}}
    mkt = {"id": "wti", "names": ["CRUDE OIL, LIGHT SWEET - NEW YORK MERCANTILE EXCHANGE",
                                  "WTI-PHYSICAL - NEW YORK MERCANTILE EXCHANGE"]}
    pos, info = fs.cftc_market(mkt, src, get, {})
    assert (pos["oi"].iloc[-5:] == 999).all() and (pos["oi"].iloc[:-5] != 999).all()
    assert info["overlap_weeks"]["cftc_disagg_futonly"] == 5


def test_a_silent_series_is_stale_and_mints_nothing() -> None:
    from datetime import UTC, datetime

    weeks = pd.date_range("2022-01-07", periods=60, freq="7D", tz="UTC")
    f = pd.DataFrame({"x": range(60), "available_time": weeks})
    built = {"cot_a": {"targets": []}, "cot_b": {"targets": []}, "xfer_ab": {"targets": []}}
    fresh = f.assign(available_time=pd.date_range(end=datetime.now(UTC), periods=60,
                                                  freq="7D"))
    frames = {"cot_a": f, "cot_b": fresh, "xfer_ab": fresh}
    reg = {"transmissions": [{"id": "ab", "a": "cot_a", "b": "cot_b"}]}
    out = fs.stale_series(built, frames, reg, datetime.now(UTC))
    assert set(out) == {"cot_a", "xfer_ab"}


def test_a_friday_close_is_public_on_monday() -> None:
    at = fs.daily_available(pd.Series(pd.to_datetime(["2026-10-30"], utc=True))).iloc[0]
    assert at == pd.Timestamp("2026-11-02 23:00", tz="UTC")


def test_discontinued_eia_curves_are_named_not_read(tmp_desk: Path) -> None:
    reg = {"sources": [{"id": "eia_futures", "terms": "DISCONTINUED", "note": "x"}],
           "eia_curves": [{"id": "wti", "series": ["RCLC1"], "targets": ["XTIUSD"]}]}
    built, _f, notes = fs.build_market_series(reg, get=lambda u: 1 / 0, state={},
                                              bars=lambda s: None)
    assert not built
    assert any(n.get("source") == "eia_futures" and n["status"] == "UNMEASURED" for n in notes)


# ------------------------------------------------------------- scheduled-release first prints

def _alfred_rows(n: int) -> list[dict[str, str]]:
    """Monthly payroll-like first prints, each released on the first Friday after its month,
    plus an archive bulk-load: 12 old periods all stamped with one realtime_start."""
    rows = [{"date": f"19{80 + i // 12:02d}-{i % 12 + 1:02d}-01", "realtime_start": "1999-01-01",
             "value": str(90000 + i)} for i in range(12)]
    for i, p in enumerate(pd.date_range("2018-01-01", periods=n, freq="MS")):
        rel = (p + pd.offsets.MonthBegin(1) + pd.offsets.Week(weekday=4)).strftime("%Y-%m-%d")
        rows.append({"date": p.strftime("%Y-%m-%d"), "realtime_start": rel,
                     "value": str(150000 + 150 * i + 20 * (i % 5) + (900 if i == n - 1 else 0))})
    return rows


def _alfred_get(rows: list[dict[str, str]]):
    calls: list[str] = []

    def get(url: str) -> Any:
        calls.append(url)
        return {"observations": rows}

    get.calls = calls  # type: ignore[attr-defined]
    return get


def test_first_prints_drop_the_archive_bulk_load_and_ask_for_initial_release() -> None:
    get = _alfred_get(_alfred_rows(60))
    p = fs.alfred_first_prints("PAYEMS", "k", get)
    assert len(p) == 60
    assert (p["released"] > p["period"]).all()
    q = urllib.parse.parse_qs(urllib.parse.urlsplit(get.calls[0]).query)
    assert q["output_type"] == ["4"] and q["series_id"] == ["PAYEMS"]


def test_release_shock_never_sees_its_own_release() -> None:
    p = fs.alfred_first_prints("PAYEMS", "k", _alfred_get(_alfred_rows(60)))
    a = fs.release_shock(p)
    b = fs.release_shock(p.iloc[:-1])
    # earlier releases are unchanged when a later one is added
    pd.testing.assert_series_equal(a["shock_z"].iloc[:-1].reset_index(drop=True),
                                   b["shock_z"].reset_index(drop=True))
    # the final print jumps by 900 over a near-steady +150 trend: a large positive shock
    assert a["shock_z"].iloc[-1] > 3


def test_release_is_available_only_after_the_new_york_release_time() -> None:
    at = fs.release_available(pd.Series(pd.to_datetime(["2026-01-09", "2026-07-10"])))
    # 08:30 New York is 13:30 UTC in winter and 12:30 UTC in summer, plus the grace
    assert str(at.iloc[0]) == "2026-01-09 13:35:00+00:00"
    assert str(at.iloc[1]) == "2026-07-10 12:35:00+00:00"


def test_first_release_set_mints_exogenous_cells(tmp_desk: Path, monkeypatch) -> None:
    monkeypatch.setenv("FRED_API_KEY", "k")
    reg = {"sources": [{"id": "fred_rates", "adapter": "fred", "terms": "OPEN",
                        "key_env": ["FRED_API_KEY"]}],
           "fred_sets": [{"id": "usrel", "mode": "first_release", "targets": ["XAUUSD"],
                          "releases": [{"series": "PAYEMS", "at": "08:30"}]}]}
    built, frames, _n = fs.build_market_series(reg, get=_alfred_get(_alfred_rows(60)),
                                               state={}, bars=lambda s: None)
    assert "fred_usrel_payems" in built
    f = frames["fred_usrel_payems"]
    assert {"available_time", "event_time", "shock_z"} <= set(f.columns)
    assert (f["available_time"] > f["event_time"]).all()
    plan = fs.cell_plan(built, frames, frozenset({"XAUUSD"}))
    assert any(c == "shock_z" for _s, c, _t, _y, _ch in plan)


def test_first_chg_is_nan_across_a_missing_period() -> None:
    p = fs.alfred_first_prints("PAYEMS", "k", _alfred_get(_alfred_rows(60)))
    gap = p.drop(index=30).reset_index(drop=True)
    sh = fs.release_shock(gap)
    assert np.isnan(sh["first_chg"].iloc[30])            # the period after the hole
    assert sh["first_chg"].iloc[31] == pytest.approx(gap["value"].iloc[31] - gap["value"].iloc[30])


def test_off_schedule_and_weekend_releases_are_dropped_and_counted() -> None:
    rows = _alfred_rows(40)
    sat = pd.Timestamp(rows[20]["realtime_start"]) + pd.Timedelta(days=1)
    assert sat.weekday() == 5
    rows[20] = dict(rows[20], realtime_start=sat.strftime("%Y-%m-%d"))   # a Saturday
    rows[25] = dict(rows[25], realtime_start=(pd.Timestamp(rows[25]["realtime_start"])
                                              - pd.Timedelta(days=3)).strftime("%Y-%m-%d"))
    counts: dict[str, int] = {}
    p = fs.alfred_first_prints("PAYEMS", "k", _alfred_get(rows), [3, 4], counts)
    assert counts["dropped_bulk_load"] == 12
    assert counts["dropped_off_schedule"] == 2
    assert len(p) == 38 and set(p["released"].dt.weekday) <= {3, 4}


def test_release_shock_mints_two_columns_only() -> None:
    p = fs.alfred_first_prints("PAYEMS", "k", _alfred_get(_alfred_rows(60)))
    assert list(fs.release_shock(p).columns) == ["first_chg", "shock_z"]


def test_release_calendar_backfill_is_written_outside_the_donation_tree(tmp_desk: Path,
                                                                        monkeypatch) -> None:
    import gzip
    import json
    monkeypatch.setenv("FRED_API_KEY", "k")
    reg = {"sources": [{"id": "fred_rates", "adapter": "fred", "terms": "OPEN",
                        "key_env": ["FRED_API_KEY"]}],
           "fred_sets": [{"id": "usrel", "mode": "first_release", "targets": ["XAUUSD"],
                          "releases": [{"series": "PAYEMS", "at": "08:30",
                                        "title": "Non-Farm Employment Change"}]}]}
    fs.build_market_series(reg, get=_alfred_get(_alfred_rows(60)), state={}, bars=lambda s: None)
    p = tmp_desk / "calendar_backfill" / "backfill_fred_usrel_payems.jsonl.gz"
    rows = [json.loads(x) for x in gzip.open(p, "rt", encoding="utf-8").read().splitlines()]
    assert len(rows) == 60
    assert rows[0]["event_date"] == "2018-02-02T13:30:00+00:00"      # 08:30 New York, winter
    assert {r["impact"] for r in rows} == {"High"} and rows[0]["currency"] == "USD"
    # the compiler reads every row under data/intelligence as a donation; this must not be there
    assert "intelligence" not in fs.CALENDAR_BACKFILL.parts


def _monthly(start: str, n: int, vals: np.ndarray) -> pd.Series:
    return pd.Series(vals, index=pd.date_range(start, periods=n, freq="MS", tz="UTC"))


def test_reaction_residual_is_taylors_rule_and_strictly_causal() -> None:
    n = 200
    rng = np.random.default_rng(3)
    px = _monthly("2005-01-01", n, 100 * np.cumprod(1 + rng.normal(0.002, 0.002, n)))
    rate = _monthly("2005-01-01", n, 2.0 + np.cumsum(rng.normal(0, 0.1, n)))
    u = _monthly("2005-01-01", n, 5.0 + np.cumsum(rng.normal(0, 0.05, n)))
    f = fs.reaction_residual(rate, px, u, target=2.0)
    t = f.index[-1]
    infl = 100 * (px / px.shift(12) - 1)
    real = (rate - infl).dropna()
    rstar = real[real.index < t].iloc[-fs.RSTAR_MONTHS:].mean()          # prior months only
    norm = u[u.index < t].iloc[-fs.UNORM_MONTHS:].mean()
    rule = rstar + infl[t] + 0.5 * (infl[t] - 2.0) + 0.5 * (-2.0 * (u[t] - norm))
    assert f.loc[t, "resid"] == pytest.approx(rate[t] - rule)
    assert f.loc[t, "infl_gap"] == pytest.approx(infl[t] - 2.0)
    # A higher policy rate today is a tighter bank today, one for one.
    bumped = rate.copy()
    bumped.iloc[-1] += 1.0
    assert fs.reaction_residual(bumped, px, u).loc[t, "resid"] == pytest.approx(
        f.loc[t, "resid"] + 1.0)
    # Nothing later changes an earlier row.
    cut = fs.reaction_residual(rate.iloc[:150], px.iloc[:150], u.iloc[:150])
    pd.testing.assert_frame_equal(cut, f.loc[cut.index])
    # No unemployment series: the rule is inflation-only, and still defined.
    assert not fs.reaction_residual(rate, px).empty
    # The first rows wait for a year of prices and RSTAR_MIN months of real rates.
    assert f.index[0] >= px.index[12 + fs.RSTAR_MIN]


def test_reaction_mode_makes_one_series_per_bank_and_the_shipped_row_is_sound() -> None:
    import json
    n = 120
    idx = pd.date_range("2010-01-01", periods=n, freq="MS", tz="UTC")
    yc = pd.DataFrame({"R": np.linspace(1, 4, n), "P": 100 * 1.002 ** np.arange(n),
                       "U": np.linspace(6, 4, n)}, index=idx)
    cv = {"id": "cb_reaction", "mode": "reaction", "window": 60, "banks": [
        {"id": "fed", "rate": "R", "inflation": "P", "unemployment": "U", "targets": ["USDX"]},
        {"id": "nope", "rate": "MISSING", "inflation": "P", "targets": ["EURUSD"]}]}
    out = fs.fred_outputs(cv, yc)
    assert [(o[0], o[3], o[4]) for o in out] == [
        ("fred_cb_reaction_fed", ["USDX"], "fred_cb_reaction")]
    assert {"resid", "resid_chg", "resid_pct", "real_rate", "infl_gap"} <= set(out[0][1].columns)
    reg = json.loads(fs.REGISTRY.read_text(encoding="utf-8"))
    row = next(r for r in reg["fred_sets"] if r["id"] == "cb_reaction")
    # Stamped after the month's own releases: the month can run 31 days and its CPI or HICP
    # prints by about the 20th of the next month.
    assert row["avail_lag_days"] >= 51
    need = {b[k] for b in row["banks"] for k in ("rate", "inflation", "unemployment") if k in b}
    assert need == set(row["series"])
    assert all(b["targets"] and b["target"] > 0 for b in row["banks"])


# ------------------------------------------------------------------ BIS rates and prices

_BIS_RATE_HEAD = ("FREQ,REF_AREA,UNIT_MEASURE,UNIT_MULT,TIME_FORMAT,COMPILATION,DECIMALS,"
                  "SOURCE_REF,SUPP_INFO_BREAKS,TITLE,TIME_PERIOD,OBS_VALUE,OBS_STATUS,OBS_CONF,"
                  "OBS_PRE_BREAK")
_BIS_CPI_HEAD = ("FREQ,REF_AREA,UNIT_MEASURE,UNIT_MULT,TIME_FORMAT,BREAKS,COVERAGE,DECIMALS,"
                 "TITLE_TS,TIME_PERIOD,OBS_VALUE,OBS_CONF,OBS_PRE_BREAK,OBS_STATUS")


def _bis_rate_csv(area: str, months: pd.DatetimeIndex, level: float = 1.0) -> str:
    # The real table repeats a long note on every row; one with commas must be quoted.
    note = '"From 2019 onwards policy rate; before that, mid-point of the target range, 1946."'
    rows = [f"M,{area},368,0,,{note},4,Some Central Bank,, Central bank policy rates,"
            f"{t:%Y-%m},{level + 0.01 * i:.2f},A,F," for i, t in enumerate(months)]
    return "\n".join([_BIS_RATE_HEAD, *rows]) + "\n"


def _bis_cpi_csv(areas: list[str], months: pd.DatetimeIndex, carried: str | None = None) -> str:
    rows = []
    for a in areas:
        vals = [100.0 * 1.002 ** i for i in range(len(months))]
        if a == carried:
            vals[-1] = vals[-2]
        for t, v in zip(months, vals, strict=True):
            rows.append(f"M,{a},628,0,,,,,,{t:%Y-%m},{v:.6f},F,,A")
            rows.append(f"M,{a},771,0,,,,,,{t:%Y-%m},2.5,F,,A")       # the yoy unit, not wanted
    return "\n".join([_BIS_CPI_HEAD, *rows]) + "\n"


def _bis_src(areas: list[str]) -> dict[str, Any]:
    return {"id": "bis_stats", "terms": "OPEN", "areas": areas, "history_start": "2000-01",
            "rate_url": "https://bis.test/WS_CBPOL/M.{area}?startPeriod={start}",
            "cpi_url": "https://bis.test/WS_LONG_CPI/M.{areas}.628?startPeriod={start}"}


def test_parse_bis_csv_reads_by_column_name_and_filters_the_unit() -> None:
    months = pd.date_range("2026-01-01", periods=9, freq="MS", tz="UTC")
    rate = fs.parse_bis_csv(_bis_rate_csv("CH", months))
    assert list(rate.columns) == ["CH"] and len(rate) == 9
    assert rate.index[0] == pd.Timestamp("2026-01-01", tz="UTC")       # a month is its first day
    assert rate["CH"].iloc[-1] == pytest.approx(1.08)                  # the note's commas are inert
    cpi = fs.parse_bis_csv(_bis_cpi_csv(["GB", "JP"], months), "628")
    assert sorted(cpi.columns) == ["GB", "JP"] and len(cpi) == 9
    assert cpi["GB"].iloc[0] == pytest.approx(100.0)                   # the index, never the 2.5
    assert fs.parse_bis_csv(_bis_cpi_csv(["GB"], months), "999").empty
    assert fs.parse_bis_csv("<html><body>Access denied</body></html>").empty
    assert fs.parse_bis_csv("").empty


def test_drop_carried_tail_blanks_only_a_repeated_last_value() -> None:
    idx = pd.date_range("2026-05-01", periods=5, freq="MS", tz="UTC")
    df = pd.DataFrame({"JP": [119.8, 119.8, 120.4, 120.649287, 120.649287],
                       "GB": [159.2, 159.3, 159.7, 160.5, 161.1]}, index=idx)
    out = fs.drop_carried_tail(df)
    assert np.isnan(out["JP"].iloc[-1]) and out["JP"].iloc[-2] == 120.649287
    assert out["JP"].iloc[1] == 119.8                                  # an earlier repeat stays
    pd.testing.assert_series_equal(out["GB"], df["GB"])
    assert df["JP"].iloc[-1] == 120.649287                             # the input is not touched


def test_bis_collect_one_request_per_area_caches_and_respects_the_refetch_gate(
        tmp_desk: Path) -> None:
    from datetime import UTC, datetime, timedelta
    (tmp_desk / "raw").mkdir()
    import urllib.error
    months = pd.date_range("2000-01-01", periods=60, freq="MS", tz="UTC")
    calls: list[str] = []
    robots: list[str] = []

    def get_text(url: str) -> str:
        if url.endswith("robots.txt"):
            robots.append(url)
            raise urllib.error.HTTPError(url, 404, "nf", None, None)  # type: ignore[arg-type]
        calls.append(url)
        if "WS_CBPOL" in url:
            return _bis_rate_csv(url.split("M.")[1].split("?")[0], months)
        return _bis_cpi_csv(["GB", "JP"], months, carried="JP")

    state: dict[str, Any] = {}
    notes: list[dict[str, Any]] = []
    now = datetime(2026, 11, 11, 12, tzinfo=UTC)
    out = fs.bis_collect(_bis_src(["GB", "JP"]), get_text, state, notes, now)
    assert calls == ["https://bis.test/WS_CBPOL/M.GB?startPeriod=2000-01",
                     "https://bis.test/WS_CBPOL/M.JP?startPeriod=2000-01",
                     "https://bis.test/WS_LONG_CPI/M.GB+JP.628?startPeriod=2000-01"]
    assert sorted(out.columns) == ["BIS_CBPOL_GB", "BIS_CBPOL_JP", "BIS_CPI_GB", "BIS_CPI_JP"]
    assert notes == [] and state["bis_last_fetch"].startswith("2026-11-11T12")
    assert robots == ["https://bis.test/robots.txt"]                   # read once for the host
    # Japan's last month repeats the one before: served blank, kept raw on disk.
    assert np.isnan(out["BIS_CPI_JP"].iloc[-1]) and not np.isnan(out["BIS_CPI_GB"].iloc[-1])
    assert pd.read_parquet(tmp_desk / "raw" / "bis_cpi.parquet")["JP"].notna().all()
    # Inside the refetch window nothing is asked and what is held comes back.
    again = fs.bis_collect(_bis_src(["GB", "JP"]), get_text, state, notes, now + timedelta(hours=3))
    assert len(calls) == 3
    pd.testing.assert_frame_equal(again, out, check_freq=False)
    # After it, only the last two years are asked for, and history is kept underneath.
    later = fs.bis_collect(_bis_src(["GB", "JP"]), get_text, state, notes,
                           now + timedelta(hours=21))
    assert len(calls) == 6 and all(u.endswith("startPeriod=2024-11") for u in calls[3:])
    assert len(later) == 60
    # Offline: held data, no request.
    offline = fs.bis_collect(_bis_src(["GB", "JP"]), None, {}, notes, now)
    pd.testing.assert_frame_equal(offline, out, check_freq=False)


def test_bis_collect_refuses_a_cut_reply_and_records_a_hard_stop(
        tmp_desk: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from datetime import UTC, datetime
    (tmp_desk / "raw").mkdir()
    months = pd.date_range("2000-01-01", periods=40, freq="MS", tz="UTC")
    now = datetime(2026, 11, 11, 12, tzinfo=UTC)
    monkeypatch.setattr(fs, "BIS_MAX_CHARS", 3000)

    def big(url: str) -> str:
        if url.endswith("robots.txt"):
            return "User-agent: *\nAllow: /\n"
        return _bis_rate_csv("GB", months) if "WS_CBPOL" in url else "<html>busy</html>"

    notes: list[dict[str, Any]] = []
    out = fs.bis_collect(_bis_src(["GB"]), big, {}, notes, now)
    # A reply near the fetcher's cap may have lost its newest rows: refused, never stored.
    assert out.empty and not (tmp_desk / "raw" / "bis_cbpol.parquet").exists()
    assert [n["status"] for n in notes] == ["TRUNCATED", "UNPARSED"]

    calls: list[str] = []

    def refused(url: str) -> str:
        calls.append(url)
        raise fs.HardStop(403, url)

    state: dict[str, Any] = {}
    assert fs.bis_collect(_bis_src(["GB", "JP"]), refused, state, notes, now).empty
    assert calls == ["https://bis.test/robots.txt"]                    # refused at the first ask
    assert state["hard_stops"]["bis_stats"]["code"] == 403
    assert "bis_last_fetch" not in state
    fs.bis_collect(_bis_src(["GB", "JP"]), refused, state, notes, now)
    assert len(calls) == 1                                             # a stop is not retried
    # Terms not OPEN: nothing is ever asked.
    fs.bis_collect({**_bis_src(["GB"]), "terms": "UNVERIFIED"}, refused, {}, notes, now)
    assert len(calls) == 1


def test_bis_is_not_fetched_when_robots_disallows(tmp_desk: Path) -> None:
    import urllib.error
    from datetime import UTC, datetime
    (tmp_desk / "raw").mkdir()
    now = datetime(2026, 11, 11, 12, tzinfo=UTC)
    calls: list[str] = []

    def disallow(url: str) -> str:
        calls.append(url)
        return "User-agent: *\nDisallow: /WS_LONG_CPI\n"            # one table is enough

    notes: list[dict[str, Any]] = []
    out = fs.bis_collect(_bis_src(["GB", "JP"]), disallow, {}, notes, now)
    assert calls == ["https://bis.test/robots.txt"] and out.empty
    assert notes == [{"source": "bis_stats", "status": "UNMEASURED", "why": "robots disallows"}]
    assert not (tmp_desk / "raw" / "bis_cbpol.parquet").exists()

    # An unreadable robots.txt (anything but a 404) is never a yes.
    calls.clear()

    def broken(url: str) -> str:
        calls.append(url)
        raise urllib.error.HTTPError(url, 500, "err", None, None)  # type: ignore[arg-type]

    assert fs.bis_collect(_bis_src(["GB", "JP"]), broken, {}, notes, now).empty
    assert calls == ["https://bis.test/robots.txt"]
    assert notes[-1]["why"] == "robots disallows"


def test_shipped_bis_reaction_row_matches_its_source() -> None:
    import json
    reg = json.loads(fs.REGISTRY.read_text(encoding="utf-8"))
    src = next(s for s in reg["sources"] if s["id"] == "bis_stats")
    row = next(r for r in reg["fred_sets"] if r["id"] == "cb_reaction_bis")
    assert src["terms"] == "OPEN" and "Bank for International Settlements" in src["citation"]
    assert row["bis"] is True and row["mode"] == "reaction"
    # After the national CPI and after the BIS table has picked it up.
    assert row["avail_lag_days"] >= 75
    for b in row["banks"]:
        area = b["rate"].removeprefix("BIS_CBPOL_")
        assert area in src["areas"] and b["inflation"] == f"BIS_CPI_{area}"
        assert b["targets"] and b["target"] > 0
        assert b.get("unemployment") is None or b["unemployment"] in row["series"]
    assert {b["unemployment"] for b in row["banks"] if "unemployment" in b} == set(row["series"])
    assert len({b["id"] for b in row["banks"]}) == len(row["banks"]) == len(src["areas"])
    # Built end to end from BIS-shaped columns: one series per bank that has both inputs.
    n = 120
    idx = pd.date_range("2010-01-01", periods=n, freq="MS", tz="UTC")
    yc = pd.DataFrame({"BIS_CBPOL_GB": np.linspace(1, 4, n),
                       "BIS_CPI_GB": 100 * 1.002 ** np.arange(n),
                       "BIS_CBPOL_NZ": np.linspace(1, 4, n)}, index=idx)
    assert [o[0] for o in fs.fred_outputs(row, yc)] == ["fred_cb_reaction_bis_boe"]
