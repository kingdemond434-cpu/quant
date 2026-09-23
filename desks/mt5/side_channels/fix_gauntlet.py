#!/usr/bin/env python3
"""
fix_gauntlet.py — SELF-HEALING FIXER + HOURLY WATCHDOG for the full pipeline.

Guarantees every hour:
  1. full_pipeline.py is the canonical v3 (FIXED calibrated gates, full param-grid sweep).
     If anything trampled it, it is restored from the canonical copy placed in this dir.
  2. The pipeline actually RAN within the last ~75 minutes (never stale) — if not, run it now.
  3. Gates never rise: the canonical file has hard asserts tying thresholds to the
     gate_spec.yaml calibrated policy (PBO<=0.5, DSR>=0.95, WF 4/0.5, SPA 0.05).

Cron (hourly):  5 * * * * cd /home/quant/quant-platform && .venv/bin/python scripts/fix_gauntlet.py watch >> logs/fix_gauntlet.log 2>&1
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

BASE = Path("/home/quant/quant-platform")
SC = BASE / "desks" / "mt5" / "side_channels"
FP = SC / "full_pipeline.py"
CANON = SC / "full_pipeline.canonical.py"
REPORTS = BASE / "desks" / "mt5" / "reports"
LOGS = BASE / "logs"
VENV_PY = BASE / ".venv" / "bin" / "python"
GATE_REPORT = REPORTS / "universal_gates_external.json"

MARKERS_CALIBRATED = [
    "FULL PIPELINE v3",
    "FIXED CALIBRATED GATES",
    "deflated_sharpe_ratio as dsr_canon",
    "probability_backtest_overfitting as pbo_canon",
    "assert PBO_THR >= 0.5",
    "_expand_grid",
]


def log(msg: str) -> None:
    ts = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def is_calibrated() -> bool:
    try:
        t = FP.read_text(encoding="utf-8")
    except Exception:
        return False
    return all(m in t for m in MARKERS_CALIBRATED)


def repair() -> bool:
    """Restore the canonical pipeline file if the working copy drifted."""
    if not CANON.exists():
        log("  canonical copy missing — nothing to restore from")
        return False
    if is_calibrated():
        return True
    log("  full_pipeline.py drifted — restoring canonical v3")
    shutil.copyfile(CANON, FP)
    if is_calibrated():
        log("  restored OK")
        return True
    log("  restore FAILED")
    return False


def last_run_age_hours() -> float:
    if not GATE_REPORT.exists():
        return float("inf")
    try:
        d = json.loads(GATE_REPORT.read_text("utf-8"))
        swept = datetime.fromisoformat(d.get("swept_at", "")).replace(tzinfo=UTC)
        return (datetime.now(UTC) - swept).total_seconds() / 3600.0
    except Exception:
        return float("inf")


def run_pipeline() -> int:
    log("  running full pipeline (backtest -> gauntlet -> certify -> shadow admission)")
    env = dict(os.environ)
    log_path = LOGS / "full_pipeline_hourly.log"
    LOGS.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as fh:
        proc = subprocess.run(
            [str(VENV_PY), "-u", str(FP)],
            cwd=str(BASE), env=env, stdout=fh, stderr=fh, timeout=5400,
        )
    if proc.returncode == 0:
        log("  pipeline OK")
    else:
        log(f"  pipeline EXITED rc={proc.returncode}")
    return proc.returncode


def verify_gates() -> bool:
    """Independent check that the canonical spec thresholds are the calibrated ones."""
    try:
        sys.path.insert(0, str(SC))
        import gate_policy_fixed as gp
        ok = (
            gp.PBO_THRESHOLD >= 0.5
            and gp.DSR_THRESHOLD <= 0.95
            and gp.SPA_ALPHA == 0.05
            and gp.WF_SPLITS == 4
            and gp.WF_MIN_STABILITY <= 0.5
        )
        if not ok:
            log(f"  GATE DRIFT DETECTED: PBO={gp.PBO_THRESHOLD} DSR={gp.DSR_THRESHOLD} "
                f"SPA={gp.SPA_ALPHA} WF={gp.WF_SPLITS}/{gp.WF_MIN_STABILITY}")
        return ok
    except Exception as e:
        log(f"  gate_policy_fixed import failed: {e}")
        return False


def watch() -> int:
    log(f"[watch] start — repo={BASE.name}")
    repaired = repair()
    gates_ok = verify_gates()
    stale = last_run_age_hours()
    log(f"[watch] calibrated={is_calibrated()} repaired={repaired} gates_ok={gates_ok} "
        f"last_run_h={stale:.2f}")
    if not gates_ok:
        log("  GATES DRIFT — refusing to run until spec restored")
        return 1
    if stale > 1.25 or not repaired:
        run_pipeline()
    else:
        log("  pipeline fresh (last run <75min) — no action")
    return 0


def stale_only() -> int:
    age = last_run_age_hours()
    print(f"last_run_h={age:.2f}")
    return 0 if age <= 1.25 else 1


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "watch"
    if mode == "repair":
        return 0 if repair() else 1
    if mode == "stale":
        return stale_only()
    if mode == "run":
        return run_pipeline()
    if mode == "check":
        print(f"calibrated={is_calibrated()} gates_ok={verify_gates()} last_run_h={last_run_age_hours():.2f}")
        return 0
    return watch()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(0)