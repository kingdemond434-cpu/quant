"""THE ORGAN CENSUS: one roster, one chain per organ, and the yield that orders research compute.

WHY IT EXISTS, measured on the trading box 2026-09-24/25. Three external reviews converged on one
closing question -- "does every claimed department actually run 24/7, use real data, generate real
hypotheses, produce measurable artifacts, enter the same canonical validation pipeline, and have
its resource allocation changed according to real survivor yield?" -- and the desk could not
answer it, because it had THREE censuses that never added up:

    reports/PRODUCER_CENSUS.json       1,568 producers   (clock + last production)
    reports/PRODUCTIVITY_CENSUS.json   2,094 producers   (the eleven-stage funnel)
    reports/DEAD_ARCHITECTURE.json       711 organs      (has anything on the other end)

    union 2,817 names.  PRODUCERS PRESENT IN ALL THREE: ZERO.

Not one organ. `dead_architecture` keys by CODE PATH (`desks/mt5/blueprint/coverage.py`), the
other two key by PRODUCER NAME (`aaii`, `sandbox:alpha101`), and nothing in the tree resolved one
onto the other. So every total the desk published about itself was a total over one roster's
vocabulary, and "how many organs are there" had three answers that could not be compared. That is
the defect this file fixes: NOT another department, NOT another measurement -- the JOIN.

WHAT IT ADDS ON TOP OF THE JOIN is exactly the two links nothing in the tree measured:

  * THE INPUT LINK. 1 of 1,409 ComponentSpecs declares an input. One. So an organ reading a file
    that stopped updating was indistinguishable from an organ reading a live one, which is how
    `fred.json` refreshed every thirty minutes and landed 893 bytes with every fence green.
  * THE ARTIFACT'S NON-TRIVIALITY. Every existing fence measures an artifact's AGE. None measures
    whether the bytes mean anything, and `rc=0` with a fresh empty file is this desk's signature
    failure mode.

AND IT TURNS THE CENSUS INTO AN ECONOMIC INSTRUMENT (coordinator, 2026-09-25). The highest
marginal-ROI build on this desk is not another generator -- it is making the generators that exist
compete on DOWNSTREAM SURVIVOR YIELD. `libs/research/search_populations.py` already runs nine
populations (gp, gflownet, symreg, program_synthesis, bayesian, zoo_mutation, graveyard_derived,
causal_derived, claims_derived) and counts each one's draws as far as `donated`. Nothing followed
a single draw to a certificate. `yield_ledger()` does, by joining the attribution lane's
per-producer certificate table to the compute ledger's per-producer hours.

TWO BOUNDARIES, BOTH LOAD-BEARING AND BOTH PINNED BY TESTS:

  1. WEAK GENERATORS ARE STARVED, NEVER ELIMINATED. `EXPLORATION_FLOOR` is the share of research
     compute reserved for producers with no track record or a bad one. A yield optimiser with no
     exploration budget stops discovering, which is the opposite of the goal, and a run of bad
     luck must never be able to permanently kill a search method.
  2. THIS ORDERS RESEARCH COMPUTE AND NEVER RATIONS THE JUDGE. Multiplicity is PINNED
     (`gate_spec.yaml: fixed_trial_count: 109`, "FIXED, NOT SWEEP-DEPENDENT"), so judging one more
     cell costs nothing at the bar. Nothing here may refuse a cell judgement, and
     `tests/governance/test_organ_census_fence.py` fails if this module ever grows a function
     that could. It caps nothing, throttles nothing and retires nothing: it publishes an ORDER.

NOTHING IS HAND-LISTED. Every row comes from a roster that already exists. An organ that lands
tomorrow is in tomorrow's census because its roster saw it, not because somebody typed it here.
"""
from __future__ import annotations

import json
import time
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / "desks" / "mt5" / "reports"

#: The seven links of the chain the reviews named, in order. An organ is only as strong as the
#: first link that breaks, which is why the census reports the chain and not a score.
LINKS: tuple[str, ...] = ("code", "clock", "input", "artifact", "pipeline", "yield", "allocation")

REAL = "REAL"
BROKEN = "BROKEN"
UNMEASURED = "UNMEASURED"

#: Bytes below which an artifact is TRIVIAL until proven otherwise. Measured, not chosen:
#: `fred.json` refreshed every thirty minutes and landed 893 bytes of nothing, and no fence on
#: this desk could tell it from a full one, because every one of them measured age alone.
TRIVIAL_BYTES = 1024

#: Keys that are an artifact's own paperwork rather than its payload. A JSON document carrying
#: only these is a receipt for work that did not happen.
_METADATA_KEYS = frozenset({
    "at", "generated", "generated_utc", "generated_at", "host", "hostname", "law", "why",
    "elapsed_s", "budget_s", "version", "schema", "basis", "note", "notes", "status", "rule",
    "boundary", "commit", "commit_sha", "run", "kind", "ok",
})

#: Source-file suffixes. A production path ending in one of these is CODE; anything else is an
#: artifact. This is the whole trick that lets a path-keyed roster meet a name-keyed one.
_CODE_SUFFIXES = (".py", ".sh", ".ps1", ".cmd", ".bat")

#: THE EXPLORATION FLOOR (principal's growth governance, Rule 2 read the right way round). The
#: share of research compute that may never be taken from producers with no track record. A
#: producer starves; it is never eliminated, and a producer that has NEVER been measured is not
#: evidence of a bad producer -- it is evidence of a desk that has not looked.
EXPLORATION_FLOOR = 0.25

#: What this module is allowed to do, asserted in the artifact so no reader has to infer it.
BOUNDARY = (
    "THIS CENSUS MEASURES AND ORDERS RESEARCH COMPUTE. It has no authority: it does not cap, "
    "throttle, retire, deprioritise or refuse anything. It NEVER rations what reaches the judge "
    "-- multiplicity is pinned at fixed_trial_count 109, so judging one more cell costs nothing "
    "at the bar and refusing one would be a pure loss. Weak generators are STARVED to the "
    f"exploration floor ({EXPLORATION_FLOOR:.0%} of research compute), never eliminated."
)


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def _norm(p: object) -> str:
    """A repo-relative path in one shape, so two rosters spelling it differently still meet."""
    s = str(p or "").replace("\\", "/").strip()
    while s.startswith("./"):
        s = s[2:]
    return s.rstrip("/")


