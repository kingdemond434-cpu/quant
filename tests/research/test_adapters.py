"""The adapter contract: every federated system's adapter exposes its name, licence and
capability family, returns a packet-shaped result over a read-only bundle, and DEGRADES to an
UNMEASURED packet -- never a stack trace -- when its upstream library is absent."""
from __future__ import annotations

import importlib
import pkgutil
from types import ModuleType

import pytest

from libs.research import adapters as A
from libs.research import external_federation as fed
from libs.research.external_federation import ExternalResearchPacket


def _modules() -> list[ModuleType]:
    out = []
    for info in pkgutil.iter_modules(A.__path__):
        if info.name.startswith("_"):
            continue
        out.append(importlib.import_module(f"{A.__name__}.{info.name}"))
    return sorted(out, key=lambda m: m.__name__)


MODULES = _modules()
IDS = [m.__name__.rsplit(".", 1)[-1] for m in MODULES]


def test_the_package_carries_every_mandated_wave() -> None:
    names = set(IDS)
    for sid in ("alphagen", "dso", "pysr", "tigramite", "causal_learn", "dowhy", "chronos2",
                "timesfm", "moment", "abides", "featuretools", "cvxportfolio", "pymc",
                "neuralforecast", "darts", "kats", "merlion", "aeon", "idtxl", "tpot",
                "openspiel", "pyg_temporal", "ripser", "ray", "easytpp", "reservoirpy",
                "kymatio", "sbi", "openevolve", "darwin_godel_machine", "ai_scientist",
                "pyribs", "dspy", "quantifact", "bridgewater_pat_aia", "alpha_search",
                "quantrocket", "quantconnect_cloud", "numerai_method",
                # the first wave the dead builder shipped
                "ruptures", "stumpy", "pysindy", "pydmd", "tsfresh", "riskfolio", "pymoo",
                "nevergrad", "botorch", "river", "mapie", "tensorly", "pyrqa", "pgmpy",
                "pyextremes", "scikit_mine", "tslearn", "pyvinecopulib", "roughpy"):
        assert sid in names, f"adapter {sid} is missing"
        assert sid in A.SPECS, f"{sid} has no Spec"
        assert sid in fed.SEED_BY_ID, f"{sid} is not on the federation roster"


@pytest.mark.parametrize("module", MODULES, ids=IDS)
def test_every_adapter_exposes_name_licence_family_and_run(module: ModuleType) -> None:
    d = A.describe(module)
    assert d["name"] == module.SYSTEM and d["name"] in A.SPECS
    assert isinstance(d["licence"], str) and d["licence"]
    assert d["licence"].startswith("UNVERIFIED"), "no licence is asserted from memory"
    assert d["licence_expected"] and d["licence_expected"] in d["licence"]
    assert d["capability_family"] in fed.CAPABILITY_FAMILIES
    assert callable(d["run"]) and callable(module.run)
    spec = A.SPECS[module.SYSTEM]
    if spec.distribution:
        assert spec.requirement.startswith(spec.distribution)


def test_describe_reports_the_licence_of_record_when_the_ledger_has_read_one() -> None:
    mod = importlib.import_module("libs.research.adapters.ruptures")
    d = A.describe(mod, licences={"ruptures": "BSD-2-Clause"})
    assert d["licence"] == "BSD-2-Clause"
    assert A.describe(mod, licences={"ruptures": "UNVERIFIED"})["licence"].startswith("UNVERIFIED")


@pytest.mark.parametrize("module", MODULES, ids=IDS)
def test_every_adapter_degrades_to_unmeasured_without_its_library(
        module: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(A, "library", lambda name: None)
    bundle = A.synthetic_bundle(seed=3, n=700, budget_s=5)
    packet = module.run(bundle)
    assert isinstance(packet, ExternalResearchPacket)
    assert packet.system_id == module.SYSTEM
    assert packet.trials_charged >= 0
    if getattr(module, "RUNS_WITHOUT_LIBRARY", False):
        assert not packet.empty(), "a REBUILT method must produce with numpy alone"
    else:
        assert A.is_unmeasured(packet), f"{module.SYSTEM} ran without its library"
        why = [r for r in packet.research_methods if r.get("kind") == "UNMEASURED"]
        assert why and "not importable" in str(why[0].get("why"))


def test_the_numpy_rebuilt_methods_run_today_and_carry_provenance() -> None:
    bundle = A.synthetic_bundle(seed=1, n=900, budget_s=10)
    numerai = importlib.import_module("libs.research.adapters.numerai_method").run(bundle)
    assert numerai.trials_charged >= 3
    kinds = {r["kind"] for r in numerai.research_methods}
    assert "numerai_contribution" in kinds
    assert numerai.commit.startswith("desk:")
    pat = importlib.import_module("libs.research.adapters.bridgewater_pat_aia").run(bundle)
    assert pat.research_methods[0]["kind"] == "REBUILT_ROUTE"
    assert len(pat.research_methods[0]["workflow"]) == 6


def test_lagged_design_is_point_in_time_and_era_blocked() -> None:
    import numpy as np
    bundle = A.synthetic_bundle(seed=2, n=400)
    f = bundle.frames("H1")[0]
    X, y, era = A.lagged_design(f, target_bars=1, era_bars=50)
    r = f.log_returns()
    # row 0 starts at t = window + lags = 27: X carries r[26], r[25], r[24]; y is r[27]
    assert np.isclose(X[0, 0], r[26]) and np.isclose(X[0, 1], r[25]) and np.isclose(y[0], r[27])
    assert X.shape[1] == len(A.LAGGED_FEATURE_NAMES)
    assert era[0] == 0 and era[-1] > 0
    X24, y24, _ = A.lagged_design(f, target_bars=24)
    assert np.isclose(y24[0], r[27:51].sum()) and X24.shape[0] == X.shape[0] - 23


def test_a_cell_commit_is_the_desk_tree_head_not_a_pypi_pin() -> None:
    assert A.commit_of("cell:anything").startswith("desk:")
    assert A.commit_of("ruptures").startswith("pypi:ruptures==")
    assert A.commit_of("never_registered") == "UNMEASURED"


def test_api_probe_measures_what_an_importable_upstream_exposes() -> None:
    import json as lib
    row = A.api_probe("x", lib, ("dumps", "loads", "not_there"))
    assert row["kind"] == "api_surface" and row["present"] == ["dumps", "loads"]
    assert "not_there" in row["expected_names"]
