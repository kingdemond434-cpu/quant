"""THE SHARED SPINE OF EVERY WORLD-SENSOR ENGINE: a gain contract, a lake series and a cell door.

THE PRINCIPAL'S ADMISSION LAW (2026-10-06): a subsystem ships only with a MEASURABLE CONTRACT
SHOWING GAIN. Every state engine the world sensor builds from the Quant Guild cards and the
Roman rows (vol conditioner, implied move, regime probabilities, model disagreement, hedging
states, Hawkes intensity, Kalman latent states, option-chain positioning) answers the same three
questions in the same shape, so one report can hold all of them and one reader can rank them:

  1. WHAT IS THE GAIN, AGAINST WHAT BASELINE, AND COULD CHANCE HAVE MADE IT?
     `gated_gain`    a state that GATES a base cell: Kelly growth of the gated payoff against the
                     ungated payoff, its circular-shift null (the state's own autocorrelation is
                     kept, its alignment with the payoff is destroyed) and the same gain WITHIN
                     strata of a control (realised-vol tercile by default), because a gate that
                     only re-discovers the vol regime adds nothing the desk lacks.
     `forecast_gain` a state that FORECASTS a quantity (realised vol, a move): loss reduction
                     against the baseline forecast, with a block-bootstrap p on the loss
                     differential (Diebold-Mariano in spirit, HAC by construction).
     `monotone_gain` a state whose claim is ORDER (bigger surprise, bigger reaction): the rank
                     correlation and its permutation p.
     Every one returns a `contract` row: verdict GAIN | NO_GAIN | UNMEASURED. UNMEASURED below its
     own minimum sample, never a zero and never a pass (L1.28a).

  2. WHERE DOES THE STATE LIVE? `write_lake_series` writes it as a canonical frame under
     `desks/mt5/data/lake/series/<id>.csv` with the PIT stamp `family_exogenous_conditioner`
     requires (`available_time`, UTC). A row without a knowable instant is refused, not guessed.

  3. HOW DOES IT REACH THE GAUNTLET? `emit_conditioner_cells` enqueues one
     `exogenous_conditioner` cell per (signal x transform x symbol x chart x side) through the one
     registry door, carrying source_id, discovery_id, mechanism and falsifier. The trials are
     charged once by the gauntlet over the full union, as for every other producer. Nothing here
     judges, sizes or trades.

`publish` writes one engine's contracts under `desks/mt5/reports/sensor_contracts/` and
`rollup` folds every engine into `desks/mt5/reports/SENSOR_CONTRACTS.json`.
"""
from __future__ import annotations

import json
import math
import os
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

UNMEASURED = "UNMEASURED"
GAIN = "GAIN"
NO_GAIN = "NO_GAIN"
DESK = Path(__file__).resolve().parents[2] / "desks" / "mt5"
LAKE = DESK / "data" / "lake" / "series"
CONTRACTS = DESK / "reports" / "sensor_contracts"
ROLLUP = DESK / "reports" / "SENSOR_CONTRACTS.json"
STAMP = ("available_time", "event_time", "source_id")
#: Trading days a year: the Kelly growth and Sharpe annualiser.
YEAR = 252
#: Defaults every engine may tighten but not loosen without saying so in its contract.
MIN_N = 250
MIN_ACTIVE = 30
ALPHA = 0.05
N_NULL = 400
MIN_SHIFT = 21


def _arr(x: Iterable[Any]) -> np.ndarray:
    return np.asarray(list(x) if not isinstance(x, np.ndarray) else x, dtype=float)


def kelly_growth(payoff: np.ndarray, active: np.ndarray | None = None) -> float | None:
    """Annualised log-growth at the full-Kelly fraction of a daily payoff stream, in cash on
    inactive days: YEAR * active_share * mu^2 / (2 sigma^2), signed by mu (a payoff the base
    cell would have to SHORT is a loss to the cell as specified, never a hidden gain)."""
    p = _arr(payoff)
    mask = np.isfinite(p) if active is None else (np.isfinite(p) & _arr(active).astype(bool))
    n_all = int(np.isfinite(p).sum())
    x = p[mask]
    if x.size < 2 or n_all == 0:
        return None
    mu, sd = float(x.mean()), float(x.std(ddof=1))
    if sd <= 0 or not math.isfinite(sd):
        return None
    return round(math.copysign(YEAR * (x.size / n_all) * mu * mu / (2 * sd * sd), mu), 6)