def _is_code(path: str) -> bool:
    return path.lower().endswith(_CODE_SUFFIXES)


# --------------------------------------------------------------------------------- triviality
def is_trivial(path: Path, *, max_read: int = 65536) -> tuple[bool, str]:
    """Does this artifact carry a payload, or only its own paperwork?

    THE QUESTION NO EXISTING FENCE ASKED. Every one of them measures age; a leg that rewrites an
    empty report every hour is fresh forever. Three shapes are trivial and all three were found
    on the box: a file under `TRIVIAL_BYTES`, a JSON container with nothing in it, and a JSON
    object whose only keys are metadata -- a receipt for work that did not happen.
    """
    try:
        size = path.stat().st_size
    except OSError as exc:
        return True, f"cannot stat: {type(exc).__name__}"
    if size == 0:
        return True, "zero bytes"
    if size < TRIVIAL_BYTES and path.suffix.lower() in (".json", ".jsonl", ".txt", ".csv", ".md"):
        return True, f"{size} bytes, under the {TRIVIAL_BYTES}-byte triviality floor"
    if size >= TRIVIAL_BYTES:
        return False, f"{size} bytes"
    try:
        raw = path.read_bytes()[:max_read].decode("utf-8-sig", errors="replace")
    except OSError as exc:
        return True, f"cannot read: {type(exc).__name__}"
    try:
        doc = json.loads(raw)
    except ValueError:
        return False, f"{size} bytes, not JSON -- payload not judged"
    if isinstance(doc, (list, dict)) and not doc:
        return True, "an empty JSON container"
    if isinstance(doc, dict) and not (set(doc) - _METADATA_KEYS):
        return True, ("every key is the artifact's own paperwork "
                      f"({sorted(doc)[:6]}) -- a receipt, not a payload")
    return False, f"{size} bytes"


# ----------------------------------------------------------------------------------- claims
@dataclass(frozen=True)
class Claim:
    """One roster's assertion that an organ exists. A claim is not evidence that it works."""

    roster: str
    name: str
    kind: str
    code_paths: tuple[str, ...] = ()
    artifacts: tuple[str, ...] = ()
    clock: str | None = None
    clocked: bool | None = None
    detail: Mapping[str, Any] = field(default_factory=dict)


def claims_from_producer_census(doc: Mapping[str, Any] | None) -> list[Claim]:
    """Clock and last production, keyed by producer name. 1,568 rows on the box."""
    out: list[Claim] = []
    for row in (doc or {}).get("rows", []) or []:
        if not isinstance(row, dict):
            continue
        paths = tuple(_norm(p) for p in (row.get("production_paths") or ()))
        organ = _norm(row.get("organ")) if row.get("organ") else ""
        code = tuple(sorted({p for p in (*paths, organ) if p and _is_code(p)}))
        arts = tuple(sorted({p for p in paths if p and not _is_code(p)}))
        clock = row.get("clock")
        out.append(Claim("producer_census", str(row.get("producer")), str(row.get("kind") or ""),
                         code, arts, str(clock) if clock else None,
                         clocked=bool(clock) and str(clock) != UNMEASURED,
                         detail={"verdict": row.get("verdict"),
                                 "criticality": row.get("criticality"),
                                 "owner": row.get("owner"),
                                 "cadence_s": row.get("cadence_s"),
                                 "age_h": row.get("age_h")}))
    return out


def claims_from_dead_architecture(doc: Mapping[str, Any] | None) -> list[Claim]:
    """Has anything on the other end, keyed by CODE PATH. 711 organs on the box, and the roster
    that shares no identity at all with the other two -- which is the whole reason for the join."""
    out: list[Claim] = []
    for path, rec in ((doc or {}).get("organs") or {}).items():
        if not isinstance(rec, dict):
            continue
        verdict = str(rec.get("verdict") or "")
        arts = tuple(_norm(a) for a in (rec.get("artifacts") or ()))
        out.append(Claim("dead_architecture", _norm(path), "code", (_norm(path),), arts, None,
                         clocked=(None if verdict not in ("NO_CLOCK", "LIVE", "BURNING",
                                                          "UNREACHED")
                                  else verdict != "NO_CLOCK"),
                         detail={"verdict": verdict,
                                 "n_consumers": rec.get("n_consumers"),
                                 "consumers": list(rec.get("consumers") or ())[:6]}))
    return out


def claims_from_productivity(doc: Mapping[str, Any] | None) -> list[Claim]:
    """The eleven-stage funnel, keyed by producer name. 2,094 rows on the box."""
    out: list[Claim] = []
    for row in (doc or {}).get("producers", []) or []:
        if not isinstance(row, dict):
            continue
        clock = row.get("clock")
        out.append(Claim("productivity", str(row.get("producer")), str(row.get("kind") or ""),
                         (), (), str(clock) if clock else None,
                         clocked=bool(clock),
                         detail={"cells": row.get("cells"),
                                 "unique_cells": row.get("unique_cells"),
                                 "cells_reached_judge": row.get("cells_reached_judge"),
                                 "reach_cause": row.get("reach_cause"),
                                 "cells_judged": row.get("cells_judged"),
                                 "certificates": row.get("certificates"),
                                 "compute_hours": row.get("compute_hours"),
                                 "region": row.get("region")}))
    return out


def claims_from_component_registry(doc: Mapping[str, Any] | None) -> list[Claim]:
    """The birth registry, which is the ONLY roster that carries declared INPUTS -- and on the box
    exactly 1 of 1,409 specs fills that field, which is itself the finding."""
    out: list[Claim] = []
    #: The artifact publishes its per-component rows under `freshness` (every spec it could date)
    #: and `unclocked` (the ones with no schedule at all); `components` is a COUNT. Reading the
    #: count as a roster is how this reader crashed on its first pass, and the two lists together
    #: are the whole registry.
    rows: list[Any] = []
    for key in ("freshness", "unclocked", "components"):
        value = (doc or {}).get(key)
        if isinstance(value, dict):
            rows.extend(value.values())
        elif isinstance(value, list):
            rows.extend(value)
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        cid = str(row.get("component_id") or row.get("id") or "")
        if not cid:
            continue
        code = tuple(sorted({_norm(p) for p in (row.get("code_paths") or ()) if p}))
        outs = tuple(sorted({_norm(p) for p in (row.get("outputs") or ()) if p}))
        sched = row.get("schedule")
        out.append(Claim("component_registry", cid, str(row.get("kind") or ""), code, outs,
                         str(sched) if sched and sched != UNMEASURED else None,
                         clocked=bool(sched) and str(sched) != UNMEASURED,
                         detail={"inputs": [_norm(p) for p in (row.get("inputs") or ())],
                                 "criticality": row.get("criticality"),
                                 "owner": row.get("owner"),
                                 "max_silence_s": row.get("max_silence_s"),
                                 "cadence_s": row.get("cadence_s")}))
    return out


