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



#: Prior used only when the desk has NO recorded history to learn one from. Labelled everywhere it
#: is used, because an unlearned prior is an assumption and must never be mistaken for a rate.
COLD_START_PRIOR = 0.15

#: Laplace smoothing on the empirical prior. Without it, a desk with 0 survivors in 420 attempts
#: derives a prior of exactly 0.0, every rejection becomes ZERO-surprise, and the accounting says
#: the desk learns nothing from any outcome -- including, absurdly, from a survivor.
_PRIOR_ALPHA = 1.0
_PRIOR_BETA = 1.0


def empirical_prior(log: Path = _LOG) -> tuple[float, str]:
    """P(survive) learned from the desk's OWN record, not asserted.

    THE DEFECT THIS CLOSES (triage #39, and its own note misdiagnoses it). `info_bits` was a
    constant 0.2345 across all 810 rows, filed as "the estimator is DEAD -- repair it". The
    estimator was never broken: 0.2345 is exactly -log2(0.85), so every caller was passing the
    same hardcoded prior of 0.15. A prior that never updates produces identical surprise for every
    outcome, which makes `total_bits` precisely `n x 0.2345` -- a ROW COUNT wearing an
    information-theory unit. Third instance this session of a counter dressed as evidence, after
    §33's min_snapshots and the allocator's closure-rate n.

    Worse than merely constant: the desk's measured record is 420/420 rejections, so scoring each
    rejection against a 0.15 prior books it as mildly SURPRISING when it is exactly what should be
    expected. The accounting overstated learning in the one direction that flatters the desk.
    """
    rows = _rows(log)
    if not rows:
        return COLD_START_PRIOR, ("COLD START: no experiments logged, so this is an ASSUMPTION "
                                  "rather than a rate. It is labelled as such wherever it appears.")
    surv = sum(1 for r in rows if r.get("survived"))
    n = len(rows)
    p = (surv + _PRIOR_ALPHA) / (n + _PRIOR_ALPHA + _PRIOR_BETA)
    return round(p, 6), (f"EMPIRICAL: {surv} survivor(s) in {n} logged experiment(s), "
                         f"Laplace-smoothed to {p:.4f}. Smoothed because an unsmoothed 0/{n} gives "
                         "a prior of exactly zero, under which every rejection is ZERO-surprise "
                         "and the desk is recorded as learning nothing from any outcome.")


def _rows(log: Path) -> list[dict[str, Any]]:
    if not log.exists():
        return []
    out = []
    for line in log.read_text("utf-8", errors="ignore").splitlines():
        line = line.strip()
        if line:
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def record_factory_cycle(tested: int, survivors: int, *, base_prior: float | None = None,
                         timeframe: str = "D1", log: Path = _LOG,
                         web: Path = Path("web/pilot.json")) -> dict[str, Any]:
    """Log one factory cycle's NEW candidates and refresh the pilot dashboard card.

    Each newly-tested hypothesis is scored against the desk's honest base survival rate
    (0.15); a survivor at that prior is high-surprise (high info), a reject is low. Over the
    30-day pilot this accumulates the ONE number that settles scale-or-not:
    forward-validated survivors per 1,000 + info-bits per experiment. tested is NEW-this-cycle
    (the factory dedups), so the log does not bloat after the first sweep.
    """
    # LEARNED, NOT ASSERTED. `base_prior=None` derives P(survive) from the desk's own logged
    # record; an explicit value is still honoured so a caller can score against a stated
    # counterfactual, but the DEFAULT no longer hardcodes a rate the desk has measured to be wrong.
    prior_why = "caller-supplied prior"
    if base_prior is None:
        base_prior, prior_why = empirical_prior(log)
    fam = f"crypto_{timeframe}"
    for _ in range(max(0, survivors)):
        log_experiment("factory_survivor", fam, base_prior, True, log=log)
    for _ in range(max(0, tested - survivors)):
        log_experiment("factory_reject", fam, base_prior, False, log=log)
    s = summary(log=log)
    per_1000 = round(1000.0 * s.get("survivors", 0) / max(1, s.get("experiments", 1)), 2)
    card = {"updated": datetime.now(tz=UTC).isoformat(),
            "pilot": "factory 30-day measurement (survivors per 1,000 decides scale-or-not)",
            "survivors_per_1000": per_1000,
            # THE PRIOR AND ITS PROVENANCE TRAVEL WITH THE NUMBER. info_bits is meaningless
            # without knowing what it was surprised RELATIVE TO -- and reporting bits against an
            # unstated prior is how 810 identical values read as accumulated information.
            "prior_used": round(float(base_prior), 6), "prior_basis": prior_why, **s}
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
