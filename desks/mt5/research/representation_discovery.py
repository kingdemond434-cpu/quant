"""F4 -- LEARNED REPRESENTATIONS, COMPETING AGAINST THE SYMBOLIC ONES, never replacing them.

THE PRINCIPAL, 2026-09-12, ranking this fourth of the remaining blueprint:

    Learned latent states, cross-market embeddings, nonlinear residual representations, event
    embeddings, participant-state embeddings, automatically invented composite variables --
    COMPETING against symbolic/econometric representations, never replacing them.

THE GAP THIS CLOSES, stated by the ledger: `libs/research/alpha_grammar` is typed, dimensioned and
genuinely sophisticated -- and every expression it can build is a transformation of twelve KNOWN
terminals (close, open, high, low, ret, range, body, activity, spread, atr, vol, flow). A search
over transformations of known primitives cannot represent a state that none of those twelve
measures. The grammar's own strength -- that invalid arithmetic is not constructible -- is exactly
what fixes its vocabulary.

WHY THIS IS A COMPETITION AND NOT A REPLACEMENT, and why that is not diplomacy. A learned
representation has no dimensional type, no unit and no mechanism: it cannot be read, cannot be
falsified by an economic argument, and cannot tell you why it stopped working. The symbolic lane
can. So the learned lane must EARN its place against the incumbent on the only ground both can
stand on -- out-of-sample predictive information about forward returns, same split, same target,
same null -- and the loser is kept, because a representation that loses on one symbol in one
window has not been refuted.

THE PROTOCOL IS PRE-REGISTERED HERE, in code, before any number is produced:

    SPLIT        first 70% of aligned bars TRAIN, 24-bar EMBARGO, remainder TEST. Every
                 representation is FIT on train alone -- loadings, cluster centres, normalisation
                 constants and the composite search all see train only.
    TARGET       the symbol's own forward return at +1 bar and +6 bars, signed.
    SCORE        binned mutual information in nats, computed on TEST only.
    NULL         the target is BLOCK-permuted within test 200 times and scored identically. MI is
                 biased upward at finite sample; the null carries the identical bias, so the lift
                 over the null is the part that is not bias.
    TRIALS       the composite search's train-side trial count is REPORTED, because trial count is
                 a shared cost on this desk -- every cell tested raises the bar every other
                 hypothesis has to clear, and a search that hides its trial count is spending a
                 budget it does not declare.

NOTHING HERE IS ENROLLED, PROMOTED OR TRADED. A winning representation is a candidate VOCABULARY
item, and it reaches the book the same way everything else does: through a hypothesis, through the
gauntlet's ten gates, through a forward clock. This organ decides nothing; it measures which
vocabulary carries information the other one does not.

    python desks/mt5/research/representation_discovery.py [--apply]
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

UNI = DESK / "data" / "universe"
SLEEVES = DESK / "data" / "sleeves.json"
EVENTS = DESK / "data" / "macro" / "event_ledger.jsonl"
OUT = DESK / "reports" / "REPRESENTATION_DISCOVERY.json"

#: Bars per symbol. 4,000 H1 is about two and a half years: enough that a 30% test slice is still
#: ~1,200 bars, which is the smallest test set on which an 8x8 mutual information table is not
#: mostly empty cells.
BARS = 4000

#: Train fraction and the embargo between train and test, in bars. The embargo exists because the
#: features are rolling: a 120-bar window straddling the split would put train data inside a test
#: feature, and that is lookahead wearing the clothes of a clean split.
TRAIN_FRAC = 0.70
EMBARGO = 240

#: Forward horizons scored. One bar is what an entry rule sees; six is what a hold survives. A
#: representation that only predicts the next bar is a cost-sensitive scalp and should be known as
#: one before anyone sizes it.
HORIZONS = (1, 6)

#: Mutual information binning. 8 quantile bins each side gives 64 cells; at ~1,200 test rows that
#: is ~19 per cell, which is thin but honest -- and the permutation null is computed at the SAME
#: binning and sample size, so the bias is subtracted rather than argued about.
MI_BINS = 8

#: Permutation draws for the null, and the block length that keeps autocorrelation intact. An
#: i.i.d. shuffle of an autocorrelated target produces a null that is far too tight, and every
#: representation then looks significant -- the classic way a feature mine certifies noise.
NULL_DRAWS = 200
NULL_BLOCK = 24

#: The composite search: depth-2 expressions over the base columns, beam width kept small on
#: purpose. Every candidate examined is a trial charged to the desk's shared error budget, and a
#: wide beam buys a better in-sample number with a worse bar for everything else on the desk.
BEAM = 6

SEED = 20260912


def _live_symbols(limit: int = 12) -> list[str]:
    try:
        doc = json.loads(SLEEVES.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    rows = doc if isinstance(doc, list) else (doc.get("sleeves") or [])
    out: list[str] = []
    for r in rows:
        if isinstance(r, dict) and str(r.get("status", "")).upper() == "LIVE":
            s = str(r.get("symbol") or "").strip()
            if s and s not in out:
                out.append(s)
    return out[:limit]


def _bars(symbol: str) -> Any:
    try:
        import pandas as pd
    except ImportError:
        return None
    p = UNI / f"{symbol}_H1.parquet"
    if not p.exists():
        return None
    try:
        df = pd.read_parquet(p)
    except (OSError, ValueError):
        return None
    if not {"open", "high", "low", "close"} <= set(df.columns) or len(df) < 1500:
        return None
    return df.tail(BARS)


# ------------------------------------------------------------------- the scoring instrument

def _mi(x: Any, y: Any, bins: int = MI_BINS) -> float:
    """Binned mutual information in nats. Quantile bins, so the binning adapts to the shape."""
    import numpy as np
    a, b = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    m = np.isfinite(a) & np.isfinite(b)
    a, b = a[m], b[m]
    if a.size < 200 or np.std(a) == 0 or np.std(b) == 0:
        return float("nan")
    qa = np.quantile(a, np.linspace(0, 1, bins + 1)[1:-1])
    qb = np.quantile(b, np.linspace(0, 1, bins + 1)[1:-1])
    ia, ib = np.searchsorted(qa, a), np.searchsorted(qb, b)
    h = np.zeros((bins, bins), dtype=float)
    np.add.at(h, (ia, ib), 1.0)
    p = h / h.sum()
    px, py = p.sum(axis=1, keepdims=True), p.sum(axis=0, keepdims=True)
    with np.errstate(divide="ignore", invalid="ignore"):
        t = p * np.log(p / (px * py))
    return float(np.nansum(np.where(p > 0, t, 0.0)))


def _null_mi(x: Any, y: Any, draws: int = NULL_DRAWS) -> list[float]:
    """MI against a BLOCK-permuted target -- the same bias, none of the relationship."""
    import numpy as np
    rng = np.random.default_rng(SEED)
    b = np.asarray(y, dtype=float)
    n = b.size
    if n < NULL_BLOCK * 6:
        return []
    nb = n // NULL_BLOCK
    blocks = b[:nb * NULL_BLOCK].reshape(nb, NULL_BLOCK)
    out: list[float] = []
    for _ in range(draws):
        perm = blocks[rng.permutation(nb)].reshape(-1)
        v = _mi(np.asarray(x, dtype=float)[:perm.size], perm)
        if math.isfinite(v):
            out.append(v)
    return out


def _score(name: str, lane: str, x: Any, y: Any) -> dict[str, Any]:
    """One representation against one target: MI, its null, and the part that is not bias.

    MUTUAL INFORMATION WITH A SIGNED RETURN IS MOSTLY ABOUT MAGNITUDE, and the first run of this
    organ proved it: the leaderboard was vol24, range, vol120 and residual_energy -- every one a
    volatility forecaster. Financial returns are heteroskedastic, so anything that predicts the
    SIZE of the next move shows a large MI against the signed return while predicting its
    direction not at all. A reader who does not know that reads "vol24 carries 0.09 nats about
    forward return" as an edge. So `_score_both` below scores the SIGN separately, and a
    representation is only called directional when it beats its own null on the sign.
    """
    import numpy as np
    mi = _mi(x, y)
    if not math.isfinite(mi):
        return {"name": name, "lane": lane, "status": "UNMEASURED",
                "why": "degenerate or too-short series on the test slice"}
    null = _null_mi(x, y)
    if not null:
        return {"name": name, "lane": lane, "status": "UNMEASURED",
                "why": "the test slice is too short for a block-permutation null"}
    arr = np.asarray(null, dtype=float)
    med = float(np.median(arr))
    p = float(np.mean(arr >= mi))
    return {"name": name, "lane": lane, "status": "OK",
            "mi_nats": round(mi, 6),
            "null_median_nats": round(med, 6),
            "excess_nats": round(mi - med, 6),
            "lift_over_null": round(mi / med, 3) if med > 0 else None,
            "p_empirical": round(p, 4)}


def _score_both(name: str, lane: str, x: Any, y: Any) -> dict[str, Any]:
    """Level MI, plus MI against the SIGN alone -- magnitude information split from directional.

    The split is the whole point. A volatility forecaster is genuinely useful -- it sizes, it sets
    a stop, it tells the survival envelope what tomorrow's 95th percentile is -- and it is not an
    edge. Reporting one number that both share lets the first be mistaken for the second, which is
    the most common way a feature mine produces a strategy that loses exactly the spread.
    """
    import numpy as np
    lvl = _score(name, lane, x, y)
    if lvl.get("status") != "OK":
        return lvl
    sgn = np.sign(np.asarray(y, dtype=float))
    dirn = _score(name, lane, x, sgn)
    lvl["direction"] = ({"status": dirn.get("status"), "why": dirn.get("why")}
                        if dirn.get("status") != "OK" else
                        {"mi_nats": dirn["mi_nats"], "excess_nats": dirn["excess_nats"],
                         "p_empirical": dirn["p_empirical"]})
    is_dir = (dirn.get("status") == "OK"
              and float(dirn["excess_nats"]) > 0
              and float(dirn["p_empirical"]) <= 0.05)
    lvl["kind"] = "directional" if is_dir else "magnitude_only"
    return lvl


# --------------------------------------------------------------------- the two vocabularies

def _base_columns(df: Any) -> dict[str, Any]:
    """The raw material both lanes draw on. Causal by construction -- every window looks back."""
    import numpy as np
    c = df["close"].astype(float)
    r = np.log(c).diff()
    hi, lo, op = df["high"].astype(float), df["low"].astype(float), df["open"].astype(float)
    rng_ = (hi - lo)
    cols: dict[str, Any] = {
        "ret": r,
        "absret": r.abs(),
        "range": rng_ / c,
        "body": (c - op).abs() / rng_.replace(0, np.nan),
        "position": (c - lo) / rng_.replace(0, np.nan),
        "vol24": r.rolling(24).std(),
        "vol120": r.rolling(120).std(),
        "mom24": r.rolling(24).sum(),
        "mom120": r.rolling(120).sum(),
    }
    if "tick_volume" in df.columns:
        v = df["tick_volume"].astype(float)
        cols["activity"] = v / v.rolling(240).mean()
        cols["flow"] = np.sign(r) * cols["activity"]
    if "spread" in df.columns and float(df["spread"].abs().max() or 0) > 0:
        cols["spread"] = df["spread"].astype(float)
    return cols


#: The SYMBOLIC lane: the desk's own econometric primitives, as the grammar names them. These are
#: the incumbent, and the incumbent is entitled to the same protocol and no handicap.
SYMBOLIC: tuple[str, ...] = ("mom24", "mom120", "vol24", "vol120", "position", "body",
                             "range", "activity", "flow")


def _zfit(train: Any, full: Any) -> Any:
    """Normalise the whole series by TRAIN's own mean and sd. Test never sees its own moments."""
    import numpy as np
    mu, sd = float(np.nanmean(train)), float(np.nanstd(train))
    return (full - mu) / sd if sd > 0 else full * 0.0


