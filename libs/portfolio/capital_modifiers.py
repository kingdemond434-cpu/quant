"""Every multiplier that touches a sleeve's capital, registered, two-sided, and scored.

THE GOVERNANCE RULE THIS ENFORCES. A risk system that only knows how to cut exposure turns into
a risk officer; the desk's rule is that every capital modifier must be able to say BOOST as well
as REDUCE, and every category it emits must prove incremental forward E[log W] or lose its
authority. So:

    STRONG_VETO   0.0x   the state's conditional expectancy is negative with evidence
    REDUCE        0.5x   clearly below unconditional
    NORMAL        1.0x   indistinguishable from unconditional
    BOOST         1.5x   clearly above unconditional
    STRONG_BOOST  2.0x   far above, with evidence

are the categories of the AI CAPITAL MODIFIER: the shrunk ratio of a sleeve's state-conditional
posterior mean to its unconditional mean, exactly the quantity `robust_elog._posterior_mu`
applies continuously inside the allocator. The categories do not re-size anything -- the
posterior already did, continuously -- they are the LEDGER of what the conditioning claimed,
so that `score()` can later ask, per category, whether trades it labelled BOOST outperformed
NORMAL out of sample. A category that does not prove its increment is reported COSTS_GROWTH and
the missed-growth ledger carries it.

THE REGISTRY lists every modifier on the desk with its range. The growth-governance fence
refuses a modifier whose range cannot exceed 1.0 unless it is declared an integrity kill-switch
(broker down, stale prices, margin anomaly) or a reduce-only decay signal that is itself a
registered, measured rail.
"""
from __future__ import annotations

import json
import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
DESK = ROOT / "desks" / "mt5"
LEDGER = DESK / "data" / "capital_modifier_ledger.jsonl"
REPORT = DESK / "reports" / "CAPITAL_MODIFIERS.json"

CATEGORIES: dict[str, float] = {"STRONG_VETO": 0.0, "REDUCE": 0.5, "NORMAL": 1.0,
                                "BOOST": 1.5, "STRONG_BOOST": 2.0}
K_STATE = 40.0


@dataclass(frozen=True)
class Modifier:
    name: str
    lo: float
    hi: float
    #: "two_sided" (must be able to boost), "integrity" (kill switch: broker/data/margin),
    #: "reduce_only" (a decay signal that must be a measured rail).
    kind: str
    where: str
    proof: str


REGISTRY: tuple[Modifier, ...] = (
    Modifier("state_posterior", 0.0, 2.0, "two_sided",
             "libs/portfolio/robust_elog._posterior_mu (state level of the hierarchy)",
             "desks/mt5/reports/STATE_ADMISSION.json"),
    Modifier("ai_capital_modifier", 0.0, 2.0, "two_sided",
             "libs/portfolio/capital_modifiers.category, ledgered by pf_allocator every pass",
             "desks/mt5/reports/CAPITAL_MODIFIERS.json"),
    Modifier("heat_resolution", 1.0, 1.5, "two_sided",
             "research/heat_policy.resolve: floor 20%, growth free to the 30% ceiling",
             "desks/mt5/reports/pf_allocation.json (aggression)"),
    Modifier("breadth_budget", 1.0, 1.5, "two_sided",
             "gateway.heat_budget: sqrt(k_eff) ladder above the base budget",
             "desks/mt5/reports/MISSED_GROWTH.json"),
    Modifier("fade", 0.5, 1.0, "reduce_only",
             "mt5desk.sizing.decay_factor (L1.59 fade flag from decay_monitor)",
             "desks/mt5/reports/MISSED_GROWTH.json"),
    Modifier("authority_ramp", 0.25, 1.0, "reduce_only",
             "gateway.promoted_lot ramp -- NOT applied to allocator-book sleeves",
             "desks/mt5/reports/MISSED_GROWTH.json"),
    Modifier("catastrophe_override", 0.0, 1.0, "integrity",
             "research/heat_policy.catastrophe_override: broker/prices/reconcile/margin",
             "n/a (integrity kill switch)"),
)


def category(mu_state: float, mu_uncond: float, n_state: int, k: float = K_STATE
             ) -> tuple[str, float]:
    """Category and continuous multiplier from the SHRUNK conditional/unconditional ratio."""
    if not (math.isfinite(mu_state) and math.isfinite(mu_uncond)) or n_state <= 0:
        return "NORMAL", 1.0
    lam = n_state / (n_state + k)
    if abs(mu_uncond) < 1e-12:
        ratio = 1.0 + lam * (1.0 if mu_state > 0 else -1.0)
    else:
        ratio = 1.0 + lam * (mu_state / mu_uncond - 1.0)
    mult = float(min(2.0, max(0.0, ratio)))
    if mult <= 0.05:
        return "STRONG_VETO", mult
    if mult < 0.7:
        return "REDUCE", mult
    if mult < 1.3:
        return "NORMAL", mult
    if mult < 1.8:
        return "BOOST", mult
    return "STRONG_BOOST", mult


