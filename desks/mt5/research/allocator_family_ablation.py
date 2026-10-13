#!/usr/bin/env python3
"""WHICH DATA FAMILIES CARRY CAPITAL VALUE -- an ablation of the allocator's own world sampler.

    python desks/mt5/research/allocator_family_ablation.py           write the report
    python desks/mt5/research/allocator_family_ablation.py --out X   write it somewhere else

THE QUESTION (ALLOC-25, principal): "for every input, say which decision it improves at what
horizon; remove an allegedly useful data family and test whether forecasts, portfolio value or
execution deteriorate out of sample." This module answers the PORTFOLIO-VALUE half, measured on
the allocator's own scenario population:

    for each data family F feeding the sleeves (and the states) the allocator samples:
      DROP     remove every sleeve whose information source is F, re-solve the book on the SAME
               worlds, and record the paired per-world change in E[log W] (median, quantiles,
               mean), the change in the survival-envelope breach probability, and the shift in
               the allocator's fractions;
      ADD      start from the price-only sleeves alone and add F's sleeves -- the reverse case:
               what F is worth on top of the baseline every desk has for free.

THE SAME WORLDS, NOT A FRESH DRAW. The population is `data/pf_allocator_cache/worlds.npz`, the
tensor `pf_allocator` drew and cached on its last pass (posterior mean shift, per-sleeve decay,
crisis overlay and cost draw already applied). Removing a family removes its COLUMNS; every world,
every resampled day and every crisis overlay is the one the allocator scored its own book on, so
the per-world difference is paired and its quantiles are the ablation's own, not two samplers'
noise. A family the tensor has no sleeve of is NOT_IN_POPULATION, never a zero.

STATE FAMILIES. The allocator also CONDITIONS the worlds on states: the macro kernel weights
(`libs.portfolio.macro_state`, a macro family), the regime labels (`pf_allocator.regime_state`,
fitted on XAUUSD daily closes -- price only). Those effects are baked into the cached tensor's
posterior draws, so they cannot be ablated by dropping columns. When the allocator's evidence
matrix (`data/pf_allocator_cache/daily_r.parquet`) is on this host, each state is ablated by
re-drawing the population from that matrix with the SAME seed and config with and without the
state; otherwise each state row reads UNMEASURED and names the missing input.

WHAT THIS IS NOT. A REPORT ONLY. It imports `robust_elog`, `kelly_surface`, `heat_policy` and
`pf_allocator` read-only, never edits them, never writes the allocator's cache, its book, the
sleeves, a registry or anything the gateway reads, and it charges NO trial: counting what the
existing book is worth without a family is a measurement of the book, not a new hypothesis tested.
Its only write is `reports/ALLOCATOR_FAMILY_ABLATION.json`.

THE MAPPING IS THE DESK'S OWN. Sleeve -> strategy family comes from `data/sleeves.json`, then
`data/sleeve_registry.json` identities, then the sleeve's own name parsed against the families
the desk registers; strategy family -> information source is `axis_registry.classify_family`
(the explicit, hand-kept table of every registered family). Two producer lanes whose names are
not family names are aliased with their provenance cited (`PROVENANCE_ALIASES`). Anything else is
UNMEASURED and counted as its own group -- an unknown source is not price only.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from collections.abc import Mapping, Sequence
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
for _p in (str(BASE), str(BASE / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.portfolio import kelly_surface  # noqa: E402
from libs.portfolio.robust_elog import (  # noqa: E402
    SleeveEvidence,
    WorldConfig,
    Worlds,
    optimise,
    sample_worlds,
)

OUT = BASE / "reports" / "ALLOCATOR_FAMILY_ABLATION.json"
WORLDS = BASE / "data" / "pf_allocator_cache" / "worlds.npz"
DAILY = BASE / "data" / "pf_allocator_cache" / "daily_r.parquet"
SLEEVES = BASE / "data" / "sleeves.json"
REGISTRY = BASE / "data" / "sleeve_registry.json"

UNMEASURED = "UNMEASURED"
MEASURED = "MEASURED"
NOT_IN_POPULATION = "NOT_IN_POPULATION"
#: The reverse case starts here: what every desk has for free from the broker's own bars.
BASELINE_FAMILY = "price_only"
#: The allocator re-draws hourly on its heavy clock; a population older than this describes a
#: book that no longer exists and the report says STALE (it still measures it -- a stale reading
#: labelled stale is information, a refusal is not).
MAX_WORLDS_AGE_S = 26 * 3600
#: Per-world quantiles of the paired delta.
QUANTILES = (0.05, 0.25, 0.50, 0.75, 0.95)
#: Ascent budget per solve. The allocator's own default; the population here is the cached one so
#: a solve costs milliseconds, not the minutes the evidence assembly costs.
ITERATIONS = 400

#: PRODUCER LANES WHOSE SLEEVE NAMES ARE NOT FAMILY NAMES, with the code that proves the source.
#:   gold_<window>          `research/portfolio_projection.build_sleeves`: `cell_trades` on the
#:                          XAUUSD H1 bars, one session bracket per gold window -- a session-range
#:                          breakout on the broker's own bars.
#:   <SYM>_<win>_<STATE>    the hunt12 survivors, same builder: the session bracket conditioned
#:                          on `run_hunt12.day_states` (TREND/NORMAL/RANGE/FAILED_BREAK), a state
#:                          derived from the same instrument's own daily bars.
PROVENANCE_ALIASES: dict[str, str] = {"session_bracket": "session_range_breakout"}
HUNT12_STATES = ("TREND_DAY", "NORMAL_DAY", "RANGE_DAY", "FAILED_BREAK", "TREND", "NORMAL",
                 "RANGE")

#: The states the allocator conditions its worlds on, and the data family each one reads.
STATE_INPUTS: dict[str, dict[str, str]] = {
    "macro_kernel": {"family": "macro",
                     "source": "libs/portfolio/macro_state.kernel_weights (dollar / risk / rates "
                               "rank of the PIT macro archive)",
                     "field": "SleeveEvidence.macro_w"},
    "regime_labels": {"family": "price_only",
                      "source": "research/pf_allocator.regime_state (HMM/GMM on XAUUSD daily "
                                "closes)",
                      "field": "WorldConfig.regime_labels / regime_probs"},
}


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8-sig"))
    except (OSError, ValueError):
        return None


# ------------------------------------------------------------------------- the mapping
def _family_table() -> dict[str, tuple[str, str, str]]:
    try:
        from research.axis_registry import FAMILY_TABLE
        return dict(FAMILY_TABLE)
    except Exception:
        return {}


def _scalp_candidates() -> dict[str, str]:
    """The scalp lane's sleeve -> family, read from `scalp_shadow.CANDIDATES` (its own source)."""
    try:
        from research.scalp_shadow import CANDIDATES
        return {str(k): str(v[1].family) for k, v in CANDIDATES.items()}
    except Exception:
        return {}


