"""ALERT LIFECYCLE -- an alert that nobody closes is not a control loop, it is a notification.

WHAT WAS ACTUALLY WRONG. Every ntfy path in this repo is a SENDER. `run_alerts.py` pushes to the
principal's phone, dedupes for six hours, and stops. `data/.last_alerts.json` stores when something
last fired, which is dedup state, not lifecycle. So an alert firing every six hours forever is
indistinguishable, on the phone and on disk, from one that fired once and was fixed. The desk could
not tell those apart, which means the human had to -- and that is precisely the work the principal
asked not to be doing.

THE STATES, AND WHY EACH EXISTS:

  OPEN            seen, nothing attempted yet.
  ATTEMPTED       a bounded remediation ran. NOT a claim that it worked.
  FIXED           the check was RE-RUN after the remediation and no longer fires. The only state
                  that may be reported as resolved, and it requires evidence rather than an
                  absence of complaint.
  FAILED          remediation ran and the check still fires. Escalates.
  NEEDS_HUMAN     nothing the desk can run will close it -- credits, keys, hardware, procurement.
                  Naming this class is what stops the loop retrying forever and stops the pager
                  crying about work nobody could have done.
  REGRESSED       fired again AFTER being verified fixed. Different information from a new alert:
                  it says the fix did not hold, and a system that reports it as new will keep
                  applying the same failing remediation indefinitely.

DEDUP IS NOT CLOSURE, and conflating them is the original defect. Suppressing a repeat for six
hours makes the pager quieter; it does nothing about the condition. This ledger keeps `last_seen`
for noise control and `state` for truth, and they are never the same field.

Pure stdlib. JSON persistence, because a lifecycle that dies with the process is not one.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

__all__ = [
    "OPEN_STATES",
    "STATES",
    "Alert",
    "AlertLedger",
]

STATES = ("OPEN", "ATTEMPTED", "FIXED", "FAILED", "NEEDS_HUMAN", "REGRESSED")

#: States that still demand something. FIXED is the only one that does not, and NEEDS_HUMAN is
#: deliberately in here: it is not resolved, it is merely not resolvable by the desk.
OPEN_STATES = ("OPEN", "ATTEMPTED", "FAILED", "NEEDS_HUMAN", "REGRESSED")


@dataclass
class Alert:
    """One condition, its history, and what has been tried."""

    id: str
    message: str = ""
    state: str = "OPEN"
    scope: str = "UNSCOPED"          # REPO / RUNTIME / UNSCOPED, from max_audit
    first_seen: str = ""
    last_seen: str = ""
    fixed_at: str = ""
    attempts: int = 0
    last_action: str = ""
    history: list[str] = field(default_factory=list)

    @property
    def open(self) -> bool:
        return self.state in OPEN_STATES

    def age_hours(self, now: datetime | None = None) -> float:
        if not self.first_seen:
            return 0.0
        ref = now or datetime.now(tz=UTC)
        return (ref - datetime.fromisoformat(self.first_seen)).total_seconds() / 3600.0


class AlertLedger:
    """Persistent alert lifecycle. Survives the process, which is the whole point."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.alerts: dict[str, Alert] = {}
        self._load()

    def _load(self) -> None:
        try:
            raw = json.loads(self.path.read_text("utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        for aid, d in (raw.get("alerts") or {}).items():
            known = {k: v for k, v in d.items() if k in Alert.__dataclass_fields__}
            self.alerts[aid] = Alert(id=aid, **{k: v for k, v in known.items() if k != "id"})

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({
            "updated": datetime.now(tz=UTC).isoformat(),
            "alerts": {a.id: asdict(a) for a in self.alerts.values()},
            "note": ("`last_seen` is dedup state and `state` is truth -- they are never the same "
                     "field. Suppressing a repeat makes the pager quieter and does nothing about "
                     "the condition."),
        }, indent=1), "utf-8")

    # ------------------------------------------------------------------ transitions

    def observe(self, aid: str, message: str, *, scope: str = "UNSCOPED") -> Alert:
        """Record that a condition is currently firing.

        A condition firing after it was verified FIXED is a REGRESSION, not a new alert. Reporting
        it as new would let the loop apply the same failing remediation forever while the counter
        reset each time -- the fix did not hold, and that is the fact worth carrying.
        """
        now = datetime.now(tz=UTC).isoformat()
        a = self.alerts.get(aid)
        if a is None:
            a = Alert(id=aid, message=message, scope=scope, first_seen=now, last_seen=now)
            a.history.append(f"{now} OPEN")
            self.alerts[aid] = a
            return a
        a.message, a.scope, a.last_seen = message, scope, now
        if a.state == "FIXED":
            a.state = "REGRESSED"
            a.history.append(f"{now} REGRESSED -- fired again after being verified fixed")
        return a

    def attempted(self, aid: str, action: str) -> Alert:
        a = self.alerts[aid]
        a.state = "ATTEMPTED"
        a.attempts += 1
        a.last_action = action
        a.history.append(f"{datetime.now(tz=UTC).isoformat()} ATTEMPTED {action}")
        return a

    def verify(self, aid: str, *, still_firing: bool) -> Alert:
        """Close an alert ONLY on re-run evidence.

        The distinction that matters: `still_firing` comes from executing the check again, never
        from the absence of a new report. A condition nobody re-tested is not fixed, and marking it
        so is the desk's own "not measured = fine" failure applied to its own repairs.
        """
        a = self.alerts[aid]
        now = datetime.now(tz=UTC).isoformat()
        if still_firing:
            a.state = "FAILED"
            a.history.append(f"{now} FAILED -- check re-run and still firing")
        else:
            a.state, a.fixed_at = "FIXED", now
            a.history.append(f"{now} FIXED -- verified by re-running the check")
        return a

    def needs_human(self, aid: str, why: str) -> Alert:
        """Mark what no command can close. Stops the loop retrying and the pager crying."""
        a = self.alerts[aid]
        a.state = "NEEDS_HUMAN"
        a.last_action = why
        a.history.append(f"{datetime.now(tz=UTC).isoformat()} NEEDS_HUMAN -- {why}")
        return a

    def resolve_absent(self, seen_ids: set[str]) -> list[Alert]:
        """Anything previously open and NOT observed this run has stopped firing.

        Absence is weaker evidence than a re-run, so these are marked FIXED with the reason
        recorded as such. The alternative -- leaving them open forever -- turns the ledger into a
        graveyard nobody reads, which is how the original pager failed.
        """
        out = []
        now = datetime.now(tz=UTC).isoformat()
        for a in self.alerts.values():
            if a.open and a.state != "NEEDS_HUMAN" and a.id not in seen_ids:
                a.state, a.fixed_at = "FIXED", now
                a.history.append(f"{now} FIXED -- no longer reported by the sweep")
                out.append(a)
        return out

    # ---------------------------------------------------------------------- views

    def open_alerts(self) -> list[Alert]:
        return [a for a in self.alerts.values() if a.open]

    def escalations(self, *, min_age_h: float = 24.0) -> list[Alert]:
        """What genuinely warrants the principal's attention.

        FAILED and REGRESSED always: the desk tried and could not. NEEDS_HUMAN only once it has
        aged, because paging instantly about something only a human can do -- at 3am, about a
        credit top-up -- is how a pager gets muted, and a muted pager is worse than none.
        """
        return [a for a in self.alerts.values()
                if a.state in ("FAILED", "REGRESSED")
                or (a.state == "NEEDS_HUMAN" and a.age_hours() >= min_age_h)]

    def summary(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for a in self.alerts.values():
            out[a.state] = out.get(a.state, 0) + 1
        return out
