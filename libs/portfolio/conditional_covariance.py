"""How much the book's dependence actually changes by regime, and what that implies for crisis.

WHAT WAS ALREADY RIGHT, so it is not rebuilt here. `sample_worlds` resamples whole ROWS of the
sleeve matrix inside a regime's own days, so contemporaneous dependence is already conditional on
regime -- and it is conditional non-parametrically, keeping the real tails, which is strictly
better than fitting a Sigma(Z) and then repairing its positive-definiteness. The crisis overlay
already loads a common factor onto every sleeve so correlations converge. None of that needed
replacing.

WHAT WAS MISSING. Two numbers governing how bad a crisis is were CONSTANTS:

    crisis_vol_mult     = 2.5
    crisis_common_share = 0.55

Nobody had measured either against this book. A one-factor overlay in which each sleeve is
sqrt(s)*common + sqrt(1-s)*idio has pairwise correlation exactly s, so `crisis_common_share` IS
the pairwise correlation the crisis worlds assume -- a quantity the desk's own return matrix can
simply be asked about. Guessing a number the data will answer is the kind of thing that survives
in a risk model precisely because it is never wrong out loud.

THE MEASUREMENT MAY ONLY MAKE THE CRISIS WORSE, NEVER MILDER. `calibrate` takes the maximum of
the standing constant and the shrunk measurement. A measured correlation of 0.30 in the stress
regime does not license modelling crises as gentler than the desk has been assuming -- that would
be relaxing a risk assumption on the strength of a quiet sample, which is exactly how a book
discovers its true correlations at the worst possible moment. It can only ratchet upward.

SHRUNK BY SAMPLE, LIKE EVERY OTHER ESTIMATE HERE. The stress regime is whichever regime carries
the highest mean sleeve volatility -- data-driven, no label parsing, so it moves when the
classifier's vocabulary does. Its correlation estimate is shrunk toward the standing constant by
n/(n+k) on the number of days in the pool, so a twelve-day stress pool moves nothing.

PER FACTOR BLOCK, UNDER THE SCALAR (2026-09-09). One book-wide share stresses every sleeve as if
it shared the same shock. The book's most likely co-explosion is a USD move, and a gold sleeve
does not share it with a EURUSD sleeve the way a GBPUSD sleeve does -- `libs/risk/fx_factors`
already decomposes each symbol into its currency legs, so the stress-regime correlation can be
measured INSIDE each factor block (USD leg, JPY leg, metals) and each sleeve handed its block's
share. The book-wide scalar stays as it was -- ratcheted upward, never softened -- and is the
CEILING for every block: a block measured LESS fused than the book keeps that independence in
crisis worlds, a block with too little data (or measured more fused) carries the scalar. So this
can only relieve a sleeve's crisis stress, never deepen it, and it says which per block.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

import numpy as np

#: Days in a regime pool before its correlation estimate is trusted over the standing constant.
CORR_K = 60.0
#: A pool below this is not measured at all: a handful of days cannot describe dependence across
#: a book, and pretending otherwise is how a risk model acquires false confidence.
MIN_POOL_DAYS = 20

#: The factor blocks a sleeve's crisis share is measured inside. Named after the shock they share:
#: a USD move, a JPY move, a metals move. A cross carrying two of them (USDJPY) is in both and
#: takes the HIGHER applied share -- the conservative side of an ambiguity.
FACTOR_BLOCKS: tuple[str, ...] = ("USD", "JPY", "metals")
#: Live sleeves a block needs in the stress pool before its own correlation is measured. Two
#: sleeves is one correlation coefficient; three is the smallest number that is a mean of any.
MIN_BLOCK_SLEEVES = 3
#: The symbol the desk's gold book carries in its sleeve names (`gold_asia` -> "gold"). It IS
#: XAUUSD on the venue, so it is mapped to XAUUSD's legs rather than reported UNKNOWN. Only the
#: bare word: a real cross such as XAUEUR decomposes on its own legs and must not be rewritten.
_GOLD_ALIAS = "GOLD"


def factor_blocks_of(symbol: str) -> tuple[str, ...]:
    """Which of `FACTOR_BLOCKS` a symbol's legs belong to; () when it cannot be decomposed.

    Uses `libs.risk.fx_factors.split_pair` so the block is the same decomposition the factor
    breadth measurement uses -- an unknown symbol is (), never guessed into a block.
    """
    s = str(symbol or "").strip().upper()
    if not s:
        return ()
    if s == _GOLD_ALIAS:
        s = "XAUUSD"
    try:
        from libs.risk.fx_factors import _NON_CURRENCY, split_pair
    except Exception:                                                    # pragma: no cover
        return ()
    legs = split_pair(s)
    if legs is None:
        return ()
    out: list[str] = []
    if any(leg in _NON_CURRENCY for leg in legs):
        out.append("metals")
    if "USD" in legs:
        out.append("USD")
    if "JPY" in legs:
        out.append("JPY")
    return tuple(b for b in FACTOR_BLOCKS if b in out)


@dataclass(frozen=True)
class BlockCov:
    """One factor block's crisis share: what was measured, and what is applied under the cap."""

    block: str
    n_sleeves: int
    n_days: int
    #: Mean off-diagonal correlation among the block's sleeves in the STRESS regime (nan when
    #: unmeasured).
    mean_corr: float
    #: The measurement shrunk toward the book-wide scalar by n/(n+k) on stress days.
    shrunk_share: float
    #: What the crisis worlds use: min(shrunk, scalar). Never above the scalar.
    applied_share: float
    status: str
    why: str = ""