def strategy_family_of(name: str, *, sleeves_doc: Any, registry_doc: Any,
                       table: Mapping[str, Any], scalp: Mapping[str, str] | None = None,
                       ) -> tuple[str | None, str]:
    """(strategy family, where it was read) for one sleeve name; (None, why) if unknown."""
    rows = (sleeves_doc or {}).get("sleeves") if isinstance(sleeves_doc, Mapping) else None
    for row in rows or ():
        if isinstance(row, Mapping) and row.get("name") == name and row.get("family"):
            return str(row["family"]), "data/sleeves.json"
    if scalp and name in scalp:
        return scalp[name], "research/scalp_shadow.CANDIDATES"
    reg = (registry_doc or {}).get("sleeves") if isinstance(registry_doc, Mapping) else None
    if isinstance(reg, Mapping):
        for key, row in reg.items():
            head = str(key).split("#", 1)[0]
            if head.replace(".", "_") == name:
                fam = ((row or {}).get("identity") or {}).get("family")
                if fam:
                    return str(fam), "data/sleeve_registry.json"
    parts = name.split("_")
    if name.startswith("gold_"):
        return "session_bracket", "portfolio_projection.build_sleeves (gold window)"
    if len(parts) >= 3 and (parts[-1] in HUNT12_STATES or "_".join(parts[-2:]) in HUNT12_STATES):
        return "session_bracket", "portfolio_projection.build_sleeves (hunt12 survivor)"
    # <SYM>_<family>_<selector>: the family is the middle, and it must be one the desk registers.
    if len(parts) >= 3:
        mid = "_".join(parts[1:-1])
        if mid in table:
            return mid, "sleeve name (registered family)"
    return None, "no registry row, no alias and no registered family in the name"


