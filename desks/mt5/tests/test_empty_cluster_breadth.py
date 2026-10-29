"""The six empty clusters' families must be buildable by the sealed gauntlet, causal, and minted.

WHAT THIS PINS, on synthetic inputs only (bars, a CBOE index file, a COT contract, the Fed
calendar and a driver's bars, all written to tmp and pointed at by monkeypatch):
  * every family builds from (bars, symbol, params) through the SEALED `build_cell`, with signals;
  * each is registered through the one door, classified into its target cluster, charged to a
    declared census class, H1-pinned, and set aside by the default-parameter sweep;
  * NO LOOKAHEAD: changing the bars AFTER a cutoff changes no signal at or before it, and the
    external inputs are lagged to when they were knowable (VIX next broker day, COT Friday 23:00
    broker, a Fed ET time +7h on the bar clock);
  * the producer charges every measured cell to its trial ledger (which experiment_ledger sums),
    donates only cells over the floor with `alpha_cluster` and the four culture fields, and writes
    one mint-ledger row per cluster;
  * the fence is RED on any cluster with zero cells minted in 24h and on an absent ledger;
  * the leg is wired hourly, in a department and a layer, and the fence is on the battery.
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

from mt5desk import families_cross_sectional as xs  # noqa: E402
from mt5desk import families_empty_clusters as ec  # noqa: E402

CLUSTERS = ("cross_asset_lead_lag", "event_surprise", "execution_entry", "news_reaction",
            "options_implied", "positioning_flow")
DAYS = 1300


def _bars(seed: int, days: int = DAYS, start: str = "2019-01-07") -> pd.DataFrame:
    """Weekday H1 bars, broker-stamped under a UTC label, with spread and tick volume."""
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(start, periods=days, tz="UTC")
    idx = pd.DatetimeIndex([d + pd.Timedelta(hours=h) for d in dates for h in range(24)])
    r = rng.standard_t(3, len(idx)) * 0.0015
    close = 1.2 * np.exp(np.cumsum(r))
    open_ = np.r_[close[0], close[:-1]]
    wig = np.abs(rng.normal(0, 0.0008, len(idx)))
    return pd.DataFrame({"open": open_, "high": np.maximum(open_, close) * (1 + wig),
                         "low": np.minimum(open_, close) * (1 - wig), "close": close,
                         "tick_volume": rng.integers(50, 500, len(idx)),
                         "spread": rng.integers(5, 40, len(idx))}, index=idx)


def _write_index(path: Path, seed: int, days: int = 2000) -> None:
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2018-06-01", periods=days)
    v = 18 * np.exp(np.cumsum(rng.normal(0, 0.06, days)) * 0.3)
    path.write_text(json.dumps({"series": [{"date": d.strftime("%m/%d/%Y"), "close": f"{x:.2f}"}
                                           for d, x in zip(dates, v, strict=True)]}), "utf-8")


def _write_cot(path: Path, seed: int) -> None:
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2012-01-03", "2024-12-31", freq="W-TUE", tz="UTC")
    n = len(dates)
    spec = np.cumsum(rng.normal(0, 4000, n))
    comm = -spec + rng.normal(0, 3000, n)
    pd.DataFrame({"report_date": dates, "open_interest_all": 200_000.0,
                  "noncomm_positions_long_all": 80_000 + np.maximum(spec, 0),
                  "noncomm_positions_short_all": 80_000 + np.maximum(-spec, 0),
                  "comm_positions_long_all": 90_000 + np.maximum(comm, 0),
                  "comm_positions_short_all": 90_000 + np.maximum(-comm, 0)}).to_parquet(path)


def _write_calendar(path: Path) -> None:
    rows = []
    for d in pd.bdate_range("2019-02-01", "2023-12-01", freq="9B"):
        rows.append({"month": d.strftime("%Y-%m"), "days": str(d.day), "time": "10:00 a.m.",
                     "type": "Speeches", "title": "Speech - Governor Somebody"})
    for d in pd.bdate_range("2019-02-01", "2023-12-01", freq="30B"):
        rows.append({"month": d.strftime("%Y-%m"), "days": str(d.day), "time": "2:00 p.m.",
                     "type": "FOMC", "title": "FOMC Meeting"})
    path.write_text(json.dumps({"raw": rows}), "utf-8")


@pytest.fixture()
def world(tmp_path, monkeypatch):
    """Bars for a target and a driver, one implied index, one COT contract and a calendar."""
    uni = tmp_path / "universe"
    obs = tmp_path / "observables"
    cot = tmp_path / "cot"
    for d in (uni, obs, cot):
        d.mkdir()
    frames = {"AUDJPY": _bars(1), "USDJPY": _bars(2), "EURUSD": _bars(3)}
    for s, f in frames.items():
        f.to_parquet(uni / f"{s}_H1.parquet")
    _write_index(obs / "cboe_vix_history.json", 7)
    _write_cot(cot / "jpy.parquet", 9)
    _write_cot(cot / "aud.parquet", 11)
    _write_calendar(obs / "fomc_calendar.json")
    monkeypatch.setattr(xs, "UNIVERSE_DIR", uni)
    xs._SERIES_CACHE.clear()
    monkeypatch.setattr(ec, "OBSERVABLES", obs)
    monkeypatch.setattr(ec, "FED_CALENDAR", obs / "fomc_calendar.json")
    monkeypatch.setattr(ec, "COT_DIR", cot)
    monkeypatch.setattr(ec, "CONSENSUS_STORE", tmp_path / "consensus_actuals.jsonl")
    return {"frames": frames, "uni": uni, "obs": obs, "cot": cot, "tmp": tmp_path}


def _params(fam: str, sym: str) -> dict:
    p = {"symbol": sym, **{k: v[0] for k, v in ec.PARAM_GRID[fam].items()}}
    if fam.startswith("entry_alpha"):
        p.update({"base_family": "asia_momentum", "base_params": {}})
    if fam == "entry_alpha_open_offset":
        p["base_family"] = "jump"      # asia_momentum's open offset is #254's (OWNED_ELSEWHERE)
    if fam in ("cross_asset_lead_lag", "lead_lag_session_handoff"):
        p["cond_symbol"] = "USDJPY"
    if fam == "entry_alpha_spread_gate":
        p["spread_q"] = 0.3
    if fam == "implied_vol_shock_fade":
        p["z_thr"] = 1.5
    return p


#: Families with a synthetic input in `world`. The consensus family needs a consensus store and
#: is pinned to REFUSE without it below.
#: `entry_alpha_limit_pullback` waits on the declared limit order type (PR #222) and is pinned
#: to REFUSE until the engine has one (`test_limit_pullback_waits_for_the_limit_engine`).
WAITING = set() if ec.limit_engine_ready() else {"entry_alpha_limit_pullback"}
FIRING = sorted(set(ec.EMPTY_CLUSTER_FAMILIES) - {"event_surprise_consensus"} - WAITING)
ENTRY_ALPHA = sorted(f for f in ec.EMPTY_CLUSTER_FAMILIES if f.startswith("entry_alpha"))


@pytest.mark.parametrize("family", FIRING)
def test_family_fires_from_symbol_alone(world, family):
    fn = ec.EMPTY_CLUSTER_FAMILIES[family]
    sigs = fn(world["frames"]["AUDJPY"], **_params(family, "AUDJPY"))
    assert sigs, f"{family} produced no signal on synthetic inputs"
    assert all(s.side in (1, -1) for s in sigs)


@pytest.mark.parametrize("family", sorted(ec.EMPTY_CLUSTER_FAMILIES))
def test_symbol_is_required_so_a_bare_cell_fails_loudly(family):
    import inspect
    sig = inspect.signature(ec.EMPTY_CLUSTER_FAMILIES[family])
    assert sig.parameters["symbol"].default is inspect.Parameter.empty


def test_refuses_without_its_input(world):
    d = world["frames"]["AUDJPY"]
    assert ec.family_event_surprise_consensus(d, symbol="AUDJPY") == []      # no store
    assert ec.family_implied_vol_risk_premium(d, symbol="NOPE12") == []       # no mapping
    assert ec.family_positioning_flow_momentum(d, symbol="EURGBP") == []      # no eur/gbp file
    assert ec.family_cross_asset_lead_lag(d, symbol="AUDJPY", cond_symbol="AUDJPY") == []
    assert ec.family_entry_alpha_limit_pullback(d, symbol="AUDJPY",
                                                base_family="lead_lag") == []  # not a base


@pytest.mark.parametrize("family", FIRING)
def test_no_lookahead_in_the_bars(world, family):
    """Signals at or before a cutoff are identical when every bar AFTER it is replaced."""
    d = world["frames"]["AUDJPY"]
    cut = d.index[len(d) * 2 // 3]
    dirty = d.copy()
    later = dirty.index > cut
    dirty.loc[later, ["open", "high", "low", "close"]] *= 1.3
    dirty.loc[later, "spread"] = 99
    fn = ec.EMPTY_CLUSTER_FAMILIES[family]
    p = _params(family, "AUDJPY")

    def key(sigs):
        return sorted((pd.Timestamp(s.time).value, s.side, round(s.stop, 8), round(s.target, 8),
                       None if s.trigger is None else round(s.trigger, 8))
                      for s in sigs if pd.Timestamp(s.time) <= cut)
    assert key(fn(d, **p)) == key(fn(dirty, **p)), f"{family} reads bars after its decision"


def test_driver_lookahead_is_impossible(world, tmp_path):
    """Truncating the DRIVER's file at T changes no lead-lag signal at or before T."""
    d = world["frames"]["AUDJPY"]
    cut = d.index[len(d) // 2]
    full = ec.family_cross_asset_lead_lag(d, **_params("cross_asset_lead_lag", "AUDJPY"))
    drv = world["frames"]["USDJPY"]
    drv[drv.index <= cut].to_parquet(world["uni"] / "USDJPY_H1.parquet")
    xs._SERIES_CACHE.clear()
    short = ec.family_cross_asset_lead_lag(d, **_params("cross_asset_lead_lag", "AUDJPY"))
    a = [(s.time, s.side) for s in full if s.time <= cut]
    b = [(s.time, s.side) for s in short if s.time <= cut]
    assert a == b


def test_implied_close_is_usable_only_from_the_next_broker_day(world):
    t, v = ec.implied_series("vix")
    first = pd.Timestamp(int(t[0]), tz="UTC")
    assert (first.hour, first.minute) == (0, 0)
    doc = json.loads((world["obs"] / "cboe_vix_history.json").read_text())
    d0 = datetime.strptime(doc["series"][0]["date"], "%m/%d/%Y")
    assert first.tz_localize(None).to_pydatetime() == d0 + timedelta(days=1)


def test_cot_is_usable_only_from_its_true_release_on_the_bar_clock(world):
    """M2 (HOLD 2026-10-07): each report is usable from PR #238's real CFTC release, put on the
    bar clock -- Friday 23:00 broker in a normal week, later in a holiday week or a lapse, never
    earlier than the nominal floor, and strictly increasing in report order."""
    from mt5desk import cot_frames as cf
    frame, orient = ec.cot_frame("USDJPY")
    assert orient == -1                                    # long yen futures = short USDJPY
    raw = pd.read_parquet(world["cot"] / "jpy.parquet")
    rd = pd.to_datetime(raw["report_date"], utc=True)
    assert frame.index.is_monotonic_increasing and frame.index.is_unique
    assert len(frame) == len(rd)                           # lapse reports are labelled, not lost
    floor = rd.dt.normalize() + ec.COT_RELEASE_LAG
    assert (frame.index >= pd.DatetimeIndex(floor)).all()
    normal = [i for i, r in enumerate(rd) if not cf.release_date(cf._week_friday(r))[1]
              and cf.release_date(cf._week_friday(r))[0] == cf._week_friday(r).date()]
    late = sorted(set(range(len(rd))) - set(normal))
    assert normal and late
    assert {(frame.index[i].dayofweek, frame.index[i].hour) for i in normal} == {(4, 23)}
    assert all(frame.index[i] > floor.iloc[i] for i in late)
    # Thanksgiving week 2019: as of Tue Nov 26, released Mon Dec 2 15:30 ET = 22:30 broker
    i = int(np.flatnonzero(rd == pd.Timestamp("2019-11-26", tz="UTC"))[0])
    assert frame.index[i] == pd.Timestamp("2019-12-02 23:00", tz="UTC")
    # the 2018-19 lapse: as of Tue Jan 8 2019 is no longer DROPPED, it is usable after its
    # CFTC catch-up release, weeks after the nominal Friday
    i = int(np.flatnonzero(rd == pd.Timestamp("2019-01-08", tz="UTC"))[0])
    assert frame.index[i] - floor.iloc[i] > pd.Timedelta(days=14)
    # the 2025 lapse (outside this fixture's span, checked on the label function directly)
    lab = ec.cot_usable_from(pd.Series(pd.to_datetime(["2025-09-30", "2025-10-07"], utc=True)))
    assert lab[0] >= pd.Timestamp("2025-11-19", tz="UTC") and lab[1] > lab[0]
    assert ec.cot_contract("AUDJPY") == ("aud", 1) and ec.cot_contract("XAUUSD") == ("gold", 1)


def test_fed_et_time_lands_on_the_bar_clock_plus_seven_hours(world):
    cal = ec.fed_calendar()
    speech = next(t for t, k, _ in cal if k == "speeches")
    ts = pd.Timestamp(speech, tz="UTC")
    assert (ts.hour, ts.minute) == (17, 0)                 # 10:00 a.m. ET -> 17:00 broker
    assert ec.utc_to_bar_ns(pd.Timestamp("2024-07-01 14:00", tz="UTC")) == \
        pd.Timestamp("2024-07-01 17:00", tz="UTC").value   # EDT: UTC-4 -> ET 10:00 -> +7


def test_registered_classified_charged_and_pinned():
    from libs.research.alpha_clusters import classify_family
    from libs.research.mechanism_census import CONSTRUCTION_CLASS
    from mt5desk import families_orthogonal as fo

    from research import orthogonal_sweep as osw
    for fam, cluster in ec.TARGETS.items():
        assert fam in fo.ORTHOGONAL_FAMILIES and fo.ORTHOGONAL_FAMILIES[fam] is \
            ec.EMPTY_CLUSTER_FAMILIES[fam]
        assert classify_family(fam) == cluster
        assert fam in CONSTRUCTION_CLASS, f"{fam} is charged to no declared census class"
        if fam in ec.ALL_CHART_FAMILIES:
            assert fam not in fo.FAMILY_TIMEFRAMES, f"{fam} decides by timestamp: every chart"
        else:
            assert fo.FAMILY_TIMEFRAMES[fam][0] == ("H1",)
        assert fo.FAMILY_INPUTS[fam] == ec.INPUTS[fam]
        assert fam in osw.NOT_SOURCED_HERE
    assert set(ec.TARGETS.values()) == set(CLUSTERS)
    for fam in ("cot_net_fade", "cot_change_fade", "cot_change_momentum", "cot_comm_follow"):
        assert classify_family(fam) == "positioning_flow"
    assert classify_family("execution_state") == "execution_entry"


def _resample(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    return df.resample(rule, label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last",
         "tick_volume": "sum", "spread": "mean"}).dropna()


@pytest.mark.parametrize("family", ["implied_vol_risk_premium", "positioning_flow_momentum",
                                    "event_surprise_consensus"])
def test_an_all_chart_family_takes_the_same_decisions_on_every_chart(world, family):
    """The families left unpinned decide by TIMESTAMP: the same days fire on H1, H4 and D1, and
    the hold spans the same market time (days x bars_per_day, or a rescaled wall-clock span)."""
    from mt5desk import families_orthogonal as fo
    if family == "event_surprise_consensus":
        rows = [{"currency": "JPY", "z": 2.0 if i % 2 else -2.0,
                 "release_utc": str(pd.Timestamp("2019-03-01 23:50") + pd.Timedelta(days=17 * i))}
                for i in range(60)]
        ec.CONSENSUS_STORE.write_text("\n".join(json.dumps(r) for r in rows), "utf-8")
    h1 = world["frames"]["AUDJPY"]
    base = _params(family, "AUDJPY")
    days, spans = {}, {}
    for tf, rule in (("H1", None), ("H4", "4h"), ("D1", "1D")):
        frame = h1 if rule is None else _resample(h1, rule)
        kw = {**base, **fo.timeframe_overrides(family, tf)} if tf != "H1" else base
        if family == "event_surprise_consensus" and tf != "H1":
            kw["hold_bars"] = fo.timeframe_overrides(family, tf)["hold_bars"]
        sigs = ec.EMPTY_CLUSTER_FAMILIES[family](frame, **kw)
        assert sigs, f"{family} fires nothing on {tf}"
        days[tf] = len({s.time.normalize() for s in sigs})
        spans[tf] = sigs[0].ttl_bars * {"H1": 1, "H4": 4, "D1": 24}[tf]
    assert min(days.values()) >= 0.8 * max(days.values()), days
    if family != "event_surprise_consensus":
        assert len(set(spans.values())) == 1, spans


def test_gauntlet_buildability_reads_them_as_buildable():
    from research.gauntlet_buildability import BUILDABLE, cell_verdict, family_verdict
    for fam in ec.EMPTY_CLUSTER_FAMILIES:
        assert family_verdict(fam)[0] == BUILDABLE, family_verdict(fam)
        assert cell_verdict(fam, {})[0] != BUILDABLE          # `symbol` is required
    assert cell_verdict("implied_vol_risk_premium", {"symbol": "US500"})[0] == BUILDABLE


def test_sealed_gauntlet_builds_every_firing_family(world, monkeypatch):
    """The judge's own door, imported as the sweep imports it, with no sealed edit."""
    sys.path.insert(0, str(_DESK / "scripts"))
    import external_gauntlet as eg
    from research.family_policy import family_banned
    monkeypatch.setattr(eg, "_bars_for", lambda sym, tf="H1": world["frames"].get(sym))
    for fam in FIRING:
        assert not family_banned(fam)
        cell = eg.build_cell("AUDJPY", fam, _params(fam, "AUDJPY"), {})
        assert cell is not None, f"{fam}: {eg.LAST_BUILD_FAILURE}"
        assert cell["sigs"], f"{fam} rebuilt by the gauntlet with no signals"


# ------------------------------------------------------------------------------ the producer ---
@pytest.fixture()
def producer(world, tmp_path, monkeypatch):
    from research import empty_cluster_breadth as ecb
    from research import proposer_common as pc
    for name, fn in (("STATE", "state.json"), ("MINT_LEDGER", "mint.jsonl"),
                     ("TRIALS", "trials.jsonl"), ("OUT", "ECB.json"),
                     ("FORCER", "absent_forcer.json"), ("VERDICTS", "absent.jsonl")):
        monkeypatch.setattr(ecb, name, tmp_path / fn)
    monkeypatch.setattr(ecb, "UNIVERSE_DIR", world["uni"])
    monkeypatch.setattr(ecb, "SEED_FLOOR", 5)
    monkeypatch.setattr(ecb, "_lane_ok", lambda s, f: True)
    donated: list[list[dict]] = []

    def fake_donate(source, rows, tests_run):
        donated.append(rows)
        return tmp_path / "discoveries.json"
    monkeypatch.setattr(pc, "donate", fake_donate)
    monkeypatch.setattr(pc, "donation_counts", lambda: {"donated": len(donated[-1])})
    return ecb, donated


def test_producer_charges_every_measured_cell_and_donates_with_cluster_and_culture(producer):
    ecb, donated = producer
    doc = ecb.run(budget_s=600, fetch=False)
    s = doc["seeding"]
    assert s["trials_charged_this_pass"] == sum(
        c.get("measured_this_pass", 0) for c in s["by_cluster"].values()) > 0
    rows = [json.loads(x) for x in ecb.TRIALS.read_text().splitlines()]
    assert all(r["cells"] and r["family"] in ec.TARGETS for r in rows)
    assert donated, "nothing donated on synthetic inputs"
    from libs.research import cell_culture as CC
    for r in donated[0]:
        assert r["alpha_cluster"] == ec.TARGETS[r["family"]]
        assert r["params"]["symbol"] == r["symbol"]
        assert not CC.validate(r), CC.validate(r)
    minted = {c for c in (r["alpha_cluster"] for r in donated[0])}
    assert {"options_implied", "positioning_flow", "news_reaction", "event_surprise",
            "cross_asset_lead_lag", "execution_entry"} <= minted
    led = [json.loads(x) for x in ecb.MINT_LEDGER.read_text().splitlines()]
    assert {r["cluster"] for r in led} == set(CLUSTERS)
    assert doc["fence"]["verdict"] == "GREEN"
    # a second pass the same day re-measures nothing, re-charges nothing, re-donates nothing
    doc2 = ecb.run(budget_s=600, fetch=False)
    assert doc2["seeding"]["trials_charged_this_pass"] == 0
    assert len(donated) == 1


def test_producer_names_the_missing_input_instead_of_reading_zero(producer):
    ecb, _donated = producer
    doc = ecb.run(budget_s=600, dry_run=True, fetch=False)
    miss = doc["seeding"]["by_cluster"]
    assert any("consensus_actuals" in m for m in miss["event_surprise"]["missing_inputs"])
    assert any("cboe_gvz_history" in m for m in miss["options_implied"]["missing_inputs"])
    assert not ecb.TRIALS.exists()                        # a dry run charges nothing
    assert doc["verdicts"]["status"] == "UNMEASURED"


def test_experiment_ledger_sums_the_trial_ledger(tmp_path, monkeypatch):
    from libs.research import experiment_ledger as el
    p = tmp_path / "t.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in (
        {"family": "cb_tone_speech_reaction", "cells": ["a", "b"]},
        {"family": "cb_tone_speech_reaction", "cells": ["b", "c"]},
        {"family": "x", "cells": ["d"], "dry_run": True})), "utf-8")
    total, fam, skipped = el._swarm_counts({"c"}, p)
    assert (total, fam, skipped) == (2, {"cb_tone_speech_reaction": 2}, 1)
    assert el.EMPTY_CLUSTER_TRIALS.name == "EMPTY_CLUSTER_TRIALS.jsonl"


