"""THE SEALED META-BENCHMARK AND THE IMMUNE SYSTEM (Tier S layers 10, 21, 34, 39).

A validator is a function Case -> (accept, reasons). The suite is every trap kind and every
genuine kind at `per_kind` seeds, generated deterministically from `libs/tiers/traps.py`; its
SEAL is the hash of the generator source, the seeds and every case's price bytes, so "the
benchmark got easier" is detectable as a changed seal rather than an argument.

    immune_score      share of planted traps the validator REJECTS (specificity)
    power             share of genuine planted signals it ACCEPTS (sensitivity)
    balanced          the mean of the two

THE REFERENCE VALIDATOR is built from the desk's own judges where they are pure functions
(`libs.validation.dsr.deflated_sharpe_ratio` for selection-aware significance) plus the checks the
fixed ten-gate list does not carry: a future-perturbation lookahead test that runs the signal
function on a path whose future was replaced, fill feasibility against the bar range, a residual
test against factors already held, a survivorship test against the full universe, a stale-quote
test, and walk-forward stability. Every threshold is a field of `ValidatorConfig`, which makes the
validator itself a GENOME: `libs/tiers/test_invention.py` proposes new checks and the architecture
evolver (`libs/tiers/self_model.py`) runs challenger configs against this same sealed suite.

THE FREEZE RULE. `immune_verdict()` compares a run with the sealed baseline and the constitution's
floor (`immune.min_trap_rejection`): if the immune score falls below the floor, or drops more than
`max_drop` below the best score this suite has recorded, the verdict is FREEZE -- the desk has just
become easier to fool, and promotion should stop until it is explained. Publishing the verdict is
research-side; the promoter reading it is a money-path change that waits for the principal.
"""
from __future__ import annotations

import hashlib
import inspect
import math
from collections.abc import Callable, Iterable, Mapping
from dataclasses import asdict, dataclass, replace
from typing import Any

import numpy as np

from libs.tiers import traps
from libs.tiers.traps import Case, Truth

Validator = Callable[[Case], tuple[bool, list[str]]]


@dataclass(frozen=True)
class ValidatorConfig:
    lookahead_probes: int = 40
    lookahead_on: bool = True
    fills_on: bool = True
    fill_tolerance: float = 1e-9
    dsr_threshold: float = 0.95
    dsr_on: bool = True
    wf_folds: int = 4
    wf_min_positive: int = 3
    wf_last_half_positive: bool = True
    wf_on: bool = True
    factor_corr_max: float = 0.5
    factor_resid_t: float = 2.0
    factor_on: bool = True
    survivorship_corr: float = 0.5
    survivorship_t: float = 2.0
    survivorship_on: bool = True
    stale_zero_share: float = 0.2
    stale_on: bool = True
    cost_stress: float = 1.0
    #: extra checks proposed by test_invention: list of (metric, op, threshold)
    extra: tuple[tuple[str, str, float], ...] = ()

    def genome(self) -> dict[str, Any]:
        d = asdict(self)
        d["extra"] = [list(x) for x in self.extra]
        return d


def positions(case: Case) -> np.ndarray:
    n = len(case.prices)
    return np.array([case.signal_fn(case.prices, t) for t in range(n)], dtype=float)


def pnl(case: Case, pos: np.ndarray, cost_mult: float = 1.0) -> np.ndarray:
    lp = np.log(case.prices)
    r = np.diff(lp)
    held = pos[:-1]
    turnover = np.abs(np.diff(np.concatenate([[0.0], held])))
    out: np.ndarray = held * r - cost_mult * case.cost_per_trade * turnover
    return out


def features(case: Case, pos: np.ndarray | None = None) -> dict[str, float]:
    """Every number a check may read; test_invention composes new checks over these names."""
    pos = positions(case) if pos is None else pos
    p = pnl(case, pos)
    n = len(p)
    sd = float(p.std(ddof=1)) if n > 2 else 0.0
    sr = float(p.mean() / sd) if sd > 0 else 0.0
    r = np.diff(np.log(case.prices))
    zero_share = float(np.mean(np.abs(r) < 1e-12)) if len(r) else 0.0
    ac1 = float(np.corrcoef(r[:-1], r[1:])[0, 1]) if len(r) > 3 and r.std() > 0 else 0.0
    half = n // 2
    s1 = float(p[:half].mean() / (p[:half].std() + 1e-12)) if half > 2 else 0.0
    s2 = float(p[half:].mean() / (p[half:].std() + 1e-12)) if n - half > 2 else 0.0
    return {"sr": sr, "t": sr * math.sqrt(max(n, 1)), "n": float(n), "zero_share": zero_share,
            "ac1": ac1, "sr_first_half": s1, "sr_second_half": s2,
            "decay": s1 - s2, "turnover": float(np.mean(np.abs(np.diff(pos)))),
            "variants": float(case.n_variants_tried)}


