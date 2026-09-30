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


class _Donor:
    """Records every donation the way the intake door would accept it."""

    def __init__(self, accept: bool = True) -> None:
        self.calls: list[tuple[list[dict], int]] = []
        self.accept = accept

    def __call__(self, cands, tests_run):
        self.calls.append((list(cands), int(tests_run)))
        if not self.accept:
            return None, {"refused_unstamped": len(cands)}
        return "intel/world_cells/discoveries_x.json", {"donated": len(cands)}


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
    donor = _Donor()
    monkeypatch.setattr(wc, "gate_bases", lambda: ["base_a", "base_b"])
    doc = wc.produce(now=NOW, door=(door.enqueue, door.record), paths={**p, "packs": False},
                     donor=donor)
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
    doc2 = wc.produce(now=NOW, door=(door.enqueue, door.record), paths={**p, "packs": False},
                      donor=donor)
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


# ------------------------------------------------------ audit of PR #123: cells reach a judge
def test_every_minted_cell_is_donated_and_charged_once(monkeypatch, tmp_path) -> None:
    """The registry is not the judge's input: every cell minted this pass is donated through the
    intake with tests_run = cells minted, its registry row is `claimed` by this organ, and a
    second pass donates nothing because nothing new was minted."""
    _policy(monkeypatch)
    p = _alt_fixture(tmp_path)
    door, donor = _Door(), _Donor()
    monkeypatch.setattr(wc, "gate_bases", lambda: ["base_a", "base_b"])
    doc = wc.produce(now=NOW, door=(door.enqueue, door.record), paths={**p, "packs": False},
                     donor=donor)
    (cands, tests_run), = donor.calls
    assert tests_run == len(cands) == 36 + 24
    d = doc["cells"]["donation"]
    assert d["status"] == "DONATED" and d["tests_run"] == 60 and d["donated"] == 60
    for v in door.cells.values():
        assert v["status"] == "claimed" and v["claimed_by"] == "world_cells"
    for c in cands:
        assert c["falsifier"] and c["family"] in {"exogenous_conditioner", "exogenous_gate"}
        assert c["source_culture"] == "BR"
        # the minted chart rides in params.timeframe, H1 by absence
        assert c["params"].get("timeframe", "H1") == c["chart"]
    wc.produce(now=NOW, door=(door.enqueue, door.record), paths={**p, "packs": False},
               donor=donor)
    assert len(donor.calls) == 1, "nothing new was minted, so nothing is donated or charged again"


def test_a_refused_donation_is_re_offered_next_pass_never_lost(monkeypatch, tmp_path) -> None:
    _policy(monkeypatch)
    p = _alt_fixture(tmp_path)
    door = _Door()
    monkeypatch.setattr(wc, "gate_bases", lambda: ["base_a"])
    doc = wc.produce(now=NOW, door=(door.enqueue, door.record), paths={**p, "packs": False},
                     donor=_Donor(accept=False))
    assert doc["cells"]["donation"]["status"] == "REFUSED"
    assert json.loads(p["cursor"].read_text())["minted"] == []
    ok = _Donor()
    doc2 = wc.produce(now=NOW, door=(door.enqueue, door.record), paths={**p, "packs": False},
                      donor=ok)
    assert doc2["cells"]["donation"]["status"] == "DONATED"
    assert ok.calls and ok.calls[0][1] == doc["cells"]["donation"]["tests_run"]


def test_world_state_inputs_names_its_consumer_and_never_claims_wiring(monkeypatch,
                                                                       tmp_path) -> None:
    _policy(monkeypatch)
    p = _alt_fixture(tmp_path)
    monkeypatch.setattr(wc, "gate_bases", lambda: [])
    wc.produce(now=NOW, door=(_Door().enqueue, _Door().record), paths={**p, "packs": False},
               donor=_Donor())
    state = json.loads(p["state"].read_text())
    assert state["consumer"].startswith("PENDING_PATCH ") and state["wired"] is False


