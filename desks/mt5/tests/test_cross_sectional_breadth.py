"""The cross-sectional class books must be buildable by the sealed gauntlet, causal, and seeded.

WHAT THIS PINS, on synthetic bars only:
  * every family builds from (bars, symbol, params) alone -- no `peers` argument, which is the
    exact defect that left `family_cross_sectional` unjudgeable (the gauntlet never supplies it);
  * NO LOOKAHEAD: truncating the OWN bars and every PEER file at T changes no signal before T;
  * a planted relative winner is ranked long by momentum and short by reversal;
  * peer classes come from the registry by asset class, never a symbol list, with the two
    double-count constructions (metal in a second currency, the dollar basket) left out;
  * the seeder donates only cells whose lower-bound trade days clear SEED_FLOOR, never re-donates,
    and reports certificates as UNMEASURED (never 0) before any verdict exists.
"""
from __future__ import annotations

import json
import sys
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
from mt5desk.engine import Signal  # noqa: E402

MEMBERS = ["AAABBB", "CCCDDD", "EEEFFF", "GGGHHH", "IIIJJJ", "KKKLLL", "MMMNNN", "OOOPPP"]
DAYS = 520


def _bars(seed: int, drift: float = 0.0, days: int = DAYS) -> pd.DataFrame:
    """Weekday H1 bars (24 a day) as a random walk with a daily drift."""
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2020-01-06", periods=days, tz="UTC")
    idx = pd.DatetimeIndex([d + pd.Timedelta(hours=h) for d in dates for h in range(24)])
    r = rng.normal(drift / 24.0, 0.002, len(idx))
    close = 100.0 * np.exp(np.cumsum(r))
    open_ = np.r_[close[0], close[:-1]]
    hi = np.maximum(open_, close) * 1.0005
    lo = np.minimum(open_, close) * 0.9995
    return pd.DataFrame({"open": open_, "high": hi, "low": lo, "close": close,
                         "tick_volume": 100}, index=idx)


@pytest.fixture()
def universe(tmp_path, monkeypatch):
    """Eight synthetic class members on disk; AAABBB is a planted relative winner."""
    frames = {}
    for i, sym in enumerate(MEMBERS):
        drift = 0.004 if sym == "AAABBB" else 0.0
        frames[sym] = _bars(i + 1, drift)
        frames[sym].to_parquet(tmp_path / f"{sym}_H1.parquet")
    monkeypatch.setattr(xs, "UNIVERSE_DIR", tmp_path)
    monkeypatch.setattr(xs, "class_of", lambda s: "fx_cross" if s in MEMBERS else None)
    monkeypatch.setattr(xs, "class_symbols", lambda k: list(MEMBERS) if k == "fx_cross" else [])
    xs._SERIES_CACHE.clear()
    yield frames
    xs._SERIES_CACHE.clear()


def _key(sigs: list[Signal]) -> list[tuple]:
    return [(pd.Timestamp(s.time).value, s.side, round(s.stop, 8), round(s.target, 8), s.tag)
            for s in sigs]


@pytest.mark.parametrize("family", sorted(xs.CROSS_SECTIONAL_FAMILIES))
def test_family_builds_from_symbol_alone(universe, family):
    fn = xs.CROSS_SECTIONAL_FAMILIES[family]
    df = universe["CCCDDD"]
    params = dict(zip(sorted(xs.PARAM_GRID[family]),
                      [xs.PARAM_GRID[family][k][0] for k in sorted(xs.PARAM_GRID[family])],
                      strict=True))
    sigs = fn(df, symbol="CCCDDD", **params)
    assert sigs, f"{family} produced no signal on eight synthetic members"
    idx = set(df.index)
    for s in sigs:
        assert s.time in idx and s.side in (1, -1) and s.trigger is None and s.wait_bars == 1
        assert (s.stop - s.target) * s.side < 0          # stop and target on opposite sides
    # the gauntlet's first call passes side=1; these families must REFUSE it (TypeError), so
    # `build_cell` falls back to the plain `fn(h1, **params)` call.
    with pytest.raises(TypeError):
        fn(df, side=1, symbol="CCCDDD", **params)


