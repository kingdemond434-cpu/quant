#!/usr/bin/env python3
"""WHAT A STALE FRACTION COSTS: the E[log W] price of sizing on a 15/60/180-minute-old solve.

    python research/fraction_staleness_cost.py [--json] [--max-commits N]

THE QUESTION (hourly-pass idea 611). The gateway and the E8 lane size from the allocator's
published fractions under a max-age check (KELLY_SURVIVAL.json's two-hour expiry, E8's own
freshness gate). How tight must that contract be? Answer it with the cost: at each decision time
t, size with the fraction published at t-L instead of t, and price the growth lost.

THE FRACTION HISTORY. `reports/KELLY_SURVIVAL.json` is gitignored and keeps no history, so the
published per-sleeve fractions come from `data/sleeves.json` (`risk_frac`, written by the
allocator/admission organs and committed with every box state push): every committed version is
one snapshot, read in one `git cat-file --batch` pass.

THE COST IS MODELLED, NOT MEASURED. No series of realised per-decision outcomes is joined to the
fraction that sized it, so the counterfactual replay the idea asks for cannot be MEASURED. The
cost is the second-order Kelly loss for growth g(f) = f*mu - f^2*sigma^2/2 near the fresh
solution: loss(L) ~= 1/2 * sum_i sigma_i^2 * (f_i(t) - f_i(t-L))^2 per day, with sigma_i^2 the
per-day R variance of sleeve i in the allocator's own worlds (`data/pf_allocator_cache/worlds.npz`;
the median column variance where a sleeve has no column). The drift distribution is the
measured one across the snapshots; the loss mapping is the model, and the artifact says MODELLED.
A bootstrap over decision times gives the 95% interval.

RECOMMENDED MAX AGE: the largest lag whose modelled cost is below 1% of the fresh book's
E[log W]/day. A fresh book with no positive growth, fewer than two snapshots, or no worlds is
UNMEASURED, never a clean verdict (L1.28a).

Report only: nothing reads it yet. Intended consumer: the freshness contract (the KELLY_SURVIVAL
expiry in the gateway / prop.e8_gold and the E8 max-age checks).

Clock: `hourly_cycle:fraction_staleness_cost` (department `forward`, layer `sizing`).
Artifact: `desks/mt5/reports/FRACTION_STALENESS_COST.json`
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parents[1]
OUT = BASE / "reports" / "FRACTION_STALENESS_COST.json"
WORLDS = BASE / "data" / "pf_allocator_cache" / "worlds.npz"
SLEEVES_REL = "desks/mt5/data/sleeves.json"
LAGS_MIN = (0, 15, 60, 180)
MAX_AGE_SHARE = 0.01
BOOTSTRAP = 2000

Snapshot = tuple[float, dict[str, float]]


def _fractions(doc: Any) -> dict[str, float]:
    rows = doc.get("sleeves") if isinstance(doc, Mapping) else doc
    out: dict[str, float] = {}
    for r in rows if isinstance(rows, list) else []:
        if isinstance(r, Mapping) and r.get("name"):
            try:
                out[str(r["name"])] = float(r.get("risk_frac") or 0.0)
            except (TypeError, ValueError):
                continue
    return out


def load_history(root: Path = ROOT, max_commits: int = 150) -> list[Snapshot]:
    """Every committed `data/sleeves.json`, oldest first, as (unix time, {sleeve: risk_frac})."""
    try:
        log = subprocess.run(["git", "-C", str(root), "log", "--format=%H %ct", "-n",
                              str(max_commits), "--", SLEEVES_REL],
                             capture_output=True, text=True, timeout=120, check=False).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    pairs = [ln.split() for ln in log.splitlines() if len(ln.split()) == 2]
    if not pairs:
        return []
    req = "".join(f"{h}:{SLEEVES_REL}\n" for h, _ in pairs).encode()
    try:
        raw = subprocess.run(["git", "-C", str(root), "cat-file", "--batch"], input=req,
                             capture_output=True, timeout=300, check=False).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    snaps: list[Snapshot] = []
    pos = 0
    for _, ts in pairs:
        nl = raw.find(b"\n", pos)
        if nl < 0:
            break
        head = raw[pos:nl].split()
        pos = nl + 1
        if len(head) < 3 or head[1] == b"missing":
            continue
        size = int(head[2])
        body = raw[pos:pos + size]
        pos += size + 1
        try:
            snaps.append((float(ts), _fractions(json.loads(body))))
        except ValueError:
            continue
    snaps.sort(key=lambda s: s[0])
    return snaps


def load_variances(path: Path = WORLDS) -> tuple[dict[str, float], dict[str, float]] | None:
    """Per-column per-day R variance and mean in the allocator's worlds, or None."""
    try:
        z = np.load(path, allow_pickle=True)
        r = np.asarray(z["r"], dtype=float)
        names = [str(n) for n in z["names"]]
    except (OSError, ValueError, KeyError):
        return None
    if r.ndim != 3 or r.shape[2] != len(names) or not names:
        return None
    flat = r.reshape(-1, r.shape[2])
    return ({n: float(flat[:, i].var()) for i, n in enumerate(names)},
            {n: float(flat[:, i].mean()) for i, n in enumerate(names)})