# --------------------------------------------------------------------------------- the fence ---
def _ledger(path: Path, minted: dict[str, int], hours_ago: float = 1.0) -> None:
    ts = (datetime.now(tz=UTC) - timedelta(hours=hours_ago)).isoformat(timespec="seconds")
    path.write_text("\n".join(json.dumps({"ts": ts, "cluster": c, "minted": minted.get(c, 0),
                                          "missing_inputs": ["x"] if not minted.get(c) else []})
                              for c in CLUSTERS), "utf-8")


def test_fence_red_on_any_cluster_with_zero_minted(tmp_path):
    sys.path.insert(0, str(_ROOT / "scripts"))
    import check_empty_cluster_minting as fence
    p = tmp_path / "mint.jsonl"
    _ledger(p, {c: 3 for c in CLUSTERS})
    assert fence.check(24, p)["verdict"] == "GREEN"
    _ledger(p, {c: 3 for c in CLUSTERS if c != "news_reaction"})
    doc = fence.check(24, p)
    assert doc["verdict"] == "RED" and doc["red_clusters"] == ["news_reaction"]
    _ledger(p, {c: 3 for c in CLUSTERS}, hours_ago=30)
    assert fence.check(24, p)["red_clusters"] == list(CLUSTERS)       # outside the window
    assert fence.check(24, tmp_path / "absent.jsonl")["verdict"] == "RED"


