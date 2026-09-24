"""The fast admission screen may only refuse what the ten gates could never pass.

If it ever refuses a cell the gates would have JUDGED, it is a gate in disguise and it is wrong
(principal 2026-09-24). These tests pin the reason vocabulary shut, pin the delegation to the
sealed judge's own gate 0, and pin the promise that the screen deletes nothing.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK.parents[1]), str(DESK), str(DESK / "research"), str(DESK / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import fast_admission as fa  # noqa: E402

SOURCE = (DESK / "research" / "fast_admission.py").read_text("utf-8")


def test_reason_vocabulary_is_closed_and_every_reason_is_a_fact() -> None:
    """Four reasons, each about the INSTRUMENT or the MECHANISM, none about the edge."""
    assert fa.REASONS == ("no_symbol_or_family", "untradeable_symbol",
                          "no_economic_prior", "off_hypothesis_lane")
    for reason in fa.REASONS:
        assert reason in fa.WHY_NEVER_PASSABLE, f"{reason} publishes no justification"
        assert reason in fa.OWNER, f"{reason} names no owner for its removal"


def test_the_screen_carries_no_statistical_judgement() -> None:
    """No score, no rank, no threshold. The ten gates are the only thing that certifies."""
    banned = ("sharpe", "pvalue", "p_value", "threshold", "score", "rank(", "min_",
              "cutoff", "percentile", "top_n", "quantile")
    decision = SOURCE.split("def screen(", 1)[1].split("\ndef build(", 1)[0].lower()
    for token in banned:
        assert token not in decision, (
            f"{token!r} appears in the screen's decision path -- that would make it a second "
            f"judge, and the ten gates in policy/gate_spec.yaml are the only thing that certifies")


def test_tradeability_and_the_prior_are_delegated_to_the_sealed_judge() -> None:
    """One judge, one predicate. A second spelling is how four pens got four different rules."""
    assert "from external_gauntlet import partition_at_economic_prior" in SOURCE
    assert "def symbol_is_tradeable" not in SOURCE
    assert "def economic_prior" not in SOURCE


def test_the_screen_writes_only_its_own_two_artifacts() -> None:
    """It never rewrites the bank. The bank keeps every row it has ever held."""
    assert "external_survivors" in SOURCE            # it READS the bank
    writes = [line for line in SOURCE.splitlines() if "_atomic_json(" in line]
    assert writes, "the screen must publish something"
    for line in writes:
        assert "RAW_DOCKET" not in line and "external_survivors" not in line, (
            f"the screen must never write the bank: {line.strip()}")


def test_screen_splits_raw_from_admissible_by_named_reason(monkeypatch) -> None:
    """The whole point: two populations, two numbers, each refusal named."""
    class _Stub:
        @staticmethod
        def timeframe_of(params, family=""):
            return str((params or {}).get("timeframe") or "H1")

        @staticmethod
        def partition_at_economic_prior(specs, meta):
            eligible, rejected = [], []
            for spec in specs:
                sym = str(spec.get("sym") or "")
                if sym not in meta:
                    rejected.append({"cell": sym, "sym": sym, "family": spec.get("family"),
                                     "terminal_gate": "symbol_eligibility"})
                elif spec.get("family") == "no_mechanism":
                    rejected.append({"cell": sym, "sym": sym, "family": spec.get("family"),
                                     "terminal_gate": "economic_prior"})
                else:
                    eligible.append(spec)
            return eligible, rejected

    monkeypatch.setitem(sys.modules, "external_gauntlet", _Stub)
    meta = {"EURUSD": {}, "XAUUSD": {}, "Apple": {}}
    rows = [
        {"symbol": "EURUSD", "family": "session_range_breakout", "params": {"rr": 1.5}},
        {"symbol": "EURUSD", "family": "session_range_breakout", "params": {"rr": 2.0}},
        {"symbol": "NOTREAL", "family": "session_range_breakout", "params": {}},
        {"symbol": "XAUUSD", "family": "no_mechanism", "params": {}},
        {"symbol": None, "family": "session_range_breakout", "params": {}},
        {"symbol": "Apple", "family": "session_range_breakout", "params": {}},
    ]

    out = fa.screen(rows, meta)

    assert out["raw_rows"] == 6
    assert out["raw_cells"] == 5            # the two EURUSD rows are two cells, not one
    assert out["refused_by_reason"]["no_symbol_or_family"] == 1
    assert out["refused_by_reason"]["untradeable_symbol"] == 1
    assert out["refused_by_reason"]["no_economic_prior"] == 1
    # Apple is a single-name equity: the two-lane order forbids hunting it for hypotheses.
    assert out["refused_by_reason"]["off_hypothesis_lane"] == 1
    assert out["admissible_cells"] == 2
    assert out["raw_cells"] - out["admissible_cells"] == out["refused_cells"] - 1


def test_an_unreadable_docket_is_unmeasured_never_an_empty_population(tmp_path: Path) -> None:
    """UNMEASURED is a real answer (L1.28a). Absence never resolves to 'nothing admissible'."""
    doc = fa.build(tmp_path / "absent.json", tmp_path / "universe.json")
    assert doc["status"] == "UNMEASURED"
    assert "admissible_cells" not in doc


def test_a_missing_registry_refuses_to_guess_tradeability(tmp_path: Path) -> None:
    """Without the registry the tradeability limb cannot run, and guessing it would refuse
    cells the gates could have judged -- which is the one thing this screen may never do."""
    docket = tmp_path / "docket.json"
    docket.write_text(json.dumps([{"symbol": "EURUSD", "family": "carry"}]), "utf-8")
    doc = fa.build(docket, tmp_path / "no_universe.json")
    assert doc["status"] == "UNMEASURED"
    assert "registry" in doc["why"]


def test_the_leg_is_on_a_clock_and_belongs_to_a_layer() -> None:
    """UNWIRED OR IDLE IS A DEFECT (III.16)."""
    from libs.research.layers import LEG_LAYER
    assert LEG_LAYER["fast_admission"] == "prediction"
    cycle = (DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert '"fast_admission", "research/fast_admission.py"' in cycle
    assert '"fast_admission": fa' in cycle
    # It must run BEFORE the judge it describes.
    assert cycle.index('"fast_admission", "research/fast_admission.py"') < \
        cycle.index('"external_gauntlet", "scripts/external_gauntlet.py"')