def _lookahead(case: Case, cfg: ValidatorConfig) -> bool:
    n = len(case.prices)
    rng = np.random.default_rng(12345)
    probes = np.linspace(5, n - 3, num=min(cfg.lookahead_probes, max(1, n - 8))).astype(int)
    for t in probes:
        alt = case.prices.copy()
        tail = n - (t + 1)
        if tail <= 0:
            continue
        alt[t + 1:] = alt[t] * np.exp(np.cumsum(rng.normal(0, 0.02, size=tail)))
        if case.signal_fn(case.prices, int(t)) != case.signal_fn(alt, int(t)):
            return True
    return False


def _ols_t(y: np.ndarray, x: np.ndarray) -> tuple[float, float]:
    """(corr, t-stat of intercept) of y on x."""
    if len(y) < 10 or x.std() == 0 or y.std() == 0:
        return 0.0, 0.0
    corr = float(np.corrcoef(x, y)[0, 1])
    X = np.column_stack([np.ones_like(x), x])
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    if float(resid.std()) <= 1e-9 * float(y.std()):
        return corr, 0.0  # y IS the held factor: nothing left over to be significant
    s2 = float(resid @ resid) / max(1, len(y) - 2)
    cov = s2 * np.linalg.pinv(X.T @ X)
    se = math.sqrt(max(cov[0, 0], 1e-300))
    return corr, float(beta[0] / se)


