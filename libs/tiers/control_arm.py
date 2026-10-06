"""A HELD-OUT CONTROL ARM FOR EVERY STEERING ORGAN (Tier S admission rule, 2026-09-30).

A contract that compares an organ's metric with its own EARLY readings (`contracts.evaluate`'s
baseline) cannot tell the organ's effect from the desk's drift: everything else changed too.
A control arm can. A fixed, hash-assigned share of the units an organ steers (legs for the
researcher market, genomes for the genome organ's falsify ordering) is HELD OUT -- steered by
nothing but chance -- and the organ is judged by the difference between the arms on the same
hours, under the same desk.

  in_control(unit, salt)   stable assignment: sha256(salt|unit) mod 1000 < share x 1000. The salt
                           names the organ, so arms are independent across organs.
  compare(treated, control)  Welch's t on the two arms' outcomes. ADMITTED when the treated arm
                           is better at one-sided 5%, REJECTED when it is worse at the same bar,
                           UNDECIDED between, UNMEASURED with fewer than MIN_N per arm.

Held-out units are never starved: a control leg keeps its base budget and every other price
source, and a control genome still emits its rows -- only the organ's own steering is withheld.
"""
from __future__ import annotations

import hashlib
import math
from collections.abc import Sequence
from typing import Any

SHARE = 0.2
MIN_N = 3
T_CRIT = 1.645


def in_control(unit: str, salt: str, share: float = SHARE) -> bool:
    h = int(hashlib.sha256(f"{salt}|{unit}".encode()).hexdigest()[:8], 16) % 1000
    return h < round(share * 1000)


def compare(treated: Sequence[float], control: Sequence[float],
            higher_is_better: bool = True) -> dict[str, Any]:
    t = [float(x) for x in treated if x is not None and math.isfinite(float(x))]
    c = [float(x) for x in control if x is not None and math.isfinite(float(x))]
    out: dict[str, Any] = {"n_treated": len(t), "n_control": len(c)}
    if len(t) < MIN_N or len(c) < MIN_N:
        return {**out, "verdict": "UNMEASURED",
                "why": f"fewer than {MIN_N} units in an arm"}
    mt, mc = sum(t) / len(t), sum(c) / len(c)
    vt = sum((x - mt) ** 2 for x in t) / (len(t) - 1)
    vc = sum((x - mc) ** 2 for x in c) / (len(c) - 1)
    se = math.sqrt(vt / len(t) + vc / len(c))
    delta = (mt - mc) if higher_is_better else (mc - mt)
    tstat = delta / se if se > 0 else (0.0 if delta == 0 else math.copysign(math.inf, delta))
    verdict = ("ADMITTED" if tstat >= T_CRIT else "REJECTED" if tstat <= -T_CRIT
               else "UNDECIDED")
    return {**out, "mean_treated": round(mt, 6), "mean_control": round(mc, 6),
            "delta": round(delta, 6), "t": round(tstat, 3) if math.isfinite(tstat) else tstat,
            "verdict": verdict}
