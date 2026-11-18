"""Alpha101 adapter (REBUILT, numpy only) -- ALL 101 published formulaic alphas (Kakushadze 2015,
arXiv:1601.00991) evaluated as one CROSS-SECTIONAL PANEL over this bundle's own bars.

`libs/research/formulaic_alphas.py` is the evaluator: the paper's operator algebra written in the
desk's own causal numpy (rank across the symbols present at a bar, ts_* per symbol over its own
bars, indneutralize within the peer class MetaTrader's registry gives each instrument), the
declared CFD proxies named (tick volume, tick-volume ADV, typical price for vwap), and `cap`
UNMEASURED because no honest proxy exists. This adapter turns that panel into a packet:

  * every alpha with a measurable status is ONE CHARGED TRIAL for its cross-sectional rank IC;
  * a per-symbol donation is charged ONCE PER CELL: about 95 alphas collapse onto the two donated
    families keyed only by window, so the donations are deduplicated by (symbol, family, params)
    BEFORE charging -- the first alpha to reach a cell donates it, every later alpha that lands on
    the same cell is named in that donation's `collapsed_alphas` and counted in the census
    (`collapsed_duplicates`, `collapsed_by_alpha`), so nothing vanishes and nothing is paid twice;
  * every finite (alpha, symbol) association is donated as a STRUCTURED_HYPOTHESIS under a
    registered price-only family -- the SIGN chooses momentum or reversion, never a strength
    threshold, so a weak association is donated exactly like a strong one -- parameterised at
    the alpha's own median window, so different alphas reach the gates as different cells;
  * UNMEASURED alphas are reported by name with the field that has no proxy.

THE TWO-LANE ORDER. The donated families are per-symbol statistical families, so the panel holds
only instruments `universe_policy.may_hypothesise` admits; a share CFD or an UNCLASSIFIED symbol
is set aside and named. Nothing here ranks alphas, sizes or approves -- the ten gates do.
"""
from __future__ import annotations

from typing import Any

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "alpha101"
CAPABILITY_FAMILY = "dsl_program_search"
LICENCE_EXPECTED = "N/A (published method)"
RUNS_WITHOUT_LIBRARY = True
MIN_BARS = 120


def horizon_bars(horizon: str, timeframe: str = "H1") -> int:
    """'4h' on an H1 panel is 4 bars; '24h' is 24; anything unreadable is one bar."""
    s = str(horizon).strip().lower()
    per_h = {"H1": 1.0, "M30": 2.0, "M15": 4.0, "M5": 12.0, "H4": 0.25}.get(timeframe, 1.0)
    try:
        if s.endswith("h"):
            return max(1, round(float(s[:-1]) * per_h))
        if s.endswith("d"):
            return max(1, round(float(s[:-1]) * 24 * per_h))
    except ValueError:
        return 1
    return 1


def family_for(ic: float, window: int) -> tuple[str, dict[str, int]]:
    """The SIGN picks the family: a positive association is momentum, a negative one reversion;
    the alpha's median window parameterises it."""
    w = max(2, min(int(window), 100))
    if ic > 0:
        return "trend_ma_cross", {"fast_ema": w, "slow_ema": max(3 * w, w + 1)}
    return "mean_reversion_rsi", {"rsi_n": max(2, min(w, 50))}


def lane_split(frames: list[A.BarFrame]) -> tuple[list[A.BarFrame], list[dict[str, Any]],
                                                  dict[str, dict[str, Any]]]:
    from libs.research import formulaic_alphas as F
    classes = F.registry_classes([f.symbol for f in frames])
    kept = [f for f in frames if classes[f.symbol]["hypothesis"]]
    aside = [{"symbol": f.symbol, "why": classes[f.symbol]["why"] or
              "not admitted by universe_policy.may_hypothesise (share CFD or UNCLASSIFIED)"}
             for f in frames if not classes[f.symbol]["hypothesis"]]
    return kept, aside, classes


