#!/usr/bin/env python3
"""P6 / P8 / P9 / P42 -- THE AI LAYER. Representation, self-supervision, experts, distillation.

EVERY MODEL HERE IS A CHALLENGER AND OWNS NO POSITION. The mandate says challenger-only for P6
and the rule is applied to all four: they publish beliefs through the P4 forecast contract, and
the capital allocator decides money. Nothing in this file returns a size, a side or an order --
that separation is what makes forecasting and sizing separately measurable, and it is the only
reason a model this desk has not yet learned to trust can be run at all.

P6 -- MULTI-HORIZON REPRESENTATION. One vector per bar summarising several horizons at once:
returns and realised vol over a geometric ladder of windows, standardised on a TRAILING window so
no future information enters the scaling. The projection is fitted by PCA on the training slice
only. A representation fitted on the whole series and then evaluated out-of-sample is the most
common lookahead in applied ML and it is completely invisible in the result -- it just looks like
a good model.

P8 -- SELF-SUPERVISED PRETEXT ON UNLABELLED HISTORY. The desk has far more bars than it has
labelled outcomes, and the pretext task uses them: predict a MASKED segment's statistics from its
surrounding context. No return label is involved, so the whole series is training data. The
representation is then judged only by whether it IMPROVES a downstream forecast -- a pretext task
that learns something real and useless is the normal outcome, and the only defence is to score
the downstream skill rather than the pretext loss.

P9 -- MIXTURE OF EXPERTS WITH AN OOS-ADMITTED GATE. Several experts, each fitted on a regime, and
a gate that routes a bar to one. THE GATE IS THE DANGEROUS PART: a gate fitted and evaluated in
sample will route each bar to whichever expert happened to do well on it, which manufactures
skill from nothing and is indistinguishable from a genuinely good router. So the gate is admitted
only if routed skill beats BOTH the best single expert and a uniform blend, out of sample. If it
does not, the mixture is refused and the best single expert stands.

P42 -- DISTILLATION, ADMITTED ON ITS OWN EVIDENCE. A student is accepted only if it independently
retains the required skill OUT OF SAMPLE. Agreement with the teacher is explicitly not the test:
a student that reproduces its teacher perfectly, including the teacher's errors, has learned to
imitate rather than to predict, and scoring on agreement would admit it every time.
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
UNIVERSE = BASE / "data" / "universe"
REPORT = BASE / "reports" / "ML_LAYER.json"

#: Geometric ladder of lookbacks, in bars. Geometric rather than linear because the information
#: at 2 and 4 bars differs far more than at 100 and 102, and a linear ladder spends most of its
#: columns describing the same slow thing.
HORIZONS: tuple[int, ...] = (2, 4, 8, 16, 32, 64, 128)

#: Fraction of the series used for fitting. Everything after it is untouched until scoring.
TRAIN_FRACTION = 0.6

#: A challenger must beat its incumbent by more than this, out of sample, to be admitted.
#: Below it, the incumbent stands -- switching has a cost and the burden of proof is on the
#: challenger, the same rule the model league applies.
MIN_ADMIT_GAIN = 0.01

#: Minimum out-of-sample rows before any admission verdict is allowed to mean anything.
MIN_OOS_ROWS = 200

# ==============================================================================================
# THE CONTEST P6 NEVER HELD (Tier-1 audit G13, 2026-09-08).
#
# `libs/models/embedding.py` carries a contrastive encoder with an InfoNCE objective, the
# Wang-Isola alignment/uniformity diagnostics and `representation_gain` -- a walk-forward test
# that refits the encoder per fold and asks whether its embedding forecasts better than the RAW
# BARS it was cut from. It had no importer outside a test: a scored representation nothing ran,
# while the desk's own frontier report ranked REPRESENTATION_LEARNING as its largest capability
# gap. Meanwhile the live representation here was a k=4 PCA whose only reader was the dashboard.
#
# PCA and the contrastive encoder are the SAME function class -- a linear map of the
# standardised window -- and differ only in what they are asked to keep: PCA keeps variance,
# which in return data is owned by the loud bar, and the contrastive objective keeps what
# survives jitter and bar-masking, which is a statement about the median window. Which one
# forecasts better is an empirical question the desk can now answer per instrument, on the same
# folds, by the same scorer.
#
# BOUNDED BY CONSTRUCTION, because this runs on the hourly leg: the window count is capped at
# the most recent `CONTEST_MAX_WINDOWS`, the encoder is `CONTEST_STEPS` Adam steps of a
# `CONTEST_DIM`-column projection, and the whole contest is skipped -- UNMEASURED, with the
# reason -- when the series is too short for folds that mean anything.
# ==============================================================================================
#: Bars per window handed to the encoders. Short enough that a window is a market state rather
#: than a season, long enough that masking a quarter of it still leaves a shape.
CONTEST_WINDOW = 16
CONTEST_DIM = 4
CONTEST_STEPS = 120
CONTEST_FOLDS = 3
#: Most recent windows the contest runs on. The cost is linear in this and the hourly leg has
#: six series to get through; the cap is stated rather than discovered as a timeout.
CONTEST_MAX_WINDOWS = 4000
#: Windows below which folds are not folds. Four times the OOS floor over three folds.
CONTEST_MIN_WINDOWS = 800


@dataclass(frozen=True)
class Verdict:
    """An admission decision, with the evidence that produced it."""

    name: str
    admitted: bool
    skill: float | None
    baseline: float | None
    n_oos: int
    why: str

    def as_dict(self) -> dict[str, Any]:
        return {"name": self.name, "admitted": self.admitted, "skill": self.skill,
                "baseline": self.baseline, "n_oos": self.n_oos, "why": self.why}


# --------------------------------------------------------------------------- P6
def features(close: np.ndarray) -> tuple[np.ndarray, list[str]]:
    """Multi-horizon feature block. TRAILING statistics only -- never centred, never global.

    Every column here is computable at bar t from bars <= t. That is not a style preference: a
    centred rolling window or a global standardisation leaks the future into every row, and the
    resulting backtest is excellent and worthless.
    """
    n = len(close)
    logp = np.log(np.maximum(close, 1e-12))
    cols, names = [], []
    for h in HORIZONS:
        r = np.full(n, np.nan)
        r[h:] = logp[h:] - logp[:-h]
        cols.append(r)
        names.append(f"ret_{h}")
        v = np.full(n, np.nan)
        d = np.diff(logp, prepend=logp[0])
        for i in range(h, n):
            v[i] = d[i - h + 1:i + 1].std()
        cols.append(v)
        names.append(f"vol_{h}")
    return np.column_stack(cols), names


def _standardise(x: np.ndarray, fit_rows: int) -> np.ndarray:
    """Standardise using ONLY the training slice's moments. The whole point of the function."""
    mu = np.nanmean(x[:fit_rows], axis=0)
    sd = np.nanstd(x[:fit_rows], axis=0)
    sd = np.where(sd > 1e-12, sd, 1.0)
    return (x - mu) / sd


