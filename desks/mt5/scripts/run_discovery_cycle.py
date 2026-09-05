"""The discovery chain, end to end, on a clock: mine -> explain -> record -> report.

WHY A DRIVER AND NOT SEVEN CRON LINES. The pieces only mean something in sequence: the miner
proposes structure, the adapters attach candidate causes and falsifiers, trajectories carry the
path, and the store records what happened so yield can be measured across stages. Wiring them
separately would let any one of them fail silently while the others kept reporting healthy --
which is this desk's most expensive defect class, and the reason this file exists as one unit.

UNWIRED IS A DEFECT (III.16). A module that runs only when a human types its name is not part of
the desk. This is the artifact-leaving, schedule-running form of the seven pieces, and it fails
LOUDLY: a stage that produces nothing says so on the report rather than letting the next stage
read an empty input as a clean result.

IT PROMOTES NOTHING. Anomalies are observations; explanations are hypotheses with falsifiers
attached. Nothing here writes a certificate, enrols a clock, or touches the authority files. The
output is a docket of things worth testing, and everything on it still walks the same ten gates.
"""
from __future__ import annotations

import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
sys.path.insert(0, str(ROOT))

from libs.research import research_state as store  # noqa: E402
from libs.research.anomaly_miner import scan  # noqa: E402
from libs.research.mechanism_adapters import coverage, explain  # noqa: E402
from libs.research.trajectory import from_anomaly, register  # noqa: E402

sys.path.insert(0, str(DESK / "research"))
from acquire_datasets import acquire  # noqa: E402
from compile_anomalies import compile_latest  # noqa: E402

REPORT = DESK / "reports" / "discovery_cycle.json"


def main() -> int:
    started = time.monotonic()
    stamp = datetime.now(UTC).isoformat(timespec="seconds")

    # ACQUIRE FIRST. The miner's vocabulary is whatever build_primitives can serve, and acquired
    # series only reach it once they are on disk -- so a cycle that mined before acquiring would
    # spend its whole pass on the price-native half and never see the external drivers.
    try:
        acquired = acquire()
    except Exception as exc:             # acquisition is best-effort; mining must still run
        acquired = {"error": f"{type(exc).__name__}: {exc}", "datasets_kept": 0}

    mined = scan()
    anomalies = mined.get("anomalies") or []
    trials = int(mined.get("trials") or 0)

    explained = unexplained = registered = 0
    by_mechanism: dict[str, int] = {}
    for a in anomalies:
        e = explain(a)
        causes = e.get("candidate_explanations") or []
        if not causes:
            unexplained += 1
            continue
        explained += 1
        for c in causes:
            m = str(c.get("mechanism"))
            by_mechanism[m] = by_mechanism.get(m, 0) + 1
        # ONE TRAJECTORY PER (anomaly, best cause). Registering every cause would multiply the
        # docket by the number of explanations, and several causes sharing a signature is the
        # normal case -- so that would inflate the count without adding a single new experiment.
        t = from_anomaly(a, causes[0])
        if register(t, trials=trials):
            registered += 1

    # COMPILE, so the chain ends in something the gauntlet can judge. Without this the cycle
    # produces trajectories nobody can test -- structure, causes and falsifiers that stop one
    # move short of the only arbiter the desk has.
    compiled = compile_latest()

    report = {
        "ran_at": stamp,
        "elapsed_s": round(time.monotonic() - started, 1),
        "mined": {
            "symbols": mined.get("symbols_scanned"),
            "cells_evaluated": trials,
            "anomalies": len(anomalies),
            "cross_sectional": mined.get("cross_sectional_anomalies"),
        },
        "acquired": {
            "datasets_kept": acquired.get("datasets_kept"),
            "total_series": acquired.get("total_series"),
            "refusals": acquired.get("refusals"),
        },
        "explained": explained,
        "unexplained": unexplained,
        "trajectories_registered": registered,
        "compiled": {
            "candidates_out": compiled.get("candidates_out"),
            "symbols": compiled.get("symbols"),
            "skipped_unexplained": compiled.get("skipped_unexplained"),
            "skipped_no_recipe": compiled.get("skipped_no_single_feature_recipe"),
        },
        "by_mechanism": dict(sorted(by_mechanism.items(), key=lambda kv: -kv[1])),
        "adapter_coverage": coverage(),
        "store": store.census(),
        "generator_yield": store.generator_yield(),
        "mechanism_yield": store.mechanism_yield()[:12],
        "promotes_nothing": ("anomalies are observations and explanations are hypotheses with "
                             "falsifiers. No certificate is written, no clock enrolled, no "
                             "authority file touched; everything still walks the ten gates."),
    }

    # A STAGE THAT PRODUCED NOTHING SAYS SO. Silence between stages is how an empty input gets
    # read downstream as a clean result -- the defect this desk keeps paying for.
    breaches = []
    if not anomalies:
        breaches.append("MINER: zero anomalies from a completed scan -- a scan that finds "
                        "nothing on 40 symbols is a wiring fault, not a quiet market")
    if anomalies and explained == 0:
        breaches.append("ADAPTERS: anomalies exist and NONE was explained -- every signature "
                        "missed, which is a defect in the adapters rather than in the data")
    if anomalies and not compiled.get("candidates_out"):
        breaches.append("COMPILER: anomalies exist and ZERO compiled to candidates -- the chain "
                        "stops one move short of the gauntlet, which is where it stopped for "
                        "every prose source that ever converted at 0 of 341")
    if registered == 0 and anomalies:
        breaches.append("STORE: nothing registered from a non-empty docket -- either every "
                        "trajectory was a duplicate, or the store is not writing")
    report["breaches"] = breaches

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=1, default=str), encoding="utf-8")
    print(f"discovery cycle: {len(anomalies)} anomalies from {trials:,} cells, "
          f"{explained} explained, {registered} new trajectories, "
          f"{compiled.get('candidates_out', 0)} candidates -> {REPORT}")
    for b in breaches:
        print(f"  BREACH: {b}")
    return 1 if breaches else 0


if __name__ == "__main__":
    sys.exit(main())
