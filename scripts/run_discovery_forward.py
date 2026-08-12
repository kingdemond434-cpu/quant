"""Discovery candidates get their own Stage-B forward clock -- the actual remaining piece.

WHY THIS IS THE REAL BLOCKER, not a missing actuator. `scripts/run_promotion_actuator.py` and
`scripts/run_slot_retirement.py` already exist, are principal-approved, and already run every 15
minutes via `run_pipeline_cycle.py` (found 2026-08-12 chasing "why can't promotion be automated" --
it already is, for the discretionary sleeve). The pattern is exactly right: a gate computes a
verdict from real evidence, an actuator transmits it with an immediate-down/wall-clock-gated-up
asymmetry, nothing skips a human on the one decision that belongs to a person (whether to START a
candidate), everything after that runs unattended.

But `scripts/check_promotion_gate.py` -- the gate `run_promotion_actuator.py` transmits -- reads
data/paper_book_pnl.json, mechanism_attribution.json, calibration_probe.json,
sleeve_allocation.json. All four are discretionary-sleeve evidence. It has never heard of
web/discovery.json. A DEPLOYABLE verdict from run_discovery.py is a full CPCV/DSR/PBO gauntlet pass
-- but on BACKTEST data already inside the panel every candidate in the library was screened
against. By this desk's own Two-Stage Discovery Law (Stage A ranks with ZERO promotion authority;
Stage B forward clocks are SOLE promotion authority), that is Stage A. It has no Stage B yet -- no
organ accrues real, out-of-sample forward days for it, the way run_derivative_shadow.py does for
oi_divergence/ls_contrarian. Without that, libs.risk.kelly_shrink.shrunk_kelly (the desk's already-
adopted, evidence-ramped sizing formula: 0 below 5 effective days, ~0.17x Kelly at day 15, ~0.36x at
40, ~0.55x at 90) has nothing to size against -- the formula is sound, there is simply no N yet.

WHAT THIS DOES. For every sleeve run_discovery.py currently reports DEPLOYABLE or SHADOW, records
the date it was FIRST seen at that status (data/discovery_forward_birth.json, first-write-wins --
reappearing after a bad run cannot buy an earlier birth date). Recomputes that sleeve's own return
construction on the full panel (imports _panels/_candidates from run_discovery.py directly rather
than re-deriving them, so the two can never quietly disagree about what a sleeve's return series
is) and counts ONLY the returns dated strictly after its birth as genuine forward evidence --
everything at or before birth was already visible to the gauntlet that promoted it and proves
nothing new. Peek-safe (anytime-valid e-process, Ville's inequality, same as
run_derivative_shadow.py) so accrual is readable daily without spending alpha; Sharpe stays
unpublished until MIN_DAYS. Writes web/discovery_forward.json.

WHAT THIS DOES NOT DO. It does not gate, size or promote anything -- ZERO promotion authority,
the same standing every Stage-A/Stage-B organ on this desk has. It writes an accrual artifact for a
future check_discovery_gate.py (not yet built) to read, the same relationship
run_derivative_shadow.py already has to its own not-yet-built promotion gate. Building THAT gate
before real forward days exist to size against would be building a decision with nothing to decide
on.

    python scripts/run_discovery_forward.py
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

_ROOT = Path("/home/quant/quant-platform")
if not _ROOT.exists():
    _ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.run_discovery import _candidates, _measured_side_cost, _panels  # noqa: E402

from libs.ops.lawful import guard as _law_guard  # noqa: E402
from libs.research.anytime_valid import e_value  # noqa: E402
from libs.validation.dsr import sharpe_ratio  # noqa: E402

_DISC = Path("web/discovery.json")
_BIRTH = Path("data/discovery_forward_birth.json")
_OUT = Path("web/discovery_forward.json")
_PPY = 365.0
_MIN_DAYS = 40


def _promotable_sleeves(disc: dict[str, object]) -> list[str]:
    return sorted({r["sleeve"] for r in disc.get("results", [])  # type: ignore[union-attr]
                   if str(r.get("status", "")).startswith(("DEPLOYABLE", "SHADOW"))})


def _load_birth(sleeves: list[str], today: str) -> dict[str, str]:
    """First-write-wins birth-date ledger -- a sleeve cannot un-flicker its way to an earlier
    birth by dropping out of DEPLOYABLE/SHADOW and reappearing later."""
    try:
        births = json.loads(_BIRTH.read_text("utf-8"))
    except (OSError, ValueError):
        births = {}
    for s in sleeves:
        births.setdefault(s, today)
    return births


def _forward_slice(series: pd.Series, birth: str) -> np.ndarray:
    birth_date = datetime.fromisoformat(birth).date()
    fwd = series[series.index.map(lambda ts: ts.date() > birth_date)]
    return fwd[fwd != 0.0].to_numpy()


def _sharpe(r: np.ndarray) -> float:
    return round(float(sharpe_ratio(r) * np.sqrt(_PPY)), 2) if len(r) > 5 else 0.0


def main() -> None:
    _law_guard()
    now = datetime.now(tz=UTC)
    today = now.date().isoformat()

    try:
        disc = json.loads(_DISC.read_text("utf-8"))
    except (OSError, ValueError) as exc:
        # ABSENT/UNREADABLE discovery.json is UNMEASURED, never zero and never fabricated.
        out = {"updated": now.isoformat(), "status": "UNMEASURED",
               "why": f"{_DISC} unreadable ({type(exc).__name__}: {exc})", "sleeves": {}}
        _OUT.parent.mkdir(parents=True, exist_ok=True)
        _OUT.write_text(json.dumps(out, indent=2), "utf-8")
        print(f"discovery forward: UNMEASURED -- {out['why']}")
        return

    sleeves = _promotable_sleeves(disc)
    births = _load_birth(sleeves, today)
    _BIRTH.parent.mkdir(parents=True, exist_ok=True)
    _BIRTH.write_text(json.dumps(births, indent=2, sort_keys=True), "utf-8")

    if not sleeves:
        out = {"updated": now.isoformat(), "status": "NO-PROMOTABLE-SLEEVES", "sleeves": {}}
        _OUT.parent.mkdir(parents=True, exist_ok=True)
        _OUT.write_text(json.dumps(out, indent=2), "utf-8")
        print("discovery forward: no DEPLOYABLE/SHADOW sleeves in discovery.json yet")
        return

    try:
        close, funding, basis, taker, adv = _panels()
        cost = {s: _measured_side_cost(s, a) for s, a in adv.items()}
        lib = _candidates(close, funding, basis, taker, adv, cost)
    except SystemExit as exc:
        # SAME CLASS as run_discovery.py's own universe-discovery refusal: fail visible, and
        # every sleeve's accrual reports the reason rather than silently freezing at 0 days.
        out = {"updated": now.isoformat(), "status": "REFUSED", "why": str(exc),
               "sleeves": {s: {"birth": births[s], "days_forward": None, "why": str(exc)}
                          for s in sleeves}}
        _OUT.parent.mkdir(parents=True, exist_ok=True)
        _OUT.write_text(json.dumps(out, indent=2), "utf-8")
        print(f"discovery forward: REFUSED -- {exc}")
        return

    dates = close.index
    rows: dict[str, dict[str, object]] = {}
    for s in sleeves:
        if s not in lib:
            rows[s] = {"birth": births[s], "days_forward": 0,
                      "why": "sleeve absent from today's panel (universe/data gap)"}
            continue
        series = pd.Series(lib[s], index=dates)
        fwd = _forward_slice(series, births[s])
        ready = len(fwd) >= _MIN_DAYS
        ev = round(e_value(fwd), 3) if len(fwd) else 0.0
        eta = (now + timedelta(days=max(0, _MIN_DAYS - len(fwd)))).date().isoformat()
        rows[s] = {
            "birth": births[s], "days_forward": len(fwd), "min_days": _MIN_DAYS,
            "progress_pct": round(100 * min(1.0, len(fwd) / _MIN_DAYS), 1),
            "expected_ready_date": eta,
            "status": "VALIDATING" if ready else "ACCUMULATING (no backtest fabricated)",
            "forward_sharpe": _sharpe(fwd) if ready else None,
            "anytime_peek": {"e_value": ev, "decisive": bool(ev >= 100.0)},
        }
    out = {
        "updated": now.isoformat(), "status": "OK", "min_days": _MIN_DAYS,
        "law": "Stage A (run_discovery.py's gauntlet pass) has ZERO promotion authority. Only "
               "days accrued strictly after a sleeve's birth date count here; a gate sized off "
               "this artifact is not yet built.",
        "sleeves": rows,
    }
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(out, indent=2, default=str), "utf-8")
    print(f"discovery forward: {len(sleeves)} promotable sleeve(s) tracked")
    for s, r in rows.items():
        print(f"  {s:18} {r.get('days_forward')}/{_MIN_DAYS}d  {r.get('status', r.get('why'))}")


if __name__ == "__main__":
    main()
