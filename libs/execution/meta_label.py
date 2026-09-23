"""The meta-labeler: SKIP / 0.5x / 1x / 1.5x / MAX for an otherwise-valid signal.

THE PRINCIPAL'S ORDER. "Train a meta-labeler: for an otherwise-valid signal, SKIP / 0.5x / 1x /
1.5x / MAX. The base strategy finds the opportunity; the meta-model decides how good this
particular occurrence is."

THE WORD THAT DOES ALL THE WORK IS "OTHERWISE-VALID". This model may only ever be asked about a
signal that has ALREADY passed every gate the desk runs. It is a sizing refinement downstream of
admission, never a second opinion on admission, and `label()` enforces that in the only way that
survives a careless caller: a signal presented with `gate_passed=False` returns SKIP with a
multiplier of exactly 0.0, and there is no argument, flag or fitted state that changes that
answer. A meta-labeler that can talk a refused signal back into the book is not a meta-labeler,
it is a gate with extra steps, and it would quietly undo every threshold the desk has paid to
learn.

THE ASYMMETRY IS DELIBERATE AND PERMANENT. Reducing size is always allowed: SKIP and 0.5x need no
fitted model, because refusing to press a bet the desk cannot justify is never the error that
ruins an account. INCREASING size is allowed only when the model is MEASURED -- the bucket has
its required sample, its interval is clear of the base bucket's, and the bucket ordering is
monotone. Until then `label()` returns BASE at exactly 1.0x. An unfitted meta-labeler is
therefore a no-op on the upside and a live safety valve on the downside, which is the only
configuration where shipping the harness early is free.

THE MULTIPLIER IS ADVISORY AND IS NOT A RISK LIMIT. It composes multiplicatively INSIDE whatever
heat the allocator has already granted the sleeve; it does not raise a cap, a floor, a daily
stop or a ruin rail, and nothing here may be read as authority to exceed one. `MAX_MULTIPLIER`
is a ceiling on this model's own output, not a licence.

WHAT IT LEARNS FROM. The fill corpus: one row per execution carrying the world at the decision,
what the desk predicted, what happened and what the alternatives would have done. The label is
the realised outcome; the features are the corpus's own columns. `fit` ranks occurrences by ONE
named feature at a time, buckets them, and charges Bonferroni for every feature x bucket
comparison it looked at -- because searching thirty columns for the one that separates good
occurrences from bad, and then reporting the winner's t-statistic as though it were the only
test, is the single most reliable way to manufacture a sizing model out of noise.
"""
from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from libs.execution.fill_corpus import FillRecord, record_from_row
from libs.execution.sample_power import DEFAULT_ALPHA, DEFAULT_POWER, sigma_of
from libs.execution.sample_power import verdict as power_verdict

__all__ = [
    "BASE",
    "HALF",
    "LABELS",
    "MAX",
    "MAX_MULTIPLIER",
    "MULTIPLIERS",
    "SKIP",
    "TARGET_DELTA_R",
    "UP",
    "MetaLabeler",
    "fit",
    "label_of_multiplier",
    "requirements",
]

MEASURED = "MEASURED"
UNMEASURED = "UNMEASURED"
Z95 = 1.959964

SKIP, HALF, BASE, UP, MAX = "SKIP", "HALF", "BASE", "UP", "MAX"
LABELS: tuple[str, ...] = (SKIP, HALF, BASE, UP, MAX)
#: The five sizes, in the principal's own terms. MAX is 2.0x and not more: this model is a
#: refinement of a size the allocator already solved for, and a refinement that can double a
#: position is already at the edge of what "refinement" means.
MULTIPLIERS: dict[str, float] = {SKIP: 0.0, HALF: 0.5, BASE: 1.0, UP: 1.5, MAX: 2.0}
MAX_MULTIPLIER = MULTIPLIERS[MAX]

#: The difference in mean realised R between a bucket and the base that makes a size change worth
#: making. Larger than the execution model's 0.04R on purpose: 0.04R is worth recovering because
#: it costs nothing to recover once known, whereas moving size is a change in risk and needs an
#: effect big enough to survive being wrong about it.
TARGET_DELTA_R = 0.10
#: Quantile edges: five buckets, one per label.
N_BUCKETS = 5
#: AN ABSOLUTE FLOOR ON TOP OF THE POWER CALCULATION, and never below it -- the same rule and the
#: same reason as `execution_choice_model.MIN_CELL_N`. A bucket of four identical outcomes has
#: zero observed variance, an infinitely tight interval and a confident verdict; a size
#: multiplier granted on that is a random number with a decimal point.
MIN_BUCKET_N = 20
#: The label each bucket earns IF, and only if, the evidence supports it. Ascending by feature.
_BUCKET_LABELS: tuple[str, ...] = (SKIP, HALF, BASE, UP, MAX)
#: Reference dispersion of realised R per trade, in R. Declared, not measured -- see
#: `execution_choice_model.REFERENCE_SIGMA_R` for why a stop-and-target desk sits near this.
REFERENCE_SIGMA_R = 1.20