@pytest.mark.parametrize("family", sorted(xs.CROSS_SECTIONAL_FAMILIES))
def test_no_lookahead_own_and_peers(universe, tmp_path_factory, monkeypatch, family):
    fn = xs.CROSS_SECTIONAL_FAMILIES[family]
    params = {k: v[0] for k, v in xs.PARAM_GRID[family].items()}
    full = _key(fn(universe["EEEFFF"], symbol="EEEFFF", **params))
    cut = universe["EEEFFF"].index[int(len(universe["EEEFFF"]) * 0.8)]
    short_dir = tmp_path_factory.mktemp("truncated")
    for sym, frame in universe.items():
        frame[frame.index < cut].to_parquet(short_dir / f"{sym}_H1.parquet")
    monkeypatch.setattr(xs, "UNIVERSE_DIR", short_dir)
    xs._SERIES_CACHE.clear()
    own = universe["EEEFFF"]
    trunc = _key(fn(own[own.index < cut], symbol="EEEFFF", **params))
    before = [k for k in full if k[0] < cut.value]
    # the last decision before the cut can lose its next bar (no bar to enter on), nothing else
    assert trunc == before or trunc == before[:-1]
    assert before, "the comparison must cover some signals"


def test_planted_winner_is_long_momentum_short_reversal(universe):
    df = universe["AAABBB"]
    mom = xs.family_cross_sectional_class_momentum(df, symbol="AAABBB", lookback_d=60)
    rev = xs.family_cross_sectional_class_reversal(df, symbol="AAABBB", lookback_d=60)
    assert sum(s.side > 0 for s in mom) > 0.8 * len(mom)
    assert sum(s.side < 0 for s in rev) > 0.8 * len(rev)


def test_refuses_without_a_class(universe):
    df = universe["AAABBB"]
    for fn in xs.CROSS_SECTIONAL_FAMILIES.values():
        assert fn(df) == []                               # no symbol
        assert fn(df, symbol="NOTAMEMBER") == []          # no class


def test_too_few_members_ranks_nobody(universe, monkeypatch):
    monkeypatch.setattr(xs, "class_symbols", lambda k: MEMBERS[:3])
    for fn in xs.CROSS_SECTIONAL_FAMILIES.values():
        assert fn(universe["AAABBB"], symbol="AAABBB") == []


def test_fx_usd_orientation_flips_the_trade(universe, monkeypatch):
    """In fx_usd a USDXXX pair is read inverted: long the currency is SHORT the pair."""
    monkeypatch.setattr(xs, "class_of", lambda s: "fx_usd" if s in MEMBERS else None)
    monkeypatch.setattr(xs, "class_symbols", lambda k: list(MEMBERS))
    plain = xs.family_cross_sectional_class_momentum(universe["AAABBB"], symbol="AAABBB")
    monkeypatch.setattr(xs, "orientation", lambda s, k: -1 if s == "AAABBB" else 1)
    flipped = xs.family_cross_sectional_class_momentum(universe["AAABBB"], symbol="AAABBB")
    # Read inverted, the planted winner ranks as the class's LOSER currency, so the rank side is
    # SHORT -- and the orientation maps short-the-currency back onto the pair: the same price
    # path is still bought. Value and trade are inverted together or the leg would be backwards.
    assert plain and flipped
    assert sum(s.side > 0 for s in plain) > 0.8 * len(plain)
    assert sum(s.side > 0 for s in flipped) > 0.8 * len(flipped)


