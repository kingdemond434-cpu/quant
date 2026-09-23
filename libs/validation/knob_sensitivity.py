"""KNOB SENSITIVITY -- can this protective constant change anything at all? (L1.49 family)

WHAT NO EXISTING INSTRUMENT ASKS. The desk has five instruments pointed at its own gates and
every one of them reads the gate's OUTPUT:

  * ``check_gate_reachability`` (L1.49) -- did the gate ever RUN?
  * ``check_fence_yield`` (L1.43)       -- did it ever FIRE?
  * ``check_partition_power`` (L1.63)   -- could its partition ever say NO?
  * ``check_denominators`` (L1.57)      -- did it examine anything?
  * ``check_input_provenance`` (L1.55)  -- were its inputs present?

None of them asks whether the gate's output DEPENDS on the knob that is advertised as its
protection. A knob can sit in a reachable gate that runs on every candidate, emits a row every
time, discriminates properly, reads every input successfully -- and still be mathematically
INERT, because the structure it modifies is not the structure the consumer reads. Every gauge is
green and the protection was never bought.

THE PROVING INSTANCE, measured 2026-08-19 and live for months in TWO files. ``CPCV.split()``
(``libs/validation/cpcv.py``) applies ``purge`` and ``embargo`` by discarding indices from
``CPCVSplit.train`` -- ``test`` is untouched, by construction and correctly so. Both consumers of
that splitter, ``libs/autodiscovery/validation._cpcv_positive_fraction`` and
``libs/validation/ensemble_gate._cpcv_positive_fraction``, score ``arr[s.test].mean() > 0`` and
never reference ``s.train``. Measured on a 3,000-bar AR(0.35) stream, the statistic is bit-
identical at 0.6666666667 across purge 0..500 and embargo 0.00..0.45 while the mean train slice
collapses from 2000.0 to 406.7 observations. Four docstrings across the two modules told every
reader -- and every audit -- that purge and embargo were "the difference between a real
out-of-sample reading and a leaked one". They were the difference between nothing and nothing.

THE MECHANISM GENERALISES, AND THAT IS THE POINT. A splitter, config or policy object exposes
several fields; a protective knob modifies field A; the consumer reads only field B. The knob is
then inert for that consumer no matter how correct both halves are in isolation -- neither file
is buggy, and no single-file review can see it. This is the same shape as L1.45's cycle (every
fence walked nodes, none walked edges): here every fence reads a value, none reads a DERIVATIVE.

THE TEST IS THE OBVIOUS ONE AND NOBODY RAN IT: perturb the knob across its plausible range,
re-run the consumer, and see whether the output moves.

THREE VERDICTS, and the third is load-bearing:

  LOAD_BEARING -- the output moved. The knob buys what it claims.
  DECORATIVE   -- the output is invariant across the whole range tried. The knob buys nothing.
  UNMEASURED   -- fewer than two values were comparable, or the probe raised on every value.
                  "We could not tell" is never folded into either answer (L1.28a).

DECORATIVE IS NOT AUTOMATICALLY A DEFECT, and conflating those two would make this fence
unusable. A knob that is decorative AND DECLARED SO in the code is honest -- the desk knows what
it is not buying. The defect is a decorative knob still ADVERTISED as protection, which is what
sends an auditor away satisfied. That is the same HONEST-GAP / FABRICATED split L1.55 draws over
absent inputs, and it is why ``declared_inert`` exists in the registry.

THE REPAIR IS UPWARD, ALWAYS (L1.49). A DECORATIVE reading never justifies deleting the gate or
lowering a bar -- a smaller gauntlet that runs is not an improvement on a larger one that does
not. It justifies exactly two moves: make the consumer read the structure the knob modifies, or
record out loud that this knob carries no information here and name where the real protection
lives. This module changes no threshold and grants no promotion authority.

ANTI-TIMIDITY READING, THE ENTIRE PURPOSE: a MEASUREMENT duty and a SCOPE EXPANSION. It lifts
nothing, sizes nothing, promotes nothing, opens no gate, loosens no statistical bar, and has no
vocabulary for turning a failing verdict into a passing one -- it only ever calls a probe and
compares outputs it did not produce. Its whole effect is to make "this gate is protected by a
purge" distinguishable from "this gate has a purge constant in it" -- byte-identical on this desk
until now, and only one of them is evidence.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

__all__ = ["DECORATIVE", "LOAD_BEARING", "UNMEASURED", "KnobVerdict", "measure_knob", "summarise"]

LOAD_BEARING = "LOAD_BEARING"
DECORATIVE = "DECORATIVE"
UNMEASURED = "UNMEASURED"

#: Two distinct values is the arithmetic floor for "did it move?" -- one value has nothing to
#: compare against and would resolve to DECORATIVE, which is the false-clean direction.
_MIN_VALUES = 2


@dataclass(frozen=True)
class KnobVerdict:
    """One (knob, consumer) pair, graded on what the consumer's output actually did."""

    name: str
    knob: str
    consumer: str
    status: str
    values_tried: list[Any]
    outputs: list[Any]
    #: Values whose probe raised. Counted, never silently dropped (L1.60) -- a knob range that
    #: blows the consumer up is a different fact from one it ignores.
    values_failed: list[Any] = field(default_factory=list)
    declared_inert: bool = False
    why: str = ""

    @property
    def overclaims(self) -> bool:
        """DECORATIVE while still advertised as protection -- the only failing state."""
        return self.status == DECORATIVE and not self.declared_inert

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "knob": self.knob,
            "consumer": self.consumer,
            "status": self.status,
            "values_tried": [_plain(v) for v in self.values_tried],
            "outputs": [_plain(o) for o in self.outputs],
            "values_failed": [_plain(v) for v in self.values_failed],
            "n_attempted": len(self.values_tried) + len(self.values_failed),
            "declared_inert": self.declared_inert,
            "overclaims": self.overclaims,
            "why": self.why,
        }


