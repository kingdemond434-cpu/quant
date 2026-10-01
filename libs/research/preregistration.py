"""Pre-registration: the hypothesis is hashed before the result exists.

Before an experiment runs it writes what it claims and how it will be judged:

    hypothesis, mechanism, direction, variables, transformations, universe, horizon,
    parameters allowed, acceptance criterion, falsifier

and the hash of that card is the experiment's name from then on. A verdict that arrives
without the card's hash, or with a card whose hash no longer matches, is a reinterpretation
after the fact -- the exact move p-hacking needs -- and `check` reports it. No AI, and no
person, gets to decide what the hypothesis was after seeing what the data said.

APPEND-ONLY, one card per line in `data/preregistrations.jsonl`. `register` returns the hash;
proposers carry it on the donated candidate as `prereg_hash`; the docket writer
(`register_docket`, via `libs/research/prereg_join.py`) cards every never-judged EXECUTABLE cell
by its `spec_id` before the judge reads the docket; `hypothesis_graph.record_gauntlet_verdicts`
stamps every verdict PREREGISTERED or POST_HOC and puts it on the graph node; and
`scripts/check_preregistration.py` re-derives the join and publishes its rate. See THE JOIN
below for why none of that held until 2026-09-30.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Container, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from libs.research.hypothesis_graph import node_id, node_id_for_spec

ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / "desks" / "mt5" / "data" / "preregistrations.jsonl"
REQUIRED: tuple[str, ...] = ("hypothesis", "mechanism", "direction", "variables", "universe",
                             "horizon", "parameters_allowed", "acceptance_criterion",
                             "falsifier")


def card_hash(card: dict[str, Any]) -> str:
    body = {k: card.get(k) for k in REQUIRED}
    body["transformations"] = card.get("transformations")
    return hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()[:16]


def validate(card: dict[str, Any]) -> list[str]:
    return [k for k in REQUIRED if not card.get(k)]


def register(card: dict[str, Any], *, source: str, path: Path = LEDGER,
             spec_id: str | None = None) -> str:
    missing = validate(card)
    if missing:
        raise ValueError(f"pre-registration incomplete: missing {missing}")
    h = card_hash(card)
    row = {"prereg_hash": h, "registered_utc": datetime.now(tz=UTC).isoformat(),
           "source": source, **{k: card.get(k) for k in REQUIRED},
           "transformations": card.get("transformations")}
    if spec_id:
        # THE JOIN KEY, outside the hash on purpose: it is DERIVED from the executable spec the
        # card already commits to (symbol, family, params), so it adds no claim the hash could
        # be asked to protect -- and every card written before it existed keeps its hash.
        row["spec_id"] = spec_id
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, default=str) + "\n")
    return h


def cards(path: Path = LEDGER) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    try:
        for ln in path.read_text("utf-8").splitlines():
            if ln.strip():
                r = json.loads(ln)
                out[str(r.get("prereg_hash"))] = r
    except (OSError, ValueError):
        pass
    return out


#: The keys a proposer ACTUALLY uses to declare a holding period, measured across the whole
#: donation corpus on 2026-09-23: hold_bars 851, horizon 616, hold_days 110, ttl_bars 12.
#: `horizon_days` -- the only bar-count key the original derivation read besides hold_bars and
#: ttl_bars -- occurs ZERO times anywhere. That is why `validate` reported `horizon` missing on
#: 58.8% of rows, `register` raised, and a bare except above swallowed it: every donation the
#: desk made between 2026-09-04 and 2026-09-23 went to the gauntlet unpreregistered. The list is
#: MEASURED, not guessed; extend it from the corpus, never from imagination.
HORIZON_KEYS: tuple[str, ...] = ("hold_bars", "horizon", "hold_days", "ttl_bars", "horizon_days")

#: What a card says when the proposer declared no such thing. A card may NEVER invent a horizon
#: or a parameter set it was not given -- that would forge the exact guarantee pre-registration
#: exists to provide. It records the absence instead, under a token any reader can grep: the
#: specification is still frozen before the verdict, and the fact that it did not pin a holding
#: period is ON the card rather than hidden behind a card that was never written at all.
UNDECLARED = "UNDECLARED"

#: Stamped on a donated row that could not be pre-registered, so the absence is a POSITIVE,
#: named record instead of a silent gap. A thing that fails silently is indistinguishable from a
#: thing that had nothing to do.
PREREG_FAILED = "PREREG_FAILED"

#: Stamped by the census on rows donated BEFORE the fix, whose evidence has already been seen.
#: These are never backfilled -- a card written after the verdict is a forgery -- so they carry
#: this instead, permanently, and any certificate resting on one can be read for what it is.
RETROSPECTIVELY_UNPREREGISTERED = "RETROSPECTIVELY_UNPREREGISTERED"


def horizon_of(params: dict[str, Any]) -> Any:
    """The declared holding period, or UNDECLARED. Never a fabricated default."""
    for k in HORIZON_KEYS:
        v = params.get(k)
        if v not in (None, "", [], {}):
            return v
    return UNDECLARED


def from_candidate(c: dict[str, Any]) -> dict[str, Any]:
    """A proposer candidate has everything a card needs; write it in the card's vocabulary."""
    params = c.get("params") or {}
    syms = c.get("symbols") if isinstance(c.get("symbols"), list) else None
    universe = [c["symbol"]] if c.get("symbol") else [s for s in (syms or []) if s]
    return {"hypothesis": c.get("title") or c.get("mechanism"),
            "mechanism": c.get("mechanism"),
            "direction": (params.get("side_mode") or params.get("side") or "as recipe"),
            # An empty parameter set is a real declaration ("nothing here is tuned"), but it is
            # indistinguishable from a proposer that simply did not populate params -- so it is
            # recorded as UNDECLARED rather than claimed as the stronger of the two readings.
            "variables": sorted(str(k) for k in params) or [UNDECLARED],
            "transformations": c.get("family"),
            "universe": universe,
            "horizon": horizon_of(params),
            "parameters_allowed": dict(params.items()) or {"declared": UNDECLARED},
            "acceptance_criterion": "the canonical ten-gate gauntlet, deflated by the sweep's "
                                    "own trial count, then the lockbox and shadow",
            "falsifier": (c.get("evidence") or {}).get("screen") or "self-deflated screen"}


