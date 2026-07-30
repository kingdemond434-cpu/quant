#!/usr/bin/env python3
"""BACKTEST ENGINE SELF-VERIFICATION -- activates libs/backtest against an independent reference.

WHY THIS EXISTS, and why it is a safeguard rather than a chore. ``libs/backtest/cross_engine.py``
opens with the reason: *"A one-person event-driven engine will contain subtle P&L bugs (adversarial
review W3.2), so results are cross-checked against independent implementations."* The check was
built and then never run outside its own unit test -- so the desk owned a P&L safeguard that was
not guarding anything.

HOW IT CAME TO LIGHT, which is the more useful half. Retiring the dead Alpha Discovery Factory on
2026-07-30 pushed max_audit's orphan-module count from 45 to 50, and the newest offenders were
``libs.backtest.*``. That looked like the retirement had broken something. It had not: the old
``libs/discovery/__init__.py`` re-exported ``factory``, and ``factory.py`` imported
``libs.backtest.engine``, so ANY script importing ``libs.discovery`` made the whole backtest package
look transitively reachable. Its only path to a live caller ran through a module with zero external
importers. Deleting the dead code did not orphan libs/backtest -- it revealed that libs/backtest had
been orphaned all along behind a fake reachability path.

So this script is the honest fix the desk's own rule demands ("wire or retire -- the budget ratchets
DOWN as the backlog is worked off, never up"), and wiring beats retiring here because an independent
P&L cross-check is worth more than the lines it costs.

WHAT IT PROVES: our event-driven engine and a pure-NumPy reference, given identical bars and
identical target positions, agree on every summary metric to 1e-9. They share no code paths -- the
engine walks events bar by bar, the reference is vectorised cumsum arithmetic -- so agreement is
real evidence rather than a tautology. A DELIBERATE MISMATCH is also run: the verifier must FAIL on
an engine result it should reject, because a checker that cannot fail proves nothing.

    python scripts/verify_backtest_engine.py [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OUT = ROOT / "data/backtest_verification.json"

#: Deterministic scenarios. Each exercises a different part of the fill/marking logic, because a
#: single flat-signal case would agree trivially and prove nothing about the interesting paths.
_CASES = (
    ("flat", 0.0),          # never in the market -- equity must be exactly init_cash
    ("always_long", 1.0),   # constant exposure -- marks every bar
    ("alternating", None),  # flips every bar -- exercises the delta/cash path hardest
)


def _bars(n: int = 240, seed: int = 11):
    import numpy as np
    import pandas as pd

    rng = np.random.default_rng(seed)
    close = 100.0 * np.exp(np.cumsum(rng.normal(0.0003, 0.012, n)))
    open_ = close * (1.0 + rng.normal(0.0, 0.001, n))
    # the canonical bar schema (libs/data/schema.py) wants an explicit tz-aware UTC `timestamp`
    # COLUMN, not a DatetimeIndex -- validate_bars rejects the frame outright otherwise
    return pd.DataFrame({
        "timestamp": pd.date_range("2025-01-01", periods=n, freq="D", tz="UTC"),
        "open": open_, "high": np.maximum(open_, close) * 1.002,
        "low": np.minimum(open_, close) * 0.998, "close": close,
        "volume": rng.lognormal(9.0, 0.4, n)})


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    from libs.backtest.cross_engine import (
        VerificationError,
        verify_against_vectorized,
        verify_cross_engine,
    )

    bars = _bars()
    n = len(bars)
    results: list[dict[str, object]] = []
    failures = 0

    for name, level in _CASES:
        targets = ([1.0 if i % 2 else -1.0 for i in range(n)] if level is None
                   else [level] * n)
        try:
            diffs = verify_against_vectorized(bars, targets, tolerance=1e-9)
            worst = max(diffs.values()) if diffs else 0.0
            results.append({"case": name, "ok": True, "worst_rel_diff": worst,
                            "metrics_compared": len(diffs)})
        except VerificationError as e:
            failures += 1
            results.append({"case": name, "ok": False, "error": str(e)[:300]})
        except Exception as e:                           # noqa: BLE001 - report, never crash cron
            failures += 1
            results.append({"case": name, "ok": False,
                            "error": f"{type(e).__name__}: {str(e)[:200]}"})

    # NEGATIVE CONTROL. A verifier that cannot fail is not evidence of anything, and this desk has
    # already shipped two guards that passed a defect they were built to catch (the label factory's
    # first two causality tests). So corrupt one metric and require the check to reject it.
    control_ok = False
    try:
        verify_cross_engine({"final_equity": 100.0}, {"final_equity": 200.0},
                            keys=("final_equity",), tolerance=1e-9)
    except VerificationError:
        control_ok = True
    if not control_ok:
        failures += 1

    payload = {
        "generated": datetime.now(tz=UTC).isoformat(),
        "status": "PASS" if failures == 0 else "FAIL",
        "bars": n, "cases": results,
        "negative_control_rejects_a_mismatch": control_ok,
        "note": "the engine walks events bar by bar; the reference is vectorised cumsum "
                "arithmetic. They share no code path, so agreement is evidence, not a tautology.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=1), "utf-8")
    tmp.replace(OUT)

    if a.json:
        print(json.dumps(payload, indent=1))
    else:
        print(f"backtest-verify | {payload['status']} over {n} bars")
        for r in results:
            mark = "ok  " if r.get("ok") else "FAIL"
            extra = (f"worst rel diff {r['worst_rel_diff']:.2e} across "
                     f"{r['metrics_compared']} metrics" if r.get("ok") else str(r.get("error"))[:120])
            print(f"  {mark} {r['case']:<12} {extra}")
        print(f"  negative control (must reject a mismatch): "
              f"{'ok' if control_ok else 'FAILED -- the checker cannot fail, so it proves nothing'}")
        print(f"\n-> {OUT.relative_to(ROOT)}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
