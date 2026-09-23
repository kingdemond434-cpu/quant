"""The sandbox runner over a throwaway desk: cells run in-process on point-in-time bars, an
absent library is UNMEASURED with an install task, TEXT_ONLY gets a REBUILT task, packets become
registry candidates with provenance and charged trials, the artifact and the federation_ops
readers see the runs, and the conformal cell's calibration reaches the dislocation lab
two-sided. Nothing here touches a tracked file."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research.sandboxes import conformal_calibration as CC  # noqa: E402
from research.sandboxes import edgar_transmission as ED  # noqa: E402
from research.sandboxes import rl_execution_challenger as RL  # noqa: E402

from libs.moat import registry as R  # noqa: E402
from libs.research import adapters as A  # noqa: E402
from libs.research import sandbox as SB  # noqa: E402
from research import sandbox_runner as SR  # noqa: E402
from research import sandboxes as CELLS  # noqa: E402

SYMBOLS = {"EURUSD": ("Forex", 0.00001, 100000.0, 12.0, 1.1),
           "XAUUSD": ("Commodities", 0.01, 100.0, 14.5, 4300.0),
           "US500": ("Indices", 0.1, 1.0, 6.0, 6500.0),
           "Apple": ("Equities", 0.01, 1.0, 3.0, 230.0)}


def _parquet(folder: Path, symbol: str, px: float, n: int = 900,
             end: datetime | None = None) -> None:
    rng = np.random.default_rng(abs(hash(symbol)) % 1000)
    end = end or (datetime.now(tz=UTC).replace(minute=0, second=0, microsecond=0)
                  - timedelta(hours=3))
    idx = pd.date_range(end=end, periods=n, freq="h", tz="UTC", name="time")
    r = rng.normal(0.0, 0.003, n) + 0.0005 * np.sin(np.arange(n) / 29.0)
    close = px * np.exp(np.cumsum(r))
    df = pd.DataFrame({"open": np.roll(close, 1), "high": close * 1.002, "low": close * 0.998,
                       "close": close, "tick_volume": rng.integers(100, 1000, n).astype("uint64"),
                       "spread": np.full(n, 3, dtype="int32"),
                       "real_volume": np.zeros(n, dtype="uint64")}, index=idx)
    df.to_parquet(folder / f"{symbol}_H1.parquet")


@pytest.fixture
def desk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    d = tmp_path / "desk"
    (d / "data" / "universe").mkdir(parents=True)
    (d / "reports").mkdir()
    for sym, spec in SYMBOLS.items():
        _parquet(d / "data" / "universe", sym, spec[4])
    reg = {sym: {"asset_class": klass, "tick_size": tick, "contract_size": size,
                 "median_spread_pts": spread} for sym, (klass, tick, size, spread, _) in
           SYMBOLS.items()}
    (d / "data" / "universe" / "universe.json").write_text(json.dumps(reg), encoding="utf-8")
    monkeypatch.setattr(R, "BACKUP", tmp_path / "no_backup")
    R.set_path(tmp_path / "alpha_registry.sqlite")
    monkeypatch.setattr(SR, "DESK", d)
    monkeypatch.setattr(SR, "TRIALS", d / "data" / "sandbox_trials.jsonl")
    monkeypatch.setattr(SB, "SANDBOX_ROOT", tmp_path / "sandbox")
    return {"desk": d, "root": tmp_path / "sandbox", "universe": d / "data" / "universe",
            "registry": d / "data" / "universe" / "universe.json",
            "fed": d / "data" / "external_federation.json",
            "state": d / "data" / "sandbox_runner_state.json",
            "report": d / "reports" / "SANDBOX_RUNNER.json",
            "processed": d / "data" / "external_packets" / "processed"}


def _pass(paths: dict[str, Path], budget_s: float = 90.0, **kw: Any) -> dict[str, Any]:
    return SR.run_pass(budget_s=budget_s, allow_fetch=False, root=paths["root"],
                       universe_dir=paths["universe"], registry_path=paths["registry"],
                       fed_state_path=paths["fed"], state_path=paths["state"],
                       report_path=paths["report"], processed=paths["processed"], **kw)


def test_the_bundle_is_closed_hypothesis_lane_bars_only(desk: dict[str, Path]) -> None:
    now_hour = datetime.now(tz=UTC).replace(minute=0, second=0, microsecond=0)
    _parquet(desk["universe"], "XAUUSD", 4300.0, n=900, end=now_hour)  # last bar still forming
    b = SR.build_bundle(universe_dir=desk["universe"], registry_path=desk["registry"],
                        n_bars=700, seed=1, budget_s=30)
    assert set(b.universe) == {"EURUSD", "XAUUSD", "US500"}, "equities never enter"
    gold = b.frame("XAUUSD")
    assert gold is not None and len(gold) == 700
    assert datetime.fromisoformat(gold.time[-1]) < now_hour
    assert b.costs["XAUUSD"].pooled_median_spread_pts == 14.5 and b.read_only
    assert SR.bars_cap(None) == 600 and SR.bars_cap(50.0) == 600 and SR.bars_cap(10_000.0) == 4000


def test_a_pass_runs_cells_names_unmeasured_libraries_and_writes_the_artifact(
        desk: dict[str, Path]) -> None:
    doc = _pass(desk, only=["ruptures", "bridgewater_pat_aia", "path_signature_lab",
                            "conformal_calibration", "coevolution_cell",
                            "rl_execution_challenger", "edgar_transmission"])
    by_id = {r["system_id"]: r for r in doc["systems_tried"]}
    rup = by_id["ruptures"]
    assert rup["run_status"] == "UNMEASURED" and rup["task"]["kind"] == "install"
    assert rup["task"]["requirement"] == "ruptures==1.0.6"
    assert any(t["requirement"] == "ruptures==1.0.6" for t in doc["install_tasks"])
    pat = by_id["bridgewater_pat_aia"]
    assert pat["run_status"] == "TEXT_ONLY" and pat["task"]["kind"] == "rebuilt"
    assert "bridgewater_pat_aia" in doc["text_only"] and doc["rebuilt_tasks"]
    for cell in ("path_signature_lab", "conformal_calibration", "coevolution_cell",
                 "rl_execution_challenger"):
        row = by_id[f"cell:{cell}"]
        assert row["run_status"] == "PRODUCED", (cell, row["why_unmeasured"], row["why"])
        assert row["licence"].startswith("desk") and row["disposition"] == "REBUILT"
        assert row["version"].startswith("desk:")
    edgar = by_id["cell:edgar_transmission"]
    assert edgar["run_status"] == "UNMEASURED" and "no cached filings" in edgar["why_unmeasured"]
    assert doc["counts"]["ran"] == 6 and doc["counts"]["produced"] >= 4
    assert doc["effective_trials"]["n_raw"] >= 0
    assert set(doc["roi"]) >= {"cell:coevolution_cell", "cell:path_signature_lab"}
    assert desk["report"].exists() and desk["state"].exists()
    assert (desk["desk"] / "reports" / CC.CALIBRATION_FILE).exists()
    assert len(list(desk["processed"].glob("*.json"))) == 6
    folder = desk["root"] / "cell_coevolution_cell"
    assert (folder / "sandbox.json").exists() and list((folder / "out").glob("*.json"))
    from research import federation_ops as fo
    seen = fo.sandbox_records()
    assert seen["cell_coevolution_cell"]["runs"], "federation_ops reads the runner's output"
    assert any(r["system_id"] == "cell:coevolution_cell" for r in fo.run_records([], seen))


def test_ingest_enqueues_candidates_with_provenance_and_charges_trials(
        desk: dict[str, Path]) -> None:
    bundle = A.synthetic_bundle(seed=1, n=400)
    pkt = A.packet("cell:test", bundle, trials=40, candidates=[A.candidate(
        "trend_ma_cross", ["EURUSD"], "a planted hypothesis", horizon="24h",
        evidence={"parameters": {"fast": 5, "slow": 20}, "objective_return": 0.01},
        source="cell:test")], representations=[{"kind": "path_signature", "symbol": "EURUSD"}])
    plan = SR.Plan("cell:test", "cell", "RUNNABLE", "REBUILT", "desk (own code)", "desk:abc", "")
    conn = R.connect()
    try:
        first = SR.ingest(pkt, plan, compute_s=1.5, conn=conn, apply=True)
        assert first["created"] == 1 and first["existing"] == 0 and first["discoveries"] == 1
        assert first["trials"][0].declared_width == 40 and first["trials"][0].family == \
            "trend_ma_cross"
        again = SR.ingest(pkt, plan, compute_s=1.5, conn=conn, apply=True)
        assert again["existing"] == 1 and again["created"] == 0
        row = conn.execute("SELECT origin, generator, lineage_json, params_json, trial_family "
                           "FROM research_candidates").fetchone()
        assert row["origin"] == "EXTERNAL" and row["generator"] == "sandbox:cell:test"
        lineage = json.loads(row["lineage_json"])
        assert lineage["disposition"] == "REBUILT" and lineage["licence"] == "desk (own code)"
        assert lineage["run_id"] == pkt.run_id and lineage["trials_charged"] == 40
        assert json.loads(row["params_json"]) == {"fast": 5, "slow": 20}
        assert row["trial_family"] == "ext:cell:test:trend_ma_cross"
    finally:
        conn.close()
    census = SR.charge_trials(first["trials"], apply=True)
    assert census["n_raw"] == 1 and census["n_effective"] >= 40
    assert SR.TRIALS.exists()


def test_text_only_is_never_a_resting_state_and_verdicts_are_refused() -> None:
    bundle = A.synthetic_bundle(seed=2, n=300)
    text = A.packet("x", bundle, trials=0, research_methods=[{"kind": "REBUILT_ROUTE"}])
    assert SR.is_text_only(text)
    assert not SR.is_text_only(A.unmeasured("x", bundle, "absent"))
    assert not SR.is_text_only(A.packet("x", bundle, trials=1, representations=[{"kind": "r"}]))
    with pytest.raises(ValueError, match="verdict-shaped"):
        A.packet("x", bundle, trials=1, candidates=[{"kind": "hypothesis", "survivor": True}])


def test_a_dry_run_writes_nothing(desk: dict[str, Path]) -> None:
    doc = _pass(desk, dry_run=True, only=["path_signature_lab", "ruptures"])
    assert doc["dry_run"] and doc["counts"]["ran"] == 1
    assert not desk["report"].exists() and not desk["state"].exists()
    assert not desk["processed"].exists() and not (desk["desk"] / "reports"
                                                    / CC.CALIBRATION_FILE).exists()


def test_the_conformal_cell_feeds_the_dislocation_lab_two_sided(desk: dict[str, Path]) -> None:
    from research import dislocation_lab as DL
    bundle = A.synthetic_bundle(seed=4, n=900, symbols=("EURUSD", "XAUUSD"), budget_s=30)
    ctx = CELLS.CellContext(desk["desk"], budget_s=30, seed=4)
    pkt = CELLS.run_cell("conformal_calibration", bundle, ctx)
    rows = [r for r in pkt.representations if r["kind"] == "conformal_interval"]
    assert rows and pkt.trials_charged == len(rows)
    assert all(0.0 <= float(r["coverage_measured"]) <= 1.0 for r in rows)
    paths = DL.Paths(desk["desk"])
    now = datetime.now(tz=UTC)
    got = DL._conformal_gap(paths, "EURUSD", "24h", now)
    assert got["status"] == DL.MEASURED and got["gap"] is not None and got["n_test"] >= 50
    assert DL._conformal_gap(paths, "USDJPY", "24h", now)["status"] == DL.UNMEASURED
    stale = DL._conformal_gap(paths, "EURUSD", "24h", now + timedelta(hours=72))
    assert stale["status"] == DL.UNMEASURED and "older" in stale["why"]
    assert DL._blend_uncertainty(0.10, None) is None
    assert DL._blend_uncertainty(None, 0.05) == 0.05
    tight, wide = DL._blend_uncertainty(0.10, 0.02), DL._blend_uncertainty(0.10, 0.30)
    assert tight is not None and wide is not None and tight < 0.10 < wide
    assert DL._conformal_direction(0.10, tight) == "tightened"
    assert DL._conformal_direction(0.10, wide) == "widened"
    assert DL._conformal_direction(0.10, None) == DL.UNMEASURED


def test_the_edgar_cell_is_event_lane_only_and_never_fetches_unasked(
        desk: dict[str, Path]) -> None:
    bundle = A.synthetic_bundle(seed=5, n=400, symbols=("US500", "XAUUSD", "Apple"))
    ctx = CELLS.CellContext(desk["desk"], budget_s=10, seed=5, network_allowed=False)
    empty = ED.run(bundle, ctx)
    why = empty.research_methods[0]
    assert why["kind"] == "UNMEASURED" and why["task"]["kind"] == "fetch"
    assert "UNENFORCED_ON_THIS_HOST" in why["network"] and not why["fetch"]["attempted"]
    cache = desk["desk"] / "data" / ED.CACHE_DIR
    cache.mkdir(parents=True)
    hits = []
    for day in range(1, 29):
        n = 30 if day in (7, 21) else 3
        hits += [{"form": "8-K", "filed": f"2026-08-{day:02d}", "items": ["2.02", "9.01"],
                  "sic": "3571"} for _ in range(n)]
        hits += [{"form": "10-Q", "filed": f"2026-08-{day:02d}", "items": []}
                 for _ in range(20 if day == 14 else 2)]
    (cache / "fulltext_test.json").write_text(json.dumps({"hits": hits}), encoding="utf-8")
    pkt = ED.run(bundle, ctx)
    assert pkt.datasets[0]["kind"] == "edgar_cache_census" and pkt.datasets[0]["hits"] == len(hits)
    bursts = {r["form"]: r for r in pkt.representations}
    assert bursts["8-K:2.02"]["bursts"] == ["2026-08-07", "2026-08-21"]
    assert pkt.candidates, "burst days yield event hypotheses on transmission instruments"
    for c in pkt.candidates:
        assert set(c["symbols"]) <= {"US500", "XAUUSD"}, "a single name never leaves"
        assert c["family"] in ("overnight_drift", "volume_spike", "volatility_squeeze")
        assert c["evidence"]["lane"] == "EVENT"
    assert "Apple" not in json.dumps(A.to_dict(pkt))


def test_the_rl_execution_challenger_is_a_challenger_only(desk: dict[str, Path]) -> None:
    bundle = A.synthetic_bundle(seed=6, n=300, symbols=("XAUUSD",))
    ctx = CELLS.CellContext(desk["desk"], budget_s=10, seed=6)
    none = RL.run(bundle, ctx)
    kinds = [r["kind"] for r in none.research_methods]
    assert kinds[0] == "UNMEASURED" and "qubo_slicing_challenger" in kinds
    rng = np.random.default_rng(0)
    rows = []
    for i in range(40):
        filled = bool(rng.random() < 0.8)
        rows.append({"symbol": "XAUUSD", "session": ("asia", "london", "ny")[i % 3],
                     "order_type": ("market", "pending_stop", "pending_limit")[i % 3],
                     "spread_frac": float(rng.uniform(1e-5, 5e-5)),
                     "vol_frac": float(rng.uniform(1e-4, 8e-4)), "filled": filled,
                     "actual_slip_frac": float(rng.uniform(0, 3e-5)) if filled else None,
                     "rejected": False})
    (desk["desk"] / "data" / RL.CASES).write_text("\n".join(json.dumps(r) for r in rows) + "\n",
                                                  encoding="utf-8")
    pkt = RL.run(bundle, ctx)
    rl = next(r for r in pkt.research_methods if r["kind"] == "execution_challenger")
    assert rl["status"] == "MEASURED" and rl["policy"] and rl["n_cases"] == 40
    assert "never live" in rl["authority"]
    for state, p in rl["policy"].items():
        assert p["action"] in RL.ACTIONS and p["n_cases"] >= 1 and "|" in state
    qubo = next(r for r in pkt.research_methods if r["kind"] == "qubo_slicing_challenger")
    assert abs(qubo["filled_share"] - 1.0) < 0.2 and len(qubo["schedule"]) == RL.SLICES
    assert pkt.trials_charged >= RL.EPISODES


def test_signature_and_coevolution_cells_donate_representations_and_lineage() -> None:
    bundle = A.synthetic_bundle(seed=7, n=900, symbols=("EURUSD", "XAUUSD", "USDJPY"),
                                budget_s=60)
    ctx = CELLS.CellContext(Path("."), budget_s=60, seed=7, dry_run=True)
    sig = CELLS.run_cell("path_signature_lab", bundle, ctx)
    rep = next(r for r in sig.representations if r["kind"] == "path_signature")
    assert rep["depth"] == 3 and len(rep["levy_area_last"]) == 3 and sig.trials_charged > 8
    for c in sig.candidates:
        assert c["family"] in A.FAMILIES and c["source"] == "cell:path_signature_lab"
    co = CELLS.run_cell("coevolution_cell", bundle, ctx)
    runs = [r for r in co.representations if r["kind"] == "coevolution_landscape"]
    assert runs and co.trials_charged >= sum(r["pairings"] for r in runs)
    assert all("best_factors" in r and "positive_pairings" in r for r in runs)
    for c in co.candidates:
        assert c["evidence"]["lineage"]["cell"] == "coevolution_cell"
        assert "generation" in c["evidence"]["lineage"] and c["family"] in A.FAMILIES
    assert co.commit.startswith("desk:") and sig.commit == co.commit
    d = CELLS.describe(CELLS.load_cell("coevolution_cell"))
    assert d["name"] == "cell:coevolution_cell" and d["capability_family"] == \
        "factor_model_coevolution" and d["licence"].startswith("desk")


def test_a_cell_that_raises_leaves_an_unmeasured_packet(monkeypatch: pytest.MonkeyPatch) -> None:
    bundle = A.synthetic_bundle(seed=8, n=300)
    mod = CELLS.load_cell("path_signature_lab")

    def boom(bundle: object, ctx: object) -> None:
        raise RuntimeError("planted")
    monkeypatch.setattr(mod, "run", boom)
    pkt = CELLS.run_cell("path_signature_lab", bundle, CELLS.CellContext(Path(".")))
    assert A.is_unmeasured(pkt) and "planted" in pkt.research_methods[0]["why"]
    with pytest.raises(KeyError):
        CELLS.load_cell("not_a_cell")
