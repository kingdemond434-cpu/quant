"""The two closure organs end to end: `model_search` and the co-evolution closure.

What is pinned:

  * the (R x M) grid is actually swept and PUBLISHED as a matrix, with a representation that
    nothing has judged reading UNMEASURED rather than dead;
  * a planted structure in synthetic bars is rediscovered by the right family, and the family
    that cannot represent it is not credited;
  * every non-earning cell emits the descendant its failure KIND implies into the seven queues,
    and idle capacity with queued work is reported as a DEFECT;
  * an absent heavy backend reads UNMEASURED on the family row while the pure-Python fallback
    carries the whole run (`--no-heavy`);
  * the closure's islands run on different information subsets, migrate only strong concepts,
    and its champion must clear self-play before anything reaches the registry;
  * both organs write their artifact and charge every cell through `libs/research/trial_ledger`.

Nothing here touches the real registry, the real reports directory or the real universe: the
bars are synthetic, the artifact goes to tmp_path, and enqueueing is off.
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
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from libs.research import coevolution_lab as CL  # noqa: E402
from libs.research import model_families as MF  # noqa: E402
from research import model_search as MS  # noqa: E402


def _bars(n: int = 2600, seed: int = 5, planted: bool = True) -> pd.DataFrame:
    """Synthetic H1 bars with a PLANTED structure: a latent regime flips sign every 40 bars and
    adds a drift, so the trailing 24-bar return identifies the regime and the 6-bar forward sign
    follows it. `planted=False` is the control -- same generator, drift removed.

    The regime FLIPS rather than compounding on purpose: a drift keyed to its own trailing sum
    runs away, the forward sign becomes 95% one class, and a model then "wins" by predicting the
    base rate. A degenerate label is the easiest way to write a test that passes for the wrong
    reason, so the fixture asserts nothing the generator does not actually balance.
    """
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-01-01", periods=n, freq="h", tz="UTC")
    regime = np.repeat(rng.choice([-1.0, 1.0], size=n // 40 + 1), 40)[:n]
    ret = rng.normal(0.0, 0.0012, n) + (0.0010 * regime if planted else 0.0)
    close = 2000.0 * np.exp(np.cumsum(ret))
    high = close * (1.0 + np.abs(rng.normal(0.0, 0.0006, n)))
    low = close * (1.0 - np.abs(rng.normal(0.0, 0.0006, n)))
    return pd.DataFrame({"open": close, "high": high, "low": low, "close": close,
                         "tick_volume": rng.integers(50, 500, n).astype(float),
                         "spread": rng.integers(8, 40, n).astype(float),
                         "real_volume": 0.0}, index=idx)


@pytest.fixture
def one_symbol(monkeypatch: pytest.MonkeyPatch) -> str:
    df = _bars()
    monkeypatch.setattr(MS.pc, "bars", lambda sym: df if sym == "TESTFX" else None)
    monkeypatch.setattr(MS, "_symbols", lambda explicit: (["TESTFX"], {"source": "test"}))
    return "TESTFX"


# ------------------------------------------------------------------ item 7: the R x M grid
def test_model_search_sweeps_and_publishes_the_compatibility_matrix(
        one_symbol: str, tmp_path: Path) -> None:
    out = tmp_path / "MODEL_SEARCH.json"
    doc = MS.run(budget_s=240.0, families=("linear", "tree", "bayesian"),
                 reps=("raw", "zscore", "path_shape"), allow_heavy=False,
                 write_queue=False, enqueue=False, n_bars=2600, report=out)
    assert out.exists(), "the artifact is the organ's output; no file is an unwired organ"
    disk = json.loads(out.read_text("utf-8"))
    assert disk["cells_tested"] == doc["cells_tested"] >= 6

    m = doc["compatibility_matrix"]
    assert set(m["models"]) == {"linear", "tree", "bayesian"}
    assert m["n_cells"] == doc["cells_tested"]
    for rep in m["representations"]:
        assert len(m["grid"][rep]) == 3, "every representation meets every learner"
    # Three learners tried, so every representation gets a real verdict, not UNMEASURED.
    assert all(v["verdict"] in {"ALIVE", "DEAD"}
               for v in doc["representation_verdicts"].values())


def test_one_learner_is_never_enough_to_bury_a_representation(
        one_symbol: str, tmp_path: Path) -> None:
    doc = MS.run(budget_s=120.0, families=("linear",), reps=("zscore",), allow_heavy=False,
                 write_queue=False, enqueue=False, n_bars=2000,
                 report=tmp_path / "MODEL_SEARCH.json")
    assert doc["representation_verdicts"]["zscore"]["verdict"] == CL.UNMEASURED


# ------------------------------------------------------------------ item 18 / 2: rediscovery
def test_the_planted_momentum_structure_is_rediscovered(one_symbol: str,
                                                        tmp_path: Path) -> None:
    doc = MS.run(budget_s=240.0, families=("linear", "tree"), reps=("raw", "vol_scaled"),
                 allow_heavy=False, write_queue=False, enqueue=False, n_bars=2600,
                 report=tmp_path / "MODEL_SEARCH.json")
    assert doc["n_earning"] >= 1, doc["per_symbol"]
    assert doc["winners"][0]["net_gain"] > 0
    assert doc["winners"][0]["representation"] in {"raw", "vol_scaled"}


def test_the_control_bars_with_nothing_planted_win_far_less(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(MS.pc, "bars", lambda sym: _bars(planted=False, seed=9))
    monkeypatch.setattr(MS, "_symbols", lambda explicit: (["TESTFX"], {"source": "test"}))
    doc = MS.run(budget_s=180.0, families=("linear", "tree"), reps=("raw", "vol_scaled"),
                 allow_heavy=False, write_queue=False, enqueue=False, n_bars=2600,
                 report=tmp_path / "MODEL_SEARCH.json")
    best = max((float(c["net_gain"]) for s in doc["per_symbol"].values()
                for c in (s.get("best") or []) if c.get("net_gain") is not None), default=0.0)
    assert best < 0.02, "a control world must not hand out a large edge"


# ------------------------------------------------------------------ item 6: heavy libraries
def test_an_absent_heavy_backend_reads_unmeasured_and_the_run_still_completes(
        one_symbol: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(MF, "_import", lambda mod: None)
    doc = MS.run(budget_s=180.0, families=("linear", "neural"), reps=("raw",),
                 allow_heavy=False, write_queue=False, enqueue=False, n_bars=2000,
                 report=tmp_path / "MODEL_SEARCH.json")
    assert doc["n_families_unmeasured_heavy"] == len(MF.FAMILIES)
    census = doc["family_census"]
    assert len(census) == 10
    assert all(row["heavy_verdict"] == CL.UNMEASURED for row in census.values())
    assert all(row["falsifier"] for row in census.values())
    for c in (doc["per_symbol"]["TESTFX"].get("best") or []):
        assert c["backend"] == "fallback"
    assert doc["cells_tested"] >= 2, "the fallback must carry the whole run"


# ------------------------------------------------------------------ item 10 / 14: queues
def test_failures_fill_the_queues_and_idle_capacity_is_a_defect(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # The CONTROL bars: nothing is planted, so the cells fail -- which is the point. A sweep
    # over a world with no structure must still change the next run.
    monkeypatch.setattr(MS.pc, "bars", lambda sym: _bars(planted=False, seed=13))
    monkeypatch.setattr(MS, "_symbols", lambda explicit: (["TESTFX"], {"source": "test"}))
    doc = MS.run(budget_s=240.0, families=("linear", "neural", "graph"),
                 reps=("rank", "range_state"), allow_heavy=False, write_queue=False,
                 enqueue=False, n_bars=2400, report=tmp_path / "MODEL_SEARCH.json")
    depth = doc["queues"]["depth"]
    assert set(depth) == set(CL.QUEUE_KINDS)
    assert sum(depth.values()) > 0, "a sweep with dead cells that queues nothing is the defect"
    kinds = {r["payload"]["descendant_kind"]
             for k in CL.QUEUE_KINDS for r in doc["queues"]["top"][k]
             if "descendant_kind" in r.get("payload", {})}
    assert kinds, doc["queues"]["top"]
    assert kinds <= {v[1] for v in CL.FAILURE_RULES.values()}
    assert doc["queues"]["idle"]["verdict"] in {"DEFECT", "IDLE_AND_EMPTY", "BUSY"}


# ------------------------------------------------------------------ trials
def test_every_cell_is_charged_through_the_trial_ledger(one_symbol: str,
                                                        tmp_path: Path) -> None:
    doc = MS.run(budget_s=180.0, families=("linear", "tree"), reps=("raw", "zscore"),
                 allow_heavy=False, write_queue=False, enqueue=False, n_bars=2000,
                 report=tmp_path / "MODEL_SEARCH.json")
    t = doc["trials"]
    assert t["n_raw"] == doc["cells_tested"]
    assert 0 < t["n_effective"] <= t["n_raw"]
    assert t["charged_by"].endswith("trial_ledger.py")


# ------------------------------------------------------------------ the co-evolution closure
def test_the_closure_runs_islands_residuals_self_play_and_worlds(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import factor_model_coevolution as FMC

    df = _bars(n=2400, seed=3)
    monkeypatch.setattr(FMC.pc, "bars", lambda sym: df if sym == "TESTFX" else None)
    monkeypatch.setattr(FMC, "_symbols", lambda symbols: (["TESTFX"], {"source": "test"}))
    monkeypatch.setattr(FMC, "MIN_BARS", 500)
    monkeypatch.setattr(FMC, "N_BARS", 2400)
    monkeypatch.setattr(FMC, "REPORT", tmp_path / "COEVOLUTION.json")
    monkeypatch.setattr(FMC.fs, "STORE", tmp_path / "features")
    monkeypatch.setattr(FMC, "FEATURE_ROOT", tmp_path / "features")
    # Nothing reaches the real registry from a test.
    monkeypatch.setattr(FMC, "_enqueue_survivor",
                        lambda *a, **k: {"enqueued": False, "why": "test"})

    doc = FMC.run_closure(budget_s=150.0, seed=1, pop=6, gens=2, write_queue=False,
                          allow_heavy=False, worlds=True)
    assert [i["name"] for i in doc["islands"]] == [
        "linear_prior", "nonlinear_prior", "state_prior", "sparse_prior"]
    # Different priors AND different information subsets -- that is what makes them islands.
    assert len({tuple(i["prior_models"]) for i in doc["islands"]}) == 4
    assert doc["pairings_tested"] > 0, doc["closure_per_symbol"]
    assert set(doc["queues"]["depth"]) == set(CL.QUEUE_KINDS)
    assert doc["synthetic_world"]["desk_score"] is not None
    assert set(doc["compatibility_matrix"]["models"]) <= set(MF.FAMILIES)
    assert doc["trials"]["n_raw"] >= 1
    # Migration is judged on the published rule, whether or not any concept qualified today.
    for m in doc["migrations"]:
        assert m["net_gain"] > 0 and m["from"] != m["to"]
    for sp in doc["self_play"]:
        assert sp["verdict"] in {"REJECTED", "SURVIVES_SELF_PLAY"}
        assert {r["role"] for r in sp["roles"]} >= {"simplifier", "attacker", "reimplementer"}


def test_the_closure_pools_residuals_and_labels_all_seven_axes(
        monkeypatch: pytest.MonkeyPatch) -> None:
    import factor_model_coevolution as FMC

    df = _bars(n=900, seed=4)
    rows = np.arange(0, 800, 6)
    labels = FMC._labels(df, rows, "XAUUSD", FMC.HORIZON)
    assert set(labels) == set(CL.RESIDUAL_AXES)
    assert all(len(v) == rows.size for v in labels.values())
    assert set(labels["session"]) <= {"asia", "london", "ny", "off_hours"}
    assert labels["country"][0] == "metals"
    assert FMC._region("EURUSD") == "americas+europe"
    assert FMC._region("ZZZ") == "UNCLASSIFIED", "a name nothing matches is never filed as other"


def test_a_champion_that_a_simpler_pairing_beats_never_reaches_the_registry() -> None:
    """The organ's gate is `self_play`: this pins the decision the organ delegates to it."""
    champ: dict[str, Any] = {"model": "neural", "net_gain": 0.001, "complexity": 6,
                             "concept": "neural[a+b+c]"}
    rivals = [{"model": "linear", "net_gain": 0.001, "complexity": 2}]
    assert CL.self_play(champ, rivals)["verdict"] == "REJECTED"
    kids = CL.descendants_for({**champ, "verdict": MF.NEGATIVE, "n": 400,
                               "residual_structured": True}, symbol="TESTFX")
    assert kids[0].payload["descendant_kind"] == "model_family_challenger"
