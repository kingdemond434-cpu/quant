"""THE COMMITTEE ENGINE: deterministic specialist ensembles that challenge, never decide.

Principal's ruling 2026-09-30 17:04: the six committees are Python specialist ensembles, not
conversational agents. Every specialist returns a TYPED result -- PASS / FAIL / UNMEASURED, a
strength, a failure class, its evidence, the test it recommends next, the information that test
would buy and what it costs -- and Python, not a vote, chooses the next experiment. LLMs stay
outside as optional idea miners and never sit here.

A COMMITTEE HAS NO AUTHORITY. It never certifies, allocates, sizes or trades. Its products are
challenges (a failure class with its evidence), the experiments that would settle them, a
falsification tree per subject and a health report. The gauntlet certifies, the allocator
allocates, the gateway trades, live evidence judges everybody -- this engine included.

WHAT THE ENGINE OWNS, so every committee gets it without re-spelling it:

  * TRIGGERS AND ESCALATION L0..L4. A committee only examines a subject when its trigger fires
    (new, changed, or due for re-measurement). Each subject starts at its trigger's level and
    climbs one level at a time, only while the level it is on leaves it unresolved: any FAIL
    that is not decisive, any disagreement between specialists, or nothing measured.
  * DYNAMIC SEAT SELECTION. Inside a level, seats run in order of expected information per
    second -- the binary entropy of the seat's calibrated FAIL rate over its declared cost --
    until the level's budget is spent. A retired seat never sits.
  * EVIDENCE PARTITIONING. A subject carries its evidence split by partition (mechanism,
    statistics, execution, provenance, pnl, ...). A seat is handed ONLY its own partition, so
    two seats that agree agree from partly independent views, which is what makes agreement
    informative.
  * CALIBRATION. Every FAIL/PASS is a probability claim; `settle()` scores it against the
    later outcome (a hypothesis-graph fate, or the same seat re-measuring on strictly newer
    data) with a Brier score per seat. A seat that says 0.95 and is right 55% of the time
    loses rank in seat selection automatically.
  * MINORITY REPORTS. When measured seats split, the losing side is written down with its
    evidence rather than averaged away.
  * OBJECTION -> EXPERIMENT. Every FAIL and UNMEASURED names the test that would settle it; the
    compiler turns those into de-duplicated experiments and the ranker orders them by
    information gain per second.
  * FALSIFICATION TREES. Per subject: the claim at the root, one branch per failure class
    raised, each branch carrying its ranked experiments and what was already measured.
  * CROSS-COMMITTEE CONTRADICTIONS. Two committees ruling opposite ways on the same key and
    the same failure class is itself a finding.
  * PLANTED TRAPS. Every seat ships a synthetic subject carrying exactly the defect it exists
    to catch (and, where it can, a clean twin). The engine runs them every pass: a seat that
    misses its own trap is BROKEN, a seat that fails its clean twin raises false alarms.
  * OVERLAP, ABLATION, ROI AND RETIREMENT. Pairwise overlap of FAIL sets, the catches only one
    seat made, and the cost of each. A seat with enough observations that never catches
    anything another cheaper seat did not also catch is RETIRED with its reason; UNMEASURED
    never retires anything (L1.28a).
"""
from __future__ import annotations

import hashlib
import json
import math
import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

PASS, FAIL, UNMEASURED = "PASS", "FAIL", "UNMEASURED"
VERDICTS: tuple[str, ...] = (PASS, FAIL, UNMEASURED)
LEVELS: tuple[int, ...] = (0, 1, 2, 3, 4)
#: A FAIL at or above this strength settles the subject at its level; below it, the committee
#: climbs to look harder rather than stop on a weak objection.
DECISIVE = 0.8
#: Measured PASSes settle a level only when at least one is this strong; a weak pass (a cheap
#: screen that found nothing) invites the next level rather than closing the question.
CONFIDENT = 0.6
#: Retirement evidence floor: a seat is judged for redundancy only after this many measurements
#: inside the window.
MIN_OBS_FOR_RETIREMENT = 60
#: THE RETIREMENT RULE (CRO D27): a seat whose ablation value -- the subjects only it objected
#: to -- is zero or less over this many days of measurement retires. A shorter history never does.
RETIRE_WINDOW_DAYS = 14
#: A retired seat still sits on one subject in this many (chosen by the subject's fingerprint,
#: so the probe sample is stable and unbiased by the seat); a unique catch inside the window
#: re-opens it.
PROBE_EVERY = 20
#: Traps: a seat that catches fewer than this share of its own traps is BROKEN.
TRAP_FLOOR = 0.8
#: Open calibration claims kept; the oldest leave first.
MAX_PENDING = 50000


