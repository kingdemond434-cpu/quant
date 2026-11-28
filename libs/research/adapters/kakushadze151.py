"""151 Trading Strategies adapter (REBUILT, numpy only) -- Kakushadze & Serur (2018), a public
SSRN survey, as the desk's SECOND formulaic family source beside the 101 alphas.

`libs/research/strategies151.py` holds the catalogue (every strategy IMPLEMENTED, UNMEASURED or
INAPPLICABLE with its reason) and the desk's own causal implementations of the ones an MT5 CFD
can carry. This adapter measures them over the bundle's own bars and donates:

  * TIME-SERIES strategies (moving averages, pivots, channels, R-squared trend, internal bar
    strength, trend following, the one-sided HP filter, KNN): one charged trial per (strategy,
    symbol) rank IC against the forward return; every finite association becomes a
    STRUCTURED_HYPOTHESIS under the strategy's own registered family when the measured sign
    agrees with the strategy's stated direction and under its declared mirror when it opposes
    it -- never chosen by strength. KNN has no family analogue and is donated as a
    representation only.
  * CROSS-SECTIONAL strategies (class momentum, low volatility, residual momentum, the
    mean-reversion clusters, rotation, skewness, contrarian): ranked within the peer class
    MetaTrader's registry gives each instrument (`universe_policy.peer_class`, a USD pair read
    as its non-USD currency), measured as one charged trial per (strategy, class) mean
    cross-sectional rank IC, and donated as a representation naming the desk's class-book family
    and grid cell it instantiates -- the class books are judged as one-symbol legs that load
    their own panel, so the gates reach them through that family, not through this queue.
  * PAIRS within a class: one charged trial per pair, donated as a representation.

UNMEASURED and INAPPLICABLE rows ride in the census representation by name. Nothing here
ranks strategies, sizes or approves -- the ten gates do.
"""
from __future__ import annotations

from typing import Any

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "kakushadze151"
CAPABILITY_FAMILY = "dsl_program_search"
LICENCE_EXPECTED = "N/A (published method)"
RUNS_WITHOUT_LIBRARY = True
MIN_BARS = 300