def data_family_of(strategy_family: str | None, table: Mapping[str, Any]) -> str:
    """The information source a strategy family reads; UNMEASURED when the table cannot say."""
    if not strategy_family:
        return UNMEASURED
    fam = PROVENANCE_ALIASES.get(strategy_family, strategy_family)
    row = table.get(fam)
    if not row or row[1] in ("", "UNKNOWN", None):
        return UNMEASURED
    return str(row[1])


def map_sleeves(names: Sequence[str], *, sleeves_doc: Any = None, registry_doc: Any = None,
                table: Mapping[str, Any] | None = None,
                scalp: Mapping[str, str] | None = None) -> dict[str, dict[str, Any]]:
    tbl = _family_table() if table is None else table
    out: dict[str, dict[str, Any]] = {}
    for n in names:
        sf, src = strategy_family_of(n, sleeves_doc=sleeves_doc, registry_doc=registry_doc,
                                     table=tbl, scalp=scalp)
        out[n] = {"strategy_family": sf, "data_family": data_family_of(sf, tbl),
                  "mapped_from": src}
    return out


# ------------------------------------------------------------------------- the population
def population_age_s(path: Path, *, now: float | None = None) -> tuple[float, str]:
    """Seconds since the population was drawn, and how that was read.

    A FILE MTIME IN A CHECKOUT IS THE CHECKOUT'S TIME, NOT THE DRAW'S. On the box the allocator
    rewrites the file and its mtime is the truth; in a clone the file is as old as its commit and
    `git worktree add` stamps it "now" -- which would call a fortnight-old population FRESH. So
    when the file is tracked and unchanged from HEAD, the commit time is used if it is older.
    """
    import subprocess
    t = now if now is not None else time.time()
    age = t - path.stat().st_mtime
    try:
        rel = str(path.resolve().relative_to(ROOT))
        dirty = subprocess.run(["git", "status", "--porcelain", "--", rel], cwd=ROOT,
                               capture_output=True, text=True, timeout=20)
        ct = subprocess.run(["git", "log", "-1", "--format=%ct", "--", rel], cwd=ROOT,
                            capture_output=True, text=True, timeout=20)
        if dirty.returncode == 0 and not dirty.stdout.strip() and ct.stdout.strip():
            committed = t - float(ct.stdout.strip())
            if committed > age:
                return committed, "git commit time (file unchanged from HEAD)"
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    return age, "file mtime"


def load_worlds(path: Path = WORLDS, *, now: float | None = None,
                ) -> tuple[Worlds | None, dict[str, Any]]:
    """The allocator's cached population, read-only, or (None, why)."""
    meta: dict[str, Any] = {"path": str(path.relative_to(ROOT)) if path.is_relative_to(ROOT)
                            else str(path)}
    try:
        z = np.load(path, allow_pickle=False)
        r = np.asarray(z["r"], dtype=np.float32)
        names = tuple(str(x) for x in z["names"])
        crisis = np.asarray(z["crisis"], dtype=bool)
        mu = np.asarray(z["mu"], dtype=float)
        meta["fingerprint"] = (str(z["fingerprint"].item()) if "fingerprint" in z.files
                               else None)
    except (OSError, ValueError, KeyError) as exc:
        meta.update(status=UNMEASURED, why=f"world population unreadable: "
                                           f"{type(exc).__name__}: {exc}")
        return None, meta
    if r.ndim != 3 or r.shape[2] != len(names) or r.shape[0] < 2:
        meta.update(status=UNMEASURED, why=f"world tensor shape {r.shape} does not match "
                                           f"{len(names)} names")
        return None, meta
    age, basis = population_age_s(path, now=now)
    meta.update(status=MEASURED, shape=list(r.shape), n_crisis=int(crisis.sum()),
                age_h=round(age / 3600.0, 2), age_basis=basis,
                freshness=("FRESH" if age <= MAX_WORLDS_AGE_S else "STALE"))
    return Worlds(r=r, names=names, crisis=crisis, mu_draws=mu,
                  note="pf_allocator cached population"), meta


