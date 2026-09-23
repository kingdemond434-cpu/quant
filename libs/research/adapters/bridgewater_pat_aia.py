"""Bridgewater AIA / PAT adapter (REBUILT, public architecture only) -- the six-stage
workflow (ambiguous question -> plan -> PIT evidence -> calculations -> causal explanation
-> testable hypotheses) mapped onto the desk organs that already carry each stage. Nothing
internal is public and nothing internal is sought; this adapter runs without any library.

IT MEASURES THE MAPPING, IT DOES NOT ASSERT IT (2026-09-23). Until this pass the adapter
returned the stage table as a route row and nothing else, so `sandbox_runner` recorded it
TEXT_ONLY -- a system that said something and measured nothing, which LAWS 5h says is never a
resting state. The mapping is now CHECKED against this tree: for every stage the named organ
file must exist, and the artifact it writes must exist and carry an age. The coverage that
leaves is `n_present/6` with the per-stage evidence, donated as a REPRESENTATION, so a stage
whose organ is deleted or whose artifact goes stale shows up as a number instead of a claim.
"""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "bridgewater_pat_aia"
CAPABILITY_FAMILY = "institutional_capability"
LICENCE_EXPECTED = "N/A (no code)"
RUNS_WITHOUT_LIBRARY = True


#: (stage, the desk file that carries it, the artifact that proves it ran). Paths are relative
#: to the repository root; the adapter runs in-process (RUNS_WITHOUT_LIBRARY) so it can read
#: them, and reads NOTHING else -- no network, no secret, no write.
STAGES: tuple[tuple[str, str, str], ...] = (
    ("ambiguous question", "desks/mt5/research/standing_questions.py",
     "desks/mt5/reports/STANDING_QUESTIONS.json"),
    ("plan", "desks/mt5/research/science_controller.py",
     "desks/mt5/reports/SCIENCE_CONTROLLER.json"),
    ("point-in-time evidence", "desks/mt5/research/data_scout.py",
     "desks/mt5/reports/DATA_SCOUT.json"),
    ("calculations", "desks/mt5/research/feature_compiler.py",
     "desks/mt5/reports/FEATURE_COMPILER.json"),
    ("causal explanation", "libs/research/adapters/tigramite.py",
     "desks/mt5/reports/SANDBOX_RUNNER.json"),
    ("testable hypotheses", "desks/mt5/research/miner_candidate_compiler.py",
     "desks/mt5/data/hypotheses/miner_candidates.json"),
)


def _root() -> Path:
    """The repository root, from this file's own location. No environment, no guess."""
    return Path(__file__).resolve().parents[3]


def _measure(root: Path, organ: str, artifact: str) -> dict[str, Any]:
    op, ar = root / organ, root / artifact
    row: dict[str, Any] = {"organ": organ, "organ_exists": op.exists(),
                           "artifact": artifact, "artifact_exists": ar.exists()}
    if ar.exists():
        try:
            age = (datetime.now(tz=UTC)
                   - datetime.fromtimestamp(ar.stat().st_mtime, tz=UTC)).total_seconds()
            row["artifact_age_h"] = round(age / 3600.0, 2)
            row["artifact_bytes"] = ar.stat().st_size
        except OSError as exc:
            row["why"] = f"{type(exc).__name__}: {exc}"[:120]
    return row


def run(bundle: A.ResearchBundle) -> ExternalResearchPacket:
    root = _root()
    rows = [{"stage": stage, **_measure(root, organ, artifact)}
            for stage, organ, artifact in STAGES]
    present = [r for r in rows if r["organ_exists"] and r["artifact_exists"]]
    missing = [r["stage"] for r in rows if not (r["organ_exists"] and r["artifact_exists"])]
    return A.packet(
        SYSTEM, bundle, trials=len(STAGES),
        representations=[{
            "kind": "institutional_workflow_coverage", "system": SYSTEM,
            "workflow": "AIA/PAT six stages (public architecture only)",
            "n_stages": len(STAGES), "n_carried": len(present),
            "coverage": round(len(present) / len(STAGES), 4),
            "missing_stages": missing, "stages": rows,
            "representation": ("which of the six stages this desk actually carries, MEASURED "
                               "against the tree: organ file present and its artifact written. "
                               "A state of the institution, never a verdict on it")}],
        research_methods=[{
            "kind": "REBUILT_ROUTE", "system": SYSTEM,
            "why": "public architecture only; every stage is carried by a desk organ on a clock",
            "coverage": f"{len(present)}/{len(STAGES)} stages carried and producing"}],
        note=f"architecture coverage measured: {len(present)}/{len(STAGES)} stages")


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
