"""Process watchdog and safe-halt orchestration (fail-closed).

The watchdog turns heartbeat silence into a restart recommendation; the safe-halt controller
fuses the platform's hard stop signals (reconciliation divergence, drawdown HALT level, heartbeat
loss, unresolved critical alerts) into a single deterministic halt decision. It recommends the
halt — the execution/risk layer enforces it — so this stays a pure, auditable decision function.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from libs.risk.drawdown import DrawdownLevel


class ProcessWatchdog:
    """Heartbeat liveness: recommends a restart when a process goes silent too long."""

    def __init__(self, *, max_silence_seconds: float) -> None:
        self.max_silence_seconds = max_silence_seconds

    def alive(self, *, last_beat_epoch: float, now_epoch: float) -> bool:
        return (now_epoch - last_beat_epoch) <= self.max_silence_seconds

    def action(self, *, last_beat_epoch: float, now_epoch: float) -> str:
        alive = self.alive(last_beat_epoch=last_beat_epoch, now_epoch=now_epoch)
        return "ok" if alive else "restart"


class HaltDecision(BaseModel):
    model_config = ConfigDict(frozen=True)

    halt: bool
    reasons: list[str] = Field(default_factory=list)


class SafeHaltController:
    """Fuses hard stop signals into one fail-closed halt decision (recommend-only)."""

    def evaluate(
        self,
        *,
        reconciliation_divergence: bool = False,
        drawdown_level: DrawdownLevel = DrawdownLevel.NORMAL,
        heartbeat_alive: bool = True,
        critical_alerts: int = 0,
    ) -> HaltDecision:
        reasons: list[str] = []
        if reconciliation_divergence:
            reasons.append("reconciliation divergence")
        if drawdown_level is DrawdownLevel.HALT:
            reasons.append("drawdown governor at HALT")
        if not heartbeat_alive:
            reasons.append("heartbeat lost")
        if critical_alerts > 0:
            reasons.append(f"{critical_alerts} unresolved critical alert(s)")
        return HaltDecision(halt=bool(reasons), reasons=reasons)