def test_peer_classes_follow_the_registry(tmp_path, monkeypatch):
    from research import universe_policy as up
    reg = {"EURUSD": {"asset_class": "Forex"}, "USDJPY": {"asset_class": "Forex"},
           "EURJPY": {"asset_class": "Forex"}, "USDTRY": {"asset_class": "Forex Exotics"},
           "XAUUSD": {"asset_class": "Commodities"}, "XAUEUR": {"asset_class": "Commodities"},
           "XTIUSD": {"asset_class": "Energy"}, "CORN": {"asset_class": "Soft Commodity"},
           "NAS100": {"asset_class": "Indices"}, "USDX": {"asset_class": "Indices"},
           "BTCUSD": {"asset_class": "Crypto"}, "UST10Y": {"asset_class": "Bonds"},
           "AAPL": {"asset_class": "Equities"}}
    path = tmp_path / "universe.json"
    path.write_text(json.dumps(reg), "utf-8")
    monkeypatch.setattr(up, "UNIVERSE", path)
    assert up.peer_class("EURUSD") == "fx_usd" and up.peer_class("USDTRY") == "fx_usd"
    assert up.peer_class("EURJPY") == "fx_cross"
    assert up.peer_class("XAUUSD") == "commodity" and up.peer_class("CORN") == "commodity"
    assert up.peer_class("XTIUSD") == "commodity"
    assert up.peer_class("XAUEUR") is None                 # the metal times an FX rate
    assert up.peer_class("NAS100") == "index" and up.peer_class("USDX") is None
    assert up.peer_class("BTCUSD") == "crypto" and up.peer_class("UST10Y") == "bond"
    # principal 2026-09-30: share CFDs are ranked in their own class, and only there
    assert up.peer_class("AAPL") == "equity"
    assert up.may_hypothesise("AAPL", "cross_sectional_class_momentum")
    assert not up.may_hypothesise("AAPL", "session_range_breakout")
    assert not up.may_hypothesise("AAPL")
    assert up.peer_class("NOTREAL") is None                # absent is not a permission
    assert up.usd_orientation("USDJPY") == -1 and up.usd_orientation("EURUSD") == 1
    classes = up.peer_classes()
    assert classes["fx_usd"] == ["EURUSD", "USDJPY", "USDTRY"]
    assert classes["equity"] == ["AAPL"]
    assert all("AAPL" not in v for k, v in classes.items() if k != "equity")


def test_registered_through_the_one_door():
    from mt5desk import families
    from mt5desk import families_orthogonal as fo
    from research.miner_candidate_compiler import _registered_family

    from libs.research.alpha_clusters import classify_family
    from libs.research.mechanism_census import CONSTRUCTION_CLASS
    for fam, target in xs.TARGETS.items():
        assert fo.ORTHOGONAL_FAMILIES[fam] is xs.CROSS_SECTIONAL_FAMILIES[fam]
        assert families.get_family_func(fam) is xs.CROSS_SECTIONAL_FAMILIES[fam]
        assert fo.timeframe_domain(fam) == ("H1",)
        assert fam in fo.FAMILY_INPUTS
        assert classify_family(fam) == target["cluster"]
        assert fam in CONSTRUCTION_CLASS
        assert _registered_family(fam)
    assert {t["cluster"] for t in xs.TARGETS.values()} == {
        "cross_sectional_fx", "crisis_drawdown", "cross_asset_lead_lag"}


def test_firing_lower_bound_walks_one_position_at_a_time():
    from research import cross_sectional_breadth as csb
    idx = pd.date_range("2024-01-01", periods=200, freq="h", tz="UTC")
    d = pd.DataFrame({"close": 1.0}, index=idx)

    def sig(i, ttl):
        return Signal(time=idx[i], side=1, stop=0.9, target=1.1, ttl_bars=ttl, tag="t")
    # held 24 bars each: the signal at bar 10 blocks 11..35, so 20 is skipped and 40 trades
    got = csb.firing([sig(10, 24), sig(20, 24), sig(40, 24), sig(199, 24)], d)
    assert got == {"signal_days": 3, "trade_days_lb": 2}


def _stub_policy(members):
    class _P:
        @staticmethod
        def peer_classes():
            return {"fx_cross": list(members), "bond": ["UST05Y", "UST10Y", "UKGILT"]}
    return _P()