def sharpe(payoff: np.ndarray, active: np.ndarray | None = None) -> float | None:
    p = _arr(payoff)
    mask = np.isfinite(p) if active is None else (np.isfinite(p) & _arr(active).astype(bool))
    x = p[mask]
    if x.size < 2:
        return None
    sd = float(x.std(ddof=1))
    return round(float(x.mean()) / sd * math.sqrt(YEAR), 6) if sd > 0 else None


def contract(*, engine: str, cards: Sequence[str], metric: str, baseline: str, falsifier: str,
             value: float | None, baseline_value: float | None, n: int, min_n: int = MIN_N,
             null_p: float | None = None, extra: Mapping[str, Any] | None = None,
             require_positive: bool = True, why: str = "") -> dict[str, Any]:
    """One contract row. GAIN needs n >= min_n, a finite gain above zero and null_p < ALPHA."""
    gain = (None if value is None or baseline_value is None
            else round(float(value) - float(baseline_value), 6))
    if n < min_n or gain is None:
        verdict = UNMEASURED
        why = why or (f"n={n} < {min_n}" if n < min_n else "the gain is not computable")
    elif (gain > 0 or not require_positive) and null_p is not None and null_p < ALPHA:
        verdict = GAIN
    else:
        verdict = NO_GAIN
    return {"engine": engine, "cards": list(cards), "metric": metric, "baseline": baseline,
            "falsifier": falsifier, "value": value, "baseline_value": baseline_value,
            "gain": gain, "null_p": null_p, "n": int(n), "min_n": int(min_n),
            "alpha": ALPHA, "verdict": verdict, "why": why, **dict(extra or {})}


def gated_gain(payoff: Sequence[float], gate: Sequence[Any], *, engine: str,
               cards: Sequence[str], falsifier: str, baseline: str = "ungated base cell",
               strata: Sequence[Any] | None = None, n_null: int = N_NULL, seed: int = 7,
               min_n: int = MIN_N, min_active: int = MIN_ACTIVE) -> dict[str, Any]:
    """Does trading the base cell only while `gate` holds raise its Kelly growth?

    NULL: the gate series circularly shifted by a random offset of at least MIN_SHIFT days, so
    its own persistence survives and only its timing against the payoff is destroyed. STRATA: the
    same gain computed inside each control stratum (e.g. realised-vol tercile) and averaged by
    active share; it is reported beside the headline and must also be positive for GAIN."""
    p = _arr(payoff)
    g = np.asarray([bool(v) if v is not None and v == v else False for v in gate], dtype=bool)
    ok = np.isfinite(p)
    p, g = p[ok], g[ok]
    n, n_active = int(p.size), int(g.sum())
    base_v = kelly_growth(p)
    val = kelly_growth(p, g) if n_active >= 2 else None
    extra: dict[str, Any] = {"n_active": n_active, "sharpe_gated": sharpe(p, g),
                             "sharpe_base": sharpe(p)}
    null_p = None
    if val is not None and base_v is not None and n >= 2 * MIN_SHIFT and n_active >= min_active:
        rng = np.random.default_rng(seed)
        obs = val - base_v
        hits = 0
        for _ in range(n_null):
            k = int(rng.integers(MIN_SHIFT, n - MIN_SHIFT))
            v = kelly_growth(p, np.roll(g, k))
            hits += int(v is not None and v - base_v >= obs)
        null_p = round((hits + 1) / (n_null + 1), 4)
    if strata is not None:
        s = np.asarray(list(strata), dtype=object)[ok]
        parts: list[tuple[float, float]] = []
        for lev in sorted({x for x in s if x is not None and x == x}, key=str):
            m = s == lev
            gv, bv = kelly_growth(p[m], g[m]), kelly_growth(p[m])
            if gv is not None and bv is not None and int(g[m].sum()) >= 5:
                parts.append((gv - bv, float(g[m].sum())))
        w = sum(x[1] for x in parts)
        extra["stratified_gain"] = round(sum(a * b for a, b in parts) / w, 6) if w else None
    why = "" if n_active >= min_active else f"gate active {n_active} < {min_active} days"
    row = contract(engine=engine, cards=cards, metric="kelly_growth_annual", baseline=baseline,
                   falsifier=falsifier, value=val, baseline_value=base_v, n=n, min_n=min_n,
                   null_p=null_p, extra=extra, why=why)
    if n_active < min_active and row["verdict"] != UNMEASURED:
        row["verdict"] = UNMEASURED
    if (row["verdict"] == GAIN and strata is not None
            and not (extra.get("stratified_gain") or 0) > 0):
        row["verdict"] = NO_GAIN
        row["why"] = "the gain vanishes inside the control strata"
    return row


