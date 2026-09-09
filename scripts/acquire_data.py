#!/usr/bin/env python3
"""ADAPTIVE DATA ACQUISITION AGENT (triage #93) -- what to acquire NEXT, ranked on measurement.

WHY #93 SAT UNBUILT. It was blocked on "Information Advantage Score (item 17) existing first",
item 17 shipped 2026-07-29, and the row has been UNBLOCKED and untouched since -- caught
mechanically by check_triage_disposition, not by anyone re-reading it.

WHAT MAKES IT ADAPTIVE, AND WHY THE OBVIOUS BUILD WOULD NOT HAVE BEEN. `research_cio.py`'s
INFORMATION ADVANTAGE SCORE is a hardcoded table: uniqueness, predictive power, persistence and
replication difficulty, all hand-assigned per source class. Ranking acquisitions by that table
produces a confident-looking order built entirely out of somebody's priors, dressed in the
vocabulary of measurement -- the exact failure libs/doctrine/contribution.py refuses, and the
reason a "made-up basis" is rejected at construction there.

So this agent scores on what the desk has actually LEARNED, and the learning enters through one
term: the ontology's own record of attempts and survivors per frontier region.

  * A source that would inform regions the desk has hammered with ZERO survivors is scored DOWN.
    That is evidence, gathered here, that this class of data is barren for this desk -- and it is
    the term that makes the ranking move as the desk works, which a static table cannot do.
  * A source that would REOPEN an under-explored region is scored UP. `ontology.map_dataset`
    already answers "which questions would this dataset help answer", and `ontology.priority`
    already folds in exhaustion with a revival floor -- because a barren region reopened by new
    data is precisely where a desk finds what everyone else gave up on.
  * REPLICATION DIFFICULTY MULTIPLIES, exactly as in EVIG. A source anyone can pull yields edge
    that is already priced; the desk's own measured advantage ranks self-recorded tape at 1.03
    against 0.37 for the next best thing.
  * COST DIVIDES. Free-and-adequate beats paid-and-marginal every time under a log objective.

WHAT IT REFUSES. A candidate whose grade, cost or region mapping cannot be read is scored
UNMEASURED and ranked with an honest penalty -- never given a plausible default. That is WS-005
applied at construction: the least-known source must not become the most attractive one by virtue
of nobody having checked it.

NO ACQUISITION AUTHORITY. This ranks and explains. It spends nothing, signs nothing and starts no
collector; a human or a later organ acts on the ordering. No keys, no order paths.

THE MAP'S FIRST MACHINE WRITER (2026-09-08). `data/data_universe_map.json` holds 190 sources with
real licence and PIT verdicts, and until this date it had NO PRODUCER: grepping for a writer
returned readers only (acquire_data, max_audit, run_cadence, blind_trigger, orphan_scan), so the
six dig seats that would write it are the only path -- and they report `last=never` on missing
credentials. A map nothing can produce is a schedule pointing at a file.

So this registers what the desk's own miners have already PROBED: dataset pages the deep-forest
miner and the world crawler fetched, with the endpoints they found. Three fences, and they are
what make a machine writer safe on a file humans curate:

    REGISTRATION IS NOT A GRADE. Every appended row is `grade: UNVERIFIED` -- the map's own
    vocabulary for "found this session, not opened/confirmed first-party, DO NOT feed a live
    signal" -- and carries the probe result that justifies exactly that much.
    A HUMAN OR LLM GRADE IS NEVER OVERWRITTEN. A source already in the map by url or by name is
    skipped whole: not re-graded, not re-described, not touched. The writer only APPENDS.
    THE MANDATE IS ENFORCED AT THE WRITE. A probe naming a crypto-exchange venue is refused by
    `mechanism_claims.forbidden_venue` before it can reach the map.
"""
from __future__ import annotations

import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.hypmax.evig import information_gain  # noqa: E402
from libs.hypmax.ontology import (  # noqa: E402
    SEED_QUESTIONS,
    load_state,
    map_dataset,
    priority,
)