def _f(x: Any) -> float | None:
    if x is None or isinstance(x, bool):
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def label_of_multiplier(mult: float) -> str:
    """The nearest named label for a multiplier. For reporting only."""
    return min(LABELS, key=lambda k: abs(MULTIPLIERS[k] - float(mult)))


def _feature_value(rec: FillRecord, name: str) -> float | None:
    """A feature off a corpus row: a top-level numeric column, or `strategy_dna`/`market_state`
    key by dotted path. Nothing is computed here -- a meta-label feature the corpus does not
    already carry is a capture gap, not a modelling opportunity."""
    if "." in name:
        head, _, tail = name.partition(".")
        blob = getattr(rec, head, None)
        if isinstance(blob, Mapping):
            return _f(blob.get(tail))
        return None
    return _f(getattr(rec, name, None))


def _mean_se(xs: Sequence[float]) -> tuple[float, float]:
    n = len(xs)
    m = sum(xs) / n
    if n < 2:
        return m, 0.0
    var = sum((x - m) ** 2 for x in xs) / (n - 1)
    return m, math.sqrt(var / n)


def _quantile_edges(xs: Sequence[float], k: int) -> list[float]:
    s = sorted(xs)
    n = len(s)
    return [s[min(n - 1, max(0, round(i * n / k) - 1))] for i in range(1, k)]


@dataclass(frozen=True)
class MetaLabeler:
    """A fitted (or refused) meta-label model on ONE feature."""

    status: str
    feature: str = ""
    #: Ascending feature thresholds; len == N_BUCKETS - 1.
    edges: list[float] = field(default_factory=list)
    #: bucket index -> {n, mean_r, se, ci95, label, multiplier, status, why}
    buckets: list[dict[str, Any]] = field(default_factory=list)
    base_mean_r: float | None = None
    power: dict[str, Any] = field(default_factory=dict)
    features_tried: list[str] = field(default_factory=list)
    n_observations: int = 0
    why: str = ""

    @property
    def usable(self) -> bool:
        return self.status == MEASURED

    def to_row(self) -> dict[str, Any]:
        return {"status": self.status, "feature": self.feature, "edges": self.edges,
                "buckets": self.buckets, "base_mean_r": self.base_mean_r,
                "power": self.power, "features_tried": self.features_tried,
                "n_observations": self.n_observations, "labels": list(LABELS),
                "multipliers": MULTIPLIERS, "why": self.why,
                "law": ("upsizing requires MEASURED; a signal that failed a gate is SKIP with "
                        "multiplier 0.0 and no fitted state changes that")}

    # -- the only entry point a caller should use ---------------------------------------
    def label(self, record: FillRecord | Mapping[str, Any] | None = None, *,
              gate_passed: bool, features: Mapping[str, float] | None = None,
              ) -> tuple[str, float, str]:
        """(label, multiplier, why) for one occurrence of an otherwise-valid signal.

        `gate_passed` is the caller's assertion that EVERY gate the desk runs has already
        admitted this signal. False returns SKIP at 0.0x unconditionally -- this model never
        re-admits, and there is no path through this function that returns a positive multiplier
        for a refused signal.
        """
        if not gate_passed:
            return SKIP, 0.0, ("a gate refused this signal; the meta-labeler never re-admits, "
                               "it only sizes what admission already allowed")
        if not self.usable:
            return BASE, 1.0, (f"{UNMEASURED}: {self.why} -- an unfitted meta-labeler is a no-op "
                               "on the upside, so size is left exactly as the allocator set it")
        v: float | None = None
        if features is not None and self.feature in features:
            v = _f(features[self.feature])
        elif record is not None:
            rec = record if isinstance(record, FillRecord) else record_from_row(record)
            v = _feature_value(rec, self.feature)
        if v is None:
            return BASE, 1.0, (f"{self.feature!r} is not populated for this occurrence; the "
                               "model does not size on an imputed feature")
        idx = 0
        for e in self.edges:
            if v > e:
                idx += 1
        b = self.buckets[min(idx, len(self.buckets) - 1)]
        mult = float(b.get("multiplier", 1.0))
        mult = max(0.0, min(MAX_MULTIPLIER, mult))
        return str(b.get("label", BASE)), mult, str(b.get("why", ""))