def _subworlds(worlds: Worlds, keep: Sequence[str]) -> Worlds:
    idx = [worlds.names.index(k) for k in keep]
    return Worlds(r=worlds.r[:, :, idx], names=tuple(keep), crisis=worlds.crisis,
                  mu_draws=(worlds.mu_draws[:, idx] if worlds.mu_draws.ndim == 2
                            else worlds.mu_draws),
                  regimes=worlds.regimes, note=worlds.note)


def proxy_evidence(worlds: Worlds, mapping: Mapping[str, Mapping[str, Any]]
                   ) -> list[SleeveEvidence]:
    """One SleeveEvidence per column, for the optimiser's redundancy term only.

    `optimise` needs evidence for `_corr_abs`. The series handed to it is the sleeve's own world
    returns, concatenated across the population -- so the co-movement the redundancy charge sees
    is the co-movement the worlds themselves carry, with ~W*T common days (the realised side of
    the blend dominates). The worlds are passed explicitly, so nothing is re-sampled from this.
    """
    w, t, _ = worlds.r.shape
    out = []
    for i, n in enumerate(worlds.names):
        m = mapping.get(n) or {}
        out.append(SleeveEvidence(name=n, daily_r=worlds.r[:, :, i].reshape(w * t).astype(float),
                                  family=str(m.get("strategy_family") or ""),
                                  symbol=n.split("_")[0]))
    return out


# ------------------------------------------------------------------------- one solve
def _heat_law() -> dict[str, float]:
    from research.heat_policy import HEAT_HARD_CEILING, HEAT_TARGET
    try:
        from research.pf_allocator import CURVE_SAMPLE_MAX
    except Exception:
        CURVE_SAMPLE_MAX = 1.0
    from mt5desk.gateway_config_fallback import MAX_DRAWDOWN_TOLERANCE
    return {"target": float(HEAT_TARGET), "ceiling": float(HEAT_HARD_CEILING),
            "sample_max": float(CURVE_SAMPLE_MAX), "tolerance": float(MAX_DRAWDOWN_TOLERANCE)}


def _bounds(names: Sequence[str], dd: Mapping[str, float], total: float) -> dict[str, float]:
    """The allocator's own per-sleeve bound (`heat_policy.per_sleeve_bounds`). A sleeve with no
    measured drawdown passes 0.0, which that function bounds as tightly as the armed book's
    worst -- the allocator's rule for an unmeasured drawdown, not one chosen here."""
    from research.heat_policy import per_sleeve_bounds
    return per_sleeve_bounds({n: float(dd.get(n, 0.0)) for n in names}, total)


def per_world_growth(worlds: Worlds, heat: Mapping[str, float]) -> np.ndarray:
    """Mean daily log growth of `heat` in each world (-inf where the book is wiped out)."""
    h = np.array([float(heat.get(n, 0.0)) for n in worlds.names], dtype=np.float32)
    port = np.einsum("wtn,n->wt", worlds.r, h, optimize=True).astype(np.float64)
    one = 1.0 + port
    ruined = np.any(one <= 1e-9, axis=1)
    g = np.log(np.where(one > 1e-9, one, 1.0)).mean(axis=1)
    return np.where(ruined, -np.inf, g)


