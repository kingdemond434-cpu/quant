"""The feature lifecycle: eight states, written transition rules, and one effort ruling.

    NEW -> USEFUL -> STATE_ONLY / EXECUTION_ONLY -> REDUNDANT -> DECAYING -> DEAD -> REVIVED

WHY A STATE MACHINE AND NOT A SCORE. The warehouse accumulates: every parameterisation anyone
ever tried keeps its block, and every block keeps costing compute to refresh, multiplicity to
deflate against, and attention to read past. A number beside a feature does not stop any of that
-- somebody still has to decide. So the ledger's measurement (`research/feature_roi.py`) is
turned into a STATE, and the state answers exactly one operational question through `withdraw`:
may an organ spend compute on this feature. DEAD says no, and that is what makes the principal's
"automatically stops spending effort on features that don't contribute" mechanical rather than
aspirational.

THE TRANSITIONS, WITH THEIR NUMBERS -- every one measured, none of them a judgement call:

  NEW -> USEFUL           a GAUNTLET-PASSING cell conditions on it. Certification is the desk's
                          only proof of an edge, so a feature inside a certificate is earning.
  NEW -> STATE_ONLY       no certified cell uses it, but an ADMITTED state dimension does: it
                          conditions capital without carrying a signal of its own.
  NEW -> EXECUTION_ONLY   only the execution layer reads it (fill quality, spread, timing). Real
                          value, but it must never be searched over for alpha -- that is the
                          fastest route to fitting the broker's plumbing.
  * -> REDUNDANT          another feature on the same bars spans its information: |corr| >= 0.95
                          against a single other feature, or R^2 >= 0.90 against the spanning
                          set. The information is not lost, only the second copy of it.
  * -> DECAYING           FeatureROI fell in 3 consecutive windows. A warning, not a sentence:
                          the feature still gets compute while it decays.
  * -> DEAD               FeatureROI <= 0 over its window with n >= 30. BELOW MIN_N NOTHING
                          DIES: an unmeasured feature is UNMEASURED, not worthless (L1.28a), and
                          killing on thin evidence is how a desk deletes a good feature during a
                          quiet regime.
  DEAD -> REVIVED         a named revival condition fires AND the measurement comes back positive
                          with n >= 30. Revival needs both: a reason and a number.

WHAT THIS MODULE DOES NOT DO. It does not measure. `Evidence` is handed to it already computed --
ROI, n, confidence interval, who consumes the feature, what spans it, how many windows it has
been falling. Keeping the arithmetic out means the rules above can be read, and tested, without
a ledger on disk.
"""
from __future__ import annotations

from dataclasses import dataclass, field

#: The eight states. NEW is where every block is born (`feature_store.STATUS_NEW`).
NEW = "NEW"
USEFUL = "USEFUL"
STATE_ONLY = "STATE_ONLY"
EXECUTION_ONLY = "EXECUTION_ONLY"
REDUNDANT = "REDUNDANT"
DECAYING = "DECAYING"
DEAD = "DEAD"
REVIVED = "REVIVED"

STATES: tuple[str, ...] = (NEW, USEFUL, STATE_ONLY, EXECUTION_ONLY, REDUNDANT, DECAYING, DEAD,
                           REVIVED)

#: Independent observations a FeatureROI needs before it can kill or revive anything. Below it
#: the verdict is UNMEASURED and the state does not move on ROI grounds.
MIN_N = 30
#: Consecutive falling ROI windows that make a feature DECAYING.
DECAY_WINDOWS_K = 3
#: The spanning bounds. |corr| against a single other feature, or R^2 against a set of them:
#: either one means the desk is paying twice for one column of information.
REDUNDANT_ABS_CORR = 0.95
REDUNDANT_R2 = 0.90

#: Who is reading the feature. The consumer decides which of the three "earning" states it
#: lands in, because the states are not degrees of goodness -- they are different jobs.
CONSUMER_GAUNTLET = "gauntlet_cell"
CONSUMER_STATE = "state_dimension"
CONSUMER_EXECUTION = "execution"
CONSUMERS: tuple[str, ...] = (CONSUMER_GAUNTLET, CONSUMER_STATE, CONSUMER_EXECUTION)

