"""The leadership atlas and the component harvester are clocked, fed and reach the Judge.

WHAT THIS PINS, on synthetic inputs only:
  * leadership atlas: a release instant from calendar_backfill + broker-clock ticks -> true-UTC
    first passages; a planted leader that moves 120s before its follower on every release
    becomes an edge with the right orientation, lag, Wilson bound and direction agreement, and
    is donated as a STRUCTURED_LEAD_LAG-shaped anomaly row the candidate compiler accepts;
    events are never counted twice; nothing after t0 sets sigma or the reference price;
  * component harvest: a rejected recipe splits into entry/stop/exit/session/regime; a planted
    informative entry with a destructive exit is HARVESTED (IS and OOS t >= 2) and flagged
    EXIT_DESTROYED_EDGE; it is re-mated with a time exit using only keys the family accepts and
    enqueued once with its parent; an uninformative entry is not; a cell is examined once;
  * both organs are hourly legs with a layer.
"""
from __future__ import annotations

import gzip
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from side_channels import leadership_atlas_miner as la  # noqa: E402
from side_channels.sources.strategy import component_harvesting as ch  # noqa: E402

# ------------------------------------------------------------------------------ atlas


def _broker(t_utc: pd.Timestamp) -> pd.Timestamp:
    """The broker stamp for a true-UTC instant (NY wall time + 7h), naive."""
    return (t_utc.tz_convert("America/New_York").tz_localize(None) + pd.Timedelta(hours=7))


