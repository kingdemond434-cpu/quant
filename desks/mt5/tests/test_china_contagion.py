"""China supply-chain / credit knowledge graph and contagion (GAP_MAP 31).

  0. the graph labels every edge MEASURED (a lawful source; none today) or STRUCTURAL (named
     prior), signs follow the quote convention, havens stay unsigned, and the commodity channel adds through measured
     export shares;
  1. the knowledge adjacency is fixed, signed, zero-diagonal, row-normalised, zero for a symbol
     the graph does not reach, and the learned GNN takes it (both knowledge kinds);
  2. UN Comtrade is fenced REFUSED_ON_TERMS: the ingest sends nothing, writes nothing, carries
     no fetch code, and the leg publishes the measured-weights gap as a missed-growth line;
  3. the stress index is causal and signed, leaves the target out, and the family trades the
     NEXT day in the graph's direction;
  4. the contagion study measures betas, agrees with a planted channel, scores the graph against
     the market, and the leg charges every grid point it ran;
  5. the leg, layer, graph node and family registration are wired.
All inputs are synthetic.
"""
from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK / "research"), str(DESK), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.models import learned_propagation as LP  # noqa: E402
from libs.research import china_graph as G  # noqa: E402
from mt5desk import family_china_contagion as F  # noqa: E402
from research import china_contagion as CC  # noqa: E402
from research import china_exposure_ingest as ING  # noqa: E402

NOW = datetime(2026, 11, 14, 6, 0, tzinfo=UTC)


# ------------------------------------------------------------------------------------ graph
def test_graph_labels_edges_and_signs_follow_the_quote():
    g = G.build({})
    assert all(e.status == G.STRUCTURAL for e in g.edges)
    ex = G.exposures(g)
    assert ex["USDCNH"]["sign"] == 1 and ex["CHINAH"]["sign"] == -1
    assert ex["AUDUSD"]["sign"] == -1 and ex["USDKRW"]["sign"] == 1
    assert ex["XCUUSD"]["exposure"] == pytest.approx(-1.0)
    for haven in ("USDJPY", "USDCHF", "XAUUSD"):
        assert ex[haven]["sign"] == 0 and "measured" in ex[haven]["why"]

    m = {"year": 2025, "countries": {"AUS": {"china_share": 0.30, "year": 2025,
                                             "chapter_share": {"26": 0.25, "74": 0.01}}}}
    g2 = G.build(m)
    aus = [e for e in g2.edges if e.dst == "AUS"]
    assert {e.status for e in aus} == {G.MEASURED}
    ex2 = G.exposures(g2)
    # direct 0.30 + ores channel 0.35 * 0.25 * 0.5 + copper 1.0 * 0.01 * 0.5 -> AUDUSD more exposed
    want = -(0.30 + 0.35 * 0.25 * G.COMMODITY_CHANNEL + 1.0 * 0.01 * G.COMMODITY_CHANNEL)
    assert ex2["AUDUSD"]["exposure"] == pytest.approx(want, abs=1e-4)
    assert ex2["AUDUSD"]["measured_share"] == 1.0
    assert ex["NZDUSD"]["measured_share"] == 0.0


def test_knowledge_adjacency_is_fixed_signed_and_feeds_the_gnn():
    syms = ["AUDUSD", "USDKRW", "NZDUSD", "XAUUSD", "USDCNH", "EURUSD"]
    a = G.knowledge_adjacency(syms, G.build({}), top_k=0)
    assert np.allclose(np.diag(a), 0) and np.allclose(a[3], 0)        # gold: unsigned, no row
    assert a[0, 1] < 0 < a[0, 2]                                        # AUD vs KRW opposite
    nz = np.abs(a).sum(axis=1)
    assert np.allclose(nz[nz > 0], 1.0)
    # the GNN: a fixed knowledge adjacency needs no returns; the learned one is masked to it
    k = LP.knowledge_adjacency(tuple(syms), "knowledge", top_k=2)
    assert (np.count_nonzero(k, axis=1) <= 2).all()
    rng = np.random.default_rng(0)
    x0 = rng.normal(size=(300, len(syms)))
    y = np.vstack([x0[1:], np.zeros((1, len(syms)))]) + rng.normal(size=(300, len(syms)))
    kl = LP.knowledge_adjacency(tuple(syms), "knowledge_lead_lag", x0, y, top_k=0)
    prior = G.knowledge_adjacency(syms, top_k=0)
    assert np.all(kl[prior == 0] == 0)
    with pytest.raises(ValueError):
        LP.adjacency(x0, y, "knowledge")
    assert {"adjacency": "knowledge", "layers": 1} in LP.GNN_GRID
    assert {"adjacency": "knowledge_lead_lag", "layers": 1} in LP.GNN_GRID