def claims_from_sandbox(doc: Mapping[str, Any] | None) -> list[Claim]:
    """The federated sandbox systems, by id. The roster where "104 of 128 produce nothing" lives."""
    out: list[Claim] = []
    reasons = (doc or {}).get("reasons")
    for sid, rec in (reasons or {}).items():
        why = str((rec or {}).get("why") if isinstance(rec, dict) else rec)[:220]
        out.append(Claim("sandbox", f"sandbox:{sid}", "sandbox", (), (),
                         "hourly_cycle:sandbox_provision", clocked=True,
                         detail={"why": why, "system": sid}))
    return out


def claims_from_sandbox_roster(doc: Mapping[str, Any] | None) -> list[Claim]:
    """All 128 federated systems with their measured candidate counts.

    THE ROSTER, not the liveness reading. `SANDBOX_LIVENESS.json` lists only what the runner
    planned UNMEASURED; the roster carries every system with `candidates` and `runs`, which is
    where "104 of 128 sandbox systems produce nothing" becomes a row per system rather than a
    sentence in a review.
    """
    out: list[Claim] = []
    for row in (doc or {}).get("systems", []) or []:
        if not isinstance(row, dict):
            continue
        sid = str(row.get("system_id") or "")
        if not sid:
            continue
        cells = row.get("candidates")
        out.append(Claim("sandbox_roster", f"sandbox:{sid}", "sandbox", (), (),
                         "hourly_cycle:sandbox_runner", clocked=True,
                         detail={"unique_cells": (int(cells) if isinstance(cells, (int, float))
                                                  else None),
                                 "disposition": row.get("disposition"),
                                 "install_status": row.get("install_status"),
                                 "runs": row.get("runs"),
                                 "last_run_age_h": row.get("last_run_age_h")}))
    return out


def claims_from_capability_graph(nodes: Sequence[Any] | None) -> list[Claim]:
    """`libs/ops/capability_graph.NODES` -- 139 organs, and THE ONLY ROSTER THAT DECLARES READS.

    This is what rescues the input link. The component registry fills `inputs` on 1 spec of 1,409;
    the capability graph declares `reads` on almost every node it holds, so for those 139 organs
    the census can actually answer "is it reading a file that stopped updating" instead of
    reporting the question as unmeasurable. It also carries `freshness_s`, the node's own
    tolerance for a stale input, which is a better silence budget than any default.
    """
    out: list[Claim] = []
    for node in nodes or ():
        name = str(getattr(node, "name", "") or "")
        module = _norm(getattr(node, "module", ""))
        if not name:
            continue
        fresh = dict(getattr(node, "freshness_s", {}) or {})
        writes = tuple(_norm(w) for w in (getattr(node, "writes", ()) or ()))
        out.append(Claim("capability_graph", name, "capability",
                         (module,) if module else (), writes, None, clocked=None,
                         detail={"inputs": [_norm(r) for r in (getattr(node, "reads", ()) or ())],
                                 "authority": list(getattr(node, "authority", ()) or ())[:4],
                                 "max_silence_s": (min(fresh.values()) if fresh else None)}))
    return out


def capability_nodes(root: Path | None = None) -> list[Any]:
    """The capability graph's nodes, or an empty list where it cannot be imported. Guarded, never
    fatal: the census has to answer on a build box, in CI and in a fresh clone."""
    base = root or ROOT
    path = base / "libs" / "ops" / "capability_graph.py"
    if not path.is_file():
        #: A ROOT THAT IS NOT THIS ONE HAS ITS OWN GRAPH OR NONE. Falling back to the package
        #: import here would hand a tmp-dir census 139 organs from the real repository, which is
        #: how a "clean tree reports nothing" test first failed: the census was reading this
        #: checkout while claiming to read another.
        return []
    if base.resolve() == ROOT.resolve():
        try:
            from libs.ops.capability_graph import NODES
            return list(NODES)
        except Exception:                                    # pragma: no cover - import guard
            pass
    try:
        import importlib.util
        import sys
        name = "_oc_capability_graph"
        spec = importlib.util.spec_from_file_location(
            name, base / "libs" / "ops" / "capability_graph.py")
        if spec is None or spec.loader is None:
            return []
        mod = importlib.util.module_from_spec(spec)
        #: REGISTERED BEFORE EXECUTION, and it is not a nicety. `@dataclass` resolves its own
        #: annotations through `sys.modules[cls.__module__]`, so on Python 3.14 a file loaded
        #: without this line dies in `dataclasses._is_type` with `'NoneType' has no attribute
        #: '__dict__'` -- which is exactly how the only roster that declares INPUTS read as
        #: missing on the trading box, taking the input link to 0 of 2,440 with it.
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
        return list(mod.NODES)
    except Exception:                                        # pragma: no cover - import guard
        return []


# ---------------------------------------------------------------------------- the reconciliation
@dataclass
class Organ:
    """One organ, after every roster that claimed it has been resolved onto one identity."""

    organ_id: str
    kind: str = ""
    rosters: set[str] = field(default_factory=set)
    code_paths: set[str] = field(default_factory=set)
    artifacts: set[str] = field(default_factory=set)
    inputs: set[str] = field(default_factory=set)
    clock: str | None = None
    clocked: bool | None = None
    detail: dict[str, Any] = field(default_factory=dict)
    chain: dict[str, dict[str, Any]] = field(default_factory=dict)

    def absorb(self, claim: Claim) -> None:
        self.rosters.add(claim.roster)
        self.kind = self.kind or claim.kind
        self.code_paths.update(claim.code_paths)
        self.artifacts.update(claim.artifacts)
        self.inputs.update(str(p) for p in (claim.detail.get("inputs") or ()) if p)
        if claim.clock and not self.clock:
            self.clock = claim.clock
        if claim.clocked is not None and self.clocked is not True:
            self.clocked = claim.clocked if self.clocked is None else (self.clocked or
                                                                       claim.clocked)
        for key, value in claim.detail.items():
            if key == "inputs":
                continue
            if value is None or self.detail.get(key) is not None:
                continue
            self.detail[key] = value


