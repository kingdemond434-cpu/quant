"""Apply the immutable discovery screen and emit candidates for the gauntlet.

There is deliberately no later, harsher, effective-N, or deflated admission
bar here. This screen ranks discoveries only: it cannot admit shadow or grant
promotion authority. Shadow admission requires the fixed original universal
ten-gate certificate in ``gate_policy.py``.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

import pandas as pd

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE.parent.parent))

from libs.validation.dsr import probabilistic_sharpe_ratio  # noqa: E402

SCREEN_VERSION = "mt5-original-psr95-sr0-v1"
PSR_THRESHOLD = 0.95
SR_BENCHMARK = 0.0
TPY = 252
FORWARD_POLICY = {
    "evaluate_after_trades": 50,
    "evaluate_after_days": 14,
    "minimum_trades_for_verdict": 20,
}

CACHE = BASE / "data" / "full_hunt_series.parquet"
OUT = BASE / "data" / "hunt_candidates.json"


def _atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def candidate_row(cell: str, sharpe: float, psr: float, n_trials: int) -> dict:
    """Canonical original-screen admission record."""
    return {
        "cell": cell,
        "in_sample_sharpe": sharpe,
        "n_trials_searched": n_trials,
        "original_psr": psr,
        "original_screen": {
            "version": SCREEN_VERSION,
            "psr_threshold": PSR_THRESHOLD,
            "sr_benchmark": SR_BENCHMARK,
        },
        "shadow_status": "PENDING_UNIVERSAL_10_GATE",
        "promotion_authority": False,
        "capital_confirmation": "FORWARD_ONLY",
        "forward_policy": dict(FORWARD_POLICY),
    }


def normalize_existing(rows: list[dict]) -> list[dict]:
    """Migrate legacy admitted rows without re-screening or excluding any."""
    out = []
    for old in rows:
        if not isinstance(old, dict) or not old.get("cell"):
            continue
        psr = old.get("original_psr", old.get("psr_raw"))
        if psr is None:
            continue
        out.append(candidate_row(
            str(old["cell"]),
            float(old.get("in_sample_sharpe", 0.0)),
            float(psr),
            int(old.get("n_trials_searched", 0)),
        ))
    out.sort(key=lambda row: (
        -row["original_psr"], -row["in_sample_sharpe"], row["cell"]
    ))
    return out


def build_candidates(df: pd.DataFrame, n_trials: int) -> list[dict]:
    rows = []
    for cell in df.columns:
        arr = df[cell].dropna().to_numpy(dtype=float)
        if len(arr) < 100:
            continue
        std = float(arr.std(ddof=1))
        sharpe = 0.0 if std == 0.0 else float(arr.mean() / std * math.sqrt(TPY))
        psr = float(probabilistic_sharpe_ratio(arr, sr_benchmark=SR_BENCHMARK))
        if psr >= PSR_THRESHOLD:
            rows.append(candidate_row(str(cell), sharpe, psr, n_trials))
    rows.sort(key=lambda row: (
        -row["original_psr"], -row["in_sample_sharpe"], row["cell"]
    ))
    return rows


def write_candidates(df: pd.DataFrame, n_trials: int) -> tuple[Path, list[dict]]:
    """Build and atomically publish the canonical shadow-admission artifact."""
    rows = build_candidates(df, n_trials)
    _atomic_json(OUT, rows)
    return OUT, rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--normalize-existing", action="store_true")
    args = parser.parse_args(argv)

    if args.normalize_existing:
        if not OUT.exists():
            print(f"no existing candidate artifact at {OUT}")
            return 0
        try:
            rows = json.loads(OUT.read_text("utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"refusing to rewrite unreadable candidate artifact: {exc}")
            return 1
        if not isinstance(rows, list):
            print("refusing to rewrite non-list candidate artifact")
            return 1
        migrated = normalize_existing(rows)
        _atomic_json(OUT, migrated)
        print(f"normalized {len(migrated)} existing candidates to {SCREEN_VERSION}")
        return 0

    if not CACHE.exists():
        print(f"no cache at {CACHE}; run full_hunt.py first")
        return 1
    df = pd.read_parquet(CACHE)
    n_trials = int(df.attrs.get("n_trials_attempted", 3168))
    _path, rows = write_candidates(df, n_trials)
    print(f"ORIGINAL IMMUTABLE SCREEN {SCREEN_VERSION}")
    print(f"PSR >= {PSR_THRESHOLD:.2f} against SR0={SR_BENCHMARK:.1f}")
    print(f"{len(rows)} discoveries queued for the original universal ten-gate gauntlet")
    print("no discovery screen or harsher overlay can admit a sleeve to shadow")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