def record(ev: Sequence[Any], book: dict[str, float], state_key: str,
           at: str | None = None) -> list[dict[str, Any]]:
    """Ledger one row per funded sleeve with state evidence. Never raises."""
    rows = []
    try:
        ts = at or datetime.now(tz=UTC).isoformat()
        for e in ev:
            h = float(book.get(e.name, 0.0))
            if h <= 1e-6:
                continue
            sr = np.asarray(getattr(e, "state_r", np.array([])), dtype=float)
            dr = np.asarray(e.daily_r, dtype=float)
            if sr.size == 0 or dr.size == 0:
                continue
            cat, mult = category(float(sr.mean()), float(dr.mean()), int(sr.size))
            rows.append({"t": ts, "sleeve": e.name, "state": state_key, "category": cat,
                         "multiplier": round(mult, 4), "n_state": int(sr.size),
                         "mu_state": round(float(sr.mean()), 6),
                         "mu_uncond": round(float(dr.mean()), 6), "heat": round(h, 6)})
        if rows:
            LEDGER.parent.mkdir(parents=True, exist_ok=True)
            with LEDGER.open("a", encoding="utf-8") as fh:
                for r in rows:
                    fh.write(json.dumps(r) + "\n")
    except Exception:
        return rows
    return rows


def _realized_by_sleeve_day() -> dict[tuple[str, str], float]:
    """Realised R per (sleeve, day) from the live and shadow ledgers, when present."""
    out: dict[tuple[str, str], float] = {}
    try:
        from research.state_admission_run import load_trades  # type: ignore[import-not-found]
        for t in load_trades("shadow"):
            day = str(t.when)[:10]
            out[(t.sleeve, day)] = out.get((t.sleeve, day), 0.0) + float(t.r)
    except Exception:
        pass
    return out


def score(write: bool = True) -> dict[str, Any]:
    """Per category: realised R on the days it was claimed, against NORMAL. The proof."""
    try:
        rows = [json.loads(ln) for ln in LEDGER.read_text("utf-8").splitlines() if ln.strip()]
    except (OSError, ValueError):
        rows = []
    realized = _realized_by_sleeve_day()
    by_cat: dict[str, list[float]] = {c: [] for c in CATEGORIES}
    for r in rows:
        key = (str(r.get("sleeve")), str(r.get("t"))[:10])
        if key in realized:
            by_cat[str(r.get("category"))].append(realized[key])
    base = np.asarray(by_cat.get("NORMAL", []), dtype=float)
    out = {}
    for cat, rs in by_cat.items():
        arr = np.asarray(rs, dtype=float)
        if arr.size < 20 or base.size < 20:
            out[cat] = {"n": int(arr.size), "verdict": "UNMEASURED",
                        "mean_r": (round(float(arr.mean()), 4) if arr.size else None)}
            continue
        diff = float(arr.mean() - base.mean())
        se = math.sqrt(arr.var(ddof=1) / arr.size + base.var(ddof=1) / base.size)
        t = diff / se if se > 0 else 0.0
        want_up = CATEGORIES[cat] > 1.0
        want_down = CATEGORIES[cat] < 1.0
        verdict = ("PROVES_INCREMENT" if ((want_up and t > 2.0) or (want_down and t < -2.0))
                   else ("COSTS_GROWTH" if ((want_up and t < -2.0) or (want_down and t > 2.0))
                         else ("NORMAL" if cat == "NORMAL" else "UNPROVEN")))
        out[cat] = {"n": int(arr.size), "mean_r": round(float(arr.mean()), 4),
                    "vs_normal": round(diff, 4), "t": round(t, 2), "verdict": verdict}
    doc = {"generated_utc": datetime.now(tz=UTC).isoformat(), "ledger_rows": len(rows),
           "matched_rows": int(sum(len(v) for v in by_cat.values())), "categories": out,
           "registry": [m.__dict__ for m in REGISTRY],
           "rule": ("a BOOST category proves itself when its realised R exceeds NORMAL's at "
                    "t > 2; a REDUCE category when it falls short at t < -2; anything else is "
                    "UNPROVEN and carries no authority beyond the continuous posterior")}
    if write:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(doc, indent=1), "utf-8")
    return doc
