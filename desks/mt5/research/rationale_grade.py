"""ECONOMIC-RATIONALE GRADE: does a candidate say WHY it should make money before it is tested?

THE DISCIPLINE (Quantedge). Before a candidate spends a judge-second it should state three things:

    (a) MECHANISM   -- in one sentence, what happens in the market that the rule exploits;
    (b) PAYER       -- who is on the other side, and why they are willing to lose;
    (c) CONSTRAINT  -- what stops arbitrageurs from competing the edge away.

`frontier_identity.economic_prior` (the judge's gate 0) passes any cell whose mechanism_status is
NAMED, so it cannot tell "a trend anchor PERMITS the entry" from "a benchmark-tracking fund must
buy at the fix and dealers pre-hedge". This module grades that difference. IT IS A TAG AND NEVER A
GATE: `grade()` returns a label and its evidence; nothing here drops, blocks, reorders or down-
weights a cell, and mining never shrinks because of it. Whether the grade should ever steer the
judge's ORDER is a separate question answered by `contract()` below, and any such change ships as
a patch file for the principal, not as code (see /mnt/project-files/patches/).

GRADES: A = all three present and non-boilerplate, B = two, C = one, NONE = none.

WHERE EACH COMPONENT MAY COME FROM, recorded per component so the grade is auditable:

    cell      the candidate's own fields: `mechanism_note`/`mechanism`/`description`;
              `payer`/`counterparty`/`actor` (top level, `structured`/`spec`, or the mechanism
              genome under `params.mechanism_genome`); `constraint`/`limits_to_arbitrage`/
              `why_edge_can_persist`
    cell_text a payer clause ("forced actor:", "paid by", "hedgers", "pension funds" ...) or a
              constraint clause ("must", "cannot", "mandate", "margin", "risk limit" ...) inside
              the cell's own mechanism sentence -- the sentence names them itself
    registry  family-level lookups the desk already owns: `libs/research/mechanism_census`
              (construction map, then signatures over family + note) for the mechanism's class
              and its PAYER -- except classes whose payer is "nobody is compelled", which is the
              census's own statement that there is no payer; `libs/research/alpha_schema.EVENTS`
              for a cell that declares its `event`. No registry on this desk names a CONSTRAINT,
              so (c) is only ever satisfied by the cell itself -- stated, not papered over.

CONTEXT FIELDS (`source_culture`, `participant_structure`, `failure_mode_hypothesis`,
`crowding_prior`), when a cell carries them, are copied into the tag's `context`; a non-
boilerplate `failure_mode_hypothesis` (>= 4 words, not a label) also satisfies (b), because it
names why the counterparty behaves differently from the desk.

`grade_cell_only` is the same grade with registry lookups off, so a reader can see how much of a
grade the family lent the cell.

CONTRACT: `contract()` joins graded cells to the judge's own history in git --
`gauntlet_seen_cells.json` (judged) and the universal-survivor certificates (certified; the
canon's `retired_certificates` are the forward failures) -- and publishes certification rate by
grade with Wilson intervals to `reports/RATIONALE_GRADE.json`. It reports what it finds, including
"no measurable difference".

    python desks/mt5/research/rationale_grade.py [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from functools import lru_cache
from itertools import pairwise
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

HYP = DESK / "data" / "hypotheses"
DOCKET = HYP / "external_survivors.json"
MINER = HYP / "miner_candidates.json"
REQUEUE = HYP / "requeue_named.json"
SEEN = HYP / "gauntlet_seen_cells.json"
SURVIVORS_REPORT = DESK / "reports" / "UNIVERSAL_SURVIVORS.json"
CANON = DESK / "data" / "UNIVERSAL_SURVIVORS.canon.json"
OUT = DESK / "reports" / "RATIONALE_GRADE.json"

GRADES: tuple[str, ...] = ("A", "B", "C", "NONE")
_GRADE_OF = {3: "A", 2: "B", 1: "C", 0: "NONE"}
_RANK = {g: i for i, g in enumerate(GRADES)}
Z95 = 1.959963984540054

_MECH_KEYS = ("mechanism_note", "mechanism", "description", "claim", "why")
_PAYER_KEYS = ("payer", "counterparty", "opposing_side", "actor", "economic_actor", "participant")
_CONSTRAINT_KEYS = ("constraint", "constraints", "limits_to_arbitrage", "arbitrage_constraint",
                    "why_edge_can_persist", "why_persists", "persistence")
_NESTS = ("structured", "spec", "rationale", "mechanism_genome")
#: Context fields other builders attach to a cell. Carried through into the tag output verbatim
#: (truncated); `failure_mode_hypothesis` also COUNTS toward the payer component when non-
#: boilerplate, because it names why the counterparty behaves differently from the desk.
CONTEXT_KEYS: tuple[str, ...] = ("source_culture", "participant_structure",
                                 "failure_mode_hypothesis", "crowding_prior")

#: Values that name nothing: labels and fillers the desk's writers emit when they have no answer.
_EMPTY = frozenset({"", "unknown", "none", "null", "n/a", "na", "tbd", "?", "other", "market",
                    "the market", "traders", "participants", "market participants", "everyone",
                    "anyone", "price only", "named registered family", "generic"})
#: Mechanism sentences that describe the DATA or the SEARCH, not a market mechanism.
_BOILER_MECH = tuple(re.compile(p, re.I) for p in (
    r"^search population \w+ over the desk's own grammar",
    r"^source supplied exact recipe",
    r"^\d\+? ?(factor|peer)? ?instruments?'? h1",
    r"^a peer instrument's h1",
    r"^statistical discovery has no economic prior",
    r"^mechanism documented at hunt registration",
))
#: A clause that names what stops the edge being competed away.
_CONSTRAINT_CLAUSE = re.compile(
    r"\b(must|cannot|can ?not|can't|unable|forced|compelled|mandate[sd]?|obliged|required to|"
    r"contractual(ly)?|margin call|margin rules?|risk[- ]limits?|capital (controls?|constraints?|"
    r"limits?)|balance[- ]sheet|inventory limits?|regulat\w*|capacity[- ]bound|too small|"
    r"limits? to arbitrage|costly to arbitrage|short[- ]sale constraints?|funding constraints?|"
    r"benchmark|fixing|index rebalanc\w*)\b", re.I)
#: A clause in the cell's own sentence that names who is on the other side.
_PAYER_CLAUSE = re.compile(
    r"\b(forced actor|forced (seller|buyer)s?|payer|counterparty|paid by|pays whoever|"
    r"on the other side|who (must|pays|is forced)|hedgers?|dealers? (who|must)|"
    r"(pension|index|tracking|passive) funds?|customers? (settling|who)|liquidat\w+)\b", re.I)


def _norm(v: Any) -> str:
    if isinstance(v, (list, tuple)):
        v = " ".join(str(x) for x in v if x)
    return re.sub(r"\s+", " ", str(v or "")).strip()


def _is_label(text: str) -> bool:
    """A bare taxonomy label (`relative_value_dislocation`) or a filler word."""
    t = text.lower()
    return t in _EMPTY or re.fullmatch(r"[a-z0-9_+\-]+", t) is not None


def _mechanism_ok(text: str) -> bool:
    t = _norm(text)
    if _is_label(t) or len(t.split()) < 6:
        return False
    return not any(p.search(t) for p in _BOILER_MECH)


def _statement_ok(text: str) -> bool:
    """A short statement, not a label or a filler: at least four words."""
    t = _norm(text)
    return not _is_label(t) and len(t.split()) >= 4


def _named_ok(text: str) -> bool:
    """A payer or constraint the cell NAMES: not a filler. A genome slot like
    `overnight_risk_limits` is a label, and a named one -- it counts."""
    t = _norm(text).lower()
    return bool(t) and t not in _EMPTY and len(t) >= 3


def _fields(row: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    out: list[Mapping[str, Any]] = [row]
    for k in _NESTS:
        v = row.get(k)
        if isinstance(v, Mapping):
            out.append(v)
    params = row.get("params")
    if isinstance(params, Mapping):
        for k in _NESTS:
            v = params.get(k)
            if isinstance(v, Mapping):
                out.append(v)
    return out


def _first(blocks: list[Mapping[str, Any]], keys: tuple[str, ...], ok: Any) -> str | None:
    for b in blocks:
        for k in keys:
            v = _norm(b.get(k))
            if v and ok(v):
                return v
    return None


@lru_cache(maxsize=8192)
def _registry(family: str, note: str) -> tuple[str | None, str | None, str | None]:
    """(class_id, mechanism definition, payer) from the census; payer None when compulsion-free."""
    try:
        from libs.research import mechanism_census as mc
    except ImportError:                                        # pragma: no cover - import context
        return None, None, None
    cls, _hits = mc.classify(f"{family} {note}", construction=family or None)
    if cls is None or cls not in mc.CLASS_BY_ID:
        return None, None, None
    c = mc.CLASS_BY_ID[cls]
    payer = None if c.payer.lower().startswith("nobody is compelled") else c.payer
    return cls, c.economic_definition, payer


def _event_payer(blocks: list[Mapping[str, Any]]) -> tuple[str | None, str | None]:
    try:
        from libs.research.alpha_schema import EVENTS
    except ImportError:                                        # pragma: no cover
        return None, None
    for b in blocks:
        ev = b.get("event")
        if isinstance(ev, str) and ev in EVENTS:
            return EVENTS[ev].get("mechanism"), EVENTS[ev].get("payer")
    return None, None


_SIG_KEYS = _MECH_KEYS + _PAYER_KEYS + _CONSTRAINT_KEYS + CONTEXT_KEYS + ("event",)


def grade(row: Mapping[str, Any], *, use_registry: bool = True) -> dict[str, Any]:
    """The grade and, per component, where it was found. Never raises on a malformed row.

    Memoised on the fields it reads (family + the rationale-bearing values), because a docket of
    a million rows carries a few thousand distinct statements; the returned dict is a copy."""
    if not isinstance(row, Mapping):
        return {"grade": "NONE", "grade_cell_only": "NONE", "census_class": None,
                "components": {}, "context": {}}
    blocks = _fields(row)
    sig = tuple(tuple((k, _norm(b.get(k))[:600]) for k in _SIG_KEYS if b.get(k)) for b in blocks)
    out = _grade_sig(_norm(row.get("family")), sig, use_registry)
    return {**out, "components": {k: dict(v) for k, v in out["components"].items()},
            "context": dict(out["context"])}


@lru_cache(maxsize=65536)
def _grade_sig(family: str, sig: tuple[tuple[tuple[str, str], ...], ...],
               use_registry: bool) -> dict[str, Any]:
    blocks: list[Mapping[str, Any]] = [dict(b) for b in sig] or [{}]
    comps: dict[str, dict[str, Any]] = {}

    mech = _first(blocks, _MECH_KEYS, _mechanism_ok)
    comps["mechanism"] = {"present": bool(mech), "source": "cell" if mech else None}
    text = " ".join(_norm(b.get(k)) for b in blocks for k in _MECH_KEYS)
    text_ok = _mechanism_ok(text)
    payer = _first(blocks, _PAYER_KEYS, _named_ok)
    comps["payer"] = {"present": bool(payer), "source": "cell" if payer else None}
    if not payer and text_ok and _PAYER_CLAUSE.search(text):
        comps["payer"] = {"present": True, "source": "cell_text"}
    # A FAILURE-MODE HYPOTHESIS names why the counterparty behaves differently from the desk --
    # the "why are they willing to lose" half of (b) -- so a real one satisfies the payer.
    if not comps["payer"]["present"] and _first(blocks, ("failure_mode_hypothesis",),
                                                 _statement_ok):
        comps["payer"] = {"present": True, "source": "cell:failure_mode_hypothesis"}
    context = {k: v[:300] for k in CONTEXT_KEYS
               if (v := _first(blocks, (k,), _named_ok)) is not None}
    cons = _first(blocks, _CONSTRAINT_KEYS, _named_ok)
    comps["constraint"] = {"present": bool(cons), "source": "cell" if cons else None}
    if not cons and text_ok and _CONSTRAINT_CLAUSE.search(text):
        comps["constraint"] = {"present": True, "source": "cell_text"}
    cell_only = sum(1 for c in comps.values() if c["present"])

    cls = None
    if use_registry:
        ev_mech, ev_payer = _event_payer(blocks)
        note = _norm(blocks[0].get("mechanism_note"))[:400]
        cls, reg_mech, reg_payer = _registry(family, note)
        if not comps["mechanism"]["present"] and (ev_mech or reg_mech):
            comps["mechanism"] = {"present": True,
                                  "source": "registry:alpha_schema" if ev_mech
                                  else f"registry:mechanism_census:{cls}"}
        if not comps["payer"]["present"] and (ev_payer or reg_payer):
            comps["payer"] = {"present": True,
                              "source": "registry:alpha_schema" if ev_payer
                              else f"registry:mechanism_census:{cls}"}
    n = sum(1 for c in comps.values() if c["present"])
    return {"grade": _GRADE_OF[n], "grade_cell_only": _GRADE_OF[cell_only],
            "census_class": cls, "components": comps, "context": context}


def best(a: str, b: str) -> str:
    return a if _RANK.get(a, 9) <= _RANK.get(b, 9) else b


def tag(row: dict[str, Any]) -> dict[str, Any]:
    """Annotate a row IN PLACE with `rationale_grade` (+ cell-only grade). Returns the row.
    Adds keys only; never removes one, so every reader of the row sees what it saw before."""
    g = grade(row)
    row["rationale_grade"] = g["grade"]
    row["rationale_grade_cell_only"] = g["grade_cell_only"]
    if g["context"]:
        row["rationale_context"] = g["context"]
    return row


def census(grades: Iterable[str]) -> dict[str, int]:
    out = dict.fromkeys(GRADES, 0)
    for g in grades:
        out[g if g in out else "NONE"] += 1
    return out


# ------------------------------------------------------------------ the contract
def wilson(k: int, n: int, z: float = Z95) -> list[float] | None:
    if n <= 0:
        return None
    p = k / n
    den = 1.0 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return [round(max(0.0, centre - half), 6), round(min(1.0, centre + half), 6)]


def _load(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _rows(obj: Any) -> list[dict[str, Any]]:
    if isinstance(obj, dict):
        obj = obj.get("hypotheses") or obj.get("cells") or []
    return [r for r in obj if isinstance(r, dict)] if isinstance(obj, list) else []


def _cid(row: Mapping[str, Any]) -> str | None:
    from frontier_identity import cell_id
    sym, fam = row.get("symbol") or row.get("sym"), row.get("family")
    if not sym or not fam:
        return None
    params = dict(row.get("params") or {}) if isinstance(row.get("params"), Mapping) else {}
    tf = str(row.get("timeframe") or "").upper()
    if tf and tf != "H1" and "timeframe" not in params:
        params["timeframe"] = tf
    try:
        return cell_id({"sym": sym, "family": fam, "params": params})
    except (KeyError, TypeError, ValueError):
        return None


def _strip(cid: str) -> str:
    return cid[len("external."):] if cid.startswith("external.") else cid


def certificates(report: Path = SURVIVORS_REPORT,
                 canon: Path = CANON) -> tuple[set[str], set[str], str | None]:
    """(certified cell ids, retired cell ids, why-unmeasured)."""
    certified: set[str] = set()
    retired: set[str] = set()
    found = False
    for p in (report, canon):
        d = _load(p)
        if not isinstance(d, dict):
            continue
        found = True
        for k, v in (d.get("survivors") or {}).items():
            certified.add(_strip(str((v or {}).get("cell") or k) if isinstance(v, dict) else k))
        for k, v in (d.get("retired_certificates") or {}).items():
            cid = _strip(str(v.get("cell") or k) if isinstance(v, dict) else str(k))
            certified.add(cid)
            retired.add(cid)
    return certified, retired, (None if found else "no certificate artifact readable")


def _by_grade(cells: dict[str, str], judged: set[str], certified: set[str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for g in GRADES:
        ids = [c for c, gg in cells.items() if gg == g and c in judged]
        k = sum(1 for c in ids if c in certified)
        out[g] = {"judged": len(ids), "certified": k,
                  "cert_rate": round(k / len(ids), 6) if ids else None,
                  "wilson95": wilson(k, len(ids))}
    return out


def _split(rates: dict[str, Any]) -> dict[str, Any]:
    """A+B against C+NONE, with Wilson intervals and whether they overlap (None: a side empty)."""
    k1 = sum(rates[g]["certified"] for g in ("A", "B"))
    n1 = sum(rates[g]["judged"] for g in ("A", "B"))
    k2 = sum(rates[g]["certified"] for g in ("C", "NONE"))
    n2 = sum(rates[g]["judged"] for g in ("C", "NONE"))
    w1, w2 = wilson(k1, n1), wilson(k2, n2)
    overlap = (None if not (w1 and w2) else not (w1[0] > w2[1] or w2[0] > w1[1]))
    return {"AB": {"judged": n1, "certified": k1, "wilson95": w1},
            "CNONE": {"judged": n2, "certified": k2, "wilson95": w2},
            "intervals_overlap": overlap}


def contract(rows:Iterable[Mapping[str, Any]] | None = None, *,
             seen: Path = SEEN, report: Path = SURVIVORS_REPORT,
             canon: Path = CANON) -> dict[str, Any]:
    """Certification rate (and forward retirement) by rationale grade, from the judge's history."""
    if rows is None:
        rows = [r for p in (DOCKET, MINER, REQUEUE) for r in _rows(_load(p))]
    seen_doc = _load(seen)
    certified, retired, why = certificates(report, canon)
    if not isinstance(seen_doc, dict) or why:
        return {"status": "UNMEASURED",
                "why": why or f"{seen.name} unreadable: the judged population is unknown"}
    full: dict[str, str] = {}
    cell_only: dict[str, str] = {}
    family_of: dict[str, str] = {}
    n_rows = 0
    for r in rows:
        cid = _cid(r)
        if cid is None:
            continue
        n_rows += 1
        g = grade(r)
        full[cid] = best(full.get(cid, "NONE"), g["grade"])
        cell_only[cid] = best(cell_only.get(cid, "NONE"), g["grade_cell_only"])
        family_of[cid] = str(r.get("family") or "")
    judged = (set(seen_doc) | certified) & set(full)
    cert_fams = {family_of[c] for c in judged if c in certified}
    in_cert_fams = {c for c in judged if family_of.get(c) in cert_fams}
    certified_graded = [c for c in judged if c in certified]
    fwd = {g: {"certified": sum(1 for c in certified_graded if full[c] == g),
               "retired": sum(1 for c in certified_graded if full[c] == g and c in retired)}
           for g in GRADES}
    rates = _by_grade(full, judged, certified)
    rates_cell = _by_grade(cell_only, judged, certified)
    split, split_cell = _split(rates), _split(rates_cell)
    ordered = [rates[g]["cert_rate"] for g in GRADES if rates[g]["cert_rate"] is not None]
    monotone = all(a >= b for a, b in pairwise(ordered))
    if split_cell["intervals_overlap"] is not False:
        verdict = ("NOT PREDICTIVE ON THE CELL'S OWN STATEMENT: the cell-only grade's A/B and "
                   "C/NONE certification intervals overlap"
                   + ("" if split["intervals_overlap"] is not False else
                      "; the registry-assisted split separates, which is the FAMILY speaking "
                      "(which families the census can place), not the candidate"))
    elif not monotone:
        verdict = "SEPARATES A/B FROM C/NONE BUT NOT MONOTONE IN GRADE"
    else:
        verdict = "PREDICTIVE: certification rate falls with grade and A/B separates from C/NONE"
    return {
        "status": "MEASURED",
        "rows_graded": n_rows, "cells_graded": len(full),
        "grade_census_all_cells": census(full.values()),
        "judged_cells_with_rationale_fields": len(judged),
        "certified_among_them": len(certified_graded),
        "certificates_total": len(certified),
        "cert_rate_by_grade": rates,
        "cert_rate_by_grade_cell_only": rates_cell,
        "cert_rate_by_grade_within_certifying_families": _by_grade(
            {c: full[c] for c in in_cert_fams}, in_cert_fams, certified),
        "forward_retirement_by_grade": fwd,
        "AB_vs_CNONE": split,
        "AB_vs_CNONE_cell_only": split_cell,
        "monotone_in_grade": monotone,
        "verdict": verdict,
        "sources": {"judged": seen.name, "certified": [report.name, canon.name],
                    "rows": [DOCKET.name, MINER.name, REQUEUE.name]},
        "caveat": ("the judged population is only the cells whose docket/miner rows are still in "
                   "git with their text; most historical verdicts live in the box-only verdict "
                   "ledger. A cell's grade is its BEST row's grade."),
    }


def build() -> dict[str, Any]:
    return {"at": datetime.now(UTC).isoformat(timespec="seconds"),
            "rule": "TAG, NEVER A GATE: grades drop, block and reorder nothing",
            "grades": {"A": "mechanism + payer + constraint", "B": "two of three",
                       "C": "one of three", "NONE": "none"},
            "contract": contract()}


def write(doc: dict[str, Any], out: Path | None = None) -> Path:
    p = OUT if out is None else out
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(f".json.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    os.replace(tmp, p)
    return p


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    doc = build()
    c = doc["contract"]
    print(json.dumps({k: c.get(k) for k in ("status", "why", "cells_graded",
                                             "grade_census_all_cells",
                                             "judged_cells_with_rationale_fields",
                                             "certified_among_them", "cert_rate_by_grade",
                                             "AB_vs_CNONE", "AB_vs_CNONE_cell_only",
                                             "verdict")}, indent=1))
    if not a.dry_run:
        print(f"-> {write(doc)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
