"""TWO MORE LABS FROM OTHER SCIENCES ON THE ROW STREAM (Tier S layer 43).

`cross_science.py` carries eight labs (queueing, control, information, ecology, signal, dynamical,
network, bayesian) and names operations research only as the researcher market's MILP allocator --
an OR tool pointed at the desk, never an OR MECHANISM looked for in the market. These two labs read
the same per-bar row stream the others read (H1 returns and tick activity, one row per bar) and
emit the same structured hit rows (`cross_science._row`: lab, statistic, null, claim, falsifier).

  operations   INVENTORY CONTROL. The dealer-inventory models of operations research
               (Ho-Stoll, Amihud-Mendelson: a market maker holding inventory skews quotes to lay
               it off) predict that signed order flow ACCUMULATED over a day is released
               afterwards. The inventory proxy is the 24-bar sum of sign(return) x tick activity,
               z-scored over 120 bars; the statistic is its correlation with the NEXT bar's
               return, judged against a BLOCK-PERMUTED null (48-bar blocks, so the proxy keeps
               its own autocorrelation) at the 99th percentile. Negative = inventory release
               (the dealer lays off), positive = the dealer leans with the flow.

  motif        RECURRING MOTIFS. Motif discovery (bioinformatics' recurring subsequences) over
               the sign alphabet of the bar stream, restricted on purpose to the motifs the alpha
               grammar can state EXACTLY -- runs of L same-sign bars, L in 2/3/5/8, up and down.
               The indicator `min(sign(ret), L)` is +1 only on an L-bar up run (`max` -1 only on
               a down run), so the expression the factory judges IS the motif, not a proxy for
               it. Each motif's next-bar mean return is a t-statistic judged at a Bonferroni bar
               over every motif examined on that symbol; follow-through and reversal are both
               claims, and the measured sign decides which one is queued.

No lab here sizes, caps or vetoes anything; each only emits a hypothesis for the gauntlet to judge.
"""
from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

import numpy as np
import numpy.typing as npt
import pandas as pd
from scipy.stats import norm

from libs.tiers.cross_science import _row

F = npt.NDArray[np.float64]

INVENTORY_BARS, Z_BARS, BLOCK = 24, 120, 48
MOTIF_LENGTHS = (2, 3, 5, 8)
MIN_MOTIF_COUNT = 30