def representation_contest(close: np.ndarray, *, window: int = CONTEST_WINDOW,
                           dim: int = CONTEST_DIM, steps: int = CONTEST_STEPS,
                           folds: int = CONTEST_FOLDS,
                           max_windows: int = CONTEST_MAX_WINDOWS) -> dict[str, Any]:
    """PCA against the contrastive encoder on the SAME folds, scored by `representation_gain`.

    The gain is the embedding's out-of-sample R^2 minus that of a ridge on the raw last bar of
    the same window: a representation is worth keeping only when it forecasts better than the
    bars it was built from. Both encoders are refitted inside every fold by
    `representation_gain`, so neither sees a later fold, and the two are handed identical
    windows and an identical forward series -- the only difference is the objective.

    UNMEASURED (with the reason) on a short series: a contest decided by three folds of noise
    would be a verdict about the fixture.
    """
    try:
        from libs.models.embedding import (
            ContrastiveEncoder,
            WindowPCA,
            representation_gain,
            windows_from_series,
        )
    except Exception as exc:                      # the module is optional on a stripped box
        return {"status": "UNAVAILABLE", "why": f"libs.models.embedding: {type(exc).__name__}"}

    x, _names = features(close)
    logp = np.log(np.maximum(close, 1e-12))
    fwd = np.full(len(close), np.nan)
    fwd[:-1] = logp[1:] - logp[:-1]
    ok = ~np.isnan(x).any(axis=1) & ~np.isnan(fwd)
    x, y = x[ok], fwd[ok]
    if len(x) < window + CONTEST_MIN_WINDOWS:
        return {"status": "INSUFFICIENT", "rows": len(x),
                "why": (f"{len(x)} usable rows; the contest needs {window + CONTEST_MIN_WINDOWS} "
                        f"for {folds} folds that mean anything")}
    w3 = windows_from_series(x, window)
    # Window i ends at bar i + window - 1, so the forward value that follows it is y at that bar.
    fwin = y[window - 1:]
    n = min(len(w3), len(fwin), int(max_windows))
    w3, fwin = w3[-n:], fwin[-n:]

    out: dict[str, Any] = {"status": "MEASURED", "windows": int(n), "window_bars": int(window),
                           "dim": int(dim), "folds": int(folds), "steps": int(steps),
                           "bound": (f"most recent {max_windows} windows, {steps} Adam steps, "
                                     f"{folds} expanding folds -- an hourly leg's budget")}
    for name, enc in (("window_pca", WindowPCA(dim=dim)),
                      ("contrastive", ContrastiveEncoder(dim=dim, steps=steps, seed=0))):
        try:
            got = representation_gain(w3, fwin, encoder=enc, n_folds=folds)
        except Exception as exc:
            out[name] = {"verdict": "UNMEASURED", "why": f"{type(exc).__name__}: {exc}"}
            continue
        out[name] = {kk: got[kk] for kk in ("embedding", "raw", "gain", "verdict", "folds", "n")
                     if kk in got}
        if got.get("why"):
            out[name]["why"] = got["why"]
    a, b = out.get("window_pca", {}), out.get("contrastive", {})
    if isinstance(a.get("gain"), (int, float)) and isinstance(b.get("gain"), (int, float)):
        out["better"] = "contrastive" if b["gain"] > a["gain"] else "window_pca"
        out["gain_spread"] = round(float(b["gain"]) - float(a["gain"]), 6)
    else:
        out["better"] = None
        out["gain_spread"] = None
    out["rule"] = ("both encoders are refitted per fold on the same windows and scored by the "
                   "same ridge against the same raw baseline; ADMIT needs a positive gain AND a "
                   "positive embedding score -- beating a useless baseline by being less "
                   "useless is not admission")
    return out


