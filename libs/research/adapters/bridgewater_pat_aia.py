"""Bridgewater AIA / PAT adapter (REBUILT, public architecture only) -- the six-stage
workflow (ambiguous question -> plan -> PIT evidence -> calculations -> causal explanation
-> testable hypotheses) mapped onto the desk organs that already carry each stage. Nothing
internal is public and nothing internal is sought; this adapter runs without any library
and donates the mapping as a research method so the coverage is measurable.
"""
from __future__ import annotations

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "bridgewater_pat_aia"
CAPABILITY_FAMILY = "institutional_capability"
LICENCE_EXPECTED = "N/A (no code)"
RUNS_WITHOUT_LIBRARY = True


def run(bundle: A.ResearchBundle) -> ExternalResearchPacket:
    stages = [
        {"stage": "ambiguous question", "desk_organ": "research/standing_questions.py"},
        {"stage": "plan", "desk_organ": "research/science_controller.py (anytime science)"},
        {"stage": "point-in-time evidence", "desk_organ": "research/data_scout.py + the "
                                                          "ingestion ledger (available_time)"},
        {"stage": "calculations", "desk_organ": "research/feature_compiler.py"},
        {"stage": "causal explanation", "desk_organ": "the causal lab (dowhy/tigramite "
                                                      "adapters + libs/research/causal*)"},
        {"stage": "testable hypotheses", "desk_organ": "miner_candidate_compiler -> the "
                                                       "ten-gate gauntlet"},
    ]
    return A.packet(SYSTEM, bundle, trials=0, research_methods=[
        {"kind": "REBUILT_ROUTE", "system": SYSTEM, "workflow": stages,
         "why": "public architecture only; every stage is carried by a desk organ on a clock",
         "coverage": f"{len(stages)}/6 stages mapped"}],
        note="architecture mapping; no upstream code exists to run")


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
