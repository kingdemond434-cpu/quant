"""Copy-trade crowd book: symbols land on one name, access stays honest, books are PIT.

Offline: every page is a fixture served by an injected `get`, so the properties are tested, not
the live sites (their markup is measured by the first box pass and reported per source).
"""
from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

pd = pytest.importorskip("pandas")

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.data.crowd_symbols import canonical  # noqa: E402
from research import copytrade_crowd as cc  # noqa: E402

UNI = frozenset({"EURUSD", "XAUUSD", "US30", "NAS100", "GBPUSD", "GER40", "BTCUSD", "XTIUSD"})

MQL5_ROBOTS = """User-agent: *
Disallow: /*/signals/*/positions/page*
Disallow: /*/signals/new
Disallow: /*/search*
User-agent: AhrefsBot
Disallow: /
"""


def mql5_page(growth: str, weeks: int, dd: str, long_: int, short: int,
              rows: list[tuple[str, int, int, int]]) -> str:
    trs = "".join(f"<tr><td>{s}</td><td>{d}</td><td>{se}</td><td>{b}</td><td>12.50</td></tr>"
                  for s, d, se, b in rows)
    return (f"<html><body><div>Growth: <span>{growth}%</span></div><div>Weeks: {weeks}</div>"
            f"<div>By Equity {dd}% (10 USD)</div>"
            f"<div>Long {long_} ({long_ / max(1, long_ + short) * 100:.2f}%)</div>"
            f"<div>Short {short} (1%)</div><h3>Distribution</h3>"
            f"<table><tr><th>Symbol</th><th>Deals</th><th>Sell</th><th>Buy</th></tr>{trs}"
            f"</table><a href='/en/signals/2375343'>x</a></body></html>")


def test_canonical_maps_broker_tickers_to_one_name() -> None:
    assert canonical("EURUSD.x", UNI) == "EURUSD"
    assert canonical("XAUUSDm", UNI) == "XAUUSD"
    assert canonical("GOLD", UNI) == "XAUUSD"
    assert canonical("US30.cash", UNI) == "US30"
    assert canonical("USTEC", UNI) == "NAS100"
    assert canonical("DE40", UNI) == "GER40"
    assert canonical("BTCUSDT", UNI) == "BTCUSD"
    assert canonical("EURUSDpro", UNI) == "EURUSD"
    assert canonical("Symbol", UNI) is None
    assert canonical("ZZZQQQ", UNI) is None


def test_robots_wildcards_longest_match_and_agent_groups() -> None:
    rules = cc.robots_rules(MQL5_ROBOTS)
    assert cc.robots_allows(rules, "https://www.mql5.com/en/signals/2375343")
    assert not cc.robots_allows(rules, "https://www.mql5.com/en/signals/1/positions/page2")
    assert not cc.robots_allows(rules, "https://www.mql5.com/en/search?q=x")
    assert cc.robots_allows([("/", False), ("/en/", True)], "https://h/en/x")
    assert not cc.robots_allows([("/x$", False)], "https://h/x")
    assert cc.robots_allows([("/x$", False)], "https://h/xy")


def test_unreadable_robots_bars_and_hard_stop_is_recorded_and_not_retried() -> None:
    calls: list[str] = []

    def get(url: str) -> tuple[int | None, str]:
        calls.append(url)
        if url.endswith("robots.txt"):
            return (500, "") if "bad" in url else (404, "")
        return 403, ""

    state: dict = {}
    f = cc.Fetcher(state, deadline=1e18, get=get)
    assert f.fetch("s", "https://bad.example/a") is None
    assert f.stats["s"]["robots_barred"] == 1
    assert f.fetch("t", "https://ok.example/a") is None
    assert state["hard_stops"]["t"]["code"] == 403
    n = len(calls)
    assert f.fetch("t", "https://ok.example/b") is None
    assert len(calls) == n            # never fetched again
    assert f.stats["t"]["hard_stopped"] == 1


