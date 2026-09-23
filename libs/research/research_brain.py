"""ResearchBrain: does a change to the research system actually DISCOVER more?

THE QUESTION NOTHING ELSE HERE ANSWERS. Every other fence asks whether an organ ran, whether an
artifact is fresh, whether a candidate passed. None asks the only question that decides whether a
research-system change was worth making: did the desk, given the same information and the same
compute, produce MORE THINGS THAT LATER CASHED? Without it a repo can grow indefinitely more
sophisticated while its discovery quietly gets worse, and every added layer looks like progress
because it runs.

That failure mode is not hypothetical here. Today alone eight organs ran clean, exited 0, returned
plausible numbers and did nothing -- four of them written the same day to fix the other four. Every
one would have passed a "is it wired?" check. The only thing that separates a real improvement
from a busy one is out-of-sample yield, measured later, against a brain that did not have the
change.

THE PROTOCOL, AND WHY EACH CONSTRAINT IS THERE.

  * INFORMATION CUTOFF. Each brain sees data only up to T. A brain that can see past T will find
    edges after T, and will look brilliant for a reason that has nothing to do with its design.
  * FIXED BUDGET. Same candidate budget and the same compute. Otherwise "better" means "ran
    longer", which is a purchase and not an improvement.
  * FROZEN OUTPUT. Each brain's candidates are frozen at T with a content hash, BEFORE any
    evaluation. Nothing may be added, dropped or re-ranked afterwards -- that is the same
    pre-registration rule this desk applies to forward clocks, for exactly the same reason.
  * JUDGED LATER, ON DATA NOBODY SAW. Scoring happens at T+k using the canonical gates and real
    forward evidence. A brain is never scored on the in-sample metrics it optimised.

THE SCORE. Independent future survivors x their contribution to E[log W], per unit of effective
trials and compute:

    score = (survivors x delta_elog) / (effective_trials x compute)

INDEPENDENT is load-bearing. Twenty survivors that are one trade wearing twenty names are worth
one, and this desk has measured that exact failure: 97% of a free-optimum book in a single
mechanism, seven sleeves sharing a 01:00 fill hour whose pairwise daily correlation was low enough
to hide it. Survivors are counted after collapsing correlated ones.

EFFECTIVE TRIALS is load-bearing too. A brain that proposes ten thousand cells and gets three
survivors has not beaten one that proposed thirty and got two -- deflation charges the width, and
so does this.

NOTHING HERE PROMOTES. The harness writes a comparison. It never certifies a candidate, never
retires a brain, and never changes what the desk trades: it produces the evidence a principal
needs to decide whether a change earned its place.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]
ARENA = _ROOT / "desks" / "mt5" / "data" / "research_brains"

#: Correlation above which two survivors are ONE finding for scoring. Deliberately strict: the
#: desk's measured concentration failure hid behind low pairwise DAILY correlation while every
#: sleeve shared a fill hour, so anything looser would reproduce it.
INDEPENDENCE_CORR = 0.5


@dataclass(frozen=True)
class BrainRun:
    """One brain's frozen output at an information cutoff. Immutable after `freeze`."""

    brain: str
    cutoff: str
    candidates: tuple[dict[str, Any], ...]
    effective_trials: int
    compute_seconds: float
    config: dict[str, Any] = field(default_factory=dict)
    frozen_at: str = ""
    content_hash: str = ""

    def compute_hash(self) -> str:
        blob = json.dumps(
            {"brain": self.brain, "cutoff": self.cutoff,
             "candidates": [dict(sorted(c.items())) for c in self.candidates],
             "effective_trials": self.effective_trials},
            sort_keys=True, default=str)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:20]


def freeze(brain: str, cutoff: str, candidates: list[dict[str, Any]],
           effective_trials: int, compute_seconds: float,
           config: dict[str, Any] | None = None) -> BrainRun:
    """Freeze a brain's output at its cutoff, hashed. Refuses to overwrite an existing freeze.

    PRE-REGISTRATION, NOT BOOKKEEPING. A frozen run that can be rewritten after the outcome is
    known is not evidence about a research system, it is a story about one. Refusing the
    overwrite is the same rule the forward clocks live under, and for the same reason.
    """
    run = BrainRun(brain=brain, cutoff=cutoff, candidates=tuple(candidates),
                   effective_trials=int(effective_trials),
                   compute_seconds=float(compute_seconds), config=config or {},
                   frozen_at=datetime.now(UTC).isoformat(timespec="seconds"))
    run = BrainRun(**{**run.__dict__, "content_hash": run.compute_hash()})
    ARENA.mkdir(parents=True, exist_ok=True)
    path = ARENA / f"{brain}_{cutoff.replace(':', '').replace('-', '')}.json"
    if path.exists():
        existing = json.loads(path.read_text("utf-8"))
        if existing.get("content_hash") != run.content_hash:
            raise FileExistsError(
                f"{path.name} is already frozen with a different hash. A pre-registration may "
                f"not be rewritten after the fact; use a new cutoff or a new brain name.")
        return run
    path.write_text(json.dumps(run.__dict__, indent=1, default=str), encoding="utf-8")
    return run