def test_gnn_runs_on_the_knowledge_graph_walk_forward():
    rng = np.random.default_rng(3)
    syms = ("AUDUSD", "USDKRW", "NZDUSD", "USDCNH", "EURUSD")
    t_n, n = 700, len(syms)
    z = rng.normal(size=(t_n, n))
    y = np.full((t_n, n), np.nan)
    y[:-1] = z[1:]
    x = np.stack([z, z, z, z, z], axis=-1)
    d = LP.Design(z=z, y=y, x=x, sigma=np.ones((t_n, n)), symbols=syms)
    for kind in ("knowledge", "knowledge_lead_lag"):
        p = LP.predictions(d, "gnn", {"adjacency": kind, "layers": 1})
        assert p.shape == (t_n, n) and np.isfinite(p[-50:]).any()


# ------------------------------------------------------------------------------------- fence
def test_comtrade_is_fenced_refused_on_terms_and_fetches_nothing(tmp_path, monkeypatch):
    """Auditor ruling on #1155: UN Comtrade licence s.5 refuses automated retrieval. The module
    sends nothing, writes nothing and carries no fetch code; the leg reports the fence."""
    import urllib.request

    def no_net(*a, **k):  # pragma: no cover - reaching here is the failure
        raise AssertionError("the fence sent a request")
    monkeypatch.setattr(urllib.request, "urlopen", no_net)
    monkeypatch.chdir(tmp_path)
    d = ING.refresh(force=True, now=NOW)
    assert d["status"] == "REFUSED_ON_TERMS" and d["refreshed"] is False
    assert d["n_measured"] == 0 and "license-agreement" in d["terms"]
    assert list(tmp_path.iterdir()) == []
    src = (DESK / "research" / "china_exposure_ingest.py").read_text("utf-8")
    for token in ("urlopen", "urllib", "requests", "comtradeapi", "write_text", "open("):
        assert token not in src, token
    assert not hasattr(G, "load_measured") and not hasattr(G, "EXPOSURE_FILE")


# ------------------------------------------------------------------------- stress + family
def _bars(daily: np.ndarray, start: str = "2023-01-02", seed: int = 0) -> pd.DataFrame:
    """H1 bars whose daily close follows exp(cumsum(daily)); flat inside the day."""
    rng = np.random.default_rng(seed)
    days = pd.date_range(start, periods=len(daily), freq="D", tz="UTC")
    px = 100.0 * np.exp(np.cumsum(daily))
    idx, close = [], []
    for d0, p in zip(days, px, strict=True):
        for h in range(24):
            idx.append(d0 + pd.Timedelta(hours=h))
            close.append(p * (1 + 1e-5 * rng.normal()))
    c = np.array(close)
    return pd.DataFrame({"open": c, "high": c * 1.001, "low": c * 0.999, "close": c},
                        index=pd.DatetimeIndex(idx))


def _world(n_days: int = 700, seed: int = 1, lagged: bool = True):
    rng = np.random.default_rng(seed)
    shock = rng.normal(0, 0.01, n_days)                                 # China stress, +=worse
    src = {"USDCNH": _bars(0.5 * shock + rng.normal(0, 0.004, n_days), seed=2),
           "CHINAH": _bars(-1.2 * shock + rng.normal(0, 0.01, n_days), seed=3),
           "HK50": _bars(-1.0 * shock + rng.normal(0, 0.01, n_days), seed=4),
           "XCUUSD": _bars(-0.8 * shock + rng.normal(0, 0.01, n_days), seed=5)}
    nxt = np.concatenate([[0.0], shock[:-1]]) if lagged else shock
    aud = _bars(-0.6 * nxt + rng.normal(0, 0.004, n_days), seed=6)     # catches up next day
    return shock, src, aud


def test_stress_index_is_causal_signed_and_leaves_the_target_out():
    shock, src, _ = _world()
    st = F.stress_index(src, G.stress_sources())
    s = st["stress"].dropna()
    real = pd.Series(shock, index=pd.date_range("2023-01-02", periods=len(shock), tz="UTC"))
    assert np.corrcoef(s.to_numpy(), real.reindex(s.index).to_numpy())[0, 1] > 0.8
    loo = F.stress_index(src, G.stress_sources(), exclude="USDCNH")
    assert int(loo["n_sources"].max()) == 3
    # perturbing the LAST day's prices cannot change any earlier day's stress
    src2 = dict(src)
    hk = src["HK50"].copy()
    hk.iloc[-24:, hk.columns.get_loc("close")] *= 1.2
    src2["HK50"] = hk
    st2 = F.stress_index(src2, G.stress_sources())
    pd.testing.assert_series_equal(st["stress"].iloc[:-1], st2["stress"].iloc[:-1])