def test_seeder_donates_only_cells_over_the_floor(universe, tmp_path, monkeypatch):
    from research import cross_sectional_breadth as csb
    from research import proposer_common as pc
    monkeypatch.setattr(xs, "_policy", lambda: _stub_policy(MEMBERS))
    monkeypatch.setattr(csb, "STATE", tmp_path / "state.json")
    monkeypatch.setattr(csb, "OUT", tmp_path / "CROSS_SECTIONAL_BREADTH.json")
    monkeypatch.setattr(csb, "BREADTH", tmp_path / "absent.json")
    monkeypatch.setattr(csb, "BREADTH_LEDGER", tmp_path / "absent2.json")
    monkeypatch.setattr(csb, "CANON", tmp_path / "absent3.json")
    monkeypatch.setattr(csb, "VERDICTS", tmp_path / "absent4.jsonl")
    donated: list[list[dict]] = []

    def fake_donate(source, rows, tests_run):
        donated.append(list(rows))
        return tmp_path / "discoveries.json"
    monkeypatch.setattr(pc, "donate", fake_donate)
    monkeypatch.setattr(pc, "donation_counts", lambda: {"donated": len(donated[-1])})

    doc = csb.run(budget_s=600, symbols=MEMBERS[:2])
    assert (tmp_path / "CROSS_SECTIONAL_BREADTH.json").exists()
    rows = donated[0]
    assert rows, "some synthetic cell must clear the floor"
    state = json.loads((tmp_path / "state.json").read_text("utf-8"))["cells"]
    by_params = {json.dumps(v["params"], sort_keys=True): v for v in state.values()}
    for r in rows:
        cell = by_params[json.dumps(r["params"], sort_keys=True)]
        assert cell["trade_days_lb"] >= csb.SEED_FLOOR
        assert r["symbol"] == r["params"]["symbol"] and r["symbol"] in MEMBERS[:2]
        assert r["family"] in xs.CROSS_SECTIONAL_FAMILIES
    held = [v for v in state.values() if v["trade_days_lb"] < csb.SEED_FLOOR]
    assert all(not v.get("donated_at") for v in held)
    # counts reconcile: every grid cell is either clearing or held back
    fam = doc["seeding"]["cells_by_family"]
    for f, c in fam.items():
        assert c["grid"] == 2 * len(csb.grid(f))
        assert c.get("clears_floor", 0) + c.get("held_back_under_floor", 0) == c["grid"]
    # UNMEASURED, never 0, before any verdict exists
    assert doc["verdicts"]["status"] == "UNMEASURED"
    assert doc["certificates"]["status"] == "UNMEASURED"
    assert doc["cluster_occupancy_now"]["status"] == "UNMEASURED"
    assert all(f["target_cluster_empty_now"] == "UNMEASURED" for f in doc["families"])

    # a second pass the same day measures nothing and donates nothing new
    donated.clear()
    doc2 = csb.run(budget_s=600, symbols=MEMBERS[:2])
    assert donated == []
    assert doc2["seeding"]["candidates_this_pass"] == 0
    assert all(c.get("measured_this_pass", 0) == 0
               for c in doc2["seeding"]["cells_by_family"].values())


def test_report_reads_occupancy_verdicts_and_certificates(universe, tmp_path, monkeypatch):
    from research import cross_sectional_breadth as csb
    monkeypatch.setattr(xs, "_policy", lambda: _stub_policy(MEMBERS))
    (tmp_path / "eb.json").write_text(json.dumps({"clusters": {
        "occupied_either": ["session_liquidity", "relative_value", "macro_rates"]}}), "utf-8")
    (tmp_path / "bl.json").write_text(json.dumps({"vacant_high_orthogonality_classes": [
        {"class": "positioning_crowding_unwind"}]}), "utf-8")
    (tmp_path / "v.jsonl").write_text("\n".join(json.dumps(r) for r in [
        {"family": "lead_lag_class_catchup", "terminal_gate": "PASSED", "passed": True},
        {"family": "lead_lag_class_catchup", "terminal_gate": "deflated_sharpe"},
        {"family": "carry", "terminal_gate": "PASSED"}]) + "\n", "utf-8")
    (tmp_path / "canon.json").write_text(json.dumps({"survivors": {
        "x.USDJPY.lead_lag_class_catchup": {"sym": "USDJPY",
                                            "shadow_spec": {"family": "lead_lag_class_catchup"}},
        "x.EURUSD.carry": {"sym": "EURUSD", "family": "carry"}}}), "utf-8")
    for name, fn in (("BREADTH", "eb.json"), ("BREADTH_LEDGER", "bl.json"),
                     ("VERDICTS", "v.jsonl"), ("CANON", "canon.json")):
        monkeypatch.setattr(csb, name, tmp_path / fn)
    doc = csb.report({"status": "OK"})
    fams = {f["family"]: f for f in doc["families"]}
    assert fams["cross_sectional_class_momentum"]["target_cluster_empty_now"] is True
    assert fams["crisis_only_class_defensive"]["census_class_vacant_now"] is True
    assert fams["lead_lag_class_catchup"]["census_class_vacant_now"] is False
    assert doc["verdicts"]["by_family"] == {
        "lead_lag_class_catchup": {"PASSED": 1, "deflated_sharpe": 1}}
    assert doc["certificates"]["by_cluster"] == {"cross_asset_lead_lag": 1}
    assert doc["certificates"]["total"] == 1


