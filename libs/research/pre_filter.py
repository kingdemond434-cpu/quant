"""Tiered gauntlet pre-filter -- HYPOTHESIS_MAX_SPEC component #1, the cheap stage before
heavy validation compute (spec'd 2026-07-20, built 2026-07-29).

WHY THIS EXISTS, measured not asserted: the 420-candidate campaign burned full-gauntlet compute
on every candidate, and the per-candidate gates show most died for CHEAP reasons -- weak
in-sample edge, cost exceeding gross edge, degenerate activity -- all detectable in
microseconds from the return stream alone. The pre-filter rejects ONLY on cheap, unambiguous
evidence; anything borderline ESCALATES to the full gauntlet. It must never become a silent
alpha killer, so every decision lands in an append-only ledger with pass/fail counts and a
spot-audit cadence (audit every 3 days once >=50 rejects accumulate in the window, weekly
otherwise -- principal 2026-07-20: audit cadence is gated by throughput volume, not data drift).

MULTIPLICITY, the rule that keeps this honest: a pre-filter REJECT still counts in the trial
ledger (n_trials / DSR budget). The filter saves COMPUTE, never multiplicity budget -- a
candidate we looked at is a candidate we tested, however cheaply. Anything else would let the
desk peek for free, which is the exact overfitting engine the gauntlet exists to stop.

The novelty/graveyard half of spec component #1 deliberately lives UPSTREAM at generation time
(run_axis_generate's do_not_repeat + the novelty gate that blocked coinmetrics netflow on
2026-07-28) -- identity checks belong where names are minted, numeric checks belong here.

Stage-A discipline: ZERO promotion authority. PASS means "worth heavy compute", nothing more.
Pure numpy. import from libs.research.pre_filter.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np

_LEDGER = Path("data/pre_filter_ledger.jsonl")

# REJECT thresholds -- deliberately far from the gauntlet's own bars, so this stage can only
# remove candidates the full gauntlet would reject with near-certainty. Borderline escalates.
_T_REJECT = 0.0          # in-sample t <= 0: the sample itself points the wrong way
_GROSS_COST_MULT = 2.0   # spec: gross edge must exceed 2x modeled round-trip cost
_MIN_ACTIVE_FRAC = 0.02  # <2% of periods active = degenerate turnover (a handful of bets)
_MIN_ACTIVE_N = 20       # and never judge economics on fewer than 20 active periods
_SIGN_WINDOWS = 4        # sign stability: quarters of the active sample
_MAX_ONE_WINDOW_FRAC = 0.90  # >90% of total P&L from one quarter = single-event artifact


def pre_filter(returns: np.ndarray, *, name: str,
               rt_cost_per_trade: float | None = None,
               ledger: Path | None = _LEDGER) -> dict[str, Any]:
    """Cheap numeric screen on a candidate's per-period return stream.

    returns: full-length per-period simple returns, 0.0 = flat/inactive (the run_discovery
    convention). rt_cost_per_trade: modeled round-trip cost per position change, in return
    units (e.g. 9e-4 for 9 bps); None = cost check skipped (escalate on cost).

    Verdicts:
      REJECT   -- cheap, unambiguous: wrong-sign in-sample t, gross edge under 2x modeled
                  round-trip cost, degenerate activity, or single-window P&L concentration.
                  Routed to the graveyard by the caller WITH the reason; still charges a trial.
      ESCALATE -- everything else, including every borderline: full gauntlet, unchanged bar.
    There is deliberately no PASS-and-skip-the-gauntlet outcome. The filter only ever saves
    compute on the doomed, never certifies the promising.
    """
    r = np.asarray(returns, dtype="float64")
    active = r[r != 0.0]
    n_act = len(active)
    out: dict[str, Any] = {"name": name, "n": len(r), "n_active": n_act,
                           "stage": "pre-filter (zero promotion authority)"}

    if n_act < _MIN_ACTIVE_N or n_act < _MIN_ACTIVE_FRAC * len(r):
        # Too few bets to call the economics unambiguous in EITHER direction -- but a strategy
        # that basically never trades cannot clear a gauntlet built on >=250 active days either.
        # This is the one structural reject: not "the edge is bad" but "there is no strategy here".
        out.update(verdict="REJECT", reason="degenerate-turnover",
                   detail=f"{n_act} active of {len(r)} periods")
        return _log(out, ledger)

    sd = float(active.std())
    t_is = float(active.mean() / sd * np.sqrt(n_act)) if sd > 0 else 0.0
    out["t_insample"] = round(t_is, 2)
    if t_is <= _T_REJECT:
        out.update(verdict="REJECT", reason="wrong-sign-insample",
                   detail=f"t={t_is:.2f} on n={n_act}")
        return _log(out, ledger)

    # Cost-floor sanity (spec): GROSS per-trade edge must beat 2x the modeled round-trip cost.
    # Position changes approximated by activity transitions -- cheap and direction-agnostic.
    if rt_cost_per_trade is not None and rt_cost_per_trade > 0:
        trades = max(int(np.count_nonzero(np.diff((r != 0.0).astype("int8")) != 0)) // 2, 1)
        gross_per_trade = float(active.sum()) / trades
        out["gross_per_trade"] = round(gross_per_trade, 6)
        out["rt_cost"] = float(rt_cost_per_trade)
        if gross_per_trade < _GROSS_COST_MULT * rt_cost_per_trade:
            out.update(verdict="REJECT", reason="cost-exceeds-edge",
                       detail=(f"gross/trade {gross_per_trade:.5f} < "
                               f"{_GROSS_COST_MULT}x rt {rt_cost_per_trade:.5f}"))
            return _log(out, ledger)

    # Sign stability: split the ACTIVE stream into quarters; a candidate whose entire P&L sits
    # in one quarter is a single-event artifact, not a mechanism (the 2020-01-03 Soleimani
    # relabelling, register #79, is the canonical instance of this failure).
    chunks = np.array_split(active, _SIGN_WINDOWS)
    sums = np.array([c.sum() for c in chunks])
    out["window_sums"] = [round(float(x), 5) for x in sums]
    # Dominance is measured against GROSS window P&L (sum of |window sums|), not net: on a
    # near-zero-sum noise stream the net denominator collapses and one lucky window reads as
    # ">90% of total" -- a false trip measured on the first calibration run. Gross dominance
    # only fires when one window carries essentially all the P&L that exists anywhere.
    gross = float(np.abs(sums).sum())
    if gross > 0 and float(sums.max()) / gross > _MAX_ONE_WINDOW_FRAC:
        out.update(verdict="REJECT", reason="single-window-concentration",
                   detail=f"{float(sums.max()) / gross:.0%} of gross P&L in one window")
        return _log(out, ledger)

    out.update(verdict="ESCALATE", reason=None,
               detail="cleared cheap checks -- full gauntlet, unchanged bar")
    return _log(out, ledger)


def _log(out: dict[str, Any], ledger: Path | None) -> dict[str, Any]:
    if ledger is not None:
        ledger.parent.mkdir(parents=True, exist_ok=True)
        row = {"ts": datetime.now(tz=UTC).isoformat(), **out}
        with ledger.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, separators=(",", ":")) + "\n")
    return out


def ledger_counts(ledger: Path = _LEDGER, *, window_days: float = 7.0) -> dict[str, int]:
    """Pass/fail counts over the trailing window -- the KPI feed and the audit trigger input."""
    counts = {"ESCALATE": 0, "REJECT": 0}
    if not ledger.exists():
        return counts
    floor = datetime.now(tz=UTC) - timedelta(days=window_days)
    for line in ledger.read_text("utf-8").splitlines():
        try:
            row = json.loads(line)
            if datetime.fromisoformat(str(row["ts"])) >= floor:
                v = str(row.get("verdict", ""))
                counts[v] = counts.get(v, 0) + 1
        except (json.JSONDecodeError, KeyError, ValueError):
            continue
    return counts


def audit_due(ledger: Path = _LEDGER, *, state: Path | None = None) -> bool:
    """Spot-audit cadence per spec: >=50 rejects in the trailing week -> audit every 3 days;
    otherwise weekly. The AUDIT itself is a human/organ action (re-derive a sample of rejects
    at full depth and check the filter was right); this only answers "is one due now".
    state: json file holding {"last_audit": iso} (default data/pre_filter_audit_state.json).
    """
    st = state if state is not None else Path("data/pre_filter_audit_state.json")
    every = 3.0 if ledger_counts(ledger)["REJECT"] >= 50 else 7.0
    try:
        last = datetime.fromisoformat(json.loads(st.read_text("utf-8"))["last_audit"])
    except (OSError, json.JSONDecodeError, KeyError, ValueError):
        return True
    return datetime.now(tz=UTC) - last >= timedelta(days=every)
