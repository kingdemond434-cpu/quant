"""THE PLUMBER -- watchdogs that FIX, and a hard line around what they may fix.

THE PRINCIPAL'S CORRECTION (2026-08-02): a watchdog that only alarms is a cost, not a control. It
consumes attention every cycle, produces nothing, and trains everyone to skim it. A leak found and
left open is worse than one never found, because now the desk has both the leak AND the false
comfort of having a monitor on it.

SO EVERY LEAK GETS A FIX TIER, AND NONE MAY SIT IN "WATCHED" FOREVER:

  AUTOFIX      the fix is deterministic, reversible, and lands on a surface the desk has
               DECLARED live-tunable. Applied immediately, with before/after recorded and the
               effect verified on the next cycle. If the effect is not there, it is rolled back.

  PATCH_READY  the fix is known exactly and written out, but it touches the money path or needs
               evidence the desk does not yet have. Emitted as a concrete action -- never as
               "investigate" -- escalated, and CHASED with a counter that only closing clears.

  BLOCKED      the fix cannot even be determined yet. The output is then the MEASUREMENT that
               would determine it, which is itself chased. "Unknown" is never a resting state.

WHAT A PLUMBER MUST NOT TOUCH, AND THIS IS NOT TIMIDITY. It fixes the PIPE, never the water. It
may not open, close, resize or flatten a position, and it may not loosen a risk rail -- those are
Tier-3 paths, and P22 makes the immutable core win every conflict unconditionally. The reason is
growth, not caution: an analysis organ with a bad model of the world and write access to the money
path can lose more in one cycle than the leak it was chasing costs in a year. Routing the fix to a
reversible config surface is what makes autonomous fixing SAFE ENOUGH TO DO AT ALL, which is why
this is the aggressive design rather than the careful one.

MARKET LOSSES ARE NOT LEAKS. A basis that moved against the book is the water. A leak is a defect
in the desk's own plumbing: an unrecorded fill, a stale parameter, an unpriced cost, a churn loop,
a monitor reading a file nobody writes. Conflating them is how a desk "fixes" a drawdown by
turning off the strategy that was working.

Pure, dependency-free. Applying a fix is the caller's act; this decides and records.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

__all__ = [
    "AUTOFIX",
    "BLOCKED",
    "PATCH_READY",
    "Leak",
    "LeakLedger",
    "apply_numeric_config_fix",
]

AUTOFIX = "AUTOFIX"
PATCH_READY = "PATCH_READY"
BLOCKED = "BLOCKED"

#: Surfaces the desk has DECLARED live-tunable -- edit and the running process picks it up with no
#: restart. An autofix may only ever land here. The list is explicit rather than inferred: a
#: heuristic that guessed which files were safe to write would eventually guess wrong on the one
#: that mattered, and the failure mode is a bad parameter reaching the money path.
TUNABLE_SURFACES: frozenset[str] = frozenset({
    "data/cashcarry_config.json",
})

#: Hard ceiling on how far a single autofix may move a parameter, as a fraction. A plumber that
#: can make a large change is a plumber that can cause a large accident, and the value of
#: autonomous fixing comes from doing many small correct things unattended rather than one big
#: one. Larger moves are legitimate and become PATCH_READY for a human.
MAX_AUTOFIX_STEP = 0.5


@dataclass
class Leak:
    """One defect in the desk's own plumbing, with the fix it warrants."""

    id: str
    what: str                       # the observed defect, in measured terms
    evidence: str                   # what supports it -- never a guess dressed as a finding
    tier: str                       # AUTOFIX / PATCH_READY / BLOCKED
    action: str                     # the exact fix, or the exact measurement that unblocks it
    surface: str = ""               # file the fix lands on, when there is one
    change: dict[str, Any] | None = None      # {"key": k, "from": x, "to": y} for an autofix
    verify: str = ""                # how the next cycle proves the fix worked
    #: REPO / RUNTIME / UNSCOPED -- whose fault it is, from the defect's own cited evidence.
    #: A leak resting on a MISSING GITIGNORED ARTIFACT is a fact about the machine, not the
    #: repository: data/ is gitignored, so "data/x.json absent" is true on every fresh checkout by
    #: construction and no commit can pre-satisfy it. Without this, such a leak reads as a fix the
    #: desk controls and has not made, which is a false accusation against any clone.
    scope: str = "UNSCOPED"

    def as_dict(self) -> dict[str, Any]:
        return {"id": self.id, "what": self.what, "evidence": self.evidence, "tier": self.tier,
                "action": self.action, "surface": self.surface, "change": self.change,
                "verify": self.verify, "scope": self.scope}