UNIVERSE = ROOT / "data/data_universe_map.json"
ONTOLOGY_STATE = ROOT / "data/ontology_state.json"
MOAT = ROOT / "data/moat_mine.json"
REPORT = ROOT / "data/acquisition_plan.json"
HISTORY = ROOT / "data/acquisition_history.jsonl"
#: Where the miners write what they PROBED. Dataset-kind discovery rows carry the url, the host,
#: the endpoints found and when the desk could first have read them -- a probe result, not a
#: claim about quality.
PROBE_DIR = ROOT / "desks/mt5/data/intelligence/world"
PROBE_GLOB = "discoveries_*.json"
#: The grade every machine-registered row carries, in the map's own vocabulary.
MACHINE_GRADE = "UNVERIFIED"
MACHINE_ORIGIN = "machine:acquire_data (miner probe, never opened by a human)"

#: Source grade -> (P(the data is usable as claimed), why). Grades are the digger's own vocabulary
#: and already carry a verification level, so this maps VERIFICATION to a probability rather than
#: inventing one. A grade nobody assigned falls to the unmeasured floor, never to a middling guess.
GRADE_P: dict[str, tuple[float, str]] = {
    "verified-clean": (0.90, "URL opened and directly confirmed"),
    "needs-monitoring": (0.60, "corroborated but never diffed against ground truth"),
    "reconstructable": (0.50, "methodology is public; the series must be rebuilt, not fetched"),
    "unverified": (0.25, "found, not confirmed -- the desk's own rule says do not adopt"),
    "destroyed-at-source": (0.02, "honest negative: no free path found this session"),
}
#: Applied when a candidate carries no grade at all. Deliberately BELOW the worst real grade: an
#: ungraded source is less known than one somebody looked at and rejected, and ranking it above
#: `unverified` would reward never checking.
UNGRADED_P = 0.01

#: Replication difficulty by access class -- how hard it is for a competitor to hold the same data.
#: Anchored to the desk's OWN measured advantage figures (self-recorded tape 1.03, next-best 0.37)
#: rather than to opinion, and everything public collapses toward the bottom because it must.
REPLICATION: dict[str, tuple[float, str]] = {
    "self-recorded": (1.03, "cannot be bought at any price -- our snapshots, from our clock"),
    "reconstructed": (0.55, "public inputs, private method: replicable only by redoing the work"),
    "gated-free": (0.37, "free but rate-limited or keyed -- a real if modest barrier"),
    "public": (0.10, "pullable in an afternoon by anyone, so any edge found is already priced"),
}

#: Relative cost, in the same units EVIG uses: 1.0 is one routine collector build.
COST: dict[str, float] = {
    "self-recorded": 3.0,      # a recorder, plus disk, plus supervision, forever
    "reconstructed": 2.0,      # rebuild the methodology and diff it
    "gated-free": 1.0,
    "public": 0.5,
}


def _rel(p: Path) -> str:
    """Display path, relative to the repo when it is inside it. `relative_to` RAISES on a path
    outside ROOT, so the unguarded version turned an honest 'the file is missing' report into a
    ValueError the moment the constant was repointed -- an error path that only breaks when it is
    needed is the worst kind."""
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return str(p)


