"""The organ: parallel scientists over a synthetic panel on a temporary registry, one failing
scientist never stops the lab, a dry run writes nothing, donations are idempotent by object id,
and the compute allocation is two-sided above a floor no tradition falls through.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pytest

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK / "research"), str(DESK), str(DESK.parents[1])):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research.mathlab import grammar as G  # noqa: E402
from research.mathlab import scientists as S  # noqa: E402
from research.mathlab.base import Scientist  # noqa: E402
from research.mathlab.objects import Panel, Variable  # noqa: E402

from research import math_lab as ML  # noqa: E402

N = 2600
FAST = ("spectral", "control_theory", "stochastic_processes", "meta_mathematics",
        "wavelet_scattering")


def _panel(target: str, seed: int) -> Panel:
    rng = np.random.default_rng(seed)
    ret = 0.0008 * np.sin(2 * np.pi * np.arange(N) / 24) + 0.0006 * rng.normal(0, 1, N)
    close = 100.0 * np.exp(np.cumsum(ret))
    columns = {"close": close, "open": close, "high": close * 1.0004, "low": close * 0.9996,
               "ret": ret, "range": np.abs(ret) * 2 + 1e-6, "body": ret,
               "activity": 100 + 8 * np.abs(rng.normal(0, 1, N)), "spread": np.full(N, 1e-4),
               "atr": np.abs(ret) * 3 + 1e-6, "vol": 0.001 + 0.0002 * np.abs(rng.normal(0, 1, N)),
               "flow": rng.normal(0, 1, N)}
    signal = G.evaluate(["z", ["sub", ["rmean", "close", 5], ["rmean", "close", 24]], 240],
                        columns, N)
    epsilon = 0.4 * np.nan_to_num(signal) + rng.normal(0, 1, N)
    regime = np.asarray(["low", "mid", "high"])[(np.arange(N) // 40) % 3]
    return Panel(target=target, times=np.arange(N, dtype=np.int64) * 3600 + 1_600_000_000,
                 epsilon=epsilon, columns=columns,
                 meta={k: Variable(k, f"bars:{target}", "bars") for k in columns},
                 regime=regime, session=np.asarray(["ny"] * N), horizon="4",
                 source="test_store", residual_discovery_id=f"disc_{target}")


class Broken(Scientist):
    tradition = "broken"

    def _propose(self, panel: Panel, deadline: float, rng: np.random.Generator) -> list[Any]:
        raise RuntimeError("this tradition explodes on purpose")


@pytest.fixture
def lab(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from libs.moat import registry as R
    monkeypatch.setattr(R, "BACKUP", tmp_path / "no_backup", raising=False)
    R.set_path(tmp_path / "alpha_registry.sqlite")
    monkeypatch.setattr(ML, "OUT", tmp_path / "reports" / "MATH_LAB.json")
    monkeypatch.setattr(ML, "ALLOCATION", tmp_path / "data" / "math_allocation.json")
    monkeypatch.setattr(ML, "DONATED", tmp_path / "data" / "mathlab_donated.json")
    monkeypatch.setattr(ML, "MATHLAB_REPRESENTATIONS", tmp_path / "data" / "representations")
    panels = [_panel("EURUSD", 1), _panel("GBPUSD", 2)]
    monkeypatch.setattr(ML, "build_panels", lambda max_targets=4: (
        panels, {"unmeasured": ["datasets: none in this test"], "targets": ["EURUSD", "GBPUSD"],
                 "panel_sources": {"EURUSD": "test_store", "GBPUSD": "test_store"}}))
    monkeypatch.setitem(S.REGISTRY, "broken", Broken)
    monkeypatch.setattr(S, "TRADITIONS", (*S.TRADITIONS, "broken"))
    donated: list[dict[str, Any]] = []

    from research import proposer_common as PC

    def fake_donate(source: str, candidates: list[dict], tests_run: int) -> Path:
        path = tmp_path / "intel" / source / "discoveries_test.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"discoveries": candidates, "tests_run": tests_run},
                                   default=str), "utf-8")
        donated.extend(candidates)
        return path

    monkeypatch.setattr(PC, "donate", fake_donate)
    monkeypatch.setattr(PC, "donation_counts", lambda: {"donated": len(donated)})
    yield {"tmp": tmp_path, "donated": donated, "registry": R}
    R.set_path(None)


def test_parallel_scientists_run_and_one_failure_never_stops_the_lab(lab):
    report = ML.run(budget_s=40.0, traditions=[*FAST, "broken"], permutations=30)
    per = report["per_tradition"]
    assert per["broken"]["status"] == "FAILED" and "explodes" in per["broken"]["why"]
    healthy = [t for t in FAST if per[t]["status"] == "OK"]
    assert len(healthy) == len(FAST), {t: per[t].get("why") for t in FAST}
    assert report["memory"]["workers"] >= 1
    assert report["objects"]["admitted"] > 0
    assert sum(per[t]["proposed"] for t in FAST) == sum(
        per[t]["objects_admitted"] for t in FAST) + report["objects"]["simplified_away_duplicates"]
    assert all(per[t]["effective_trials"] >= 1 for t in FAST)
    assert report["allocates_capital"] is False
    assert ML.OUT.exists()
    written = json.loads(ML.OUT.read_text("utf-8"))
    assert written["per_tradition"]["broken"]["status"] == "FAILED"


def test_objects_reach_the_registry_the_ledger_and_the_compiler(lab):
    report = ML.run(budget_s=40.0, traditions=list(FAST), permutations=30)
    R = lab["registry"]
    rows = R.discoveries(limit=500)
    # `discoveries` has no `kind` column: the registry kind rides in the payload, and the
    # generator column carries `math:<tradition>`.
    kinds = {str(json.loads(str(r.get("payload_json") or "{}")).get("registry_kind"))
             for r in rows}
    assert kinds & {"math_relationship", "math_representation", "math_mechanism", "math_law",
                    "math_search_method"}, kinds
    generators = {str(r.get("generator")) for r in rows}
    assert all(g.startswith("math:") for g in generators)
    yields = {str(r["generator"]): r for r in R.generator_yields()}
    assert all(f"math:{t}" in yields for t in FAST)
    assert all(float(yields[f"math:{t}"]["compute_s"]) > 0 for t in FAST)
    ok, n = R.verify_trial_chain()
    assert ok and n == len(FAST)
    assert report["registry"]["discoveries"] == report["objects"]["admitted"]
    assert report["registry"]["links"] > 0, "provenance to the residual target was not linked"
    if report["objects"]["passed_burden"]:
        rows = lab["donated"]
        assert rows, report["donation"]
        for row in rows:
            assert row["family"] == "formula" and row["kind"] == "hypothesis"
            assert row["symbol"] in ("EURUSD", "GBPUSD")
            params = row["params"]
            assert {"expr", "norm", "entry_z", "side_mode", "hold_bars"} <= set(params)
            from libs.research.alpha_grammar import is_valid
            assert is_valid(params["expr"], allow_drivers=False)
            assert "entry_rule" in row["evidence"] and "exit_rule" in row["evidence"]
            assert row["evidence"]["tradition"] in FAST
        assert report["representations"]["minted"] >= 0


def test_dry_run_writes_nothing(lab):
    report = ML.run(budget_s=25.0, traditions=list(FAST), dry_run=True, permutations=20)
    assert report["dry_run"] is True
    assert not ML.OUT.exists() and not ML.ALLOCATION.exists() and not ML.DONATED.exists()
    assert not ML.MATHLAB_REPRESENTATIONS.exists()
    assert lab["donated"] == []
    assert report["registry"] == {"status": "SKIPPED_DRY_RUN"}
    R = lab["registry"]
    assert R.discoveries(limit=10) == []


def test_donations_are_idempotent_by_object_id(lab):
    first = ML.run(budget_s=40.0, traditions=list(FAST), permutations=30)
    n_first = len(lab["donated"])
    if n_first == 0:
        pytest.skip(f"nothing passed the burden screen this run: {first['objects']}")
    cursor = json.loads(ML.DONATED.read_text("utf-8"))
    assert len(cursor["object_ids"]) == n_first
    second = ML.run(budget_s=40.0, traditions=list(FAST), permutations=30)
    assert len(lab["donated"]) == n_first, "a second pass re-donated the same objects"
    assert second["donation"]["already_donated_in_a_previous_pass"] >= 1
    assert second["allocation"]["traditions"]["spectral"]["lifetime_trials"] >= \
        first["allocation"]["traditions"]["spectral"]["lifetime_trials"]


def test_allocation_is_two_sided_and_floored():
    equal = ML.allocation(dict.fromkeys(S.TRADITIONS))
    shares = [v["share"] for v in equal["traditions"].values()]
    assert all(s == pytest.approx(shares[0]) for s in shares)
    assert sum(shares) == pytest.approx(1.0, abs=1e-4)
    roi: dict[str, float | None] = dict.fromkeys(S.TRADITIONS)
    roi["spectral"] = 5.0
    roi["topology"] = -5.0
    roi["causal"] = 0.0
    priced = ML.allocation(roi)
    t = priced["traditions"]
    assert t["spectral"]["share"] > t["causal"]["share"] > t["topology"]["share"]
    assert all(v["share"] >= ML.FLOOR_SHARE for v in t.values())
    assert t["topology"]["share"] == pytest.approx(ML.FLOOR_SHARE, abs=0.02)
    assert sum(v["share"] for v in t.values()) == pytest.approx(1.0, abs=1e-4)
    assert t["geometry"]["roi_status"] == "UNMEASURED"
    assert "not an unproductive one" in t["geometry"]["why"]
    extreme = dict.fromkeys(S.TRADITIONS, -100.0)
    floors = ML.allocation(extreme)["traditions"]
    assert all(v["share"] >= ML.FLOOR_SHARE for v in floors.values())


def test_workers_are_derived_from_measured_memory_and_floored(monkeypatch):
    monkeypatch.setattr(ML, "_free_phys_bytes", lambda: None)
    workers, detail = ML.max_workers()
    assert workers == ML.WORKER_FLOOR and detail["status"] == "UNMEASURED"
    monkeypatch.setattr(ML, "_free_phys_bytes", lambda: 64 * 2 ** 30)
    workers, detail = ML.max_workers()
    assert detail["status"] == "MEASURED" and ML.WORKER_FLOOR <= workers <= detail["cpus"]
    monkeypatch.setattr(ML, "_free_phys_bytes", lambda: 100 * 2 ** 20)
    workers, _ = ML.max_workers()
    assert workers == ML.WORKER_FLOOR


def test_an_empty_panel_set_reports_unmeasured_and_never_idles_silently(lab, monkeypatch):
    monkeypatch.setattr(ML, "build_panels", lambda max_targets=4: (
        [], {"unmeasured": ["residual store: no horizon carries rows"]}))
    report = ML.run(budget_s=5.0, traditions=list(FAST))
    assert report["objects"]["admitted"] == 0
    assert any("no target produced" in u for u in report["unmeasured"])
    assert any("residual store" in u for u in report["unmeasured"])
    assert ML.OUT.exists()