def test_family_trades_the_next_day_in_the_graph_direction():
    _, src, aud = _world()
    sig = F.family_china_stress_contagion(aud, symbol="AUDUSD", exposure_sign=-1, sources=src,
                                          entry_z=1.5, window=1, hold_bars=24)
    assert sig, "a planted stress series must fire"
    st = F.stress_index(src, G.stress_sources(), exclude="AUDUSD")["stress"]
    for s in sig[:20]:
        day = pd.Timestamp(s.time).normalize()
        prev = st[st.index < day].iloc[-1]
        assert abs(prev) >= 1.5 and s.side == -int(np.sign(prev))
        assert pd.Timestamp(s.time).hour >= 2
    rev = F.family_china_stress_contagion(aud, symbol="AUDUSD", exposure_sign=-1, sources=src,
                                          direction="opposite", entry_z=1.5)
    assert [s.side for s in rev[:10]] == [-s.side for s in sig[:10]]
    assert F.family_china_stress_contagion(aud, symbol="AUDUSD", exposure_sign=0,
                                           sources=src) == []
    assert F.family_china_stress_contagion(aud, symbol="AUDUSD", exposure_sign=-1,
                                           sources={"USDCNH": src["USDCNH"]}) == []


# ------------------------------------------------------------------------ study + leg
def test_contagion_study_finds_a_planted_channel_and_scores_the_graph():
    shock, src, aud_lag = _world(lagged=True)
    rng = np.random.default_rng(9)
    n = len(shock)
    bars = {**src, "AUDUSD": aud_lag,
            "NZDUSD": _bars(-0.5 * shock + rng.normal(0, 0.004, n), seed=10),
            "USDKRW": _bars(0.4 * shock + rng.normal(0, 0.004, n), seed=11),
            "USDBRL": _bars(0.3 * shock + rng.normal(0, 0.006, n), seed=12),
            "EURUSD": _bars(-0.05 * shock + rng.normal(0, 0.004, n), seed=13),
            "XAUUSD": _bars(0.3 * shock + rng.normal(0, 0.004, n), seed=14)}
    ex = G.exposures(G.build({}))
    m = CC.measure(bars, ex)
    aud = m["instruments"]["AUDUSD"]
    assert aud["next_day"]["beta"] < 0 and aud["next_day"]["t"] < -3
    assert aud["walk_forward"]["status"] == "MEASURED" and aud["walk_forward"]["oos_ic"] > 0
    assert m["instruments"]["NZDUSD"]["sign_agrees"] is True
    assert m["instruments"]["XAUUSD"]["measured_sign"] == 1           # haven, measured not assumed
    assert m["instruments"]["USDTHB"]["status"] == "UNMEASURED_NO_BARS"
    assert m["graph_vs_market"]["status"] == "MEASURED"
    assert m["graph_vs_market"]["sign_agreement"] >= 0.8

    rep = CC.run(bars=bars, donate=False, write=False, refresh_weights=True, budget_s=120,
                 now=NOW)
    assert rep["status"] == "OK"
    p = rep["proposer"]
    # every unsigned instrument the market measured is admitted with its sign (no |t| screen),
    # so every grid point it ran is charged
    admitted = {s for s, r in m["instruments"].items() if r.get("measured_sign")}
    reached_with_bars = len({s for s in G.reached() if s in bars} | admitted)
    assert p["tests_attempted"] == len(CC.GRID) * reached_with_bars
    assert rep["weights"]["status"] == "REFUSED_ON_TERMS"
    mg = rep["missed_growth"]
    assert mg["measured_mass_share"] == 0.0 and mg["cost_elog"] == "UNMEASURED"
    assert mg["n_measured_edges"] == 0 and "missed_growth.jsonl" in mg["where"]
    assert rep["official_notice_sources"]["CSRC"].startswith("REFUSED")
    assert rep["credit_proxy"].startswith("PRICE_SIDE")


def test_no_sources_charges_no_trials():
    _, _, aud = _world()
    rep = CC.run(bars={"AUDUSD": aud}, donate=False, write=False, refresh_weights=False,
                 now=NOW)
    assert rep["status"] == "UNMEASURED_NO_STRESS_SOURCES"
    assert rep["proposer"]["tests_attempted"] == 0


def test_wired():
    hc = (DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert '"china_contagion", "research/china_contagion.py"' in hc
    assert '"china_contagion": chc' in hc
    from libs.research import layers
    assert layers.LEG_LAYER["china_contagion"] == "information"
    cg = (ROOT / "libs" / "ops" / "capability_graph.py").read_text("utf-8")
    assert '"desks/mt5/research/china_contagion.py"' in cg
    from mt5desk import families_orthogonal as fo
    assert fo.ORTHOGONAL_FAMILIES["china_stress_contagion"] is F.family_china_stress_contagion