@dataclass(frozen=True)
class RegimeCov:
    """The dependence and scale one regime actually produced."""

    regime: str
    n_days: int
    #: Mean off-diagonal Pearson correlation across sleeve pairs.
    mean_corr: float
    #: Mean per-sleeve standard deviation, in the matrix's own units (R).
    mean_vol: float
    #: Correlation of the equally-weighted book with itself is meaningless; this is the ratio of
    #: book variance to the sum of sleeve variances -- 1/N under independence, 1.0 under perfect
    #: dependence. The number that says what diversification actually survives in this regime.
    diversification_ratio: float


@dataclass(frozen=True)
class Calibration:
    """What the crisis overlay should assume, and where each number came from."""

    crisis_common_share: float
    crisis_vol_mult: float
    stress_regime: str
    by_regime: dict[str, RegimeCov] = field(default_factory=dict)
    unconditional: RegimeCov | None = None
    note: str = ""
    #: Per factor block, when `calibrate` was handed symbols; empty otherwise.
    by_block: dict[str, BlockCov] = field(default_factory=dict)
    #: Per sleeve name, the share the crisis worlds apply -- only sleeves whose share differs
    #: from the scalar are listed, so an empty map means "every sleeve at the scalar".
    share_by_sleeve: dict[str, float] = field(default_factory=dict)
    #: Which block(s) each sleeve was assigned to, for the artifact.
    blocks_by_sleeve: dict[str, tuple[str, ...]] = field(default_factory=dict)

    def as_overrides(self) -> dict[str, object]:
        out: dict[str, object] = {"crisis_common_share": self.crisis_common_share,
                                  "crisis_vol_mult": self.crisis_vol_mult}
        if self.share_by_sleeve:
            out["crisis_common_share_by_sleeve"] = tuple(sorted(self.share_by_sleeve.items()))
        return out


def _mean_offdiag_corr(hist: np.ndarray) -> float:
    """Mean pairwise correlation, ignoring sleeves that never move."""
    if hist.ndim != 2 or hist.shape[1] < 2 or hist.shape[0] < 3:
        return float("nan")
    sd = hist.std(axis=0)
    live = sd > 0
    if int(live.sum()) < 2:
        return float("nan")
    c = np.corrcoef(hist[:, live], rowvar=False)
    if not np.isfinite(c).all():
        c = np.nan_to_num(c, nan=0.0)
    k = c.shape[0]
    off = c[~np.eye(k, dtype=bool)]
    return float(off.mean()) if off.size else float("nan")


def _cov_of(hist: np.ndarray, regime: str) -> RegimeCov:
    sd = hist.std(axis=0)
    live = sd > 0
    book_var = float(hist[:, live].sum(axis=1).var()) if int(live.sum()) else 0.0
    sum_var = float((sd[live] ** 2).sum()) if int(live.sum()) else 0.0
    return RegimeCov(
        regime=regime, n_days=int(hist.shape[0]),
        mean_corr=_mean_offdiag_corr(hist),
        mean_vol=float(sd[live].mean()) if int(live.sum()) else float("nan"),
        diversification_ratio=float(book_var / sum_var) if sum_var > 0 else float("nan"),
    )


def by_regime(hist: np.ndarray, labels: Sequence[str]) -> dict[str, RegimeCov]:
    """Per-regime dependence, over the rows each regime actually produced."""
    out: dict[str, RegimeCov] = {}
    lab = np.asarray(labels, dtype=object)
    if lab.size != hist.shape[0]:
        return out
    for name in sorted({str(x) for x in lab if str(x)}):
        rows = np.flatnonzero(lab == name)
        if rows.size < MIN_POOL_DAYS:
            continue
        out[name] = _cov_of(hist[rows], name)
    return out