#: The legal edges. A transition this table does not name is a bug in the rules, not a discovery,
#: and `transition` never emits one -- `test_feature_lifecycle` pins that.
ALLOWED: dict[str, frozenset[str]] = {
    NEW: frozenset({NEW, USEFUL, STATE_ONLY, EXECUTION_ONLY, REDUNDANT, DECAYING, DEAD}),
    USEFUL: frozenset({USEFUL, STATE_ONLY, EXECUTION_ONLY, REDUNDANT, DECAYING, DEAD}),
    STATE_ONLY: frozenset({STATE_ONLY, USEFUL, EXECUTION_ONLY, REDUNDANT, DECAYING, DEAD}),
    EXECUTION_ONLY: frozenset({EXECUTION_ONLY, USEFUL, STATE_ONLY, REDUNDANT, DECAYING, DEAD}),
    REDUNDANT: frozenset({REDUNDANT, USEFUL, STATE_ONLY, EXECUTION_ONLY, DECAYING, DEAD}),
    DECAYING: frozenset({DECAYING, USEFUL, STATE_ONLY, EXECUTION_ONLY, REDUNDANT, DEAD}),
    # A DEAD feature leaves only through REVIVED: nothing gets to quietly become useful again
    # without the revival being named and measured.
    DEAD: frozenset({DEAD, REVIVED}),
    REVIVED: frozenset({REVIVED, USEFUL, STATE_ONLY, EXECUTION_ONLY, REDUNDANT, DECAYING, DEAD}),
}

#: States an organ may still spend compute on, and why the others are closed.
_EFFORT: dict[str, tuple[bool, str]] = {
    NEW: (True, "NEW: never measured, so it gets the compute that would measure it"),
    USEFUL: (True, "USEFUL: a certified cell conditions on it"),
    STATE_ONLY: (True, "STATE_ONLY: an admitted state dimension conditions capital on it"),
    EXECUTION_ONLY: (True, "EXECUTION_ONLY: the execution layer reads it -- refresh it, but "
                           "never search it for alpha"),
    REDUNDANT: (False, f"REDUNDANT: another feature on the same bars spans it "
                       f"(|corr| >= {REDUNDANT_ABS_CORR} or R^2 >= {REDUNDANT_R2}); the "
                       "information survives in the spanning feature, the second copy does not "
                       "earn its compute"),
    DECAYING: (True, f"DECAYING: ROI fell {DECAY_WINDOWS_K} windows running, but a decaying "
                     "feature is still contributing and still gets compute"),
    DEAD: (False, f"DEAD: FeatureROI <= 0 over its window with n >= {MIN_N}; effort is "
                  "withdrawn until a revival condition fires"),
    REVIVED: (True, "REVIVED: a named condition fired and the measurement came back positive"),
}


@dataclass(frozen=True)
class Effort:
    """The one operational answer a lifecycle state carries. Truthy when compute may be spent."""

    may_spend: bool
    why: str

    def __bool__(self) -> bool:
        return self.may_spend


@dataclass(frozen=True)
class Evidence:
    """Everything the rules read, measured elsewhere. Defaults are the UNMEASURED case."""

    #: FeatureROI_j = dE[logW | F_j] / (acquisition + compute + maintenance + multiplicity).
    roi: float | None = None
    #: Independent observations behind `roi`. Below MIN_N nothing dies and nothing revives.
    n: int = 0
    #: The ROI's confidence interval, reported in the WHY so a verdict is never a point estimate.
    ci: tuple[float, float] | None = None
    #: Which layers read the feature (see CONSUMERS).
    consumers: frozenset[str] = field(default_factory=frozenset)
    #: The feature whose information spans this one, and by how much.
    spanned_by: str | None = None
    max_abs_corr: float | None = None
    spanned_r2: float | None = None
    #: Consecutive windows in which FeatureROI fell.
    falling_windows: int = 0
    #: The named revival condition, when one fired. Empty means none did.
    revival: str = ""


def _ci_text(ev: Evidence) -> str:
    if ev.ci is None:
        return ""
    return f", 95% CI [{ev.ci[0]:+.6g}, {ev.ci[1]:+.6g}]"


def is_spanned(ev: Evidence) -> bool:
    """Is this feature's information already carried by others, at the stated bounds?"""
    if not ev.spanned_by:
        return False
    corr = abs(ev.max_abs_corr) if ev.max_abs_corr is not None else 0.0
    r2 = ev.spanned_r2 if ev.spanned_r2 is not None else 0.0
    return corr >= REDUNDANT_ABS_CORR or r2 >= REDUNDANT_R2