def reconcile(claims: Sequence[Claim]) -> tuple[dict[str, Organ], dict[str, Any]]:
    """Resolve every roster's vocabulary onto ONE identity, and publish what would not resolve.

    THE RULE, and it is deliberately conservative. Name-keyed rosters merge by name. A path-keyed
    claim (`dead_architecture`) merges into a named organ only when EXACTLY ONE named organ
    claims that code path -- an unambiguous join. When several do (a `full_pipeline.py` that fills
    forty seats), the path is published as AMBIGUOUS and merged into none of them, because
    crediting one seat's liveness to forty is exactly the flattery that would make the census
    worthless. When none do, the path stands as its own organ: something exists that no producer
    roster has ever heard of, which is a finding rather than a nuisance.
    """
    organs: dict[str, Organ] = {}
    named = [c for c in claims if c.roster != "dead_architecture"]
    paths = [c for c in claims if c.roster == "dead_architecture"]

    for claim in named:
        organ = organs.get(claim.name)
        if organ is None:
            organ = organs[claim.name] = Organ(claim.name)
        organ.absorb(claim)

    owners: dict[str, set[str]] = {}
    for oid, organ in organs.items():
        for path in organ.code_paths:
            owners.setdefault(path, set()).add(oid)

    merged = 0
    ambiguous: dict[str, int] = {}
    standalone = 0
    for claim in paths:
        path = claim.name
        holders = owners.get(path) or set()
        if len(holders) == 1:
            organs[next(iter(holders))].absorb(claim)
            merged += 1
        elif len(holders) > 1:
            ambiguous[path] = len(holders)
            organ = organs.get(path)
            if organ is None:
                organ = organs[path] = Organ(path, kind="code")
            organ.absorb(claim)
            organ.detail["ambiguous_owners"] = sorted(holders)[:8]
            standalone += 1
        else:
            organ = organs.get(path)
            if organ is None:
                organ = organs[path] = Organ(path, kind="code")
            organ.absorb(claim)
            standalone += 1

    by_roster: dict[str, int] = {}
    for claim in claims:
        by_roster[claim.roster] = by_roster.get(claim.roster, 0) + 1
    coverage = {r: sum(1 for o in organs.values() if r in o.rosters) for r in by_roster}
    seen_by: dict[int, int] = {}
    for organ in organs.values():
        seen_by[len(organ.rosters)] = seen_by.get(len(organ.rosters), 0) + 1
    #: THE HEADLINE DEFECT, kept as its own number. These three are the desk's THREE CENSUSES and
    #: they are meant to describe the same population; before this join, the count below was 0.
    three = ("producer_census", "productivity", "dead_architecture")
    return organs, {
        "claims_read": len(claims),
        "claims_by_roster": dict(sorted(by_roster.items())),
        "organs_after_join": len(organs),
        "organs_seen_by_roster": dict(sorted(coverage.items())),
        "organs_by_roster_count": dict(sorted(seen_by.items())),
        "organs_seen_by_one_roster_only": seen_by.get(1, 0),
        "organs_in_all_three_censuses": sum(1 for o in organs.values()
                                            if o.rosters >= set(three)),
        "three_censuses": list(three),
        "path_claims_merged": merged,
        "path_claims_standalone": standalone,
        "ambiguous_code_paths": dict(sorted(ambiguous.items(), key=lambda kv: -kv[1])[:20]),
        "n_ambiguous_code_paths": len(ambiguous),
        "why": ("A path-keyed roster merges into a named organ only on an UNAMBIGUOUS code path. "
                "Standalone rows are organs no producer roster has ever named; ambiguous paths "
                "are shared runners whose liveness may not be credited to any one seat."),
    }


# ------------------------------------------------------------------------------ the seven links
def _link(verdict: str, why: str, **evidence: Any) -> dict[str, Any]:
    return {"verdict": verdict, "why": why, **evidence}


#: How many of the most recent files the payload search will open. A seat whose last payload is
#: more than this many donations ago has not produced in any sense the desk can use.
PAYLOAD_SCAN = 40


def _candidates(root: Path, rels: Iterable[str],
                limit: int = PAYLOAD_SCAN) -> list[tuple[float, str, int]]:
    """The most recent files under these paths, newest first, as (mtime, relpath, bytes)."""
    found: list[tuple[float, str, int]] = []
    for rel in rels:
        p = root / rel
        try:
            if p.is_dir():
                scanned = 0
                for f in p.iterdir():
                    if scanned > 4000:
                        break
                    scanned += 1
                    if f.is_file():
                        st = f.stat()
                        found.append((st.st_mtime, _norm(f.relative_to(root)), st.st_size))
                    elif f.is_dir():
                        for g in f.iterdir():
                            scanned += 1
                            if scanned > 4000:
                                break
                            if g.is_file():
                                st = g.stat()
                                found.append((st.st_mtime, _norm(g.relative_to(root)),
                                              st.st_size))
            elif p.is_file():
                st = p.stat()
                found.append((st.st_mtime, rel, st.st_size))
        except OSError:
            continue
    found.sort(key=lambda t: -t[0])
    return found[:limit]


def _newest_payload(root: Path, rels: Iterable[str]) -> tuple[
        tuple[float, str, int] | None, tuple[float, str, int] | None, int]:
    """(newest file, newest file WITH A PAYLOAD, how many recent files were trivial).

    WHY THE NEWEST FILE IS THE WRONG ANSWER, measured on the trading box 2026-09-24. Judging a
    donation directory by its newest file flagged `quantconnect` (596 files, 495 of them over a
    kilobyte, a 7 KB payload written twenty minutes earlier) as having STOPPED PRODUCING, because
    the single most recent file was a 214-byte receipt. One empty write masks a full directory,
    and a fence that flaps like that is a fence that gets switched off (L1.43).

    AND THE SAME SCAN IS WHAT FINDS THE REAL DEFECT. `aaii` has written 144 donation files and
    NOT ONE of them reaches a kilobyte; so have `earnings` (110), `tradingview` (112), `shipping`
    (125), `fear_greed` (195) and `weather` (126). 812 files between them, no payload in any of
    them, every age-based fence on this desk green for their entire lives. That is the shape this
    function exists to separate from a healthy organ having one quiet write.
    """
    cands = _candidates(root, rels)
    if not cands:
        return None, None, 0
    payload: tuple[float, str, int] | None = None
    trivial_seen = 0
    for rec in cands:
        if is_trivial(root / rec[1])[0]:
            trivial_seen += 1
        elif payload is None:
            payload = rec
    return cands[0], payload, trivial_seen


