"""Information-value accounting -- judge research by UNCERTAINTY REMOVED, not alpha count.

The factory's honest success metric is not "how many strategies did we test" but "how much did
we learn per unit effort". This logs, per experiment, the EV-gate prior P(survive), the actual
outcome, and the Shannon surprise = -log2(P(observed outcome)) -- high surprise = high
information gain (a confidently-predicted result teaches little; a surprising one teaches a lot).
The running summary answers the questions that decide whether SCALING generation is worth it:

  - information gain per experiment (bits) -- is throughput buying learning or just noise?
  - distinct alpha FAMILIES explored -- is breadth growing, or are we re-drawing one pool?
  - survivor rate + forward-validated survivors -- the number that settles "scale or not".

Pure stdlib, append-only JSONL -> cheap to call from the research cycle, permanent record.
"""

from __future__ import annotations

import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_LOG = Path("data/information_value.jsonl")
_EPS = 1e-6


def surprise_bits(prior_survive: float, survived: bool) -> float:
    """Shannon surprise of the observed outcome in bits. Prior clamped to (0,1)."""
    p = min(1.0 - _EPS, max(_EPS, float(prior_survive)))
    p_obs = p if survived else (1.0 - p)
    return round(-math.log2(p_obs), 4)


def log_experiment(name: str, family: str, prior_survive: float, survived: bool,
                   *, forward_validated: bool = False, lesson: str = "",
                   log: Path = _LOG) -> dict[str, Any]:
    """Append one experiment's information record. Returns the record (incl. surprise bits)."""
    rec = {
        "ts": datetime.now(tz=UTC).isoformat(), "name": name, "family": family,
        "prior_survive": round(float(prior_survive), 4), "survived": bool(survived),
        "forward_validated": bool(forward_validated),
        "info_bits": surprise_bits(prior_survive, survived), "lesson": lesson,
    }
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")
    return rec


def record_factory_cycle(tested: int, survivors: int, *, base_prior: float = 0.15,
                         timeframe: str = "D1", log: Path = _LOG,
                         web: Path = Path("web/pilot.json")) -> dict[str, Any]:
    """Log one factory cycle's NEW candidates and refresh the pilot dashboard card.

    Each newly-tested hypothesis is scored against the desk's honest base survival rate
    (0.15); a survivor at that prior is high-surprise (high info), a reject is low. Over the
    30-day pilot this accumulates the ONE number that settles scale-or-not:
    forward-validated survivors per 1,000 + info-bits per experiment. tested is NEW-this-cycle
    (the factory dedups), so the log does not bloat after the first sweep.
    """
    fam = f"crypto_{timeframe}"
    for _ in range(max(0, survivors)):
        log_experiment("factory_survivor", fam, base_prior, True, log=log)
    for _ in range(max(0, tested - survivors)):
        log_experiment("factory_reject", fam, base_prior, False, log=log)
    s = summary(log=log)
    per_1000 = round(1000.0 * s.get("survivors", 0) / max(1, s.get("experiments", 1)), 2)
    card = {"updated": datetime.now(tz=UTC).isoformat(),
            "pilot": "factory 30-day measurement (survivors per 1,000 decides scale-or-not)",
            "survivors_per_1000": per_1000, **s}
    web.parent.mkdir(parents=True, exist_ok=True)
    web.write_text(json.dumps(card, indent=2), "utf-8")
    return card


def summary(log: Path = _LOG) -> dict[str, Any]:
    """Aggregate information-value metrics -- the scale-or-not decision numbers."""
    if not log.exists():
        return {"experiments": 0, "note": "no experiments logged yet"}
    rows = []
    for line in log.read_text("utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    n = len(rows)
    if not n:
        return {"experiments": 0, "note": "no experiments logged yet"}
    survivors = sum(1 for r in rows if r.get("survived"))
    fwd = sum(1 for r in rows if r.get("forward_validated"))
    families = sorted({r.get("family", "?") for r in rows})
    total_bits = sum(float(r.get("info_bits", 0.0)) for r in rows)
    return {
        "experiments": n,
        "survivors": survivors,
        "forward_validated_survivors": fwd,
        "survivor_rate": round(survivors / n, 4),
        "distinct_families": len(families),
        "families": families,
        "total_information_bits": round(total_bits, 2),
        "info_bits_per_experiment": round(total_bits / n, 4),
        # the scale-or-not verdict keys off DURABLE SURVIVORS, not raw info -- rejections
        # trivially accumulate bits (you learn an idea is dead), so info-bits alone would
        # wrongly reward a pure-reject run. Forward-validated survivors are the honest signal.
        "verdict_hint": (
            f"{fwd} forward-validated survivor(s) in {n} trials -- scaling generation may be "
            "EV-positive; the CPU rental is now evidence-backed" if fwd > 0
            else f"0 durable survivors in {n} trials -- throughput is re-drawing a known pool; "
            "the constraint is DATA/MECHANISM, not volume. Do NOT rent hardware yet"),
    }
