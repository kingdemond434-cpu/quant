"""DataHub contracts must be refreshed by a clock the repo knows and must reach judged cells; the
analytics tool registry must import, match its signatures, read real contracts, and stay
propose-only."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_DESK = _ROOT / "desks" / "mt5"
for _p in (str(_ROOT), str(_DESK), str(_DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.data import datahub_desk as dd  # noqa: E402
from libs.data.datahub import desk_hub  # noqa: E402
from libs.research import tool_registry as tr  # noqa: E402

NEW = ("micro.flow_bars", "micro.depth_probe", "micro.surfaces", "tape.spread_flow",
       "macro.fred_daily", "cot.positioning")


def test_the_desk_hub_registers_every_contract_with_metadata() -> None:
    names = set(desk_hub().contracts())
    assert set(NEW) <= names
    assert names == set(dd.META), "a contract without ContractMeta cannot be audited"
    # the other thread's namespaces stay theirs
    assert not any(n.startswith(("ais.", "tanker.", "openbb.")) for n in NEW)


def test_every_declared_clock_is_one_the_repo_knows() -> None:
    known = dd._clock_resolver(_ROOT)
    for name, meta in dd.META.items():
        assert meta.clocks, name
        assert any(known(c) for c in meta.clocks), f"{name}: no known clock in {meta.clocks}"


def test_coverage_verdicts_follow_the_judge_record(tmp_path: Path) -> None:
    jc = tmp_path / "JUDGE_COVERAGE.json"
    jc.write_text(json.dumps({"at": "x", "totals": {"judged_verdicts": 10},
                              "families": {"carry": {"judged_total": 5},
                                           "event_reaction": {"judged_total": 0}}}))
    ledger = tmp_path / "ledger.jsonl"
    ledger.write_text(
        json.dumps({"cell": "a", "family": "exogenous_conditioner", "passed": False,
                    "terminal_gate": "deflated_sharpe", "params": {"source": "micro_EURUSD"}})
        + "\n" + json.dumps({"cell": "b", "family": "exogenous_conditioner",
                             "terminal_gate": "UNKNOWN", "source": "micro_GBPUSD"}) + "\n")
    rep = dd.coverage(judge_coverage=jc, ledger=ledger, flow_report=tmp_path / "none.json",
                      probe=False)
    rows = rep["rows"]
    assert rows["terms.swap_diff"]["verdict"] == dd.REACHES
    assert rows["calendar.events"]["verdict"] == dd.AWAITING
    assert rows["bars.h1"]["judged"] == 10
    # one real verdict; the UNKNOWN line is not a judgement
    assert rows["micro.flow_bars"]["judged"] == 1
    assert rows["micro.flow_bars"]["verdict"] == dd.REACHES
    assert rows["micro.depth_probe"]["verdict"] == dd.UNBUILDABLE
    assert rep["reaching_judge"] == sum(r["verdict"] == dd.REACHES for r in rows.values())


def test_an_absent_judge_record_is_unmeasured_not_zero(tmp_path: Path) -> None:
    rep = dd.coverage(judge_coverage=tmp_path / "x.json", ledger=tmp_path / "y.jsonl",
                      flow_report=tmp_path / "z.json", probe=False)
    assert rep["rows"]["terms.swap_diff"]["verdict"] == dd.UNMEASURED
    assert rep["rows"]["micro.flow_bars"]["verdict"] == dd.UNMEASURED


def test_the_tool_registry_verifies_every_tool() -> None:
    rep = tr.build()
    bad = [(r["name"], r["status"], r.get("why")) for r in rep["rows"] if r["status"] != "OK"]
    assert not bad, bad
    assert not rep["duplicate_names"]
    assert all(r["authority"] == tr.PROPOSE_ONLY for r in rep["rows"])
    block = tr.prompt_block(rep)
    assert "flow_toxicity_series" in block and "propose-only" in block


def test_call_refuses_undeclared_inputs_and_runs_declared_ones() -> None:
    with pytest.raises(TypeError):
        tr.call("deflate_t", t_obs=3.0, n_tests=10, extra=1)
    assert tr.call("deflate_t", t_obs=3.0, n_tests=10) < 3.0
    with pytest.raises(KeyError):
        tr.by_name("no_such_tool")


def test_no_live_sizing_module_imports_the_registry() -> None:
    money = (_ROOT / "ops" / "money_closure.txt").read_text("utf-8").split()
    for rel in money:
        p = _ROOT / rel
        if p.suffix == ".py" and p.exists():
            assert "tool_registry" not in p.read_text("utf-8", errors="replace"), rel


def test_the_leg_is_on_the_hourly_clock_and_in_a_layer() -> None:
    from libs.research.layers import LEG_LAYER
    src = (_DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    for leg in ("flow_toxicity", "datahub_coverage", "tool_registry"):
        assert f'_costed("{leg}"' in src
        assert leg in LEG_LAYER