def block_shares(stress_rows: np.ndarray, names: Sequence[str], symbols: Sequence[str], *,
                 scalar: float, lam: float, n_days: int,
                 min_sleeves: int = MIN_BLOCK_SLEEVES,
                 ) -> tuple[dict[str, BlockCov], dict[str, float], dict[str, tuple[str, ...]]]:
    """Crisis share per factor block on the stress regime's own rows, capped at `scalar`.

    Returns (by_block, share_by_sleeve, blocks_by_sleeve). `share_by_sleeve` lists only the
    sleeves whose applied share is BELOW the scalar; every other sleeve carries the scalar and
    is not listed, so the caller's world config changes nothing for them.
    """
    n = int(stress_rows.shape[1]) if stress_rows.ndim == 2 else 0
    if n != len(names) or n != len(symbols):
        return {}, {}, {}
    members: dict[str, list[int]] = {b: [] for b in FACTOR_BLOCKS}
    blocks_by_sleeve: dict[str, tuple[str, ...]] = {}
    for i, (name, sym) in enumerate(zip(names, symbols, strict=True)):
        blk = factor_blocks_of(sym)
        blocks_by_sleeve[str(name)] = blk
        for b in blk:
            members[b].append(i)
    sd = stress_rows.std(axis=0) if stress_rows.shape[0] > 1 else np.zeros(n)
    by_block: dict[str, BlockCov] = {}
    applied: dict[str, float] = {}
    for b in FACTOR_BLOCKS:
        idx = [i for i in members[b] if sd[i] > 0]
        if len(idx) < min_sleeves:
            by_block[b] = BlockCov(block=b, n_sleeves=len(idx), n_days=int(n_days),
                                   mean_corr=float("nan"), shrunk_share=scalar,
                                   applied_share=scalar, status="UNMEASURED",
                                   why=(f"{len(idx)} live sleeve(s) in the stress pool, need "
                                        f"{min_sleeves}; the book-wide scalar stands"))
            continue
        corr = _mean_offdiag_corr(stress_rows[:, idx])
        if not np.isfinite(corr):
            by_block[b] = BlockCov(block=b, n_sleeves=len(idx), n_days=int(n_days),
                                   mean_corr=float("nan"), shrunk_share=scalar,
                                   applied_share=scalar, status="UNMEASURED",
                                   why="correlation not finite on the stress pool")
            continue
        measured = float(np.clip(corr, 0.0, 0.95))
        shrunk = float(lam * measured + (1.0 - lam) * scalar)
        # THE SCALAR IS THE CEILING. The ratchet lives on the scalar; a block measured MORE
        # fused than the book is carried at the scalar (its excess is reported, not applied),
        # so no sleeve is ever stressed harder than every sleeve was before blocks existed.
        use = float(min(shrunk, scalar))
        status = "MEASURED" if use < scalar - 1e-9 else "AT_SCALAR"
        by_block[b] = BlockCov(block=b, n_sleeves=len(idx), n_days=int(n_days),
                               mean_corr=round(float(corr), 4), shrunk_share=round(shrunk, 4),
                               applied_share=round(use, 4), status=status,
                               why=(f"stress-pool correlation {corr:.2f} over {len(idx)} "
                                    f"sleeve(s), shrunk at weight {lam:.2f} toward the "
                                    f"{scalar:.2f} scalar"
                                    + ("" if use < scalar - 1e-9 else
                                       "; measured at or above the scalar, so the scalar "
                                       "(the ceiling) is applied")))
        applied[b] = use
    share_by_sleeve: dict[str, float] = {}
    for name, blk in blocks_by_sleeve.items():
        measured_blocks = [applied[b] for b in blk if b in applied]
        if not measured_blocks:
            continue
        # A sleeve in two blocks (USDJPY) takes the HIGHER applied share: the ambiguity is
        # resolved on the side that stresses it more, and never past the scalar.
        s = max(measured_blocks)
        if s < scalar - 1e-9:
            share_by_sleeve[name] = round(s, 4)
    return by_block, share_by_sleeve, blocks_by_sleeve