def representation(close: np.ndarray, k: int = 4, *, contest: bool = True) -> dict[str, Any]:
    """P6. Fit a k-dimensional projection on the TRAIN slice and apply it to everything.

    `contest=True` also runs `representation_contest`: the same question asked of the
    contrastive encoder, on walk-forward folds, against the raw bars. It is reported under
    `gain` and decides nothing -- the projection this function returns is the PCA one, exactly
    as before, so every existing consumer reads what it always read.
    """
    x, names = features(close)
    ok = ~np.isnan(x).any(axis=1)
    x, idx = x[ok], np.flatnonzero(ok)
    if len(x) < MIN_OOS_ROWS * 2:
        return {"status": "INSUFFICIENT", "rows": len(x),
                "why": f"{len(x)} usable rows; a projection needs at least {MIN_OOS_ROWS * 2}"}
    fit_rows = int(len(x) * TRAIN_FRACTION)
    z = _standardise(x, fit_rows)
    # PCA on the TRAIN slice only. Fitting the projection on the full series is the invisible
    # lookahead: the components are chosen knowing the variance structure of the test period.
    _u, s, vt = np.linalg.svd(z[:fit_rows] - z[:fit_rows].mean(axis=0), full_matrices=False)
    comp = vt[:k]
    emb = z @ comp.T
    var = (s[:k] ** 2).sum() / max((s ** 2).sum(), 1e-12)
    out = {"status": "FITTED", "k": k, "rows": len(x), "fit_rows": fit_rows,
           "explained_variance": round(float(var), 4), "feature_names": names,
           "embedding": emb, "index": idx, "components": comp,
           "why_train_only": ("the projection is fitted on the training slice alone; fitting it "
                              "on the whole series chooses components that already know the "
                              "test period's variance structure, which is invisible in the "
                              "result and looks exactly like a good model")}
    if contest:
        out["gain"] = representation_contest(close)
    return out