def _read(p: Path):
    try:
        if not p.exists() or p.stat().st_size <= 2:
            return None
        return json.loads(p.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _grade_p(grade: str) -> tuple[float, str]:
    g = (grade or "").strip().lower()
    for key, (p, why) in GRADE_P.items():
        if key in g:
            return p, why
    return UNGRADED_P, ("NO GRADE RECORDED -- ranked below every graded source, including the "
                        "rejected ones. An unchecked source must never outrank a checked-and-poor "
                        "one, or the ranking rewards not looking")


def _access_class(entry: dict) -> str:
    """Access class from the entry's own fields, never guessed from the name."""
    blob = " ".join(str(entry.get(k, "")) for k in
                    ("access", "class", "kind", "notes", "why", "grade")).lower()
    if "self-record" in blob or "own recorder" in blob:
        return "self-recorded"
    # Prose, not an enum: the digger writes "rebuilt from the public methodology" as readily as
    # "reconstructable". Matching one spelling silently demoted real reconstructions to `public`,
    # which is the most-discounted class -- so the miss was expensive in exactly one direction.
    if any(w in blob for w in ("reconstruct", "rebuil", "re-deriv", "rederiv", "self-comput")):
        return "reconstructed"
    if "key" in blob or "rate-limit" in blob or "gated" in blob or "community" in blob:
        return "gated-free"
    return "public"


def score_candidate(name: str, entry: dict, state: dict) -> dict:
    """One acquisition candidate, scored EVIG-shaped on measured terms.

    score = P(usable) x information_gain(P) x replication_difficulty x region_priority / cost

    Multiplicative for the reason EVIG is: no term rescues a dead one. A perfectly unique source
    informing a region the desk has proved barren is still not worth acquiring, and a rich region
    reachable only through data everyone already has yields edge that is already priced.
    """
    desc = " ".join(str(entry.get(k, "")) for k in ("description", "notes", "why", "metrics"))
    regions = map_dataset(name, desc, SEED_QUESTIONS)
    grade = str(entry.get("grade", ""))
    p, p_why = _grade_p(grade)
    access = _access_class(entry)
    rep, rep_why = REPLICATION[access]
    cost = COST[access]

    # THE ADAPTIVE TERM. Region priority already folds in the desk's recorded attempts and
    # survivors with a revival floor, so a class of data the desk has worked to exhaustion scores
    # down HERE, from evidence, rather than being demoted by an author's opinion in a table.
    by_id = {q.id: q for q in SEED_QUESTIONS}
    prios = [priority(by_id[r], state=state) for r in regions if r in by_id]
    region_p = max(prios) if prios else 0.0
    worked = sum(int(state.get(r, {}).get("attempts", 0)) for r in regions)
    survived = sum(int(state.get(r, {}).get("survivors", 0)) for r in regions)

    score = p * information_gain(p) * rep * region_p / max(cost, 1e-6)
    unmeasured = (p == UNGRADED_P) or not regions
    return {
        "source": name,
        "score": round(score, 6),
        "p_usable": p,
        "grade": grade or "(none)",
        "access_class": access,
        "replication": rep,
        "cost": cost,
        "regions": regions[:8],
        "region_priority": round(region_p, 6),
        "desk_record": f"{survived} survivor(s) from {worked} attempt(s) in these regions",
        "unmeasured": unmeasured,
        "why": (
            f"{p_why}; {rep_why}; "
            + (f"informs {len(regions)} frontier region(s), best priority {region_p:.3f} "
               f"({survived}/{worked} survived there)"
               if regions else
               "MAPS TO NO FRONTIER REGION -- either genuinely off-thesis or the entry carries too "
               "little description to match. Scored zero rather than defaulted: a source nobody "
               "can say what it would answer is not an acquisition, it is a wish")),
    }


# ------------------------------------------------------------------ the machine writer

def _norm(s: object) -> str:
    """A url or name reduced to what makes two entries the same source."""
    t = str(s or "").strip().lower().rstrip("/")
    for p in ("https://", "http://", "www."):
        if t.startswith(p):
            t = t[len(p):]
    return t


def _entries(universe: dict) -> list[dict]:
    """Every source entry in the map, whatever shape its class holds."""
    out: list[dict] = []
    for v in (universe.get("sources") or {}).values():
        for e in (v if isinstance(v, list) else [v]):
            if isinstance(e, dict):
                out.append(e)
    return out


def _known(universe: dict) -> set[str]:
    """Everything the map already names, by url and by name. Membership here is a REFUSAL to
    write: the entry may carry a human licence verdict this script must never touch."""
    keys: set[str] = set()
    for e in _entries(universe):
        for field in ("url", "name", "host"):
            if e.get(field):
                keys.add(_norm(e[field]))
    return keys


def _forbidden(text: str) -> str | None:
    """The crypto-exchange fence, from the same table the miners use. A failure to import it is
    a REFUSAL to write, never a silent pass: an unenforceable mandate must stop the writer."""
    from libs.research.mechanism_claims import forbidden_venue
    return forbidden_venue(text)


def probe_rows(probe_dir: Path | None = None) -> list[dict]:
    """Dataset-kind discovery rows the miners have written, newest file last.

    THE PATH IS RESOLVED AT CALL TIME, NOT BOUND AS A DEFAULT. A `Path = PROBE_DIR` default
    captures the real directory when this module is imported, so repointing the constant --
    which is how every caller and every test aims this script at another tree -- silently does
    nothing and the run reads the live desk instead. Measured here the first time it ran.
    """
    probe_dir = PROBE_DIR if probe_dir is None else probe_dir
    rows: list[dict] = []
    try:
        files = sorted(probe_dir.glob(PROBE_GLOB))
    except OSError:
        return rows
    for f in files:
        doc = _read(f)
        for r in (doc if isinstance(doc, list) else []):
            if isinstance(r, dict) and str(r.get("kind") or "") == "dataset" and r.get("url"):
                rows.append(r)
    return rows


def _candidate_entry(r: dict, now: str) -> dict:
    """One probe as a map entry. The probe RESULT is the whole justification, and it is written
    down beside the grade so a human re-grading this row can see what was actually observed."""
    eps = int(r.get("n_endpoints") or 0)
    return {
        "name": str(r.get("title") or r.get("host") or r.get("url"))[:160],
        "url": str(r.get("url")),
        "host": str(r.get("host") or ""),
        "grade": MACHINE_GRADE,
        "origin": MACHINE_ORIGIN,
        "cost": "free",
        "verification": ("NOT opened or confirmed first-party; registered from a miner fetch. "
                         "DO NOT feed a live signal until a human or a dig seat grades it"),
        "probe": {"probed_at": str(r.get("available_time") or r.get("published") or now),
                  "registered_at": now, "n_endpoints": eps,
                  "endpoints": [str(e) for e in (r.get("endpoints") or [])[:12]],
                  "ground": r.get("ground"), "region": r.get("region"),
                  "language": r.get("language") or r.get("lang"),
                  "source": r.get("source"), "source_hash": r.get("source_hash")},
        "class": str(r.get("dataset_class") or "unclassified"),
        "note": (f"machine-registered: the miner fetched this page and found {eps} data "
                 f"endpoint(s). Registration is not adoption and not a licence verdict"),
    }


def merge_probes(universe: dict, rows: list[dict], *, now: str | None = None) -> dict:
    """Append every probed source the map does not already name. Returns the report.

    `universe` is mutated in place. Nothing that already exists is read, re-graded or rewritten:
    the only operation this function performs on the document is appending new entries and
    stamping `machine_updated` / `machine_writer`. The human `updated` date is left alone, so a
    reader can still see when a person last curated the file.
    """
    now = now or datetime.now(tz=UTC).isoformat()
    known = _known(universe)
    added: list[dict] = []
    skipped_known = 0
    refused: list[dict] = []
    for r in rows:
        key = _norm(r.get("url"))
        if not key:
            continue
        if key in known or _norm(r.get("title")) in known:
            skipped_known += 1
            continue
        blob = " ".join(str(r.get(k) or "") for k in ("title", "url", "host", "ground",
                                                      "dataset_class"))
        venue = _forbidden(blob)
        if venue:
            refused.append({"url": str(r.get("url")), "venue": venue})
            continue
        entry = _candidate_entry(r, now)
        cls = entry["class"]
        # `sources` is created only when there is something to put in it. A `setdefault` here
        # added an empty `sources` key to a map that had none, and since every reader resolves
        # the document as `universe.get("sources", universe)`, that empty key HID the whole
        # flat-shaped universe: a writer that adds nothing must leave no trace at all.
        sources = universe.setdefault("sources", {})
        bucket = sources.get(cls)
        if bucket is None:
            sources[cls] = [entry]
        elif isinstance(bucket, list):
            bucket.append(entry)
        else:
            # A human wrote this class as something other than a list. Its shape is not this
            # writer's to change, so the machine rows go beside it under their own key.
            sources.setdefault(f"{cls}__machine_probed", []).append(entry)
        known.add(key)
        added.append(entry)
    if added:
        universe["machine_updated"] = now
        universe["machine_writer"] = (
            "scripts/acquire_data.py registers miner-probed sources at grade "
            f"{MACHINE_GRADE} and never edits an existing entry: a human or LLM grade is "
            "final until a person changes it. Registration is not adoption.")
    return {"probes_read": len(rows), "added": len(added),
            "skipped_already_known": skipped_known, "refused_forbidden_venue": refused,
            "added_names": [e["name"] for e in added[:12]]}


def write_universe(universe: dict, path: Path | None = None) -> bool:
    """Resolved at call time for the reason `probe_rows` states: a bound default would write the
    live map however the constant was repointed."""
    path = UNIVERSE if path is None else path
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(universe, indent=1, ensure_ascii=False), "utf-8")
        return True
    except OSError:
        return False