def reference_validator(cfg: ValidatorConfig | None = None) -> Validator:
    cfg = cfg or ValidatorConfig()

    def run(case: Case) -> tuple[bool, list[str]]:
        reasons: list[str] = []
        if cfg.lookahead_on and _lookahead(case, cfg):
            reasons.append("LOOKAHEAD: signal changes when only the future is changed")
        if cfg.fills_on:
            bad = np.mean((case.fills < case.lows - cfg.fill_tolerance)
                          | (case.fills > case.highs + cfg.fill_tolerance))
            if bad > 0:
                reasons.append(f"FILLS: {bad:.1%} of fills outside the bar range")
        pos = positions(case)
        p = pnl(case, pos, cfg.cost_stress)
        feats = features(case, pos)
        if cfg.stale_on and feats["zero_share"] > cfg.stale_zero_share:
            reasons.append(f"STALE: {feats['zero_share']:.0%} zero returns")
        if cfg.dsr_on:
            if p.std() == 0 or len(p) < 30:
                reasons.append("DSR: degenerate pnl")
            else:
                from libs.validation.dsr import deflated_sharpe_ratio
                res = deflated_sharpe_ratio(p, n_trials=max(1, case.n_variants_tried),
                                            variance_of_sharpes=1.0 / len(p),
                                            threshold=cfg.dsr_threshold)
                if not res.passed:
                    reasons.append(f"DSR: {res.dsr:.3f} < {cfg.dsr_threshold} at "
                                   f"{case.n_variants_tried} trials")
        if cfg.wf_on and len(p) >= cfg.wf_folds * 20:
            folds = np.array_split(p, cfg.wf_folds)
            pos_folds = sum(1 for f in folds if f.mean() > 0)
            if pos_folds < cfg.wf_min_positive:
                reasons.append(f"WALK_FORWARD: {pos_folds}/{cfg.wf_folds} folds positive")
            if cfg.wf_last_half_positive and np.concatenate(
                    folds[cfg.wf_folds // 2:]).mean() <= 0:
                reasons.append("WALK_FORWARD: nothing left in the second half")
        if cfg.factor_on:
            f = case.factor_returns
            fpos = np.sign(f[: len(case.prices)])
            fp = pnl(case, fpos)
            corr, t = _ols_t(p, fp)
            if abs(corr) > cfg.factor_corr_max and t < cfg.factor_resid_t:
                reasons.append(f"FACTOR: corr {corr:.2f} with a held factor, residual t {t:.2f}")
        if cfg.survivorship_on and not bool(np.all(case.universe_alive)):
            # The book was drawn from a universe that included assets now dead. Re-run the SAME
            # positions on the universe as it stood ex ante; an edge that exists only among the
            # survivors is the survivorship itself.
            u = case.universe_returns.mean(axis=1)
            lp = np.diff(np.log(case.prices))
            m = min(len(u), len(lp))
            corr, _t = _ols_t(lp[:m], u[:m])
            full = pos[: m - 1] * u[1:m]
            ft = float(full.mean() / (full.std() + 1e-12) * math.sqrt(len(full)))
            if corr > cfg.survivorship_corr and ft < cfg.survivorship_t:
                reasons.append(f"SURVIVORSHIP: on the ex-ante universe t {ft:.2f}")
        for metric, op, thr in cfg.extra:
            v = feats.get(metric)
            if v is None:
                continue
            if (op == ">" and v > thr) or (op == "<" and v < thr):
                reasons.append(f"INVENTED: {metric} {op} {thr:.4g} ({v:.4g})")
        return (not reasons), reasons

    return run


@dataclass(frozen=True)
class Suite:
    per_kind: int = 12
    n: int = 1500
    base_seed: int = 20260929

    def cases(self) -> Iterable[tuple[Case, Truth]]:
        for k_i, kind in enumerate(traps.ALL_KINDS):
            for j in range(self.per_kind):
                yield traps.generate(kind, self.base_seed + 1000 * k_i + j, self.n)

    def seal(self) -> str:
        h = hashlib.sha256()
        h.update(inspect.getsource(traps).encode())
        h.update(f"{self.per_kind}|{self.n}|{self.base_seed}".encode())
        for case, truth in self.cases():
            h.update(case.prices.tobytes())
            h.update(truth.kind.encode())
        return h.hexdigest()


def score(validator: Validator, suite: Suite | None = None,
          cases: list[tuple[Case, Truth]] | None = None) -> dict[str, Any]:
    suite = suite or Suite()
    rows = cases if cases is not None else list(suite.cases())
    per_kind: dict[str, dict[str, int]] = {}
    tp = fn = tn = fp = 0
    for case, truth in rows:
        ok, _reasons = validator(case)
        d = per_kind.setdefault(truth.kind, {"n": 0, "accepted": 0})
        d["n"] += 1
        d["accepted"] += int(ok)
        if truth.genuine:
            tp += int(ok)
            fn += int(not ok)
        else:
            fp += int(ok)
            tn += int(not ok)
    immune = tn / (tn + fp) if tn + fp else None
    power = tp / (tp + fn) if tp + fn else None
    balanced = ((immune or 0.0) + (power or 0.0)) / 2 if immune is not None \
        and power is not None else None
    return {"immune_score": immune, "power": power, "balanced": balanced,
            "n_cases": len(rows), "per_kind": {k: {**v, "accept_rate": v["accepted"] / v["n"]}
                                                for k, v in sorted(per_kind.items())},
            "traps_let_through": {k: v["accepted"] for k, v in per_kind.items()
                                  if k in traps.TRAP_KINDS and v["accepted"]}}


def immune_verdict(result: Mapping[str, Any], history: Iterable[Mapping[str, Any]], *,
                   floor: float = 0.9, max_drop: float = 0.05, seal: str = "") -> dict[str, Any]:
    """FREEZE when the desk got easier to fool; OK otherwise. Only same-seal history counts."""
    imm = result.get("immune_score")
    same = [float(h["immune_score"]) for h in history
            if h.get("seal") == seal and h.get("immune_score") is not None]
    best = max(same) if same else None
    if imm is None:
        return {"verdict": "UNMEASURED", "why": "no traps scored"}
    if float(imm) < floor:
        return {"verdict": "FREEZE", "why": f"immune score {imm:.3f} below the constitutional "
                f"floor {floor}", "best": best}
    if best is not None and float(imm) < best - max_drop:
        return {"verdict": "FREEZE", "why": f"immune score fell {best:.3f} -> {imm:.3f}",
                "best": best}
    return {"verdict": "OK", "immune_score": imm, "best": best}


def with_extra(cfg: ValidatorConfig, check: tuple[str, str, float]) -> ValidatorConfig:
    return replace(cfg, extra=(*cfg.extra, check))