def _newest(root: Path, rels: Iterable[str]) -> tuple[float, str | None, int]:
    """(mtime, path, bytes) of the newest existing file among these repo-relative paths."""
    best: tuple[float, str | None, int] = (0.0, None, 0)
    for rel in rels:
        p = root / rel
        try:
            if p.is_dir():
                #: TWO LEVELS, bounded. The desk's declared inputs are directories as often as
                #: files, and the commonest one -- `desks/mt5/data/intelligence/` -- holds only
                #: SEAT DIRECTORIES at the top level. A one-level walk finds no file in it and
                #: reports the busiest input on the desk as absent.
                scanned = 0
                for f in p.iterdir():
                    if scanned > 4000:
                        break
                    scanned += 1
                    if f.is_file():
                        st = f.stat()
                        if st.st_mtime > best[0]:
                            best = (st.st_mtime, _norm(f.relative_to(root)), st.st_size)
                    elif f.is_dir():
                        for g in f.iterdir():
                            scanned += 1
                            if scanned > 4000:
                                break
                            if g.is_file():
                                st = g.stat()
                                if st.st_mtime > best[0]:
                                    best = (st.st_mtime, _norm(g.relative_to(root)), st.st_size)
            elif p.is_file():
                st = p.stat()
                if st.st_mtime > best[0]:
                    best = (st.st_mtime, rel, st.st_size)
        except OSError:
            continue
    return best


def _budget_s(organ: Organ) -> int:
    """How long this organ may be silent before silence is a fault. Its own declaration where it
    has one; otherwise a day, which is long enough that a quiet hour is never a defect."""
    for key in ("max_silence_s", "cadence_s"):
        raw = organ.detail.get(key)
        if raw:
            try:
                value = int(float(raw))
            except (TypeError, ValueError):
                continue
            return max(6 * 3600, value * (1 if key == "max_silence_s" else 3))
    return 24 * 3600