def solve_variant(worlds: Worlds, keep: Sequence[str], mapping: Mapping[str, Mapping[str, Any]],
                  *, cfg: WorldConfig, law: Mapping[str, float], dd: Mapping[str, float],
                  ) -> dict[str, Any]:
    """The allocator's two solves on the `keep` columns of the same population, plus survival."""
    if not keep:
        return {"status": "EMPTY", "n_sleeves": 0, "heat": {}, "total_heat": 0.0,
                "g_w": np.zeros(worlds.n_worlds)}
    sub = _subworlds(worlds, keep)
    ev = proxy_evidence(sub, mapping)
    bounds = _bounds(keep, dd, law["target"])
    free = optimise(ev, hard_cap=law["sample_max"], target=None, cfg=cfg, worlds=sub,
                    max_per_sleeve=bounds, iterations=ITERATIONS)
    # THE MANDATED BOOK, at the heat law's target -- or at what the per-sleeve bounds can hold,
    # when a small family cannot fill it (named, never silently clipped).
    room = float(sum(bounds.values()))
    target = min(law["target"], room * (1.0 - 1e-9))
    mand = optimise(ev, hard_cap=max(law["sample_max"], target), target=target, cfg=cfg,
                    worlds=sub, max_per_sleeve=bounds, iterations=ITERATIONS)
    surf = kelly_surface.surface(sub, mand.heat, tolerance=law["tolerance"],
                                 alpha=cfg.cvar_alpha)
    env = kelly_surface.envelope(surf.get("rows") or [], alpha=cfg.cvar_alpha,
                                 fallback=law["ceiling"])
    at_book = surf.get("at_book") or {}
    return {
        "status": MEASURED, "n_sleeves": len(keep),
        "heat": {k: round(v, 6) for k, v in mand.heat.items()},
        "total_heat": round(mand.total_heat, 6),
        "target_heat": round(target, 6),
        "target_short_by_bounds": bool(room < law["target"]),
        "free_heat": round(free.total_heat, 6),
        "free_mean_log_growth": free.mean_log_growth,
        "free_robust_score": free.robust_score,
        "mean_log_growth": mand.mean_log_growth, "robust_score": mand.robust_score,
        "cvar_log_growth": mand.cvar_log_growth, "annual_growth_pct": mand.annual_growth_pct,
        "prob_annual_loss": mand.prob_annual_loss,
        "breach_p": at_book.get("p_dd_over_tolerance"), "ruin_p": at_book.get("p_ruin"),
        "envelope_ceiling": env.get("ceiling"), "envelope_status": env.get("status"),
        "envelope_binding": env.get("binding"),
        "g_w": per_world_growth(sub, mand.heat),
    }


def _num(x: Any) -> float | None:
    if isinstance(x, (int, float)) and math.isfinite(float(x)):
        return float(x)
    return None


def _diff(a: Any, b: Any, nd: int = 8) -> float | None:
    fa, fb = _num(a), _num(b)
    return None if fa is None or fb is None else round(fa - fb, nd)


def compare(variant: Mapping[str, Any], base: Mapping[str, Any]) -> dict[str, Any]:
    """Paired per-world delta of the mandated book's log growth, and every other shift."""
    gv, gb = np.asarray(variant["g_w"], float), np.asarray(base["g_w"], float)
    ok = np.isfinite(gv) & np.isfinite(gb)
    d = gv[ok] - gb[ok]
    dist: dict[str, Any] = {"n_worlds": int(ok.sum()),
                            "n_ruined_variant": int((~np.isfinite(gv)).sum()),
                            "n_ruined_base": int((~np.isfinite(gb)).sum())}
    if d.size:
        dist["mean"] = round(float(d.mean()), 8)
        for q in QUANTILES:
            dist[f"p{int(q * 100):02d}"] = round(float(np.quantile(d, q)), 8)
        dist["median_annual_pct"] = round((math.exp(float(np.median(d)) * 252.0) - 1.0) * 100, 3)
        dist["share_worlds_worse"] = round(float((d < 0).mean()), 4)
    hb, hv = base.get("heat") or {}, variant.get("heat") or {}
    names = sorted(set(hb) | set(hv))
    shift = {n: round(float(hv.get(n, 0.0)) - float(hb.get(n, 0.0)), 6) for n in names}
    movers = sorted(shift.items(), key=lambda kv: -abs(kv[1]))[:5]
    return {
        "delta_elog_per_world": dist,
        "delta_mean_log_growth": _diff(variant.get("mean_log_growth"), base.get("mean_log_growth")),
        "delta_robust_score": _diff(variant.get("robust_score"), base.get("robust_score")),
        "delta_free_mean_log_growth": _diff(variant.get("free_mean_log_growth"),
                                            base.get("free_mean_log_growth")),
        "delta_annual_growth_pct": _diff(variant.get("annual_growth_pct"),
                                         base.get("annual_growth_pct"), 3),
        "delta_breach_p": _diff(variant.get("breach_p"), base.get("breach_p"), 6),
        "delta_ruin_p": _diff(variant.get("ruin_p"), base.get("ruin_p"), 6),
        "delta_envelope_ceiling": _diff(variant.get("envelope_ceiling"),
                                        base.get("envelope_ceiling"), 6),
        "delta_total_heat": _diff(variant.get("total_heat"), base.get("total_heat"), 6),
        "fractions_l1_shift": round(float(sum(abs(v) for v in shift.values())), 6),
        "top_fraction_movers": [{"sleeve": k, "delta_heat": v} for k, v in movers if v],
    }


