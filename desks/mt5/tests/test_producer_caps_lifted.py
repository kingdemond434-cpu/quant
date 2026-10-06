"""The four producers sealed pass 2 unblocked carry no artificial breadth cap (2026-10-01).

cross_asset_graph swept `book_symbols()[:12]`, asia_transmission was on no clock, and the two
event_reaction organs donated 10 and 15 of their clearing cells. Each pin below fails if the
cap comes back.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parents[1]
for _p in (str(_ROOT), str(_DESK), str(_DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import cross_asset_graph as cag  # noqa: E402
import event_response_atlas as era  # noqa: E402
import event_surprise as es  # noqa: E402

from research import producer_breadth as pb  # noqa: E402


def test_the_statistical_pair_space_is_every_ordered_pair_once() -> None:
    syms = [f"S{i:02d}" for i in range(30)]
    pairs = cag._pairs(syms, {}, set(syms))
    stat = [(a, b) for a, b, role in pairs if role is None]
    assert len(stat) == len(set(stat)) == 30 * 29


def test_the_universe_is_not_a_twelve_name_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    import universe_policy as up
    monkeypatch.setattr(up, "may_hypothesise", lambda s, f=None: not s.startswith("EQ"))
    have = {f"FX{i:02d}" for i in range(20)} | {"XAUUSD", "EQ1"}
    out = cag._universe(["XAUUSD", "FX05"], have)
    assert out[:2] == ["XAUUSD", "FX05"]                        # the book first
    assert len(out) == 21 and "EQ1" not in out                  # never a single name


def _bars(n: int, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-01-01", periods=n, freq="h", tz="UTC")
    close = 1.0 + np.cumsum(rng.normal(0, 1e-3, n))
    return pd.DataFrame({"open": close, "high": close, "low": close, "close": close}, index=idx)


def test_the_cursor_walks_the_whole_space_and_the_graph_keeps_every_edge(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    syms = [f"S{i}" for i in range(5)]                          # 20 statistical pairs
    monkeypatch.setattr(cag, "GRAPH", tmp_path / "g.json")
    monkeypatch.setattr(cag, "REPORT", tmp_path / "r.json")
    monkeypatch.setattr(cag, "CURSOR", tmp_path / "c.json")
    monkeypatch.setattr(cag, "CHARGED", tmp_path / "charged.json")
    monkeypatch.setattr(cag.pc, "NULL_PASS_TRIALS", tmp_path / "null.jsonl")
    monkeypatch.setattr(cag, "_book_symbols", lambda: syms)
    monkeypatch.setattr(cag, "_universe", lambda book, have: list(book))
    monkeypatch.setattr(cag, "_event_times", lambda: [])
    monkeypatch.setattr(cag.pc, "universe_meta", lambda: {})
    monkeypatch.setattr(cag.pc, "UNI", tmp_path)
    for s in syms:
        (tmp_path / f"{s}_H1.parquet").write_bytes(b"")
    monkeypatch.setattr(cag.pc, "bars", lambda s: _bars(50, hash(s) % 97))
    calls = {"n": 0}

    def edge(d, t, plausible_role=None):
        calls["n"] += 1
        return {"verdict": "NO_EDGE", "t": 0.1}
    monkeypatch.setattr(cag.lead_lag, "edge", edge)
    clock = iter(range(0, 10_000))
    # each edge costs one "second"; a 14 s budget at GRAPH_SHARE 0.5 measures ~7 per pass
    monkeypatch.setattr(cag.time, "monotonic", lambda: float(next(clock)))
    for _ in range(4):
        cag.run(budget_s=14.0)
    doc = json.loads((tmp_path / "g.json").read_text("utf-8"))
    assert doc["coverage"]["pairs_in_space"] == 20
    assert doc["n_pairs"] == 20                                  # every pair held after wrap
    assert json.loads((tmp_path / "c.json").read_text("utf-8"))["n_stat"] == 20


def test_asia_transmission_is_on_the_hourly_clock() -> None:
    src = (_DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    clocks = pb.clocks_for("asia_transmission", "asia_transmission",
                           {"hourly_cycle": src}, [])
    assert clocks == ["hourly_cycle:asia_transmission"]
    assert '"research/asia_transmission.py", "--propose"' in src


def test_the_event_reaction_organs_donate_every_clearing_cell() -> None:
    assert es.MAX_DONATIONS == es.MAX_PUBLISHED
    assert era.MAX_DONATIONS == era.MAX_PUBLISHED
    import inspect
    assert inspect.signature(era.run).parameters["max_donations"].default == era.MAX_PUBLISHED
    assert inspect.signature(es.build).parameters["max_donations"].default == es.MAX_PUBLISHED


def test_the_inventory_says_the_caps_are_lifted() -> None:
    for name in ("cross_asset_graph", "event_surprise", "event_response_atlas"):
        assert pb.INVENTORY[name]["status"] == "WIDENED"
    assert pb.INVENTORY["asia_transmission"]["status"] == "WIRED"


def test_execution_state_is_swept_in_both_modes_on_surface_symbols_only(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import breadth_sweep as bs
    spec = bs.READY["execution_state"]
    assert {g["mode"] for g in spec["grid"]} == {"cheap_deep", "dear_thin"}
    from research import orthogonal_sweep as inputs
    surf = tmp_path / "MICROSTRUCTURE_SURFACES.json"
    surf.write_text(json.dumps({"symbols": {"EURUSD": {"x": 1}, "GBPUSD": {}}}), "utf-8")
    monkeypatch.setattr(inputs, "MICROSTRUCTURE_SURFACES", surf)
    assert bs._targets("execution_state", spec, ["EURUSD", "GBPUSD", "USDJPY"]) == [
        ("EURUSD", {})]
    monkeypatch.setattr(inputs, "MICROSTRUCTURE_SURFACES", tmp_path / "absent.json")
    assert len(bs._targets("execution_state", spec, ["EURUSD", "USDJPY"])) == 2


# =============================================================================================
# The audit's HOLD on #180 (2026-10-06): trials charged once over the union, null passes charged,
# donations distinct by what the replay executes.
# =============================================================================================

def _graph_world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, syms: list[str]) -> Path:
    null = tmp_path / "null.jsonl"
    for name, path in (("GRAPH", "g.json"), ("REPORT", "r.json"), ("CURSOR", "c.json"),
                       ("CHARGED", "charged.json")):
        monkeypatch.setattr(cag, name, tmp_path / path)
    monkeypatch.setattr(cag.pc, "NULL_PASS_TRIALS", null)
    monkeypatch.setattr(cag.pc, "universe_meta", lambda: {})
    monkeypatch.setattr(cag.pc, "UNI", tmp_path)
    monkeypatch.setattr(cag, "_event_times", lambda: [])
    for s in syms:
        (tmp_path / f"{s}_H1.parquet").write_bytes(b"")
    monkeypatch.setattr(cag.pc, "bars", lambda s: _bars(50, hash(s) % 97))
    monkeypatch.setattr(cag.lead_lag, "edge",
                        lambda d, t, plausible_role=None: {"verdict": "NO_EDGE", "t": 0.1})
    return null


def _pair_charges(null: Path) -> list[int]:
    rows = [json.loads(x) for x in null.read_text("utf-8").splitlines() if x.strip()]
    return [r["tests_run"] for r in rows if r.get("kind") == "pair_identity_union"]


def test_every_lag_searched_pair_is_charged_once_over_the_lifetime(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Two passes over the same pairs charge them once; a new symbol's new pairs add one each."""
    null = _graph_world(tmp_path, monkeypatch, ["A", "B", "C", "D"])
    cag.run(symbols=["A", "B", "C"], budget_s=1e6)               # 6 ordered pairs
    assert _pair_charges(null) == [6]
    rep = cag.run(symbols=["A", "B", "C"], budget_s=1e6)          # the same 6: nothing new
    assert _pair_charges(null) == [6]
    assert rep["pairs_newly_charged"] == 0 and rep["pairs_lifetime_union"] == 6
    rep = cag.run(symbols=["A", "B", "C", "D"], budget_s=1e6)     # 12 pairs, 6 of them new
    assert _pair_charges(null) == [6, 6]
    assert rep["pairs_lifetime_union"] == 12
    union = json.loads((tmp_path / "charged.json").read_text("utf-8"))["pairs"]
    assert cag.pair_identity("A", "B") in union
    assert cag.pair_identity("A", "B").endswith(f"|lags=1..{cag.lead_lag.MAX_LAG}|"
                                                f"{cag.EDGE_METHOD}")
    assert cag.pair_identity("A", "B") != cag.pair_identity("B", "A")   # ordered