def fit(records: Iterable[FillRecord | Mapping[str, Any]], *,
        features: Sequence[str],
        target_delta_r: float = TARGET_DELTA_R,
        outcome: str = "realized_r",
        alpha: float = DEFAULT_ALPHA, power: float = DEFAULT_POWER,
        min_n_per_bucket: int | None = None) -> MetaLabeler:
    """Fit the meta-labeler on the best of `features`, or refuse and say what sample it needs.

    Bonferroni is charged over EVERY feature x bucket comparison examined -- `len(features)` x
    (N_BUCKETS - 1) -- not over the winner alone. That is the difference between a model and a
    scan, and it is what stops a thirty-column corpus from producing a confident sizing rule from
    thirty coin flips.

    A bucket earns a multiplier above 1.0 only when its interval is entirely above the BASE
    bucket's mean AND the ordering of bucket means is monotone in the feature. A non-monotone
    ranking is a fit to noise even when a cell is individually significant, and the correct
    response is to refuse the whole feature rather than to keep the significant cells.
    """
    recs = [r if isinstance(r, FillRecord) else record_from_row(r) for r in records]
    ys: list[tuple[FillRecord, float]] = []
    for r in recs:
        y = _f(getattr(r, outcome, None))
        if y is not None:
            ys.append((r, y))
    feats = list(dict.fromkeys(str(f) for f in features if str(f)))
    comparisons = max(1, len(feats) * (N_BUCKETS - 1))
    sigma = sigma_of([y for _, y in ys])
    need = power_verdict(n_have=0, delta_target=target_delta_r, sigma=sigma,
                         reference_sigma=REFERENCE_SIGMA_R, alpha=alpha, power=power,
                         n_comparisons=comparisons, what=f"meta-label bucket on {outcome}")
    min_bucket = max(MIN_BUCKET_N,
                     int(min_n_per_bucket) if min_n_per_bucket is not None else need.n_required)
    powered: dict[str, Any] = {"per_bucket": need.to_row(),
                               "comparisons_charged": comparisons,
                               "n_required_per_bucket": min_bucket,
                               "n_required_total": min_bucket * N_BUCKETS,
                               "n_have_total": len(ys),
                               "outcome": outcome, "target_delta_r": target_delta_r}
    if len(ys) < min_bucket * N_BUCKETS:
        return MetaLabeler(status=UNMEASURED, features_tried=feats, power=powered,
                           n_observations=len(ys),
                           why=(f"{len(ys)} labelled outcomes; {N_BUCKETS} buckets need "
                                f"{min_bucket} each = {min_bucket * N_BUCKETS} at "
                                f"delta={target_delta_r:g}R with {comparisons} comparisons "
                                f"charged. Harness live, model NOT fitted."))

    best: MetaLabeler | None = None
    for name in feats:
        cand = _fit_one(ys, name, min_bucket, comparisons, target_delta_r, sigma,
                        alpha, power, outcome)
        if cand is None:
            continue
        if best is None:
            best = cand                                   # something to report is better than none
        elif cand.usable and (not best.usable or _strength(cand) > _strength(best)):
            best = cand
    if best is None:
        return MetaLabeler(status=UNMEASURED, features_tried=feats, power=powered,
                           n_observations=len(ys),
                           why=("no feature is populated on enough rows to bucket; a meta-label "
                                "feature the corpus does not carry is a capture gap"))
    return MetaLabeler(status=best.status, feature=best.feature, edges=best.edges,
                       buckets=best.buckets, base_mean_r=best.base_mean_r,
                       power={**powered, **best.power}, features_tried=feats,
                       n_observations=best.n_observations, why=best.why)


def _strength(m: MetaLabeler) -> float:
    """How strong a fitted feature's WORST upsized claim is: the smallest lower bound among the
    buckets it upsizes. Used only to prefer one MEASURED feature over another, and it never turns
    an UNMEASURED fit into a usable one.

    NOT the point spread. Ranking candidate features by how far apart their bucket means sit
    picks the NOISIEST feature -- extreme means are what noise produces -- and doing that after
    scanning several features is the multiplicity error twice over. The lower bound of the
    interval is the part of the claim the evidence actually supports, so that is what competes.
    """
    lows = [ci[0] for b in m.buckets
            if float(b.get("multiplier", 1.0)) > 1.0
            and isinstance(ci := b.get("ci95"), list) and ci and _f(ci[0]) is not None]
    return min(lows) if lows else 0.0