def test_mql5_distribution_is_parsed_and_self_checked(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cc, "canonical", lambda s: canonical(s, UNI))
    t = cc.page_text(mql5_page("3 584.65", 68, "33.14", 205, 372,
                               [("XAUUSD", 178, 100, 78), ("EURUSD.x", 56, 10, 40)]))
    q = cc.parse_quality(t)
    assert q["growth_pct"] == pytest.approx(3584.65)
    assert q["weeks"] == 68 and q["dd_pct"] == pytest.approx(33.14)
    fl = cc.parse_mql5_flow(t)
    assert fl["long"] == 205 and fl["short"] == 372
    assert fl["symbols"]["XAUUSD"] == {"deals": 178, "sell": 100, "buy": 78}
    # 10 + 40 != 56: the columns are not (sell, buy), so the row stays unsided
    assert fl["symbols"]["EURUSD"] == {"deals": 56}


def test_flow_delta_signs_sided_rows_and_concentrated_unsided_rows() -> None:
    prev = {"long": 10, "short": 10, "symbols": {"XAUUSD": {"deals": 10, "sell": 5, "buy": 5},
                                                 "EURUSD": {"deals": 4}}}
    cur = {"long": 10, "short": 10, "symbols": {"XAUUSD": {"deals": 14, "sell": 5, "buy": 9},
                                                "EURUSD": {"deals": 4}}}
    d = cc.flow_delta(prev, cur)
    assert d == {"XAUUSD": {"deals": 4.0, "signed": 4.0}}
    cur2 = {"long": 13, "short": 11, "symbols": {"XAUUSD": {"deals": 10, "sell": 5, "buy": 5},
                                                 "EURUSD": {"deals": 9}}}
    d2 = cc.flow_delta(prev, cur2)
    assert d2["EURUSD"]["deals"] == 5 and d2["EURUSD"]["signed"] == pytest.approx(5 * (3 - 1) / 4)
    reset = {"symbols": {"XAUUSD": {"deals": 1}}}
    assert cc.flow_delta(prev, reset) is None
    assert cc.flow_delta(None, cur) is None


def test_positions_rows_skip_pending_orders(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cc, "canonical", lambda s: canonical(s, UNI))
    html = ("<table><tr><th>Symbol</th><th>Type</th><th>Lots</th></tr>"
            "<tr><td>EURUSD.x</td><td>Buy</td><td>1.50</td><td>1.0812</td></tr>"
            "<tr><td>GOLD</td><td>Sell</td><td>0.20</td><td>2400.1</td></tr>"
            "<tr><td>US30</td><td>Buy Limit</td><td>1.00</td><td>39000</td></tr></table>")
    rows = cc.parse_positions(html)
    assert rows == [{"symbol": "EURUSD", "side": "long", "lots": 1.5},
                    {"symbol": "XAUUSD", "side": "short", "lots": 0.2}]


def _obs(src: str, acct: str, g: float, dd: float, w: float, pos=None, flow=None) -> dict:
    return {"source": src, "account": acct, "growth_pct": g, "dd_pct": dd, "weeks": w,
            "positions": pos, "flow": flow, "captured_at": "2026-11-03T00:00:00+00:00"}


def test_cohorts_and_smart_minus_dumb() -> None:
    obs = [_obs("f", f"s{i}", 50 + i, 10, 60, pos=[{"symbol": "EURUSD", "side": "long",
                                                    "lots": 1.0}]) for i in range(10)]
    obs += [_obs("f", f"d{i}", -20 - i, 60, 10, pos=[{"symbol": "EURUSD", "side": "short",
                                                      "lots": 2.0}]) for i in range(10)]
    g = cc.cohorts(obs)
    assert g["smart"] == {"f:s9"}
    assert all(f"f:d{i}" in g["dumb"] for i in range(10))
    b = cc.books(obs)["EURUSD"]
    assert b["pos_net_acct_all"] == pytest.approx(0.0)
    assert b["pos_net_acct_smart"] == 1.0 and b["pos_net_acct_dumb"] == -1.0
    assert b["pos_net_acct_smart_minus_dumb"] == 2.0
    assert b["pos_net_lots_all"] == pytest.approx((10 - 20) / 30)