def _public(v: Mapping[str, Any]) -> dict[str, Any]:
    keep = ("status", "n_sleeves", "total_heat", "target_heat", "target_short_by_bounds",
            "free_heat", "mean_log_growth", "robust_score", "cvar_log_growth",
            "annual_growth_pct", "prob_annual_loss", "breach_p", "ruin_p", "envelope_ceiling",
            "envelope_status", "envelope_binding")
    out = {k: v.get(k) for k in keep if k in v}
    for k, x in list(out.items()):
        if isinstance(x, float) and not math.isfinite(x):
            out[k] = None
    return out


# ------------------------------------------------------------------------- the sleeve ablation
def sleeve_ablation(worlds: Worlds, mapping: Mapping[str, Mapping[str, Any]], *,
                    cfg: WorldConfig, law: Mapping[str, float],
                    dd: Mapping[str, float] | None = None,
                    families: Sequence[str] | None = None) -> dict[str, Any]:
    dd = dd or {}
    names = list(worlds.names)
    by_fam: dict[str, list[str]] = {}
    for n in names:
        by_fam.setdefault(str((mapping.get(n) or {}).get("data_family") or UNMEASURED),
                          []).append(n)
    try:
        from research.axis_registry import INFORMATION_SOURCES
        universe = [f for f in INFORMATION_SOURCES if f != "UNKNOWN"]
    except Exception:
        universe = []
    fams = list(families) if families is not None else sorted(set(universe) | set(by_fam))
    full = solve_variant(worlds, names, mapping, cfg=cfg, law=law, dd=dd)
    price = by_fam.get(BASELINE_FAMILY, [])
    base_price = solve_variant(worlds, price, mapping, cfg=cfg, law=law, dd=dd)
    rows: dict[str, Any] = {}
    for fam in fams:
        members = by_fam.get(fam, [])
        row: dict[str, Any] = {"family_status": UNMEASURED if fam == UNMEASURED else MEASURED,
                               "n_sleeves": len(members), "sleeves": members}
        if not members:
            row.update(status=NOT_IN_POPULATION,
                       why=f"no sleeve in the allocator's population reads '{fam}'; its capital "
                           "value here is unmeasured, not zero")
            rows[fam] = row
            continue
        rest = [n for n in names if n not in members]
        drop = solve_variant(worlds, rest, mapping, cfg=cfg, law=law, dd=dd)
        row["status"] = MEASURED
        row["drop"] = {"book": _public(drop), **compare(drop, full)}
        if fam == BASELINE_FAMILY:
            row["add_to_price_only"] = {"status": "IS_BASELINE"}
        elif not price:
            row["add_to_price_only"] = {"status": UNMEASURED,
                                        "why": "no price-only sleeve in the population to add to"}
        else:
            add = solve_variant(worlds, price + members, mapping, cfg=cfg, law=law, dd=dd)
            row["add_to_price_only"] = {"book": _public(add), **compare(add, base_price)}
        rows[fam] = row
    return {"full_book": _public(full), "price_only_book": _public(base_price),
            "families": rows}


# ------------------------------------------------------------------------- the state ablation
def _bare_evidence(daily: Any, mapping: Mapping[str, Mapping[str, Any]]) -> list[SleeveEvidence]:
    return [SleeveEvidence(name=str(c), daily_r=daily[c].to_numpy(dtype=float),
                           family=str((mapping.get(str(c)) or {}).get("strategy_family") or ""),
                           symbol=str(c).split("_")[0]) for c in daily.columns]