def test_the_lifetime_ledger_reads_the_pair_charge(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The charge lands where `experiment_ledger.lifetime` looks, under the lead_lag family."""
    from libs.research import experiment_ledger as el
    desk = tmp_path / "desk"
    (desk / "data").mkdir(parents=True)
    monkeypatch.setattr(el, "DESK", desk)
    null = _graph_world(tmp_path, monkeypatch, ["A", "B", "C"])
    monkeypatch.setattr(cag.pc, "NULL_PASS_TRIALS", desk / "data" / "null_pass_trials.jsonl")
    cag.run(symbols=["A", "B", "C"], budget_s=1e6)
    cag.run(symbols=["A", "B", "C"], budget_s=1e6)
    total, by_fam = el._proposer_counts()
    # 6 pair identities once, plus each pass's screened rows (0: no EDGE, nothing screened)
    assert by_fam.get("lead_lag") == 6 and total == 6
    assert not null.exists()


def test_an_unmeasured_pair_was_never_searched_and_is_not_charged(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    null = _graph_world(tmp_path, monkeypatch, ["A", "B"])
    monkeypatch.setattr(cag.lead_lag, "edge",
                        lambda d, t, plausible_role=None: {"verdict": "UNMEASURED", "n": 3})
    rep = cag.run(symbols=["A", "B"], budget_s=1e6)
    assert rep["pairs_newly_charged"] == 0 and not null.exists()


def test_an_asia_pass_that_donates_nothing_is_still_charged(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import asia_transmission as atx

    from research import proposer_common as pc
    null = tmp_path / "null.jsonl"
    monkeypatch.setattr(pc, "NULL_PASS_TRIALS", null)
    monkeypatch.setattr(atx, "OUT", tmp_path / "ASIA.json")
    monkeypatch.setattr(atx, "measure", lambda budget_s=600.0: {"rows": [], "bars": {},
                                                                "meta": {}})
    donated: list[int] = []
    monkeypatch.setattr(pc, "donate", lambda *a, **k: donated.append(1) or None)
    assert atx.main(["--propose", "--budget", "5"]) == 0
    rows = [json.loads(x) for x in null.read_text("utf-8").splitlines()]
    want = len(atx.CHAINS) * len(atx.ENTRY_Z) * len(atx.HOLDS)
    assert [(r["source"], r["tests_run"], r["by_family"]) for r in rows] == [
        ("asia_transmission", want, {"lead_lag": want})]
    assert donated == []                                          # nothing to donate
    assert json.loads((tmp_path / "ASIA.json").read_text("utf-8"))["null_trials_charged"] == want
    # a pass WITHOUT --propose screened nothing and charges nothing
    assert atx.main(["--budget", "5"]) == 0
    assert len(null.read_text("utf-8").splitlines()) == 1


def test_an_asia_pass_whose_donation_lands_is_not_charged_twice(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import asia_transmission as atx

    from research import proposer_common as pc
    null = tmp_path / "null.jsonl"
    monkeypatch.setattr(pc, "NULL_PASS_TRIALS", null)
    monkeypatch.setattr(atx, "OUT", tmp_path / "ASIA.json")
    monkeypatch.setattr(atx, "measure", lambda budget_s=600.0: {"rows": [], "bars": {},
                                                                "meta": {}})
    monkeypatch.setattr(atx, "propose", lambda m, budget_s=600.0: [])
    monkeypatch.setattr(pc, "best_per_cell", lambda rows: [
        {"symbol": "AUDUSD", "params": {"lag": 1}, "chain": "x"}])
    sent: list[list[dict]] = []
    monkeypatch.setattr(pc, "donate", lambda src, cands, tests_run: sent.append(cands)
                        or tmp_path / "discoveries_x.json")
    assert atx.main(["--propose"]) == 0
    assert not null.exists()
    # the candidate is built with its title and evidence (five arguments raised TypeError)
    assert sent[0][0]["title"].startswith("AUDUSD.lead_lag.") and "evidence" in sent[0][0]


_PROFILE_UP = {"15m": 4.0, "1h": 9.0, "4h": 20.0, "1d": 6.0}       # peaks at 4h, decays by 1d
_PROFILE_LATE = {"15m": -3.0, "1h": -2.0, "4h": 5.0, "1d": 15.0}   # adverse first hour, no decay


def test_the_measured_shape_sets_hold_cooldown_and_entry_delay() -> None:
    shape = era.measured_shape(_PROFILE_UP, 1.0)
    assert shape["peak"] == "4h" and shape["delayed"] is False
    # half of 20bp is 10bp, crossed between 4h (20) and 1d (6): 240 + 1200 * 10/14 minutes
    assert shape["half_life_h"] == pytest.approx((240 + 1200 * 10 / 14) / 60, abs=0.01)
    late = era.measured_shape(_PROFILE_LATE, 1.0)
    assert late["peak"] == "1d" and late["half_life_h"] is None and late["delayed"] is True
    assert era.measured_shape(_PROFILE_UP, -1.0) == {}             # never oriented positive
    p = era.donation_params("1h", "continuation", profile_bp=_PROFILE_UP, sign=1.0)
    assert (p["hold_bars"], p["ttl_bars"], p["cooldown_bars"]) == (4, 4, 18)
    assert "entry_timing" not in p
    q = era.donation_params("1d", "continuation", profile_bp=_PROFILE_LATE, sign=1.0)
    assert (q["hold_bars"], q["ttl_bars"], q["entry_timing"]) == (24, 24, "delayed")
    # the conditioner the reaction was measured in becomes an executable key
    assert era.donation_params("4h", "continuation", profile_bp=_PROFILE_UP, sign=1.0,
                               axis="vol_tercile", bucket="high")["regime"] == "high_vol"
    assert era.donation_params("4h", "reversal", profile_bp={"4h": -5.0}, sign=-1.0,
                               axis="surprise_proxy", bucket="move_dn_ge1sigma")["side"] == -1
    # every key it adds is one the replay applies, never a label it ignores
    from mt5desk import cell_modifiers as cm
    from mt5desk.family_event_reaction import family_event_reaction
    _call, mods = cm.split(family_event_reaction, {**q, "regime": "high_vol"})
    assert cm.refusal(mods) is None and set(mods) == {"entry_timing", "regime"}


def _clearing(symbol: str, kind: str, axis: str, bucket: str,
              profile: dict[str, float]) -> list[dict]:
    return [{"cell": f"{kind}.{symbol}.{h}.{axis}={bucket}", "kind": kind, "symbol": symbol,
             "horizon": h, "axis": axis, "bucket": bucket, "n": 30, "mean_bp": v, "t": 6.0,
             "hit_rate": 0.6, "cost_bp": 1.0, "cost_source": "x", "profile_bp": profile,
             "direction": "continuation" if v > 0 else "reversal"}
            for h, v in profile.items() if v > 0]


def test_the_atlas_donates_one_cell_per_executable_identity(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """Four horizons of one reaction are one trade; two kinds with the same shape are one; a
    reaction with a different shape is a second cell."""
    clearing = (_clearing("EURUSD", "cpi", "all", "all", _PROFILE_UP)
                + _clearing("EURUSD", "nfp", "all", "all", _PROFILE_UP)
                + _clearing("EURUSD", "pmi", "all", "all", _PROFILE_LATE))
    sent: list[dict] = []
    monkeypatch.setattr(era, "_registered_family", lambda name: True)
    monkeypatch.setattr(era, "_lane_ok", lambda s: True)
    monkeypatch.setattr(era, "_donate", lambda c, n: sent.extend(c) or Path("x.json"))
    out = era.donate_clearing({"clearing": clearing, "n_cells": 500}, 300)
    assert len(clearing) == 10
    assert out["n"] == 2 and out["duplicates_dropped"] == 8
    idents = {era.executable_identity(c["symbol"], c["family"], c["params"]) for c in sent}
    assert len(idents) == 2


def test_event_surprise_drops_executable_duplicates(monkeypatch: pytest.MonkeyPatch) -> None:
    def cell(kind: str, bucket: str, profile: dict[str, float]) -> dict:
        h = max(profile, key=lambda k: profile[k])
        return {"cell": f"EURUSD {kind} {bucket} {h} ALL", "symbol": "EURUSD", "kind": kind,
                "bucket": bucket, "horizon": h, "regime": "ALL", "mean_bp": profile[h],
                "n": 30, "t": 6.0, "sd_bp": 3.0, "hit_rate": 0.6, "impact_mean_bp": 1.0,
                "cost_bp": 1.0, "direction": "with_surprise", "tradable_share": 0.5,
                "profile_bp": profile}
    clearing = [cell("cpi", "up_ge1sigma", _PROFILE_UP), cell("nfp", "up_ge1sigma", _PROFILE_UP),
                cell("pmi", "dn_lt1sigma", _PROFILE_LATE)]
    monkeypatch.setattr(es, "_registered", lambda f: True)
    monkeypatch.setattr(es, "_may_hypothesise", lambda s: True)
    out, refused = es.donation_rows(clearing, 400)
    assert len(out) == 2
    assert [r["why"].startswith("an executable duplicate") for r in refused] == [True]
    assert out[1]["params"]["entry_timing"] == "delayed" and out[1]["params"]["ttl_bars"] == 24


def test_asia_chain_measurements_are_charged_once_per_chain_identity(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Each chain's pooled and Asia-hours lag searches are looks: charged the first pass, never
    again; a new chain adds its two; an UNMEASURED window ran no search and is not charged."""
    import asia_transmission as atx

    from libs.research import lead_lag
    from research import proposer_common as pc
    null = tmp_path / "null.jsonl"
    monkeypatch.setattr(pc, "NULL_PASS_TRIALS", null)
    monkeypatch.setattr(atx, "CHARGED", tmp_path / "asia_charged.json")
    monkeypatch.setattr(pc, "universe_meta", lambda: {})
    monkeypatch.setattr(pc, "UNI", tmp_path)
    for s in ("D1", "T1", "D2", "T2"):
        (tmp_path / f"{s}_H1.parquet").write_bytes(b"")
    monkeypatch.setattr(pc, "bars", lambda s: _bars(50, 1))
    monkeypatch.setattr(lead_lag, "edge",
                        lambda d, t, plausible_role=None: {"verdict": "NO_EDGE", "t": 0.1})

    def chain(name: str, d: str, t: str) -> dict:
        return {"name": name, "hops": [], "driver": d, "target": t, "expected": "same",
                "rationale": "r", "falsifier": "f"}
    one = (chain("c1", "D1", "T1"),)
    monkeypatch.setattr(atx, "CHAINS", one)

    def charges() -> list[int]:
        return [json.loads(x)["tests_run"] for x in null.read_text("utf-8").splitlines()
                if json.loads(x).get("kind") == "chain_identity_union"]
    assert atx.measure(budget_s=1e6)["chain_looks"]["newly_charged"] == 2
    assert atx.measure(budget_s=1e6)["chain_looks"] == {"looked": 2, "newly_charged": 0,
                                                        "lifetime_union": 2}
    assert charges() == [2]
    monkeypatch.setattr(atx, "CHAINS", (*one, chain("c2", "D2", "T2")))
    assert atx.measure(budget_s=1e6)["chain_looks"]["lifetime_union"] == 4
    assert charges() == [2, 2]
    union = json.loads((tmp_path / "asia_charged.json").read_text("utf-8"))["pairs"]
    assert atx.chain_identity("c1", "D1", "T1", "asia_hours", lead_lag.MAX_LAG) in union
    monkeypatch.setattr(atx, "CHAINS", (chain("c3", "D1", "T2"),))
    monkeypatch.setattr(lead_lag, "edge",
                        lambda d, t, plausible_role=None: {"verdict": "UNMEASURED", "n": 3})
    assert atx.measure(budget_s=1e6)["chain_looks"]["newly_charged"] == 0
    assert charges() == [2, 2]
