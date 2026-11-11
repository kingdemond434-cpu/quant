"""SLEEVE FORECAST LEDGER: what the allocator believed about each sleeve before the outcome, and
whether the outcomes were worse than it believed (ALLOC-08, ALLOC-24, ALLOC-28, DECAY-05, DECAY-07).

Mandate 2026-10-06, Growth allocator overhaul:
  ALLOC-28 "Each sleeve forecast names sleeve/model version, info cutoff, state, horizon,
           expected return, uncertainty, dependence, costs, expiry ..."
  DECAY-05 "keep a versioned conditional future net-return distribution with expected return,
           confidence, horizon, evidence cutoff, effective sample, regime, expiry, current costs"
  DECAY-07 "Preserve the forecast made before each outcome and test whether outcomes are worse
           than predicted, using time-uniform confidence sequences and cross-sleeve error control"
  ALLOC-08 "calibration of forecast distributions, tail representation ... vs realised"
  ALLOC-24 "The allocator publishes research requests: ... cost-dominated forecasts, missing
           inputs dominating uncertainty"

None of these existed: the allocator's posterior was recomputed every pass and thrown away, so
no outcome could ever be checked against the belief that sized it.

PUBLISH. Once per evidence cutoff (the last day of the daily matrix), each sleeve gets one row
in `data/sleeve_forecasts.jsonl`, an append-only ledger:

    forecast_id      sleeve @ cutoff
    model            "robust_elog._posterior_mu", the allocator's own hierarchical posterior
    model_version    sha256 of robust_elog's source (12 hex)
    info_cutoff      last evidence day the posterior read
    horizon_days     `HORIZON` (5, the allocator's holding window)
    expiry           cutoff + horizon business days: after it the row is a claim to be scored
    expected_r       horizon x posterior mean daily R
    mean_se          horizon x posterior standard error (parameter uncertainty)
    predictive_sd    sqrt(horizon x daily variance + mean_se^2) (noise plus parameter)
    n_obs, n_eff     days the sleeve has, and its Kish effective sample under the macro kernel
    regime           the newest regime label `regime_state` gives, or UNMEASURED
    cost_r_horizon   horizon x activity x |cost_r|: the cost the horizon is expected to pay
    corr_to_book     the sleeve's correlation with the equal-weight book (its dependence)

SCORE. A row whose expiry has passed and whose horizon days are in the matrix is scored:
    realized_r = the sum of the sleeve's R over the horizon days after the cutoff
    PIT        = Phi((realized - expected) / predictive_sd)

Calibration (ALLOC-08) reads the PITs: their mean (0.5 when calibrated), the 80% and 95%
interval coverage, and the left-tail rate P(PIT < 0.05) (0.05 when the tail is represented).

THE ANYTIME-VALID TEST (DECAY-07). Per sleeve, H0 is "outcomes are not worse than forecast",
meaning PIT is stochastically at least uniform, so E[1 - 2 PIT] <= 0. The e-process is
    E_t = mean over lambda in `LAMBDAS` of prod_s (1 + lambda (1 - 2 PIT_s))
This is a nonnegative supermartingale under H0 for any stopping time (each factor is in
[1 - lambda, 1 + lambda] with mean <= 1), so it is time-uniform: it can be read every hour
without paying for peeking. Cross-sleeve error control is e-BH at `ALPHA` (Wang & Ramdas
2022). e-BH is valid under arbitrary dependence, which sleeves sharing a factor have. A sleeve
it rejects is WORSE_THAN_FORECAST.

RESEARCH REQUESTS (ALLOC-24), per newest forecast:
    cost_dominated       the horizon's expected cost >= |expected_r|: the edge is a cost question
    uncertainty_bound    mean_se^2 >= half the predictive variance: the parameter uncertainty is
                         the larger part of the forecast's uncertainty, so more evidence on this
                         sleeve is worth more than another model

AUTHORITY: none. This is a ledger and a report (`reports/SLEEVE_FORECASTS.json`). A
WORSE_THAN_FORECAST sleeve is evidence for `decay_monitor` and the health lab to weigh. It
retires nothing by itself.
"""
from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import math
import os
import sys
import time
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
for _p in (str(BASE), str(BASE / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

LEDGER = BASE / "data" / "sleeve_forecasts.jsonl"
OUT = BASE / "reports" / "SLEEVE_FORECASTS.json"
MODEL = "robust_elog._posterior_mu"
#: Forecast horizon in trading days; derived from the allocator: 5 days is
#: `input_ablation.HORIZON`, the window a solved book is held over before it is re-solved.
HORIZON = 5
#: e-BH level. 0.05 is the desk's family-wise level (`input_ablation.FAMILY_ALPHA` = 0.05).
ALPHA = 0.05
#: Betting fractions mixed in the e-process. Derived as a geometric grid 0.05..0.8: small bets
#: win against slight optimism and large bets against gross optimism, and the mixture pays at
#: most a factor of 5 (the grid size) for not knowing which in advance.
LAMBDAS = (0.05, 0.1, 0.2, 0.4, 0.8)
#: Minimum scored outcomes before a sleeve enters e-BH. 1 is enough for validity; 5 is
#: derived from the horizon (one week of outcomes) so a verdict is never one draw.
MIN_SCORED = 5


def model_version() -> str:
    from libs.portfolio import robust_elog
    return hashlib.sha256(inspect.getsource(robust_elog).encode()).hexdigest()[:12]


def _phi(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


# ------------------------------------------------------------------ publish

def make_rows(names: Sequence[str], daily: pd.DataFrame, post_mean: Mapping[str, float],
              se: Mapping[str, float], *, cost_r: Mapping[str, float] | None = None,
              n_eff: Mapping[str, float] | None = None, regime: str = "UNMEASURED",
              version: str = "", horizon: int = HORIZON) -> list[dict[str, Any]]:
    """One forecast row per sleeve from the posterior, as of the matrix's last day."""
    cutoff = str(daily.index[-1])[:10]
    # The horizon is counted in TRADING days (score() counts matrix rows), so the expiry is the
    # cutoff plus `horizon` business days, not calendar days.
    expiry = str(np.busday_offset(np.datetime64(cutoff), horizon, roll="forward"))
    book = daily.mean(axis=1, skipna=True)
    rows = []
    for n in names:
        if n not in post_mean or n not in daily.columns:
            continue
        col = daily[n]
        ok = col.dropna()
        if ok.size < 2:
            continue
        var = float(ok.var(ddof=1))
        mu, s = float(post_mean[n]), float(se.get(n, 0.0))
        mean_se = horizon * s
        pred_sd = math.sqrt(max(horizon * var + mean_se ** 2, 0.0))
        act = float((ok != 0).mean())
        both = pd.concat([col, book], axis=1).dropna()
        corr = (float(np.corrcoef(both.iloc[:, 0], both.iloc[:, 1])[0, 1])
                if len(both) > 2 and both.iloc[:, 0].std() > 0 and both.iloc[:, 1].std() > 0
                else None)
        rows.append({
            "forecast_id": f"{n}@{cutoff}", "sleeve": n, "model": MODEL,
            "model_version": version, "info_cutoff": cutoff, "horizon_days": horizon,
            "expiry": expiry, "expected_r": round(horizon * mu, 8),
            "mean_se": round(mean_se, 8), "predictive_sd": round(pred_sd, 8),
            "n_obs": int(ok.size),
            "n_eff": (round(float(n_eff[n]), 2) if n_eff and n in n_eff else int(ok.size)),
            "regime": regime,
            "cost_r_horizon": round(horizon * act * abs(float((cost_r or {}).get(n, 0.0))), 8),
            "corr_to_book": round(corr, 4) if corr is not None and math.isfinite(corr) else None,
            "published_utc": datetime.now(UTC).isoformat(),
        })
    return rows


def read_ledger(path: Path = LEDGER) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    try:
                        out.append(json.loads(line))
                    except ValueError:
                        continue
    except OSError:
        pass
    return out


def append_new(rows: Sequence[Mapping[str, Any]], path: Path = LEDGER) -> int:
    """Append rows whose forecast_id is not in the ledger yet. Never rewrites a past row."""
    have = {r.get("forecast_id") for r in read_ledger(path)}
    new = [r for r in rows if r.get("forecast_id") not in have]
    if new:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8", newline="\n") as fh:
            for r in new:
                fh.write(json.dumps(r, sort_keys=True) + "\n")
    return len(new)


# ------------------------------------------------------------------ score

#: A row counts as point-in-time only if it was published within this many calendar days of its
#: info_cutoff: derived as a weekend (2 days, a Friday cutoff first published on Sunday) plus one
#: day of evidence-cache age (the matrix is rebuilt once a day), 3 days in all. A row written
#: later than that could have been written knowing part of its own outcome window.
PIT_LAG_DAYS = 3


def _point_in_time(r: Mapping[str, Any]) -> bool:
    pub = str(r.get("published_utc") or "")[:10]
    cut = str(r.get("info_cutoff") or "")[:10]
    try:
        return (date.fromisoformat(pub) - date.fromisoformat(cut)).days <= PIT_LAG_DAYS
    except ValueError:
        return True                                     # no stamp: legacy row, kept


def non_overlapping(rows: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    """One sleeve's scored rows thinned so each bet settles before the next is placed.

    The e-process multiplies one bet per outcome; that product is a test supermartingale only
    when each outcome is unknown at the time of the next bet. Forecasts are written daily with a
    HORIZON-day window, so consecutive windows share HORIZON-1 days. Keeping a row only when its
    info_cutoff is on or after the previous kept row's outcome_end restores that order.
    """
    kept: list[Mapping[str, Any]] = []
    last_end = ""
    for r in sorted(rows, key=lambda x: str(x.get("info_cutoff"))):
        if not kept or str(r.get("info_cutoff")) >= last_end:
            kept.append(r)
            last_end = str(r.get("outcome_end") or r.get("info_cutoff"))
    return kept


def score(rows: Sequence[Mapping[str, Any]], daily: pd.DataFrame) -> list[dict[str, Any]]:
    """Every matured row with its realized horizon return and PIT."""
    idx = [str(d)[:10] for d in daily.index]
    pos = {d: i for i, d in enumerate(idx)}
    out = []
    for r in rows:
        n, cut, h = r.get("sleeve"), str(r.get("info_cutoff")), int(r.get("horizon_days") or 0)
        if n not in daily.columns or cut not in pos or h <= 0:
            continue
        i = pos[cut]
        if i + h >= len(idx):
            continue                                    # not matured in the matrix yet
        window = daily[n].iloc[i + 1:i + 1 + h]
        if window.isna().all():
            continue
        if not _point_in_time(r):
            continue                                    # published too long after its cutoff
        realized = float(window.fillna(0.0).sum())
        sd = float(r.get("predictive_sd") or 0.0)
        if not sd > 0:
            continue
        pit = _phi((realized - float(r["expected_r"])) / sd)
        out.append({**r, "realized_r": round(realized, 8), "pit": round(pit, 6),
                    "outcome_end": idx[i + h]})
    return out


def calibration(pits: Sequence[float]) -> dict[str, Any]:
    p = np.asarray(pits, dtype=float)
    if p.size == 0:
        return {"status": "UNMEASURED", "n": 0}
    return {"status": "MEASURED", "n": int(p.size), "mean_pit": round(float(p.mean()), 4),
            "cover_80": round(float(((p >= 0.1) & (p <= 0.9)).mean()), 4),
            "cover_95": round(float(((p >= 0.025) & (p <= 0.975)).mean()), 4),
            "left_tail_5": round(float((p < 0.05).mean()), 4),
            "right_tail_5": round(float((p > 0.95).mean()), 4),
            "ideal": {"mean_pit": 0.5, "cover_80": 0.8, "cover_95": 0.95, "left_tail_5": 0.05}}


def e_value(pits: Sequence[float], lambdas: Sequence[float] = LAMBDAS) -> float:
    """Mixture betting e-process against 'not worse than forecast' (PIT >= uniform)."""
    vals = []
    for lam in lambdas:
        w = 1.0
        for p in pits:
            w *= 1.0 + float(lam) * (1.0 - 2.0 * float(p))
        vals.append(w)
    return float(np.mean(vals)) if vals else 1.0


def e_bh(evals: Mapping[str, float], alpha: float = ALPHA) -> list[str]:
    """e-BH: reject the k largest e-values, k the largest with e_(k) >= K / (alpha k)."""
    items = sorted(evals.items(), key=lambda kv: -kv[1])
    k_n = len(items)
    best = 0
    for k in range(1, k_n + 1):
        if items[k - 1][1] >= k_n / (alpha * k):
            best = k
    return [n for n, _ in items[:best]]


def research_requests(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for r in rows:
        exp = abs(float(r.get("expected_r") or 0.0))
        cost = float(r.get("cost_r_horizon") or 0.0)
        sd = float(r.get("predictive_sd") or 0.0)
        se = float(r.get("mean_se") or 0.0)
        if cost > 0 and cost >= exp:
            out.append({"sleeve": r["sleeve"], "kind": "cost_dominated",
                        "why": f"horizon cost {cost:.4f}R >= |expected| {exp:.4f}R",
                        "ask": "measure this sleeve's real fill cost (markouts, spread by "
                               "session) before more alpha research"})
        if sd > 0 and se * se >= 0.5 * sd * sd:
            out.append({"sleeve": r["sleeve"], "kind": "uncertainty_bound",
                        "why": f"parameter variance {se * se:.6f} >= half the predictive "
                               f"{sd * sd:.6f}",
                        "ask": "more independent evidence (forward days, a new venue/session "
                               "sample) is worth more than another model"})
    return out


def judge(scored: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    by: dict[str, list[float]] = {}
    rows_by: dict[str, list[Mapping[str, Any]]] = {}
    for r in sorted(scored, key=lambda x: str(x.get("info_cutoff"))):
        by.setdefault(str(r["sleeve"]), []).append(float(r["pit"]))
        rows_by.setdefault(str(r["sleeve"]), []).append(r)
    # The e-process sees only bets that settled before the next was placed (non_overlapping);
    # calibration and the mean PIT still use every scored row.
    bets = {n: [float(r["pit"]) for r in non_overlapping(rs)] for n, rs in rows_by.items()}
    evals = {n: e_value(p) for n, p in bets.items() if len(p) >= MIN_SCORED}
    rejected = set(e_bh(evals))
    per = {n: {"n_scored": len(p), "n_bets": len(bets.get(n, [])), "e_value": round(evals[n], 4) if n in evals else None,
               "mean_pit": round(float(np.mean(p)), 4),
               "verdict": ("WORSE_THAN_FORECAST" if n in rejected else
                           "CONSISTENT" if n in evals else "UNMEASURED")}
           for n, p in by.items()}
    return {"per_sleeve": per, "n_tested": len(evals), "n_worse": len(rejected),
            "rule": (f"mixture betting e-process over lambda {list(LAMBDAS)} on 1 - 2 PIT, "
                     f"non-overlapping outcome windows only; "
                     f"e-BH at alpha {ALPHA} across sleeves with >= {MIN_SCORED} outcomes")}


# ------------------------------------------------------------------ the desk's pass

def _write(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()


def _desk_rows(daily: pd.DataFrame) -> list[dict[str, Any]]:
    from libs.portfolio import robust_elog as re_
    from research import pf_allocator as pa
    ev = pa.sleeve_evidence(daily, {}, {}, pa.search_trials())
    diag: dict[str, Any] = {}
    re_._posterior_mu(ev, np.random.default_rng(0), 1, diag)
    n_eff = {}
    for e in ev:
        w = np.asarray(getattr(e, "macro_w", np.array([])), dtype=float)
        if w.size and float((w * w).sum()) > 0:
            n_eff[e.name] = float(w.sum() ** 2 / (w * w).sum())
    regime = "UNMEASURED"
    try:
        labels, _probs, _ = pa.regime_state(daily)
        if labels:
            regime = str(labels[-1])
    except Exception:
        pass
    return make_rows([e.name for e in ev], daily, diag.get("post_mean", {}), diag.get("se", {}),
                     cost_r={e.name: float(e.cost_r) for e in ev}, n_eff=n_eff, regime=regime,
                     version=model_version())


def run(ledger: Path = LEDGER, out: Path = OUT, daily: pd.DataFrame | None = None,
        rows_fn: Any = None) -> dict[str, Any]:
    t0 = time.time()
    if daily is None:
        from research import pf_allocator as pa
        try:
            daily, _ = pa.build_evidence(force=False)
        except SystemExit as exc:
            # `build_evidence` REFUSES with SystemExit when the hunt report is absent. That is an
            # UNMEASURED pass for this leg, published as such, never a crashed leg.
            doc = {"generated_utc": datetime.now(UTC).isoformat(), "status": "UNMEASURED",
                   "authority": "none: a ledger and a report; it retires and sizes nothing",
                   "why": f"no evidence matrix: {str(exc)[:200]}", "n_scored": 0,
                   "elapsed_s": round(time.time() - t0, 2)}
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
            return doc
    daily = daily.sort_index()
    rows = (rows_fn or _desk_rows)(daily)
    added = append_new(rows, ledger)
    led = read_ledger(ledger)
    scored = score(led, daily)
    newest_cut = max((str(r.get("info_cutoff")) for r in led), default=None)
    newest = [r for r in led if str(r.get("info_cutoff")) == newest_cut]
    doc = {"generated_utc": datetime.now(UTC).isoformat(),
           "status": "MEASURED" if scored else ("PUBLISHING" if led else "UNMEASURED"),
           "authority": "none: a ledger and a report; it retires and sizes nothing",
           "ledger": str(ledger.relative_to(BASE)) if ledger.is_relative_to(BASE) else str(ledger),
           "n_forecasts": len(led), "n_added": added, "n_scored": len(scored),
           "newest_cutoff": newest_cut, "model": MODEL, "model_version": model_version(),
           "calibration": calibration([r["pit"] for r in scored]),
           "outcomes_vs_forecast": judge(scored),
           "research_requests": research_requests(newest),
           "elapsed_s": round(time.time() - t0, 1)}
    _write(out, doc)
    return doc


def main(argv: list[str] | None = None) -> int:
    argparse.ArgumentParser(description=__doc__.split("\n")[0]).parse_args(argv)
    doc = run()
    j = doc["outcomes_vs_forecast"]
    print(f"sleeve forecasts {doc['status']}: {doc['n_forecasts']} rows (+{doc['n_added']}), "
          f"{doc['n_scored']} scored, {j['n_worse']}/{j['n_tested']} worse than forecast, "
          f"{len(doc['research_requests'])} research request(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
