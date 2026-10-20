"""Spread recovery (P8-M2) and the factor-factory registry (pass 8): measured, causal, wired.

Item A -- spread recovery:
* events are located on the bar clock: the week open by its gap, rollover at server midnight
  (week open excluded), Tokyo at 00:00 UTC through `session_clock.utc_to_server`;
* a planted exponential decay is recovered; a one-bar shock is BELOW_RESOLUTION, never fitted;
* the `spread_gate` modifier is TWO-SIDED: a normal spread enters a bar earlier than the fixed
  wait, a wide one later; it never drops a signal; a bad value is refused by name;
* the fade family is causal (perturbing the future leaves past signals unchanged) and fades;
* the organ seeds the preregistered grid, charges every point once, never twice, and publishes
  missed-growth lines that `missed_growth` carries;
* the family is registered through every door.

Item B -- the producer registry:
* the five factor-factory producers read SUPERSEDED while `alpha_evolution` produces, and DEAD
  (fatal) when it does not;
* `alpha_rl_run` is SET_ASIDE while it emits no cell and the set-aside lifts, permanently, on the
  first measured cell;
* the learned miners' weekly leg (tested in test_learned_trials_once.py) drives the one
  contract clock; its contract is held to seven days in producer health.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
DESK = ROOT / "desks" / "mt5"
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import cell_modifiers as cm  # noqa: E402
from mt5desk import family_spread_recovery as fsr  # noqa: E402
from mt5desk.engine import Signal  # noqa: E402

from libs.regime.session_clock import utc_to_server  # noqa: E402


def _bars(n_days: int = 60, seed: int = 3, shock: float = 4.0, decay_bars: float = 0.0,
          start: str = "2026-01-05") -> pd.DataFrame:
    """Weekday H1 bars on the server clock, spread 10 points, `shock` x at server midnight."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range(start, periods=n_days * 24, freq="1h", tz="UTC")
    idx = idx[idx.dayofweek < 5]
    n = len(idx)
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.001, n)))
    open_ = np.r_[close[0], close[:-1]]
    sp = np.full(n, 10.0)
    for i in np.flatnonzero(idx.hour == 0):
        for k in range(8):
            if i + k < n:
                excess = (shock - 1.0) * (np.exp(-k * np.log(2) / decay_bars) if decay_bars
                                          else (1.0 if k == 0 else 0.0))
                sp[i + k] = 10.0 * (1.0 + excess)
    return pd.DataFrame({"open": open_, "high": np.maximum(open_, close) * 1.0005,
                         "low": np.minimum(open_, close) * 0.9995, "close": close,
                         "tick_volume": 100.0, "spread": sp}, index=idx)


# =================================================================================== events
def test_events_are_placed_on_the_server_clock() -> None:
    d = _bars(30)
    idx = d.index
    week = fsr.event_positions(idx, "sunday_open")
    assert len(week) > 0 and all(idx[p].dayofweek == 0 and idx[p].hour == 0 for p in week)
    roll = fsr.event_positions(idx, "rollover")
    assert all(idx[p].hour == 0 for p in roll)
    assert not set(roll) & set(week), "the week open is its own event, not a rollover"
    tok = fsr.event_positions(idx, "tokyo_open")
    stamps = {utc_to_server(pd.Timestamp(idx[p].date(), tz="UTC") + pd.Timedelta(days=k))
              for p in tok for k in (0, 1)}
    for p in tok:
        assert idx[p] in stamps
        assert idx[p].hour in (2, 3), "00:00 UTC is 02:00/03:00 on the server clock"


def test_a_planted_decay_is_recovered_and_a_one_bar_shock_is_below_resolution() -> None:
    m = fsr.measure(_bars(80, shock=5.0, decay_bars=2.0), "rollover")
    assert m["state"] == "FITTED"
    assert m["half_life_h"] == pytest.approx(2.0, rel=0.15)
    assert m["excess_t0"] == pytest.approx(4.0, rel=0.05) and m["n"] > 30
    one = fsr.measure(_bars(80, shock=5.0), "rollover")
    assert one["state"] == "BELOW_RESOLUTION" and one["half_life_h"] is None
    assert one["half_life_upper_bound_h"] == pytest.approx(1.0)
    flat = fsr.measure(_bars(80, shock=1.0), "rollover")
    assert flat["state"] == "NO_SHOCK"
    assert fsr.measure(_bars(10).drop(columns="spread"), "rollover")["state"] == "UNMEASURED"


