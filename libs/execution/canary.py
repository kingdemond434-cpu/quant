"""§5 canary: prove the execution path still works BEFORE the strategy needs it.

Every 6h the desk does a minimum-notional round-trip on the most liquid pair. The point is not
the trade -- it is the discovery that keys have been revoked, the IP whitelist has drifted, the
venue has changed a filter, or latency has quietly tripled, on a schedule we choose rather than
at the moment a real signal fires.

Failure or excess latency puts the desk in DEGRADED mode for 6h: limit-only (no market orders --
if the path is sick, do not pay the spread to find out again) and -50% max size.

The critical design point is the direction of the unknown: `mode()` treats "no successful canary
on record" as degraded, not as healthy. A file that has never been written, or was deleted, or
belongs to a fresh host, must not read as a clean bill of health -- the failure mode of the
opposite choice is that a desk with a broken execution path believes it is fine indefinitely.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_STATE = Path("data/canary_state.json")

CANARY_INTERVAL_S = 6 * 3600.0
DEGRADED_S = 6 * 3600.0
# round-trip budget. Generous by design: this is a health probe, not a latency SLO, and a bar
# tight enough to trip on ordinary venue jitter would degrade the desk for noise.
MAX_LATENCY_MS = 5_000.0
DEGRADED_SIZE_MULT = 0.5
# a canary older than this is not merely due, it is evidence the runner itself is dead.
STALE_MULTIPLE = 2.0


@dataclass(frozen=True)
class CanaryMode:
    limit_only: bool
    size_multiplier: float
    reason: str

    @property
    def degraded(self) -> bool:
        return self.limit_only or self.size_multiplier < 1.0


@dataclass
class CanaryState:
    last_attempt_ts: float | None = None
    last_ok_ts: float | None = None
    last_latency_ms: float | None = None
    consecutive_failures: int = 0
    degraded_until: float = 0.0
    history: list[dict[str, Any]] = None  # type: ignore[assignment]
    path: Path = _STATE

    def __post_init__(self) -> None:
        if self.history is None:
            self.history = []

    @classmethod
    def load(cls, path: Path = _STATE) -> CanaryState:
        try:
            d = json.loads(path.read_text("utf-8"))
        except (OSError, json.JSONDecodeError):
            d = {}
        if not isinstance(d, dict):
            d = {}

        def _f(k: str) -> float | None:
            v = d.get(k)
            return float(v) if isinstance(v, (int, float)) else None

        hist = d.get("history")
        return cls(
            last_attempt_ts=_f("last_attempt_ts"),
            last_ok_ts=_f("last_ok_ts"),
            last_latency_ms=_f("last_latency_ms"),
            consecutive_failures=int(d.get("consecutive_failures", 0) or 0),
            degraded_until=float(d.get("degraded_until", 0.0) or 0.0),
            history=hist if isinstance(hist, list) else [],
            path=path,
        )

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps({
            "last_attempt_ts": self.last_attempt_ts,
            "last_ok_ts": self.last_ok_ts,
            "last_latency_ms": self.last_latency_ms,
            "consecutive_failures": self.consecutive_failures,
            "degraded_until": self.degraded_until,
            "history": self.history[-200:],
        }, indent=2), "utf-8")
        tmp.replace(self.path)

    def is_due(self, now: float) -> bool:
        return self.last_attempt_ts is None or (now - self.last_attempt_ts) >= CANARY_INTERVAL_S

    def is_stale(self, now: float) -> bool:
        """Overdue by enough that the RUNNER, not the venue, is the suspect."""
        if self.last_attempt_ts is None:
            return True
        return (now - self.last_attempt_ts) >= CANARY_INTERVAL_S * STALE_MULTIPLE

    def record(self, *, ok: bool, latency_ms: float | None, now: float,
               detail: str = "") -> CanaryMode:
        """Record one round-trip outcome and return the mode now in force."""
        self.last_attempt_ts = now
        self.last_latency_ms = latency_ms
        slow = ok and latency_ms is not None and latency_ms > MAX_LATENCY_MS
        if ok and not slow:
            self.last_ok_ts = now
            self.consecutive_failures = 0
        else:
            self.consecutive_failures += 1
            # extend, never shorten: a fresh failure inside an existing degraded window must not
            # hand back a window that expires sooner than the one already running.
            self.degraded_until = max(self.degraded_until, now + DEGRADED_S)
        self.history.append({"ts": now, "ok": bool(ok and not slow),
                             "latency_ms": latency_ms, "detail": detail[:200]})
        return self.mode(now)

    def mode(self, now: float) -> CanaryMode:
        """Current execution mode. Unknown history reads as DEGRADED, never as healthy."""
        if self.last_ok_ts is None:
            return CanaryMode(True, DEGRADED_SIZE_MULT,
                              "no successful canary on record -- unproven execution path")
        if now < self.degraded_until:
            mins = (self.degraded_until - now) / 60.0
            return CanaryMode(True, DEGRADED_SIZE_MULT,
                              f"canary failure ({self.consecutive_failures} consecutive) -- "
                              f"degraded for {mins:.0f}m more")
        if self.is_stale(now):
            hrs = (now - (self.last_attempt_ts or now)) / 3600.0
            return CanaryMode(True, DEGRADED_SIZE_MULT,
                              f"canary has not run in {hrs:.1f}h -- probe itself unproven")
        return CanaryMode(False, 1.0, "canary healthy")
