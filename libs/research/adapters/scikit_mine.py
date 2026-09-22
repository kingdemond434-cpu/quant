"""scikit-mine adapter -- SLIM pattern mining over discretised bar events -> sequential-pattern
representations and cells.

Each bar becomes tokens (big up/down move, high/low vol, wide range); transactions are 4-bar
windows with position-encoded tokens so order is preserved. One SLIM fit per symbol is one
charged trial. Patterns pairing a big move with high vol suggest vol mean reversion; repeated
same-signed moves suggest continuation -- both leave as hypotheses.
"""
from __future__ import annotations

from typing import Any

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "scikit_mine"
SPAN, WINDOW, MAX_PATTERNS = 4, 24, 12


def _tokens(r: Any, vol: Any, rng: Any, i: int) -> list[str]:
    import numpy as np
    out = []
    if r[i] > 1.5 * vol[i]:
        out.append("UPB")
    elif r[i] < -1.5 * vol[i]:
        out.append("DNB")
    if vol[i] > np.nanquantile(vol, 0.8):
        out.append("VOLH")
    elif vol[i] < np.nanquantile(vol, 0.2):
        out.append("VOLL")
    if rng[i] > np.nanquantile(rng, 0.8):
        out.append("WIDE")
    return out


def _patterns(slim: Any, D: list[list[str]]) -> list[tuple[list[str], int]]:
    """The code table, through whichever API this scikit-mine exposes."""
    slim.fit(D)
    if hasattr(slim, "discover"):
        got = slim.discover()
        items: Any = got.items() if hasattr(got, "items") else enumerate(got)
        return [(sorted(str(x) for x in k), int(v)) for k, v in items]
    table = getattr(slim, "codetable_", None)
    if table is None:
        raise AttributeError("no discover() and no codetable_ on SLIM")
    return [(sorted(str(x) for x in k), len(v)) for k, v in table.items()]


def run(bundle: A.ResearchBundle) -> ExternalResearchPacket:
    itemsets = A.library("skmine.itemsets")
    if itemsets is None:
        return A.unmeasured(SYSTEM, bundle, "scikit-mine (skmine) is not importable here")
    import numpy as np
    deadline = A.Deadline(bundle.compute_budget_s)
    trials = 0
    reps: list[dict[str, Any]] = []
    cands: list[dict[str, Any]] = []
    for f in bundle.frames("H1"):
        if deadline.expired():
            break
        r = f.log_returns()
        if r.shape[0] < 300:
            continue
        vol = A.realised_vol(r, WINDOW)
        c = np.asarray(f.close, float)[1:]
        rng = (np.asarray(f.high, float)[1:] - np.asarray(f.low, float)[1:]) / np.maximum(c,
                                                                                         1e-12)
        D: list[list[str]] = []
        for a in range(WINDOW, r.shape[0] - SPAN):
            tx = [f"t{k}_{tok}" for k in range(SPAN) for tok in _tokens(r, vol, rng, a + k)]
            if tx:
                D.append(tx)
        trials += 1
        try:
            found = _patterns(itemsets.SLIM(), D)
        except Exception as exc:
            reps.append({"kind": "UNMEASURED", "symbol": f.symbol,
                         "why": f"{type(exc).__name__}: {exc}"[:200]})
            continue
        multi = sorted((p for p in found if len(p[0]) >= 2), key=lambda p: -p[1])[:MAX_PATTERNS]
        reps.append({"kind": "sequential_event_pattern", "symbol": f.symbol,
                     "timeframe": f.timeframe, "span_bars": SPAN, "n_transactions": len(D),
                     "vocabulary": ["UPB", "DNB", "VOLH", "VOLL", "WIDE"],
                     "patterns": [{"items": p, "usage": u} for p, u in multi]})
        for p, u in multi[:3]:
            joined = " ".join(p)
            if "VOLH" in joined and ("UPB" in joined or "DNB" in joined):
                family, why = "vol_mean_reversion", "a big move inside high vol"
            elif joined.count("UPB") >= 2 or joined.count("DNB") >= 2:
                family, why = "momentum_volgate", "repeated same-signed big moves"
            else:
                continue
            cands.append(A.candidate(
                family, [f.symbol],
                f"{f.symbol} H1: SLIM's code table keeps the {SPAN}-bar pattern {p} (usage {u} "
                f"of {len(D)} windows) -- {why}; a {family.replace('_', ' ')} hypothesis",
                horizon=bundle.horizons[0], source=SYSTEM,
                evidence={"pattern": p, "usage": u, "n_transactions": len(D)}))
    return A.packet(SYSTEM, bundle, trials=trials, representations=reps, candidates=cands)


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