def test_a_world_cell_reaches_the_docket_end_to_end(monkeypatch, tmp_path) -> None:
    """world_cells -> the intake donation (the REAL proposer_common door) -> the REAL
    miner_candidate_compiler main -> the docket input `merge_hypotheses` reads
    (miner_candidates.json `hypotheses`)."""
    import libs.ops.repair_invoke as ri
    import libs.research.hypothesis_graph as hg
    from libs.research import preregistration as pr
    from research import miner_candidate_compiler as mcc
    from research import proposer_common as pc
    _policy(monkeypatch)
    p = _alt_fixture(tmp_path)
    intel = tmp_path / "intel"
    monkeypatch.setattr(pc, "INTEL", intel)
    monkeypatch.setattr(pr, "LEDGER", tmp_path / "prereg.jsonl")
    monkeypatch.setattr(pc, "_lane_filtered", lambda c: (c, []))
    monkeypatch.setattr(wc, "gate_bases", lambda: ["range_reversion"])
    door = _Door()
    doc = wc.produce(now=NOW, door=(door.enqueue, door.record), paths={**p, "packs": False})
    don = doc["cells"]["donation"]
    assert don["status"] == "DONATED", don
    contract = json.loads(Path(don["path"]).read_text("utf-8"))
    assert contract["tests_run"] == don["tests_run"] == len(door.cells)
    assert Path(don["path"]).parent == intel / "world_cells"

    class _Graph:
        def prior_failures(self, *_a, **_k):
            return {"n_failed": 0, "region": ""}

        def rows(self):
            return []

    for name, val in (("INTEL_ROOTS", (intel,)), ("OUT", tmp_path / "out.json"),
                      ("DEEPEN", tmp_path / "deepen.json"),
                      ("DEEPEN_WORKED", tmp_path / "deepening_worked.jsonl"),
                      ("DEEPENED", tmp_path / "deepened.json"),
                      ("CURSOR", tmp_path / "cursor_mcc.json")):
        monkeypatch.setattr(mcc, name, val)
    monkeypatch.setattr(mcc, "known_symbols", lambda: {"CORN", "EURUSD"})
    monkeypatch.setattr(mcc, "structurally_untestable_families", dict)
    monkeypatch.setattr(mcc, "expand_axes", lambda rows: rows)
    monkeypatch.setattr(hg, "Graph", _Graph)
    monkeypatch.setattr(hg, "record_candidates", lambda *a, **k: 0)
    monkeypatch.setattr(ri, "request_repair", lambda reason, **kw: False)
    monkeypatch.setattr(mcc, "_lineage", lambda out: None)   # writes data/lineage.sqlite
    assert mcc.main() == 0
    out = json.loads((tmp_path / "out.json").read_text("utf-8"))
    hyps = [h for h in out["hypotheses"] if str(h.get("source")) == "miner:world_cells"]
    fams = {h["family"] for h in hyps}
    assert fams == {"exogenous_conditioner", "exogenous_gate"}, fams
    assert {h["symbol"] for h in hyps} <= {"CORN", "EURUSD"}
    gate = next(h for h in hyps if h["family"] == "exogenous_gate")
    assert gate["params"]["source"] == "alt_power_test"
    assert gate["params"]["base_family"] == "range_reversion"

    # ---- PAST THE DOCKET, THROUGH ADMISSION (audit PR123_v2): every world cell the docket
    # carries is judged and fails (the common case), the gauntlet's OWN ledger writer records
    # it, the ONE lifetime online-FDR stream charges it, and the promotion door reads the
    # verdict for an FX certificate that arrives after them.
    if str(DESK / "scripts") not in sys.path:
        sys.path.insert(0, str(DESK / "scripts"))
    import external_gauntlet as eg

    from libs.tiers import authority, online_fdr
    from libs.tiers import promotion_authority as pa
    from research import tier_s as ts
    monkeypatch.setattr(eg, "GATE_LEDGER", tmp_path / "gate_verdict_ledger.jsonl")
    monkeypatch.setattr(eg, "GATE_INDEX", tmp_path / "gate_verdict_index.json")
    verdicts = [{"cell": f"world.{h['symbol']}.{h['family']}.{i}", "sym": h["symbol"],
                 "family": h["family"], "passed": False, "terminal_gate": "deflated_sharpe"}
                for i, h in enumerate(hyps)]
    eg._append_gate_ledger(verdicts)
    n_gate = sum(1 for h in hyps if h["family"] == "exogenous_gate")
    assert n_gate >= 1
    surv = {"hunt.EURUSD.carry.x": {"gated_at": "2999-01-01T00:00:00",
                                    "shadow_spec": {"family": "carry"},
                                    "gates": {"reality_check_spa": {"p_value": 2e-5}}},
            "hunt.GBPUSD.carry.y": {"gated_at": "2999-01-01T00:00:01",
                                    "shadow_spec": {"family": "carry"},
                                    "gates": {"reality_check_spa": {"p_value": 0.2}}}}
    monkeypatch.setattr(ts, "GATE_LEDGER", eg.GATE_LEDGER)
    monkeypatch.setattr(ts, "HGRAPH", tmp_path / "no_graph.jsonl")
    monkeypatch.setattr(ts, "OUT_DIR", tmp_path / "tier_s")
    monkeypatch.setattr(ts, "survivors", lambda: surv)
    fdr = ts.organ_online_fdr()
    assert fdr["failed_tests_charged"] == len(verdicts), "every world cell is charged"
    assert fdr["n_tests"] == len(verdicts) + 2
    rows = json.loads((tmp_path / "tier_s" / "ONLINE_FDR_ROWS.json").read_text("utf-8"))
    rows["generated_utc"] = datetime.now(UTC).isoformat()
    monkeypatch.setattr(pa, "ROOT", tmp_path)
    monkeypatch.setattr(pa, "FDR_ROWS", tmp_path / "tier_s" / "ONLINE_FDR_ROWS.json")
    pa.FDR_ROWS.write_text(json.dumps(rows), "utf-8")
    monkeypatch.setattr(pa.firewall, "may", lambda *a, **k: True)
    monkeypatch.setattr(authority, "suspended", lambda *a, **k: False)
    assert pa._fdr("EURUSD.carry.x") is None, "the strong FX certificate is admitted"
    held = str(pa._fdr("GBPUSD.carry.y"))
    assert held.startswith("ONLINE_FDR_OVER_BUDGET")
    if hasattr(online_fdr, "replay_budgeted"):
        # exogenous_gate_fdr_budget applied: the gate cells are charged to their own share of
        # the ONE budget and the door quotes the bound its rule actually carries
        assert rows["budgets"]["exogenous_gate"]["n_tests"] == n_gate
        assert rows["fdr_bound"]["fdr_bound"] == online_fdr.fdr_bound()["fdr_bound"]
        assert "FDR bound" in held and "lifetime online-FDR budget was spent" not in held
    else:
        # patch not applied: the gate cells share the pooled stream with FX/metals
        assert "budgets" not in rows