def test_leg_and_fence_are_wired():
    text = (_DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert '_costed("empty_cluster_breadth"' in text
    assert '"research/empty_cluster_breadth.py"' in text
    from libs.research.layers import LEG_LAYER
    assert LEG_LAYER["empty_cluster_breadth"] == "prediction"
    import importlib
    hc = importlib.import_module("research.hourly_cycle")
    assert hc.department_of("empty_cluster_breadth") == "discovery"
    assert hc.LEG_BUDGET_SEC["empty_cluster_breadth"] >= 900 + 300
    from research.batteries import FENCES
    assert any(e.path == "scripts/check_empty_cluster_minting.py" for e in FENCES)


def test_forcer_names_this_organ_and_donates_through_the_door(tmp_path, monkeypatch):
    from research import empty_cluster_forcer as f
    from research import proposer_common as pc
    for c in CLUSTERS:
        assert "empty_cluster_breadth" in f.CLUSTER_PROPOSER[c]
    got: list = []
    monkeypatch.setattr(pc, "donate", lambda s, rows, n: got.append((s, rows)) or tmp_path / "x")
    monkeypatch.setattr(pc, "donation_counts", lambda: {"donated": len(got[-1][1])})
    path, _counts = f.donate([{"family": "dow_effect", "symbols": ["EURUSD"],
                               "alpha_cluster": "fixing_roll_calendar", "text": "t",
                               "title": "t"}])
    assert path is not None and got[0][0] == f.SEAT_SOURCE
    row = got[0][1][0]
    assert row["symbol"] == "EURUSD" and row["alpha_cluster"] == "fixing_roll_calendar"
    assert "source_culture" in row


# ------------------------------------------------- execution_entry operators: causality (#163)
def _entry_key(sigs, upto=None):
    return sorted((pd.Timestamp(s.time).value, s.side, round(s.stop, 8), round(s.target, 8),
                   None if s.trigger is None else round(s.trigger, 8))
                  for s in sigs if upto is None or pd.Timestamp(s.time) <= upto)


@pytest.mark.parametrize("family", ENTRY_ALPHA)
def test_entry_alpha_future_bar_perturbation_leaves_every_earlier_signal(world, family):
    """Corrupt prices AND spreads of every bar after a cutoff: signals at or before it must be
    byte-identical. A waiting family must refuse identically on both."""
    d = world["frames"]["AUDJPY"]
    p = _params(family, "AUDJPY")
    fn = ec.EMPTY_CLUSTER_FAMILIES[family]
    rng = np.random.default_rng(5)
    for frac in (0.4, 0.7):
        cut = d.index[int(len(d) * frac)]
        dirty = d.copy()
        later = dirty.index > cut
        n = int(later.sum())
        dirty.loc[later, ["open", "high", "low", "close"]] *= rng.uniform(0.7, 1.3, (n, 1))
        dirty.loc[later, "high"] = dirty.loc[later, ["open", "high", "close"]].max(axis=1)
        dirty.loc[later, "low"] = dirty.loc[later, ["open", "low", "close"]].min(axis=1)
        dirty.loc[later, "spread"] = rng.integers(1, 200, n)
        a = _entry_key(fn(d, **p), cut)
        assert a or family in WAITING, f"{family} emitted nothing before {cut}: vacuous"
        assert a == _entry_key(fn(dirty, **p), cut), f"{family} reads bars after {cut}"


@pytest.mark.parametrize("family", ENTRY_ALPHA)
def test_entry_alpha_fill_bar_spread_probe(world, family):
    """The defect fixed 2026-10-06: `entry_alpha_spread_gate` admitted an entry on the spread of
    the bar it FILLS in, which has not closed when the order is sent. For a sample of emitted
    signals, widen ONLY the fill bar's spread: that signal and every one before it must stand."""
    d = world["frames"]["AUDJPY"]
    p = _params(family, "AUDJPY")
    fn = ec.EMPTY_CLUSTER_FAMILIES[family]
    sigs = fn(d, **p)
    if family in WAITING:
        assert sigs == []
        return
    assert len(sigs) >= 10, f"{family}: too few signals for the probe"
    col = d.columns.get_loc("spread")
    for s in sigs[:: max(1, len(sigs) // 12)]:
        j = d.index.get_loc(pd.Timestamp(s.time))
        if j + 1 >= len(d):
            continue
        for wide in (1, 10_000):
            poked = d.copy()
            poked.iloc[j + 1, col] = wide
            assert _entry_key(sigs, s.time) == _entry_key(fn(poked, **p), s.time), (
                f"{family}: the fill bar's spread after {s.time} moved a decision")


def test_spread_gate_admits_only_on_a_closed_normal_bar_after_a_wide_decision(world):
    """Every emitted spread-gate signal sits on a bar whose OWN spread is at or under its
    trailing quantile, and the base decision it delays was on a bar that was not."""
    d = world["frames"]["AUDJPY"]
    p = _params("entry_alpha_spread_gate", "AUDJPY")
    sigs = ec.family_entry_alpha_spread_gate(d, **p)
    assert sigs
    sp = d["spread"].astype(float)
    thr = sp.rolling(240, min_periods=120).quantile(float(p["spread_q"])).shift(1)
    for s in sigs:
        t = pd.Timestamp(s.time)
        assert sp[t] <= thr[t], f"{t}: admitted on a bar whose own spread was wide"
        assert s.trigger is None and s.tag.startswith("entry_alpha_spread_gate<")


def test_limit_pullback_waits_for_the_limit_engine(world, producer):
    """Until the engine declares `Signal.order_type == "limit"` (PR #222) the limit operator
    refuses, and the producer names the wait as execution_entry's missing artifact instead of
    charging cells that cannot fire."""
    if ec.limit_engine_ready():
        pytest.skip("the limit engine is present: the family is armed and covered by FIRING")
    d = world["frames"]["AUDJPY"]
    p = _params("entry_alpha_limit_pullback", "AUDJPY")
    assert ec.family_entry_alpha_limit_pullback(d, **p) == []
    ecb, _donated = producer
    cells, missing = ecb.plan()
    assert not any(f == "entry_alpha_limit_pullback" for _s, f, _p in cells)
    assert ec.LIMIT_ENGINE_WAIT in missing["execution_entry"]


# ------------------------------------------------------------ HOLD fixes (2026-10-07) on #163 ---
@pytest.mark.parametrize("side", [1, -1])
def test_a_crossed_exit_is_dropped_never_mirrored(side):
    """`_rebased` used abs(): a base whose target or stop the reference close had already passed
    was re-stamped with that exit on the OTHER side of the entry. It must return None."""
    from mt5desk.engine import Signal
    t = pd.Timestamp("2024-01-02 09:00", tz="UTC")
    ref = 1.1000

    def sig(stop_off, tgt_off):
        return Signal(time=t, side=side, stop=ref - side * stop_off,
                      target=ref + side * tgt_off, ttl_bars=5, tag="b")
    ok = ec._rebased(sig(0.002, 0.004), t, ref, trigger=None, wait=1, tag="x")
    assert ok is not None
    assert side * (ref - ok.stop) == pytest.approx(0.002)
    assert side * (ok.target - ref) == pytest.approx(0.004)
    assert ec._rebased(sig(0.002, -0.001), t, ref, trigger=None, wait=1, tag="x") is None
    assert ec._rebased(sig(-0.001, 0.004), t, ref, trigger=None, wait=1, tag="x") is None
    assert ec._rebased(sig(0.002, 0.0), t, ref, trigger=None, wait=1, tag="x") is None


@pytest.mark.parametrize("family", ["entry_alpha_spread_gate", "entry_alpha_open_offset"])
def test_every_delayed_entry_keeps_its_exits_on_the_right_side(world, family):
    d = world["frames"]["AUDJPY"]
    sigs = ec.EMPTY_CLUSTER_FAMILIES[family](d, **_params(family, "AUDJPY"))
    assert sigs
    close = d["close"]
    for s in sigs:
        c = float(close[pd.Timestamp(s.time)])
        assert s.side * (c - s.stop) > 0 and s.side * (s.target - c) > 0, s


def test_operator_pairs_owned_by_254_are_not_minted(world, producer):
    """Coordinator ruling: #254 owns the execution-entry operator pairs, so the spread gate over
    overnight_gap_decay and the open offset over asia_momentum are neither built nor planned."""
    d = world["frames"]["AUDJPY"]
    assert ec.family_entry_alpha_spread_gate(d, symbol="AUDJPY",
                                             base_family="overnight_gap_decay") == []
    assert ec.family_entry_alpha_open_offset(d, symbol="AUDJPY", base_family="asia_momentum") == []
    ecb, _donated = producer
    cells, _missing = ecb.plan()
    pairs = {(f, p.get("base_family")) for _s, f, p in cells}
    for fam, bases in ec.OWNED_ELSEWHERE.items():
        assert not any((fam, b) in pairs for b in bases)
    assert ("entry_alpha_spread_gate", "asia_momentum") in pairs     # the rest still mint


def test_a_stale_spread_neither_delays_nor_admits(world):
    """A missing spread carries forward at most SPREAD_STALE_MAX_BARS bars; past that the bar's
    spread is unknown. Blanking a long run of spreads must remove every signal inside it."""
    d = world["frames"]["AUDJPY"].copy()
    p = _params("entry_alpha_spread_gate", "AUDJPY")
    lo, hi = len(d) // 2, len(d) // 2 + 400
    d["spread"] = d["spread"].astype(float)
    d.iloc[lo:hi, d.columns.get_loc("spread")] = np.nan
    sigs = ec.family_entry_alpha_spread_gate(d, **p)
    blind_from = d.index[lo + ec.SPREAD_STALE_MAX_BARS]
    blind_to = d.index[hi - 1]
    assert sigs
    assert not [s for s in sigs if blind_from <= pd.Timestamp(s.time) <= blind_to]


def test_spread_gate_over_opening_range_is_pinned_to_m1_h1(world):
    """The spread gate runs on every chart, but its base's pin binds it: opening_range is M1-H1
    in FAMILY_TIMEFRAMES, so the wrapped cell refuses on H4 and D1 and fires on H1."""
    from mt5desk import families_orthogonal as fo
    assert fo.FAMILY_TIMEFRAMES["opening_range"][0] == ("M1", "M5", "M15", "M30", "H1")
    h1 = world["frames"]["AUDJPY"]
    p = {**_params("entry_alpha_spread_gate", "AUDJPY"), "base_family": "opening_range"}
    assert ec.base_chart_ok(h1, "opening_range")
    assert ec.family_entry_alpha_spread_gate(h1, **p)
    for rule in ("4h", "1D"):
        frame = _resample(h1, rule)
        assert not ec.base_chart_ok(frame, "opening_range")
        assert ec.family_entry_alpha_spread_gate(frame, **p) == []
    assert ec.base_chart_ok(_resample(h1, "4h"), "asia_momentum")     # an unpinned base


def test_event_surprise_consensus_future_perturbation_leaves_every_earlier_signal(world):
    """Corrupt every bar AND every release after a cutoff (new z, flipped signs, extra rows):
    signals at or before the cutoff must be identical."""
    d = world["frames"]["AUDJPY"]
    rng = np.random.default_rng(17)
    t0 = pd.Timestamp("2019-02-01 12:30", tz="UTC")
    rows = [{"currency": c, "z": float(rng.normal(0, 2)),
             "release_utc": str(t0 + pd.Timedelta(hours=int(h)))}
            for c, h in zip(rng.choice(["JPY", "AUD", "USD"], 400),
                            np.cumsum(rng.integers(30, 150, 400)), strict=True)]
    p = {"symbol": "AUDJPY", "side_on_up": 1, "z_min": 1.0}

    def run(frame, rs):
        ec.CONSENSUS_STORE.write_text("\n".join(json.dumps(r) for r in rs), "utf-8")
        ec._consensus_cached.cache_clear()
        return ec.family_event_surprise_consensus(frame, **p)
    for frac in (0.4, 0.7):
        cut = d.index[int(len(d) * frac)]
        clean = _entry_key(run(d, rows), cut)
        assert clean, f"no consensus signal before {cut}: vacuous"
        dirty = d.copy()
        later = dirty.index > cut
        dirty.loc[later, ["open", "high", "low", "close"]] *= rng.uniform(0.7, 1.3,
                                                                         (int(later.sum()), 1))
        dirty.loc[later, "high"] = dirty.loc[later, ["open", "high", "close"]].max(axis=1)
        dirty.loc[later, "low"] = dirty.loc[later, ["open", "low", "close"]].min(axis=1)
        future = [dict(r, z=-3.0 * float(r["z"]) + 1.0)
                  if pd.Timestamp(r["release_utc"]) > cut else r
                  for r in rows]
        future += [{"currency": "JPY", "z": 5.0,
                    "release_utc": str(cut + pd.Timedelta(hours=k))}
                   for k in (2, 5, 30)]
        assert clean == _entry_key(run(dirty, future), cut), f"reads the future after {cut}"

