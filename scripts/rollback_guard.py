"""Reversible autonomous change guard -- checkpoint -> monitor -> auto-revert.

Every autonomous implementation must be reversible. This is the mechanism:
  checkpoint <label>  -- snapshot the autonomous-mutable code surface (scripts/ libs/ tests/ +
                         web/index.html + the root state JSONs) into data/rollback/<id>/, plus a
                         cheap baseline metrics record. Fast, no .venv/secrets/lake (code only).
  evaluate <id>       -- run the CI gate + compare live health to the baseline; print OK or REVERT
                         with reasons. Triggers (attributable to a CODE change, NOT market noise):
                         CI regression, executor heartbeat went stale, new cycle errors, or a
                         hedge-drift signal. PnL is deliberately NOT a trigger -- it is market-
                         confounded, so reverting on it would be noise-driven (dishonest).
  revert <id>         -- restore every tracked file from the snapshot (exact rollback).

Keeps the last 20 checkpoints. Pure stdlib. The autonomous CRO cycle checkpoints BEFORE it modifies
a subsystem and evaluates AFTER; it auto-reverts on a REVERT verdict.

    python scripts/rollback_guard.py checkpoint <label>
    python scripts/rollback_guard.py evaluate  <id>
    python scripts/rollback_guard.py revert    <id>
"""

from __future__ import annotations

import contextlib
import json
import shutil
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from libs.ops.platform_paths import venv_python

_ROOT = Path(__file__).resolve().parent.parent
_RB = _ROOT / "data" / "rollback"
_PY = venv_python(_ROOT)
_KEEP = 20
_ERR_GROWTH_LIMIT = 200                      # bytes of NEW error-log content that trips a revert

_TRACK_DIRS = ("scripts", "libs", "tests")   # snapshot every .py under these
_TRACK_FILES = ("web/index.html", "research_agenda.json", "engineering_backlog.json",
                "research_state.json", "alpha_pipeline.json")


def _tracked() -> list[Path]:
    out: list[Path] = []
    for d in _TRACK_DIRS:
        base = _ROOT / d
        if base.exists():
            out += [p.relative_to(_ROOT) for p in base.rglob("*.py")
                    if "__pycache__" not in p.parts]
    out += [Path(f) for f in _TRACK_FILES if (_ROOT / f).exists()]
    return out


def _metrics() -> dict[str, object]:
    """Cheap, no-network health snapshot (baseline for deterioration detection)."""
    err = _ROOT / "data" / "cashcarry_error.log"
    hb = _ROOT / "data" / "cashcarry_exec_heartbeat"
    port: dict[str, Any] = {}
    cc: dict[str, Any] = {}
    with contextlib.suppress(OSError, json.JSONDecodeError):
        port = json.loads((_ROOT / "web" / "portfolio.json").read_text("utf-8")).get("deployed", {})
    with contextlib.suppress(OSError, json.JSONDecodeError):
        cc = json.loads((_ROOT / "web" / "cashcarry_live.json").read_text("utf-8"))
    acts = cc.get("last_actions", []) if isinstance(cc.get("last_actions"), list) else []
    return {
        "ts": datetime.now(tz=UTC).isoformat(),
        "error_log_bytes": err.stat().st_size if err.exists() else 0,
        "hb_age_s": round(time.time() - hb.stat().st_mtime, 1) if hb.exists() else None,
        "hedge_drift": any("re-hedge" in a or "cover-orphan" in a or "RISK-FLATTEN" in a
                           for a in acts),
        "net_pnl": port.get("net_pnl"),
    }


def _ci_green() -> bool:
    r = subprocess.run([_PY, "scripts/run_ci.py"], cwd=str(_ROOT),
                       capture_output=True, text=True, check=False)
    return r.returncode == 0


def checkpoint(label: str) -> str:
    cid = f"{datetime.now(tz=UTC):%Y%m%dT%H%M%S}_{label}"
    dest = _RB / cid
    for rel in _tracked():
        (dest / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(_ROOT / rel, dest / rel)
    (dest / "_baseline.json").write_text(json.dumps(_metrics(), indent=2), "utf-8")
    for old in sorted(_RB.glob("*/"))[:-_KEEP]:               # prune to last _KEEP
        shutil.rmtree(old, ignore_errors=True)
    print(f"checkpoint {cid} ({len(_tracked())} files)")
    return cid


def evaluate(cid: str) -> str:
    dest = _RB / cid
    base = json.loads((dest / "_baseline.json").read_text("utf-8"))
    now = _metrics()
    reasons: list[str] = []
    if not _ci_green():
        reasons.append("CI regression (lint/tests/stress fail)")
    if now["error_log_bytes"] - base.get("error_log_bytes", 0) > _ERR_GROWTH_LIMIT:
        reasons.append(f"new cycle errors (+{now['error_log_bytes'] - base['error_log_bytes']}B)")
    if now["hedge_drift"] and not base.get("hedge_drift"):
        reasons.append("hedge drift appeared post-change")
    if base.get("hb_age_s") is not None and (now["hb_age_s"] or 999) > 240 \
            and base["hb_age_s"] <= 240:
        reasons.append("executor heartbeat went stale post-change")
    verdict = "REVERT" if reasons else "OK"
    print(f"evaluate {cid}: {verdict}" + (f" -> {'; '.join(reasons)}" if reasons else " (healthy)"))
    return verdict


def revert(cid: str) -> None:
    dest = _RB / cid
    n = 0
    for src in dest.rglob("*"):
        if src.is_file() and src.name != "_baseline.json":
            rel = src.relative_to(dest)
            (_ROOT / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, _ROOT / rel)
            n += 1
    print(f"reverted {cid} ({n} files restored)")


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    cmd, arg = sys.argv[1], sys.argv[2]
    if cmd == "checkpoint":
        checkpoint(arg)
    elif cmd == "evaluate":
        return 1 if evaluate(arg) == "REVERT" else 0
    elif cmd == "revert":
        revert(arg)
    else:
        print(f"unknown command: {cmd}")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