def register_candidate(c: dict[str, Any], *, source: str,
                       path: Path | None = None) -> tuple[str | None, str | None]:
    """Pre-register ONE candidate. Returns `(hash, None)` or `(None, named_reason)`.

    TOTAL BY CONSTRUCTION AND NAMED ON FAILURE. The caller needs a per-row answer it cannot
    drop: registering candidates inside one try block meant the first row whose card was
    incomplete aborted the loop and took every later row in the batch with it -- measured
    2026-09-23, 30.9% of unregistered rows had a COMPLETE card and failed only because they
    stood behind one that did not. The catch here is narrow (a bad card, an unwritable ledger)
    and the reason is returned rather than swallowed.
    """
    try:
        card = from_candidate(c)
        missing = validate(card)
        if missing:
            return None, "incomplete card: missing " + ",".join(missing)
        # Resolved at CALL time, not bound at def time, so the ledger a caller writes to can be
        # redirected (a test must never append to the desk's real pre-registration ledger).
        sid = node_id_for_spec(c) if (c.get("symbol") and c.get("family")) else None
        return register(card, source=source, path=path if path is not None else LEDGER,
                        spec_id=sid), None
    except (ValueError, TypeError, AttributeError) as exc:
        return None, f"{type(exc).__name__}: {exc}"
    except OSError as exc:
        return None, f"ledger unwritable: {type(exc).__name__}: {exc}"


def check(verdicts: list[dict[str, Any]], path: Path = LEDGER) -> dict[str, Any]:
    """Every verdict must name a registered card whose hash still matches its content."""
    reg = cards(path)
    ok, unregistered, mismatched = 0, [], []
    for v in verdicts:
        h = str(v.get("prereg_hash") or "")
        if not h or h not in reg:
            unregistered.append(v.get("id") or v.get("cell"))
            continue
        if row_hash(reg[h]) != h:
            mismatched.append(h)
            continue
        ok += 1
    return {"ok": not unregistered and not mismatched, "registered": ok,
            "unregistered": unregistered[:20], "mismatched": mismatched[:20],
            "n_cards": len(reg)}


# =============================================================================== THE JOIN
# WHY NOTHING JOINED (measured 2026-09-30, `reports/six_event_trace.md` event 2). 3,948 cards,
# 108,189 graph rows, and not one row carrying a hash, for three reasons that compounded:
#
#   1. NO WRITER. `hypothesis_graph.record_verdicts` had no production caller at all. Every
#      FAILED / CERTIFIED fate in the graph was written by `scripts/backfill_hypothesis_graph.py`,
#      a hand-run import of `research_queue.json` whose last run is why the last fate is dated
#      2026-09-03. The gauntlet writes `gate_verdict_ledger.jsonl` and never the graph.
#   2. NO CARRIER. A card was written per DONATED row, then the compiler expanded and re-keyed
#      that row into executable cells and the hash was not carried; the gauntlet then built each
#      cell from `symbol/family/params` alone and dropped every other key. A hash that exists
#      only on a row nobody judges joins nothing.
#   3. NO KEY. A card held no identity of the cell it described, so even a reader holding both
#      files could not say which card belonged to which verdict.
#
# The repair is one key and two stamps. `spec_id` is the graph's own node id of the EXECUTABLE
# spec (symbol, family, params exactly as the judge builds the cell), so a card, a docket row, a
# gate-ledger row and a graph node all name the cell the same way. The docket writer registers
# every never-judged cell in one batch card before the judge reads the docket, and every verdict
# is stamped from the ledger -- PREREGISTERED with the card's hash when a card for that exact spec
# was written BEFORE the cell was first judged, and `prereg_hash: null`, POST_HOC otherwise.
# Nothing is dropped and nothing is backfilled: a card written after the evidence is a forgery.

