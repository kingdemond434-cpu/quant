"""Market event tokenization: turning price into a discrete alphabet a sequence model can read.

THE HYPOTHESIS THIS EXISTS TO TEST

    Can a self-supervised model discover microstructure grammar that our
    human-defined SMC state machine misses?

Not "BPE for ticks". Byte-pair encoding was built around repeated symbol fragments in text, and
markets carry continuous numeric state; a tokenizer that assumes text structure imports an
assumption it cannot defend. BPE-style merging of recurrent motifs is ONE candidate encoder here,
entered as a competitor and kept only if it wins.

THE TOKENIZER IS ITSELF THE EXPERIMENT

Five encoders over identical bars and one downstream objective:

    quantile      fixed quantile discretization of returns -- the honest baseline
    event         hand-specified market events (the vocabulary below)
    vq            k-means codebook over standardised feature vectors, VQ-style
    bpe           greedy merging of the most frequent adjacent pair, over event tokens
    continuous    NO discretization at all

The continuous baseline is mandatory and is the one most likely to win. Without it a tokenizer's
victory may only be a victory over the other tokenizers, which answers a question nobody asked.

WHAT A REDISCOVERY WOULD MEAN

If a learned encoder independently produces a recurring motif matching

    SWEEP -> DISPLACEMENT -> RETRACEMENT

that is strong evidence in both directions at once: it corroborates the hand-built state machine,
and it shows the encoder finds real structure rather than fitting noise. `find_motifs` looks for
exactly that, and a hit is recorded as a result rather than assumed.

NOTHING HERE IS A SIGNAL. These are representations. They enter the ordinary promotion protocol
with their full trial count attached, and a vocabulary of 40 tokens searched over 5 encoders is
200 trials before a single parameter is tuned -- see mt5desk.canonical.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

#: The hand-specified vocabulary. Deliberately small and mechanical: every token is computable
#: from OHLC alone, so the encoder runs on any symbol without depth, news or a broker feed.
EVENT_TOKENS = (
    "UP_SMALL", "UP_LARGE", "DOWN_SMALL", "DOWN_LARGE", "FLAT",
    "VOL_BURST", "VOL_COLLAPSE",
    "SWEEP_HIGH", "SWEEP_LOW",
    "DISPLACEMENT_UP", "DISPLACEMENT_DOWN",
    "FVG_UP", "FVG_DOWN",
    "SPREAD_EXPANSION", "QUOTE_GAP",
    "RANGE_EXPANSION", "RANGE_CONTRACTION",
)

#: Return magnitude, in units of trailing realised vol, separating SMALL from LARGE.
_LARGE_SIGMA = 1.0
#: Below this the bar is FLAT rather than a small move -- noise should not become a token.
_FLAT_SIGMA = 0.25
#: Displacement: a directional move this many sigma with high close-to-range efficiency.
_DISPLACEMENT_SIGMA = 1.5
_DISPLACEMENT_EFFICIENCY = 0.6


@dataclass
class Encoding:
    """A token stream plus the provenance needed to reproduce and to charge it for its search."""
    name: str
    tokens: list[str]
    index: pd.DatetimeIndex
    vocab: list[str]
    n_trials: int = 1
    meta: dict = field(default_factory=dict)

    def __len__(self) -> int:
        return len(self.tokens)

    def counts(self) -> Counter:
        return Counter(self.tokens)


def _features(h1: pd.DataFrame, lookback: int = 20) -> pd.DataFrame:
    """The continuous state every encoder discretizes. One place, so encoders differ only in HOW."""
    o, h, l, c = (h1[k].astype(float) for k in ("open", "high", "low", "close"))
    rng = (h - l).replace(0.0, np.nan)
    ret = np.log(c).diff()
    sigma = ret.rolling(lookback).std()
    f = pd.DataFrame(index=h1.index)
    f["ret"] = ret
    f["ret_sigma"] = ret / sigma
    f["range"] = rng
    f["range_z"] = (rng - rng.rolling(lookback).mean()) / rng.rolling(lookback).std()
    f["efficiency"] = (c - o).abs() / rng            # close-to-open over the whole bar's travel
    f["upper_wick"] = (h - np.maximum(o, c)) / rng
    f["lower_wick"] = (np.minimum(o, c) - l) / rng
    f["vol_z"] = (sigma - sigma.rolling(lookback).mean()) / sigma.rolling(lookback).std()
    # Sweep: took out the prior N-bar extreme and closed back inside it.
    ph, pl = h.rolling(lookback).max().shift(1), l.rolling(lookback).min().shift(1)
    f["sweep_high"] = (h > ph) & (c < ph)
    f["sweep_low"] = (l < pl) & (c > pl)
    # Fair value gap: a three-bar imbalance where bar1 and bar3 do not overlap.
    f["fvg_up"] = l > h.shift(2)
    f["fvg_down"] = h < l.shift(2)
    f["gap"] = (o - c.shift(1)).abs() / rng.shift(1)
    return f


# ------------------------------------------------------------------- the encoders

def encode_events(h1: pd.DataFrame, lookback: int = 20) -> Encoding:
    """Hand-specified market events. The interpretable competitor.

    ORDER OF TESTS IS THE PRIORITY ORDER, and it is a modelling choice rather than a detail: a bar
    can be a sweep AND a large up move, and emitting one token per bar forces a decision about
    which fact matters more. Structure beats magnitude here, because magnitude is already
    recoverable from the quantile encoder.
    """
    f = _features(h1, lookback)
    out: list[str] = []
    for _, r in f.iterrows():
        rs, eff, rz = r["ret_sigma"], r["efficiency"], r["range_z"]
        if not np.isfinite(rs):
            out.append("FLAT")
            continue
        if r["sweep_high"]:
            tok = "SWEEP_HIGH"
        elif r["sweep_low"]:
            tok = "SWEEP_LOW"
        elif np.isfinite(r["gap"]) and r["gap"] > 0.5:
            tok = "QUOTE_GAP"
        elif abs(rs) > _DISPLACEMENT_SIGMA and np.isfinite(eff) and eff > _DISPLACEMENT_EFFICIENCY:
            tok = "DISPLACEMENT_UP" if rs > 0 else "DISPLACEMENT_DOWN"
        elif bool(r["fvg_up"]):
            tok = "FVG_UP"
        elif bool(r["fvg_down"]):
            tok = "FVG_DOWN"
        elif np.isfinite(r["vol_z"]) and r["vol_z"] > 1.5:
            tok = "VOL_BURST"
        elif np.isfinite(r["vol_z"]) and r["vol_z"] < -1.5:
            tok = "VOL_COLLAPSE"
        elif np.isfinite(rz) and rz > 1.5:
            tok = "RANGE_EXPANSION"
        elif np.isfinite(rz) and rz < -1.5:
            tok = "RANGE_CONTRACTION"
        elif abs(rs) < _FLAT_SIGMA:
            tok = "FLAT"
        elif abs(rs) > _LARGE_SIGMA:
            tok = "UP_LARGE" if rs > 0 else "DOWN_LARGE"
        else:
            tok = "UP_SMALL" if rs > 0 else "DOWN_SMALL"
        out.append(tok)
    return Encoding("event", out, h1.index, list(EVENT_TOKENS), n_trials=1,
                    meta={"lookback": lookback})


def encode_quantile(h1: pd.DataFrame, n_bins: int = 8, lookback: int = 20) -> Encoding:
    """Equal-frequency bins of vol-normalised returns. The honest baseline.

    Uses TRAILING quantiles, not whole-sample ones. Fitting bin edges on the full series leaks
    the future into the tokenization -- every bar would be labelled using the distribution of
    bars that had not happened yet, which is the day_states defect wearing a different hat.
    """
    f = _features(h1, lookback)
    z = f["ret_sigma"]
    edges = z.rolling(250, min_periods=60).quantile(0.5)      # placeholder to force alignment
    toks: list[str] = []
    hist: list[float] = []
    for v in z.to_numpy():
        if not np.isfinite(v) or len(hist) < 60:
            toks.append("Q_NA")
        else:
            qs = np.quantile(hist, np.linspace(0, 1, n_bins + 1)[1:-1])
            toks.append(f"Q{int(np.searchsorted(qs, v))}")
        if np.isfinite(v):
            hist.append(float(v))
            if len(hist) > 1000:
                hist.pop(0)
    del edges
    return Encoding("quantile", toks, h1.index,
                    ["Q_NA"] + [f"Q{i}" for i in range(n_bins)],
                    n_trials=1, meta={"n_bins": n_bins, "trailing": True})


def encode_vq(h1: pd.DataFrame, k: int = 12, lookback: int = 20,
              seed: int = 0, warmup: int = 500) -> Encoding:
    """Vector quantization: a k-means codebook over standardised feature vectors.

    THE CODEBOOK IS FIT ON THE WARMUP WINDOW ONLY and then frozen. Fitting on the whole series
    would let every token carry information from the end of the sample, and the resulting
    "discovery" would be guaranteed.
    """
    f = _features(h1, lookback)
    cols = ["ret_sigma", "range_z", "efficiency", "upper_wick", "lower_wick", "vol_z"]
    x = f[cols].to_numpy(dtype=float)
    ok = np.isfinite(x).all(axis=1)
    if ok.sum() < max(warmup, k * 10):
        return Encoding("vq", ["V_NA"] * len(f), h1.index, ["V_NA"], n_trials=1,
                        meta={"status": "INSUFFICIENT_DATA", "usable_rows": int(ok.sum())})
    idx = np.flatnonzero(ok)
    fit_rows = x[idx[:warmup]]
    mu, sd = fit_rows.mean(axis=0), fit_rows.std(axis=0)
    sd[sd == 0] = 1.0
    rng = np.random.default_rng(seed)
    cent = ((fit_rows - mu) / sd)[rng.choice(len(fit_rows), k, replace=False)].copy()
    for _ in range(25):                                  # Lloyd's algorithm, fixed iterations
        d = ((fit_rows - mu) / sd)[:, None, :] - cent[None, :, :]
        lab = (d ** 2).sum(axis=2).argmin(axis=1)
        for j in range(k):
            if (lab == j).any():
                cent[j] = ((fit_rows - mu) / sd)[lab == j].mean(axis=0)
    toks = []
    for i in range(len(x)):
        if not ok[i]:
            toks.append("V_NA")
            continue
        z = (x[i] - mu) / sd
        toks.append(f"V{int(((z[None, :] - cent) ** 2).sum(axis=1).argmin())}")
    return Encoding("vq", toks, h1.index, ["V_NA"] + [f"V{i}" for i in range(k)],
                    n_trials=1, meta={"k": k, "codebook_fit_rows": int(warmup), "frozen": True})


def encode_bpe(base: Encoding, n_merges: int = 20) -> Encoding:
    """Greedy byte-pair merging over an existing token stream.

    Repeatedly merges the most frequent adjacent pair into one symbol, so recurrent MOTIFS become
    single tokens: `SWEEP_HIGH+DISPLACEMENT_DOWN` becomes an atom if the market repeats it. This
    is where a genuine grammar would show up, and where a spurious one would too -- every merge is
    a choice made by looking at the data, so `n_trials` accumulates.
    """
    toks = list(base.tokens)
    merges: list[tuple[str, str]] = []
    for _ in range(n_merges):
        pairs = Counter(zip(toks, toks[1:]))
        if not pairs:
            break
        (a, b), cnt = pairs.most_common(1)[0]
        if cnt < 10:                       # a motif seen nine times is not a motif
            break
        merged, out, i = f"{a}+{b}", [], 0
        while i < len(toks):
            if i + 1 < len(toks) and toks[i] == a and toks[i + 1] == b:
                out.append(merged)
                i += 2
            else:
                out.append(toks[i])
                i += 1
        toks, _ = out, merges.append((a, b))
    return Encoding(f"bpe({base.name})", toks, base.index[:len(toks)],
                    sorted(set(toks)), n_trials=base.n_trials + len(merges),
                    meta={"merges": [f"{a}+{b}" for a, b in merges], "n_merges": len(merges)})


def encode_continuous(h1: pd.DataFrame, lookback: int = 20) -> pd.DataFrame:
    """No discretization. THE MANDATORY BASELINE -- a tokenizer must beat not tokenizing."""
    return _features(h1, lookback)


# ------------------------------------------------------------------ motif discovery

def find_motifs(enc: Encoding, length: int = 3, top: int = 15) -> list[tuple[tuple, int]]:
    """The most frequent n-token sequences. Where a rediscovery would appear."""
    seqs = Counter(tuple(enc.tokens[i:i + length]) for i in range(len(enc.tokens) - length + 1))
    return seqs.most_common(top)


#: The structure the SMC state machine already encodes. A learned encoder reproducing it without
#: being told is corroboration of both; it is recorded, never assumed.
SMC_SIGNATURE = ("SWEEP", "DISPLACEMENT", "RETRACE")


#: A motif must beat its independent-draw expectation by this factor to count as structure.
#: Without it the test is "did these tokens ever land next to each other", and in a long enough
#: stream the answer is always yes.
_LIFT = 2.0
#: And it must actually happen. A 3x lift on an expectation of 0.4 occurrences is one accident.
_MIN_COUNT = 20


def rediscovers_smc(enc: Encoding, length: int = 3, top: int = 40) -> dict:
    """Did this encoding independently produce the sweep -> displacement structure?

    THE FIRST VERSION OF THIS FUNCTION FIRED ON RANDOM WALKS. It asked only whether "SWEEP" and
    "DISPLACEMENT" both appeared somewhere in a frequent motif, so it reported
    `DISPLACEMENT_DOWN|SWEEP_LOW|SWEEP_LOW` -- displacement BEFORE the sweep, nine occurrences --
    as a rediscovery of a structure that says the sweep comes first. Its own negative control
    caught it, which is the entire reason that control exists: a detector that cannot fail on
    noise turns every dataset into a confirmation.

    Two requirements now, and both are the point rather than tuning:

      ORDER. The SMC claim is that liquidity is taken and THEN price displaces away. A motif with
      displacement first is the opposite claim and must not satisfy it.

      LIFT OVER CHANCE. The observed count is compared with what independent draws from this
      encoding's own token distribution would produce. A motif of common tokens is expected to
      recur often, and recurring exactly as often as expected is not structure -- it is the
      marginal distribution restated.
    """
    n = len(enc.tokens)
    if n <= length:
        return {"encoder": enc.name, "rediscovered": False, "motifs": [],
                "why": "stream shorter than the motif length"}
    freq = enc.counts()
    hits = []
    for seq, cnt in find_motifs(enc, length=length, top=top):
        idx_sweep = next((i for i, t in enumerate(seq) if "SWEEP" in t), None)
        idx_disp = next((i for i, t in enumerate(seq) if "DISPLACEMENT" in t), None)
        if idx_sweep is None or idx_disp is None or idx_sweep >= idx_disp:
            continue                     # not the structure, or the structure backwards
        p = 1.0
        for t in seq:
            p *= freq[t] / n
        expected = p * (n - length + 1)
        lift = cnt / expected if expected > 0 else 0.0
        if cnt >= _MIN_COUNT and lift >= _LIFT:
            hits.append({"motif": "|".join(seq), "count": cnt,
                         "expected_by_chance": round(expected, 2), "lift": round(lift, 2)})
    return {
        "encoder": enc.name, "rediscovered": bool(hits), "motifs": hits,
        "criteria": {"ordered_sweep_before_displacement": True,
                     "min_count": _MIN_COUNT, "min_lift_over_chance": _LIFT},
        "why": ("a learned encoding independently producing sweep->displacement, ORDERED and "
                "above chance, corroborates the hand-built state machine AND shows the encoder "
                "finds structure rather than noise. Absence is not evidence against the SMC "
                "engine -- only that this vocabulary at this bar size did not surface it."),
    }