def chain_for(organ: Organ, *, root: Path, now: float,
              mirror: bool) -> dict[str, dict[str, Any]]:
    """The seven links, each measured or each honestly UNMEASURED. Never inferred from existence."""
    out: dict[str, dict[str, Any]] = {}
    budget = _budget_s(organ)

    # 1. CODE -------------------------------------------------------------------------------
    if not organ.code_paths:
        out["code"] = _link(UNMEASURED, "no roster names a code path for this organ, so whether "
                                        "it is real code cannot be read from this tree")
    else:
        present = sorted(p for p in organ.code_paths if (root / p).is_file())
        missing = sorted(set(organ.code_paths) - set(present))
        if present:
            out["code"] = _link(REAL, f"{len(present)} declared code path(s) exist on disk",
                                code_paths=present[:4], missing=missing[:4])
        else:
            out["code"] = _link(BROKEN, "every declared code path is absent from this tree: "
                                        f"{missing[:4]}", missing=missing[:4])

    # 2. CLOCK ------------------------------------------------------------------------------
    if organ.clocked is True and organ.clock:
        out["clock"] = _link(REAL, f"scheduled by {organ.clock}", clock=organ.clock)
    elif organ.clocked is False or (organ.detail.get("verdict") == "NO_CLOCK"):
        out["clock"] = _link(BROKEN, "nothing in this repository schedules it: no systemd unit, "
                                     "box task or cycle leg")
    else:
        out["clock"] = _link(UNMEASURED, "no roster that saw this organ declares a schedule for "
                                         "it, so whether it is clocked is unread here")

    # 3. INPUT ------------------------------------------------------------------------------
    if not organ.inputs:
        out["input"] = _link(UNMEASURED,
                             "this organ declares NO input. The desk has no input contract -- 1 "
                             "of 1,409 registry specs fills the field -- so an organ reading a "
                             "file that stopped updating cannot be told from one reading a live "
                             "one. That is a gap in the contract, not a clean bill of health")
    elif mirror:
        out["input"] = _link(UNMEASURED, "this checkout is a mirror of the host that runs the "
                                         "clocks, so an old input here is not a stale input")
    else:
        mtime, path, size = _newest(root, organ.inputs)
        if mtime <= 0:
            out["input"] = _link(BROKEN, f"every declared input is absent: "
                                         f"{sorted(organ.inputs)[:3]}",
                                 inputs=sorted(organ.inputs)[:4])
        else:
            age = now - mtime
            trivial, note = is_trivial(root / path) if path else (False, "")
            if age > budget:
                out["input"] = _link(BROKEN,
                                     f"its freshest input ({path}) last changed "
                                     f"{age / 3600.0:.1f}h ago, past the {budget / 3600.0:.0f}h "
                                     "budget: this organ is reading a file that stopped updating",
                                     input_path=path, input_age_h=round(age / 3600.0, 2))
            elif trivial:
                out["input"] = _link(BROKEN,
                                     f"its freshest input ({path}) is fresh and EMPTY: {note}. A "
                                     "refresh that lands nothing is the fred.json shape",
                                     input_path=path, input_bytes=size)
            else:
                out["input"] = _link(REAL, f"{path} changed {age / 3600.0:.1f}h ago ({note})",
                                     input_path=path, input_age_h=round(age / 3600.0, 2))

    # 4. ARTIFACT ---------------------------------------------------------------------------
    if not organ.artifacts:
        out["artifact"] = _link(UNMEASURED, "this organ declares no artifact, so nothing here can "
                                            "measure whether it produced. rc=0 is not evidence")
    elif mirror:
        out["artifact"] = _link(UNMEASURED, "this checkout holds none of the clocks, so an old "
                                            "artifact here is a stale mirror, not a dark organ")
    else:
        newest, payload, n_trivial = _newest_payload(root, organ.artifacts)
        if newest is None:
            out["artifact"] = _link(BROKEN,
                                    "it has NEVER produced: no declared artifact exists anywhere "
                                    f"in this tree ({sorted(organ.artifacts)[:3]})",
                                    artifacts=sorted(organ.artifacts)[:4])
        elif payload is None:
            out["artifact"] = _link(BROKEN,
                                    f"EVERY ONE of its {n_trivial} most recent artifacts is "
                                    f"TRIVIAL -- newest {newest[1]} at {newest[2]} bytes, "
                                    f"{(now - newest[0]) / 3600.0:.1f}h old. It runs, it writes, "
                                    "and it donates nothing; every age-only fence on this desk "
                                    "reads that as healthy",
                                    artifact=newest[1], artifact_bytes=newest[2],
                                    artifact_age_h=round((now - newest[0]) / 3600.0, 2),
                                    trivial_writes=n_trivial)
        else:
            age = now - payload[0]
            if age > budget:
                out["artifact"] = _link(BROKEN,
                                        f"its last artifact with a payload ({payload[1]}) moved "
                                        f"{age / 3600.0:.1f}h ago, past the "
                                        f"{budget / 3600.0:.0f}h silence budget"
                                        + (f"; the {n_trivial} writes since were all trivial"
                                           if n_trivial else ""),
                                        artifact=payload[1], artifact_bytes=payload[2],
                                        artifact_age_h=round(age / 3600.0, 2),
                                        trivial_writes=n_trivial)
            else:
                out["artifact"] = _link(REAL,
                                        f"{payload[1]} carried {payload[2]} bytes "
                                        f"{age / 3600.0:.1f}h ago",
                                        artifact=payload[1], artifact_bytes=payload[2],
                                        artifact_age_h=round(age / 3600.0, 2),
                                        trivial_writes=n_trivial)

    # 5. PIPELINE ---------------------------------------------------------------------------
    reached = organ.detail.get("cells_reached_judge")
    cells = organ.detail.get("unique_cells")
    if reached is None and cells is None:
        out["pipeline"] = _link(UNMEASURED, "no funnel row exists for this organ, so whether any "
                                            "of its output reached data/intelligence -> compiler "
                                            "-> docket -> sealed judge is unmeasured")
    elif (reached or 0) > 0:
        out["pipeline"] = _link(REAL, f"{int(reached or 0)} of its cells reached the canonical "
                                      f"pipeline (out of {int(cells or 0)} unique)",
                                cells_reached_judge=int(reached or 0),
                                unique_cells=int(cells or 0))
    elif (cells or 0) > 0:
        out["pipeline"] = _link(BROKEN,
                                f"{int(cells or 0)} unique cell(s) and NONE reached the judge: "
                                f"{str(organ.detail.get('reach_cause') or '')[:160]}",
                                unique_cells=int(cells or 0))
    else:
        out["pipeline"] = _link(BROKEN, "it donated no cell to the canonical pipeline in the "
                                        "census window")

    # 6. YIELD ------------------------------------------------------------------------------
    certs = organ.detail.get("certificates_attributed")
    judged = organ.detail.get("cells_judged")
    if certs is None and judged is None:
        out["yield"] = _link(UNMEASURED, "no verdict has ever come back naming this organ, so its "
                                         "survivor yield is unmeasured -- which is a finding "
                                         "about the attribution chain, never a zero")
    elif (certs or 0) > 0:
        out["yield"] = _link(REAL, f"{int(certs or 0)} certificate(s) name this organ",
                             certificates=int(certs or 0), cells_judged=int(judged or 0))
    elif (judged or 0) > 0:
        out["yield"] = _link(REAL, f"{int(judged or 0)} of its cells were judged and none "
                                   "certified: a measured yield of zero, which is an answer",
                             certificates=0, cells_judged=int(judged or 0))
    else:
        out["yield"] = _link(BROKEN, "nothing it produced has ever been judged")

    # 7. ALLOCATION -------------------------------------------------------------------------
    rate = organ.detail.get("survivors_per_compute_hour")
    hours = organ.detail.get("compute_hours")
    if rate is not None:
        out["allocation"] = _link(REAL, f"its compute is priced against a measured yield of "
                                        f"{float(rate):.4f} survivors/compute-hour",
                                  survivors_per_compute_hour=float(rate))
    elif hours:
        out["allocation"] = _link(BROKEN,
                                  f"it spent {float(hours):.3f} compute hour(s) and no allocator "
                                  "reads its yield: the budget it gets is not a function of what "
                                  "it returns",
                                  compute_hours=float(hours))
    else:
        out["allocation"] = _link(UNMEASURED, "no compute is attributed to this organ, so whether "
                                              "its allocation follows its yield is unmeasured")
    return out