# ===================================================================================== gate
def _sig(t: Any, side: int = 1) -> Signal:
    return Signal(time=t, side=side, stop=90.0, target=110.0, ttl_bars=4, tag="t")


def test_the_gate_is_two_sided_and_never_drops_a_signal() -> None:
    d = _bars(40, shock=5.0, decay_bars=2.0)
    idx = d.index
    wide = [p for p in np.flatnonzero(idx.hour == 0) if p > 200][:5]
    calm = [p + 6 for p in wide]
    sigs = [_sig(idx[p]) for p in wide + calm]
    out = fsr.apply_gate(sigs, d, "k:1.5")
    assert len(out) == len(sigs)
    pos = {t: i for i, t in enumerate(idx)}
    waits = [pos[o.time] - pos[s.time] for o, s in zip(out, sigs, strict=True)]
    assert all(w > 1 for w in waits[:5]), "a wide spread waits beyond the fixed one bar"
    assert all(w == 0 for w in waits[5:]), "a normal spread enters a bar EARLIER than fixed"
    hl = fsr.gate_waits(d, wide, ("hl", 2.0))
    assert all(w >= 2 for w in hl)


def test_the_gate_rides_the_cell_modifier_door() -> None:
    assert "spread_gate" in cm.MODIFIER_KEYS
    assert cm.refusal({"spread_gate": "k:0.9"}) is not None
    assert cm.refusal({"spread_gate": "soon"}) is not None
    assert cm.refusal({"spread_gate": "hl:2"}) is None

    def fam(df: pd.DataFrame, *, n: int = 1) -> list:
        return [_sig(df.index[p]) for p in np.flatnonzero(df.index.hour == 0)[5:9]]
    d = _bars(30, shock=5.0, decay_bars=2.0)
    kw, mods = cm.split(fam, {"n": 1, "spread_gate": "k:1.5"})
    assert kw == {"n": 1} and mods == {"spread_gate": "k:1.5"}
    gated = cm.apply(fam(d, **kw), d, mods)
    assert [s.time for s in gated] != [s.time for s in fam(d)]
    assert cm.apply(fam(d), d.drop(columns="spread"), mods) == [], \
        "no spread column: nothing is built under the gate's name"


# ===================================================================================== fade
def test_the_fade_is_causal_and_fades_the_wide_window_move() -> None:
    d = _bars(60, shock=5.0, decay_bars=1.5)
    # Plant a displacement inside every wide window: a jump at the rollover bar.
    for p in np.flatnonzero(d.index.hour == 0):
        d.iloc[p:p + 5, d.columns.get_loc("close")] *= 1.01
    sigs = fsr.family_spread_recovery_fade(d, event="rollover", k_mult=1.5, min_disp_atr=0.25)
    assert sigs and all(s.side == -1 for s in sigs), "an up-move in the hole is faded short"
    cut = len(d) * 2 // 3
    e = d.copy()
    e.iloc[cut:, e.columns.get_loc("close")] *= 1.05
    e.iloc[cut:, e.columns.get_loc("spread")] *= 3.0
    before = [(s.time, s.side) for s in sigs if d.index.get_loc(s.time) < cut - 1]
    after = [(s.time, s.side) for s in fsr.family_spread_recovery_fade(
        e, event="rollover", k_mult=1.5, min_disp_atr=0.25) if e.index.get_loc(s.time) < cut - 1]
    assert before == after


