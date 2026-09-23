"""DoWhy adapter -- identify / estimate / REFUTE a lagged cross-asset effect: does a one-sigma
shock in symbol A's last return move symbol B's next return, given B's own vol? The
placebo refutation is the adversarial verifier the roster names; the estimate and its
refutation are donated as research methods, never as a signal.
"""
from __future__ import annotations

from typing import Any

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "dowhy"
CAPABILITY_FAMILY = "causal_discovery"
LICENCE_EXPECTED = "MIT"
MAX_SYMBOLS = 3
SIMS = 20


def run(bundle: A.ResearchBundle) -> ExternalResearchPacket:
    dw = A.library("dowhy")
    pd = A.library("pandas")
    if dw is None or pd is None:
        return A.unmeasured(SYSTEM, bundle, "dowhy (or pandas) is not importable here (pip "
                                            "install dowhy==0.8)")
    import numpy as np
    frames = [f for f in bundle.frames("H1") if len(f) > 400][:MAX_SYMBOLS]
    if len(frames) < 2:
        return A.unmeasured(SYSTEM, bundle, "fewer than two H1 frames long enough")
    deadline = A.Deadline(bundle.compute_budget_s)
    n = min(len(f) for f in frames) - 2
    rets = {f.symbol: f.log_returns()[-n - 1:] for f in frames}
    trials = 0
    rows: list[dict[str, Any]] = []
    for a in frames:
        for b in frames:
            if a is b or deadline.expired():
                continue
            ra, rb = rets[a.symbol], rets[b.symbol]
            vol = A.realised_vol(rb, 24)
            ok = np.isfinite(vol[:-1])
            t = (np.abs(ra[:-1]) > np.nanstd(ra)).astype(int)[ok]
            df = pd.DataFrame({"t": t, "y": rb[1:][ok], "v": vol[:-1][ok]})
            trials += 1
            try:
                model = dw.CausalModel(data=df, treatment="t", outcome="y", common_causes=["v"])
                ident = model.identify_effect(proceed_when_unidentifiable=True)
                est = model.estimate_effect(ident, method_name="backdoor.linear_regression")
                ref = model.refute_estimate(ident, est, method_name="placebo_treatment_refuter",
                                            placebo_type="permute", num_simulations=SIMS)
                pval = getattr(ref, "refutation_result", {}) or {}
                rows.append({"kind": "causal_estimate", "treatment": a.symbol,
                             "outcome": b.symbol, "effect": float(est.value),
                             "placebo_effect": float(getattr(ref, "new_effect", float("nan"))),
                             "placebo_p": pval.get("p_value") if isinstance(pval, dict)
                             else None, "n": int(df.shape[0]),
                             "method": "backdoor.linear_regression + placebo refuter"})
            except Exception as exc:
                rows.append({"kind": "UNMEASURED", "treatment": a.symbol, "outcome": b.symbol,
                             "why": f"{type(exc).__name__}: {exc}"[:200]})
    return A.packet(SYSTEM, bundle, trials=trials, research_methods=rows)


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