def main() -> int:
    t0 = time.time()
    universe = _read(UNIVERSE)
    state = load_state(ONTOLOGY_STATE)
    moat = _read(MOAT) or {}

    if not isinstance(universe, dict) or not universe:
        out = {
            "ts": datetime.now(tz=UTC).isoformat(),
            "state": "NO SOURCE UNIVERSE",
            "reason": (f"{_rel(UNIVERSE)} absent or empty -- the digger publishes it "
                       "and data/ is gitignored, so this is expected in a fresh checkout and a "
                       "REAL blocker on the VPS. No ranking is offered: ranking zero candidates "
                       "would print an empty plan that reads like 'nothing worth acquiring'."),
            "next": "run the data-axis digger (ops/run_dataaxis_dig.sh) to publish the map",
            "candidates": 0,
        }
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(out, indent=1), "utf-8")
        print(f"acquire: NO SOURCE UNIVERSE -- {_rel(UNIVERSE)} absent. "
              "Ranking refused rather than faked.")
        return 0

    # REGISTER WHAT THE MINERS PROBED, BEFORE RANKING, so a source found this cycle is ranked
    # this cycle rather than a day later. A write failure is reported and never fatal: the
    # ranking is the job, and losing it because the map is read-only would be the worse trade.
    try:
        merged = merge_probes(universe, probe_rows())
        merged["written"] = bool(merged["added"]) and write_universe(universe)
    except Exception as exc:
        merged = {"probes_read": 0, "added": 0, "written": False,
                  "why": f"{type(exc).__name__}: {exc}"}

    entries = universe.get("sources", universe)
    rows = [score_candidate(str(k), v if isinstance(v, dict) else {"description": str(v)}, state)
            for k, v in entries.items()]
    rows.sort(key=lambda r: (-r["score"], r["source"]))
    for i, r in enumerate(rows, 1):
        r["rank"] = i

    measured = [r for r in rows if not r["unmeasured"]]
    out = {
        "ts": datetime.now(tz=UTC).isoformat(),
        "seconds": round(time.time() - t0, 2),
        "candidates": len(rows),
        "measured": len(measured),
        "registered": merged,
        "moat_coverage_pct": (moat.get("cumulative_coverage", {}) or {}).get("coverage_pct"),
        "plan": rows[:25],
        "top": rows[0]["source"] if rows else None,
        "note": (
            "score = P(usable) x information_gain(P) x replication_difficulty x region_priority "
            "/ cost. Multiplicative, like EVIG: no term rescues a dead one. The ADAPTIVE term is "
            "region_priority, which reads the ontology's recorded attempts and survivors -- so a "
            "class of data this desk has worked to exhaustion falls from EVIDENCE rather than "
            "from an author's opinion in a table. An ungraded source ranks below every graded "
            "one including the rejected ones, because a ranking that rewards not looking is "
            "worse than no ranking."),
        "authority": ("RANK AND REGISTER. It spends nothing, signs nothing and starts no "
                      f"collector. It appends miner-probed sources to {_rel(UNIVERSE)} at grade "
                      f"{MACHINE_GRADE} and never edits an existing entry -- a human or LLM "
                      "grade is final until a person changes it."),
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(out, indent=1), "utf-8")
    with HISTORY.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"ts": out["ts"], "candidates": len(rows),
                             "measured": len(measured),
                             "top": out["top"]}, separators=(",", ":")) + "\n")

    print(f"acquire: {len(rows)} candidate(s), {len(measured)} measured | {out['seconds']}s")
    print(f"  registered: {merged['added']} new source(s) at {MACHINE_GRADE} from "
          f"{merged.get('probes_read', 0)} probe(s), "
          f"{merged.get('skipped_already_known', 0)} already known, "
          f"{len(merged.get('refused_forbidden_venue') or [])} refused (forbidden venue)"
          + ("" if merged.get("written") or not merged["added"] else "  [MAP NOT WRITTEN]"))
    for r in rows[:8]:
        flag = "    " if not r["unmeasured"] else "UNM "
        print(f"  [{flag}] #{r['rank']:<2} {r['source'][:38]:<38} {r['score']:.5f}  "
              f"{r['access_class']:<14} {r['desk_record']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