def _block_bootstrap_p(d: np.ndarray, block: int, n_boot: int, seed: int) -> float | None:
    """One-sided p that the mean of the loss differential `d` (baseline - model) is <= 0."""
    n = d.size
    if n < 2 * block:
        return None
    rng = np.random.default_rng(seed)
    centred = d - d.mean()
    obs = d.mean()
    nb = math.ceil(n / block)
    hits = 0
    for _ in range(n_boot):
        starts = rng.integers(0, n - block + 1, size=nb)
        sample = np.concatenate([centred[s:s + block] for s in starts])[:n]
        hits += int(sample.mean() >= obs)
    return round((hits + 1) / (n_boot + 1), 4)


def forecast_gain(y: Sequence[float], model: Sequence[float], base: Sequence[float], *,
                  engine: str, cards: Sequence[str], falsifier: str, baseline: str,
                  loss: str = "mse", block: int = 21, n_boot: int = N_NULL, seed: int = 11,
                  min_n: int = MIN_N) -> dict[str, Any]:
    """Loss reduction of `model` over `base` forecasting `y`. loss: mse | qlike (variances)."""
    a, f, b = _arr(y), _arr(model), _arr(base)
    ok = np.isfinite(a) & np.isfinite(f) & np.isfinite(b)
    if loss == "qlike":
        ok &= (a > 0) & (f > 0) & (b > 0)
    a, f, b = a[ok], f[ok], b[ok]

    def L(fc: np.ndarray) -> np.ndarray:
        if loss == "qlike":
            return np.asarray(a / fc - np.log(a / fc) - 1.0, dtype=float)
        return np.asarray((a - fc) ** 2, dtype=float)

    n = int(a.size)
    if n < 2:
        return contract(engine=engine, cards=cards, metric=f"{loss}_reduction",
                        baseline=baseline, falsifier=falsifier, value=None,
                        baseline_value=None, n=n, min_n=min_n)
    lm, lb = L(f), L(b)
    d = lb - lm
    p = _block_bootstrap_p(d, block, n_boot, seed)
    # value = -model loss, baseline = -baseline loss: a positive gain is a loss reduction
    return contract(engine=engine, cards=cards, metric=f"{loss}_reduction", baseline=baseline,
                    falsifier=falsifier, value=round(-float(lm.mean()), 10),
                    baseline_value=round(-float(lb.mean()), 10), n=n, min_n=min_n, null_p=p,
                    extra={"relative_reduction": (round(float(d.mean() / lb.mean()), 6)
                                                  if lb.mean() > 0 else None)})


def _rank(x: np.ndarray) -> np.ndarray:
    order = x.argsort(kind="mergesort")
    r = np.empty(x.size, dtype=float)
    r[order] = np.arange(x.size, dtype=float)
    return r