def run(bundle: A.ResearchBundle) -> ExternalResearchPacket:
    import numpy as np

    from libs.research import formulaic_alphas as F

    frames = [f for f in bundle.frames("H1") if len(f) > MIN_BARS]
    if not frames:
        return A.unmeasured(SYSTEM, bundle, f"no H1 frame carries more than {MIN_BARS} bars")
    kept, aside, classes = lane_split(frames)
    if not kept:
        return A.unmeasured(SYSTEM, bundle, "no frame is in the hypothesis lane: "
                            + "; ".join(f"{r['symbol']}: {r['why']}" for r in aside)[:400])
    deadline = A.Deadline(bundle.compute_budget_s)
    panel = F.panel_from_frames(kept, {s: c["group"] for s, c in classes.items()})
    h = horizon_bars(bundle.horizons[0] if bundle.horizons else "1h")
    with np.errstate(all="ignore"):
        fwd = F.forward_returns(panel, h)
    census = F.census()
    ids = list(F.ALPHAS)
    k = bundle.seed % len(ids)
    order = ids[k:] + ids[:k]          # a pass the budget cuts short starts elsewhere next hour
    reps: list[dict[str, Any]] = []
    cands: list[dict[str, Any]] = []
    trials = 0
    not_reached: list[str] = []
    cells: dict[tuple[str, str, tuple[tuple[str, int], ...]], dict[str, Any]] = {}
    collapsed_by_alpha: dict[str, int] = {}
    for aid in order:
        if deadline.expired():
            not_reached.append(aid)
            continue
        info = census[aid]
        sig, why = F.evaluate(aid, panel)
        if sig is None:
            reps.append({"kind": "formulaic_alpha", "alpha": aid, "status": "UNMEASURED",
                         "why": why, "proxies": info["proxies"]})
            continue
        trials += 1
        with np.errstate(all="ignore"):
            xic, n_rows = F.xs_ic(sig, fwd)
        per_symbol: dict[str, float | None] = {}
        for j, sym in enumerate(panel.symbols):
            idx = np.flatnonzero(panel.present[:, j])
            ic = F.rank_ic(sig[idx, j], fwd[idx, j])
            per_symbol[sym] = None if np.isnan(ic) else ic
            if np.isnan(ic):
                continue
            fam, params = family_for(ic, info["horizon_bars"])
            cell = (sym, fam, tuple(sorted(params.items())))
            if cell in cells:              # same (symbol, family, params): one cell, one charge
                cells[cell]["evidence"].setdefault("collapsed_alphas", []).append(aid)
                collapsed_by_alpha[aid] = collapsed_by_alpha.get(aid, 0) + 1
                continue
            trials += 1
            cand = A.candidate(
                fam, [sym],
                f"{sym} H1: published formulaic alpha {aid} ({info['status'].lower()}"
                f"{', proxies ' + '/'.join(info['proxies']) if info['proxies'] else ''}) scores "
                f"a rank IC of {ic:+.4f} against the {h}-bar forward return over {idx.size} "
                f"bars -- {'momentum' if ic > 0 else 'mean reversion'} at window "
                f"{info['horizon_bars']}",
                horizon=bundle.horizons[0], source=SYSTEM,
                evidence={"alpha": aid, "ic_rank": ic, "n_bars": int(idx.size),
                          "status": info["status"], "proxies": info["proxies"],
                          "parameters": params, "forward_bars": h,
                          "method": "time-series rank IC of a cross-sectional formulaic alpha "
                                    "(desk numpy operators, causal)"})
            cells[cell] = cand
            cands.append(cand)
        reps.append({"kind": "formulaic_alpha", "alpha": aid, "status": info["status"],
                     "proxies": info["proxies"], "xs_ic_mean": None if np.isnan(xic) else xic,
                     "xs_bars": n_rows, "ic_by_symbol": per_symbol,
                     "horizon_bars": info["horizon_bars"], "forward_bars": h,
                     "symbols": list(panel.symbols)})
    counts = F.census_counts(census)
    reps.insert(0, {"kind": "formulaic_alpha_census", "n_alphas": len(F.ALPHAS), **counts,
                    "proxies": F.PROXIES, "no_proxy": F.NO_PROXY,
                    "not_reached_this_pass": not_reached, "set_aside_by_lane": aside,
                    "donated_cells": len(cells),
                    "collapsed_duplicates": sum(collapsed_by_alpha.values()),
                    "collapsed_by_alpha": collapsed_by_alpha,
                    "panel_symbols": list(panel.symbols),
                    "groups": dict(zip(panel.symbols, panel.groups, strict=True)),
                    "source": "Kakushadze (2015) 101 Formulaic Alphas; desk numpy operators"})
    return A.packet(SYSTEM, bundle, trials=trials, representations=reps, candidates=cands,
                    note=f"{len(F.ALPHAS) - len(not_reached)} of {len(F.ALPHAS)} alphas over "
                         f"{len(panel.symbols)} symbols; {counts}")


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