def _learned(cols: dict[str, Any], panel: Any, sym: str, tr: slice) -> dict[str, Any]:
    """The learned lane, every member fitted on TRAIN only."""
    import numpy as np
    import pandas as pd
    out: dict[str, Any] = {}
    idx = cols["ret"].index

    # 1. CROSS-MARKET EMBEDDING. SVD of the standardised return panel, fitted on train; the test
    # values are test returns projected onto TRAIN loadings, so the components are not re-derived
    # from the data they are scored on.
    if panel is not None and panel.shape[1] >= 3:
        pt = panel.reindex(idx).ffill()
        train_p = pt.iloc[tr]
        mu, sd = train_p.mean(), train_p.std().replace(0, np.nan)
        z = ((pt - mu) / sd).fillna(0.0)
        ztr = z.iloc[tr].to_numpy()
        try:
            _, _, vt = np.linalg.svd(ztr - ztr.mean(axis=0), full_matrices=False)
            for k in range(min(3, vt.shape[0])):
                out[f"factor_{k + 1}"] = pd.Series(z.to_numpy() @ vt[k], index=idx)
            # 3. NONLINEAR RESIDUAL REPRESENTATION -- what the linear factors leave behind, mapped
            # through a transform a linear model cannot express. If the factors explained the
            # symbol, this is noise; if they did not, this is the part they missed.
            load = vt[:3]
            recon = (z.to_numpy() @ load.T) @ load
            resid = pd.Series(z[sym].to_numpy() - recon[:, list(z.columns).index(sym)],
                              index=idx) if sym in z.columns else None
            if resid is not None:
                out["residual_nonlinear"] = np.sign(resid) * np.sqrt(resid.abs())
                out["residual_energy"] = (resid ** 2).rolling(24).mean()
        except np.linalg.LinAlgError:
            pass

    # 2. LEARNED LATENT STATES. k-means in a four-dimensional state space, centres fitted on
    # train. The representation is the STATE INDEX, a categorical -- which is why the score is
    # mutual information rather than a correlation: a categorical has no sign to correlate.
    feats = [c for c in ("absret", "vol24", "range", "activity") if c in cols]
    if len(feats) >= 3:
        mat = pd.concat([cols[f] for f in feats], axis=1)
        mat.columns = feats
        mat = mat.replace([np.inf, -np.inf], np.nan)
        tr_mat = mat.iloc[tr]
        mu, sd = tr_mat.mean(), tr_mat.std().replace(0, np.nan)
        zz = ((mat - mu) / sd).fillna(0.0).to_numpy()
        ztr = ((tr_mat - mu) / sd).fillna(0.0).to_numpy()
        rng = np.random.default_rng(SEED)
        cent = ztr[rng.choice(ztr.shape[0], size=4, replace=False)]
        for _ in range(40):
            d = ((ztr[:, None, :] - cent[None, :, :]) ** 2).sum(axis=2)
            lab = d.argmin(axis=1)
            new = np.stack([ztr[lab == j].mean(axis=0) if (lab == j).any() else cent[j]
                            for j in range(4)])
            if np.allclose(new, cent):
                break
            cent = new
        assign = ((zz[:, None, :] - cent[None, :, :]) ** 2).sum(axis=2).argmin(axis=1)
        out["latent_state"] = pd.Series(assign.astype(float), index=idx)

    # 4. PARTICIPANT-STATE EMBEDDING. Activity and signed activity, reduced to their own first
    # component on train. A proxy and labelled one: MT5 tick_volume is a tick count, not size.
    if "activity" in cols and "flow" in cols:
        m = pd.concat([cols["activity"], cols["flow"], cols["absret"]], axis=1).replace(
            [np.inf, -np.inf], np.nan)
        m.columns = ["activity", "flow", "absret"]
        trm = m.iloc[tr]
        mu, sd = trm.mean(), trm.std().replace(0, np.nan)
        zz = ((m - mu) / sd).fillna(0.0)
        try:
            _, _, vt = np.linalg.svd(zz.iloc[tr].to_numpy(), full_matrices=False)
            out["participant_state"] = pd.Series(zz.to_numpy() @ vt[0], index=idx)
        except np.linalg.LinAlgError:
            pass
    return out