def monotone_gain(x: Sequence[float], y: Sequence[float], *, engine: str,
                  cards: Sequence[str], falsifier: str, baseline: str = "no order (rho = 0)",
                  n_null: int = N_NULL, seed: int = 13, min_n: int = 100) -> dict[str, Any]:
    """Spearman rho of y on x and its permutation p (one-sided, rho > 0)."""
    a, b = _arr(x), _arr(y)
    ok = np.isfinite(a) & np.isfinite(b)
    a, b = a[ok], b[ok]
    n = int(a.size)
    if n < 3:
        return contract(engine=engine, cards=cards, metric="spearman_rho", baseline=baseline,
                        falsifier=falsifier, value=None, baseline_value=0.0, n=n, min_n=min_n)
    ra, rb = _rank(a), _rank(b)
    ra -= ra.mean()
    rb -= rb.mean()
    den = float(np.sqrt((ra ** 2).sum() * (rb ** 2).sum()))
    rho = float((ra * rb).sum() / den) if den > 0 else 0.0
    rng = np.random.default_rng(seed)
    hits = sum(int(float((ra * rng.permutation(rb)).sum()) / den >= rho) for _ in range(n_null)
               ) if den > 0 else n_null
    return contract(engine=engine, cards=cards, metric="spearman_rho", baseline=baseline,
                    falsifier=falsifier, value=round(rho, 6), baseline_value=0.0, n=n,
                    min_n=min_n, null_p=round((hits + 1) / (n_null + 1), 4))


# ============================================================================== the lake series
def write_lake_series(series_id: str, rows: Sequence[Mapping[str, Any]], *,
                      root: Path | None = None) -> dict[str, Any]:
    """Write a state series as the canonical frame `family_exogenous_conditioner` reads.

    Every row needs `available_time` (UTC ISO, the instant the desk could act on it) and at
    least one numeric column. Rows without it are dropped and counted. Sorted, de-duplicated on
    available_time (last wins), written atomically as CSV."""
    import pandas as pd
    base = root or LAKE
    kept = [dict(r) for r in rows if str(r.get("available_time") or "") not in ("", UNMEASURED)]
    out: dict[str, Any] = {"series_id": series_id, "rows_in": len(rows), "rows": len(kept),
                           "dropped_without_available_time": len(rows) - len(kept)}
    if not kept:
        out["status"] = UNMEASURED
        return out
    df = pd.DataFrame(kept)
    df["available_time"] = pd.to_datetime(df["available_time"], utc=True, errors="coerce")
    df = df.dropna(subset=["available_time"]).sort_values("available_time")
    df = df.drop_duplicates(subset=["available_time"], keep="last")
    df["available_time"] = df["available_time"].map(lambda t: t.isoformat())
    df["source_id"] = df.get("source_id", series_id)
    base.mkdir(parents=True, exist_ok=True)
    path = base / f"{series_id}.csv"
    tmp = path.with_suffix(".tmp")
    df.to_csv(tmp, index=False)
    os.replace(tmp, path)
    out.update({"status": "WRITTEN", "path": str(path), "rows": len(df),
                "columns": [c for c in df.columns if c not in STAMP]})
    return out


# ============================================================================== the cell door
def emit_conditioner_cells(series_id: str, signals: Sequence[str], symbols: Sequence[str], *,
                           mechanism: str, falsifier: str, generator: str,
                           sides: Sequence[int] = (1,), transforms: Sequence[str] = ("level_z",),
                           charts: Sequence[str] = ("H1", "H4", "D1"),
                           threshold: float = 1.0, dry_run: bool = False,
                           data_source: str | None = None) -> dict[str, Any]:
    """One `exogenous_conditioner` cell per (signal x transform x symbol x chart x side).

    `data_source` names where the series' numbers come from (e.g. "fred:DGS10",
    "yahoo:cboe_indices:^VIX", "mt5:bars"). The terms hold (`libs.data.terms_hold`) is checked
    first and fails closed: an undeclared or held source emits no cell and says why."""
    from libs.data.terms_hold import gauntlet_terms
    if not data_source:
        return {"series_id": series_id, "emitted": 0, "created": 0, "status": "HELD_TERMS",
                "why": "no data_source declared: the terms gate cannot clear an unnamed source"}
    ok, why = gauntlet_terms(data_source)
    if not ok:
        return {"series_id": series_id, "emitted": 0, "created": 0, "status": "HELD_TERMS",
                "data_source": data_source, "why": why}
    made = created = 0
    errors: list[str] = []
    did = ""
    if not dry_run:
        try:
            from libs.moat.registry import record_discovery
            did, _ = record_discovery(source_id=series_id, source_type="world_sensor_state",
                                      mechanism=mechanism, origin=generator, generator=generator,
                                      assets=list(symbols), exact_rule_if_known="",
                                      horizons=list(charts),
                                      note=f"state series {series_id}; falsifier: {falsifier}")
        except Exception as exc:
            return {"series_id": series_id, "emitted": 0, "created": 0,
                    "error": f"record_discovery: {type(exc).__name__}: {str(exc)[:80]}"}
    for sig in signals:
        for tf in transforms:
            for sym in symbols:
                for chart in charts:
                    for side in sides:
                        made += 1
                        if dry_run:
                            continue
                        try:
                            from libs.moat.registry import enqueue_candidate
                            _cid, new = enqueue_candidate(
                                family="exogenous_conditioner", symbol=sym,
                                params={"source": series_id, "signal": sig, "transform": tf,
                                        "threshold": threshold, "side_when_high": int(side)},
                                origin=generator, mechanism=mechanism, chart=chart,
                                horizon=chart, source_id=series_id, discovery_id=did or None,
                                generator=generator, department="information",
                                asset_class="", transformation="world_sensor_state",
                                required_data=[f"desks/mt5/data/lake/series/{series_id}.csv"],
                                pit_status="STAMPED", causal_rationale=mechanism,
                                falsifier=falsifier)
                            created += int(bool(new))
                        except Exception as exc:
                            errors.append(f"{sig}/{tf}/{sym}/{chart}/{side}: "
                                          f"{type(exc).__name__}: {str(exc)[:60]}")
    return {"series_id": series_id, "discovery_id": did, "emitted": made, "created": created,
            "errors": errors[:5]}