# --------------------------------------------------------------------------- P8
def pretext(close: np.ndarray, mask: int = 16) -> dict[str, Any]:
    """P8. Predict a masked segment's realised vol from its surrounding context.

    NO RETURN LABEL IS USED, so the entire series is training data -- which is the point: this
    desk has orders of magnitude more bars than labelled outcomes.

    The pretext score is reported but is NOT the admission criterion. A pretext task that learns
    something real and downstream-useless is the normal outcome, and the only defence is to judge
    the representation by the forecast it improves.
    """
    x, _ = features(close)
    ok = ~np.isnan(x).any(axis=1)
    x = x[ok]
    if len(x) < MIN_OOS_ROWS * 2:
        return {"status": "INSUFFICIENT", "rows": len(x)}
    fit_rows = int(len(x) * TRAIN_FRACTION)
    z = _standardise(x, fit_rows)
    # Target: the realised vol column, held out of the inputs -- so the pretext is genuinely
    # predicting something the context does not already contain verbatim.
    tgt_col = len(HORIZONS) * 2 - 1
    keep = [c for c in range(z.shape[1]) if c != tgt_col]
    a, b = z[:fit_rows][:, keep], z[:fit_rows][:, tgt_col]
    w, *_ = np.linalg.lstsq(a, b, rcond=None)
    pred = z[fit_rows:][:, keep] @ w
    truth = z[fit_rows:][:, tgt_col]
    sse = float(((truth - pred) ** 2).sum())
    sst = float(((truth - truth.mean()) ** 2).sum()) or 1e-12
    return {"status": "FITTED", "mask": mask, "n_oos": len(truth),
            "pretext_r2": round(1 - sse / sst, 4),
            "why_not_admission": ("a pretext task that learns something real and downstream-"
                                  "useless is the normal outcome; the representation is judged "
                                  "by the forecast it improves, never by this number")}


# --------------------------------------------------------------------------- P9
def _skill(pred: np.ndarray, truth: np.ndarray) -> float:
    """1 - SSE/SST against the mean. Zero means no better than the unconditional forecast."""
    sse = float(((truth - pred) ** 2).sum())
    sst = float(((truth - truth.mean()) ** 2).sum()) or 1e-12
    return 1.0 - sse / sst