def now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def sha(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()[:16]


@dataclass(frozen=True)
class Result:
    """What one specialist says about one subject. Typed, so nothing can be said in prose only."""

    specialist: str
    verdict: str
    strength: float = 0.0            # 0..1: how decisive the measurement is, not a vote
    failure_class: str = ""
    evidence: Mapping[str, Any] = field(default_factory=dict)
    recommended_test: str = ""
    info_gain: float = 0.0           # expected bits the recommended test would buy
    cost_s: float = 0.0              # measured seconds this result cost
    probes: str = ""                 # the failure class the seat tests, whatever it found

    def row(self) -> dict[str, Any]:
        return {"specialist": self.specialist, "verdict": self.verdict,
                "strength": round(float(self.strength), 4), "failure_class": self.failure_class,
                "evidence": dict(self.evidence), "recommended_test": self.recommended_test,
                "info_gain": round(float(self.info_gain), 4), "cost_s": round(self.cost_s, 4),
                "probes": self.probes}


@dataclass
class Subject:
    """One thing a committee examines. `evidence` is keyed by partition."""

    committee: str
    key: str                                   # stable identity across passes
    evidence: dict[str, Any]
    keys: dict[str, str] = field(default_factory=dict)   # cross-committee join keys
    trigger: str = "new"
    level: int = 0
    claim: str = ""

    def fingerprint(self) -> str:
        """Hash what is cheap to hash: a Lazy partition is identified by the stamps beside it."""
        return sha({k: (None if isinstance(v, Lazy) else v) for k, v in self.evidence.items()})


class Lazy:
    """Evidence that costs something to load (bars, a built cell): loaded once, on first use,
    by the first seat that needs it -- so a subject settled at L0 never pays for L1's frame."""

    def __init__(self, load: Callable[[], Any]) -> None:
        self._load, self._done = load, False
        self._value: Any = None
        self._error: Exception | None = None

    def get(self) -> Any:
        if not self._done:
            self._done = True
            try:
                self._value = self._load()
            except Exception as exc:     # remembered: a failed load is not retried per seat
                self._error = exc
        if self._error is not None:
            raise self._error
        return self._value


@dataclass(frozen=True)
class Specialist:
    """One deterministic seat: a check over ONE evidence partition."""

    name: str
    committee: str
    partition: str
    level: int
    failure_class: str
    cost_s: float                               # declared cost, used before it is measured
    check: Callable[[Any, str], Result]         # (partition evidence, subject key) -> Result
    trap: Callable[[int], Any] | None = None    # seed -> evidence the seat MUST fail
    clean: Callable[[int], Any] | None = None   # seed -> evidence the seat must NOT fail
    settles_by: str = "remeasure"               # "fate" | "remeasure"


def result(sp: Specialist, verdict: str, strength: float = 0.0, *,
           evidence: Mapping[str, Any] | None = None, test: str = "",
           gain: float = 0.0) -> Result:
    if verdict not in VERDICTS:
        raise ValueError(f"{sp.name}: verdict {verdict!r} is not one of {VERDICTS}")
    return Result(sp.name, verdict, max(0.0, min(1.0, float(strength))),
                  sp.failure_class if verdict != PASS else "", dict(evidence or {}), test,
                  float(gain), 0.0, sp.failure_class)


def entropy(p: float) -> float:
    p = min(max(p, 1e-6), 1 - 1e-6)
    return -(p * math.log2(p) + (1 - p) * math.log2(1 - p))


# ------------------------------------------------------------------------------------ state
def blank_state() -> dict[str, Any]:
    return {"seats": {}, "seen": {}, "pending": [], "retired": {}, "broken": {}, "days": {},
            "missed": {}}


def seat_stats(state: Mapping[str, Any], name: str) -> dict[str, Any]:
    return dict((state.get("seats") or {}).get(name) or {})


def fail_prior(state: Mapping[str, Any], name: str) -> float:
    """The seat's Laplace-smoothed FAIL rate: its prior before it looks at a subject."""
    s = seat_stats(state, name)
    return (float(s.get("fails", 0)) + 1.0) / (float(s.get("measured", 0)) + 2.0)


def calibrated_weight(state: Mapping[str, Any], name: str) -> float:
    """1 - Brier over every settled claim AND every planted-trap reading (ground truth the seat
    cannot see coming); 0.25 is a coin, and a seat with nothing scored keeps weight 0.75."""
    s = seat_stats(state, name)
    n = int(s.get("settled", 0)) + int(s.get("trap_settled", 0))
    b = float(s.get("brier_sum", 0.0)) + float(s.get("trap_brier_sum", 0.0))
    return 1.0 - (b / n if n else 0.25)


def p_fail(verdict: str, strength: float) -> float:
    """The probability of FAIL a typed result asserts."""
    return 0.5 + 0.5 * strength if verdict == FAIL else 0.5 - 0.5 * strength


def is_probe(fingerprint: str) -> bool:
    return int(fingerprint[:8] or "0", 16) % PROBE_EVERY == 0


def plan(seats: Sequence[Specialist], state: Mapping[str, Any], level: int, budget_s: float,
         partitions: Iterable[str] | None = None, probe: bool = False
         ) -> tuple[list[Specialist], list[str], list[str]]:
    """DYNAMIC SEAT SELECTION: this level's seats, most information per second first.

    Returns (chosen, left out for budget, retired and skipped). Only seats whose partition the
    subject CARRIES sit (a partition present but empty is carried, and its seat says
    UNMEASURED). A retired seat sits only on a probe subject. THE ORDER DECIDES WHAT FITS: when
    the budget runs out, the seats later in the order are the ones not run, and they are named."""
    retired = set(state.get("retired") or {})
    has = None if partitions is None else set(partitions)
    here = [s for s in seats if s.level == level and (has is None or s.partition in has)]
    live = [s for s in here if probe or s.name not in retired]
    skipped_retired = sorted(s.name for s in here if s not in live)

    def rate(s: Specialist) -> float:
        cost = max(float(seat_stats(state, s.name).get("mean_cost_s") or s.cost_s), 1e-3)
        return entropy(fail_prior(state, s.name)) * calibrated_weight(state, s.name) / cost

    out: list[Specialist] = []
    over: list[str] = []
    spent = 0.0
    for s in sorted(live, key=lambda s: (-rate(s), s.name)):
        cost = float(seat_stats(state, s.name).get("mean_cost_s") or s.cost_s)
        if out and spent + cost > budget_s:
            over.append(s.name)
            continue
        out.append(s)
        spent += cost
    return out, over, skipped_retired


def select(seats: Sequence[Specialist], state: Mapping[str, Any], level: int,
           budget_s: float, partitions: Iterable[str] | None = None) -> list[Specialist]:
    return plan(seats, state, level, budget_s, partitions)[0]


def run_seat(sp: Specialist, evidence: Mapping[str, Any], key: str) -> Result:
    """EVIDENCE PARTITIONING: the seat sees its own partition and nothing else."""
    t0 = time.monotonic()
    part, why = evidence.get(sp.partition), f"no {sp.partition} evidence for {key}"
    if isinstance(part, Lazy):
        try:
            part = part.get()
        except Exception as exc:          # evidence that cannot load measured nothing
            part, why = None, f"{sp.partition} evidence failed to load: {type(exc).__name__}: {exc}"
    if part is None:
        r = result(sp, UNMEASURED, evidence={"why": why})
    else:
        try:
            r = sp.check(part, key)
        except Exception as exc:          # a seat that crashes measured nothing
            r = result(sp, UNMEASURED, evidence={"why": f"{type(exc).__name__}: {exc}"})
    return Result(r.specialist, r.verdict, r.strength, r.failure_class, r.evidence,
                  r.recommended_test, r.info_gain, time.monotonic() - t0,
                  r.probes or sp.failure_class)


def unresolved(rs: Sequence[Result]) -> bool:
    measured = [r for r in rs if r.verdict != UNMEASURED]
    if not measured:
        return True
    fails = [r for r in measured if r.verdict == FAIL]
    if fails:
        # A decisive objection stops the climb and is reported; a weak one (or a split) climbs.
        return max(r.strength for r in fails) < DECISIVE
    return max(r.strength for r in measured) < CONFIDENT


def examine(subject: Subject, seats: Sequence[Specialist], state: Mapping[str, Any],
            budget_s: float) -> dict[str, Any]:
    """TRIGGER -> L0..L4 ESCALATION for one subject."""
    results: list[Result] = []
    levels_run: list[int] = []
    over_budget: list[str] = []
    retired_skipped: list[str] = []
    level = max(0, min(4, subject.level))
    fp = subject.fingerprint()
    probe = is_probe(fp)
    deadline = time.monotonic() + budget_s
    while level <= 4:
        left = deadline - time.monotonic()
        if left <= 0:
            over_budget += [s.name for s in seats if s.level >= level
                            and s.partition in subject.evidence]
            break
        chosen, over, gone = plan(seats, state, level, left, subject.evidence, probe)
        over_budget += over
        retired_skipped += gone
        if chosen:
            levels_run.append(level)
            here = [run_seat(sp, subject.evidence, subject.key) for sp in chosen]
            results.extend(here)
            if not unresolved(here):
                break
        level += 1
    # EXPERIMENTS SAVED: a decisive objection that stops the climb spares every seat above it.
    saved: dict[str, float] = {}
    stoppers = [r.specialist for r in results if r.verdict == FAIL and r.strength >= DECISIVE]
    if stoppers and levels_run and levels_run[-1] < 4:
        retired = set(state.get("retired") or {})
        spared = sum(float(seat_stats(state, s.name).get("mean_cost_s") or s.cost_s)
                     for s in seats if s.level > levels_run[-1] and s.name not in retired
                     and s.partition in subject.evidence)
        for name in stoppers:
            saved[name] = round(spared / len(stoppers), 4)
    return {"key": subject.key, "committee": subject.committee, "trigger": subject.trigger,
            "claim": subject.claim, "keys": dict(subject.keys), "levels": levels_run,
            "fingerprint": fp, "results": [r.row() for r in results],
            "minority": minority(results), "verdict": overall(results), "saved_s": saved,
            "probe": probe, "over_budget": over_budget, "retired_skipped": retired_skipped}


def overall(rs: Sequence[Result]) -> str:
    """A CHALLENGE STATUS, never an authority: FAIL means 'a seat objects with evidence'."""
    if any(r.verdict == FAIL for r in rs):
        return FAIL
    if any(r.verdict == PASS for r in rs):
        return PASS
    return UNMEASURED


def minority(rs: Sequence[Result]) -> list[dict[str, Any]]:
    """MINORITY REPORTS: when measured seats split, keep the smaller side, with its evidence."""
    fails = [r for r in rs if r.verdict == FAIL]
    passes = [r for r in rs if r.verdict == PASS]
    if not fails or not passes:
        return []
    side = fails if len(fails) < len(passes) else passes
    return [r.row() for r in side]


# ------------------------------------------------------------ objections -> experiments
def compile_experiments(examined: Iterable[Mapping[str, Any]],
                        costs: Mapping[str, float]) -> list[dict[str, Any]]:
    """Every FAIL/UNMEASURED that names a test becomes one de-duplicated experiment."""
    exps: dict[str, dict[str, Any]] = {}
    for ex in examined:
        for r in ex.get("results") or []:
            test = str(r.get("recommended_test") or "")
            if r.get("verdict") == PASS or not test:
                continue
            k = f"{ex['committee']}|{ex['key']}|{test}"
            cost = float(costs.get(test, 0.0) or r.get("cost_s") or 1.0)
            gain = float(r.get("info_gain") or entropy(0.5 if r["verdict"] == UNMEASURED
                                                        else 1 - float(r.get("strength") or 0)))
            e = exps.setdefault(k, {"committee": ex["committee"], "subject": ex["key"],
                                    "test": test, "raised_by": [], "classes": [],
                                    "info_gain": 0.0, "cost_s": max(cost, 1e-3)})
            e["raised_by"].append(r["specialist"])
            if r.get("failure_class"):
                e["classes"].append(r["failure_class"])
            e["info_gain"] = max(e["info_gain"], gain)
    return rank(exps.values())


def rank(exps: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """THE RANKER: information gain per second, most first; ties go to more objectors."""
    out = [dict(e) | {"gain_per_s": round(float(e["info_gain"]) / float(e["cost_s"]), 6)}
           for e in exps]
    return sorted(out, key=lambda e: (-e["gain_per_s"], -len(e["raised_by"]), e["test"]))


def falsification_tree(ex: Mapping[str, Any], experiments: Sequence[Mapping[str, Any]]
                       ) -> dict[str, Any]:
    """The claim at the root, one branch per failure class raised, ranked experiments under it."""
    branches: dict[str, dict[str, Any]] = {}
    for r in ex.get("results") or []:
        cls = str(r.get("failure_class") or "")
        if not cls:
            continue
        b = branches.setdefault(cls, {"failure_class": cls, "measured": [], "experiments": []})
        b["measured"].append({"specialist": r["specialist"], "verdict": r["verdict"],
                              "strength": r["strength"]})
    for e in experiments:
        if e["subject"] != ex["key"] or e["committee"] != ex["committee"]:
            continue
        for cls in e["classes"] or ["UNCLASSIFIED"]:
            branches.setdefault(cls, {"failure_class": cls, "measured": [], "experiments": []})
            branches[cls]["experiments"].append(e["test"])
    return {"root": ex.get("claim") or ex["key"], "verdict": ex["verdict"],
            "branches": sorted(branches.values(), key=lambda b: b["failure_class"])}


def contradictions(examined: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """One join key, one failure class: a committee that only PASSed it and another that only
    FAILed it. Disagreement inside one committee is its minority report, not a contradiction."""
    seen: dict[tuple[str, str, str], dict[str, dict[str, set[str]]]] = {}
    for ex in examined:
        for r in ex.get("results") or []:
            probe = str(r.get("probes") or r.get("failure_class") or "")
            if r["verdict"] == UNMEASURED or not probe:
                continue
            for kname, kval in (ex.get("keys") or {}).items():
                if not kval:
                    continue
                by_c = seen.setdefault((kname, str(kval), probe), {})
                sides = by_c.setdefault(ex["committee"], {PASS: set(), FAIL: set()})
                sides[r["verdict"]].add(r["specialist"])
    out = []
    for (kname, kval, probe), by_c in sorted(seen.items()):
        only_pass = sorted(c for c, s in by_c.items() if s[PASS] and not s[FAIL])
        only_fail = sorted(c for c, s in by_c.items() if s[FAIL] and not s[PASS])
        if only_pass and only_fail:
            out.append({"join": kname, "value": kval, "failure_class": probe,
                        "pass": {c: sorted(by_c[c][PASS]) for c in only_pass},
                        "fail": {c: sorted(by_c[c][FAIL]) for c in only_fail}})
    return out


# -------------------------------------------------------------- traps, overlap, ROI
def run_traps(seats: Sequence[Specialist], seed: int = 0) -> dict[str, dict[str, Any]]:
    """PLANTED TRAPS: each seat against the defect it exists to catch, and its clean twin.

    The fixtures are GENERATED from `seed` (the pass sets it from the clock), so every pass
    plants a fresh instance of each defect: a seat tuned to one fixed fixture fails the next."""
    out: dict[str, dict[str, Any]] = {}
    for sp in seats:
        row: dict[str, Any] = {"seed": seed}
        for kind, make in (("trap", sp.trap), ("clean", sp.clean)):
            if make is None:
                row[kind] = UNMEASURED
                continue
            try:
                ev = make(seed)
            except Exception as exc:          # a fixture that cannot build measured nothing
                row[kind], row[f"{kind}_why"] = UNMEASURED, f"{type(exc).__name__}: {exc}"
                continue
            r = run_seat(sp, {sp.partition: ev}, f"{kind}:{sp.name}")
            row[kind], row[f"{kind}_strength"] = r.verdict, round(r.strength, 4)
            if kind == "trap":
                row["caught"] = r.verdict == FAIL
            else:
                row["false_alarm"] = r.verdict == FAIL
        out[sp.name] = row
    return out


def overlap(examined: Sequence[Mapping[str, Any]], seats: Sequence[Specialist]
            ) -> dict[str, Any]:
    """Pairwise Jaccard of FAIL sets and each seat's unique catches (the ablation's answer)."""
    fails: dict[str, set[str]] = {s.name: set() for s in seats}
    measured: dict[str, int] = {s.name: 0 for s in seats}
    for ex in examined:
        for r in ex.get("results") or []:
            if r["specialist"] not in fails:
                continue
            if r["verdict"] != UNMEASURED:
                measured[r["specialist"]] += 1
            if r["verdict"] == FAIL:
                fails[r["specialist"]].add(ex["key"])
    names = sorted(fails)
    pairs: list[dict[str, Any]] = []
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            u = fails[a] | fails[b]
            if u:
                pairs.append({"a": a, "b": b,
                              "jaccard": round(len(fails[a] & fails[b]) / len(u), 4)})
    unique = {n: len(fails[n] - set().union(*(fails[m] for m in names if m != n)))
              for n in names}
    # Ablation at the committee's own verdict: subjects that go from FAIL to not-FAIL without n.
    ablation = {n: sum(1 for ex in examined
                       if {r["specialist"] for r in ex.get("results") or []
                           if r["verdict"] == FAIL} == {n}) for n in names}
    return {"pairs": sorted(pairs, key=lambda p: -float(p["jaccard"]))[:50], "unique": unique,
            "ablation": ablation, "fails": {n: len(v) for n, v in fails.items()},
            "measured": measured}


def update_state(state: dict[str, Any], examined: Sequence[Mapping[str, Any]],
                 traps: Mapping[str, Mapping[str, Any]]) -> None:
    seats = state.setdefault("seats", {})
    open_claims = {(c["specialist"], c["key"], c.get("fingerprint"))
                   for c in state.get("pending") or []}
    for ex in examined:
        state.setdefault("seen", {})[f"{ex['committee']}|{ex['key']}"] = ex["fingerprint"]
        for r in ex.get("results") or []:
            s = seats.setdefault(r["specialist"], {})
            s["runs"] = int(s.get("runs", 0)) + 1
            s["cost_s"] = float(s.get("cost_s", 0.0)) + float(r["cost_s"])
            s["mean_cost_s"] = round(s["cost_s"] / s["runs"], 6)
            if r["verdict"] == FAIL:
                s["fails"] = int(s.get("fails", 0)) + 1
            if r["verdict"] == UNMEASURED:
                continue
            s["measured"] = int(s.get("measured", 0)) + 1
            claim_id = (r["specialist"], ex["key"], ex["fingerprint"])
            if claim_id in open_claims:
                continue                     # the same claim on the same evidence, once
            open_claims.add(claim_id)
            # A claim to settle later: the P(FAIL) it asserted, and on what evidence.
            p = p_fail(r["verdict"], float(r["strength"]))
            claim = {"specialist": r["specialist"], "committee": ex["committee"],
                     "key": ex["key"], "p_fail": round(p, 4), "at": now(),
                     "fingerprint": ex["fingerprint"]}
            if (ex.get("keys") or {}).get("cell"):
                claim["cell"] = ex["keys"]["cell"]
            state.setdefault("pending", []).append(claim)
    for name, t in traps.items():
        s = seats.setdefault(name, {})
        if "caught" in t:
            s["traps"] = int(s.get("traps", 0)) + 1
            s["traps_caught"] = int(s.get("traps_caught", 0)) + int(bool(t["caught"]))
        if "false_alarm" in t:
            s["cleans"] = int(s.get("cleans", 0)) + 1
            s["false_alarms"] = int(s.get("false_alarms", 0)) + int(bool(t["false_alarm"]))
        # GROUND TRUTH: a planted defect is a FAIL by construction and its clean twin a PASS, so
        # every seat, whatever its committee, is scored for calibration on every pass.
        for kind, truth in (("trap", 1.0), ("clean", 0.0)):
            v = t.get(kind)
            if v in (PASS, FAIL):
                q = p_fail(str(v), float(t.get(f"{kind}_strength") or 0.0))
                s["trap_settled"] = int(s.get("trap_settled", 0)) + 1
                s["trap_brier_sum"] = round(float(s.get("trap_brier_sum", 0.0))
                                            + (q - truth) ** 2, 6)
        rate = s.get("traps_caught", 0) / s["traps"] if s.get("traps") else None
        if rate is not None and rate < TRAP_FLOOR:
            state.setdefault("broken", {})[name] = {
                "at": now(), "why": f"caught {s['traps_caught']}/{s['traps']} of its own traps"}
        else:
            state.setdefault("broken", {}).pop(name, None)
    # Keep the pending ledger bounded: oldest claims first out.
    state["pending"] = state.get("pending", [])[-MAX_PENDING:]


def settle(state: dict[str, Any], outcome: Callable[[Mapping[str, Any]], bool | None]) -> int:
    """CALIBRATION: score each pending P(FAIL) against its later outcome (None = not yet)."""
    keep, n = [], 0
    seats = state.setdefault("seats", {})
    for claim in state.get("pending") or []:
        got = outcome(claim)
        if got is None:
            keep.append(claim)
            continue
        s = seats.setdefault(claim["specialist"], {})
        s["settled"] = int(s.get("settled", 0)) + 1
        s["brier_sum"] = float(s.get("brier_sum", 0.0)) + (float(claim["p_fail"]) - float(got)) ** 2
        n += 1
    state["pending"] = keep
    return n


def record_day(state: dict[str, Any], examined: Sequence[Mapping[str, Any]],
               seats: Sequence[Specialist], ov: Mapping[str, Any], day: str) -> None:
    """Per seat per UTC day: measured, fails, unique catches and sole objections, so the
    retirement rule reads a WINDOW, never a lifetime count against one pass's catches. Retired
    seats that were skipped are billed the information they would have been expected to buy."""
    days = state.setdefault("days", {})
    for sp in seats:
        d = days.setdefault(sp.name, {}).setdefault(day, {"measured": 0, "fails": 0,
                                                          "unique": 0, "sole": 0})
        d["measured"] += int((ov.get("measured") or {}).get(sp.name, 0))
        d["fails"] += int((ov.get("fails") or {}).get(sp.name, 0))
        d["unique"] += int((ov.get("unique") or {}).get(sp.name, 0))
        d["sole"] += int((ov.get("ablation") or {}).get(sp.name, 0))
        keep = sorted(days[sp.name])[-(RETIRE_WINDOW_DAYS * 4):]
        days[sp.name] = {k: days[sp.name][k] for k in keep}
    missed = state.setdefault("missed", {})
    for ex in examined:
        for name in ex.get("retired_skipped") or []:
            m = missed.setdefault(name, {"subjects": 0, "bits": 0.0})
            m["subjects"] += 1
            m["bits"] = round(m["bits"] + entropy(fail_prior(state, name))
                              * calibrated_weight(state, name), 4)


def window(state: Mapping[str, Any], name: str, day: str) -> dict[str, Any]:
    """The seat's last RETIRE_WINDOW_DAYS days: totals, and how many days it spans."""
    from datetime import date, timedelta
    end = date.fromisoformat(day)
    start = (end - timedelta(days=RETIRE_WINDOW_DAYS - 1)).isoformat()
    rows = {k: v for k, v in ((state.get("days") or {}).get(name) or {}).items()
            if start <= k <= day}
    first = min((state.get("days") or {}).get(name) or {day: {}})
    tot = {k: sum(int(v.get(k, 0)) for v in rows.values())
           for k in ("measured", "fails", "unique", "sole")}
    return tot | {"history_days": (end - date.fromisoformat(first)).days + 1}


def retire(state: dict[str, Any], seats: Sequence[Specialist], day: str) -> dict[str, list[str]]:
    """THE ROI RULE (CRO D27): ablation value <= 0 over RETIRE_WINDOW_DAYS days with enough
    measurements retires a seat; a unique catch by a retired seat's probes inside the window
    re-opens it. UNMEASURED never retires (no measurements, no verdict), and a broken seat is
    repaired, never retired for being blind."""
    out: dict[str, list[str]] = {"retired": [], "reopened": []}
    retired = state.setdefault("retired", {})
    for sp in seats:
        w = window(state, sp.name, day)
        value = w["unique"] + w["sole"]
        if sp.name in retired:
            if value > 0:
                # A RE-OPENING on positive evidence (a unique catch), recorded, never an erasure.
                state.setdefault("reopened", {})[sp.name] = \
                    retired[sp.name] | {"reopened_at": now()}
                retired = state["retired"] = {k: v for k, v in retired.items() if k != sp.name}
                out["reopened"].append(sp.name)
            continue
        if w["history_days"] >= RETIRE_WINDOW_DAYS and w["measured"] >= \
                MIN_OBS_FOR_RETIREMENT and value <= 0 and sp.name not in (state.get("broken")
                                                                          or {}):
            retired[sp.name] = {
                "at": now(), "window_days": RETIRE_WINDOW_DAYS, "measured": w["measured"],
                "ablation_value": value,
                "why": f"no subject only it objected to in {w['measured']} measurements over "
                       f"{RETIRE_WINDOW_DAYS} days; probes on 1 in {PROBE_EVERY} subjects "
                       f"re-open it on its first unique catch",
                "reopen": f"a unique catch by a probe inside {RETIRE_WINDOW_DAYS} days"}
            out["retired"].append(sp.name)
    return out


def roi(state: Mapping[str, Any], seats: Sequence[Specialist], ov: Mapping[str, Any]
        ) -> dict[str, dict[str, Any]]:
    stats = state.get("seats") or {}
    out = {}
    for sp in seats:
        s = stats.get(sp.name) or {}
        n = int(s.get("settled", 0))
        out[sp.name] = {
            "committee": sp.committee, "level": sp.level, "partition": sp.partition,
            "runs": int(s.get("runs", 0)), "measured": int(s.get("measured", 0)),
            "fails": int(s.get("fails", 0)), "unique_catches": (ov.get("unique") or {}).get(
                sp.name, 0), "cost_s": round(float(s.get("cost_s", 0.0)), 3),
            "brier": round(float(s.get("brier_sum", 0.0)) / n, 4) if n else UNMEASURED,
            "settled": n,
            "traps": f"{s.get('traps_caught', 0)}/{s.get('traps', 0)}" if s.get("traps")
            else UNMEASURED,
            "false_alarms": f"{s.get('false_alarms', 0)}/{s.get('cleans', 0)}"
            if s.get("cleans") else UNMEASURED,
            "status": ("RETIRED" if sp.name in (state.get("retired") or {}) else
                       "BROKEN" if sp.name in (state.get("broken") or {}) else "ACTIVE")}
    return out