@dataclass
class LeakLedger:
    """Open leaks and how long each has stood. A counter that only CLOSING clears.

    Without persistence a leak that is re-detected every cycle looks like a fresh finding every
    cycle, and "we have been leaking for three weeks" is invisible -- which is exactly how a
    monitor becomes wallpaper.
    """

    cycles_open: dict[str, int] = field(default_factory=dict)
    fixed: dict[str, str] = field(default_factory=dict)

    def observe(self, leaks: list[Leak]) -> None:
        seen = {leak.id for leak in leaks}
        for lid in seen:
            self.cycles_open[lid] = self.cycles_open.get(lid, 0) + 1
        for lid in [k for k in self.cycles_open if k not in seen]:
            self.fixed[lid] = datetime.now(tz=UTC).isoformat()
            self.cycles_open.pop(lid, None)

    def age(self, lid: str) -> int:
        return int(self.cycles_open.get(lid, 0))

    def save(self, path: Path | str) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({
            "_": ("cycles each leak has stood open. Cleared ONLY by the leak disappearing -- a "
                  "counter that resets on its own lets a three-week leak look like a fresh "
                  "finding every morning, which is how a monitor becomes wallpaper."),
            "updated": datetime.now(tz=UTC).isoformat(),
            "cycles_open": dict(sorted(self.cycles_open.items())),
            "fixed": dict(sorted(self.fixed.items())),
        }, indent=1), "utf-8")

    @classmethod
    def load(cls, path: Path | str) -> LeakLedger:
        try:
            d = json.loads(Path(path).read_text("utf-8"))
            return cls({str(k): int(v) for k, v in d.get("cycles_open", {}).items()},
                       {str(k): str(v) for k, v in d.get("fixed", {}).items()})
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            return cls()


def apply_numeric_config_fix(root: Path, leak: Leak, *, dry_run: bool = False) -> dict[str, Any]:
    """Apply an AUTOFIX to a declared live-tunable config. Refuses everything else.

    FIVE REFUSALS, EACH FOR A REASON THE DESK HAS ALREADY PAID FOR ONCE:

      not AUTOFIX          a PATCH_READY leak touches the money path; applying it here would be
                           the analysis organ writing to a Tier-3 surface by the back door.
      surface not declared writing a file nobody declared tunable is writing to an unknown
                           contract; the running process may not reload it, or may reload it
                           mid-trade.
      key absent           creating a key the executor does not read is a fix that changes
                           nothing while reporting success -- the exact silent-no-op class this
                           desk keeps finding.
      step too large       small unattended corrections compound; one large one is an accident.
      value not numeric    a type the config never held is a config the executor may not parse.

    Returns what it did, including a refusal, because a refused fix is a REPORTABLE state and not
    a silent skip.
    """
    if leak.tier != AUTOFIX or not leak.change:
        return {"applied": False, "reason": f"tier {leak.tier} is not autofixable"}
    if leak.surface not in TUNABLE_SURFACES:
        return {"applied": False,
                "reason": f"{leak.surface} is not a declared live-tunable surface -- an autofix "
                          "may only ever land on one, because anything else is a contract nobody "
                          "declared reloadable"}
    path = root / leak.surface
    try:
        cfg = json.loads(path.read_text("utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        return {"applied": False, "reason": f"cannot read {leak.surface}: {e}"}

    key = str(leak.change.get("key", ""))
    new = leak.change.get("to")
    if key not in cfg:
        return {"applied": False,
                "reason": f"key '{key}' absent from {leak.surface} -- creating it would change "
                          "nothing the executor reads while reporting success"}
    old = cfg[key]
    if not isinstance(old, int | float) or not isinstance(new, int | float):
        return {"applied": False, "reason": f"'{key}' is not numeric; refusing to change its type"}
    if old and abs(float(new) - float(old)) / abs(float(old)) > MAX_AUTOFIX_STEP:
        return {"applied": False,
                "reason": f"step {old} -> {new} exceeds {MAX_AUTOFIX_STEP:.0%} -- legitimate, but "
                          "a large unattended change is an accident waiting; escalated instead"}
    if dry_run:
        return {"applied": False, "reason": "dry run", "would_change": {key: [old, new]}}

    cfg[key] = type(old)(new)
    path.write_text(json.dumps(cfg, indent=1), "utf-8")
    return {"applied": True, "surface": leak.surface, "key": key, "from": old, "to": cfg[key],
            "verify": leak.verify,
            "reversible": "single numeric key on a declared live-tunable surface; restore the "
                          "prior value to undo, no restart required"}