def state_ablation(daily_path: Path, mapping: Mapping[str, Mapping[str, Any]], *,
                   law: Mapping[str, float], seed: int = 0,
                   macro_weights: Any = None, regime: Any = None) -> dict[str, Any]:
    """Each conditioning state ablated by re-drawing from the evidence matrix, same seed/config.

    `macro_weights(dates) -> (weights, meta)` and `regime(daily) -> (labels, probs, diag)` default
    to `macro_state.kernel_weights` and `pf_allocator.regime_state`, both read-only.
    """
    out: dict[str, Any] = {k: dict(v) for k, v in STATE_INPUTS.items()}
    if not daily_path.exists():
        for row in out.values():
            row.update(status=UNMEASURED,
                       why=f"{daily_path.name} (the allocator's evidence matrix) is not on this "
                           "host; the cached world tensor carries the state effects baked into "
                           "its posterior draws, so the state cannot be removed from it")
        return out
    try:
        import pandas as pd
        daily = pd.read_parquet(daily_path)
        daily.index = [str(x) for x in daily.index]
        if macro_weights is None:
            from libs.portfolio.macro_state import kernel_weights as macro_weights
        if regime is None:
            from research.pf_allocator import regime_state as regime
        from research.pf_allocator import worst_dd_r
        dd = worst_dd_r(daily)
        dates = list(daily.index)
        w, _kmeta = macro_weights(dates)
        w = np.asarray(w, dtype=float)
        labels, probs, _diag = regime(daily)
        bare = _bare_evidence(daily, mapping)
        with_macro = [replace(e, macro_w=w) if w.size == e.daily_r.size else e for e in bare]
        cfg_full = WorldConfig(seed=seed, n_worlds=128, n_rows=256, regime_labels=tuple(labels),
                               regime_probs=tuple(probs))
        cfg_noreg = replace(cfg_full, regime_labels=(), regime_probs=())
        names = [e.name for e in bare]
        mp = {e.name: (mapping.get(e.name) or {}) for e in bare}

        def _solve(ev: list[SleeveEvidence], cfg: WorldConfig) -> dict[str, Any]:
            wp = sample_worlds(ev, cfg)
            return solve_variant(wp, names, mp, cfg=cfg, law=law, dd=dd)

        full = _solve(with_macro, cfg_full)
        variants = {"macro_kernel": (bare, cfg_full), "regime_labels": (with_macro, cfg_noreg)}
        for key, (ev, cfg) in variants.items():
            row = out[key]
            active = (bool(w.size) and any(e.macro_w.size for e in with_macro)
                      if key == "macro_kernel" else bool(labels and probs))
            if not active:
                row.update(status=UNMEASURED, why="the state produced nothing on this matrix "
                                                  "(no weights / no labels), so there is "
                                                  "nothing to remove")
                continue
            v = _solve(ev, cfg)
            row.update(status=MEASURED, pairing=("same seed, same config; worlds re-drawn "
                                                 "without the state"),
                       drop={"book": _public(v), **compare(v, full)})
        out["_full_book"] = _public(full)
        out["_basis"] = ("bare evidence matrix (daily_r.parquet) with only the state under test "
                         "-- no forward append, cost surface or hazard decay -- so the level is "
                         "approximate; the DELTA is the state's own")
    except Exception as exc:
        for k in STATE_INPUTS:
            out[k].update(status=UNMEASURED, why=f"state ablation failed: "
                                                 f"{type(exc).__name__}: {exc}")
    return out


