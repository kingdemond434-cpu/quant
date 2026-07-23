#!/usr/bin/env python3
"""GAP #19 VENUE-TRUTH DIVERGENCE -- SHADOW (observe-only, principal-approved 2026-07-23).

WHAT: logs the gap between the MARK-based book NAV (live_combined mcurve) and the VENUE-TRUTH
NAV (the dead-man's independent measure) every tick, so the circuit breaker's band can be
calibrated at "~2x OBSERVED noise" (GAP19_RECONCILE_GUARD_SPEC) from real data.

WHY SHADOW FIRST: you cannot calibrate a threshold against noise you have never measured. The
2026-07-22 dead-man false fires happened precisely because a trigger was set without knowing the
measurement noise of its own inputs. This measures first, arms later. The breaker itself stays
QUEUED post-Gate-0 per the spec (property/mutation testing + independence gate required).

Origin: proposed unprompted by TWO independent tier1 seats (moonshotai/kimi "Venue-Truth-First
Risk Measurement" + google/gemini "Venue-Truth Disconnect Circuit Breaker") -- corroboration is
why gap #19 was accepted while kimi's other two tier1 findings were rejected.

STRICTLY READ-ONLY. It never pauses opens, never pages, never flattens, and NEVER writes the
dead-man's state file (two-writers-on-one-rail was the 07-11 false-fire root cause). It only
appends to its own log.

    python scripts/run_venue_divergence_shadow.py            # sample once
    python scripts/run_venue_divergence_shadow.py --report   # calibration stats
"""
from __future__ import annotations

import argparse
import contextlib
import itertools
import json
from datetime import UTC, datetime
from pathlib import Path

_VENUE = Path("web/venue_equity.json")
_MARK = Path("data/live_combined_state.json")
_LOG = Path("data/venue_divergence_shadow.jsonl")
_STALE_S = 900.0          # a feed older than this cannot be compared honestly


def _age_s(p: Path) -> float:
    try:
        return max(0.0, datetime.now(tz=UTC).timestamp() - p.stat().st_mtime)
    except Exception:
        return float("inf")


def _venue_nav() -> float | None:
    try:
        return float(json.loads(_VENUE.read_text("utf-8"))["equity"])
    except Exception:
        return None


def _mark_nav() -> float | None:
    """Newest mark-based NAV from the live_combined equity curve."""
    try:
        curve = json.loads(_MARK.read_text("utf-8")).get("mcurve") or []
        return float(curve[-1][1]) if curve else None
    except Exception:
        return None


def sample() -> dict:
    v, m = _venue_nav(), _mark_nav()
    va, ma = _age_s(_VENUE), _age_s(_MARK)
    # A STALE feed manufactures fake divergence -- excluding it from calibration is the whole
    # point: a band fitted to stale-feed artefacts would trip on nothing real.
    stale = va > _STALE_S or ma > _STALE_S
    rec: dict[str, object] = {
        "ts": datetime.now(tz=UTC).isoformat(),
        "venue_nav": v, "mark_nav": m,
        "venue_age_s": round(va, 1) if va != float("inf") else None,
        "mark_age_s": round(ma, 1) if ma != float("inf") else None,
        "stale": bool(stale),
    }
    if v is not None and m is not None and v > 0:
        rec["abs_diff"] = round(m - v, 2)
        rec["pct_diff"] = round(100.0 * (m - v) / v, 4)
    _LOG.parent.mkdir(parents=True, exist_ok=True)
    with _LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")
    return rec


def report() -> None:
    if not _LOG.exists():
        print("venue-divergence shadow: no samples yet")
        return
    rows = []
    for line in _LOG.read_text("utf-8").splitlines():
        with contextlib.suppress(Exception):
            rows.append(json.loads(line))
    clean = [r for r in rows if not r.get("stale")
             and r.get("venue_nav") is not None and r.get("mark_nav") is not None]
    usable = [abs(float(r["pct_diff"])) for r in clean if r.get("pct_diff") is not None]

    # INCREMENT DIVERGENCE -- the signal gap #19 actually needs (2026-07-23 shadow finding).
    # The two feeds sit ~36% apart BY CONSTRUCTION (different bases: live_combined marks a
    # 15,000-based book; the dead-man measure is fut margin + TRACKED legs + USDT delta and
    # deliberately excludes untracked faucet spot). A level-vs-level band would trip instantly
    # and permanently on that definitional offset. What genuinely signals a reconciliation
    # break is the two measures DRIFTING APART between ticks.
    incs = []
    for a, b in itertools.pairwise(clean):
        dv = float(b["venue_nav"]) - float(a["venue_nav"])
        dm = float(b["mark_nav"]) - float(a["mark_nav"])
        base = abs(float(b["venue_nav"])) or 1.0
        incs.append(abs(dm - dv) / base * 100.0)
    if incs:
        incs.sort()
        m = len(incs)
        print(f"  INCREMENT divergence |d(mark)-d(venue)|: p50={incs[m // 2]:.4f}%  "
              f"p95={incs[min(m - 1, int(m * 0.95))]:.4f}%  max={incs[-1]:.4f}%  (n={m})")
        band = 2 * incs[min(m - 1, int(m * 0.95))]
        print(f"  ARMABLE BAND (~2x observed increment noise) => ~{band:.3f}%")
    else:
        print("  INCREMENT divergence: need >=2 clean consecutive samples")
    print(f"venue-divergence shadow: {len(rows)} samples, {len(usable)} usable "
          f"({len(rows) - len(usable)} excluded as stale/incomplete)")
    if not usable:
        print("  no clean samples yet -- band NOT calibratable; do NOT arm gap #19")
        return
    usable.sort()
    n = len(usable)
    p50 = usable[n // 2]
    p95 = usable[min(n - 1, int(n * 0.95))]
    mx = usable[-1]
    print(f"  LEVEL offset |pct_diff| p50={p50:.4f}% p95={p95:.4f}% max={mx:.4f}% "
          "(DEFINITIONAL -- different bases; do NOT band on this)")
    if n < 200:
        print(f"  NOT ENOUGH DATA to arm ({n} clean samples; want >=200 spanning rebalances "
              "and at least one regime event) -- gap #19 stays queued.")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args()
    if a.report:
        report()
        return
    r = sample()
    d = r.get("pct_diff")
    print(f"venue-divergence shadow: venue={r['venue_nav']} mark={r['mark_nav']} "
          f"diff={d if d is not None else 'n/a'}% stale={r['stale']}")


if __name__ == "__main__":
    main()