def run(bundle: A.ResearchBundle) -> ExternalResearchPacket:
    import numpy as np

    from libs.research import formulaic_alphas as F
    from libs.research import strategies151 as S
    from libs.research.adapters.alpha101 import horizon_bars

    frames = [f for f in bundle.frames("H1") if len(f) > MIN_BARS]
    if not frames:
        return A.unmeasured(SYSTEM, bundle, f"no H1 frame carries more than {MIN_BARS} bars")
    classes = F.registry_classes([f.symbol for f in frames])
    #: The class books admit share CFDs (principal 2026-09-30); everything else does not.
    xs_frames = [f for f in frames if classes[f.symbol]["class_book"]]
    aside = [{"symbol": f.symbol, "why": classes[f.symbol]["why"] or "not admitted by "
              "universe_policy (UNCLASSIFIED)"} for f in frames
             if not classes[f.symbol]["class_book"]]
    if not xs_frames:
        return A.unmeasured(SYSTEM, bundle, "no frame is admitted by the two-lane order")
    deadline = A.Deadline(bundle.compute_budget_s)
    panel = F.panel_from_frames(xs_frames, {s: c["group"] for s, c in classes.items()})
    ts_ok = np.array([bool(classes[s]["hypothesis"]) for s in panel.symbols])
    orient = np.array([float(classes[s]["orientation"]) for s in panel.symbols])
    h = horizon_bars(bundle.horizons[0] if bundle.horizons else "1h")
    horizon = bundle.horizons[0] if bundle.horizons else "4h"
    with np.errstate(all="ignore"):
        fwd = F.forward_returns(panel, h)
    min_members = F.min_class_members()
    reps: list[dict[str, Any]] = []
    cands: list[dict[str, Any]] = []
    trials = 0
    not_reached: list[str] = []
    for sid in S.TS_IDS:
        if deadline.expired():
            not_reached.append(sid)
            continue
        row = S.BY_ID[sid]
        sig = S.ts_signal(sid, panel, h)
        ics: dict[str, float | None] = {}
        for j, sym in enumerate(panel.symbols):
            if not ts_ok[j]:
                continue                      # a share CFD never takes a time-series family
            idx = np.flatnonzero(panel.present[:, j])
            trials += 1
            ic = F.rank_ic(sig[idx, j], fwd[idx, j])
            ics[sym] = None if np.isnan(ic) else ic
            if np.isnan(ic) or row.aligned is None or row.mirror is None:
                continue
            fam, params = row.aligned if ic > 0 else row.mirror
            cands.append(A.candidate(
                fam, [sym],
                f"{sym} H1: '{row.name}' (Kakushadze & Serur 2018, {row.section}) scores a rank "
                f"IC of {ic:+.4f} against the {h}-bar forward return over {idx.size} bars -- "
                f"{'as the strategy states' if ic > 0 else 'opposite to the strategy'}",
                horizon=horizon, source=SYSTEM,
                evidence={"strategy": sid, "ic_rank": ic, "n_bars": int(idx.size),
                          "parameters": dict(params), "forward_bars": h,
                          "method": "time-series rank IC, desk numpy implementation"}))
        reps.append({"kind": "strategy151", "strategy": sid, "name": row.name,
                     "section": row.section, "shape": "time_series", "ic_by_symbol": ics,
                     "forward_bars": h})
    for sid in S.XS_IDS:
        if deadline.expired():
            not_reached.append(sid)
            continue
        row = S.BY_ID[sid]
        sig, groups = S.xs_signal(sid, panel, orient, min_members)
        by_class: dict[str, Any] = {}
        for g in sorted({g for g in groups if g}):
            cols = [j for j, gg in enumerate(groups) if gg == g]
            sub = sig[:, cols]
            if not np.isfinite(sub).any():
                by_class[g] = {"xs_ic_mean": None, "members": len(cols),
                               "why": f"fewer than {min_members} members carry a score"}
                continue
            trials += 1
            with np.errstate(all="ignore"):
                xic, n_rows = F.xs_ic(sub, fwd[:, cols])
            by_class[g] = {"xs_ic_mean": None if np.isnan(xic) else xic, "xs_bars": n_rows,
                           "members": len(cols),
                           "symbols": [panel.symbols[j] for j in cols]}
        reps.append({"kind": "strategy151", "strategy": sid, "name": row.name,
                     "section": row.section, "shape": "cross_sectional",
                     "desk_family": row.desk_family, "desk_params": dict(row.desk_params),
                     "by_class": by_class, "forward_bars": h,
                     "symbols": [panel.symbols[j] for j, g in enumerate(groups) if g]})
    pair_rows: list[dict[str, Any]] = []
    if not deadline.expired():
        hyp = [j for j in range(len(panel.symbols)) if ts_ok[j]]
        for i, j, sig, chg in S.pair_signals(panel):
            if i not in hyp or j not in hyp:
                continue
            trials += 1
            ic = F.rank_ic(sig, chg)
            pair_rows.append({"legs": [panel.symbols[i], panel.symbols[j]],
                              "class": panel.groups[i], "ic_rank": None if np.isnan(ic) else ic})
        reps.append({"kind": "strategy151", "strategy": "stk.pairs", "name": "pairs trading",
                     "section": "stocks", "shape": "pair", "pairs": pair_rows,
                     "forward_bars": 1})
    else:
        not_reached.append("stk.pairs")
    reps.insert(0, {
        "kind": "strategy151_census", **S.counts(),
        "implemented": [r.sid for r in S.CATALOGUE if r.disposition == S.IMPLEMENTED],
        "unmeasured": {r.sid: r.why for r in S.CATALOGUE if r.disposition == S.UNMEASURED},
        "inapplicable": {r.sid: r.why for r in S.CATALOGUE if r.disposition == S.INAPPLICABLE},
        "not_reached_this_pass": not_reached, "set_aside_by_lane": aside,
        "panel_symbols": list(panel.symbols), "min_class_members": min_members,
        "source": "Kakushadze & Serur (2018) 151 Trading Strategies (SSRN); catalogue "
                  "reconstructed by the desk, implementations in desk numpy"})
    return A.packet(SYSTEM, bundle, trials=trials, representations=reps, candidates=cands,
                    note=f"{len(S.TS_IDS) + len(S.XS_IDS) + len(S.PAIR_IDS) - len(not_reached)}"
                         f" strategies measured over {len(panel.symbols)} symbols")


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