def independent_count(survivors: list[dict[str, Any]],
                      corr: dict[tuple[str, str], float] | None = None) -> int:
    """Survivors after collapsing correlated ones. Twenty names for one trade count as one.

    Falls back to counting distinct (mechanism, symbol-family) pairs when no correlation matrix
    is supplied -- coarser, and it errs toward UNDER-counting, which is the safe direction for a
    score that decides whether a research change earned its place.
    """
    if not survivors:
        return 0
    if corr:
        keys = [str(s.get("id") or s.get("cell") or i) for i, s in enumerate(survivors)]
        kept: list[str] = []
        for k in keys:
            if all(abs(corr.get((k, j), corr.get((j, k), 0.0))) < INDEPENDENCE_CORR
                   for j in kept):
                kept.append(k)
        return len(kept)
    seen = {(str(s.get("mechanism") or "?"), str(s.get("symbol") or "?")) for s in survivors}
    return len(seen)


def score(run: dict[str, Any], survivors: list[dict[str, Any]], delta_elog: float,
          corr: dict[tuple[str, str], float] | None = None) -> dict[str, Any]:
    """Score a frozen run on evidence from AFTER its cutoff. Never on its own metrics."""
    n_ind = independent_count(survivors, corr)
    trials = max(1, int(run.get("effective_trials") or 1))
    compute = max(1e-6, float(run.get("compute_seconds") or 1.0) / 3600.0)
    value = n_ind * float(delta_elog)
    return {
        "brain": run.get("brain"),
        "cutoff": run.get("cutoff"),
        "content_hash": run.get("content_hash"),
        "candidates_frozen": len(run.get("candidates") or []),
        "survivors_raw": len(survivors),
        "survivors_independent": n_ind,
        "delta_elog": round(float(delta_elog), 8),
        "effective_trials": trials,
        "compute_hours": round(compute, 4),
        "score": round(value / (trials * compute), 12),
        "note": ("survivors x delta_elog per effective trial per compute hour. Independent "
                 "survivors only: correlated ones are one finding. Scored on evidence from after "
                 "the cutoff, never on the metrics the brain optimised."),
    }


def compare(scored: list[dict[str, Any]]) -> dict[str, Any]:
    """Rank scored brains and state the verdict plainly, including when there isn't one."""
    if not scored:
        return {"verdict": "UNMEASURED", "why": "no scored runs"}
    ranked = sorted(scored, key=lambda r: -float(r.get("score") or 0.0))
    best, rest = ranked[0], ranked[1:]
    if not rest:
        return {"verdict": "UNMEASURED", "ranked": ranked,
                "why": ("one brain cannot beat anything. A change is only demonstrated against "
                        "the version that lacks it, on the same cutoff and budget.")}
    margin = float(best["score"]) - float(rest[0]["score"])
    # A brain with zero independent survivors has not won; it has tied at nothing.
    if int(best.get("survivors_independent") or 0) == 0:
        verdict = "UNMEASURED"
        why = ("the top brain produced no independent survivor after its cutoff. Nothing was "
               "discovered, so nothing is demonstrated -- absence is not a win (L1.28a).")
    elif margin <= 0:
        verdict = "TIED"
        why = "no brain separated from the next on out-of-sample yield per trial per hour."
    else:
        verdict = "IMPROVED"
        why = (f"{best['brain']} beat {rest[0]['brain']} by {margin:.3g} on independent "
               f"survivors x delta_elog per effective trial per compute hour.")
    return {"verdict": verdict, "why": why, "winner": best["brain"], "ranked": ranked,
            "rule": ("A research-system change is accepted only when it beats the incumbent brain "
                     "on LATER, UNSEEN survivor production. Running is not improving.")}


def arena() -> dict[str, Any]:
    """Every frozen run, for the health fences."""
    ARENA.mkdir(parents=True, exist_ok=True)
    runs = []
    for p in sorted(ARENA.glob("*.json")):
        try:
            d = json.loads(p.read_text("utf-8"))
        except (OSError, ValueError):
            continue
        runs.append({"brain": d.get("brain"), "cutoff": d.get("cutoff"),
                     "candidates": len(d.get("candidates") or []),
                     "effective_trials": d.get("effective_trials"),
                     "content_hash": d.get("content_hash")})
    return {"n_runs": len(runs), "runs": runs, "arena": str(ARENA)}
