"""Dependence-aware portfolio and monetisation decision intelligence.

This module closes related decision gaps with one shared set of inputs.  It does not create
strategies or place orders: it measures joint path risk, effective breadth, state uncertainty,
execution realism and operational leakage so the existing capital competition can compare
opportunities on net expected log-growth.

All resampling uses one stationary-block index for the *entire* return matrix.  Sampling columns
or rows independently would manufacture diversification by destroying contemporaneous and serial
dependence, precisely the risk a portfolio simulation exists to retain.
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Mapping, Sequence
from itertools import pairwise
from typing import cast

import numpy as np

from libs.backtest.queue_fill import maker_fill
from libs.core.coerce import finite_float
from libs.validation.bootstrap import stationary_block_indices

__all__ = [
    "VENUE_STRESS_COMPONENTS",
    "alpha_retention",
    "capital_inventory_policy",
    "dependence_preserving_monte_carlo",
    "effective_breadth",
    "execution_opportunity",
    "exit_reallocation_decision",
    "momentum_rebound_surface",
    "monetisation_latency",
    "path_drawdown_state",
    "regime_conditional_allocation",
    "regime_model_selection",
    "return_attribution",
    "transition_posterior",
    "transition_surprise",
    "trigger_collision_control",
    "venue_stress_state",
    "volatility_manifold_state",
    "xsec_momentum_book",
]


def _matrix(values: Sequence[Sequence[float]] | np.ndarray) -> np.ndarray:
    x = np.asarray(values, dtype="float64")
    if x.ndim != 2 or x.shape[0] < 2 or x.shape[1] < 1:
        raise ValueError("returns must be a time x sleeve matrix with at least two rows")
    if not np.isfinite(x).all():
        raise ValueError("returns must be finite; align and disposition missing data first")
    return x


def _max_drawdown(simple_returns: np.ndarray) -> float:
    wealth = np.cumprod(1.0 + simple_returns)
    peaks = np.maximum.accumulate(np.r_[1.0, wealth])[:-1]
    return float(np.max(1.0 - wealth / peaks))


def dependence_preserving_monte_carlo(
    returns: Sequence[Sequence[float]] | np.ndarray,
    weights: Sequence[float],
    *,
    n_paths: int = 1000,
    mean_block: float = 10.0,
    ruin_floor: float = 0.02,
    seed: int = 0,
) -> dict[str, object]:
    """Joint stationary-block portfolio paths and survival diagnostics.

    ``ruin_floor`` is remaining wealth (2% means a 98% loss), not a permission to spend a ruin
    budget.  The constitutional probability limit remains a separate hard gate.
    """
    x = _matrix(returns)
    w = np.asarray(weights, dtype="float64")
    if w.shape != (x.shape[1],) or not np.isfinite(w).all():
        raise ValueError("weights must align with sleeves and be finite")
    if n_paths < 1 or mean_block < 1 or not 0 < ruin_floor < 1:
        raise ValueError("invalid simulation settings")
    rng = np.random.default_rng(seed)
    elog = np.empty(n_paths)
    drawdown = np.empty(n_paths)
    ruined = np.empty(n_paths, dtype=bool)
    for i in range(n_paths):
        joint = x[stationary_block_indices(len(x), mean_block, rng)]
        p = joint @ w
        if np.any(p <= -1.0):
            elog[i], drawdown[i], ruined[i] = -math.inf, 1.0, True
            continue
        wealth = np.cumprod(1.0 + p)
        elog[i] = float(np.log1p(p).sum())
        drawdown[i] = _max_drawdown(p)
        ruined[i] = bool(np.min(wealth) <= ruin_floor)
    finite = elog[np.isfinite(elog)]
    return {
        "status": "MEASURED",
        "paths": n_paths,
        "mean_block": float(mean_block),
        "mean_log_wealth": float(np.mean(finite)) if finite.size else -math.inf,
        "p05_log_wealth": float(np.quantile(finite, 0.05)) if finite.size else -math.inf,
        "median_max_drawdown": float(np.median(drawdown)),
        "p95_max_drawdown": float(np.quantile(drawdown, 0.95)),
        "ruin_probability": float(np.mean(ruined)),
        "dependence_preserved": "same time indices resample every sleeve jointly",
        "authority": "DIAGNOSTIC_ONLY -- survival gates and capital caps remain binding",
    }


def effective_breadth(returns: Sequence[Sequence[float]] | np.ndarray) -> dict[str, object]:
    """Effective independent bets from the correlation eigen-spectrum (Parker breadth)."""
    x = _matrix(returns)
    if x.shape[1] == 1:
        return {"nominal_sleeves": 1, "effective_sleeves": 1.0, "breadth_ratio": 1.0}
    corr = np.corrcoef(x, rowvar=False)
    corr = np.nan_to_num(corr, nan=0.0, posinf=0.0, neginf=0.0)
    np.fill_diagonal(corr, 1.0)
    eig = np.clip(np.linalg.eigvalsh(corr), 0.0, None)
    effective = float(eig.sum() ** 2 / max(float(eig @ eig), 1e-12))
    return {
        "nominal_sleeves": int(x.shape[1]),
        "effective_sleeves": effective,
        "breadth_ratio": effective / x.shape[1],
        "eigenvalues": eig.tolist(),
        "note": "formula count is not breadth; correlated variants share one risk budget",
    }


def transition_posterior(states: Sequence[str], *, smoothing: float = 0.5) -> dict[str, object]:
    """Smoothed Markov posterior plus duration-conditioned empirical hazards."""
    if len(states) < 2 or smoothing <= 0:
        return {"status": "UNMEASURED", "reason": "need transitions and positive smoothing"}
    names = sorted(set(map(str, states)))
    counts = {a: dict.fromkeys(names, smoothing) for a in names}
    run_lengths: dict[str, list[tuple[int, bool]]] = defaultdict(list)
    run_state, run = str(states[0]), 1
    for raw in states[1:]:
        nxt = str(raw)
        counts[run_state][nxt] += 1.0
        if nxt == run_state:
            run += 1
        else:
            run_lengths[run_state].append((run, True))
            run_state, run = nxt, 1
    run_lengths[run_state].append((run, False))
    posterior = {a: {b: v / sum(row.values()) for b, v in row.items()} for a, row in counts.items()}
    hazards: dict[str, dict[str, float]] = {}
    for state, runs in run_lengths.items():
        max_run = max(n for n, _ in runs)
        hazards[state] = {}
        for age in range(1, max_run + 1):
            at_risk = sum(n >= age for n, _ in runs)
            ended = sum(n == age and complete for n, complete in runs)
            hazards[state][str(age)] = ended / at_risk if at_risk else 0.0
    return {
        "status": "MEASURED",
        "states": names,
        "posterior": posterior,
        "duration_hazard": hazards,
        "last_state": str(states[-1]),
        "last_duration": run,
    }


def transition_surprise(
    previous: str, observed: str, posterior: Mapping[str, Mapping[str, float]]
) -> dict[str, object]:
    p = float(posterior.get(previous, {}).get(observed, 0.0))
    return {
        "previous": previous,
        "observed": observed,
        "probability": p,
        "surprise": -math.log(max(p, 1e-12)),
        "route_to_hypothesis_factory": bool(p < 0.05),
    }


def path_drawdown_state(returns: Sequence[float], *, lookback: int = 20) -> dict[str, object]:
    r = np.asarray(returns, dtype="float64")
    if r.size < 2 or not np.isfinite(r).all() or np.any(r <= -1):
        return {"status": "UNMEASURED"}
    wealth = np.cumprod(1 + r)
    peak = np.maximum.accumulate(np.r_[1.0, wealth])[:-1]
    dd = 1.0 - wealth / peak
    end = float(dd[-1])
    trough = int(np.argmax(dd))
    speed = float(np.max(np.diff(dd[-min(lookback, len(dd)) :], prepend=0.0)))
    rebound = float(wealth[-1] / wealth[trough] - 1.0) if trough < len(wealth) - 1 else 0.0
    return {
        "status": "MEASURED",
        "current_drawdown": end,
        "max_drawdown": float(dd.max()),
        "drawdown_speed": speed,
        "rebound_from_trough": rebound,
        "path_state": "CASCADE" if speed >= 0.04 else "SLOW" if end > 0 else "PEAK",
    }


def capital_inventory_policy(
    *,
    deployable: float,
    dry_powder: float,
    opportunity_score: float,
    future_option_score: float,
    max_tranches: int = 8,
) -> dict[str, object]:
    if min(deployable, dry_powder) < 0 or max_tranches < 1:
        raise ValueError("capital must be non-negative and max_tranches positive")
    advantage = max(0.0, opportunity_score) / max(
        max(0.0, opportunity_score) + max(0.0, future_option_score), 1e-12
    )
    amount = min(deployable, dry_powder * advantage)
    tranches = 0 if amount == 0 else max(1, min(max_tranches, math.ceil(max_tranches * advantage)))
    return {
        "deploy_now": amount,
        "retain_optionality": dry_powder - amount,
        "tranches": tranches,
        "tranche_size": amount / tranches if tranches else 0.0,
    }


def trigger_collision_control(
    trigger_history: Sequence[Sequence[float]] | np.ndarray, *, threshold: float = 0.75
) -> dict[str, object]:
    x = _matrix(trigger_history)
    breadth = effective_breadth(x)
    corr = np.nan_to_num(np.corrcoef(x, rowvar=False), nan=0.0)
    groups: list[list[int]] = []
    remaining = set(range(x.shape[1]))
    while remaining:
        seed = min(remaining)
        group = sorted(i for i in remaining if i == seed or abs(corr[seed, i]) >= threshold)
        groups.append(group)
        remaining.difference_update(group)
    return {
        **breadth,
        "collision_groups": groups,
        "sizing_multiplier": min(1.0, finite_float(breadth.get("effective_sleeves")) / x.shape[1]),
    }


def xsec_momentum_book(
    prices: Sequence[Sequence[float]] | np.ndarray, *, lookback: int = 20, gross: float = 1.0
) -> dict[str, object]:
    p = _matrix(prices)
    if lookback < 1 or p.shape[0] <= lookback or np.any(p <= 0):
        return {"status": "UNMEASURED"}
    mom = p[-1] / p[-1 - lookback] - 1.0
    order = np.argsort(mom)
    n = len(mom)
    k = max(1, n // 3)
    continuation = np.zeros(n)
    continuation[order[:k]], continuation[order[-k:]] = -gross / (2 * k), gross / (2 * k)
    return {
        "status": "MEASURED",
        "momentum": mom.tolist(),
        "continuation_weights": continuation.tolist(),
        "crowded_reversal_weights": (-continuation).tolist(),
        "authority": "COMPETING_SLEEVES -- validation selects neither in-sample",
    }


def momentum_rebound_surface(
    momentum: Sequence[float], drawdown: Sequence[float], forward_returns: Sequence[float]
) -> dict[str, object]:
    m, d, y = (np.asarray(v, dtype="float64") for v in (momentum, drawdown, forward_returns))
    if not (m.shape == d.shape == y.shape) or m.size < 20:
        return {"status": "UNMEASURED"}
    mq, dq = np.median(m), np.median(d)
    cells = {}
    for mn, mm in (("weak", m < mq), ("strong", m >= mq)):
        for dn, dm in (("shallow", d < dq), ("deep", d >= dq)):
            z = y[mm & dm]
            cells[f"{mn}|{dn}"] = {"n": int(z.size), "mean": float(z.mean()) if z.size else None}
    return {
        "status": "MEASURED",
        "cells": cells,
        "authority": "HYPOTHESIS_SURFACE -- requires untouched-OOS conditional validation",
    }


def exit_reallocation_decision(
    hold_scenarios: Sequence[float],
    alternative_scenarios: Sequence[float],
    *,
    switching_cost: float = 0.0,
) -> dict[str, object]:
    h, a = (
        np.asarray(hold_scenarios, dtype="float64"),
        np.asarray(alternative_scenarios, dtype="float64"),
    )
    if h.size == 0 or h.shape != a.shape or np.any(h <= -1) or np.any(a - switching_cost <= -1):
        return {"status": "UNMEASURED"}
    hold = float(np.log1p(h).mean())
    realloc = float(np.log1p(a - switching_cost).mean())
    return {
        "status": "MEASURED",
        "hold_elog": hold,
        "reallocate_elog": realloc,
        "decision": "REALLOCATE" if realloc > hold else "HOLD",
        "elog_advantage": realloc - hold,
    }


def execution_opportunity(
    *,
    gross_edge_bps: float,
    order_size: float,
    queue_ahead: float,
    through_volume: float,
    taker_cost_bps: float,
    adverse_selection_bps: float = 0.0,
    feed_latency_s: float = 0.0,
    resting_window_s: float = 1.0,
) -> dict[str, object]:
    fill = maker_fill(
        order_size=order_size,
        queue_ahead=queue_ahead,
        through_volume=through_volume,
        feed_latency_s=feed_latency_s,
        resting_window_s=resting_window_s,
    )
    maker_net = gross_edge_bps - adverse_selection_bps
    taker_net = gross_edge_bps - taker_cost_bps
    expected = fill.fill_fraction * maker_net + (1.0 - fill.fill_fraction) * taker_net
    return {
        "maker_fill_probability": fill.fill_fraction,
        "maker_net_bps": maker_net,
        "taker_net_bps": taker_net,
        "expected_net_bps": expected,
        "eligible": bool(expected > 0),
        "model": "existing queue-priority maker_fill",
    }


def alpha_retention(
    *, intended_pnl: float, realised_pnl: float, leaks: Mapping[str, float] | None = None
) -> dict[str, object]:
    leak_rows = {str(k): float(v) for k, v in (leaks or {}).items()}
    ratio = realised_pnl / intended_pnl if intended_pnl > 0 else None
    return {
        "status": "MEASURED" if ratio is not None else "UNMEASURED",
        "intended_pnl": intended_pnl,
        "realised_pnl": realised_pnl,
        "retention_ratio": ratio,
        "leaks": leak_rows,
        "unattributed_leak": intended_pnl - realised_pnl - sum(leak_rows.values()),
    }


def return_attribution(
    strategy_returns: Sequence[float],
    market_returns: Sequence[float],
    *,
    selection_returns: Sequence[float] | None = None,
    execution_costs: Sequence[float] | None = None,
) -> dict[str, object]:
    y, m = (
        np.asarray(strategy_returns, dtype="float64"),
        np.asarray(market_returns, dtype="float64"),
    )
    if y.shape != m.shape or y.size < 3:
        return {"status": "UNMEASURED"}
    beta = float(np.cov(y, m, ddof=1)[0, 1] / np.var(m, ddof=1)) if np.var(m, ddof=1) > 0 else 0.0
    beta_pnl = float((beta * m).sum())
    selection = (
        float(np.asarray(selection_returns, dtype="float64").sum())
        if selection_returns is not None
        else 0.0
    )
    execution = (
        float(np.asarray(execution_costs, dtype="float64").sum())
        if execution_costs is not None
        else 0.0
    )
    total = float(y.sum())
    alpha = total - beta_pnl - selection + execution
    return {
        "status": "MEASURED",
        "total": total,
        "beta": beta,
        "beta_pnl": beta_pnl,
        "selection_pnl": selection,
        "execution_pnl": -execution,
        "alpha_pnl": alpha,
    }


def monetisation_latency(
    stage_times: Mapping[str, float], *, edge_bps: float, half_life_seconds: float
) -> dict[str, object]:
    order = ("discovered", "tested", "validated", "canary", "decision", "order", "fill")
    present = [(s, float(stage_times[s])) for s in order if s in stage_times]
    if len(present) < 2 or half_life_seconds <= 0:
        return {"status": "UNMEASURED"}
    legs = {f"{a}_to_{b}": max(0.0, tb - ta) for (a, ta), (b, tb) in pairwise(present)}
    total = max(0.0, present[-1][1] - present[0][1])
    retained = 0.5 ** (total / half_life_seconds)
    return {
        "status": "MEASURED",
        "stage_seconds": legs,
        "total_seconds": total,
        "edge_retained": retained,
        "latency_regret_bps": edge_bps * (1.0 - retained),
    }


def regime_conditional_allocation(
    state_posterior: Mapping[str, float],
    state_elog: Mapping[str, Mapping[str, float]],
    *,
    entropy_penalty: float = 0.25,
) -> dict[str, object]:
    states = set(state_posterior)
    if not states or abs(sum(state_posterior.values()) - 1.0) > 1e-6:
        return {"status": "UNMEASURED"}
    entropy = -sum(p * math.log(max(p, 1e-12)) for p in state_posterior.values())
    max_entropy = math.log(max(len(states), 1))
    confidence = 1.0 - entropy_penalty * (entropy / max_entropy if max_entropy else 0.0)
    scores = {
        alpha: confidence * sum(state_posterior.get(s, 0.0) * vals.get(s, 0.0) for s in states)
        for alpha, vals in state_elog.items()
    }
    positive = {a: max(0.0, v) for a, v in scores.items()}
    z = sum(positive.values())
    return {
        "status": "MEASURED",
        "posterior_entropy": entropy,
        "confidence": confidence,
        "scores": scores,
        "weights": {a: v / z if z else 0.0 for a, v in positive.items()},
    }


def regime_model_selection(
    models: Mapping[str, Mapping[str, float]], *, complexity_penalty: float = 0.001
) -> dict[str, object]:
    """Select on untouched-OOS E[log W] net of declared model complexity."""
    if not models:
        return {"status": "UNMEASURED"}
    rows = []
    for name, metrics in models.items():
        score = float(metrics.get("oos_elog", -math.inf)) - complexity_penalty * float(
            metrics.get("parameters", 0)
        )
        rows.append(
            {
                "model": name,
                "score": score,
                "oos_elog": metrics.get("oos_elog"),
                "parameters": metrics.get("parameters", 0),
            }
        )
    rows.sort(key=lambda r: (-finite_float(r.get("score")), str(r.get("model"))))
    return {
        "status": "MEASURED",
        "selected": rows[0]["model"],
        "ranking": rows,
        "criterion": "untouched-OOS E[log W] - complexity penalty",
    }


def capital_topology(
    accounts: Sequence[Mapping[str, object]],
    *,
    max_venue_fraction: float = 1.0,
    max_collateral_fraction: float = 1.0,
) -> dict[str, object]:
    """Measure where wealth can be lost or stranded, not merely what strategy owns it.

    Failure probabilities and recovery fractions must be supplied by the caller; missing values
    remain unmeasured.  The result is decision intelligence only and never transfers collateral.
    """
    if not 0 < max_venue_fraction <= 1 or not 0 < max_collateral_fraction <= 1:
        raise ValueError("topology caps must lie in (0, 1]")
    rows = [row for row in accounts if finite_float(row.get("equity")) > 0]
    total = sum(finite_float(row.get("equity")) for row in rows)
    if total <= 0:
        return {"status": "UNMEASURED", "reason": "no positive capital locations"}

    def concentration(field: str) -> dict[str, object]:
        grouped: dict[str, float] = defaultdict(float)
        for row in rows:
            grouped[str(row.get(field, "UNKNOWN"))] += finite_float(row.get("equity"))
        shares = {name: value / total for name, value in grouped.items()}
        return {
            "shares": shares,
            "largest": max(shares.values(), default=0.0),
            "hhi": sum(value * value for value in shares.values()),
            "unknown_fraction": shares.get("UNKNOWN", 0.0),
        }

    venue = concentration("venue")
    collateral = concentration("collateral")
    chain = concentration("chain")
    bridge = concentration("bridge")
    expected_log_drag = 0.0
    risk_measured = True
    stress_rows = []
    for row in rows:
        share = finite_float(row.get("equity")) / total
        p = row.get("failure_probability")
        recovery = row.get("recovery_fraction")
        if not isinstance(p, (int, float)) or not isinstance(recovery, (int, float)):
            risk_measured = False
            stress_rows.append({"venue": row.get("venue"), "status": "UNMEASURED"})
            continue
        probability = min(1.0, max(0.0, float(p)))
        recovered = min(1.0, max(0.0, float(recovery)))
        loss_fraction = share * (1.0 - recovered)
        contribution = -math.inf if loss_fraction >= 1 else probability * math.log1p(-loss_fraction)
        expected_log_drag += contribution
        stress_rows.append(
            {
                "venue": row.get("venue"),
                "capital_fraction": share,
                "failure_probability": probability,
                "recovery_fraction": recovered,
                "stress_loss_fraction": loss_fraction,
                "expected_log_drag": contribution,
                "transfer_seconds": row.get("transfer_seconds"),
                "withdrawal_available": row.get("withdrawal_available"),
            }
        )
    breaches = []
    if finite_float(venue.get("largest")) > max_venue_fraction:
        breaches.append("VENUE_CONCENTRATION")
    if finite_float(collateral.get("largest")) > max_collateral_fraction:
        breaches.append("COLLATERAL_CONCENTRATION")
    effective_capital = sum(
        finite_float(row.get("equity")) * finite_float(row.get("margin_efficiency"), 1.0)
        for row in rows
    )
    return {
        "status": "MEASURED" if risk_measured else "PARTIALLY_MEASURED",
        "total_capital": total,
        "venue": venue,
        "collateral": collateral,
        "chain": chain,
        "bridge": bridge,
        "stress": stress_rows,
        "expected_log_drag": expected_log_drag if risk_measured else None,
        "capital_efficiency": effective_capital / total,
        "breaches": breaches,
        "eligible": not breaches and risk_measured,
        "authority": "MEASUREMENT_ONLY -- existing custody, withdrawal and risk rails decide",
    }


def volatility_manifold_state(
    surfaces: Sequence[Sequence[float]] | np.ndarray,
    *,
    train_rows: int,
    rank: int,
    anomaly_quantile: float = 0.99,
    asset_labels: Sequence[str] | None = None,
) -> dict[str, object]:
    """Fit a low-rank volatility-surface manifold on calibration rows only.

    Held-out reconstruction error is emitted as a candidate state variable.  It has no predictive
    meaning until tested against future outcomes through the ordinary multiplicity-aware path.
    """
    if not 0.5 < anomaly_quantile < 1:
        raise ValueError("anomaly_quantile must lie in (0.5, 1)")
    x = np.asarray(surfaces, dtype="float64")
    if x.ndim != 2 or not np.isfinite(x).all():
        return {"status": "UNMEASURED", "reason": "finite time x surface matrix required"}
    if train_rows < 5 or train_rows >= x.shape[0] or rank < 1:
        return {
            "status": "UNMEASURED",
            "reason": "need >=5 calibration rows, held-out rows and positive fixed rank",
        }
    train = x[:train_rows]
    if rank >= min(train.shape):
        return {"status": "UNMEASURED", "reason": "rank must be below calibration dimensions"}
    center = train.mean(axis=0)
    _, singular, right = np.linalg.svd(train - center, full_matrices=False)
    basis = right[:rank]

    def errors(rows: np.ndarray) -> np.ndarray:
        centered = rows - center
        reconstruction = (centered @ basis.T) @ basis
        return cast("np.ndarray", np.mean((centered - reconstruction) ** 2, axis=1))

    calibration_error = errors(train)
    held_out_error = errors(x[train_rows:])
    threshold = float(np.quantile(calibration_error, anomaly_quantile))
    scale = max(threshold, float(np.median(calibration_error)), 1e-12)
    ratios = held_out_error / scale
    total_variance = float(np.sum(singular**2))
    explained = float(np.sum(singular[:rank] ** 2) / total_variance) if total_variance else 1.0
    labels = list(asset_labels or [])
    by_asset: dict[str, dict[str, float | int]] = {}
    if len(labels) == x.shape[0]:
        held_labels = labels[train_rows:]
        for asset in sorted(set(held_labels)):
            selected = held_out_error[np.asarray([label == asset for label in held_labels])]
            by_asset[asset] = {
                "n": int(selected.size),
                "mean_reconstruction_error": float(selected.mean()),
                "anomaly_rate": float(np.mean(selected > threshold)),
            }
    return {
        "status": "MEASURED",
        "calibration_rows": train_rows,
        "held_out_rows": int(x.shape[0] - train_rows),
        "rank": rank,
        "explained_calibration_variance": explained,
        "anomaly_quantile": anomaly_quantile,
        "calibration_error_threshold": threshold,
        "held_out_reconstruction_error": held_out_error.tolist(),
        "held_out_error_ratio": ratios.tolist(),
        "latest_state": "ABNORMAL" if held_out_error[-1] > threshold else "NORMAL_MANIFOLD",
        "held_out_anomaly_rate": float(np.mean(held_out_error > threshold)),
        "by_asset": by_asset,
        "authority": (
            "CANDIDATE STATE ONLY -- fixed calibration split; future-response and incremental "
            "information tests remain mandatory"
        ),
    }


VENUE_STRESS_COMPONENTS = (
    "liquidations",
    "open_interest_change_abs",
    "funding_abs",
    "basis_abs",
    "depth_drop",
    "insurance_fund_drawdown",
    "collateral_haircut",
    "adl_level",
    "withdrawal_constraint",
)


def venue_stress_state(
    history: Sequence[Mapping[str, object]],
    *,
    components: Sequence[str] = VENUE_STRESS_COMPONENTS,
    alert_z: float | None = None,
) -> dict[str, object]:
    """Measure a dynamic venue stress state from explicitly stress-positive components."""
    if alert_z is not None and alert_z <= 0:
        raise ValueError("alert_z must be positive")
    if len(history) < 4:
        return {"status": "UNMEASURED", "reason": "need baseline history plus a current state"}
    latest, baseline = history[-1], history[:-1]
    measured: list[dict[str, object]] = []
    missing = []
    for name in tuple(dict.fromkeys(str(value) for value in components)):
        prior: list[float] = []
        for row in baseline:
            raw = row.get(name)
            if isinstance(raw, bool) or not isinstance(raw, (int, float)):
                continue
            value = float(raw)
            if math.isfinite(value):
                prior.append(value)
        current = latest.get(name)
        if len(prior) < 3 or not isinstance(current, (int, float)):
            missing.append(name)
            continue
        average = float(np.mean(prior))
        deviation = float(np.std(prior, ddof=1))
        z_score = (float(current) - average) / max(deviation, 1e-12)
        measured.append(
            {
                "component": name,
                "current": float(current),
                "baseline_mean": average,
                "baseline_sd": deviation,
                "stress_z": z_score,
            }
        )
    if not measured:
        return {
            "status": "UNMEASURED",
            "reason": "no component has current value and >=3 baseline observations",
            "missing_components": missing,
        }
    positive = [max(0.0, finite_float(row.get("stress_z"))) for row in measured]
    score = float(np.mean(positive))
    status = "MEASURED" if not missing else "PARTIALLY_MEASURED"
    return {
        "status": status,
        "venue": latest.get("venue", "UNKNOWN"),
        "as_of": latest.get("as_of"),
        "stress_score": score,
        "components": measured,
        "coverage": len(measured) / max(len(tuple(components)), 1),
        "missing_components": missing,
        "alert_z": alert_z,
        "stress_alert": score >= alert_z if alert_z is not None else None,
        "uses": ["alpha_research", "risk_protection", "venue_economics"],
        "authority": (
            "STATE/PROTECTIVE INPUT ONLY -- existing venue, withdrawal and survival rails decide"
        ),
    }
