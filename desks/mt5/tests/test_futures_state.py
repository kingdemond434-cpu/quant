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


def test_gamma_is_positive_and_peaks_at_the_money() -> None:
    atm = fs.bs_gamma(100.0, 100.0, 0.6, 30 / 365)
    otm = fs.bs_gamma(100.0, 140.0, 0.6, 30 / 365)
    assert atm > otm > 0
    assert fs._deribit_expiry("BTC-27DEC26").isoformat() == "2026-12-27T08:00:00+00:00"


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


def test_exact_names_never_swallow_a_cross_contract() -> None:
    from mt5desk import fetch_tff

    cme = " - CHICAGO MERCANTILE EXCHANGE"
    df = pd.DataFrame({"Market_and_Exchange_Names": ["EURO FX" + cme,
                                                     "EURO FX/JAPANESE YEN XRATE" + cme,
                                                     "EURO FX/BRITISH POUND XRATE" + cme],
                       "Report_Date_as_YYYY-MM-DD": ["2026-08-11"] * 3,
                       "Open_Interest_All": [700000, 21455, 30000]})
    eur = dict(fetch_tff.TARGETS)["eur"]
    got = fetch_tff.pick(df, eur)
    assert list(got["market"]) == ["EURO FX" + cme]
    assert list(fetch_tff.pick(df, dict(fetch_tff.TARGETS)["eurjpy"])["oi"]) == [21455]


def test_registry_names_every_unmeasured_fx_input() -> None:
    import json

    reg = json.loads(fs.REGISTRY.read_text(encoding="utf-8"))
    g = fs.gaps(reg, {}, [])
    assert "fx_options_risk_reversals" in g["missed_growth_unmeasured"]
    held = {h["id"] for h in g["held_or_unconfirmed_venues"]}
    assert {"mof_japan_intervention", "cls_fx_volumes", "mt5_fx_tick_tape"} <= held
    for m in reg["cftc_markets"]:
        assert bool(m.get("names")) != bool(m.get("like")), m["id"]
        assert "/" not in str(m.get("like", "")), "a cross must be named, never patterned"
