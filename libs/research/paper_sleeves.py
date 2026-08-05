"""PAPER-SLEEVE AUTO-SPAWN LOGIC (R0102) -- every Stage-A survivor gets a forward clock, LAWFULLY.

THE GAP THIS CLOSES. A SCREEN-INTERESTING verdict that survives the annualization correction and
the campaign multiplicity bar (scripts/finalize_axis_screens.py, `verdict_adjusted`) is the desk's
scarcest research output -- and until now NOTHING converted it into a paper sleeve. Conversion was
a by-hand step, and by-hand steps run at zero when nobody is looking (the desk's most expensive
recurring defect class: built-never-wired). A paper sleeve is costless -- it tests the execution
path and accrues forward evidence, it never touches capital -- so every survivor should get one
AUTOMATICALLY.

THE CONSTRAINT THAT MAKES THIS NON-TRIVIAL (found at triage, 2026-08-05): the forward cohort is at
the Holm cap, 12/12 (libs/research/slot_registry.MAX_FORWARD_SLOTS). A naive auto-spawn would push
`over_cap` and RAISE EVERY STANDING CANDIDATE'S BAR -- each new concurrent clock tightens the Holm
correction for all of them. So the mechanism must QUEUE behind slot retirements, never spawn over
cap, and the fail-safe direction is inherited from the registry: an INCOMPLETE cohort measurement
(any unreadable source) means m is a lower bound, so free slots are treated as ZERO rather than
guessed.

QUEUE ORDER IS THE DEPLOYMENT-RACE LAW (L1.18a, same rule run_promotion_queue.py applies one stage
later): shortest capacity runway first. A long-runway edge loses nothing by waiting a month; a
short-runway edge loses everything -- arrival order systematically sacrifices exactly the edges
that cannot afford to wait. Candidates with UNKNOWN capacity sort LAST (runway inf), because an
unknown-runway edge must never jump ahead of one measurably about to expire.

Pure logic -- no I/O beyond what the caller hands in. The organ is
scripts/run_paper_sleeve_spawner.py.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from libs.research.capacity_policy import growth_runway

__all__ = [
    "Candidate",
    "decide",
    "dedupe",
    "order_queue",
    "parse_screen_verdicts",
    "slug",
    "standing_names",
]

#: The only verdict_adjusted prefix that qualifies. SCREEN-WEAK (fails the corrected 0.5 Sharpe
#: floor or the multiplicity bar) and NOT-A-CANDIDATE (controls / future-peeking diagnostics) are
#: excluded BY CONSTRUCTION -- promoting a diagnostic is the rule-8 artifact-as-edge failure.
QUALIFYING_PREFIX = "SCREEN-INTERESTING"


def slug(text: str) -> str:
    """Sleeve-safe name: lowercase, [a-z0-9_], collapsed. Deterministic so dedupe is stable."""
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", str(text).lower())).strip("_")


@dataclass(frozen=True)
class Candidate:
    """One qualifying screen survivor. `name` is the sleeve identity; `root` is the signal family
    (trial name before '->'), used for dedupe so two horizons of one signal are one sleeve."""

    name: str
    axis: str
    trial: str
    ic_t: float = 0.0
    sharpe_corrected: float = 0.0
    capacity_usd: float | None = None
    verdict: str = ""
    source: str = ""
    root: str = field(default="")

    def dedupe_keys(self) -> set[str]:
        return {k for k in (self.name, self.root, slug(self.axis)) if k}


def _capacity_of(trial: dict[str, Any]) -> float | None:
    for key in ("capacity_usd", "capacity"):
        v = trial.get(key)
        if isinstance(v, (int, float)) and math.isfinite(float(v)) and float(v) > 0:
            return float(v)
    return None


def parse_screen_verdicts(reports_dir: Path) -> dict[str, Any]:
    """Read every axis-screen report carrying corrected verdicts; return candidates + provenance.

    The verdict store is the artifact scripts/finalize_axis_screens.py writes:
    reports/axis_screens/<axis>.json with per-trial `verdict_adjusted`. Files WITHOUT that field
    are raw harness output the correction layer never processed -- they are counted as scanned but
    can qualify nothing, because the uncorrected Sharpe is inflated up to 4.47x at 20d.

    Refusal is a RESULT, not an exception: `status` is REFUSED-NO-INPUT when the store is absent
    or holds no corrected verdicts, and the caller must not spawn from it.
    """
    import json

    files_scanned, files_with_verdicts, trials_seen = [], [], 0
    candidates: list[Candidate] = []
    if reports_dir.is_dir():
        for p in sorted(reports_dir.glob("*.json")):
            try:
                doc = json.loads(p.read_text("utf-8"))
            except (OSError, ValueError):
                continue                       # unreadable file cannot qualify anything
            files_scanned.append(p.name)
            trials = doc.get("trials") if isinstance(doc, dict) else None
            if not isinstance(trials, list):
                continue
            corrected = [t for t in trials
                         if isinstance(t, dict) and isinstance(t.get("verdict_adjusted"), str)]
            if not corrected:
                continue
            files_with_verdicts.append(p.name)
            axis = str(doc.get("axis", p.stem))
            for t in corrected:
                trials_seen += 1
                if t.get("is_candidate") is False:
                    continue                   # controls / diagnostics: never promotable
                verdict = str(t["verdict_adjusted"])
                if not verdict.startswith(QUALIFYING_PREFIX):
                    continue                   # SCREEN-WEAK / NOT-A-CANDIDATE do not qualify
                trial_name = str(t.get("name", ""))
                root = slug(trial_name.split("->")[0])
                candidates.append(Candidate(
                    name=slug(f"{axis}_{trial_name}"), axis=axis, trial=trial_name,
                    ic_t=float(t.get("ic_t_stat") or 0.0),
                    sharpe_corrected=float(t.get("sharpe_best_corrected") or 0.0),
                    capacity_usd=_capacity_of(t), verdict=verdict, source=p.name, root=root))

    if not files_with_verdicts:
        return {"status": "REFUSED-NO-INPUT", "candidates": [],
                "files_scanned": files_scanned, "trials_seen": 0,
                "why": (f"{reports_dir} absent" if not reports_dir.is_dir() else
                        f"{len(files_scanned)} report(s) scanned, NONE carries verdict_adjusted "
                        "-- the correction layer (finalize_axis_screens) has not run, and raw "
                        "harness verdicts are inflated up to 4.47x at 20d, so nothing may spawn "
                        "from them")}

    # One sleeve per signal FAMILY: two horizons of one construction are one bet, and spawning
    # both would spend two Holm slots on one hypothesis. Keep the strongest ic_t deterministically.
    by_root: dict[str, Candidate] = {}
    for c in sorted(candidates, key=lambda c: (-c.ic_t, c.name)):
        by_root.setdefault(c.root or c.name, c)
    kept = sorted(by_root.values(), key=lambda c: c.name)
    return {"status": "OK" if kept else "NO-CANDIDATES", "candidates": kept,
            "files_scanned": files_scanned, "files_with_verdicts": files_with_verdicts,
            "trials_seen": trials_seen,
            "why": "" if kept else (f"{trials_seen} corrected trial(s), zero qualifying "
                                    f"{QUALIFYING_PREFIX} survivors -- the spawner being idle "
                                    "IS the correct state of this store")}


def standing_names(slots_payload: dict[str, Any], data_dir: Path,
                   queue_doc: dict[str, Any] | None = None) -> set[str]:
    """Every sleeve identity already standing -- spawning one of these again is a duplicate.

    Three sources, union'd, because each covers a failure of the others: the derived cohort
    (axis + standing + derivative clocks, the registry's own occupancy), the on-disk
    `*_shadow_state.json` files (covers a sleeve whose roster write crashed mid-spawn), and the
    queue document's own `spawned` ledger (covers a state file swept away by a data reset).
    """
    names: set[str] = set()
    for s in slots_payload.get("slots", []) if isinstance(slots_payload, dict) else []:
        if isinstance(s, dict) and s.get("name"):
            names.add(slug(str(s["name"])))
    if data_dir.is_dir():
        for p in data_dir.glob("*_shadow_state.json"):
            stem = p.name[: -len("_shadow_state.json")]
            if stem:
                names.add(slug(stem))
    for row in (queue_doc or {}).get("spawned", []):
        if isinstance(row, dict) and row.get("name"):
            names.add(slug(str(row["name"])))
    return names


def dedupe(candidates: list[Candidate],
           standing: set[str]) -> tuple[list[Candidate], list[dict[str, Any]]]:
    """Split candidates into (fresh, duplicates). A candidate whose name, signal root, or axis is
    already a standing clock is a duplicate: its hypothesis is ALREADY accruing forward evidence,
    and a second clock on it would spend a Holm slot to learn nothing new."""
    fresh, dupes = [], []
    for c in candidates:
        hit = sorted(c.dedupe_keys() & standing)
        if hit:
            dupes.append({"name": c.name, "matched_standing": hit,
                          "why": "already accruing -- a second clock on one hypothesis spends a "
                                 "Holm slot to learn nothing new"})
        else:
            fresh.append(c)
    return fresh, dupes


def runway_of(c: Candidate, book_usd: float | None = None) -> float:
    """Capacity runway in multiples of the current book; inf when capacity is UNMEASURED.

    inf is the deliberate direction: an unknown-runway candidate must never jump the queue ahead
    of one measurably about to expire, and treating unknown as short would let every capacity-less
    screen cut the line.
    """
    if c.capacity_usd is None:
        return math.inf
    return float(growth_runway(c.capacity_usd, book_usd=book_usd))


def order_queue(candidates: list[Candidate],
                book_usd: float | None = None) -> list[Candidate]:
    """Deployment-race order: SHORTEST capacity runway first (L1.18a), then strongest evidence,
    then name -- fully deterministic so two runs agree on who is next."""
    return sorted(candidates, key=lambda c: (runway_of(c, book_usd), -c.ic_t, c.name))


def free_slots(cohort: dict[str, Any]) -> tuple[int, str]:
    """(spawnable count, why). NEVER positive on an incomplete or over-cap cohort.

    The registry's fail-safe carries through: `complete=False` means some source was unreadable and
    m_concurrent is a LOWER BOUND -- spawning against a lower bound is how a cap gets breached
    while every number on screen says it was not.
    """
    cap = int(cohort.get("cap", 0))
    m = int(cohort.get("m_concurrent", cap))
    if not cohort.get("complete", False):
        return 0, ("cohort INCOMPLETE (unreadable sources: "
                   f"{cohort.get('unknown_sources')}) -- m={m} is a lower bound, so free slots "
                   "are treated as ZERO rather than guessed")
    if cohort.get("over_cap") or m >= cap:
        return 0, f"cohort at/over cap ({m}/{cap}) -- queue behind retirements, never spawn over"
    return cap - m, f"{cap - m} free slot(s) ({m}/{cap} accruing)"


def decide(candidates: list[Candidate], standing: set[str], cohort: dict[str, Any],
           book_usd: float | None = None) -> dict[str, Any]:
    """spawn-vs-queue for one run. Spawns at most the free-slot count, in runway order."""
    fresh, dupes = dedupe(candidates, standing)
    ordered = order_queue(fresh, book_usd)
    n_free, why_free = free_slots(cohort)
    spawn, queue = ordered[:n_free], ordered[n_free:]
    return {
        "spawn": spawn, "queue": queue, "duplicates": dupes,
        "free_slots": n_free, "why_free": why_free,
        "order_law": "L1.18a deployment race -- shortest capacity runway first; unknown capacity "
                     "sorts LAST (runway inf), never ahead of a measurably expiring edge",
    }