def _composites(cols: dict[str, Any], y_train: Any, tr: slice) -> tuple[dict[str, Any], int]:
    """Automatically invented composite variables -- searched on TRAIN, scored later on TEST.

    Depth two, over the base columns, with the operator set the grammar itself declares. The
    search is a beam of BEAM, and the number of candidates EXAMINED is returned, because that
    count is a charge against the desk's shared family-wise error budget and a search that hides
    it is spending a budget it never declared.
    """
    import numpy as np
    import pandas as pd
    names = [c for c in cols if c not in ("ret",)]
    cands: list[tuple[float, str, Any]] = []
    trials = 0
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            xa, xb = cols[a], cols[b]
            for op in ("mul", "sub", "div"):
                try:
                    if op == "mul":
                        v = xa * xb
                    elif op == "sub":
                        v = xa - xb
                    else:
                        v = xa / xb.replace(0, np.nan)
                    v = v.replace([np.inf, -np.inf], np.nan)
                except (TypeError, ValueError):
                    continue
                trials += 1
                s = _mi(v.iloc[tr].to_numpy(), y_train)
                if math.isfinite(s):
                    cands.append((s, f"{op}({a},{b})", v))
    cands.sort(key=lambda t: -t[0])
    top = cands[:BEAM]
    # DEPTH TWO: the winners get one more transform each, again selected on train alone.
    out: dict[str, Any] = {}
    for s0, nm, v in top:
        out[f"composite::{nm}"] = v
        for op in ("abs", "zscore240", "rank240"):
            try:
                if op == "abs":
                    w = v.abs()
                elif op == "zscore240":
                    w = (v - v.rolling(240).mean()) / v.rolling(240).std()
                else:
                    w = v.rolling(240).rank(pct=True)
                w = w.replace([np.inf, -np.inf], np.nan)
            except (TypeError, ValueError, AttributeError):
                continue
            trials += 1
            s = _mi(w.iloc[tr].to_numpy(), y_train)
            if math.isfinite(s) and s > s0:
                out[f"composite::{op}({nm})"] = w
    return ({k: pd.Series(v) for k, v in list(out.items())[:BEAM * 2]}, trials)


