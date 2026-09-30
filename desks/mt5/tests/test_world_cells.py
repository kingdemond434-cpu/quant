"""World cells: every published world series used direct, indirect and for allocation -- once."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import world_cells as wc  # noqa: E402

NOW = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)
ALT_URL = ("https://power.larc.nasa.gov/api/temporal/daily/point?parameters=T2M_MAX"
           "&start=20100101&end={today}&format=JSON")


def _alt_fixture(tmp_path: Path, *, authority: bool = True) -> dict[str, Path]:
    acq = tmp_path / "acquired"
    acq.mkdir()
    idx = pd.date_range("2025-01-01", periods=400, freq="D")
    rng = np.random.default_rng(3)
    names = {}
    for col in ("T2M_MAX", "PRECTOTCORR"):
        name = f"power_larc_point_{col}"
        pd.DataFrame({"value": rng.normal(20, 5, len(idx))}, index=idx).to_parquet(
            acq / f"{name}.parquet")
        names[name] = {"path": str(acq / f"{name}.parquet"),
                       "url": ALT_URL.replace("{today}", "20260929"),
                       "pit_authority": authority,
                       "pit_blocking": [] if authority else ["selection UNMEASURED"]}
    (tmp_path / "registry.json").write_text(json.dumps({"series": names, "by_url": {}}))
    (tmp_path / "alt.json").write_text(json.dumps({"rows": [
        {"id": "alt_power_test", "class": "satellite", "fetch": True, "keyless": True,
         "machine_use_allowed": True, "url": ALT_URL, "publication_lag_s": 259200,
         "instruments": ["CORN", "EURUSD", "NOT_A_SYMBOL"], "region": "br",
         "participant_structure": "physical_flow", "failure_mode_hypothesis": "farmer hedging"},
        {"id": "alt_blocked", "class": "patents", "fetch": False, "keyless": False,
         "machine_use_allowed": True, "url": "https://x", "blocker": "needs a key",
         "instruments": ["US500"]}]}))
    (tmp_path / "universe.json").write_text(json.dumps({"CORN": {}, "EURUSD": {}, "US500": {}}))
    return {"alt": tmp_path / "alt.json", "acquired": tmp_path / "registry.json",
            "alfred": tmp_path / "alfred", "lake": tmp_path / "lake",
            "cursor": tmp_path / "cursor.json", "report": tmp_path / "WORLD_CELLS.json",
            "state": tmp_path / "STATE.json", "universe": tmp_path / "universe.json"}


class _Door:
    """A registry that records every enqueue and dedups on the same content, like the real one."""

    def __init__(self) -> None:
        self.cells: dict[str, dict] = {}
        self.discoveries: list[dict] = []

    def enqueue(self, *, family, symbol, params, origin, mechanism="", **fields):
        key = json.dumps([family, symbol, params, fields.get("chart")], sort_keys=True)
        new = key not in self.cells
        self.cells.setdefault(key, {"family": family, "symbol": symbol, "params": params,
                                    **fields})
        return key, new

    def record(self, **kw):
        self.discoveries.append(kw)
        return "disc_1", True


def _policy(monkeypatch) -> None:
    import universe_policy
    monkeypatch.setattr(universe_policy, "may_hypothesise",
                        lambda s, family=None: s in {"CORN", "EURUSD"})


def test_alt_series_publish_on_their_own_available_time_clock(tmp_path) -> None:
    p = _alt_fixture(tmp_path)
    pub = wc.publish(alt_path=p["alt"], acquired_path=p["acquired"], alfred_dir=p["alfred"],
                     lake=p["lake"], packs=False)
    by = {r["source"]: r for r in pub}
    assert by["alt_power_test"]["status"] == "PUBLISHED"
    assert set(by["alt_power_test"]["signals"]) == {"power_larc_point_T2M_MAX",
                                                    "power_larc_point_PRECTOTCORR"}
    assert by["alt_power_test"]["source_culture"] == "BR"
    assert by["alt_blocked"]["status"] == "NOT_PUBLISHED"
    assert by["alfred_*"]["reason"].startswith("UNMEASURED")
    frame = pd.read_parquet(p["lake"] / "alt_power_test.parquet")
    lag = pd.to_datetime(frame["available_time"]) - pd.to_datetime(frame["event_time"])
    assert (lag == pd.Timedelta(seconds=259200)).all()
    from mt5desk.family_exogenous_conditioner import conditioner
    cond = conditioner("alt_power_test", "power_larc_point_T2M_MAX", "level_z", root=p["lake"])
    assert cond is not None and len(cond) > 300


def test_a_series_without_pit_authority_is_withheld_not_published(tmp_path) -> None:
    p = _alt_fixture(tmp_path, authority=False)
    pub = wc.publish(alt_path=p["alt"], acquired_path=p["acquired"], alfred_dir=p["alfred"],
                     lake=p["lake"], packs=False)
    row = next(r for r in pub if r["source"] == "alt_power_test")
    assert row["status"] == "NOT_PUBLISHED" and "withheld" in row["reason"]
    assert not (p["lake"] / "alt_power_test.parquet").exists()


def test_alfred_first_prints_and_revisions_skip_the_vintage_record_start() -> None:
    rows = []
    # record starts 2020-01-01 with 3 old observations; later months print once and revise once
    for obs in ("2019-10-01", "2019-11-01", "2019-12-01"):
        rows.append((obs, "2020-01-01", 1.0))
    for i, (obs, rt) in enumerate((("2020-01-01", "2020-02-14"), ("2020-02-01", "2020-03-13"),
                                   ("2020-03-01", "2020-04-15"))):
        rows.append((obs, rt, 10.0 + i))
        rows.append((obs, pd.Timestamp(rt) + pd.Timedelta(days=20), 10.5 + i))
    df = pd.DataFrame(rows, columns=["observation_date", "realtime_date", "value"])
    out = wc.alfred_frame(df, "PAYEMS")
    assert list(out["first_print"]) == [10.0, 11.0, 12.0]
    assert out["available_time"].iloc[0] == pd.Timestamp("2020-02-15", tz="UTC")
    # when Feb printed (03-13) Jan had been revised on 03-05 to 10.5: revision 0.5
    assert out["revision_prior"].iloc[1] == 0.5
    assert np.isnan(out["revision_prior"].iloc[0])


def test_direct_and_gated_cells_are_minted_once_with_culture_on_every_cell(monkeypatch,
                                                                          tmp_path) -> None:
    _policy(monkeypatch)
    p = _alt_fixture(tmp_path)
    door = _Door()
    monkeypatch.setattr(wc, "gate_bases", lambda: ["base_a", "base_b"])
    doc = wc.produce(now=NOW, door=(door.enqueue, door.record), paths={**p, "packs": False})
    c = doc["cells"]
    # 2 signals x 3 transforms x 2 admissible targets x 3 charts
    assert c["direct"]["minted"] == 36 and c["direct"]["created"] == 36
    # 2 signals x 2 bases x 2 targets x 3 bands
    assert c["indirect"]["minted"] == 24
    fams = {v["family"] for v in door.cells.values()}
    assert fams == {"exogenous_conditioner", "exogenous_gate"}
    assert not any(v["symbol"] == "NOT_A_SYMBOL" for v in door.cells.values())
    for v in door.cells.values():
        assert v["source_culture"] == "BR" and v["participant_structure"] == "physical_flow"
        assert v["failure_mode_hypothesis"] == "farmer hedging"
        assert v["generator"] == "world_cells"
    gate = next(v for v in door.cells.values() if v["family"] == "exogenous_gate")
    assert set(gate["params"]) == {"base_family", "base_params", "source", "signal",
                                   "transform", "threshold", "band"}
    # SECOND PASS: nothing is re-enqueued, so the census is never charged twice
    before = len(door.cells)
    doc2 = wc.produce(now=NOW, door=(door.enqueue, door.record), paths={**p, "packs": False})
    assert doc2["cells"]["direct"]["minted"] == 0 and doc2["cells"]["indirect"]["minted"] == 0
    assert doc2["cells"]["direct"]["already"] == 36 and len(door.cells) == before
    state = json.loads(p["state"].read_text())
    assert state["advisory"] is True and "CORN" in state["by_instrument"]
    assert json.loads(p["report"].read_text())["published"] == 1


def test_the_gate_cap_defers_rather_than_drops(monkeypatch, tmp_path) -> None:
    _policy(monkeypatch)
    p = _alt_fixture(tmp_path)
    door = _Door()
    pub = wc.publish(alt_path=p["alt"], acquired_path=p["acquired"], alfred_dir=p["alfred"],
                     lake=p["lake"], packs=False)
    minted: set[str] = set()
    s1 = wc.mint(pub, minted=minted, bases=["a", "b"], gate_cap=10,
                 universe={"CORN", "EURUSD"}, door=(door.enqueue, door.record))
    assert s1["indirect"]["minted"] == 10 and s1["indirect"]["deferred_to_next_pass"] == 14
    s2 = wc.mint(pub, minted=minted, bases=["a", "b"], gate_cap=100,
                 universe={"CORN", "EURUSD"}, door=(door.enqueue, door.record))
    assert s2["indirect"]["minted"] == 14 and s2["indirect"]["already"] == 10


def test_the_gate_family_filters_its_base_and_refuses_without_a_series(monkeypatch,
                                                                       tmp_path) -> None:
    import mt5desk.family_exogenous_gate as g
    from mt5desk.families import Signal
    idx = pd.date_range("2025-01-05", periods=4000, freq="h", tz="UTC")
    rng = np.random.default_rng(0)
    close = 100 + np.cumsum(rng.normal(0, 0.1, len(idx)))
    bars = pd.DataFrame({"open": close, "high": close + 0.2, "low": close - 0.2, "close": close,
                         "volume": 1.0}, index=idx)
    assert g.family_exogenous_gate(bars, base_family="x", source="none", signal="v") == []
    assert not g.gateable("exogenous_gate") and not g.gateable("exit_operated")
    assert g.in_band(1.5, "high", 1.0) and g.in_band(-1.5, "low", 1.0)
    assert g.in_band(0.2, "calm", 1.0) and not g.in_band(float("nan"), "extreme", 1.0)
    # flat, then a high regime from 2025-01-01, then a low one
    lake = tmp_path / "lake"
    lake.mkdir()
    days = pd.date_range("2024-03-07", periods=500, freq="D", tz="UTC")
    vals = np.r_[np.zeros(300), rng.normal(0, 1, 100) + 3.0, rng.normal(0, 1, 100) - 3.0]
    pd.DataFrame({"available_time": days, "v": vals}).to_parquet(lake / "ser.parquet")

    def family_every_bar(df, **_kw):
        return [Signal(time=t, side=1, stop=0.0, target=0.0, ttl_bars=4, tag="t", trigger=None,
                       wait_bars=1) for t in df.index[::10]]
    monkeypatch.setattr(g, "wrappable", lambda name: name == "every_bar")
    monkeypatch.setattr(g, "get_family_func",
                        lambda name: family_every_bar if name == "every_bar" else None)
    base = family_every_bar(bars)
    hi = g.family_exogenous_gate(bars, base_family="every_bar", source="ser", signal="v",
                                 transform="level_z", band="high", threshold=1.0,
                                 series_root=lake)
    calm_all = g.family_exogenous_gate(bars, base_family="every_bar", source="ser", signal="v",
                                       band="calm", threshold=1e9, series_root=lake)
    assert 0 < len(hi) < len(base)
    assert calm_all == []            # the gate removed nothing: the base cell, not a new one


def test_the_gate_family_is_registered_where_every_door_reads() -> None:
    from mt5desk import families_orthogonal as fo
    from research.axis_registry import FAMILY_TABLE
    assert "exogenous_gate" in fo.ORTHOGONAL_FAMILIES and "exogenous_gate" in fo.FAMILY_INPUTS
    assert "exogenous_gate" in FAMILY_TABLE
    src = (DESK / "research" / "orthogonal_sweep.py").read_text("utf-8")
    assert '"exogenous_gate":' in src