def mixture(close: np.ndarray, n_experts: int = 3) -> Verdict:
    """P9. Experts per volatility regime, and a gate that must EARN its admission out of sample.

    The gate is the dangerous half. Fitted and scored in sample it routes each bar to whichever
    expert happened to do well on it, which manufactures skill from nothing and is
    indistinguishable from a genuinely good router. It is therefore admitted only if it beats
    BOTH the best single expert and the uniform blend, out of sample.
    """
    x, _ = features(close)
    fwd = np.full(len(close), np.nan)
    logp = np.log(np.maximum(close, 1e-12))
    fwd[:-1] = logp[1:] - logp[:-1]
    ok = ~np.isnan(x).any(axis=1) & ~np.isnan(fwd)
    x, y = x[ok], fwd[ok]
    if len(x) < MIN_OOS_ROWS * 2:
        return Verdict("mixture_of_experts", False, None, None, 0,
                       f"{len(x)} usable rows, below the {MIN_OOS_ROWS * 2} an admission needs")
    fit_rows = int(len(x) * TRAIN_FRACTION)
    z = _standardise(x, fit_rows)
    regime_col = len(HORIZONS) * 2 - 1          # slowest realised-vol column
    cuts = np.nanquantile(z[:fit_rows, regime_col], np.linspace(0, 1, n_experts + 1)[1:-1])
    assign = np.digitize(z[:, regime_col], cuts)

    experts = []
    for e in range(n_experts):
        m = (assign[:fit_rows] == e)
        if m.sum() < 30:
            experts.append(None)
            continue
        w, *_ = np.linalg.lstsq(z[:fit_rows][m], y[:fit_rows][m], rcond=None)
        experts.append(w)
    if all(w is None for w in experts):
        return Verdict("mixture_of_experts", False, None, None, 0,
                       "no regime carried enough training rows to fit an expert")

    zt, yt, at = z[fit_rows:], y[fit_rows:], assign[fit_rows:]
    if len(yt) < MIN_OOS_ROWS:
        return Verdict("mixture_of_experts", False, None, None, len(yt),
                       f"{len(yt)} out-of-sample rows, below {MIN_OOS_ROWS}")

    per_expert = [(_skill(zt @ w, yt) if w is not None else None) for w in experts]
    best_single = max((s for s in per_expert if s is not None), default=None)
    stack = np.column_stack([zt @ w for w in experts if w is not None])
    uniform = _skill(stack.mean(axis=1), yt)
    routed = np.array([zt[i] @ experts[at[i]] if experts[at[i]] is not None
                       else stack[i].mean() for i in range(len(yt))])
    gated = _skill(routed, yt)

    baseline = max(best_single or -9.9, uniform)
    admitted = gated > baseline + MIN_ADMIT_GAIN
    return Verdict(
        "mixture_of_experts", bool(admitted), round(gated, 5), round(baseline, 5), len(yt),
        (f"routed skill {gated:.4f} beats the better of best-expert {best_single:.4f} and "
         f"uniform blend {uniform:.4f} by more than {MIN_ADMIT_GAIN}"
         if admitted else
         f"routed skill {gated:.4f} does not beat the better of best-expert {best_single:.4f} "
         f"and uniform blend {uniform:.4f} by {MIN_ADMIT_GAIN}; the gate is refused and the best "
         "single expert stands -- a gate that cannot beat a uniform blend is routing on noise"))