def calibrate(hist: np.ndarray, labels: Sequence[str] | None,
              *, standing_share: float, standing_vol_mult: float,
              corr_k: float = CORR_K,
              symbols: Sequence[str] | Mapping[str, str] | None = None,
              names: Sequence[str] | None = None) -> Calibration:
    """What the crisis overlay should assume for THIS book, ratcheting only upward.

    `hist` is the (days, sleeves) return matrix the worlds are drawn from -- the same object
    `sample_worlds` bootstraps, so the calibration describes the population being sampled rather
    than some other estimate of it.

    `symbols` (one per column, or a name -> symbol mapping) with `names` (one per column) turns
    on the per-factor-block measurement; without them the result is exactly what it was.
    """
    hist = np.asarray(hist, dtype=float)
    if hist.ndim != 2 or hist.shape[1] < 2 or hist.shape[0] < MIN_POOL_DAYS:
        return Calibration(crisis_common_share=standing_share,
                           crisis_vol_mult=standing_vol_mult, stress_regime="",
                           note="matrix too small to measure dependence; standing constants kept")

    uncond = _cov_of(hist, "")
    per = by_regime(hist, labels) if labels is not None else {}
    if not per:
        return Calibration(crisis_common_share=standing_share,
                           crisis_vol_mult=standing_vol_mult, stress_regime="",
                           unconditional=uncond,
                           note=("no regime pool reached "
                                 f"{MIN_POOL_DAYS} days; standing constants kept"))

    # THE STRESS REGIME IS THE MOST VOLATILE ONE, not the one whose label contains a scary word.
    # Labels come from a classifier whose vocabulary changes; volatility is the thing the crisis
    # overlay is actually about.
    stress = max(per.values(), key=lambda c: (c.mean_vol if np.isfinite(c.mean_vol) else -1.0))
    lam = stress.n_days / (stress.n_days + corr_k)

    share = standing_share
    if np.isfinite(stress.mean_corr):
        measured = float(np.clip(stress.mean_corr, 0.0, 0.95))
        share = float(lam * measured + (1.0 - lam) * standing_share)

    # THE REFERENCE IS THE CALM REGIME, NOT THE UNCONDITIONAL POOL. "How much worse than normal
    # does a crisis get" is a comparison against normal, and the unconditional pool CONTAINS the
    # stress days -- using it as the denominator lets a turbulent history quietly argue that
    # crises are only slightly worse than average, which is the wrong direction for a risk
    # assumption to be wrong in.
    calm = min(per.values(), key=lambda c: (c.mean_vol if np.isfinite(c.mean_vol) else 1e9))
    vol_mult = standing_vol_mult
    if np.isfinite(stress.mean_vol) and np.isfinite(calm.mean_vol) and calm.mean_vol > 0:
        measured_mult = float(stress.mean_vol / calm.mean_vol)
        vol_mult = float(lam * measured_mult + (1.0 - lam) * standing_vol_mult)

    # RATCHET. A quiet sample may not license a gentler crisis than the desk has been assuming.
    share = max(standing_share, share)
    vol_mult = max(standing_vol_mult, vol_mult)

    # PER FACTOR BLOCK, on the same stress rows, under the ratcheted scalar. Only when the
    # caller says which symbol each column is; otherwise nothing here changes.
    by_block: dict[str, BlockCov] = {}
    share_by_sleeve: dict[str, float] = {}
    blocks_by_sleeve: dict[str, tuple[str, ...]] = {}
    if symbols is not None and names is not None and len(names) == hist.shape[1]:
        syms = ([str(symbols.get(str(n), "")) for n in names] if isinstance(symbols, Mapping)
                else [str(s) for s in symbols])
        if len(syms) == hist.shape[1]:
            lab = np.asarray(list(labels), dtype=object) if labels is not None else None
            rows = (np.flatnonzero(lab == stress.regime) if lab is not None
                    and lab.size == hist.shape[0] else np.array([], dtype=int))
            if rows.size >= MIN_POOL_DAYS:
                by_block, share_by_sleeve, blocks_by_sleeve = block_shares(
                    hist[rows], [str(n) for n in names], syms, scalar=round(share, 4),
                    lam=lam, n_days=int(rows.size))

    gap = ""
    if calm.regime != stress.regime and np.isfinite(calm.mean_corr):
        gap = (f"; pairwise correlation {calm.mean_corr:.2f} in {calm.regime} vs "
               f"{stress.mean_corr:.2f} in {stress.regime}")
    blk_note = ""
    if by_block:
        relieved = sorted(b for b, v in by_block.items() if v.status == "MEASURED")
        blk_note = (f"; factor blocks measured on the stress pool: "
                    f"{len(relieved)} below the scalar ({', '.join(relieved) or 'none'}), "
                    f"{len(share_by_sleeve)} sleeve(s) relieved")
    return Calibration(
        crisis_common_share=round(share, 4), crisis_vol_mult=round(vol_mult, 4),
        stress_regime=stress.regime, by_regime=per, unconditional=uncond,
        note=(f"stress regime {stress.regime} ({stress.n_days}d, shrink weight {lam:.2f})"
              f"{gap}{blk_note}"),
        by_block=by_block, share_by_sleeve=share_by_sleeve, blocks_by_sleeve=blocks_by_sleeve,
    )
