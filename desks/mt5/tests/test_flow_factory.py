"""The flow factory: tick tape -> point-in-time flow series -> judged cells, and an honest report.

Pinned here, on fixtures with no network:
  * the bucket arithmetic (tick rule carries the last non-zero sign; OFI is sign(dBid)+sign(dAsk);
    spread and quote rate), and that the OPEN bucket is never written;
  * the series is a vintage: a later pass never rewrites a bucket it already wrote;
  * the families fold buckets onto bars left-labelled and never read a bucket from the future;
  * both families are registered where the sealed gauntlet looks, so the cells reach the judge;
  * a full pass donates with tests_run 0, fetches nothing, reports every family with a status,
    HELD sources carry their terms quote, and the unknown-unknown miner classifies new things.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK.parents[1]), str(_DESK), str(_DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import flow_factory as ff  # noqa: E402
from mt5desk import family_tick_flow as tfam  # noqa: E402

MIN5 = 300_000


def _tape(root: Path, sym: str, days: int = 3, n: int = 6000, seed: int = 1,
          flags: bool = False, start: str = "2026-09-01") -> None:
    rng = np.random.default_rng(seed)
    d = root / sym
    d.mkdir(parents=True, exist_ok=True)
    px = 100.0
    for day in pd.date_range(start, periods=days, freq="D"):
        ms = (day.value // 10**6) + np.sort(rng.integers(0, 86_400_000, n))
        mid = px + np.cumsum(rng.choice([-1, 0, 1], n) * 0.01)
        px = float(mid[-1])
        spr = 0.02 + 0.01 * rng.random(n)
        f = pd.DataFrame({"time_msc": ms, "bid": mid - spr / 2, "ask": mid + spr / 2})
        if flags:
            f["flags"] = rng.choice([6, 38, 70], n)
        f.to_parquet(d / f"{day:%Y%m%d}.parquet", index=False)


# ----------------------------------------------------------------------------- arithmetic
def test_bucket_features_are_the_named_constructions() -> None:
    ms = np.array([0, 1000, 2000, 3000, MIN5 + 10, MIN5 + 20], dtype="int64")
    bid = np.array([1.0, 1.1, 1.1, 1.0, 1.0, 1.2])
    ask = np.array([1.2, 1.3, 1.3, 1.3, 1.3, 1.3])
    mid, spr = (bid + ask) / 2, ask - bid
    g = ff.buckets_from_ticks(ms, mid, spr)
    assert len(g) == 2
    b0 = g.iloc[0]
    # mid: 1.1, 1.2, 1.2, 1.15 -> signs 0, +1, 0, -1; tick rule carries +1 over the flat tick.
    assert b0["mid_sign"] == 0
    assert b0["tick_rule"] == 0 + 1 + 1 - 1
    # OFI unit depth: (dbid, dask) signs: (0,0) (+,+) (0,0) (-,0) -> 0+2+0-1
    assert b0["quote_ofi"] == 1
    assert b0["quote_rate"] == 4
    assert b0["spread_max_bp"] == pytest.approx(0.3 / 1.15 * 1e4)
    assert g.index[1] == pd.Timestamp(MIN5, unit="ms", tz="UTC")


def test_open_bucket_is_never_written_and_old_buckets_never_rewritten(tmp_path: Path) -> None:
    _tape(tmp_path / "t", "EURUSD", days=2)
    days = ff.tape_index(tmp_path / "t")["EURUSD"]
    f1, info1 = ff.build_series("EURUSD", days, None, deadline=1e18)
    assert f1 is not None and info1["new_buckets"] == len(f1)
    last_ms = int(pd.read_parquet(days[max(days)])["time_msc"].max())
    assert f1.index.max() < pd.Timestamp((last_ms // MIN5) * MIN5, unit="ms", tz="UTC")
    assert (f1["available"] - f1.index == pd.Timedelta(minutes=5)).all()
    # Corrupt the OLDER day after it was written and add a new day: the vintage keeps what it
    # wrote and only the new buckets arrive.
    first = days[min(days)]
    raw = pd.read_parquet(first)
    raw["bid"] = raw["bid"] - 5.0
    raw.to_parquet(first, index=False)
    _tape(tmp_path / "t", "EURUSD", days=1, start="2026-09-03", seed=9)
    days2 = ff.tape_index(tmp_path / "t")["EURUSD"]
    f2, info2 = ff.build_series("EURUSD", days2, f1, deadline=1e18)
    assert info2["new_buckets"] > 0
    pd.testing.assert_frame_equal(f2.loc[f1.index, tfam.FEATURES], f1[list(tfam.FEATURES)])


# ----------------------------------------------------------------------------- the families
def _bars_and_series(n_bars: int = 400, seed: int = 3) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2026-08-01", periods=n_bars, freq="1h", tz="UTC")
    close = 100 + np.cumsum(rng.normal(0, 0.2, n_bars))
    bars = pd.DataFrame({"open": close, "high": close + 0.3, "low": close - 0.3,
                         "close": close}, index=idx)
    bidx = pd.date_range(idx[0], idx[-1] + pd.Timedelta("55min"), freq="5min", tz="UTC")
    s = pd.DataFrame({c: rng.normal(0, 1, len(bidx)) for c in tfam.FEATURES}, index=bidx)
    s["quote_rate"] = rng.integers(50, 150, len(bidx)).astype(float)
    s["spread_bp"] = 1 + rng.random(len(bidx))
    s["spread_max_bp"] = s["spread_bp"] * 1.5
    # Inject one-sided flow bursts so the z gate fires.
    for k in range(80, n_bars, 37):
        s.loc[idx[k]:idx[k] + pd.Timedelta("55min"), "tick_rule"] += 6.0
    s.index.name = "bucket"
    return bars, s


def test_on_bars_is_left_labelled_and_never_reads_a_later_bucket() -> None:
    bars, s = _bars_and_series()
    x = tfam.on_bars(s, bars.index, "tick_rule")
    assert x is not None
    t = bars.index[10]
    assert x.loc[t] == pytest.approx(s.loc[t:t + pd.Timedelta("55min"), "tick_rule"].sum())
    # Corrupting everything after bar 200 changes nothing at or before bar 199.
    s2 = s.copy()
    s2.loc[s2.index >= bars.index[200], "tick_rule"] = 1e6
    x2 = tfam.on_bars(s2, bars.index, "tick_rule")
    pd.testing.assert_series_equal(x.iloc[:200], x2.iloc[:200])


@pytest.mark.parametrize("fam,kw", [
    (tfam.family_tick_flow, {"feature": "tick_rule", "mode": "follow"}),
    (tfam.family_tick_flow, {"feature": "spread_bp", "mode": "move_fade", "z_in": 1.0}),
    (tfam.family_flow_residual, {"feature": "tick_rule", "mode": "unabsorbed"}),
])
def test_families_fire_on_the_series_and_have_no_lookahead(fam: Any, kw: dict) -> None:
    bars, s = _bars_and_series()
    sig = fam(bars, series=s, **kw)
    assert sig, "the injected bursts must fire the family"
    cut = bars.index[300]
    s2 = s.copy()
    s2.loc[s2.index >= cut, list(tfam.FEATURES)] *= -50
    bars2 = bars.copy()
    bars2.loc[bars2.index >= cut, ["open", "high", "low", "close"]] *= 3
    early = [(x.time, x.side) for x in sig if x.time < cut]
    early2 = [(x.time, x.side) for x in fam(bars2, series=s2, **kw) if x.time < cut]
    assert early == early2


def test_families_refuse_rather_than_fall_back_to_price(tmp_path: Path) -> None:
    bars, s = _bars_and_series()
    assert tfam.family_tick_flow(bars, source="tf_NOPE") == []
    assert tfam.family_tick_flow(bars, series=s, feature="spread_bp", mode="follow") == []
    assert tfam.family_flow_residual(bars, series=s, feature="quote_rate") == []
    assert tfam.series_path("../etc/passwd") is None
    assert tfam.series_path("tf_A/B") is None


def test_both_families_are_where_the_sealed_gauntlet_looks() -> None:
    from mt5desk import families_orthogonal as fo
    from mt5desk.families import get_family_func

    from libs.research.alpha_clusters import FAMILY_CLUSTER
    for name in ("tick_flow", "flow_residual"):
        assert get_family_func(name) is not None
        assert name in fo.FAMILY_INPUTS and name in fo.FAMILY_TIMEFRAMES
        assert "M1" not in fo.FAMILY_TIMEFRAMES[name][0]
        assert FAMILY_CLUSTER[name] == "session_liquidity"


# ----------------------------------------------------------------------------- the pass
@pytest.fixture
def isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    data = tmp_path / "data"
    (data / "cot").mkdir(parents=True)
    pd.DataFrame({"report_date": pd.to_datetime(["2020-01-07", "2026-08-11"], utc=True)}
                 ).to_parquet(data / "cot" / "gold.parquet", index=False)
    (data / "universe").mkdir()
    (data / "universe" / "universe.json").write_text(json.dumps({
        "EURUSD": {"asset_class": "Forex"}, "XAUUSD": {"asset_class": "Commodities"},
        "UKOIL_Z26": {"asset_class": "Energy"}, "WEIRD": {"asset_class": "Weather Futures"}}))
    (data / "fill_corpus.jsonl").write_text("\n".join(json.dumps(r) for r in [
        {"symbol": "XAUUSD", "session": "asia", "slip_frac": 0.0001, "order_type": "market",
         "decided_at": "2026-09-01T04:00:00+00:00", "retcode": 10009},
        {"symbol": "XAUUSD", "session": "asia", "rejected": True, "reject_reason": "x",
         "order_type": "iceberg_peg", "retcode": 10099,
         "decided_at": "2026-09-02T04:00:00+00:00"}]))
    for name, val in {"FILL_CORPUS": data / "fill_corpus.jsonl",
                      "ORDER_INTENTS": data / "order_intents.jsonl",
                      "COT_DIR": data / "cot", "UNIVERSE_JSON": data / "universe" / "universe.json",
                      "DEPTH_PROBE": data / "depth_probe.json",
                      "DONATED": data / "ff" / "donated.json",
                      "GRAMMAR_STATE": data / "ff" / "grammar.json",
                      "REPORT": tmp_path / "FLOW_FACTORY.json"}.items():
        monkeypatch.setattr(ff, name, val)
    monkeypatch.setattr(ff, "MIN_BUCKETS", 500)
    calls: list[dict[str, Any]] = []
    import proposer_common

    def fake_donate(source: str, candidates: list[dict], tests_run: int) -> Path:
        calls.append({"source": source, "n": len(candidates), "tests_run": tests_run,
                      "candidates": candidates})
        proposer_common.LAST_DONATION.clear()
        proposer_common.LAST_DONATION.update({"donated": len(candidates)})
        return tmp_path / "contract.json"
    monkeypatch.setattr(proposer_common, "donate", fake_donate)

    def no_network(*a: Any, **k: Any) -> Any:
        raise AssertionError("the factory must fetch nothing")
    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", no_network)
    tape = tmp_path / "tape"
    _tape(tape, "EURUSD", days=3)
    _tape(tape, "XAUUSD", days=3, seed=2)
    _tape(tape, "NEWCFD", days=1, seed=4, flags=True)
    return {"tmp": tmp_path, "tape": tape, "series": tmp_path / "series", "calls": calls}


def test_a_pass_collects_mints_and_reports_every_family(isolated: dict[str, Any]) -> None:
    doc = ff.run(tape_dir=isolated["tape"], series_dir=isolated["series"])
    assert (isolated["series"] / "tf_EURUSD.parquet").exists()
    assert json.loads(ff.REPORT.read_text())["seat"] == "flow_factory"
    calls = isolated["calls"]
    assert len(calls) == 1 and calls[0]["tests_run"] == 0
    assert doc["donated"]["trials_charged"] == 0
    per = len(ff.TICK_GRID) * len(ff.CHARTS)
    assert doc["grid"]["total"] == 2 * per            # NEWCFD has one day: under MIN_BUCKETS
    fams = {r["key"]: r for r in doc["families"]}
    assert {r["status"] for r in fams.values()} <= {"COLLECTING", "HELD", "NEEDS_KEY",
                                                    "UNMEASURED"}
    for key in ("orderflow_minus_price_response", "options_flow_minus_underlying_response",
                "dealer_hedge_pressure_minus_realized_move",
                "iv_change_minus_realized_vol_change", "oi_change_minus_volume",
                "futures_flow_minus_cfd_response", "cross_venue_lead_minus_mt5_reaction",
                "gamma_state_x_ofi", "auction_imbalance_x_overnight"):
        assert fams[key]["priority_residual"] is True
    assert fams["orderflow_ticks"]["status"] == "COLLECTING"
    assert fams["orderflow_ticks"]["judge"]["reaches_judge"] is True
    assert fams["orderflow_minus_price_response"]["cells_generated"] == 2 * 8
    assert fams["cot_positioning"]["status"] == "COLLECTING"
    assert fams["cot_positioning"]["history"]["first"] == "2020-01-07"
    assert fams["own_execution_state"]["status"] == "COLLECTING"
    assert fams["own_execution_state"]["cells_generated"] == 0
    for key in ("options_tape", "dealer_hedge_pressure_minus_realized_move",
                "crypto_reference_options", "off_exchange_short_volume", "depth_queue_l2_l3"):
        assert fams[key]["status"] == "HELD" and fams[key]["why"]
    for r in fams.values():
        for s in r["sources"]:
            assert r["pit"][s] and r["publication_lag"][s]
    # Each identity is donated once: a second pass donates nothing new.
    ff.run(tape_dir=isolated["tape"], series_dir=isolated["series"])
    assert len(isolated["calls"]) == 1


def test_a_dry_run_writes_no_series_no_state_and_no_donation(isolated: dict[str, Any]) -> None:
    out = isolated["tmp"] / "dry.json"
    doc = ff.run(dry_run=True, tape_dir=isolated["tape"], series_dir=isolated["series"], out=out)
    assert out.exists() and doc["status"] == "DRY_RUN"
    assert not isolated["series"].exists()
    assert not ff.GRAMMAR_STATE.exists() and not ff.DONATED.exists()
    assert isolated["calls"] == []


def test_no_tape_on_this_host_is_unmeasured_never_zero(isolated: dict[str, Any]) -> None:
    doc = ff.run(dry_run=True, tape_dir=isolated["tmp"] / "absent",
                 series_dir=isolated["series"], out=isolated["tmp"] / "d.json")
    fams = {r["key"]: r for r in doc["families"]}
    assert fams["orderflow_ticks"]["status"] == "UNMEASURED"
    assert "trading box" in fams["orderflow_ticks"]["history"]["why"]


def test_the_unknown_unknown_miner_classifies_what_the_grammar_does_not_name(
        isolated: dict[str, Any]) -> None:
    doc = ff.run(tape_dir=isolated["tape"], series_dir=isolated["series"])
    m = doc["unknown_unknown_miner"]
    kinds = {(f["kind"], f["value"]) for f in m["finds"]}
    assert ("new_product", "NEWCFD") in kinds
    assert ("new_tick_flag", "BUY") in kinds and ("new_tick_flag", "SELL") in kinds
    assert ("new_asset_class", "Weather Futures") in kinds
    assert ("expiry_convention", "UKOIL_Z26:Z26") in kinds
    assert ("new_order_type", "iceberg_peg") in kinds
    assert ("new_retcode", "10099") in kinds
    assert m["candidate_cells"] >= len(m["finds"])
    assert "NEWCFD" in doc["grammar"]["axes"]["instrument"]
    assert "BUY" in json.loads(ff.GRAMMAR_STATE.read_text())["aggressor"]


def test_terms_fail_closed() -> None:
    for sid, s in ff.SOURCES.items():
        assert s["verdict"] in (ff.PERMITTED, ff.HELD, ff.FIRST_PARTY), sid
        assert s["terms_quote"] and s["checked_at"]
        if s["verdict"] == ff.PERMITTED:
            assert s["terms_url"].startswith("https://") and "(not" not in s["terms_quote"]
        if s["verdict"] == ff.HELD:
            assert s.get("why_held")
            assert s.get("collector") is None


def test_the_leg_is_wired_into_the_hourly_cycle() -> None:
    src = (_DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert '_costed("flow_factory", flow_factory)' in src
    assert '"flow_factory": flf' in src
    from libs.research.layers import LEG_LAYER
    from research import hourly_cycle as hc
    assert hc.LEG_BUDGET_SEC["flow_factory"] > 900
    assert hc.LEG_DEPARTMENT["flow_factory"] == "data"
    assert LEG_LAYER["flow_factory"] == "prediction"