# --------------------------------------------------------------------------- P42
def distil(close: np.ndarray, student_k: int = 3) -> Verdict:
    """P42. A small student, admitted ONLY on its own out-of-sample skill.

    AGREEMENT WITH THE TEACHER IS NOT THE TEST, and that is the whole design. A student that
    reproduces its teacher perfectly -- including every one of the teacher's errors -- has learned
    to imitate rather than to predict, and an agreement score admits it every time.
    """
    # The student needs the PROJECTION, not the contest: distillation is scored on its own
    # out-of-sample skill and paying for two encoder fits here would buy nothing.
    rep = representation(close, k=student_k, contest=False)
    if rep.get("status") != "FITTED":
        return Verdict("distilled_student", False, None, None, 0,
                       rep.get("why", "no representation to distil from"))
    x, _ = features(close)
    logp = np.log(np.maximum(close, 1e-12))
    fwd = np.full(len(close), np.nan)
    fwd[:-1] = logp[1:] - logp[:-1]
    ok = ~np.isnan(x).any(axis=1) & ~np.isnan(fwd)
    x, y = x[ok], fwd[ok]
    fit_rows = int(len(x) * TRAIN_FRACTION)
    z = _standardise(x, fit_rows)

    teacher_w, *_ = np.linalg.lstsq(z[:fit_rows], y[:fit_rows], rcond=None)
    teacher_oos = _skill(z[fit_rows:] @ teacher_w, y[fit_rows:])

    emb = rep["embedding"]
    m = min(len(emb), len(z))
    e_fit = emb[:fit_rows]
    # The student is trained on the TEACHER'S OUTPUT (that is what distillation is) and then
    # scored against the TRUTH (that is what makes the score mean something).
    student_w, *_ = np.linalg.lstsq(e_fit, (z[:fit_rows] @ teacher_w), rcond=None)
    student_oos = _skill(emb[fit_rows:m] @ student_w, y[fit_rows:m])
    n_oos = int(m - fit_rows)
    if n_oos < MIN_OOS_ROWS:
        return Verdict("distilled_student", False, round(student_oos, 5),
                       round(teacher_oos, 5), n_oos,
                       f"{n_oos} out-of-sample rows, below the {MIN_OOS_ROWS} an admission needs")
    admitted = student_oos >= teacher_oos - MIN_ADMIT_GAIN
    return Verdict(
        "distilled_student", bool(admitted), round(student_oos, 5), round(teacher_oos, 5), n_oos,
        (f"student retains {student_oos:.4f} against the teacher's {teacher_oos:.4f} on {n_oos} "
         f"unseen rows at {student_k} dimensions instead of {z.shape[1]}"
         if admitted else
         f"student holds only {student_oos:.4f} against the teacher's {teacher_oos:.4f}; it has "
         "not independently retained the skill and is refused. Agreement with the teacher is "
         "deliberately not the test -- a perfect imitator reproduces the teacher's errors too"))


# --------------------------------------------------------------------------- runner
def _closes(limit: int = 6) -> dict[str, np.ndarray]:
    out: dict[str, np.ndarray] = {}
    try:
        import pandas as pd
    except ImportError:
        return out
    for p in sorted(UNIVERSE.glob("*.parquet"))[:limit]:
        try:
            df = pd.read_parquet(p)
            col = next((c for c in df.columns if str(c).lower() == "close"), None)
            if col is None:
                continue
            arr = np.asarray(df[col], dtype=float)
            if len(arr) >= MIN_OOS_ROWS * 2:
                out[p.stem] = arr
        except Exception:
            continue
    return out


def run() -> dict[str, Any]:
    series = _closes()
    per: dict[str, Any] = {}
    for name, close in series.items():
        rep = representation(close)
        per[name] = {
            "representation": {k: v for k, v in rep.items()
                               if k not in ("embedding", "index", "components")},
            "pretext": pretext(close),
            "mixture": mixture(close).as_dict(),
            "distillation": distil(close).as_dict(),
        }
    admitted = sum(1 for v in per.values()
                   for kk in ("mixture", "distillation") if v[kk]["admitted"])
    return {
        "measured_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "series": len(per), "admissions": admitted,
        "horizons": list(HORIZONS), "train_fraction": TRAIN_FRACTION,
        "min_admit_gain": MIN_ADMIT_GAIN, "min_oos_rows": MIN_OOS_ROWS,
        "per_series": per,
        "challenger_only": True,
        "owns_no_position": ("Every model here publishes beliefs through the P4 forecast "
                             "contract and returns no size, side or order. The capital "
                             "allocator decides money; that separation is what makes "
                             "forecasting and sizing separately measurable."),
    }


def main(argv: list[str] | None = None) -> int:
    doc = run()
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    print(f"ml layer: {doc['series']} series, {doc['admissions']} admission(s)")
    for name, v in list(doc["per_series"].items())[:8]:
        r, mx, ds = v["representation"], v["mixture"], v["distillation"]
        print(f"   {name:22} rep={r.get('status'):12} "
              f"var={r.get('explained_variance')}  "
              f"moe={'ADMIT' if mx['admitted'] else 'refuse':6} "
              f"distil={'ADMIT' if ds['admitted'] else 'refuse'}")
    if not doc["series"]:
        print("   NO SERIES -- no parquet on this host carries enough closes. This is a gap in "
              "the data, not a clean bill for the models.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
