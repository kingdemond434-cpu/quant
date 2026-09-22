"""PROGRESS HEARTBEATS, NOT PROCESS HEARTBEATS.

A PID is not health. Measured on this desk repeatedly: a resident whose lock was held by a live
process and whose log had not moved in two hours; a search leg SIGKILLed at the same prefix every
hour so the tail was never reached, reporting as scheduled and running the whole time; a gauntlet
process alive while its trial cursor stood still. Every one of those is GREEN to a liveness probe
and BROKEN to anyone who looks at the work.

So health is a monotone WORK counter, one per component, and the reconciler compares its movement
against the component's own SLA:

    progress("leg:forest_korea", "sources_scanned", 1412)
    progress("gauntlet", "trial_id", 88301)
    progress("forward_lab", "forward_observations", 512)

A PID alive whose watermark has not advanced beyond `max_silence_s` is STALLED -- a state of its
own, distinct from DEAD, because the repair differs: a dead organ is restarted, a stalled one is
restarted AND its fingerprint recorded, since something inside it is wedged.

MONOTONE ON PURPOSE. A counter that can go backwards cannot distinguish "did no work" from "was
restarted and forgot". A lower value is recorded as a REGRESSION (kept, counted, timestamped) and
never overwrites the high-water mark -- which is how a restarted component announces itself
without erasing the evidence that it used to be further along.

Writes are atomic (tmp + os.replace) and never raise into the caller: an organ that dies because
its telemetry failed is a worse organ than one that runs untelemetered, and the reconciler reports
a missing watermark as UNMEASURED, which is a finding.
"""
from __future__ import annotations

import contextlib
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
DESK = ROOT / "desks" / "mt5"
WATERMARK_DIR = DESK / "data" / "watermarks"

_SAFE = re.compile(r"[^A-Za-z0-9._-]+")


def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _stem(component_id: str) -> str:
    """`leg:forest_korea` -> `leg__forest_korea`. One file per component, on NTFS and ext4."""
    return _SAFE.sub("__", component_id.strip()) or "unnamed"


def path_for(component_id: str, root: Path | None = None) -> Path:
    base = WATERMARK_DIR if root is None else Path(root)
    return base / f"{_stem(component_id)}.json"


def read(component_id: str, root: Path | None = None) -> dict[str, Any] | None:
    p = path_for(component_id, root)
    try:
        doc = json.loads(p.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None
    return doc if isinstance(doc, dict) else None


def _numeric(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        with contextlib.suppress(ValueError):
            return float(value)
    return None


def progress(component_id: str, metric: str, value: Any, *, run_id: str | None = None,
             epoch_id: str | None = None, root: Path | None = None,
             **extra: Any) -> dict[str, Any]:
    """Record that `component_id` advanced `metric` to `value`. Returns the row it wrote.

    NEVER RAISES. Every failure path returns the row it would have written with `written: False`
    and a reason, so a caller that wants to know can look and a caller that does not is unharmed.
    """
    now = _now()
    prev = read(component_id, root) or {}
    prev_value = prev.get("value")
    new_n, old_n = _numeric(value), _numeric(prev_value)
    regressed = (new_n is not None and old_n is not None and new_n < old_n
                 and str(prev.get("metric")) == str(metric))
    row: dict[str, Any] = {
        "component_id": component_id,
        "metric": str(metric),
        "value": prev_value if regressed else value,
        "at": prev.get("at") if regressed else now,
        "run_id": prev.get("run_id") if regressed else run_id,
        "epoch_id": prev.get("epoch_id") if regressed else epoch_id,
        "updates": int(prev.get("updates") or 0) + 1,
        "first_seen": prev.get("first_seen") or now,
        "last_write_at": now,
        "regressions": int(prev.get("regressions") or 0) + (1 if regressed else 0),
        "last_regression": ({"from": prev_value, "to": value, "at": now, "run_id": run_id}
                            if regressed else prev.get("last_regression")),
    }
    if extra:
        row["extra"] = {**(prev.get("extra") or {}), **extra}
    p = path_for(component_id, root)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(row, indent=1, default=str), encoding="utf-8")
        os.replace(tmp, p)
        row["written"] = True
    except OSError as exc:
        row["written"] = False
        row["why"] = f"{type(exc).__name__}: {exc}"
    return row


def age_s(component_id: str, now: datetime | None = None,
          root: Path | None = None) -> float | None:
    """Seconds since this component's watermark last ADVANCED. None = never recorded."""
    row = read(component_id, root)
    if not row:
        return None
    stamp = str(row.get("at") or "")
    try:
        t = datetime.fromisoformat(stamp)
    except ValueError:
        return None
    if t.tzinfo is None:
        t = t.replace(tzinfo=UTC)
    return (now or datetime.now(tz=UTC)).timestamp() - t.timestamp()


def advancing(component_id: str, max_silence_s: int | None, now: datetime | None = None,
              root: Path | None = None) -> dict[str, Any]:
    """Is this component's work counter moving inside its SLA?

    Returns {"state": ..., "age_s": ..., "why": ...} where state is one of:
      UNMEASURED  no watermark has ever been written (a finding, never a pass)
      ADVANCING   it moved inside max_silence
      STALLED     it exists and has not moved inside max_silence
    """
    row = read(component_id, root)
    if row is None:
        return {"state": "UNMEASURED", "age_s": None,
                "why": f"no watermark file for {component_id}; nothing calls progress()"}
    a = age_s(component_id, now, root)
    if a is None:
        return {"state": "UNMEASURED", "age_s": None,
                "why": f"{component_id} watermark has no readable timestamp"}
    if max_silence_s is None:
        return {"state": "UNMEASURED", "age_s": round(a, 1),
                "why": f"{component_id} declares no cadence, so no silence window exists"}
    if a <= max_silence_s:
        return {"state": "ADVANCING", "age_s": round(a, 1), "metric": row.get("metric"),
                "value": row.get("value"), "why": ""}
    return {"state": "STALLED", "age_s": round(a, 1), "metric": row.get("metric"),
            "value": row.get("value"),
            "why": (f"{component_id} last advanced {round(a)}s ago, beyond its "
                    f"{max_silence_s}s silence window")}


def all_watermarks(root: Path | None = None) -> dict[str, dict[str, Any]]:
    base = WATERMARK_DIR if root is None else Path(root)
    out: dict[str, dict[str, Any]] = {}
    if not base.is_dir():
        return out
    for p in sorted(base.glob("*.json")):
        try:
            doc = json.loads(p.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            continue
        if isinstance(doc, dict) and doc.get("component_id"):
            out[str(doc["component_id"])] = doc
    return out
