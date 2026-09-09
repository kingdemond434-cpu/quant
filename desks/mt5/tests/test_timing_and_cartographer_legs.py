"""Three modules that ran on nobody's clock now run on the daily one (Tier-1 audit G18/G15).

hour_surface has been measuring expected R by UTC hour and its only importer was its own
producer; hour_prior turns that into the bounded prior `pf_allocator` already looks for and had
never written its file; alpha_periodic_table -- the mechanism x axis white-space map -- had NO
caller anywhere. What is pinned here is the CONTRACT the daily cycle's module list imposes:
importable by bare name, a `run()`/`write()`/`main()` it can call, an artifact written on every
path including the unmeasured one, and -- the part that would have cost the most -- no
BaseException escaping into a loop that only catches Exception.
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
# THE PRODUCTION PATH, deliberately: `daily_cycle` puts BASE, BASE/research and BASE/scripts on
# sys.path and NOT side_channels, so `__import__("alpha_periodic_table")` there resolves to the
# research leg. Adding side_channels here would shadow it with the implementation module and the
# test would be exercising something the cycle never runs.
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

LEGS = ("hour_surface", "hour_prior", "alpha_periodic_table")


def _feedback_list() -> list[str]:
    """The module names `_state_research_feedback` iterates, read from the source."""
    tree = ast.parse((_DESK / "research" / "daily_cycle.py").read_text("utf-8"))
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "_state_research_feedback")
    for node in ast.walk(fn):
        if isinstance(node, ast.For) and isinstance(node.iter, ast.Tuple):
            return [e.value for e in node.iter.elts if isinstance(e, ast.Constant)]
    raise AssertionError("the feedback list is no longer a tuple literal -- re-pin it")


# --------------------------------------------------------------------------- the list
def test_the_three_legs_are_appended_at_the_end_of_the_list() -> None:
    names = _feedback_list()
    assert names[-3:] == list(LEGS), names[-6:]
    assert len(set(names)) == len(names), "a leg is listed twice"


def test_hour_prior_runs_after_hour_surface_because_it_reads_its_artifact() -> None:
    names = _feedback_list()
    assert names.index("hour_surface") < names.index("hour_prior")


@pytest.mark.parametrize("name", LEGS)
def test_each_leg_satisfies_the_lists_call_contract(name: str) -> None:
    """`mod = __import__(name)`, then run() / write() / main() -- in that order."""
    mod = __import__(name)
    assert hasattr(mod, "run") or hasattr(mod, "write") or hasattr(mod, "main"), name
    if hasattr(mod, "run"):
        assert callable(mod.run)
    assert callable(getattr(mod, "main", None)), f"{name} has no main() to run standalone"


# --------------------------------------------------------------------------- the artifacts
def test_hour_surface_writes_its_artifact_and_names_the_gap(tmp_path, monkeypatch) -> None:
    import hour_surface as hs

    monkeypatch.setattr(hs, "OUT", tmp_path / "hour_surface.json")
    doc = hs.run()
    assert hs.OUT.exists()
    written = json.loads(hs.OUT.read_text("utf-8"))
    assert written["covered_hours"] == doc["covered_hours"]
    assert "gap" in written and len(written["hours"]) == 24
    # An hour nobody traded reports None, never 0.0 -- the rule the module already stated.
    assert all(h["expected_r"] is None or isinstance(h["expected_r"], float)
               for h in written["hours"])


def test_a_projection_refusal_is_a_named_gap_and_never_a_torn_down_cycle(monkeypatch) -> None:
    """THE ONE THAT WOULD HAVE COST THE MOST. `portfolio_projection.build_sleeves` raises
    SystemExit when hunt12_partial.json is absent -- correctly -- and SystemExit is a
    BaseException, so the daily cycle's `except Exception` around each module would NOT have
    caught it: one missing report would have taken down the whole cycle, promotion chain
    included."""
    import hour_surface as hs
    import research.portfolio_projection as pp
    monkeypatch.setattr(pp, "build_sleeves",
                        lambda *a, **k: (_ for _ in ()).throw(SystemExit("REFUSING to project")))
    got = hs.sleeve_hours()
    assert got == {}
    assert "SystemExit" in hs.REFUSAL and "REFUSING" in hs.REFUSAL
    doc = hs.build()
    assert doc["covered_hours"] == 0 and "REFUSING" in doc["gap"]
    # And the leg itself returns rather than raising, which is what the loop needs.
    assert isinstance(hs.run(), dict)


def test_hour_prior_writes_an_unmeasured_artifact_when_the_surface_is_absent(tmp_path,
                                                                            monkeypatch) -> None:
    """It used to return without writing anything, so a box with no surface had no artifact --
    indistinguishable from a box where this had never run."""
    import hour_prior as hp

    monkeypatch.setattr(hp, "SURFACE", tmp_path / "absent.json")
    monkeypatch.setattr(hp, "OUT", tmp_path / "hour_prior.json")
    doc = hp.run()
    assert hp.OUT.exists()
    assert doc["status"] == "UNMEASURED" and doc["priors"] == {}
    # `prior_for` reads that file and must still answer "no opinion", never a zero.
    assert hp.prior_for(8) == 1.0


def test_hour_prior_turns_a_surface_into_a_bounded_prior(tmp_path, monkeypatch) -> None:
    import hour_prior as hp

    surface = {"hours": [
        {"hour_utc": 8, "expected_r": 0.166, "trades": 6143, "funded_heat": 0.0755},
        {"hour_utc": 14, "expected_r": 0.164, "trades": 6154, "funded_heat": 0.0004},
        {"hour_utc": 3, "expected_r": 0.9, "trades": 5, "funded_heat": 0.0},
    ]}
    s = tmp_path / "hour_surface.json"
    s.write_text(json.dumps(surface), "utf-8")
    monkeypatch.setattr(hp, "SURFACE", s)
    monkeypatch.setattr(hp, "OUT", tmp_path / "hour_prior.json")
    doc = hp.run()
    assert doc["priors"]["8"] > 1.0 and doc["priors"]["14"] > 1.0
    assert max(doc["priors"].values()) <= 1.0 + hp.MAX_SHADE + 1e-9
    assert doc["priors"]["3"] == 1.0, "a loud hour on five trades must have no opinion"
    assert 14 in doc["starved_positive_hours"], (
        "the free finding is a STARVED WINNER: significant and under 1% of the book")
    assert 8 not in doc["starved_positive_hours"]


def test_the_periodic_table_writes_the_map_and_refuses_to_flatter_its_coverage(tmp_path,
                                                                              monkeypatch
                                                                              ) -> None:
    import alpha_periodic_table as leg
    from side_channels import alpha_periodic_table as impl

    monkeypatch.setattr(impl, "REPORT", tmp_path / "ALPHA_PERIODIC_TABLE.json")
    monkeypatch.setattr(impl, "PERIODIC_DIR", tmp_path / "matrix")
    (tmp_path / "matrix").mkdir()
    doc = leg.run()
    assert impl.REPORT.exists()
    assert doc["cells_total"] == len(impl.MECHANISMS) * len(impl.AXES) == 63
    assert doc["cells_empty"] + doc["cells_discovered"] + doc["cells_validated"] \
        == doc["cells_total"]
    # 0 empty cells must NOT read as full coverage: every cell is pre-filled with a seed
    # description, and the measurement that means coverage is cells_validated.
    assert "cells_validated" in doc["coverage_caveat"] or doc["cells_empty"] > 0
    assert doc["cells_validated"] == 0, "no hypothesis has been registered on this host"
    assert (tmp_path / "matrix" / "mechanism_matrix.csv").exists()


def test_the_bare_name_resolves_to_the_leg_on_the_cycles_own_path() -> None:
    """`daily_cycle` imports by bare name off BASE/research; the implementation must not shadow
    the leg there, or the cycle would run a module it never meant to."""
    import alpha_periodic_table as leg
    assert Path(leg.__file__).parent.name == "research"
    assert callable(leg.run) and callable(leg.main)


def test_the_implementation_loads_without_its_package_context() -> None:
    """A relative import would be fatal to any bare-name loader, which is why the package
    import keeps a fallback. Loaded here straight off the file, with no package."""
    import importlib.util
    path = _DESK / "side_channels" / "alpha_periodic_table.py"
    spec = importlib.util.spec_from_file_location("_standalone_periodic_table", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod                     # the loader protocol dataclasses relies on
    try:
        spec.loader.exec_module(mod)                 # would raise on a bare relative import
    finally:
        sys.modules.pop(spec.name, None)
    assert callable(mod.run) and callable(mod.main)
    assert len(mod.MECHANISMS) * len(mod.AXES) == 63


def test_none_of_the_three_reaches_the_network_or_a_terminal() -> None:
    for name in ("research/hour_surface.py", "research/hour_prior.py",
                 "side_channels/alpha_periodic_table.py", "research/alpha_periodic_table.py"):
        src = (_DESK / name).read_text("utf-8")
        for forbidden in ("import requests", "urllib.request", "MetaTrader5", "httpx"):
            assert forbidden not in src, f"{name} reaches for {forbidden}"