def _plain(value: Any) -> Any:
    """JSON-safe rendering that never invents precision it did not measure."""
    if isinstance(value, bool | int | str) or value is None:
        return value
    if isinstance(value, float):
        return round(value, 12)
    if isinstance(value, tuple | list):
        return [_plain(v) for v in value]
    return repr(value)


def measure_knob(
    probe: Callable[[Any], Any],
    values: Sequence[Any],
    *,
    name: str,
    knob: str,
    consumer: str,
    declared_inert: bool = False,
    inert_reason: str = "",
) -> KnobVerdict:
    """Run ``probe`` once per knob value and grade whether the output ever moved.

    ``probe`` must be a PURE read of the real consumer -- it exists to observe, never to stand in
    for it. A probe that re-implements the consumer measures the probe.

    Exceptions are caught per value and RECORDED (``values_failed``), never swallowed: a probe
    that raises on 4 of 6 values still yields a real verdict on the surviving 2, and hiding the
    other 4 would make a narrow measurement look like a wide one (L1.60).
    """
    outputs: list[Any] = []
    tried: list[Any] = []
    failed: list[Any] = []
    for value in values:
        try:
            outputs.append(probe(value))
            tried.append(value)
        except Exception:
            # The failure IS the datum and it is recorded on the next line -- never swallowed
            # (L1.41 condition 5, L1.60). A probe that dies on half its range still yields a
            # real verdict on the other half, and hiding the deaths would make a narrow
            # measurement read as a wide one.
            failed.append(value)

    if len(tried) < _MIN_VALUES:
        return KnobVerdict(
            name=name, knob=knob, consumer=consumer, status=UNMEASURED,
            values_tried=tried, outputs=outputs, values_failed=failed,
            declared_inert=declared_inert,
            why=(f"only {len(tried)} of {len(values)} probe value(s) returned; "
                 f"{_MIN_VALUES} are needed before 'did it move?' has an answer"),
        )

    moved = any(_differs(o, outputs[0]) for o in outputs[1:])
    if moved:
        return KnobVerdict(
            name=name, knob=knob, consumer=consumer, status=LOAD_BEARING,
            values_tried=tried, outputs=outputs, values_failed=failed,
            declared_inert=declared_inert,
            why=f"output moved across {len(tried)} value(s) of {knob}",
        )
    return KnobVerdict(
        name=name, knob=knob, consumer=consumer, status=DECORATIVE,
        values_tried=tried, outputs=outputs, values_failed=failed,
        declared_inert=declared_inert,
        why=(inert_reason if declared_inert and inert_reason else
             f"output identical at {_plain(outputs[0])} across {len(tried)} value(s) of {knob} -- "
             f"the consumer does not read the structure this knob modifies"),
    )


def _differs(a: Any, b: Any) -> bool:
    """Exact inequality. A knob that only perturbs the 15th decimal is not buying protection."""
    if isinstance(a, float) and isinstance(b, float):
        return a != b            # NaN != NaN is True, which is the honest reading of "moved"
    return bool(a != b)


def summarise(verdicts: Sequence[KnobVerdict]) -> dict[str, Any]:
    """Roll a probe set up into the fence's artifact.

    ``UNMEASURED`` on an empty roster, never OK (L1.28a): a run that compared nothing has not
    shown that anything is load-bearing.
    """
    n = len(verdicts)
    overclaimed = [v for v in verdicts if v.overclaims]
    unmeasured = [v for v in verdicts if v.status == UNMEASURED]
    bearing = [v for v in verdicts if v.status == LOAD_BEARING]
    declared = [v for v in verdicts if v.status == DECORATIVE and v.declared_inert]

    if n == 0:
        status, why = UNMEASURED, "no (knob, consumer) probes registered -- nothing was compared"
        nxt = "register at least one probe; an empty roster cannot certify a knob"
    elif overclaimed:
        status = "OVERCLAIMED"
        why = (f"{len(overclaimed)} knob(s) are inert yet still advertised as protection: "
               + ", ".join(f"{v.name} ({v.knob})" for v in overclaimed))
        nxt = ("REPAIR UPWARD (L1.49): make the consumer read the structure the knob modifies, or "
               "declare the knob inert in code and correct every docstring that claims otherwise. "
               "Deleting the gate lowers a bar and is forbidden.")
    elif unmeasured:
        status = UNMEASURED
        why = (f"{len(unmeasured)} probe(s) could not be graded: "
               + ", ".join(v.name for v in unmeasured))
        nxt = ("give each ungradeable probe two comparable knob values, "
               "or record why it cannot have them")
    else:
        status = "OK"
        why = (f"{len(bearing)} load-bearing, {len(declared)} declared-inert of {n} probe(s) -- "
               "every knob either changes its consumer's output or says out loud that it does not")
        nxt = "add the next protective constant to the roster; coverage is a ratchet (L1.0)"

    return {
        "law": "L1.49 family -- a knob whose value cannot change the output is not protection",
        "status": status,
        "n_probes": n,
        "n_load_bearing": len(bearing),
        "n_declared_inert": len(declared),
        "n_overclaimed": len(overclaimed),
        "n_unmeasured": len(unmeasured),
        "probes": [v.as_dict() for v in verdicts],
        "why": why,
        "next_action": nxt,
    }
