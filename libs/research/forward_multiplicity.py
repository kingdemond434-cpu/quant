"""THE HOLM `m` COUNTS TRIALS RUN, NOT CLOCKS STILL RUNNING -- which is what the law already said.

WHY THIS MODULE EXISTS. The desk had 12 of 12 forward slots occupied, ZERO accruing, and 26
corrected Stage-A survivors queued behind the cap. The obvious repair -- retire the dead clocks so
the queue drains -- was refused, by me, on the grounds that `slot_registry.derive_slots()` drops
RETIRED rows from `m_concurrent`, so every retirement SHRINKS m and LOOSENS every standing clock's
Holm bar. That is a real mechanical fact about the implementation and it is the forbidden
direction, so automatic retirement looked unbuildable.

It is not. THE IMPLEMENTATION AND THE DECLARED LAW DISAGREED, and the implementation was the loose
one. `data/promotion_queue.json` states the design in its own words:

    "design forward window for a cohort entrant (carries the Holm correction over all
     trailing-180d entrants INCLUDING KILLED ONES)"

Including killed ones. A trial that was started and then abandoned still CONSUMED A TEST -- the
desk looked at it, and looking is what multiplicity charges for. Dropping it from m is the garden
of forking paths in its purest form: run twelve clocks, retire the eleven that disappointed, and
judge the twelfth against m=1. Nothing about that is made safe by the retirements being honest.

So the correction is computed over ENTRANTS IN THE TRAILING WINDOW, retired or not:

    m_effective = live clocks + clocks retired inside the window

which has three properties that matter, in order of importance:

  1. RETIREMENT CANNOT LOOSEN ANY BAR. Retiring a clock moves it from one term of that sum to the
     other. m is unchanged, every standing clock's threshold is unchanged, and freeing capacity
     stops being a statistical act at all. This is what makes automatic retirement safe to build.
  2. IT IS STRICTLY MORE CONSERVATIVE THAN TODAY, never less. m_effective >= m_concurrent by
     construction, and a larger m is a HIGHER bar. Adopting this can only tighten.
  3. THE CAP GOES BACK TO BEING WHAT IT IS -- a concurrency budget of 12 live clocks, a resource
     limit on how much the desk can watch at once. It stops doubling as the multiplicity, which is
     the conflation that made a full slot table look like a statistical wall.

WHAT THIS DOES NOT DO. It never lowers m below the concurrent count, it has no way to express a
window short enough to forget an inconvenient trial (WINDOW_DAYS is a module constant, matched to
the 180d the law names, and a test pins it), and it grants nothing. It is an integer and a reason.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

__all__ = ["RETIREMENT_LEDGER", "WINDOW_DAYS", "Multiplicity", "bar_for", "effective_m"]

_ROOT = Path(__file__).resolve().parents[2]

#: The Holm family window the law names. A trial started inside it is charged for, whatever
#: happened to it afterwards. NOT tunable per call: a window that can be shortened at the point of
#: use is a window that gets shortened whenever the answer is inconvenient.
WINDOW_DAYS = 180.0

#: Append-only record of every clock the desk has retired, with its birth date. This is what makes
#: a retired trial still countable -- without it, retirement really would erase the evidence that
#: the test was ever run.
RETIREMENT_LEDGER = "data/slot_retirements.jsonl"


@dataclass(frozen=True)
class Multiplicity:
    """The number of forward trials the Holm correction is over, and where each one came from."""

    m: int
    live: int
    retired_in_window: int
    complete: bool
    why: str

    @property
    def loosened_against(self) -> bool:
        """Always False by construction -- kept as a named property so callers can assert it."""
        return self.m < self.live


def _rows(path: Path) -> list[dict[str, Any]]:
    try:
        text = path.read_text("utf-8", errors="ignore")
    except OSError:
        return []
    out = []
    for line in text.splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
    return out


def retired_in_window(*, root: Path | None = None, now: datetime | None = None) -> list[str]:
    """Clocks retired whose BIRTH falls inside the window -- they still consumed a test.

    Keyed on birth, not on retirement date, and the distinction is the whole point. Keying on the
    retirement date would let a long-running trial drop out of the family the moment it was killed,
    which is the forking path this module exists to close.
    """
    base = root or _ROOT
    ref = now or datetime.now(tz=UTC)
    cutoff = ref - timedelta(days=WINDOW_DAYS)
    names = []
    for row in _rows(base / RETIREMENT_LEDGER):
        started = row.get("shadow_start") or row.get("started")
        try:
            ts = datetime.fromisoformat(str(started))
            ts = ts if ts.tzinfo else ts.replace(tzinfo=UTC)
        except (TypeError, ValueError):
            # UNKNOWN BIRTH COUNTS. An unparseable start date is not evidence that the trial was
            # outside the window, and resolving it outward would be the one direction that
            # shrinks m.
            names.append(str(row.get("name", "?")))
            continue
        if ts >= cutoff:
            names.append(str(row.get("name", "?")))
    return sorted(set(names))


def effective_m(*, root: Path | None = None, now: datetime | None = None,
                live: int | None = None, complete: bool | None = None) -> Multiplicity:
    """live clocks + clocks retired inside the window. Never less than the live count.

    `live`/`complete` may be passed to avoid re-deriving the slot table; omitted, they are read
    from slot_registry so there is still exactly one definition of what a live clock is.
    """
    base = root or _ROOT
    if live is None or complete is None:
        try:
            from libs.research.slot_registry import derive_slots
            d = derive_slots()
            live = int(d.get("m_concurrent") or 0) if live is None else live
            complete = bool(d.get("complete")) if complete is None else complete
        except (ImportError, OSError, ValueError, KeyError):
            live, complete = (live or 0), False

    gone = retired_in_window(root=base, now=now)
    m = int(live) + len(gone)
    return Multiplicity(
        m=max(m, int(live)), live=int(live), retired_in_window=len(gone), complete=bool(complete),
        why=(f"{live} live clock(s) + {len(gone)} retired inside the {WINDOW_DAYS:.0f}d window. "
             "A retired trial still consumed a test, so retiring one moves it between terms and "
             "leaves m -- and therefore every standing clock's bar -- unchanged."
             + ("" if complete else " Cohort INCOMPLETE: a source was unreadable, so this is a "
                                    "LOWER bound and the true bar may be higher.")))


def bar_for(rank: int = 1, *, root: Path | None = None, now: datetime | None = None,
            alpha: float = 0.05) -> dict[str, Any]:
    """The Holm z threshold at the effective m, alongside the concurrent-only one it replaces.

    Both are reported so the direction of the change is visible on every run rather than asserted
    once in a docstring. `at_least_as_strict` is the property that must hold forever.
    """
    from libs.validation.forward_stats import holm_bar

    mult = effective_m(root=root, now=now)
    z_eff = float(holm_bar(max(1, mult.m), rank, alpha=alpha))
    z_live = float(holm_bar(max(1, mult.live), rank, alpha=alpha))
    return {
        "m_effective": mult.m, "m_concurrent_only": mult.live,
        "retired_in_window": mult.retired_in_window,
        "z": z_eff, "z_if_only_live_counted": z_live,
        "at_least_as_strict": z_eff >= z_live,
        "complete": mult.complete,
        "why": mult.why,
        "law": "Holm over all trailing-180d entrants INCLUDING KILLED ONES "
               "(data/promotion_queue.json). Counting only the survivors would judge the last "
               "clock standing against m=1 after eleven looks.",
    }
