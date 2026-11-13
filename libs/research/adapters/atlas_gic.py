"""atlas_gic adapter -- REBUILT: ATLAS-GIC's self-improving experiment archive, read for what
it adds over single-symbol search: GENERALISATION. Every experiment (mechanism kind x window)
is run on EVERY frame of the bundle; the archive keeps, per experiment, its train evidence on
each instrument; the next generation mutates only experiments that worked on MORE THAN ONE
instrument, and an experiment is donated to an instrument only when it held on that
instrument's holdout AND its train evidence was positive on at least TRANSFER_MIN other
instruments. A configuration that works once is a fit; one that transfers is a mechanism.

WHY NOT THE UPSTREAM. No distribution resolvable on the box (ledger: NO_DISTRIBUTION_PINNED)
and its experiment proposer is an LLM. The archive-guided, transfer-gated improvement loop is
the transferable part.
"""
from __future__ import annotations

import random
from typing import Any

from libs.research import adapter_kit as K
from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "atlas_gic"
CAPABILITY_FAMILY = "trajectory_evolution"
LICENCE_EXPECTED = "UNVERIFIED"
MODULE = "atlas_gic"
RUNS_WITHOUT_LIBRARY = True
CENSUS_CLASS = "b"
ROLE = "hypothesis generator (cross-instrument transfer-gated experiment archive, rebuilt)"
HORIZON = 12
GENERATIONS = 3
TRANSFER_MIN = 2
KINDS: tuple[str, ...] = ("momentum", "trend", "reversion", "band_reversion",
                          "range_reversion", "pullback", "breakout", "squeeze")


def run(bundle: A.ResearchBundle) -> ExternalResearchPacket:
    fr = K.frames(bundle, limit=10)
    if len(fr) < 2:
        return A.unmeasured(SYSTEM, bundle, "transfer needs at least two H1 frames of 300 bars")
    deadline = A.Deadline(bundle.compute_budget_s)
    rng = random.Random(bundle.seed + 23)  # noqa: S311 -- a seeded mutation order
    data = []
    for f in fr:
        a = K.arrays(f)
        data.append((f, a, K.split(a["c"].shape[0]), K.cost_frac(bundle, f.symbol, a["c"])))
    pop = [(k, w) for k in KINDS for w in (12, 48)]
    archive: dict[tuple[str, int], dict[str, Any]] = {}
    trials = 0
    for gen in range(GENERATIONS):
        if deadline.expired():
            break
        for exp in pop:
            if exp in archive:
                continue
            per = {}
            for f, a, cut, cost in data:
                trials += 1
                per[f.symbol] = K.score_kinds(a, [exp], HORIZON, cost, cut)[0]
            archive[exp] = {"generation": gen, "per_symbol": per,
                            "n_positive_train": sum(1 for r in per.values()
                                                    if r["train"]["mean_net"] > 0)}
        movers = [e for e, v in archive.items() if v["n_positive_train"] >= TRANSFER_MIN]
        pop = [(k, max(3, min(200, int(w * rng.choice((0.5, 0.75, 1.5, 2.0))))))
               for k, w in rng.sample(movers, min(len(movers), 6))] if movers else []
    cands: list[dict[str, Any]] = []
    for (kind, w), v in archive.items():
        for sym, r in v["per_symbol"].items():
            others = v["n_positive_train"] - (1 if r["train"]["mean_net"] > 0 else 0)
            if (r["train"]["mean_net"] > 0 and r["holdout"]["mean_net"] > 0
                    and r["holdout"]["n_active"] >= 20 and others >= TRANSFER_MIN):
                cands.append(K.donate(
                    A, SYSTEM, kind, sym,
                    f"{sym} H1: an ATLAS-style archive experiment ({kind}, {w} bars) held on "
                    f"{sym}'s holdout and was positive on the train span of {others} other "
                    f"instruments in the same bundle; a transferring {kind} hypothesis",
                    horizon_label=bundle.horizons[-1],
                    ev={"generation": v["generation"], "transfer_count": others,
                        "train": r["train"], "holdout": r["holdout"]},
                    window=w, horizon=HORIZON))
    cands = sorted(cands, key=lambda c: -float(c["evidence"]["transfer_count"]))[:12]
    reps = [{"kind": "experiment_archive", "n_experiments": len(archive),
             "transfer_min": TRANSFER_MIN,
             "experiments": [{"kind_": k, "window": w, "generation": v["generation"],
                              "n_positive_train": v["n_positive_train"]}
                             for (k, w), v in sorted(archive.items(),
                                                     key=lambda kv: -kv[1]["n_positive_train"])
                             ][:30]}]
    methods = [K.upstream_row(SYSTEM, MODULE, "self-improving experiment archive gated on "
                              "cross-instrument transfer", "no distribution on the box and its "
                              "proposer is an LLM; mutation of transferring experiments stands "
                              "for it")]
    return A.packet(SYSTEM, bundle, trials=trials, representations=reps, candidates=cands,
                    research_methods=methods)


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
