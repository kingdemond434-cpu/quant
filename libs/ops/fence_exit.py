#!/usr/bin/env python3
"""FENCE EXIT MAPPING (L1.28a / L1.43) -- a fence that exits 0 while measuring nothing is a
false GREEN, and a false GREEN is strictly worse than no fence at all.

THE DEFECT THIS EXISTS TO END (R0237, deep sweep SYNTH0801 P1-6). Eight fences mapped status
to exit code with the same idiom::

    return 2 if rep["status"] == "DARK" else 0

That enumerates exactly ONE failing status. Every OTHER status -- including every BLIND one
(``UNMEASURED``, ``UNFORECASTING``, ``UNMEASURED-BIRTHS``) -- falls down the ``else 0`` path.
Cron, systemd, the pre-push hook and CI read ONLY the exit code, so a fence whose input had
vanished reported SUCCESS to every consumer able to act on it. L1.28a is explicit that an
unmeasured quantity counts as ZERO, never as fine; the exit map said the opposite.

THE INVERSION IS THE WHOLE FIX. Name the PASSING set; everything else fails. The property that
matters is not today's status list -- it is that a status added NEXT YEAR, by someone who never
reads this module, fails closed instead of silently joining the ``else 0`` branch. Enumerating
failures is a list that rots; enumerating passes is a list that cannot.

WHY A DECLARED PASS SET AND NOT JUST ``!= "OK"``. The model implementation at
``check_law_families.py:178`` hardcodes ``"OK"``, but the fences do not share a vocabulary:
``check_mechanism_attribution`` passes on ``ATTRIBUTED``, ``check_change_window`` on ``OPEN`` and
``STERILE``, ``check_conversion`` on ``REPAIR-MODE`` (a designed MODE signal that drives
``run_max_push``, not a failure). A blanket ``!= "OK"`` would have turned three working fences
permanently red, and a fence that is red from day one gets switched off (L1.43) -- which is how
the fix becomes the next outage. Each caller declares its own pass set, in one place, visibly.

NOT TIMIDITY, NOT LOOSENING. This module can only ever make a fence fail on MORE inputs than
before; it has no vocabulary for turning a failure into a pass. Widening a pass set is an edit
to the caller, in the diff, with a reason -- never a default.

    from libs.ops.fence_exit import fence_exit
    _PASSING = frozenset({"OK"})
    ...
    return fence_exit(rep["status"], _PASSING)

THE SECOND HALF, ADDED 2026-08-05 (L1.57). Naming the passing statuses fixed the map from status
to exit code. It cannot fix a status that is honestly ``OK`` because the fence examined NOTHING:
an empty ``rglob``, a mutated-at-import registry, ``all([])``. Pass ``scanned=`` and a passing
status over a zero denominator is refused::

    return fence_exit(rep["status"], _PASSING, scanned=len(found), of="scripts/check_*.py")

Consulted ONLY when the status was already going to pass, so this direction is one-way too --
it turns passes into failures and has no vocabulary for the reverse. Omitting ``scanned`` leaves
behaviour byte-identical and is counted against a coverage ratchet instead (L1.0/L1.43).
"""
from __future__ import annotations

from collections.abc import Iterable

#: The desk-wide "this fence failed" exit code. 2 (not 1) so a fence FAILURE stays
#: distinguishable from an interpreter/argparse error, which exits 1.
FAIL = 2


def fence_exit(status: object, passing: Iterable[str], *, fail: int = FAIL,
               scanned: object = None, of: str = "", fence: str = "") -> int:
    """Return 0 only for an explicitly declared passing status; ``fail`` for everything else.

    ``status`` is deliberately typed ``object``: a fence whose report was built from a missing
    or malformed artifact can hand us ``None``, a dict, or a status key that was never spelled.
    Every one of those is a fence that did not measure, so every one of them fails. Coercing to
    ``str`` and comparing is the point -- there is no input this function turns into a pass by
    accident.

    ``scanned`` is the DENOMINATOR of the verdict (L1.57): how many things this run actually
    examined to earn it. When declared, a passing status over a count of zero -- or over a
    non-integer, which is what a failed scope discovery hands back -- is refused. When omitted
    the exit code is unchanged and the fence is counted as UNDECLARED against the L1.57 coverage
    ratchet, so wiring is a ratchet rather than a cliff. ``of`` names what was counted, for the
    registry and the report; it is required whenever ``scanned`` is passed.
    """
    if status is None:
        return fail
    code = 0 if str(status) in frozenset(passing) else fail
    if scanned is None:
        return code
    # The verdict is computed HERE, from the arguments in hand, and never depends on the
    # registry import succeeding. Telemetry is best-effort; the refusal is not. Deciding
    # vacuity inside the try block would make an unwritable data/ silently restore the pass.
    vacuous = code == 0 and (isinstance(scanned, bool) or not isinstance(scanned, int)
                             or scanned < 1)
    try:                                   # best-effort: feeds the L1.57 coverage ratchet
        from libs.ops.denominator import caller_name, record
        record(fence or caller_name(), of or "<undeclared>", scanned, code == 0)
    except Exception:
        pass
    return fail if vacuous else code