def _write_ticks(root: Path, sym: str, t0: pd.Timestamp, move_at_s: int | None, sign: int,
                 seed: int) -> None:
    rng = np.random.default_rng(seed)
    secs = np.arange(-1800, 1800)
    px = 1.1 + np.cumsum(rng.normal(0, 2e-6, len(secs)))
    if move_at_s is not None:
        px[secs >= move_at_s] += sign * 0.002
    utc = t0 + pd.to_timedelta(secs, unit="s")
    broker = [_broker(t) for t in utc]
    df = pd.DataFrame({"time_msc": [int(b.value // 10**6) for b in broker],
                       "bid": px - 1e-5, "ask": px + 1e-5})
    day = broker[len(broker) // 2].date().isoformat()
    d = root / sym
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{day}.parquet"
    if p.exists():
        df = pd.concat([pd.read_parquet(p), df], ignore_index=True)
    df.to_parquet(p, index=False)


def _calendar(root: Path, instants: list[pd.Timestamp]) -> None:
    root.mkdir(parents=True, exist_ok=True)
    with gzip.open(root / "backfill_fred_usrel_payems.jsonl.gz", "wt", encoding="utf-8") as fh:
        for t in instants:
            fh.write(json.dumps({"event_date": t.isoformat(), "title": "Nonfarm payrolls",
                                 "series": "PAYEMS"}) + "\n")


def test_first_passage_uses_only_pre_event_quotes() -> None:
    t0 = pd.Timestamp("2026-03-06 13:30", tz="UTC")
    idx = t0 + pd.to_timedelta(np.arange(-1800, 600), unit="s")
    rng = np.random.default_rng(0)
    mid = pd.Series(1.1 + np.cumsum(rng.normal(0, 2e-6, len(idx))), index=idx)
    mid[mid.index >= t0 + pd.Timedelta(seconds=30)] += 0.003
    a = la.first_passage(mid, t0)
    b = la.first_passage(mid[mid.index <= t0 + pd.Timedelta(seconds=40)], t0)
    assert a is not None and b is not None
    assert a["sigma_1s"] == b["sigma_1s"]
    assert a["first_move"] == t0 + pd.Timedelta(seconds=30) and a["sign"] == 1


def test_atlas_learns_a_planted_leader_and_donates_a_lead_lag_row(tmp_path: Path,
                                                                 monkeypatch: pytest.MonkeyPatch
                                                                 ) -> None:
    ticks, cal, uni, out = (tmp_path / x for x in ("ticks", "cal", "uni", "out"))
    uni.mkdir()
    for s in ("USDJPY", "XAUUSD"):
        for c in ("M1", "H1"):
            (uni / f"{s}_{c}.parquet").write_bytes(b"x")
    instants = [pd.Timestamp("2025-01-10 13:30", tz="UTC") + pd.DateOffset(months=i)
                for i in range(16)]
    for i, t in enumerate(instants):
        sign = 1 if i % 2 else -1
        _write_ticks(ticks, "USDJPY", t, 20, sign, seed=i)
        _write_ticks(ticks, "XAUUSD", t, 140, -sign, seed=100 + i)
    _calendar(cal, instants)
    work, rep = tmp_path / "work", tmp_path / "rep.json"
    kw = dict(budget_s=120, calendar_root=cal, ticks_root=ticks, universe_root=uni, out_dir=out,
              work_dir=work, report_path=rep, watch=("USDJPY", "XAUUSD"))
    doc = la.run(**kw)
    assert doc["events_new_this_pass"] == 16 and doc["donated"] >= 1
    assert doc["bh_rejected"] >= 1 and doc["keys_tested"] >= doc["bh_rejected"]
    # only donations reach data/intelligence; state, edge table and matrix stay in the work dir
    assert {p.name.split("_")[0] for p in out.iterdir()} == {"discoveries"}
    assert (work / "atlas_state.json").exists() and rep.exists()
    rows = json.loads(next(out.glob("discoveries_*.json")).read_text("utf-8"))
    r = next(x for x in rows if x["regime"] == "all")
    assert r["kind"] == "anomaly" and r["family_hint"] == "release_lead_lag"
    assert r["against"] == "USDJPY" and r["symbols"] == ["XAUUSD"]
    assert r["corr"] == -1.0 and r["chart"] == "M1" and r["horizon"] == 2
    assert r["event_type"] == "US_NFP" and r["wilson_lb"] >= la.MIN_WILSON
    assert r["p_value"] < la.FDR_Q and r["tests_charged"] == doc["keys_tested"]
    assert r["claim_family"] == "leadership_atlas:US_NFP" and r["claim_selection_trials"] >= 1
    # every regime-conditioned donation names the LEADER's regime
    assert all(x["regime"] in ("all", "calm", "stressed") for x in rows)
    # a second pass adds no event twice and re-donates nothing unchanged
    doc2 = la.run(**kw)
    assert doc2["events_new_this_pass"] == 0 and doc2["events_total_processed"] == 16
    assert doc2["donated"] == 0 and doc2["unchanged_not_redonated"] >= 1


def test_bh_controls_the_search_and_regime_keys_follow_the_leader() -> None:
    p = {f"k{i}": 0.01 for i in range(3)}
    assert la.bh_reject(p, 0.05, m=3) == set(p)
    assert la.bh_reject(p, 0.05, m=1000) == set()           # the whole search is charged
    ar = la.AtlasRun()
    t = pd.Timestamp("2026-01-01", tz="UTC")
    for i in range(14):
        ar.record({"event_type": "X"}, {
            "AAA": {"first_move": t + pd.Timedelta(seconds=90), "sign": 1, "quote_move": None,
                    "sigma_1s": 1.0 + i},
            "BBB": {"first_move": t, "sign": 1, "quote_move": None, "sigma_1s": 1.0}})
    edges, pvals = ar.edges()
    assert all(e.leader == "BBB" for e in edges.values())
    # AAA follows: a key conditioned on AAA's regime is counted but never becomes an edge
    assert any("AAA=" in k for k in pvals) and not any("AAA" == e.leader for e in edges.values())


def test_calendar_skips_alfred_and_date_only_rows(tmp_path: Path) -> None:
    from mt5desk import release_calendar as rc
    root = tmp_path / "cal"
    root.mkdir()
    with gzip.open(root / "a.jsonl.gz", "wt", encoding="utf-8") as fh:
        for row in ({"event_date": "2026-01-09T13:30:00+00:00", "title": "Nonfarm payrolls"},
                    {"event_date": "2026-01-09", "title": "Nonfarm payrolls"},
                    {"event_date": "2026-01-09T13:30:00", "title": "Nonfarm payrolls"},
                    {"event_date": "2026-02-06T13:30:00+00:00", "title": "Nonfarm payrolls",
                     "source": "alfred_first_release"}):
            fh.write(json.dumps(row) + "\n")
    counts: dict[str, int] = {}
    evs = rc.calendar_events(root, tmp_path / "none", counts)
    assert [e["time"] for e in evs] == [pd.Timestamp("2026-01-09 13:30", tz="UTC")]
    assert counts == {"skipped_not_an_instant": 2, "skipped_alfred": 1}


def test_release_lead_lag_family_fires_only_after_the_release() -> None:
    from mt5desk.family_release_lead_lag import family_release_lead_lag
    rng = np.random.default_rng(5)
    idx = pd.date_range("2026-01-01", periods=4000, freq="min", tz="UTC")
    drv = pd.DataFrame({"close": 100 * np.exp(np.cumsum(rng.normal(0, 1e-4, len(idx))))},
                       index=idx)
    c = 50 * np.exp(np.cumsum(rng.normal(0, 1e-4, len(idx))))
    tgt = pd.DataFrame({"open": c, "high": c * 1.0002, "low": c * 0.9998, "close": c},
                       index=idx)
    ev = [idx[600], idx[1500], idx[2500]]
    for e in ev:                                   # the driver jumps on each release bar
        i = idx.get_loc(e)
        drv.iloc[i:, 0] *= 1.01
    sigs = family_release_lead_lag(tgt, driver=drv, driver_symbol="DRV", event_type="X",
                                   lag=2, direction="opposite", bar_events=ev)
    assert [s.time for s in sigs] == ev and all(s.side == -1 for s in sigs)
    assert family_release_lead_lag(tgt, driver=drv, event_type="", bar_events=ev) == []
    assert family_release_lead_lag(tgt, driver=drv, event_type="X", regime="calm",
                                   bar_events=ev) == []          # < MIN_PRIOR prior releases


def test_atlas_donation_compiles_faithfully() -> None:
    from research import miner_candidate_compiler as mcc
    row = {"kind": "anomaly", "family_hint": "release_lead_lag", "symbols": ["XAUUSD"],
           "against": "USDJPY", "horizon": 2, "corr": -1.0, "chart": "M1",
           "event_type": "US_NFP", "regime": "stressed",
           "condition": "release_lead_lag_USDJPY_US_NFP_lag2"}
    cands, why = mcc.compile_row("leadership_atlas", row, {"XAUUSD", "USDJPY"})
    assert why == "STRUCTURED_RELEASE_LEAD_LAG" and len(cands) == 1
    c = cands[0]
    assert c["family"] == "release_lead_lag" and c["symbol"] == "XAUUSD"
    assert c["params"] == {"driver_symbol": "USDJPY", "lag": 2, "direction": "opposite",
                           "event_type": "US_NFP", "regime": "stressed", "timeframe": "M1"}
    # the chart is pinned: axis expansion leaves the cell as it is (no 16-cell fan-out)
    assert mcc.expand_axes([c]) == [c]
    from mt5desk.families import get_family_func
    assert get_family_func("release_lead_lag") is not None


def test_wilson_bound() -> None:
    assert la.wilson_lb(16, 16) > 0.79 and la.wilson_lb(8, 16) < 0.3


# ------------------------------------------------------------------------------ harvest


def _bars(n: int = 3000, seed: int = 1) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-01-01", periods=n, freq="h", tz="UTC")
    c = 100 * np.exp(np.cumsum(rng.normal(0, 0.002, n)))
    o = np.r_[c[0], c[:-1]]
    return pd.DataFrame({"open": o, "high": np.maximum(o, c) * 1.0005,
                         "low": np.minimum(o, c) * 0.9995, "close": c}, index=idx)


class _Sig:
    def __init__(self, time: pd.Timestamp, side: int, stop: float, target: float, ttl: int):
        self.time, self.side, self.stop, self.target, self.ttl_bars = time, side, stop, target, ttl


def _planted(bars: pd.DataFrame, step: int = 25, drift: float = 0.006) -> list[_Sig]:
    """Signals whose next 6 bars drift their way; each with a 0.1% stop (destroys the edge)."""
    sigs = []
    for i in range(50, len(bars) - 30, step):
        side = 1 if (i // step) % 2 else -1
        for k in range(1, 7):
            bars.iloc[i + k, bars.columns.get_loc("close")] *= np.exp(side * drift * k / 6)
        px = bars["close"].iloc[i]
        sigs.append(_Sig(bars.index[i], side, px * (1 - side * 0.001), px * (1 + side * 0.05),
                         6))
    bars["open"] = np.r_[bars["close"].iloc[0], bars["close"].to_numpy()[:-1]]
    bars["high"] = np.maximum(bars["open"], bars["close"]) * 1.0015
    bars["low"] = np.minimum(bars["open"], bars["close"]) * 0.9985
    return sigs


def test_decompose_puts_every_key_in_one_role() -> None:
    p = {"lookback": 20, "stop_atr": 2.0, "rr": 1.5, "ttl_bars": 24, "session_start_hour": 7,
         "adx_min": 20, "entry_z": 1.5}
    d = ch.decompose(p)
    assert d["entry"] == {"lookback": 20, "entry_z": 1.5} and d["stop"] == {"stop_atr": 2.0}
    assert d["exit"] == {"rr": 1.5, "ttl_bars": 24}
    assert d["session"] == {"session_start_hour": 7} and d["regime"] == {"adx_min": 20}
    assert sum(len(v) for v in d.values()) == len(p)


def test_informative_entry_is_harvested_and_bad_exit_named(monkeypatch: pytest.MonkeyPatch,
                                                           tmp_path: Path) -> None:
    bars = _bars()
    sigs = _planted(bars)
    em = ch.entry_markout(bars, sigs, "NOSUCH")
    assert em["harvest"] and em["h_star"] in (3, 6, 12)
    own = ch.own_exit_returns(bars, sigs, "NOSUCH")
    assert own.mean() < em["by_h"][em["h_star"]]["oos_mean"]

    def fam(df: pd.DataFrame, *, lookback: int = 20, stop_atr: float = 2.0, rr: float = 1.5,
            ttl_bars: int = 24) -> list[Any]:
        return sigs
    monkeypatch.setattr("mt5desk.families.get_family_func", lambda name: fam)
    seen: list[dict[str, Any]] = []

    def enqueue(**k: Any) -> tuple[str, bool]:
        seen.append(k)
        return f"c{len(seen)}", True
    rej = [{"id": "cand_1", "family": "planted", "symbol": "NOSUCH", "chart": "H1",
            "search_count": 3,
            "params_json": json.dumps({"lookback": 20, "stop_atr": 0.5, "rr": 1.5,
                                       "ttl_bars": 24})},
           {"id": "cand_0", "family": "planted", "symbol": "NOSUCH", "chart": "H1",
            "origin": "component_harvest", "params_json": "{}"}]
    led = tmp_path / "claim_families.json"
    cut = ch.screen_cut(bars)
    built: list[pd.Timestamp] = []

    def fam_spy(df: pd.DataFrame, *, lookback: int = 20, stop_atr: float = 2.0,
                rr: float = 1.5, ttl_bars: int = 24) -> list[Any]:
        built.append(df.index.max())
        return [s for s in sigs if s.time in df.index]
    monkeypatch.setattr("mt5desk.families.get_family_func", lambda name: fam_spy)
    kw = dict(bars_for=lambda s, c: bars, enqueue=enqueue, out_dir=tmp_path, claim_ledger=led,
              lane_ok=lambda s, f: True)
    doc = ch.harvest_pass(rejected=rej, **kw)
    # the screen never reads the lockbox side of the cut
    assert built and max(built) < cut
    # a harvest child is never re-screened
    assert doc["examined_this_pass"] == 1
    # the bill: every look this pass + the parent's own trials + the re-mates, once per family
    n = len(ch.HORIZONS) + 3 + 2
    fam_charge = json.loads(led.read_text("utf-8"))["families"]["harvest:cand_1"]
    assert fam_charge["selection_trials"] == n == doc["trials_charged"]["selection_trials"]
    assert seen[0]["lineage_json"]["claim_family"] == "harvest:cand_1"
    assert seen[0]["lineage_json"]["claim_selection_trials"] == n
    assert seen[0]["lineage_json"]["parent_ids"] == ["cand_1"]
    assert doc["donated_to_judge"] == 2 and doc["tally"]["EXIT_DESTROYED_EDGE"] == 1
    assert seen[0]["origin"] == "component_harvest" and seen[0]["parent_ids_json"] == ["cand_1"]
    assert seen[0]["params"]["ttl_bars"] == em["h_star"]
    assert seen[0]["params"]["rr"] == ch.NO_TARGET_RR and seen[0]["params"]["lookback"] == 20
    assert seen[1]["params"]["stop_atr"] == ch.WIDE_STOP_ATR
    again = ch.harvest_pass(rejected=rej, **kw)
    assert again["examined_this_pass"] == 0 and len(seen) == 2
    # routing runs before any enqueue
    gated = ch.harvest_pass(rejected=[{**rej[0], "id": "cand_2"}],
                            **{**kw, "lane_ok": lambda s, f: False})
    assert gated["tally"].get("LANE_SET_ASIDE") == 1 and len(seen) == 2
    # state and ledger never sit in data/intelligence
    assert "intelligence" not in str(ch.HARVEST_DIR) and "intelligence" not in str(ch.REPORT_P)


def test_remate_keeps_entry_timing() -> None:
    def fam(df: pd.DataFrame, *, lookback: int = 20, stop_atr: float = 2.0, rr: float = 1.5,
            ttl_bars: int = 24, wait_bars: int = 1, cooldown_bars: int = 0) -> list[Any]:
        return []
    import mt5desk.families as F
    orig = F.get_family_func
    F.get_family_func = lambda name: fam  # type: ignore[assignment]
    try:
        out = ch.remate("x", {"lookback": 9, "stop_atr": 1.0, "rr": 2.0, "ttl_bars": 5,
                              "wait_bars": 3, "cooldown_bars": 7}, 6)
    finally:
        F.get_family_func = orig  # type: ignore[assignment]
    assert all(p["wait_bars"] == 3 and p["cooldown_bars"] == 7 and p["ttl_bars"] == 6
               for p in out)


def test_remate_charge_reaches_the_docket_row() -> None:
    from libs.moat.docket_feed import _row
    from libs.research.trial_ledger import trial_from_record
    lin = json.dumps({"claim_family": "harvest:cand_1", "claim_selection_trials": 7})
    row = _row({"id": "c9", "symbol": "EURUSD", "family": "planted", "params_json": "{}",
                "lineage_json": lin})
    assert row is not None and row["claim_selection_trials"] == 7
    t = trial_from_record(row)
    assert t.lineage == "harvest:cand_1" and t.selection_trials == 7


def test_noise_entry_is_not_harvested() -> None:
    bars = _bars(seed=7)
    rng = np.random.default_rng(3)
    sigs = [_Sig(bars.index[i], int(rng.choice([-1, 1])), 0.0, 1e9, 6)
            for i in range(50, len(bars) - 30, 20)]
    em = ch.entry_markout(bars, sigs, "NOSUCH")
    assert not em["harvest"]


# ------------------------------------------------------------------------------ clocks


def test_both_organs_are_hourly_legs_with_a_layer() -> None:
    src = (_DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert "side_channels/leadership_atlas_miner.py" in src
    assert "side_channels/sources/strategy/component_harvesting.py" in src
    from libs.research.layers import LEG_LAYER
    assert LEG_LAYER.get("leadership_atlas") and LEG_LAYER.get("component_harvest")