def _fit_one(ys: Sequence[tuple[FillRecord, float]], name: str, min_bucket: int,
             comparisons: int, target_delta_r: float, sigma: float | None,
             alpha: float, power: float, outcome: str) -> MetaLabeler | None:
    pairs = [(v, y) for v, y in ((_feature_value(r, name), y) for r, y in ys) if v is not None]
    if len(pairs) < min_bucket * N_BUCKETS:
        return MetaLabeler(status=UNMEASURED, feature=name, n_observations=len(pairs),
                           why=(f"{name!r} populated on {len(pairs)} rows; needs "
                                f"{min_bucket * N_BUCKETS}"))
    edges = _quantile_edges([v for v, _ in pairs], N_BUCKETS)
    groups: list[list[float]] = [[] for _ in range(N_BUCKETS)]
    for v, y in pairs:
        idx = 0
        for e in edges:
            if v > e:
                idx += 1
        groups[min(idx, N_BUCKETS - 1)].append(y)
    base_idx = _BUCKET_LABELS.index(BASE)
    if any(len(g) < min_bucket for g in groups) or not groups[base_idx]:
        thin = [i for i, g in enumerate(groups) if len(g) < min_bucket]
        return MetaLabeler(status=UNMEASURED, feature=name, edges=[round(e, 8) for e in edges],
                           n_observations=len(pairs),
                           why=(f"buckets {thin} hold fewer than {min_bucket} observations; the "
                                "feature does not spread the corpus evenly enough to size on"))
    stats = [_mean_se(g) for g in groups]
    means = [m for m, _ in stats]
    monotone = (all(means[i] <= means[i + 1] for i in range(len(means) - 1))
                or all(means[i] >= means[i + 1] for i in range(len(means) - 1)))
    #: A descending feature is used ascending by flipping the label order, not by re-fitting: the
    #: buckets are the same partition either way and re-fitting on the reversed feature would be
    #: a second search on the same data with no charge.
    order = _BUCKET_LABELS if means[-1] >= means[0] else tuple(reversed(_BUCKET_LABELS))
    base_mean, base_se = stats[order.index(BASE)]
    buckets: list[dict[str, Any]] = []
    any_up = False
    for i, (m, se) in enumerate(stats):
        lbl = order[i]
        want = MULTIPLIERS[lbl]
        adv = m - base_mean
        sd = math.sqrt(se * se + base_se * base_se)
        ci = [adv - Z95 * sd, adv + Z95 * sd]
        pv = power_verdict(n_have=min(len(groups[i]), len(groups[order.index(BASE)])),
                           delta_target=target_delta_r, sigma=sigma,
                           reference_sigma=REFERENCE_SIGMA_R, alpha=alpha, power=power,
                           n_comparisons=comparisons,
                           what=f"{name} bucket {i} vs base on {outcome}")
        ok_up = (want > 1.0 and monotone and pv.status == MEASURED and ci[0] > 0)
        ok_down = want < 1.0
        mult = want if (ok_up or ok_down) else 1.0
        if ok_up:
            any_up = True
        buckets.append({
            "bucket": i, "n": len(groups[i]), "mean_r": round(m, 8), "se": round(se, 8),
            "advantage_vs_base_r": round(adv, 8),
            "ci95": [round(ci[0], 8), round(ci[1], 8)],
            "label": lbl if mult == want else BASE, "multiplier": mult,
            "power": pv.to_row(),
            "why": ("interval clear of the base bucket at the required sample" if ok_up else
                    "a size REDUCTION needs no fitted model -- refusing to press a bet is never "
                    "the ruinous error" if ok_down else
                    f"not upsized: monotone={monotone}, power={pv.status}, ci_low={ci[0]:.4f}"),
        })
    status = MEASURED if any_up else UNMEASURED
    return MetaLabeler(
        status=status, feature=name, edges=[round(e, 8) for e in edges], buckets=buckets,
        base_mean_r=round(base_mean, 8),
        power={"monotone": monotone, "feature": name},
        n_observations=len(pairs),
        why=("at least one bucket earns an upsize on evidence" if any_up else
             ("bucket means are not monotone in the feature, so any significant cell is a fit to "
              "noise -- the whole feature is refused, not pruned to its winners" if not monotone
              else "no bucket's interval clears the base bucket at the required sample")))


def requirements(*, target_delta_r: float = TARGET_DELTA_R, n_features: int = 1,
                 alpha: float = DEFAULT_ALPHA, power: float = DEFAULT_POWER,
                 sigma: float = REFERENCE_SIGMA_R) -> dict[str, Any]:
    """What the corpus must hold before a meta-labeler may be fitted at all.

    Reported as the deliverable while the model is UNMEASURED, so "not yet" comes with a number
    the desk can plan against rather than an indefinite wait.
    """
    from libs.execution.sample_power import required_n
    comparisons = max(1, int(n_features) * (N_BUCKETS - 1))
    n = required_n(sigma, target_delta_r, alpha=alpha, power=power, n_comparisons=comparisons)
    return {"target_delta_r": target_delta_r, "sigma": sigma, "sigma_measured": False,
            "alpha": alpha, "power": power, "n_features_scanned": int(n_features),
            "comparisons_charged": comparisons, "n_buckets": N_BUCKETS,
            "n_per_bucket": n, "n_total_labelled_outcomes": n * N_BUCKETS,
            "note": ("labelled outcome = one CLOSED trade with a realised R on a corpus row. "
                     "Scanning more features raises the bar: the charge is linear in the number "
                     "of features examined, which is the price of looking.")}