# ==================================================================================== organ
@pytest.fixture()
def universe(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    from research import spread_recovery as sr
    from research import universe_policy
    uni = tmp_path / "universe"
    uni.mkdir()
    _bars(400, shock=5.0, decay_bars=1.5).to_parquet(uni / "EURUSD_H1.parquet")
    (uni / "universe.json").write_text(json.dumps({"EURUSD": {"tick_size": 1e-5,
                                                              "asset_class": "Forex"}}))
    monkeypatch.setattr(universe_policy, "may_hypothesise", lambda s, f=None: s == "EURUSD")
    monkeypatch.setattr(sr, "SEED_FLOOR", 5)
    return uni


def test_the_organ_charges_every_grid_point_once(universe: Path, tmp_path: Path,
                                                 monkeypatch: pytest.MonkeyPatch) -> None:
    from research import proposer_common as pc
    from research import spread_recovery as sr
    donated: list[tuple[int, int]] = []

    def door(source: str, rows: list, tests_run: int) -> Path:
        assert all(r["declared_width"] == 1 for r in rows)
        donated.append((len(rows), tests_run))
        return tmp_path / "d.json"
    monkeypatch.setattr(pc, "donate", door)
    monkeypatch.setattr(pc, "donation_counts", lambda: {"donated": 1})
    kw: dict[str, Any] = {"universe": universe, "git_bars": tmp_path / "none",
                          "ticks": tmp_path / "none", "state_path": tmp_path / "state.json",
                          "out": tmp_path / "SPREAD_RECOVERY.json"}
    rep = sr.run(budget_s=600, **kw)
    grid = len(sr.plan(["EURUSD"]))
    assert rep["cells"]["cells_planned"] == grid == 24 + len(sr.GATE_VALUES)
    assert donated and donated[0][1] == grid, "every point charged, fired or not"
    assert rep["cells"]["trials_pending_charge"] == 0
    roll = next(h for h in rep["half_lives"] if h["event"] == "rollover")
    assert roll["state"] in ("FITTED", "TWO_POINT") and roll["n"] > 100
    lines = rep["missed_growth"]
    assert {ln["gate"] for ln in lines} == {f"spread_gate={g}" for g in sr.GATE_VALUES}
    assert all(ln["direction"] == "two_sided" for ln in lines)
    donated.clear()
    sr.run(budget_s=600, **kw)
    assert not donated, "a second pass donates nothing and charges nothing again"
    assert json.loads((tmp_path / "SPREAD_RECOVERY.json").read_text())["source"] == sr.SOURCE


def test_missed_growth_carries_the_gate_lines(tmp_path: Path,
                                              monkeypatch: pytest.MonkeyPatch) -> None:
    import missed_growth as mg
    p = tmp_path / "SPREAD_RECOVERY.json"
    monkeypatch.setattr(mg, "SPREAD_RECOVERY", p)
    assert mg.spread_gate_lines()["verdict"] == mg.UNMEASURED
    p.write_text(json.dumps({"generated_at": datetime.now(tz=UTC).isoformat(),
                             "missed_growth": [{"gate": "spread_gate=k:1.5", "value": -1e-5,
                                                "verdict": "COSTS_GROWTH", "n_advanced": 3,
                                                "n_delayed": 4}]}))
    got = mg.spread_gate_lines()
    assert got["verdict"] == mg.COSTS and got["by_direction"] == {"advanced": 3, "delayed": 4}
    p.write_text(json.dumps({"generated_at": (datetime.now(tz=UTC)
                                              - timedelta(hours=9)).isoformat(),
                             "missed_growth": [{"value": 1.0}]}))
    assert mg.spread_gate_lines()["verdict"] == mg.UNMEASURED


def test_the_family_is_registered_through_every_door() -> None:
    from mt5desk.families_orthogonal import FAMILY_INPUTS, FAMILY_TIMEFRAMES, ORTHOGONAL_FAMILIES

    from libs.research import layers
    from libs.research.alpha_clusters import FAMILY_CLUSTER
    from libs.research.mechanism_census import CONSTRUCTION_CLASS
    from research import alpha_genome, axis_registry, orthogonal_sweep
    from research import hourly_cycle as hc
    fam = "spread_recovery_fade"
    assert fam in ORTHOGONAL_FAMILIES and fam in FAMILY_INPUTS and fam in FAMILY_TIMEFRAMES
    assert fam in axis_registry.FAMILY_TABLE and fam in FAMILY_CLUSTER
    assert fam in CONSTRUCTION_CLASS and fam in orthogonal_sweep.NOT_SOURCED_HERE
    assert alpha_genome.MECHANISM_CLASS[fam] == "microstructure"
    for leg in ("spread_recovery", "learned_miners_weekly"):
        assert hc.LEG_DEPARTMENT[leg] == "discovery" and leg in layers.LEG_LAYER
    assert hc.LEG_BUDGET_SEC["spread_recovery"] > 480
    assert hc.LEG_BUDGET_SEC["learned_miners_weekly"] > 900
    src = (DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert '"research/spread_recovery.py"' in src and '"--weekly"' in src


# ======================================================================= item B: the registry
@pytest.fixture()
def fence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    from scripts import check_producer_yield as f
    for name, fn in (("CENSUS", "census.json"), ("BLOCKERS", "blockers.json"),
                     ("RATCHET", "ratchet.json"), ("REGISTRY_DB", "reg.sqlite"),
                     ("ROW_CONVERSION", "row.json")):
        monkeypatch.setattr(f, name, tmp_path / fn)
    return f


def _seats(f: Any, monkeypatch: pytest.MonkeyPatch, seats: dict[str, int]) -> None:
    monkeypatch.setattr(f, "_seat_output", lambda window_days: dict(seats))


def test_the_factor_factory_is_superseded_while_its_successor_produces(
        fence: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    dead = ("mathlab", "lab_timeseries", "lab_probability", "expression_factory",
            "alpha_periodic_table")
    assert {k: fence.SUPERSEDED_BY[k] for k in dead} == dict.fromkeys(dead, "alpha_evolution")
    _seats(fence, monkeypatch, {"alpha_evolution": 900, "other": 1000,
                                **dict.fromkeys(dead, 0)})
    doc = fence.audit()
    rows = {r["producer"]: r for r in doc["producers"]}
    assert all(rows[k]["verdict"] == "SUPERSEDED" for k in dead)
    assert not doc["superseded_successor_not_alive"]
    assert not any(r["producer"] in dead for r in doc["dead_without_a_declared_replacement"])
    # The successor goes stale: every one of the five is DEAD again, and fatally so.
    _seats(fence, monkeypatch, {"alpha_evolution": 0, "other": 1000, **dict.fromkeys(dead, 0)})
    doc = fence.audit()
    rows = {r["producer"]: r for r in doc["producers"]}
    assert all(rows[k]["verdict"] == "DEAD" for k in dead)
    assert {r["producer"] for r in doc["superseded_successor_not_alive"]} == set(dead)


def test_alpha_rl_is_set_aside_until_it_emits_a_cell(fence: Any, tmp_path: Path) -> None:
    import sqlite3
    (tmp_path / "census.json").write_text(json.dumps({"producers": [
        {"producer": "alpha_rl_run", "key": "alpha_rl_run", "compute_hours": 0.5,
         "compute_hours_ledger": 0.5, "compute_hours_registry": 0.0}]}))

    def registry(gen: str) -> None:
        (tmp_path / "reg.sqlite").unlink(missing_ok=True)
        con = sqlite3.connect(tmp_path / "reg.sqlite")
        con.execute("create table research_candidates (created_at text, generator text, "
                    "grid_cell text, content_hash text, family text, symbol text, horizon "
                    "text, donated_cell text, status text, discovery_id text)")
        con.execute("create table discoveries (discovery_id text, generator text)")
        con.execute("insert into research_candidates values (?,?,?,?,?,?,?,?,?,?)",
                    ("2999-01-01T00:00:00+00:00", gen, "g1", "h", "f", "EURUSD", "h1", None,
                     "judged", None))
        con.commit()
        con.close()
    registry("other")
    doc = fence.yield_audit(window_hours=24.0)
    assert doc["n_owing"] == 0 and doc["declared"][0]["declared"]["kind"] == "SET_ASIDE"
    assert doc["set_aside_lifted_now"] == []
    registry("alpha_rl_run")
    doc = fence.yield_audit(window_hours=24.0)
    assert doc["set_aside_lifted_now"] == ["alpha_rl_run"]
    rat = fence.tighten_ratchet(doc)
    assert rat is not None and "alpha_rl_run" in rat["set_aside_lifted"]
    (tmp_path / "ratchet.json").write_text(json.dumps(rat))
    # The lift is permanent: back to zero cells, it now OWES like any producer.
    registry("other")
    doc = fence.yield_audit(window_hours=24.0)
    assert [r["producer"] for r in doc["owing"]] == ["alpha_rl_run"]


def test_learned_miners_contract_has_a_seven_day_max_age_in_producer_health() -> None:
    from research import mission_control as mc
    path, max_age_h = mc.INPUTS["learned_miners"]
    assert path.name == "learned_miners_contract.json" and max_age_h == 7 * 24.0