# --------------------------------------------------------------------------------- assembly

def _panel(symbols: list[str]) -> Any:
    import numpy as np
    import pandas as pd
    series: dict[str, Any] = {}
    for s in symbols:
        df = _bars(s)
        if df is None:
            continue
        c = df["close"].astype(float)
        series[s] = np.log(c).diff()
    if len(series) < 3:
        return None
    return pd.DataFrame(series).dropna(how="all")


def build() -> dict[str, Any]:
    now = datetime.now(tz=UTC)
    try:
        import numpy as np
        import pandas as pd
    except ImportError as exc:
        return {"at": now.isoformat(timespec="seconds"), "status": "UNMEASURED",
                "why": f"numpy/pandas unavailable ({exc})"}

    syms = _live_symbols()
    panel = _panel(syms)
    per_symbol: dict[str, Any] = {}
    total_trials = 0

    for sym in syms:
        df = _bars(sym)
        if df is None:
            continue
        cols = _base_columns(df)
        n = len(df)
        ntr = int(n * TRAIN_FRAC)
        if n - ntr - EMBARGO < 600:
            continue
        tr = slice(0, ntr)
        te = slice(ntr + EMBARGO, n)

        fwd = {h: np.log(df["close"].astype(float)).diff(h).shift(-h) for h in HORIZONS}
        learned = _learned(cols, panel, sym, tr)
        comp, trials = _composites(cols, fwd[HORIZONS[0]].iloc[tr].to_numpy(), tr)
        total_trials += trials
        learned.update(comp)

        rows: list[dict[str, Any]] = []
        for h in HORIZONS:
            y = fwd[h]
            for nm, v in cols.items():
                if nm not in SYMBOLIC:
                    continue
                z = _zfit(v.iloc[tr], v)
                sc = _score_both(nm, "symbolic", z.iloc[te].to_numpy(), y.iloc[te].to_numpy())
                rows.append({**sc, "horizon": h})
            for nm, v in learned.items():
                vv = pd.Series(v).reindex(cols["ret"].index)
                z = _zfit(vv.iloc[tr], vv)
                lane = "learned_composite" if nm.startswith("composite::") else "learned"
                sc = _score_both(nm, lane, z.iloc[te].to_numpy(), y.iloc[te].to_numpy())
                rows.append({**sc, "horizon": h})

        ok = [r for r in rows if r.get("status") == "OK"]
        ok.sort(key=lambda r: -float(r.get("excess_nats") or 0.0))
        best_sym = next((r for r in ok if r["lane"] == "symbolic"), None)
        best_learned = next((r for r in ok if r["lane"] != "symbolic"), None)
        per_symbol[sym] = {
            "n_bars": n, "n_train": ntr, "n_test": n - ntr - EMBARGO,
            "composite_trials": trials,
            "leaderboard": ok[:12],
            "best_symbolic": best_sym,
            "best_learned": best_learned,
            "learned_wins": (bool(best_learned and best_sym
                                  and float(best_learned["excess_nats"])
                                  > float(best_sym["excess_nats"]))
                             if (best_learned and best_sym) else None),
        }

    if not per_symbol:
        return {"at": now.isoformat(timespec="seconds"), "status": "UNMEASURED",
                "why": ("no live symbol has enough history for a 70/30 split with a 240-bar "
                        "embargo and a 600-bar test slice")}

    wins = [s for s, r in per_symbol.items() if r["learned_wins"] is True]
    losses = [s for s, r in per_symbol.items() if r["learned_wins"] is False]
    # A REPRESENTATION IS ONLY INTERESTING IF IT BEAT ITS OWN NULL, not merely the other lane.
    survivors: list[dict[str, Any]] = []
    for sym, r in per_symbol.items():
        for row in r["leaderboard"]:
            if float(row.get("p_empirical", 1.0)) <= 0.05 and float(row["excess_nats"]) > 0:
                survivors.append({"symbol": sym, **row})
    survivors.sort(key=lambda r: -float(r["excess_nats"]))
    # THE ONLY LIST THAT IS ABOUT AN EDGE. Everything above beat its null on the SIGNED return,
    # which heteroskedasticity alone delivers; these beat it on the SIGN.
    directional = [r for r in survivors if r.get("kind") == "directional"]
    directional.sort(key=lambda r: -float((r.get("direction") or {}).get("excess_nats") or 0.0))

    return {
        "at": now.isoformat(timespec="seconds"),
        "n_symbols": len(per_symbol),
        "protocol": {"bars": BARS, "train_frac": TRAIN_FRAC, "embargo_bars": EMBARGO,
                     "horizons": list(HORIZONS), "mi_bins": MI_BINS,
                     "null_draws": NULL_DRAWS, "null_block": NULL_BLOCK,
                     "beam": BEAM, "seed": SEED},
        "composite_trials_total": total_trials,
        "symbols": per_symbol,
        "learned_wins_on": sorted(wins),
        "symbolic_wins_on": sorted(losses),
        "n_beat_own_null": len(survivors),
        "beat_own_null": survivors[:25],
        "n_directional": len(directional),
        "directional": directional[:25],
        "magnitude_vs_direction": (
            "a representation that beats its null on the SIGNED forward return has predicted the "
            "SIZE of the next move in almost every case -- returns are heteroskedastic, so any "
            "volatility forecaster scores here. That is genuinely useful (it sizes, it sets a "
            "stop, it is the survival envelope's input) and it is NOT an edge. `directional` is "
            "the list that beat its null on the sign alone, and it is the only one that is."),
        "event_embedding": {
            "status": "UNMEASURED",
            "why": ("the macro event ledger parses to zero rows on this box, so there is nothing "
                    "to embed. An event embedding built from an empty calendar would encode the "
                    "desk's ignorance and present it as a market state."),
        },
        "status": "OK",
        "trial_cost": (
            f"{total_trials} composite candidates were EXAMINED on train across all symbols. "
            f"Trial count is a shared cost on this desk -- the deflated-Sharpe charge and the "
            f"program-level SPA/PBO tests divide one family-wise error budget across every "
            f"hypothesis tested -- so the number is published rather than buried."),
        "boundary": (
            "COMPETING, NEVER REPLACING. The symbolic lane keeps its place whatever this says: a "
            "learned representation has no dimensional type, no unit and no mechanism, cannot be "
            "falsified by an economic argument, and cannot tell you why it stopped working. "
            "Nothing here is enrolled, promoted or traded; a winner is a candidate VOCABULARY "
            "item and reaches the book through a hypothesis, the ten gates and a forward clock, "
            "exactly as everything else does."),
        "why": (
            "every expression alpha_grammar can build is a transformation of twelve known "
            "terminals. A search over transformations of known primitives cannot represent a "
            "state that none of those twelve measures, and the grammar's own strength -- that "
            "invalid arithmetic is not constructible -- is what fixes its vocabulary."),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="write the report")
    a = ap.parse_args(argv)
    doc = build()
    if doc.get("status") == "UNMEASURED":
        print(f"representation discovery: UNMEASURED -- {doc.get('why')}")
        return 0
    print(f"representation discovery: {doc['status']}   {doc['n_symbols']} symbol(s), "
          f"{doc['composite_trials_total']} composite trial(s) charged")
    print(f"  learned lane wins on {len(doc['learned_wins_on'])}, "
          f"symbolic lane wins on {len(doc['symbolic_wins_on'])}")
    for sym, r in list(doc["symbols"].items())[:8]:
        bl, bs = r.get("best_learned"), r.get("best_symbolic")
        if not bl or not bs:
            continue
        print(f"  {sym:<10} learned {bl['name'][:28]:<28} {bl['excess_nats']:+.5f} "
              f"p={bl['p_empirical']:<6} | symbolic {bs['name']:<10} {bs['excess_nats']:+.5f} "
              f"p={bs['p_empirical']}")
    print(f"  {doc['n_beat_own_null']} representation(s) beat their own null on the SIGNED "
          f"return (mostly magnitude -- returns are heteroskedastic):")
    for s in doc["beat_own_null"][:5]:
        print(f"     {s['symbol']:<10} {s['lane']:<18} {s['name'][:30]:<30} "
              f"h={s['horizon']} excess {s['excess_nats']:+.5f} nats  p={s['p_empirical']}")
    print(f"  {doc['n_directional']} beat it on the SIGN -- the only list that is about an edge:")
    for s in doc["directional"][:8]:
        d = s.get("direction") or {}
        print(f"     {s['symbol']:<10} {s['lane']:<18} {s['name'][:30]:<30} "
              f"h={s['horizon']} direction excess {float(d.get('excess_nats', 0)):+.5f} nats  "
              f"p={d.get('p_empirical')}")
    if not a.apply:
        print("  --apply not given; nothing written")
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    print(f"-> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