def _block_permute(x: F, block: int, rng: np.random.Generator) -> F:
    n = len(x)
    k = max(1, n // block)
    blocks = [x[i * block:(i + 1) * block] for i in range(k)]
    tail = x[k * block:]
    order = rng.permutation(k)
    return np.concatenate([blocks[i] for i in order] + [tail])


def inventory_z(r: F, v: F) -> F:
    """The dealer-inventory proxy: 24-bar signed activity, z-scored over 120 bars (causal)."""
    act = v / (float(np.mean(v)) or 1.0)
    inv = pd.Series(np.sign(r) * act).rolling(INVENTORY_BARS).sum()
    mu = inv.rolling(Z_BARS).mean()
    sd = inv.rolling(Z_BARS).std()
    out: F = ((inv - mu) / sd.replace(0.0, np.nan)).to_numpy(dtype=float)
    return out


def operations_lab(panel: Mapping[str, F], volumes: Mapping[str, F], top: int = 10,
                   n_null: int = 60, seed: int = 0) -> list[dict[str, Any]]:
    rng = np.random.default_rng(seed)
    rows = []
    for s in sorted(set(panel) & set(volumes)):
        r = np.asarray(panel[s], dtype=float)
        v = np.asarray(volumes[s], dtype=float)
        n = min(len(r), len(v))
        if n < 500:
            continue
        r, v = r[-n:], v[-n:]
        if not np.isfinite(v).all() or float(v.sum()) <= 0:
            continue
        z = inventory_z(r, v)
        x, y = z[:-1], r[1:]
        ok = np.isfinite(x) & np.isfinite(y)
        x, y = x[ok], y[ok]
        if len(x) < 300 or x.std() == 0 or y.std() == 0:
            continue
        c = float(np.corrcoef(x, y)[0, 1])
        null = [abs(float(np.corrcoef(_block_permute(x, BLOCK, rng), y)[0, 1]))
                for _ in range(n_null)]
        thr = float(np.quantile(null, 0.99))
        if abs(c) <= thr:
            continue
        mode = ("inventory release: accumulated signed flow is laid off (reversal)" if c < 0
                else "dealers lean with accumulated flow (continuation)")
        rows.append(_row("operations", [s], c * math.sqrt(len(x)),
                         f"block-permuted |corr| 99% {thr:.4f}",
                         f"{s}: 24-bar signed-activity inventory predicts the next bar "
                         f"(corr {c:+.4f}) -- {mode}",
                         "the inventory correlation falls inside the block-permuted null out of "
                         "sample", corr=round(c, 6), model="dealer_inventory"))
    rows.sort(key=lambda r: -abs(float(r["statistic"])))
    return rows[:top]


def run_indicator(r: F, length: int, up: bool) -> F:
    """1.0 on the bar that completes an L-bar same-sign run, else 0.0 (causal)."""
    s = pd.Series(np.sign(r))
    if up:
        up_run: F = (s.rolling(length).min() > 0).to_numpy(dtype=float)
        return up_run
    down_run: F = (s.rolling(length).max() < 0).to_numpy(dtype=float)
    return down_run


def motif_lab(panel: Mapping[str, F], top: int = 10) -> list[dict[str, Any]]:
    rows = []
    n_motifs = 2 * len(MOTIF_LENGTHS)
    bar = float(norm.ppf(1 - 0.025 / n_motifs))
    for s, r0 in sorted(panel.items()):
        r = np.asarray(r0, dtype=float)
        if len(r) < 500:
            continue
        nxt = r[1:]
        sd_all = float(nxt.std()) or 1e-12
        for length in MOTIF_LENGTHS:
            for up in (True, False):
                hit = run_indicator(r, length, up)[:-1] > 0
                cnt = int(hit.sum())
                if cnt < MIN_MOTIF_COUNT:
                    continue
                f = nxt[hit]
                m = float(f.mean())
                t = m / (sd_all / math.sqrt(cnt))
                if abs(t) < bar:
                    continue
                word = ("U" if up else "D") * length
                follow = "continues" if (m > 0) == up else "reverses"
                rows.append(_row("motif", [s], t, f"Bonferroni |t| {bar:.2f} over {n_motifs} "
                                 "motifs", f"{s}: after the motif {word} ({cnt} occurrences) the "
                                 f"next bar {follow} (mean {m:+.6f})",
                                 "the motif's next-bar mean is inside the Bonferroni bar out of "
                                 "sample", motif=word, length=length, up=up,
                                 follow=follow, count=cnt))
    rows.sort(key=lambda r: -abs(float(r["statistic"])))
    return rows[:top]


def expression(hit: Mapping[str, Any]) -> str | None:
    """The lab's mechanism as an alpha-grammar expression, validated by the tests."""
    lab = str(hit.get("lab") or "")
    if lab == "operations":
        inv = f"zscore(sum(mul(sign(ret), activity), {INVENTORY_BARS}), {Z_BARS})"
        return f"neg({inv})" if float(hit.get("corr") or 0.0) < 0 else inv
    if lab == "motif":
        n = int(hit.get("length") or 0)
        if n not in MOTIF_LENGTHS:
            return None
        if hit.get("up"):
            ind = f"add(min(sign(ret), {n}), abs(min(sign(ret), {n})))"     # +2 on the run
        else:
            ind = f"sub(max(sign(ret), {n}), abs(max(sign(ret), {n})))"     # -2 on the run
        return ind if hit.get("follow") == "continues" else f"neg({ind})"
    return None


def run_all(panel: Mapping[str, F], volumes: Mapping[str, F] | None = None
            ) -> dict[str, list[dict[str, Any]]]:
    out = {"motif": motif_lab(panel)}
    out["operations"] = operations_lab(panel, volumes) if volumes else []
    return out
