"""rd_agent adapter -- REBUILT: RD-Agent's factor R&D loop (propose -> implement -> evaluate ->
feedback) with its two distinctive disciplines kept and its LLM replaced by a deterministic
proposer: (1) a factor is accepted only when it is NOVEL against the library already accepted
(|corr| < NOVELTY_MAX with every earlier factor, RD-Agent's dedup against its SOTA library) and
(2) the FEEDBACK of every round re-weights which hypothesis TEMPLATE the next round draws from,
so the loop is an experiment that changes the next one rather than a grid.

THE PROPOSER. A small typed grammar -- operator x lookback x transform -- standing where the
LLM proposed factor code: ts_mom(w), ts_zscore(w), ts_rank(w), range_pos(w), vol_ratio(w1, w2),
up_ratio(w), with an optional sign flip. Templates are weighted by their running holdout IC.
Every evaluated factor is a charged trial.

WHY NOT THE UPSTREAM. `rdagent` cannot run without an LLM provider key: its proposer and coder
ARE model calls (sandbox_install_ledger: REJECTED_WITH_EVIDENCE). LLMs propose only on this desk
and the research path carries none; the loop's structure is the transferable mechanism.
"""
from __future__ import annotations

from typing import Any

from libs.research import adapter_kit as K
from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "rd_agent"
CAPABILITY_FAMILY = "factor_model_coevolution"
LICENCE_EXPECTED = "MIT"
MODULE = "rdagent"
RUNS_WITHOUT_LIBRARY = True
CENSUS_CLASS = "b"
ROLE = "hypothesis generator (factor R&D loop with novelty dedup, rebuilt)"
ROUNDS = 6
PER_ROUND = 6
NOVELTY_MAX = 0.7
HORIZON = 12
LOOKBACKS: tuple[int, ...] = (5, 10, 20, 40, 80)
TEMPLATES: dict[str, str] = {"ts_mom": "momentum", "ts_zscore": "band_reversion",
                             "range_pos": "range_reversion", "vol_ratio": "squeeze",
                             "up_ratio": "momentum", "ts_rank": "momentum"}


def factor(name: str, a: dict[str, Any], w: int) -> Any:
    import numpy as np
    c = a["c"]
    n = c.shape[0]
    if name == "ts_mom":
        x = np.full(n, np.nan)
        x[w:] = np.log(c[w:] / np.maximum(c[:-w], 1e-12))
        return x
    if name == "ts_zscore":
        return K.zscore(c, w)
    if name == "range_pos":
        hi, lo = K.rolling_max(a["h"], w), K.rolling_min(a["l"], w)
        return (c - lo) / np.maximum(hi - lo, 1e-12)
    if name == "vol_ratio":
        r = np.diff(np.log(np.maximum(c, 1e-12)), prepend=np.nan)
        return K.rolling_std(np.nan_to_num(r), w) / np.maximum(
            K.rolling_std(np.nan_to_num(r), 4 * w), 1e-12)
    if name == "up_ratio":
        return K.sma((np.diff(c, prepend=c[0]) > 0).astype(float), w)
    if name == "ts_rank":
        x = np.full(n, np.nan)
        for i in range(w - 1, n):
            seg = c[i - w + 1:i + 1]
            x[i] = float(np.sum(seg <= seg[-1])) / w
        return x
    raise ValueError(name)


def run(bundle: A.ResearchBundle) -> ExternalResearchPacket:
    import random

    import numpy as np
    fr = K.frames(bundle, limit=8)
    if not fr:
        return A.unmeasured(SYSTEM, bundle, "no H1 frame carries 300 bars")
    deadline = A.Deadline(bundle.compute_budget_s)
    rng = random.Random(bundle.seed + 11)  # noqa: S311 -- a seeded proposal order
    trials = 0
    reps: list[dict[str, Any]] = []
    cands: list[dict[str, Any]] = []
    for f in fr:
        a = K.arrays(f)
        fwd = K.forward_return(a["c"], HORIZON)
        cut = K.split(a["c"].shape[0])
        weights = dict.fromkeys(TEMPLATES, 1.0)
        library: list[tuple[dict[str, Any], Any]] = []
        log: list[dict[str, Any]] = []
        for rnd in range(ROUNDS):
            if deadline.expired():
                break
            names = list(weights)
            for _ in range(PER_ROUND):
                t = rng.choices(names, weights=[weights[x] for x in names])[0]
                w = rng.choice(LOOKBACKS)
                x = factor(t, a, w)
                trials += 1
                ic_tr, ic_ho = K.rank_ic(x[:cut], fwd[:cut]), K.rank_ic(x[cut:], fwd[cut:])
                novel = all(abs(K.corr(x, y)) < NOVELTY_MAX for _, y in library)
                stable = ic_tr != 0 and np.sign(ic_tr) == np.sign(ic_ho)
                row: dict[str, Any] = {"round": rnd, "template": t, "window": w,
                                       "ic_train": round(ic_tr, 5),
                                       "ic_holdout": round(ic_ho, 5), "novel": bool(novel),
                                       "accepted": bool(novel and stable and abs(ic_ho) > 0.02)}
                log.append(row)
                # FEEDBACK: the template's weight follows its holdout evidence
                weights[t] = max(0.2, weights[t] + (abs(ic_ho) * 20 if row["accepted"] else -0.1))
                if row["accepted"]:
                    library.append((row, x))
        reps.append({"kind": "rd_loop_trace", "symbol": f.symbol, "rounds": ROUNDS,
                     "template_weights": {k: round(v, 3) for k, v in weights.items()},
                     "accepted": [r for r, _ in library], "n_evaluated": len(log)})
        for row, _ in sorted(library, key=lambda rx: -abs(rx[0]["ic_holdout"]))[:2]:
            kind = TEMPLATES[row["template"]]
            if kind == "momentum" and row["ic_holdout"] < 0:
                kind = "reversion"
            cands.append(K.donate(
                A, SYSTEM, kind, f.symbol,
                f"{f.symbol} H1: RD-Agent-style R&D loop accepted "
                f"{row['template']}({row['window']}) in round {row['round']} -- novel against the "
                f"accepted library, holdout rank IC "
                f"{row['ic_holdout']:+.3f}; a {kind} hypothesis",
                horizon_label=bundle.horizons[-1], ev=row, window=int(row["window"]),
                horizon=HORIZON))
    methods = [K.upstream_row(SYSTEM, MODULE, "propose/implement/evaluate/feedback factor loop "
                              "with library dedup", "the upstream proposer and coder are LLM "
                              "calls (REJECTED_WITH_EVIDENCE: no provider key on the research "
                              "path); a typed grammar proposes instead")]
    return A.packet(SYSTEM, bundle, trials=trials, representations=reps, candidates=cands,
                    research_methods=methods)


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
