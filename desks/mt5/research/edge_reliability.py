"""P(this edge works NOW), per sleeve: one number that fuses what the desk already measures.

MEASURED 2026-09-08 (Tier-1 programme item P6): the desk has a hazard (P(breaks next
horizon), drift-channel-derived, often None under its own floors), a decay verdict
(HEALTHY / FADE / RETIRE), a forward ledger (n, expectancy, t) and, since wave W3, an
e-process reading -- and no single reliability posterior that combines them. Each reader
picks one. The allocator sees the ledger, the promoter sees the verdict, the dashboard sees
the hazard, and "is this sleeve working right now" has four answers on four pages.

WHAT THIS IS. A fused score with NAMED components, per sleeve, written as an artifact:

    evidence   Beta-binomial P(mean R > 0) from the forward ledger (n, exp_r, t) -- the
               ledger's own t-statistic mapped through a logistic, shrunk to 0.5 below MIN_N
    decay      the decay monitor's verdict as a declared multiplier (DECAY_FACTOR)
    e_process  wave W3's kill-only e-value: evidence the sleeve LOSES, mapped to 1/(1+e)
               above the alpha line -- present only when the engine stamped one
    half_life  the fitted half-life (wave W5b) as time-to-fade against the forward bar

    p_works_now = evidence x decay x e_process x half_life_factor

WHAT IT IS NOT. Not a posterior in the Bayesian sense -- the factors are declared, not
learned -- and the artifact says so in `basis`. Not a decision: nothing reads this to size,
promote or retire; it is published so the allocator wave can decide whether it may, and so
that "P(works now)" is a column rather than a debate. UNMEASURED per sleeve when the ledger
is below MIN_N; every factor that is absent reads 1.0 and is listed under `absent`.
"""
from __future__ import annotations

import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
REPO = BASE.parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

SHADOW = BASE / "reports" / "shadow"
STATE_FILES = ("shadow_state.json", "qquant_shadow_state.json", "scalp_shadow_state.json",
               "external_shadow_state.json")
DECAY = BASE / "data" / "decay_live.json"
OUT = BASE / "reports" / "edge_reliability.json"

MIN_N = 20                       # below this the ledger says nothing and evidence is 0.5
DECAY_FACTOR = {"HEALTHY": 1.0, "FADE": 0.5, "RETIRE": 0.1}
E_ALPHA = 0.01                   # forward_verdict.E_ALPHA: 1/alpha is the kill line
FORWARD_BAR_D = 14.0             # the verdict clock; a shorter half-life is a fade in flight


def _read(path: Path) -> dict[str, Any]:
    try:
        d = json.loads(path.read_text("utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _num(*vals: Any) -> float | None:
    for v in vals:
        if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v):
            return float(v)
    return None


def evidence_factor(n: int | None, t: float | None) -> tuple[float, str]:
    """P(mean R > 0) from the ledger's t-statistic through a logistic; 0.5 below MIN_N."""
    if not n or n < MIN_N:
        return 0.5, f"n={n or 0} < {MIN_N}: ledger says nothing yet"
    if t is None:
        return 0.5, "no t-statistic on the row"
    return round(1.0 / (1.0 + math.exp(-1.7 * t)), 4), f"logistic(1.7 x t={t:.2f}) at n={n}"


def e_factor(e_value: Any) -> tuple[float, str]:
    e = _num(e_value)
    if e is None:
        return 1.0, "absent"
    line = 1.0 / E_ALPHA
    if e < 1.0:
        return 1.0, f"e={e:.3g} < 1: no evidence of loss"
    return round(1.0 / (1.0 + e / line), 4), f"e={e:.3g} against the {line:.0f} kill line"


def half_life_factor(hl_days: Any) -> tuple[float, str]:
    hl = _num(hl_days)
    if hl is None or hl <= 0:
        return 1.0, "absent"
    return round(min(1.0, hl / (2.0 * FORWARD_BAR_D)), 4), \
        f"half-life {hl:.1f}d against 2 x {FORWARD_BAR_D:.0f}d"


def sleeve_score(row: dict[str, Any], decay: dict[str, Any] | None) -> dict[str, Any]:
    n = int(_num(row.get("n")) or 0)
    t = _num(row.get("forward_t"), row.get("t"))
    exp_r = _num(row.get("exp_r"), row.get("expectancy_r"))
    ev, ev_why = evidence_factor(n, t)
    verdict = str((decay or {}).get("verdict") or "")
    dfac = DECAY_FACTOR.get(verdict, 1.0)
    efac, e_why = e_factor(row.get("e_value"))
    model = (decay or {}).get("decay_model") or {}
    hfac, h_why = half_life_factor(model.get("half_life_days") if isinstance(model, dict) else None)
    absent = [k for k, ok in (("decay", bool(verdict)), ("e_process", e_why != "absent"),
                              ("half_life", h_why != "absent")) if not ok]
    p = round(ev * dfac * efac * hfac, 4)
    return {"p_works_now": p if n >= MIN_N else None,
            "status": "MEASURED" if n >= MIN_N else "UNMEASURED",
            "n": n, "t": t, "exp_r": exp_r,
            "factors": {"evidence": ev, "decay": dfac, "e_process": efac, "half_life": hfac},
            "why": {"evidence": ev_why, "decay": verdict or "absent", "e_process": e_why,
                    "half_life": h_why},
            "absent": absent, "sleeve_id": row.get("sleeve_id"),
            "certificate": row.get("certificate")}


def load_rows(shadow: Path = SHADOW) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for name in STATE_FILES:
        doc = _read(shadow / name)
        items = list(doc.items())
        if isinstance(doc.get("sleeves"), dict):
            items += list(doc["sleeves"].items())
        for key, row in items:
            if isinstance(row, dict) and "status" in row:
                rows[str(key)] = row
    return rows


def build(now: datetime | None = None, shadow: Path = SHADOW,
          decay_path: Path = DECAY) -> dict[str, Any]:
    now = now or datetime.now(tz=UTC)
    rows = load_rows(shadow)
    decay = _read(decay_path)
    verdicts = decay.get("verdicts") if isinstance(decay.get("verdicts"), dict) else {}
    sleeves = {k: sleeve_score(r, verdicts.get(k)) for k, r in rows.items()}
    measured = {k: v for k, v in sleeves.items() if v["status"] == "MEASURED"}
    ranked = sorted(measured.items(), key=lambda kv: -(kv[1]["p_works_now"] or 0.0))
    return {
        "at": now.isoformat(timespec="seconds"), "sleeves": sleeves,
        "n_sleeves": len(sleeves), "n_measured": len(measured),
        "ranked": [{"sleeve": k, "p_works_now": v["p_works_now"]} for k, v in ranked[:50]],
        "basis": ("fused score with declared factors, not a learned posterior: "
                  "evidence(logistic t) x decay(HEALTHY 1 / FADE .5 / RETIRE .1) x "
                  "e_process(1/(1+e/100)) x half_life(min(1, hl/28d)); consumer: none yet"),
        "parameters": {"min_n": MIN_N, "decay_factor": DECAY_FACTOR, "e_alpha": E_ALPHA,
                       "forward_bar_d": FORWARD_BAR_D},
        "status": "MEASURED" if measured else ("UNMEASURED" if sleeves else "NO_SLEEVES"),
    }


def main(argv: list[str] | None = None) -> int:
    doc = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    print(f"edge reliability: {doc['status']}; {doc['n_measured']}/{doc['n_sleeves']} sleeves "
          f"measured; top {doc['ranked'][:3]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