# --------------------------------------------------------------------------- the yield ledger
def yield_ledger(organs: Mapping[str, Organ], *,
                 exploration_floor: float = EXPLORATION_FLOOR) -> dict[str, Any]:
    """Survivor yield per unit compute, per producer, with the exploration floor applied.

    THE MEASUREMENT THE DESK NEVER HAD. `search_populations.py` counts each of its nine
    populations as far as `donated` and stops; `compute_economics` prices wall hours per
    department and reports `survivors_per_wall_hour: null` for all 23. Joining the attribution
    lane's per-producer certificate table to the per-producer compute hours is what turns two
    half-measurements into a rate.

    THE FLOOR IS THE POINT, not a softener. `share` is what a yield-proportional split would give;
    `floor_share` is what this ledger actually publishes, with `exploration_floor` of the budget
    divided equally among producers whose yield is UNMEASURED or zero. A producer therefore
    starves and is never eliminated, and a search method cannot be permanently killed by a run of
    bad luck. Nothing here is applied to anything: it is an ORDER, published for the allocator.
    """
    rows: list[dict[str, Any]] = []
    for oid, organ in organs.items():
        hours = organ.detail.get("compute_hours")
        certs = organ.detail.get("certificates_attributed")
        judged = organ.detail.get("cells_judged")
        cells = organ.detail.get("unique_cells")
        reached = organ.detail.get("cells_reached_judge")
        if not hours and not cells and not certs:
            continue
        h = float(hours or 0.0)
        c = float(certs or 0.0)
        rate = (c / h) if h > 0 else None
        per_1000 = ((c * 1000.0 / float(cells)) if cells else None)
        rows.append({
            "producer": oid,
            "kind": organ.kind,
            "compute_hours": round(h, 4),
            "unique_cells": int(cells or 0),
            "cells_reached_judge": int(reached or 0),
            "cells_judged": int(judged or 0),
            "certificates": int(c),
            "survivors_per_compute_hour": (None if rate is None else round(rate, 6)),
            "survivors_per_1000_unique": (None if per_1000 is None else round(per_1000, 4)),
            "measured": bool(h > 0 and (judged or certs)),
        })

    measured = [r for r in rows if r["measured"] and (r["survivors_per_compute_hour"] or 0) > 0]
    unmeasured = [r for r in rows if r not in measured]
    total_rate = sum(float(r["survivors_per_compute_hour"] or 0.0) for r in measured)
    for row in rows:
        row["share"] = 0.0
        row["floor_share"] = 0.0
    if total_rate > 0:
        for row in measured:
            row["share"] = round(float(row["survivors_per_compute_hour"] or 0.0) / total_rate, 6)
            row["floor_share"] = round(row["share"] * (1.0 - exploration_floor), 6)
    if unmeasured:
        #: THE FLOOR, divided equally. A producer with no track record is not evidence of a bad
        #: producer -- it is evidence the desk has not looked, and a share of zero would make sure
        #: it never does.
        each = round(exploration_floor / len(unmeasured), 8) if total_rate > 0 else round(
            1.0 / len(unmeasured), 8)
        for row in unmeasured:
            row["floor_share"] = each
    rows.sort(key=lambda r: (-(r["survivors_per_compute_hour"] or -1.0), -r["unique_cells"]))
    zero_yield_compute = sorted(
        (r for r in rows if r["compute_hours"] > 0 and r["certificates"] == 0),
        key=lambda r: -r["compute_hours"])
    return {
        "law": ("SURVIVOR YIELD PER UNIT COMPUTE, PER GENERATOR. The existing populations, "
                "scientists and miners compete on DOWNSTREAM yield, not on how much they emit."),
        "boundary": BOUNDARY,
        "exploration_floor": exploration_floor,
        "n_rows": len(rows),
        "n_with_measured_rate": len(measured),
        "n_unmeasured_on_the_floor": len(unmeasured),
        "rations_the_judge": False,
        "top_by_yield": rows[:20],
        "zero_yield_compute": zero_yield_compute[:20],
        "rows": rows,
    }


# ------------------------------------------------------------------------------- the census
def load_feeders(root: Path | None = None) -> dict[str, Any]:
    """Every roster and every yield source, read from the artifacts that already exist."""
    base = root or ROOT
    reports = base / "desks" / "mt5" / "reports"
    names = {
        "producer_census": "PRODUCER_CENSUS.json",
        "productivity": "PRODUCTIVITY_CENSUS.json",
        "dead_architecture": "DEAD_ARCHITECTURE.json",
        "component_registry": "COMPONENT_REGISTRY.json",
        "sandbox": "SANDBOX_LIVENESS.json",
        "sandbox_roster": "SANDBOX_ROSTER.json",
        "attribution": "ATTRIBUTION_COVERAGE.json",
        "compute_economics": "COMPUTE_ECONOMICS.json",
    }
    out: dict[str, Any] = {}
    for key, name in names.items():
        doc = _read_json(reports / name)
        out[key] = doc
        out[f"{key}__missing"] = doc is None
    out["capability_nodes"] = capability_nodes(base)
    out["capability_nodes__missing"] = not out["capability_nodes"]
    return out


def _certificates_by_producer(attribution: Mapping[str, Any] | None) -> dict[str, int]:
    """The attribution lane's own per-producer certificate table. CONSUMED, never recomputed:
    `desks/mt5/research/certificate_provenance.py` owns that join and got 174/174 named."""
    certs = (attribution or {}).get("certificates")
    if not isinstance(certs, dict):
        return {}
    for key in ("by_producer", "by_producer_top", "producers"):
        table = certs.get(key)
        if isinstance(table, dict):
            return {str(k): int(v) for k, v in table.items()
                    if isinstance(v, (int, float))}
    return {}


def _compute_hours_by_producer(productivity: Mapping[str, Any] | None) -> dict[str, float]:
    out: dict[str, float] = {}
    for row in (productivity or {}).get("producers", []) or []:
        if isinstance(row, dict) and row.get("compute_hours"):
            out[str(row.get("producer"))] = float(row["compute_hours"])
    return out