PREREGISTERED = "PREREGISTERED"
POST_HOC = "POST_HOC"
#: A docket BATCH card: one card committing to many executable specs by their `spec_id`, under
#: one test plan. A per-cell card is ~900 bytes; a docket of 448,391 rows (measured on the box
#: 2026-09-24) would put 400 MB into a tracked ledger in one hour. A spec id is 16 bytes and is a
#: hash commitment to the cell's exact parameters, which is all the card needs to prove.
BATCH_KIND = "docket_batch"
TEST_PLAN = ROOT / "desks" / "mt5" / "policy" / "gate_spec.yaml"
ACCEPTANCE = ("the canonical ten-gate gauntlet under the pinned gate spec (test_plan.sha), "
              "deflated by the sweep's own trial count, then the lockbox and shadow")
FALSIFIER = "any gate of the pinned gate spec failing on this exact spec"


def judge_plan(path: Path | None = None) -> dict[str, str]:
    """The judge's pinned contract, hashed: the TEST PLAN half of every batch card."""
    p = path if path is not None else TEST_PLAN
    try:
        sha = hashlib.sha256(p.read_bytes()).hexdigest()[:16]
    except OSError:
        sha = "UNREADABLE"                 # named, never a silent default (L1.28a)
    try:
        rel = str(p.relative_to(ROOT))
    except ValueError:
        rel = str(p)
    return {"path": rel, "sha": sha}


def batch_hash(row: Mapping[str, Any]) -> str:
    body = {"kind": BATCH_KIND, "test_plan": row.get("test_plan"),
            "acceptance_criterion": row.get("acceptance_criterion"),
            "falsifier": row.get("falsifier"),
            "specs": sorted(str(s) for s in (row.get("specs") or []))}
    return hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()[:16]


def row_hash(row: dict[str, Any]) -> str:
    """The hash a ledger row's content implies, whichever kind of card it is."""
    return batch_hash(row) if row.get("kind") == BATCH_KIND else card_hash(row)


def judged_spec(row: Mapping[str, Any]) -> dict[str, Any] | None:
    """The cell the judge will build from one docket row, EXACTLY as `external_gauntlet.main`
    builds it: `symbol`, `family`, `params`, with a non-H1 row-level `timeframe` folded into
    params when params do not already name one. A different reading here would mint a card for
    a cell the judge never builds."""
    sym = row.get("symbol")
    fam = row.get("family")
    if not sym or not fam:
        return None
    raw = row.get("params")
    params = dict(raw) if isinstance(raw, Mapping) else {}
    tf = str(row.get("timeframe") or "").upper()
    if tf and tf != "H1" and "timeframe" not in params:
        params["timeframe"] = tf
    return {"sym": sym, "family": fam, "params": params}


def _legacy_spec_id(card: Mapping[str, Any]) -> str | None:
    """A per-candidate card written before `spec_id` existed names its cell only through
    `universe`, `transformations` (the family) and `parameters_allowed`. One symbol or none."""
    uni = card.get("universe")
    fam = card.get("transformations")
    if not isinstance(uni, list) or len(uni) != 1 or not fam:
        return None
    params = card.get("parameters_allowed")
    if not isinstance(params, dict) or params == {"declared": UNDECLARED}:
        params = {}
    return node_id(str(uni[0]), str(fam), params)


def spec_index(path: Path | None = None) -> dict[str, tuple[str, str]]:
    """spec_id -> (EARLIEST registered_utc, that card's hash). Streamed, so a large ledger costs
    one pass and a dict of 16-byte keys, never the whole file resident."""
    p = path if path is not None else LEDGER
    out: dict[str, tuple[str, str]] = {}
    try:
        fh = p.open("r", encoding="utf-8", errors="replace")
    except OSError:
        return out
    with fh:
        for ln in fh:
            if not ln.strip():
                continue
            try:
                r = json.loads(ln)
            except ValueError:
                continue
            if not isinstance(r, dict):
                continue
            at, h = str(r.get("registered_utc") or ""), str(r.get("prereg_hash") or "")
            if not at or not h:
                continue
            if r.get("kind") == BATCH_KIND:
                sids = [str(s) for s in (r.get("specs") or [])]
            else:
                sid = r.get("spec_id") or _legacy_spec_id(r)
                sids = [str(sid)] if sid else []
            for sid in sids:
                cur = out.get(sid)
                if cur is None or at < cur[0]:
                    out[sid] = (at, h)
    return out