def _role(ev: Evidence) -> tuple[str, str] | None:
    """The state a feature's CONSUMERS put it in, or None when nothing reads it."""
    if CONSUMER_GAUNTLET in ev.consumers:
        return USEFUL, "a gauntlet-passing cell conditions on it"
    if CONSUMER_STATE in ev.consumers:
        return STATE_ONLY, ("an admitted state dimension conditions capital on it; no certified "
                            "cell carries it as a signal")
    if CONSUMER_EXECUTION in ev.consumers:
        return EXECUTION_ONLY, ("only the execution layer reads it; it must not be searched over "
                                "for alpha")
    return None


def transition(current: str, ev: Evidence) -> tuple[str, str]:
    """The next state and WHY, in the order the rules bind. Never emits an illegal edge.

    ORDER MATTERS AND IS DELIBERATE: revival first (it is the only way out of DEAD), then death
    (the hardest verdict, so nothing masks it), then redundancy (an alive feature can still be a
    duplicate), then decay, then the consumer's role. A feature nothing reads and nothing has
    measured stays exactly where it is -- silence is not a verdict.
    """
    cur = current if current in ALLOWED else NEW
    measured = ev.roi is not None and ev.n >= MIN_N

    if cur == DEAD:
        if ev.revival and measured and float(ev.roi or 0.0) > 0.0:
            return _guard(cur, REVIVED,
                          f"revival condition fired ({ev.revival}) and FeatureROI came back "
                          f"positive at {float(ev.roi or 0.0):+.6g} on n={ev.n}{_ci_text(ev)}")
        if ev.revival:
            return _guard(cur, DEAD,
                          f"revival condition fired ({ev.revival}) but the measurement does not "
                          f"support it yet: n={ev.n} (needs {MIN_N}), roi="
                          f"{'UNMEASURED' if ev.roi is None else format(ev.roi, '+.6g')}"
                          f"{_ci_text(ev)}")
        return _guard(cur, DEAD, f"still dead: no revival condition named (n={ev.n})")

    if measured and float(ev.roi or 0.0) <= 0.0:
        return _guard(cur, DEAD,
                      f"FeatureROI {float(ev.roi or 0.0):+.6g} <= 0 on n={ev.n} >= {MIN_N}"
                      f"{_ci_text(ev)}; effort withdrawn")

    if is_spanned(ev):
        corr = "n/a" if ev.max_abs_corr is None else f"{abs(ev.max_abs_corr):.3f}"
        r2 = "n/a" if ev.spanned_r2 is None else f"{ev.spanned_r2:.3f}"
        return _guard(cur, REDUNDANT,
                      f"spanned by {ev.spanned_by} (|corr|={corr} >= {REDUNDANT_ABS_CORR} or "
                      f"R^2={r2} >= {REDUNDANT_R2}); the information stays, the duplicate does "
                      "not earn its compute")

    if ev.falling_windows >= DECAY_WINDOWS_K:
        return _guard(cur, DECAYING,
                      f"FeatureROI fell in {ev.falling_windows} consecutive windows "
                      f"(>= {DECAY_WINDOWS_K}); still funded, but on notice")

    role = _role(ev)
    if role is not None:
        target, why = role
        if measured:
            why = f"{why}; FeatureROI {float(ev.roi or 0.0):+.6g} on n={ev.n}{_ci_text(ev)}"
        return _guard(cur, target, why)

    return _guard(cur, cur, f"unchanged: nothing reads it and n={ev.n} is below MIN_N={MIN_N} -- "
                            "UNMEASURED, which is not a verdict")


def _guard(current: str, target: str, why: str) -> tuple[str, str]:
    """Refuse an edge the table does not name, holding the current state and saying so. A rule
    that wants a new edge changes ALLOWED, in the open, rather than slipping through here."""
    if target == current:
        return current, why
    if target in ALLOWED.get(current, frozenset()):
        return target, why
    return current, (f"held at {current}: {current} -> {target} is not a legal transition "
                     f"({why})")


def withdraw(status: str) -> Effort:
    """May an organ spend compute on a feature in this state? DEAD and REDUNDANT say no.

    This is the whole point of the lifecycle: `if not withdraw(status): skip`. An unknown status
    is treated as NEW -- a feature the ledger has not judged is not thereby condemned.
    """
    may, why = _EFFORT.get(status, _EFFORT[NEW])
    if status not in _EFFORT:
        return Effort(may, f"unknown status {status!r} read as NEW: {why}")
    return Effort(may, why)