# ============================================================================== publication
def publish(engine: str, contracts: Sequence[Mapping[str, Any]], *,
            extra: Mapping[str, Any] | None = None, root: Path | None = None) -> Path:
    base = root or CONTRACTS
    base.mkdir(parents=True, exist_ok=True)
    doc = {"engine": engine, "at": datetime.now(UTC).isoformat(timespec="seconds"),
           "contracts": list(contracts),
           "verdicts": {v: sum(1 for c in contracts if c.get("verdict") == v)
                        for v in (GAIN, NO_GAIN, UNMEASURED)},
           "authority": "NONE", **dict(extra or {})}
    path = base / f"{engine}.json"
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(doc, indent=1, sort_keys=True, default=str) + "\n", "utf-8")
    os.replace(tmp, path)
    return path


def rollup(root: Path | None = None, out: Path | None = None,
           cards: Mapping[str, Mapping[str, Any]] | None = None) -> dict[str, Any]:
    """Every engine's contracts in one place, plus each declared card's disposition."""
    base = root or CONTRACTS
    engines: dict[str, Any] = {}
    by_card: dict[str, list[dict[str, Any]]] = {}
    for p in sorted(base.glob("*.json")) if base.exists() else []:
        try:
            doc = json.loads(p.read_text("utf-8"))
        except (OSError, ValueError):
            continue
        engines[p.stem] = {"at": doc.get("at"), "verdicts": doc.get("verdicts")}
        for c in doc.get("contracts") or []:
            for card in c.get("cards") or []:
                by_card.setdefault(str(card), []).append(
                    {"engine": p.stem, "metric": c.get("metric"), "verdict": c.get("verdict"),
                     "gain": c.get("gain"), "null_p": c.get("null_p"), "n": c.get("n"),
                     "label": c.get("label")})
    card_rows = {}
    for cid, meta in (cards or {}).items():
        rows = by_card.get(cid, [])
        best = (GAIN if any(r["verdict"] == GAIN for r in rows) else
                NO_GAIN if any(r["verdict"] == NO_GAIN for r in rows) else UNMEASURED)
        card_rows[cid] = {**dict(meta), "contracts": len(rows), "best_verdict": best}
    doc = {"at": datetime.now(UTC).isoformat(timespec="seconds"), "engines": engines,
           "cards": card_rows or {k: {"contracts": len(v)} for k, v in by_card.items()},
           "rule": "GAIN needs n >= min_n, positive gain, p < 0.05 vs its null; UNMEASURED is "
                   "never zero and never a pass"}
    target = out or ROLLUP
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".tmp")
    tmp.write_text(json.dumps(doc, indent=1, sort_keys=True, default=str) + "\n", "utf-8")
    os.replace(tmp, target)
    return doc