def _at(snaps: Sequence[Snapshot], t: float) -> dict[str, float] | None:
    """The snapshot in force at time t (the latest published at or before t)."""
    best = None
    for ts, fr in snaps:
        if ts <= t:
            best = fr
        else:
            break
    return best


def daily_losses(snaps: Sequence[Snapshot], var: Mapping[str, float], lag_min: float,
                 default_var: float) -> list[float]:
    """Per decision time, 1/2 * sum sigma^2 * (f(t) - f(t-L))^2."""
    out: list[float] = []
    for t, fresh in snaps:
        stale = _at(snaps, t - lag_min * 60.0)
        if stale is None:
            continue
        names = set(fresh) | set(stale)
        out.append(0.5 * sum(var.get(n, default_var)
                             * (fresh.get(n, 0.0) - stale.get(n, 0.0)) ** 2 for n in names))
    return out


def fresh_growth(snaps: Sequence[Snapshot], var: Mapping[str, float], mean: Mapping[str, float],
                 default_var: float) -> float:
    """Mean E[log W]/day of the book at its fresh fractions, g = sum f*mu - f^2*sigma^2/2."""
    vals = []
    for _, fr in snaps:
        vals.append(sum(f * mean.get(n, 0.0) - 0.5 * f * f * var.get(n, default_var)
                        for n, f in fr.items() if f and n in mean))
    return float(np.mean(vals)) if vals else 0.0


def _ci(x: Sequence[float], seed: int = 0) -> list[float]:
    a = np.asarray(x, dtype=float)
    if a.size == 0:
        return [0.0, 0.0]
    rng = np.random.default_rng(seed)
    boots = a[rng.integers(0, a.size, size=(BOOTSTRAP, a.size))].mean(axis=1)
    return [float(np.quantile(boots, 0.025)), float(np.quantile(boots, 0.975))]


def measure(snaps: Sequence[Snapshot], worlds: tuple[dict[str, float], dict[str, float]] | None,
            lags: Sequence[int] = LAGS_MIN) -> dict[str, Any]:
    doc: dict[str, Any] = {
        "generated_at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "report_only": True, "consumer": None,
        "intended_consumer": "the freshness contract: KELLY_SURVIVAL.json max-age check in the "
                             "gateway / prop.e8_gold and the E8 lane's fraction max-age checks",
        "fraction_source": f"git history of {SLEEVES_REL} (risk_frac per sleeve)",
        "loss_model": "1/2 * sum_i sigma_i^2 * (f_i(t) - f_i(t-L))^2 per day (2nd-order Kelly)",
        "lags_min": list(lags), "snapshots": len(snaps)}
    if worlds is None:
        doc.update(status="UNMEASURED", basis="UNMEASURED",
                   why="allocator worlds unreadable", recommended_max_age_min="UNMEASURED")
        return doc
    if len(snaps) < 2:
        doc.update(status="UNMEASURED", basis="UNMEASURED",
                   why=f"{len(snaps)} fraction snapshot(s); need two to see drift",
                   recommended_max_age_min="UNMEASURED")
        return doc
    var, mean = worlds
    dv = float(np.median(list(var.values()))) if var else 0.0
    g0 = fresh_growth(snaps, var, mean, dv)
    doc.update(status="OK", basis="MODELLED", fresh_elogw_per_day=g0,
               span_hours=round((snaps[-1][0] - snaps[0][0]) / 3600.0, 2),
               default_sigma2=dv,
               median_snapshot_gap_min=round(float(np.median(np.diff([t for t, _ in snaps])))
                                             / 60.0, 1),
               resolution_caveat="a lag shorter than the snapshot gap reads the previous "
                                 "snapshot, so its cost is an UPPER bound on that lag's cost",
               max_age_rule="largest lag whose 95%-upper cost is below 1% of fresh "
                            "E[log W]/day")
    rows: dict[str, Any] = {}
    for lag in lags:
        losses = daily_losses(snaps, var, lag, dv)
        cost = float(np.mean(losses)) if losses else 0.0
        rows[str(lag)] = {"n_decisions": len(losses),
                          "delta_elogw_per_day": -cost,
                          "delta_elogw_ci95": [-c for c in reversed(_ci(losses))],
                          "share_of_fresh": (cost / g0) if g0 > 0 else None}
    doc["by_lag"] = rows
    if g0 <= 0:
        doc["recommended_max_age_min"] = "UNMEASURED"
        doc["why"] = "fresh book E[log W]/day is not positive; a 1% share has no meaning"
    else:
        ok = [lag for lag in lags if -rows[str(lag)]["delta_elogw_ci95"][0] < MAX_AGE_SHARE * g0]
        doc["recommended_max_age_min"] = max(ok) if ok else 0
    return doc


def write_atomic(doc: Mapping[str, Any], out: Path = OUT) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.name + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=float), encoding="utf-8")
    os.replace(tmp, out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--max-commits", type=int, default=150)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    doc = measure(load_history(ROOT, a.max_commits), load_variances())
    write_atomic(doc, a.out)
    if a.json:
        print(json.dumps(doc, indent=1, default=float))
    else:
        print(f"fraction_staleness_cost: {doc['status']} basis={doc['basis']} "
              f"max_age={doc['recommended_max_age_min']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
