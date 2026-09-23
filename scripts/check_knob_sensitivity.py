#!/usr/bin/env python3
"""KNOB-SENSITIVITY FENCE (L1.49 family) -- does the protection constant change anything?

Every instrument this desk points at its own gates reads the gate's OUTPUT: did it RUN (L1.49),
did it FIRE (L1.43), could its partition say NO (L1.63), did it scan anything (L1.57), were its
inputs present (L1.55). None of them can see a gate that runs, discriminates and reads every
input successfully while the knob advertised as its protection is mathematically INERT -- because
the structure the knob modifies is not the structure the consumer reads. See
``libs/validation/knob_sensitivity`` for the mechanism and the measurement that produced it.

THE ROSTER IS HAND-BUILT AND NARROW, ON PURPOSE. L1.61's general version was refuted by its own
falsifier: an auto-discovered registry emitted hundreds of same-name-different-question pairs of
which ~all were noise, and a detector that cries wolf gets acked into silence (L1.37). A probe
earns its place by naming a REAL consumer and a REAL knob, and by being a pure read of that
consumer rather than a re-implementation of it.

STATUSES, none of which may read clean on an empty measurement set (L1.28a):
  OK           (exit 0) -- every knob either moves its consumer's output or is DECLARED inert.
  UNMEASURED   (exit 2) -- no probes, or a probe could not be graded at all.
  OVERCLAIMED  (exit 2) -- a knob is inert AND still advertised as protection. The only defect.

THE REPAIR IS UPWARD (L1.49). An OVERCLAIMED reading never justifies deleting the gate or
lowering a bar; it justifies making the consumer read the structure the knob modifies, or
declaring the knob inert in code and correcting every docstring that claims otherwise.

    python scripts/check_knob_sensitivity.py [--report-only] [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from libs.ops.fence_exit import fence_exit  # noqa: E402
from libs.ops.lawful import guard as _law_guard  # noqa: E402
from libs.validation.knob_sensitivity import KnobVerdict, measure_knob, summarise  # noqa: E402

_OUT = _ROOT / "data" / "knob_sensitivity.json"
_PASSING = ("OK",)

#: Purge is an index count and embargo a fraction of the sample, so the two ranges are swept in
#: their own units. Both span from "off" to "so aggressive it would gut the training set", which
#: is the range over which an effect could not possibly hide.
_PURGE_VALUES: tuple[int, ...] = (0, 1, 2, 50, 500)
_EMBARGO_VALUES: tuple[float, ...] = (0.0, 0.01, 0.10, 0.45)


def _stream(n: int = 3000, rho: float = 0.35, seed: int = 7) -> np.ndarray:
    """A serially-correlated return stream -- the exact case purge and embargo exist for.

    Fixed seed and fixed parameters: a probe that varies its own input cannot attribute a moved
    output to the knob. The AR coefficient is what makes this a fair test -- on an IID stream a
    purge would have nothing to remove even in a consumer that read the train set.
    """
    rng = np.random.default_rng(seed)
    innovation = rng.normal(0.0004, 0.01, n)
    out = np.zeros(n, dtype="float64")
    for i in range(1, n):
        out[i] = rho * out[i - 1] + innovation[i]
    return out


def _patched(module: Any, attr: str, value: Any, call: Any) -> Any:
    """Set a module constant, call the REAL consumer, restore. Never leaves the patch behind.

    The constants are read at call time inside the consumer's body, so this genuinely changes
    what the shipped function does -- which is the whole requirement: the probe must observe the
    consumer, not stand in for it.
    """
    original = getattr(module, attr)
    try:
        setattr(module, attr, value)
        return call()
    finally:
        setattr(module, attr, original)


def build_probes() -> list[KnobVerdict]:
    """The roster. Each entry names a shipped consumer and a constant that claims to protect it."""
    import libs.autodiscovery.validation as av
    import libs.validation.ensemble_gate as eg
    from libs.validation.revalidation import WalkForwardEngine

    arr = _stream()
    verdicts: list[KnobVerdict] = []

    # ---- the two CPCV consumers. CPCV.split() applies purge/embargo to `train` ONLY (correctly);
    # both consumers score `arr[s.test]` and never reference `s.train`, so neither constant can
    # reach the statistic. Declared inert at the definition site in both modules.
    for mod, label in ((av, "autodiscovery.validation"), (eg, "validation.ensemble_gate")):
        for attr, values, unit in (("_CPCV_PURGE", _PURGE_VALUES, "purge"),
                                   ("_CPCV_EMBARGO", _EMBARGO_VALUES, "embargo")):
            verdicts.append(measure_knob(
                lambda v, m=mod, a=attr: _patched(
                    m, a, v, lambda: m._cpcv_positive_fraction(arr)),
                values,
                name=f"{label}.cpcv[{unit}]",
                knob=f"{label}.{attr}",
                consumer=f"{label}._cpcv_positive_fraction",
                declared_inert=True,
                inert_reason=(
                    "CPCV.split() applies purge/embargo to CPCVSplit.train only; this consumer "
                    "scores arr[s.test] and never reads s.train, so the constant is inert BY "
                    "CONSTRUCTION. Declared at the definition site; the gate still measures "
                    "combinatorial sub-period consistency, which is what it is now documented as."),
            ))

    # ---- POSITIVE CONTROL. Same family, same shape, and it MUST come back LOAD_BEARING: the
    # walk-forward embargo shrinks train_end, and revalidation DOES read arr[split.train] to build
    # the IS Sharpe that feeds not_too_lucky. A run where this probe reads DECORATIVE means the
    # fence itself is broken, not that the desk got safer (the desk's own positive-control rule:
    # a gauntlet never shown to PASS a known-good input has not been validated).
    engine = WalkForwardEngine()
    verdicts.append(measure_knob(
        lambda v: round(float(engine.evaluate(
            arr, n_splits=4, test_size=300, embargo=int(v)).is_sharpe), 12),
        (0, 1, 50, 500),
        name="validation.walk_forward[embargo] (POSITIVE CONTROL)",
        knob="walk_forward_splits(embargo=)",
        consumer="revalidation.WalkForwardEngine.evaluate -> is_sharpe",
    ))
    return verdicts


def build() -> dict[str, Any]:
    rep = summarise(build_probes())
    rep["generated_at"] = datetime.now(UTC).isoformat()
    rep["probe_stream"] = {"n": 3000, "ar_rho": 0.35, "seed": 7,
                           "note": "fixed by construction; a probe that varies its own input "
                                   "cannot attribute a moved output to the knob"}
    return rep


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--report-only", action="store_true",
                    help="write the artifact and always exit 0")
    ap.add_argument("--json", action="store_true", help="print the artifact")
    args = ap.parse_args()

    rep = build()
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(rep, indent=2) + "\n", "utf-8")

    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        print(f"knob sensitivity (L1.49 family): {rep['status']} -- "
              f"{rep['n_load_bearing']} load-bearing / {rep['n_declared_inert']} declared-inert / "
              f"{rep['n_overclaimed']} overclaimed of {rep['n_probes']} probe(s)")
        for p in rep["probes"]:
            mark = {"LOAD_BEARING": "LOAD-BEARING", "DECORATIVE": "DECORATIVE  ",
                    "UNMEASURED": "UNMEASURED  "}[p["status"]]
            flag = "  <-- OVERCLAIMS" if p["overclaims"] else ""
            print(f"  {mark} {p['name']}: outputs={p['outputs']}{flag}")
            if p["values_failed"]:
                print(f"                 {len(p['values_failed'])} value(s) raised: "
                      f"{p['values_failed']}")
        print(f"  why:  {rep['why']}")
        print(f"  next: {rep['next_action']}")

    if args.report_only:
        return 0
    # Subject to L1.57: the roster size is this fence's denominator, so a run that compared
    # nothing refuses its own pass rather than reporting a clean board.
    return fence_exit(rep["status"], _PASSING, scanned=rep["n_probes"],
                      of="knob/consumer probes", fence="check_knob_sensitivity.py")


if __name__ == "__main__":
    raise SystemExit(main())