def census(*, root: Path | None = None, feeders: Mapping[str, Any] | None = None,
           now: float | None = None, mirror: bool | None = None) -> dict[str, Any]:
    """Every claimed organ, its chain, and the yield that orders research compute."""
    base = root or ROOT
    t = now if now is not None else time.time()
    feed = dict(feeders) if feeders is not None else load_feeders(base)
    if mirror is None:
        try:
            from libs.ops.producer_census import runs_clocks_here
            mirror = runs_clocks_here(base) is not True
        except Exception:                                     # pragma: no cover - import guard
            mirror = False

    claims = (claims_from_producer_census(feed.get("producer_census"))
              + claims_from_productivity(feed.get("productivity"))
              + claims_from_component_registry(feed.get("component_registry"))
              + claims_from_capability_graph(feed.get("capability_nodes"))
              + claims_from_sandbox(feed.get("sandbox"))
              + claims_from_sandbox_roster(feed.get("sandbox_roster"))
              + claims_from_dead_architecture(feed.get("dead_architecture")))
    organs, reconciliation = reconcile(claims)

    certs = _certificates_by_producer(feed.get("attribution"))
    for name, n in certs.items():
        organ = organs.get(name)
        if organ is not None:
            organ.detail["certificates_attributed"] = n
    rates = ((feed.get("compute_economics") or {}).get("by_department") or {})
    for dept, rec in rates.items():
        if not isinstance(rec, dict):
            continue
        rate = rec.get("survivors_per_wall_hour")
        organ = organs.get(str(dept))
        if organ is not None and rate is not None:
            organ.detail["survivors_per_compute_hour"] = rate

    for organ in organs.values():
        organ.chain = chain_for(organ, root=base, now=t, mirror=bool(mirror))

    link_counts = {link: {REAL: 0, BROKEN: 0, UNMEASURED: 0} for link in LINKS}
    for organ in organs.values():
        for link in LINKS:
            link_counts[link][organ.chain[link]["verdict"]] += 1

    def _n(link: str, verdict: str = REAL) -> int:
        return link_counts[link][verdict]

    ledger = yield_ledger(organs)
    rows: list[dict[str, Any]] = [{
        "organ": organ.organ_id,
        "kind": organ.kind,
        "rosters": sorted(organ.rosters),
        "clock": organ.clock,
        "code_paths": sorted(organ.code_paths)[:4],
        "chain": {link: organ.chain[link]["verdict"] for link in LINKS},
        "first_break": next((link for link in LINKS
                             if organ.chain[link]["verdict"] == BROKEN), None),
        "why": {link: organ.chain[link]["why"] for link in LINKS},
        "evidence": {link: {k: v for k, v in organ.chain[link].items()
                            if k not in ("verdict", "why")} for link in LINKS},
    } for organ in sorted(organs.values(), key=lambda o: o.organ_id)]

    producing = _n("artifact")
    worst = sorted(
        (r for r in rows if r["chain"]["clock"] == REAL and r["chain"]["artifact"] == BROKEN),
        key=lambda r: r["organ"])
    emits_nothing_reaches = [r for r in rows if r["chain"]["pipeline"] == BROKEN
                             and r["chain"]["artifact"] == REAL]
    #: THE fred.json POPULATION, by name. An organ whose every recent write is trivial runs on a
    #: clock, exits zero, refreshes its own timestamp and donates nothing -- and until the
    #: payload test existed, nothing on this desk could tell it from a working one.
    receipts = [r for r in rows
                if (r["evidence"].get("artifact") or {}).get("trivial_writes")
                and r["chain"]["artifact"] == BROKEN
                and "EVERY ONE" in str((r["why"] or {}).get("artifact") or "")]
    return {
        "at": now_iso(),
        "law": ("EVERY CLAIMED ORGAN IS ONE CHAIN: real code -> a clock -> a fresh real input -> "
                "a non-trivial artifact -> the canonical pipeline -> a measured survivor yield -> "
                "an allocation that follows that yield. An organ is as strong as its first broken "
                "link, and a link nobody measured reads UNMEASURED, never REAL."),
        "boundary": BOUNDARY,
        "mirror_host": bool(mirror),
        "feeders_missing": sorted(k[:-9] for k in feed if k.endswith("__missing") and feed[k]),
        "reconciliation": reconciliation,
        "totals": {
            "organs_claimed": len(organs),
            "real_code": _n("code"),
            "clocked": _n("clock"),
            "fresh_real_input": _n("input"),
            "producing": producing,
            "reaching_pipeline": _n("pipeline"),
            "with_measured_yield": _n("yield"),
            "allocation_follows_yield": _n("allocation"),
        },
        "by_link": link_counts,
        "clocked_but_not_producing": [r["organ"] for r in worst],
        "n_clocked_but_not_producing": len(worst),
        "produces_but_reaches_nothing": [r["organ"] for r in emits_nothing_reaches][:40],
        "n_produces_but_reaches_nothing": len(emits_nothing_reaches),
        "writes_only_receipts": [r["organ"] for r in receipts][:40],
        "n_writes_only_receipts": len(receipts),
        "yield_ledger": ledger,
        "rows": rows,
    }


# ---------------------------------------------------------------------------------- the fence
def silent_stops(doc: Mapping[str, Any], previous: Mapping[str, Any] | None) -> list[dict[str,
                                                                                          Any]]:
    """Organs that were PRODUCING in the last census and produce nothing now.

    THIS IS THE STALL, NOT A CAUSE. It does not ask why an organ stopped -- a timeout, a broken
    donation door, a credential on the wrong machine, a cause nobody has met yet. It asks only
    whether something that demonstrably worked has quietly stopped working, which is the one
    question that survives the next unknown failure.
    """
    if not previous:
        return []
    before = {str(r.get("organ")): r for r in previous.get("rows", []) or []}
    #: AND IT MUST NOT BLINK. A stop reported only at the instant of the transition fails the
    #: gate for exactly one pass: the NEXT census compares broken against broken, sees no
    #: transition, and goes green over an organ that is still dark. That is the silence this file
    #: exists to end, re-entering through the comparison itself. So an unresolved stop is CARRIED
    #: FORWARD from the previous census's own list until the organ produces again or somebody
    #: names it in the debt -- fix it or declare it, never wait it out.
    carried = {str(s.get("organ")) for s in (previous.get("silent_stops") or ())
               if isinstance(s, dict)}
    out: list[dict[str, Any]] = []
    for row in doc.get("rows", []) or []:
        oid = str(row.get("organ"))
        if (row.get("chain") or {}).get("artifact") != BROKEN:
            continue
        was = before.get(oid)
        transition = was is not None and (was.get("chain") or {}).get("artifact") == REAL
        if not transition and oid not in carried:
            continue
        out.append({"organ": oid,
                    "since": ("this pass" if transition else "an earlier pass, still unresolved"),
                    "why": str((row.get("why") or {}).get("artifact") or "")[:240]})
    return sorted(out, key=lambda r: r["organ"])


def breach(doc: Mapping[str, Any], *, previous: Mapping[str, Any] | None = None,
           debt: Mapping[str, Any] | None = None) -> list[str]:
    """Why this census is a fence failure. Empty means nothing measurable has quietly stopped."""
    out: list[str] = []
    if doc.get("mirror_host"):
        return out
    excused = set((debt or {}).get("silent_stops") or ())
    stops = [s for s in silent_stops(doc, previous) if s["organ"] not in excused]
    if stops:
        names = [s["organ"] for s in stops]
        out.append(f"{len(stops)} organ(s) were producing at the last census and produce nothing "
                   f"now: {names[:8]}. A department that stops producing must FAIL, not go quiet")
    ratchet = (debt or {}).get("max_ambiguous_code_paths")
    n_amb = int((doc.get("reconciliation") or {}).get("n_ambiguous_code_paths") or 0)
    if ratchet is not None and n_amb > int(ratchet):
        out.append(f"{n_amb} code paths are claimed by more than one organ against a ratchet of "
                   f"{ratchet}: the join is losing resolution, and a census that cannot say which "
                   f"organ a file belongs to cannot credit its production to one")
    floor = (doc.get("yield_ledger") or {}).get("exploration_floor")
    if floor is None or float(floor) <= 0.0:
        out.append("the yield ledger publishes no exploration floor: a yield order with no "
                   "exploration budget can permanently kill a search method on a run of bad luck")
    if (doc.get("yield_ledger") or {}).get("rations_the_judge"):
        out.append("the yield ledger claims to ration what reaches the judge, which is forbidden: "
                   "multiplicity is pinned at fixed_trial_count 109 and judging more is free")
    return out