def test_hourly_leg_is_wired():
    """The seeder is a costed leg of the hourly cycle, in a department and a layer."""
    text = (_DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert '_costed("cross_sectional_breadth"' in text
    assert '"research/cross_sectional_breadth.py"' in text
    from libs.research.layers import LEG_LAYER
    assert LEG_LAYER["cross_sectional_breadth"] == "prediction"
    import importlib
    hc = importlib.import_module("research.hourly_cycle")
    assert hc.department_of("cross_sectional_breadth") == "discovery"
    assert hc.LEG_BUDGET_SEC["cross_sectional_breadth"] >= 900


def test_sealed_gauntlet_rebuilds_every_family_through_its_own_import_path(universe, monkeypatch):
    """The judge's OWN door: `external_gauntlet.build_cell`, imported exactly as the sweep imports
    it, rebuilds every family from (symbol, family, params) with no sealed edit -- and none of the
    families is banned by `family_policy` (whose PERMANENT list holds `discovered`)."""
    sys.path.insert(0, str(_DESK / "scripts"))
    import external_gauntlet as eg
    from research.family_policy import PERMANENT, family_banned
    monkeypatch.setattr(eg, "_bars_for", lambda sym, tf="H1": universe.get(sym))
    for fam in xs.CROSS_SECTIONAL_FAMILIES:
        assert not family_banned(fam) and fam not in PERMANENT
        params = {"symbol": "GGGHHH", **{k: v[0] for k, v in xs.PARAM_GRID[fam].items()}}
        cell = eg.build_cell("GGGHHH", fam, dict(params), {})
        assert cell is not None, f"{fam}: {eg.LAST_BUILD_FAILURE}"
        assert eg.LAST_BUILD_FAILURE is None
        assert cell["sigs"], f"{fam} rebuilt by the gauntlet with no signals"


def test_real_registry_ranks_share_cfds_only_in_their_own_class():
    """On the desk's own registry: single names rank only against single names (principal
    2026-09-30); every other class is hypothesis-lane only, and indices are ranked too."""
    from research import universe_policy as up
    classes = up.peer_classes()
    ranked = {s for k, v in classes.items() if k != "equity" for s in v}
    if not ranked:
        pytest.skip("registry absent on this host -- UNMEASURED, not a pass")
    assert all(up.lane(s) == up.HYPOTHESIS for s in ranked)
    assert all(up.is_equity(s) for s in classes.get("equity", []))
    assert classes.get("index"), "indices are ranked too"


def test_equity_admission_is_pinned_to_the_class_book_families():
    from mt5desk.families_cross_sectional import CROSS_SECTIONAL_FAMILIES

    from research import universe_policy as up
    assert set(CROSS_SECTIONAL_FAMILIES) | {"zoo_alpha_class"} == set(up.CROSS_SECTIONAL_FAMILIES)

def test_merge_door_admits_a_share_cfd_only_in_a_class_book(tmp_path, monkeypatch):
    """The docket door passes the row's family, so AAPL momentum reaches the judge and AAPL
    breakout stays in the event lane (principal 2026-09-30)."""
    from research import merge_hypotheses as mh
    from research import universe_policy as up
    reg = {"EURUSD": {"asset_class": "Forex"}, "AAPL": {"asset_class": "Equities"}}
    path = tmp_path / "universe.json"
    path.write_text(json.dumps(reg), "utf-8")
    monkeypatch.setattr(up, "UNIVERSE", path)
    refusal, _why = mh.lane_router({"EURUSD": "EURUSD", "AAPL": "AAPL"})
    assert refusal is not None
    rows = [{"symbol": "AAPL", "family": "cross_sectional_class_momentum"},
            {"symbol": "AAPL", "family": "session_range_breakout"},
            {"symbol": "EURUSD", "family": "session_range_breakout"}]
    judged, off, _, _ = mh.split_by_lane(rows, refusal, "now")
    assert [(r["symbol"], r["family"]) for r in judged] == [
        ("AAPL", "cross_sectional_class_momentum"), ("EURUSD", "session_range_breakout")]
    assert [(r["symbol"], r["family"]) for r in off] == [("AAPL", "session_range_breakout")]


def test_one_argument_doors_still_work():
    from research import merge_hypotheses as mh
    judged, off, _, _ = mh.split_by_lane([{"symbol": "X", "family": "f"}],
                                         lambda s: "event", "now")
    assert not judged and len(off) == 1
