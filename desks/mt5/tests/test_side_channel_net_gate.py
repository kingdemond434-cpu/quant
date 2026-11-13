"""Every side-channel miner's traffic goes through one door: refused hosts are never contacted,
robots are read fail closed under the agent sent, and no browser User-Agent is ever sent."""
from __future__ import annotations

import sys
import urllib.error
import urllib.robotparser
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "side_channels"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import net_gate as G  # noqa: E402
import run_all_miners as ram  # noqa: E402


def _rules(lines):
    rp = urllib.robotparser.RobotFileParser()
    rp.parse(lines)
    return rp


def test_refused_hosts_never_reach_robots(monkeypatch) -> None:
    monkeypatch.setattr(G, "_robots", lambda *a: pytest.fail("robots read for a refused host"))
    for url in ("https://www.youtube.com/x", "https://api.stlouisfed.org/fred/x",
                "https://api.open-meteo.com/v1/forecast", "https://kr.investing.com/a"):
        assert G.refusal(url).startswith("BLOCKED_TERMS")


def test_robots_fail_closed_and_disallow_refuses(monkeypatch) -> None:
    monkeypatch.setattr(G, "_ROBOTS", {
        "https://a.example.org": _rules(["User-agent: *", "Disallow: /private"]),
        "https://down.example.org": "robots.txt unreadable (HTTP 500)"})
    assert G.refusal("https://a.example.org/private/x").startswith("ROBOTS_REFUSED")
    assert G.refusal("https://down.example.org/x").startswith("ROBOTS_REFUSED")
    assert G.refusal("https://a.example.org/open") is None


def test_robots_status_codes(monkeypatch) -> None:
    def fail(code):
        def _open(req, timeout=None):
            raise urllib.error.HTTPError(req.full_url, code, "x", {}, None)
        return _open
    for code, allowed in ((404, True), (403, False), (500, False)):
        monkeypatch.setattr(G, "_ROBOTS", {})
        monkeypatch.setattr(G, "_ORIGINAL_URLOPEN", fail(code))
        assert (G.refusal("https://h.example.org/x") is None) is allowed


def test_browser_agents_are_replaced_and_contacts_kept() -> None:
    assert G.honest_agent("Mozilla/5.0 (Windows NT 10.0) Chrome/126") == G.AGENT
    assert G.honest_agent("python-requests/2.32") == G.AGENT
    contact = "desk research contact@example.org"
    assert G.honest_agent(contact) == contact


def test_installed_door_blocks_requests_and_urllib(monkeypatch) -> None:
    import urllib.request

    import requests
    monkeypatch.setattr(urllib.request, "urlopen", urllib.request.urlopen)
    monkeypatch.setattr(requests.Session, "request", requests.Session.request)
    G.install()
    with pytest.raises(requests.RequestException):
        requests.get("https://www.reddit.com/r/forex.json", timeout=1)
    with pytest.raises(G.Refused):
        urllib.request.urlopen("https://www.tradingview.com/ideas/")


def test_no_blocked_channel_is_loaded_and_each_is_reported(monkeypatch) -> None:
    names = {n for n, _ in ram.ALL_MINERS}
    assert not names & set(ram.BLOCKED_ON_TERMS)
    assert len(names | set(ram.BLOCKED_ON_TERMS)) == 25
    assert "youtube" not in names
    monkeypatch.setattr(ram, "ALL_MINERS", [("cot", None)])
    monkeypatch.setattr(ram, "_run_miner", lambda name, fn: ("ok", [{"n": name}]))
    monkeypatch.delenv("QUANT_MINERS_ALLOW", raising=False)
    r = ram.run_all_miners()
    assert r["youtube"]["status"] == "BLOCKED_ON_TERMS"
    assert r["summary"]["producing"] == ["cot"]


def _write_bars(tmp_path, sym, rets):
    idx = pd.date_range("2018-01-01", periods=len(rets), freq="1D", tz="UTC")
    close = 100 * np.exp(np.cumsum(rets))
    frame = pd.DataFrame({"close": close}, index=idx.rename("time"))
    frame.to_parquet(tmp_path / f"{sym}_H1.parquet")


def test_correlation_miner_reports_a_break_between_two_instruments(tmp_path, monkeypatch) -> None:
    import _bars
    import correlation_miner as C
    rng = np.random.default_rng(3)
    n = 900
    common = rng.normal(0, 0.01, n)
    a = common + rng.normal(0, 0.002, n)
    b = common + rng.normal(0, 0.002, n)
    b[-30:] = -common[-30:] + rng.normal(0, 0.002, 30)          # the relationship flips
    _write_bars(tmp_path, "EURUSD", a)
    _write_bars(tmp_path, "GBPUSD", b)
    monkeypatch.setattr(_bars, "hypothesis_symbols", lambda u=None: ["EURUSD", "GBPUSD"])
    rows = C.mine_correlations(tmp_path)
    assert rows and rows[0]["symbols"] == ["EURUSD", "GBPUSD"] and rows[0]["z"] < -C.Z_MIN


def test_seasonality_month_effect_is_a_t_statistic_across_years() -> None:
    import seasonality_miner as S
    idx = pd.date_range("2016-01-01", "2025-12-31", freq="1D", tz="UTC")
    step = np.where(idx.month == 3, 0.002, 0.0)
    close = pd.Series(100 * np.exp(np.cumsum(step + 1e-5 * np.sin(np.arange(len(idx))))), index=idx)
    row = S.month_effect(close, 3)
    assert row is not None and row["n"] >= 9 and row["t"] > S.T_MIN and row["hit"] == 1.0
    assert S.month_effect(close.iloc[:100], 3) is None


def test_cot_rows_come_from_the_open_data_route_with_z_scores() -> None:
    import cot_miner as C
    idx = pd.date_range("2023-01-03", periods=170, freq="7D", tz="UTC")
    base = 0.1 + np.random.default_rng(1).normal(0, 0.02, 170)
    base[-1] = 0.3

    def fetch(code):
        return pd.Series(base, index=idx)
    rows = C.mine_cot(fetch)
    kinds = {r["type"] for r in rows}
    assert {"positioning", "extreme_positioning", "positioning_shift"} <= kinds
    assert all(r["symbols"] for r in rows)
    assert "Mozilla" not in Path(C.__file__).read_text("utf-8")