def test_build_two_passes_writes_pit_series(tmp_path: Path,
                                            monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cc, "canonical", lambda s: canonical(s, UNI))
    monkeypatch.setattr(cc, "RAW", tmp_path / "raw")
    monkeypatch.setattr(cc, "mint_cells", lambda frames, state, dry_run: {"stub": len(frames)})
    pages = {"buy": 78}

    def get(url: str) -> tuple[int | None, str]:
        if url.endswith("robots.txt"):
            return 200, MQL5_ROBOTS
        if url.endswith("/signals/mt5"):
            return 200, "<a href='/en/signals/1111111'>a</a><a href='/en/signals/2222222'>b</a>"
        if "/signals/mt5/page" in url or "/mt4" in url:
            return 200, ""
        if url.endswith("1111111"):
            return 200, mql5_page("900", 80, "8", 205, 372,
                                  [("XAUUSD", 100 + pages["buy"], 100, pages["buy"])])
        return 200, mql5_page("-40", 5, "70", 50, 50, [("XAUUSD", 120 + (pages["buy"] - 78),
                                                         120 + (pages["buy"] - 78), 0)])

    reg = {"sources": {"mql5_signals": {
        "adapter": "mql5", "population_pages": ["https://www.mql5.com/en/signals/mt5",
                                                "https://www.mql5.com/en/signals/mt5/page{n}"],
        "population_max_pages": 3, "account_url": "https://www.mql5.com/en/signals/{id}",
        "per_pass_accounts": 10}, "darwinex": {"adapter": "none", "blocked_by": "x"}}}
    t1 = datetime(2026, 11, 3, 12, tzinfo=UTC)
    st = tmp_path / "state.json"
    d1 = cc.build(get=get, registry=reg, state_path=st, series_root=tmp_path / "s", now=t1)
    assert d1["observations_this_pass"] == 2 and d1["symbols"] == 0     # no baseline yet
    assert d1["gaps"]["darwinex"]["blocked_by"] == "x"
    pages["buy"] = 83
    t2 = t1 + timedelta(hours=1)
    d2 = cc.build(get=get, registry=reg, state_path=st, series_root=tmp_path / "s", now=t2)
    row = d2["book_top"]["XAUUSD"]
    assert row["flow_net_all"] == pytest.approx(0.0)          # +5 buys smart, +5 sells dumb
    assert row["flow_net_smart"] == 1.0 and row["flow_net_dumb"] == -1.0
    assert row["flow_net_smart_minus_dumb"] == 2.0
    df = pd.read_parquet(tmp_path / "s" / "ctc_XAUUSD.parquet")
    assert list(pd.to_datetime(df["available_time"], utc=True)) == [pd.Timestamp(t2)]
    assert (tmp_path / "s" / "ctc_XAUUSD.pit.json").exists()
    assert d2["cells"] == {"stub": 1}


def test_login_wall_is_recorded_not_parsed(monkeypatch: pytest.MonkeyPatch) -> None:
    def get(url: str) -> tuple[int | None, str]:
        if url.endswith("robots.txt"):
            return 404, ""
        if "openpositions" in url:
            return 200, "<div>Open orders</div><div>You are not currently logged in.</div>"
        return 200, "<div>Total return: 12%</div><div>Drawdown: 5%</div>"

    state: dict = {}
    f = cc.Fetcher(state, deadline=1e18, get=get)
    src = {"adapter": "fxblue", "account_url": "https://api.fxblue.com/v?id={id}",
           "positions_url": "https://api.fxblue.com/v?id={id}&mode=openpositions"}
    o = cc.observe("fxblue", src, "u1", f, state, datetime(2026, 11, 3, tzinfo=UTC))
    assert o is not None and o["positions"] is None and o["growth_pct"] == 12
    assert f.stats["fxblue"]["login_wall"] == 1
