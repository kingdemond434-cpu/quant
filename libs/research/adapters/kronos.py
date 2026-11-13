"""kronos adapter -- REBUILT: Kronos's K-line TOKENISER and an autoregressive next-token model,
in their simplest faithful form. Kronos (a foundation model for candlesticks) quantises each
bar's OHLCV into discrete tokens and learns next-token distributions; this rebuild quantises
each H1 bar into a token (body sign x body size tercile x range tercile, against trailing
quantiles so it is causal) and fits an order-2 n-gram on the train span. Where the n-gram's
predicted next-bar direction carries out-of-sample evidence on the holdout, the token context
that drives it is donated as a recipe.

WHY NOT THE UPSTREAM. No wheel resolvable on the box interpreter (ledger: NO_DISTRIBUTION_
PINNED) and its weights would come from a model hub the research path does not reach. The
tokenise-then-predict mechanism needs no weights to be measured.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from libs.research import adapter_kit as K
from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "kronos"
CAPABILITY_FAMILY = "foundation_model"
LICENCE_EXPECTED = "UNVERIFIED"
MODULE = "kronos"
RUNS_WITHOUT_LIBRARY = True
CENSUS_CLASS = "b"
ROLE = "hypothesis generator (candle tokeniser + n-gram next-token model, rebuilt)"
QWIN = 240
MIN_COUNT = 15


def tokens(a: dict[str, Any]) -> Any:
    """Token = sign(body) * (1 + 3*body_tercile + range_tercile), 0 for a doji; trailing
    terciles only, so a token never uses a later bar."""
    import numpy as np
    o, h, lo, c = a["o"], a["h"], a["l"], a["c"]
    body = np.abs(c - o)
    rng = h - lo
    n = c.shape[0]
    tok = np.zeros(n, dtype=int)
    for i in range(QWIN, n):
        b_q = np.quantile(body[i - QWIN:i], (1 / 3, 2 / 3))
        r_q = np.quantile(rng[i - QWIN:i], (1 / 3, 2 / 3))
        bt = int(np.searchsorted(b_q, body[i]))
        rt = int(np.searchsorted(r_q, rng[i]))
        s = int(np.sign(c[i] - o[i]))
        tok[i] = s * (1 + 3 * bt + rt)
    return tok


def run(bundle: A.ResearchBundle) -> ExternalResearchPacket:
    import numpy as np
    fr = K.frames(bundle, min_bars=QWIN + 300)
    if not fr:
        return A.unmeasured(SYSTEM, bundle, f"no H1 frame carries {QWIN + 300} bars")
    deadline = A.Deadline(bundle.compute_budget_s)
    trials = 0
    reps: list[dict[str, Any]] = []
    cands: list[dict[str, Any]] = []
    for f in fr:
        if deadline.expired():
            break
        a = K.arrays(f)
        tok = tokens(a)
        c = a["c"]
        n = c.shape[0]
        fwd1 = K.forward_return(c, 1)
        cut = K.split(n)
        stats: dict[tuple[int, int], list[float]] = defaultdict(list)
        for i in range(QWIN + 1, cut - 1):
            stats[(int(tok[i - 1]), int(tok[i]))].append(float(fwd1[i]))
        trials += 1
        model = {k: float(np.mean(v)) for k, v in stats.items() if len(v) >= MIN_COUNT}
        sig = np.zeros(n)
        for i in range(cut, n - 1):
            m = model.get((int(tok[i - 1]), int(tok[i])))
            if m is not None:
                sig[i] = np.sign(m)
        cost = K.cost_frac(bundle, f.symbol, c)
        ho = K.evidence(sig, fwd1, cost, cut, n)
        # does the model lean on continuation (next bar same sign as the last token) or reversal?
        cont = [np.sign(m) * np.sign(k[1]) for k, m in model.items() if k[1] != 0]
        lean = float(np.mean(cont)) if cont else 0.0
        reps.append({"kind": "kline_token_ngram", "symbol": f.symbol, "vocabulary": 19,
                     "contexts_fitted": len(model), "continuation_lean": round(lean, 4),
                     "holdout": ho})
        if ho["n_active"] >= 30 and ho["mean_net"] > 0 and lean != 0:
            kind = "momentum" if lean > 0 else "reversion"
            cands.append(K.donate(
                A, SYSTEM, kind, f.symbol,
                f"{f.symbol} H1: a Kronos-style candle tokeniser with an order-2 next-token "
                f"model fitted on {cut} bars leans {'continuation' if lean > 0 else 'reversal'} "
                f"({lean:+.2f}) and kept a positive net mean on the holdout; a {kind} "
                f"hypothesis at the bar scale", horizon_label=bundle.horizons[0],
                ev={"continuation_lean": lean, "holdout": ho, "contexts": len(model)},
                window=3, horizon=4))
    methods = [K.upstream_row(SYSTEM, MODULE, "K-line tokenisation + autoregressive next-token "
                              "model", "no wheel resolvable on the box and no model-hub weights "
                              "on the research path; an n-gram stands for the transformer")]
    return A.packet(SYSTEM, bundle, trials=trials, representations=reps, candidates=cands,
                    research_methods=methods)


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
