"""Evidence-adjustable audit thresholds -- self-tuning WITHIN HARD BOUNDS, never a free optimizer.

The audit/gate-calibration thresholds (depth-days, deploy-bar, leak-tolerance, min-sample) were
hardcoded. Hardcoded is arbitrary; a free optimizer is dangerous (it can silently loosen a gate
until it passes everything). This module is the safe middle: each threshold declares a DEFAULT, a
hard FLOOR and CEILING it can never cross, and a DIRECTION guard -- safety-critical bars are
``tighten_only`` (evidence can make them stricter, never looser). Every adjustment is clamped to the
bounds, direction-checked, and appended to an audit log; the current value persists to
``data/adaptive_thresholds.json`` and reverts to the default if the store is missing or corrupt.

This is the desk's existing "5-bps threshold is EVIDENCE-ADJUSTABLE, raise it only if..." pattern,
generalised: max ROI (metrics stop being arbitrary, self-correct toward what the evidence supports)
with the downside fenced (a bound can never be crossed, a safety bar can never be loosened).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

Direction = Literal["free", "tighten_only", "loosen_only"]


class ThresholdSpec(BaseModel):
    """One tunable threshold: its default and the hard bounds evidence can never cross."""

    model_config = ConfigDict(frozen=True)

    name: str
    default: float
    floor: float  # hard minimum -- evidence can never set below this
    ceiling: float  # hard maximum -- evidence can never set above this
    direction: Direction  # "tighten_only" = safety bar (raise-only); "loosen_only"; "free"
    tighten_is_up: bool  # True if a HIGHER value is stricter (e.g. deploy bar); False if lower is
    rationale: str


# The registry: every audit/gate-calibration threshold that may self-tune, with its safety envelope.
_REGISTRY: dict[str, ThresholdSpec] = {
    "depth_deep_days": ThresholdSpec(
        name="depth_deep_days", default=180.0, floor=90.0, ceiling=730.0,
        direction="free", tighten_is_up=True,
        rationale="days of history for an axis to count 'deep'; bounded so it can't trivialise "
                  "depth (floor) or demand impossible history (ceiling)"),
    "reject_deploy_threshold": ThresholdSpec(
        name="reject_deploy_threshold", default=0.5, floor=0.3, ceiling=2.0,
        direction="tighten_only", tighten_is_up=True,
        rationale="forward metric a reject must clear to count as 'would have paid'; tighten-only "
                  "so the gate-leak audit can never be made to cry wolf by lowering the bar"),
    "reject_leak_tolerance": ThresholdSpec(
        name="reject_leak_tolerance", default=0.10, floor=0.05, ceiling=0.25,
        direction="tighten_only", tighten_is_up=False,
        rationale="share of rejects that may pay OOS before the gate is over-strict; tighten-only "
                  "(a LOWER tolerance is stricter) so leak detection can never be dulled"),
    "reject_min_sample": ThresholdSpec(
        name="reject_min_sample", default=5.0, floor=5.0, ceiling=50.0,
        direction="tighten_only", tighten_is_up=True,
        rationale="decided rejects needed before judging the gate; raise-only, so a verdict always "
                  "rests on at least as much evidence, never less"),
}


def registry() -> dict[str, ThresholdSpec]:
    return dict(_REGISTRY)


class ThresholdBook:
    """Reader/adjuster for the persisted threshold values (bounded, direction-guarded, logged)."""

    def __init__(self, store: Path, *, log: Path | None = None) -> None:
        self.store = store
        self.log = log if log is not None else store.with_name("adaptive_thresholds_log.jsonl")

    def _load(self) -> dict[str, float]:
        try:
            raw = json.loads(self.store.read_text("utf-8"))
            return {k: float(v) for k, v in raw.items() if k in _REGISTRY}
        except Exception:
            return {}

    def get(self, name: str) -> float:
        """Current value for ``name`` -- the persisted value if present and in-bounds, else default.

        Always re-clamps to the current bounds, so a store that was hand-edited (or written under an
        older, wider bound) can never return an out-of-envelope value.
        """
        spec = _REGISTRY[name]
        val = self._load().get(name, spec.default)
        return max(spec.floor, min(spec.ceiling, val))

    def propose(self, name: str, target: float, *, reason: str) -> tuple[float, bool, str]:
        """Move ``name`` toward ``target`` within its safety envelope; return (value, changed, why).

        The move is rejected (value unchanged) if it would loosen a ``tighten_only`` bar or tighten
        a ``loosen_only`` one; otherwise it is clamped to [floor, ceiling] and persisted. Every call
        -- applied or rejected -- is appended to the log, so the tuning history is fully auditable
        and every change is reversible (set the value back; the default is always recoverable).
        """
        spec = _REGISTRY[name]
        current = self.get(name)
        clamped = max(spec.floor, min(spec.ceiling, target))
        stricter = (clamped > current) if spec.tighten_is_up else (clamped < current)
        looser = (clamped < current) if spec.tighten_is_up else (clamped > current)
        if spec.direction == "tighten_only" and looser:
            why = f"rejected: {name} is tighten-only; {clamped:g} would loosen from {current:g}"
            applied = current
            changed = False
        elif spec.direction == "loosen_only" and stricter:
            why = f"rejected: {name} is loosen-only; {clamped:g} would tighten from {current:g}"
            applied = current
            changed = False
        elif clamped == current:
            why = f"no-op: {name} already at {current:g}"
            applied = current
            changed = False
        else:
            values = self._load()
            values[name] = clamped
            self.store.parent.mkdir(parents=True, exist_ok=True)
            self.store.write_text(json.dumps(values, indent=1), "utf-8")
            why = f"applied: {name} {current:g} -> {clamped:g}"
            applied = clamped
            changed = True
        self._append_log(name, current, target, applied, changed, reason, why)
        return applied, changed, why

    def _append_log(self, name: str, before: float, target: float, after: float,
                    changed: bool, reason: str, why: str) -> None:
        from libs.core.time import to_iso8601, utcnow
        entry = {
            "ts": to_iso8601(utcnow()), "name": name, "before": before, "target": target,
            "after": after, "changed": changed, "reason": reason, "why": why,
        }
        try:
            self.log.parent.mkdir(parents=True, exist_ok=True)
            with self.log.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry) + "\n")
        except Exception:
            pass
