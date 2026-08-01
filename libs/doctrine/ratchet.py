"""THE AGGRESSION RATCHET -- a constitutional principle may be strengthened, never weakened.

WHY A MECHANISM AND NOT A PROMISE. Institutions do not decide to become timid. They drift there
one reasonable-sounding amendment at a time, each defensible in isolation, and the sum is a desk
that compounds slower while every individual decision looked prudent. A rule against that has to
have TEETH or it is just another sentence in a document nobody diffs.

HOW IT WORKS. Every principle carries an integer `aggression`. This module keeps a HIGH-WATER MARK
on disk that is only ever RAISED automatically: strengthen a principle and the mark follows it up
on the next run, with no ceremony at all. Lower one and the mark stays where it was, the check
fails, and the only way to proceed is to hand-edit a file called CONSTITUTION_RATCHET.json -- a
deliberate, dated, reviewable act.

WHAT IT CANNOT DO, STATED PLAINLY BECAUSE A CONTROL THAT OVERSTATES ITSELF IS WORSE THAN NONE. It
cannot detect a statement whose WORDS are watered down while its integer stays put. No test can;
that is a semantic judgement. `constitution.weakening_language()` catches the accidental kind by
vocabulary and will miss a determined one. The ratchet's actual claim is narrower and still worth
having: weakening the constitution cannot happen by accident, cannot happen silently, and cannot
happen without a diff that says exactly what was given up.

DELETION IS WEAKENING. A principle that disappears is scored as its aggression dropping to zero,
because "we removed the rule" is the strongest possible form of relaxing it and would otherwise be
the trivial way around the whole mechanism.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from libs.doctrine.constitution import PRINCIPLES, aggression_map

__all__ = [
    "BASELINE_PATH",
    "RatchetReport",
    "check",
    "load_baseline",
    "update_high_water",
]

BASELINE_PATH = Path("docs/research/CONSTITUTION_RATCHET.json")


@dataclass(frozen=True)
class RatchetReport:
    ok: bool
    violations: list[str]
    raised: list[str]
    baseline: dict[str, int]


def load_baseline(path: Path | str = BASELINE_PATH) -> dict[str, int]:
    """Missing file means NO history, not a clean slate at zero.

    Returning an empty mark is correct here and is not a fail-open: with no recorded history there
    is nothing to have regressed FROM, and the first run writes the current values as the mark. A
    deleted baseline is caught by the audit as a missing artifact, which is the right layer for
    that -- this function's job is to read, not to infer motive.
    """
    try:
        d = json.loads(Path(path).read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    marks = d.get("high_water", d)
    return {str(k): int(v) for k, v in marks.items() if isinstance(v, int | float)}


def check(current: dict[str, int] | None = None,
          baseline: dict[str, int] | None = None) -> RatchetReport:
    """Compare the constitution as it stands against the high-water mark."""
    cur = dict(current if current is not None else aggression_map())
    base = dict(baseline if baseline is not None else load_baseline())

    violations, raised = [], []
    for pid, mark in sorted(base.items()):
        now = cur.get(pid)
        if now is None:
            violations.append(
                f"{pid}: DELETED. A principle that disappears is that principle relaxed to zero "
                f"-- it stood at aggression {mark}. Restore it or state the argument in "
                f"{BASELINE_PATH.name}.")
        elif now < mark:
            violations.append(
                f"{pid}: aggression {mark} -> {now}. The constitution may be strengthened "
                "freely; weakening it requires a deliberate hand-edit of the high-water mark "
                "with a dated reason. This is the ratchet doing its only job.")
        elif now > mark:
            raised.append(f"{pid}: {mark} -> {now}")
    for pid, now in sorted(cur.items()):
        if pid not in base:
            raised.append(f"{pid}: NEW at {now}")
    return RatchetReport(not violations, violations, raised, base)


def update_high_water(path: Path | str = BASELINE_PATH,
                      current: dict[str, int] | None = None) -> dict[str, int]:
    """Raise the mark to match any strengthened principle. NEVER lowers anything.

    This asymmetry is the whole design: strengthening is frictionless so nobody is discouraged
    from doing it, and weakening is impossible through this path so it has to be argued for
    somewhere a reviewer will see it.
    """
    cur = dict(current if current is not None else aggression_map())
    base = load_baseline(path)
    new = {pid: max(int(cur.get(pid, 0)), int(base.get(pid, 0))) for pid in set(base) | set(cur)}
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({
        "_": ("HIGH-WATER MARK for constitutional aggression. Raised automatically; NEVER "
              "lowered by code. Editing a number DOWN in this file is the only way to weaken a "
              "principle, and it is meant to be a visible, dated, argued act -- institutions "
              "drift toward timidity one reasonable amendment at a time, and this is the "
              "mechanism that makes each one cost a decision."),
        "updated": datetime.now(tz=UTC).isoformat(),
        "principles": {p_.id: p_.name for p_ in PRINCIPLES},
        "high_water": dict(sorted(new.items())),
    }, indent=1), "utf-8")
    return new