def register_docket(rows: list[dict[str, Any]], *, judged: Container[str] = frozenset(),
                    source: str = "merge_hypotheses", path: Path | None = None,
                    index: dict[str, tuple[str, str]] | None = None,
                    now: datetime | None = None) -> dict[str, Any]:
    """Pre-register every docket row BEFORE the judge reads the docket. Stamps rows in place.

    Three outcomes per row, all written ON the row so the docket itself says which it is:
      * a card for this exact spec already exists -> that card's hash, PREREGISTERED
      * no card, and the cell has NEVER been judged -> a new spec in this run's batch card
      * no card, and the cell WAS judged already -> RETROSPECTIVELY_UNPREREGISTERED, no card.
        Writing one now would let the next re-judgement read as pre-registered, which is the
        exact forgery the ledger exists to prevent; `judged` names such cells by spec id.
    """
    p = path if path is not None else LEDGER
    idx = index if index is not None else spec_index(p)
    new: dict[str, list[dict[str, Any]]] = {}
    out: dict[str, Any] = {"rows": 0, "already": 0, "new_specs": 0, "retrospective": 0,
                           "no_spec": 0, "batch_hash": None, "error": None}
    for r in rows:
        if not isinstance(r, dict):
            continue
        out["rows"] += 1
        spec = judged_spec(r)
        if spec is None:
            out["no_spec"] += 1
            r["prereg_status"] = PREREG_FAILED
            r["prereg_failure"] = "no symbol or family: the judge builds no cell from this row"
            continue
        sid = node_id_for_spec(spec)
        r["spec_id"] = sid
        if sid in idx:
            r["prereg_hash"] = idx[sid][1]
            r["prereg_status"] = PREREGISTERED
            out["already"] += 1
        elif sid in judged:
            r["prereg_hash"] = None
            r["prereg_status"] = RETROSPECTIVELY_UNPREREGISTERED
            out["retrospective"] += 1
        else:
            new.setdefault(sid, []).append(r)
    if not new:
        return out
    card: dict[str, Any] = {"kind": BATCH_KIND, "test_plan": judge_plan(),
                            "acceptance_criterion": ACCEPTANCE, "falsifier": FALSIFIER,
                            "specs": sorted(new)}
    h = batch_hash(card)
    at = (now or datetime.now(tz=UTC)).isoformat()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"prereg_hash": h, "registered_utc": at, "source": source,
                                 **card}, default=str) + "\n")
    except OSError as exc:
        out["error"] = f"ledger unwritable: {type(exc).__name__}: {exc}"
        for rs in new.values():
            for r in rs:
                r["prereg_hash"] = None
                r["prereg_status"] = PREREG_FAILED
                r["prereg_failure"] = out["error"]
        return out
    for sid, rs in new.items():
        idx[sid] = (at, h)
        for r in rs:
            r["prereg_hash"] = h
            r["prereg_status"] = PREREGISTERED
    out["new_specs"] = len(new)
    out["batch_hash"] = h
    return out


def stamp_verdict(v: dict[str, Any], spec: Mapping[str, Any] | None, *,
                  index: Mapping[str, tuple[str, str]], first_judged: str | None,
                  at: str) -> dict[str, Any]:
    """Stamp ONE verdict in place with `spec_id`, `prereg_hash` and `prereg_status`.

    PREREGISTERED only when a card for this exact spec was registered STRICTLY BEFORE the cell
    was first judged -- `first_judged` when the caller knows it, this verdict's own time
    otherwise. A hash the verdict already carries is honoured only on the same terms: one that
    names no earlier card for this spec is REFUSED, not trusted, and the verdict reads POST_HOC
    with `prereg_hash: null`. Never dropped, never silently treated as registered.
    """
    s = spec if spec is not None else v
    sid = str(v.get("spec_id") or "")
    if not sid and (s.get("symbol") or s.get("sym")) and s.get("family"):
        sid = node_id_for_spec(s)
    cutoff = min(x for x in (first_judged, at) if x) if (first_judged or at) else ""
    hit = index.get(sid) if sid else None
    v["spec_id"] = sid or None
    if hit is not None and cutoff and hit[0] < cutoff:
        v["prereg_hash"] = hit[1]
        v["prereg_status"] = PREREGISTERED
    else:
        v["prereg_hash"] = None
        v["prereg_status"] = POST_HOC
    return v