# ------------------------------------------------------------------------- the report
def _table(sleeves: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for fam, r in (sleeves.get("families") or {}).items():
        d = (r.get("drop") or {})
        a = (r.get("add_to_price_only") or {})
        dd_ = d.get("delta_elog_per_world") or {}
        ad = a.get("delta_elog_per_world") or {}
        rows.append({"family": fam, "status": r.get("status"), "n_sleeves": r.get("n_sleeves"),
                     "drop_delta_elog_median": dd_.get("p50"),
                     "drop_delta_elog_p05": dd_.get("p05"),
                     "drop_delta_elog_p95": dd_.get("p95"),
                     "drop_delta_breach_p": d.get("delta_breach_p"),
                     "drop_fractions_l1": d.get("fractions_l1_shift"),
                     "add_delta_elog_median": ad.get("p50"),
                     "add_delta_breach_p": a.get("delta_breach_p")})
    return rows


def build(*, worlds_path: Path = WORLDS, daily_path: Path = DAILY, seed: int = 0,
          now: float | None = None) -> dict[str, Any]:
    t0 = time.time()
    doc: dict[str, Any] = {
        "generated_at": _now(), "requirement": "ALLOC-25",
        "question": ("for each data family feeding the allocator's sleeves and states: the "
                     "robust forward E[log W] and survival envelope lost when the family is "
                     "removed from the worlds the allocator samples, and gained when it alone "
                     "is added to the price-only baseline"),
        "report_only": True, "trials_charged": 0,
        "writes": ["desks/mt5/reports/ALLOCATOR_FAMILY_ABLATION.json"],
        "units": ("delta_elog_* are paired per-world differences in the mandated book's mean "
                  "daily log growth (variant minus reference); median_annual_pct annualises "
                  "the median at 252 days; delta_breach_p is the change in "
                  "P(drawdown > tolerance) at the book"),
    }
    worlds, wmeta = load_worlds(worlds_path, now=now)
    doc["population"] = wmeta
    law = _heat_law()
    doc["heat_law"] = law
    sl = _read_json(SLEEVES)
    reg = _read_json(REGISTRY)
    if worlds is None:
        doc["status"] = UNMEASURED
        doc["why"] = wmeta.get("why")
        doc["sleeves"] = {"status": UNMEASURED, "why": wmeta.get("why")}
        mapping: dict[str, dict[str, Any]] = {}
    else:
        mapping = map_sleeves(worlds.names, sleeves_doc=sl, registry_doc=reg,
                              scalp=_scalp_candidates())
        dd: dict[str, float] = {}
        if daily_path.exists():
            try:
                import pandas as pd

                from research.pf_allocator import worst_dd_r
                dd = worst_dd_r(pd.read_parquet(daily_path))
            except Exception:
                dd = {}
        cfg = WorldConfig(seed=seed)
        doc["sleeves"] = sleeve_ablation(worlds, mapping, cfg=cfg, law=law, dd=dd)
        doc["sleeves"]["drawdown_basis"] = (
            "measured per sleeve from daily_r.parquet" if dd else
            "UNMEASURED on this host: every sleeve bounded as the armed book's worst "
            "(heat_policy.per_sleeve_bounds's rule for an unmeasured drawdown)")
        doc["status"] = MEASURED if wmeta.get("freshness") == "FRESH" else "STALE"
    doc["mapping"] = mapping
    unm = sorted(n for n, m in mapping.items() if m.get("data_family") == UNMEASURED)
    doc["mapping_unmeasured"] = unm
    doc["states"] = state_ablation(daily_path, mapping, law=law, seed=seed)
    doc["table"] = _table(doc.get("sleeves") or {})
    measured = [r for r in doc["table"] if r["status"] == MEASURED]
    doc["summary"] = {
        "n_families_measured": len(measured),
        "n_families_not_in_population": sum(r["status"] == NOT_IN_POPULATION
                                            for r in doc["table"]),
        "n_sleeves_mapping_unmeasured": len(unm),
        "n_states_measured": sum((v or {}).get("status") == MEASURED
                                 for k, v in doc["states"].items() if not k.startswith("_")),
        # A family "carries capital value" when removing it lowers the median world's growth.
        "families_carrying_value": sorted(
            r["family"] for r in measured
            if isinstance(r.get("drop_delta_elog_median"), (int, float))
            and r["drop_delta_elog_median"] < 0),
    }
    doc["runtime_s"] = round(time.time() - t0, 2)
    return doc


def _clean(x: Any) -> Any:
    if isinstance(x, dict):
        return {str(k): _clean(v) for k, v in x.items() if k != "g_w"}
    if isinstance(x, (list, tuple)):
        return [_clean(v) for v in x]
    if isinstance(x, (np.floating, float)):
        f = float(x)
        return f if math.isfinite(f) else None
    if isinstance(x, np.integer):
        return int(x)
    if isinstance(x, np.bool_):
        return bool(x)
    return x


def write(doc: Mapping[str, Any], out: Path = OUT) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".tmp")
    tmp.write_text(json.dumps(_clean(doc), indent=1, sort_keys=False), encoding="utf-8")
    tmp.replace(out)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--worlds", type=Path, default=WORLDS)
    ap.add_argument("--daily", type=Path, default=DAILY)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args(argv)
    doc = build(worlds_path=a.worlds, daily_path=a.daily, seed=a.seed)
    write(doc, a.out)
    print(f"allocator_family_ablation: {doc['status']} population="
          f"{(doc.get('population') or {}).get('shape')} "
          f"age_h={(doc.get('population') or {}).get('age_h')} runtime={doc['runtime_s']}s")
    for r in doc["table"]:
        print(f"  {r['family']:<16} {r['status']:<18} n={r['n_sleeves']:<3} "
              f"drop dElog med={r['drop_delta_elog_median']} "
              f"dBreach={r['drop_delta_breach_p']}  add dElog med={r['add_delta_elog_median']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
