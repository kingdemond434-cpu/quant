"""inalpha adapter -- REBUILT: factor TIMING. The same mechanism earns in one state of the tape
and loses in another; InAlpha's contribution is to time a factor's exposure by state rather
than to search for a new factor. Each mechanism kind is scored on the train span CONDITIONAL
on the volatility tercile it was taken in (terciles fixed on the train span); the state the
tape is in at the end of the bundle selects which mechanism is "on"; that timed choice is read
on the holdout restricted to the same state, and donated when it holds there.

WHY NOT THE UPSTREAM. No distribution resolvable on the box (ledger: NO_DISTRIBUTION_PINNED)
and its strategy-code evolution is LLM-written. State-conditional factor timing needs neither.
"""
from __future__ import annotations

from typing import Any

from libs.research import adapter_kit as K
from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "inalpha"
CAPABILITY_FAMILY = "evolutionary_search"
LICENCE_EXPECTED = "UNVERIFIED"
MODULE = "inalpha"
RUNS_WITHOUT_LIBRARY = True
CENSUS_CLASS = "b"
ROLE = "hypothesis generator (volatility-state factor timing, rebuilt)"
HORIZON = 12
SPECS: tuple[tuple[str, int], ...] = (("momentum", 24), ("trend", 50), ("reversion", 14),
                                      ("band_reversion", 20), ("breakout", 24),
                                      ("squeeze", 20), ("pullback", 50))
STATES = ("calm", "normal", "stressed")


def run(bundle: A.ResearchBundle) -> ExternalResearchPacket:
    import numpy as np
    fr = K.frames(bundle)
    if not fr:
        return A.unmeasured(SYSTEM, bundle, "no H1 frame carries 300 bars")
    deadline = A.Deadline(bundle.compute_budget_s)
    trials = 0
    reps: list[dict[str, Any]] = []
    cands: list[dict[str, Any]] = []
    for f in fr:
        if deadline.expired():
            break
        a = K.arrays(f)
        c = a["c"]
        n = c.shape[0]
        cut = K.split(n)
        cost = K.cost_frac(bundle, f.symbol, c)
        lc = np.log(np.maximum(c, 1e-12))
        vol = K.rolling_std(np.diff(lc, prepend=lc[0]), 48)
        if not np.isfinite(vol[:cut]).any():
            continue
        q = np.nanquantile(vol[:cut], (1 / 3, 2 / 3))
        state = np.searchsorted(q, np.nan_to_num(vol, nan=float(q[0])))
        fwd = K.forward_return(c, HORIZON)
        table: dict[str, dict[str, Any]] = {}
        for kind, w in SPECS:
            s = K.kind_signal(kind, a, w)
            for k, name in enumerate(STATES):
                trials += 1
                masked = np.where(state == k, s, 0.0)
                table.setdefault(name, {})[kind] = {
                    "window": w, "train": K.evidence(masked, fwd, cost, 0, cut),
                    "holdout": K.evidence(masked, fwd, cost, cut, n)}
        now = STATES[int(state[-1])]
        on = sorted(((r["train"]["t_ratio"], kind) for kind, r in table[now].items()
                     if r["train"]["mean_net"] > 0), reverse=True)
        reps.append({"kind": "state_conditional_factor_table", "symbol": f.symbol,
                     "current_state": now,
                     "on_by_state": {st: max(((r["train"]["t_ratio"], k) for k, r in
                                              table[st].items()), default=(0.0, ""))[1]
                                     for st in STATES}})
        if not on:
            continue
        kind = on[0][1]
        r = table[now][kind]
        if r["holdout"]["mean_net"] > 0 and r["holdout"]["n_active"] >= 10:
            cands.append(K.donate(
                A, SYSTEM, kind, f.symbol,
                f"{f.symbol} H1: InAlpha-style factor timing selects {kind} in the tape's "
                f"current {now} volatility state (train evidence conditional on that state), "
                f"and it held on the holdout restricted to the same state",
                horizon_label=bundle.horizons[-1],
                ev={"state": now, "window": r["window"], "train": r["train"],
                    "holdout": r["holdout"]}, window=int(r["window"]), horizon=HORIZON))
    methods = [K.upstream_row(SYSTEM, MODULE, "state-conditional factor timing",
                              "no distribution on the box; its strategy-code evolution is "
                              "LLM-written")]
    return A.packet(SYSTEM, bundle, trials=trials, representations=reps, candidates=cands,
                    research_methods=methods)


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
