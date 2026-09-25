#!/usr/bin/env python3
"""IMMUTABLE EVALUATOR (portable fence) -- research agents may not modify the test they failed.

autoresearch-trading's split, made a law here: the files that JUDGE a hypothesis -- the
gauntlet, the multiplicity charge, the cost engine, the lockbox access, the promotion law, the
heat law and the growth governance fences -- are hashed into `data/IMMUTABLE_MANIFEST.json`.
Any change to one of them must arrive with a re-signed manifest (a human commit that runs
`--sign`), otherwise the gate is red. An organ that dislikes a verdict can change the
hypothesis; it cannot change the judge.

    python scripts/check_immutable_evaluator.py          # verify (rc=1 on drift)
    python scripts/check_immutable_evaluator.py --sign   # re-sign after a deliberate change

The MUTABLE side -- hypotheses, strategies, models, factors, proposers -- is everything else.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import platform
import re
import sys
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "desks" / "mt5" / "data" / "IMMUTABLE_MANIFEST.json"

IMMUTABLE: tuple[str, ...] = (
    "desks/mt5/scripts/external_gauntlet.py",
    "desks/mt5/research/universal_gate.py",
    "desks/mt5/research/multiplicity.py",
    "desks/mt5/research/gate_policy.py",
    "desks/mt5/research/heat_policy.py",
    "desks/mt5/research/promoter.py",
    "desks/mt5/mt5desk/gateway_config_fallback.py",
    "libs/portfolio/allocator_proof.py",
    "libs/portfolio/rails.py",
    "libs/portfolio/capital_modifiers.py",
    "libs/validation/redteam.py",
    "libs/validation/replay2.py",
    "libs/validation/calibration.py",
    "libs/regime/state_admission.py",
    "scripts/check_growth_governance.py",
    "scripts/check_heat_floor_wiring.py",
    "scripts/check_immutable_evaluator.py",
    "scripts/run_deadman_switch.py",
)

# ------------------------------------------------------------- the wall beyond frozen code
#: THE WALL IS NOT ONLY CODE (W19). The list above says the JUDGE may not be edited. The
#: constitution says more: the forward clocks' ledgers, the live ledger, the measured cost
#: surface and the research lineage chain are RECORDS, and a record that can be rewritten is
#: not evidence. They cannot be frozen like a source file -- they grow every hour, and hashing
#: them whole would make this fence permanently red for exactly the reason the CRLF bug did.
#: They are sealed by PREFIX instead: what was already written must still be there, byte for
#: byte, in the same order, and the only legal change is MORE records after it.
#:
#: (path-or-one-directory-glob, mode, why). `lines` = one record per line (jsonl); `rows` = a
#: JSON list, or a document with a "rows" list, whose elements are the records.
APPEND_ONLY: tuple[tuple[str, str, str], ...] = (
    ("desks/mt5/data/live_ledger.jsonl", "lines",
     "the live ledger -- the actual execution records every attribution is measured on"),
    ("desks/mt5/data/research_artifacts.jsonl", "lines",
     "the research lineage chain (libs/research/artifact_chain.py): hash-linked, append-only"),
    ("desks/mt5/reports/shadow/ledger_*.json", "rows",
     "the forward clocks' ledgers -- the preregistered evidence promotion reads"),
)

#: REBUILT, NEVER BACK-DATED. The cost surface is not append-only: it is re-measured, and a
#: fresher measurement is the whole point of it. What no self-improving organ may do is move it
#: BACKWARDS -- swap today's measured spread for an older, cheaper one and re-judge a cell that
#: failed net of cost. So the seal is the vintage stamp: it may advance, and a stamp that goes
#: backwards, or vanishes, is a breach. (path, stamp field, why)
VINTAGE: tuple[tuple[str, str, str], ...] = (
    ("desks/mt5/data/cost_surface.json", "built_at",
     "the measured cost surface -- the actual costs every net-of-cost verdict is charged"),
)


def _expand(rel: str) -> list[tuple[str, Path]]:
    """A path, or every file a one-directory glob matches, as (rel, absolute) pairs."""
    if "*" not in rel:
        return [(rel, ROOT / rel)]
    head, _, pattern = rel.rpartition("/")
    parent = ROOT / head
    if not parent.is_dir():
        return []
    return sorted((f"{head}/{p.name}", p) for p in parent.glob(pattern) if p.is_file())


def _records(path: Path, mode: str, drop: frozenset[str] | None = None) -> list[str] | None:
    """The file's records as canonical strings, or None when it cannot be read as records.

    `drop` is the RULER: which keys the canonical form leaves out. Default is the ruler in force
    (`_PASS_STAMPS`); `frozenset()` reproduces the ruler that was in force before 2026-09-24, and
    that is what lets a seal taken under the old one be verified instead of re-taken (see
    `_LEGACY_RULER`).
    """
    try:
        raw = path.read_text("utf-8", errors="replace")
    except OSError:
        return None
    if mode == "lines":
        return [ln for ln in raw.replace("\r\n", "\n").split("\n") if ln.strip()]
    try:
        doc = json.loads(raw)
    except ValueError:
        return None
    rows = doc if isinstance(doc, list) else (doc.get("rows") if isinstance(doc, dict) else None)
    if not isinstance(rows, list):
        return None
    keys = _PASS_STAMPS if drop is None else drop
    return [json.dumps(_evidence(r, keys), sort_keys=True, separators=(",", ":")) for r in rows]


#: FACTS ABOUT THE PASS, NOT ABOUT THE RECORD (measured on the trading box 2026-09-23).
#:
#: `shadow_forward` RE-DERIVES each forward ledger from bars on every pass and re-stamps EVERY
#: row with that pass's fetch time. Measured: 50 of 50 shadow ledgers carry exactly ONE distinct
#: `bars_fetched_utc` across all of their rows, including rows for trades that closed on
#: 2026-08-17 -- a month before the stamp. So the canonical form of an untouched August trade
#: changed every pass, the sealed prefix hash changed with it, and this fence reported
#: "a record was rewritten" on 22+ ledgers continuously.
#:
#: THAT IS THE WORST FAILURE MODE A SEAL CAN HAVE, and it is why this is a ruler fix and not a
#: relaxation. While every ledger is red on every pass, a ledger whose r_multiple was ACTUALLY
#: rewritten is indistinguishable from the other 21 -- the fence had lost the ability to detect
#: the one thing it exists for, and a permanent red trains the desk to stop reading it (L1.43).
#:
#: Excluded are exactly the three stamps that describe the DERIVATION RUN: when it fetched bars,
#: how fresh the freshest was, and whether it judged them stale. Everything that is the EVIDENCE
#: stays sealed -- entry_time, exit_time, side, entry, exit, r_multiple, reason, phase -- and so
#: do `bar_source`, `evidence_venue`, `promotion_authority` and `h1_source_version`, which are
#: provenance the record's CLAIM rests on and which do not move pass to pass. A venue swap or a
#: flipped promotion_authority still BREACHES, as it must.
#:
#: `mode="lines"` is untouched: `live_ledger.jsonl` holds real execution records that are
#: genuinely appended, never re-derived, and every byte of those stays under seal.
_PASS_STAMPS: frozenset[str] = frozenset({
    "bars_fetched_utc",     # when THIS pass fetched bars
    "bars_freshest",        # the freshest bar THIS pass saw
    "bars_stale",           # whether THIS pass judged its input stale
})


def _evidence(row: object, drop: frozenset[str] = _PASS_STAMPS) -> object:
    """A record's sealed form: everything it claims, minus the stamps of the run that derived it."""
    if not isinstance(row, dict):
        return row
    return {k: v for k, v in row.items() if k not in drop}


# -------------------------------------------- A SEAL MUST CARRY THE RULER IT WAS TAKEN WITH (2026-09-24)
#: THE FENCE CHANGED ITS OWN RULER AND THEN CALLED THE OLD MEASUREMENTS A CRIME. Measured today:
#: 152 of the 192 shadow ledgers on the sealing box reported BREACH -- "a record was rewritten" --
#: and 151 of them had not moved a byte. `_PASS_STAMPS` (the three derivation stamps above) landed
#: 2026-09-24T00:20:57 in d94dfb16a21; the standing record seal was taken 2026-09-23T01:17:54, 23
#: hours EARLIER, under the canonical form that hashed every field including those three. So the
#: seal and the check were measuring with two different rulers, and every difference between the
#: rulers was charged to the record.
#:
#: The proof is exact and it is why this is a verification, not a relaxation: recompute the sealed
#: prefix under the OLD canonical form and all 151 reproduce byte for byte -- same hash, same order,
#: same length. A file whose bytes reproduce a hash taken before it was allegedly rewritten was not
#: rewritten. The 152nd (`ledger_AUDCAD_discovered_asia.json`) reproduces under NEITHER ruler and
#: stays a BREACH, which is the whole point: the reclassification is evidence-driven per file, not
#: a blanket amnesty.
#:
#: RE-SEALING WOULD HAVE "FIXED" THIS AND DESTROYED THE ANSWER. `--seal-records` overwrites
#: `prefix_sha` with today's bytes, after which no one can ever ask whether those 151 ledgers
#: changed -- the question becomes unanswerable, and the one real difference disappears into the
#: same act. The seal is evidence; the ruler is the thing that was wrong.
#:
#: So every seal from now on RECORDS ITS RULER, and a seal that carries none is judged under the
#: ruler that predates the field -- the only honest reading of a measurement whose units were not
#: written down.
_RULER = "2026-09-24/pass-stamps-excluded"
_LEGACY_RULER = "pre-2026-09-24/every-field-hashed"


def _prefix_sha(records: Sequence[str], n: int) -> str:
    h = hashlib.sha256()
    for rec in records[:n]:
        h.update(rec.encode("utf-8", "replace"))
        h.update(b"\n")
    return h.hexdigest()[:16]


# ------------------------------------------------------- WHICH record, and WHICH field (2026-09-24)
#: A PREFIX HASH CANNOT NAME ITS OWN BREACH, AND THAT COST THE DESK A FULL FORENSIC ESCALATION.
#:
#: Until today this fence could say only "the sealed prefix of 151 record(s) changed". `151` is the
#: SEALED PREFIX LENGTH -- the number of records the hash covers -- and it was read, reasonably, as
#: "151 execution records were rewritten". It was escalated in those words: the live ledger, the
#: file every realised-R, gold-P&L and matched-fills claim rests on, apparently edited after
#: sealing on 151 rows. The measured answer (2026-09-24, keyed on the MT5 deal ticket) was that
#: **not one traded quantity had moved**: pl_quote, volume, side, symbol, entry_price, fill_price,
#: sl, tp, commission, swap, contract_size and order were byte-identical on all 151 deals, and what
#: differed was `time` (the gateway's own append stamp, `now()`), `sleeve` (a broker close label
#: corrected to the opening tag), `risk_quote` and `r_multiple` (the documented backfill in
#: `scripts/backfill_live_ledger_r.py`). Four completely different severities, and the fence wore
#: one word for all of them.
#:
#: SO THE SEAL NOW CARRIES WHAT THE VERDICT NEEDS. A per-record digest localises the change to an
#: INDEX, and a per-field digest names the FIELDS that moved without ever storing a value -- so the
#: fence answers "did a price or a volume change?" itself, in one line, instead of costing a
#: session. Digests only: the manifest never becomes a second copy of the ledger, and an account
#: number cannot leak through a SHA-256.
#:
#: Both are additive. A seal written before today has neither, and is judged exactly as it was --
#: the old verdict is preserved, and the message now says plainly that it cannot localise.
_DETAIL_MAX_RECORDS = 20_000
_DETAIL_MAX_FIELDS = 96
#: The host that took the seal. A record file is written by ONE box; another box's copy arrives by
#: git and is routinely a different derivation of the same account history. Naming the sealing host
#: is what lets a reader tell "a record was rewritten" from "this is not the box that writes it".
_HOST = platform.node() or "unknown"


def _row_digest(rec: str) -> str:
    return hashlib.sha256(rec.encode("utf-8", "replace")).hexdigest()[:12]


def _field_digests(rec: str) -> dict[str, str] | None:
    """{field: digest} for a record that is a JSON object, else None. Values are never stored."""
    try:
        doc = json.loads(rec)
    except ValueError:
        return None
    if not isinstance(doc, dict) or len(doc) > _DETAIL_MAX_FIELDS:
        return None
    out: dict[str, str] = {}
    for k, v in doc.items():
        blob = json.dumps(v, sort_keys=True, separators=(",", ":"), default=str)
        out[str(k)] = hashlib.sha256(blob.encode("utf-8", "replace")).hexdigest()[:8]
    return out


def _detail(records: Sequence[str]) -> tuple[list[str], list[dict[str, str] | None]]:
    head = list(records[:_DETAIL_MAX_RECORDS])
    return [_row_digest(r) for r in head], [_field_digests(r) for r in head]


def localise(records: Sequence[str], rec: Mapping[str, Any], at: int) -> dict[str, Any]:
    """WHICH of the sealed records differ here, and WHICH fields moved inside them.

    Returns `{"localised": False, ...}` when the seal predates per-record digests: the fence says
    so rather than implying it checked. Field names are reported, values never are.
    """
    rows = rec.get("rows")
    if not isinstance(rows, list) or not rows:
        return {"localised": False,
                "why": "this seal carries no per-record digests, so the fence cannot say WHICH "
                       "of those records moved. RE-SEALING IS NOT THE ANSWER HERE: --seal-records "
                       "overwrites prefix_sha with today's bytes, which is the only evidence that "
                       "could ever settle whether this file was rewritten. Read the file against "
                       "the writer's history first; a future seal localises by itself"}
    raw_fields = rec.get("fields")
    fields: list[Any] = raw_fields if isinstance(raw_fields, list) else []
    n = min(at, len(rows), len(records))
    changed = [i for i in range(n) if _row_digest(records[i]) != str(rows[i])]
    moved: dict[str, int] = {}
    held: set[str] = set()
    unparsed = 0
    for i in changed:
        was = fields[i] if i < len(fields) and isinstance(fields[i], dict) else None
        now = _field_digests(records[i])
        if was is None or now is None:
            unparsed += 1
            continue
        for k in set(was) | set(now):
            if was.get(k) != now.get(k):
                moved[k] = moved.get(k, 0) + 1
            else:
                held.add(k)
    return {"localised": True, "n_sealed": n, "n_changed": len(changed),
            "first_changed": changed[0] if changed else None,
            "changed_index_sample": changed[:20],
            "fields_moved": dict(sorted(moved.items(), key=lambda kv: -kv[1])),
            "fields_unchanged": sorted(held - set(moved)),
            "records_not_json": unparsed}


def append_only_seal() -> dict[str, dict[str, Any]]:
    """{rel: {records, prefix_sha, mode}} for every append-only record file present HERE.

    A path this host does not have is simply not sealed: these are files the trading box writes
    and a clean clone legitimately lacks. `wall_rows` reports that as UNMEASURED with the reason
    named -- an absent record file must never read as a verified one (L1.28a).
    """
    out: dict[str, dict[str, Any]] = {}
    for rel, mode, _why in APPEND_ONLY:
        for name, path in _expand(rel):
            recs = _records(path, mode)
            if recs is None:
                continue
            half = len(recs) // 2
            rows, fields = _detail(recs)
            out[name] = {"records": len(recs), "prefix_sha": _prefix_sha(recs, len(recs)),
                         "half": half, "half_sha": _prefix_sha(recs, half), "mode": mode,
                         "host": _HOST, "ruler": _RULER, "rows": rows, "fields": fields}
    return out


def vintage_seal() -> dict[str, dict[str, Any]]:
    """{rel: {field, stamp}} for every rebuilt-but-never-back-dated artifact present here."""
    out: dict[str, dict[str, Any]] = {}
    for rel, field, _why in VINTAGE:
        path = ROOT / rel
        try:
            doc = json.loads(path.read_text("utf-8"))
        except (OSError, ValueError):
            continue
        stamp = doc.get(field) if isinstance(doc, dict) else None
        if not isinstance(stamp, str) or not stamp:
            continue
        out[rel] = {"field": field, "stamp": stamp}
    return out


def _append_only_rows(sealed: Mapping[str, Any]) -> list[dict[str, Any]]:
    """One row per append-only record file: verified, grew, behind, absent, unsealed or BREACH.

    THE OVERLAP IS WHAT IS JUDGED, and that choice is the difference between a fence that means
    something and a fence that is red on every clean checkout. The seal is taken on the box that
    WRITES these files; another host's copy is routinely shorter (an older pull, a clone that
    never had the untracked forward ledgers at all). So the prefix is recomputed at min(n_now,
    n_sealed):

        identical there, and longer   -> `grew`      the only change these files may make
        identical there, and equal    -> `verified`
        identical there, and shorter  -> `behind`    UNMEASURED, named, never a pass
        identical under the SEAL's
        own ruler, not today's        -> `ruler_change`  the fence's canonical form moved after
                                                     the seal was taken; the bytes reproduce the
                                                     sealed hash exactly, so nothing was rewritten
        DIFFERENT under BOTH          -> BREACH      a record was rewritten, and that is the
                                                     one thing an append-only record cannot do
    """
    rows: list[dict[str, Any]] = []
    live = append_only_seal()
    for rel, mode, why in APPEND_ONLY:
        found = _expand(rel)
        if not found:
            rows.append({"path": rel, "kind": "append_only", "status": "absent", "why":
                         f"not on this host ({why}); UNMEASURED, not verified"})
            continue
        for name, path in found:
            rec = sealed.get(name)
            now = live.get(name)
            if not path.exists():
                rows.append({"path": name, "kind": "append_only", "status": "absent",
                             "why": f"not on this host ({why}); UNMEASURED, not verified"})
                continue
            if now is None:
                rows.append({"path": name, "kind": "append_only", "status": "unreadable",
                             "why": f"{path.name} could not be read as {mode} records"})
                continue
            if not isinstance(rec, Mapping):
                rows.append({"path": name, "kind": "append_only", "status": "unsealed",
                             "why": "not in the signed manifest; run --sign once",
                             "records": now["records"]})
                continue
            n_now, n_was = int(now["records"]), int(rec.get("records") or 0)
            n_half = int(rec.get("half") or 0)
            recs = _records(path, mode) or []
            # The checkpoint to judge at: the full seal when this host has at least that many
            # records, else the half seal, which is what makes a SHORTER copy checkable at all.
            if n_now >= n_was:
                at, want = n_was, str(rec.get("prefix_sha") or "")
            elif n_now >= n_half and n_half > 0:
                at, want = n_half, str(rec.get("half_sha") or "")
            else:
                rows.append({"path": name, "kind": "append_only", "status": "behind",
                             "why": f"{n_now} record(s) here against {n_was} sealed and no "
                                    "checkpoint below that: UNMEASURED, not verified",
                             "records": n_now})
                continue
            here = _prefix_sha(recs, at)
            # THE RULER THE SEAL WAS TAKEN WITH, BEFORE THE RECORD IS ACCUSED (2026-09-24).
            # A seal with no `ruler` predates `_PASS_STAMPS`, so its hash covered EVERY field.
            # Recomputing the same prefix under that canonical form is not a second chance for a
            # tampered file -- it is the only arithmetic that answers the question actually asked,
            # "are these bytes the bytes that were sealed". If they are, the hash reproduces
            # exactly, and the difference lives in the fence, not in the record. If they are not,
            # neither form reproduces and the BREACH below stands untouched.
            if here != want and mode != "lines" and not rec.get("ruler"):
                legacy = _records(path, mode, drop=frozenset()) or []
                if _prefix_sha(legacy, at) == want:
                    rows.append({"path": name, "kind": "append_only", "status": "ruler_change",
                                 "records": n_now, "sealed_ruler": _LEGACY_RULER,
                                 "ruler": _RULER,
                                 "why": f"{at} sealed record(s) reproduce EXACTLY under the "
                                        f"ruler the seal was taken with ({_LEGACY_RULER}): not "
                                        f"one byte of evidence moved. The current ruler "
                                        f"({_RULER}) drops {', '.join(sorted(_PASS_STAMPS))}, "
                                        "which landed AFTER this seal, so the two forms hash "
                                        "differently on a record nobody touched. Verified, not "
                                        "excused -- a rewritten record reproduces NEITHER form. "
                                        "The seal is evidence: re-sealing would erase the proof "
                                        "instead of recording it."})
                    continue
            if here != want:
                # NAME THE DAMAGE, NEVER THE PREFIX LENGTH. `at` is how many records the seal
                # COVERS; saying "the sealed prefix of 151 records changed" reads as "151 records
                # were rewritten" and was escalated in exactly those words (see `localise`).
                loc = localise(recs, rec, at)
                host = str(rec.get("host") or "")
                if host and host != _HOST:
                    where = (f"; sealed on host {host!r}, checked here on {_HOST!r} -- a record "
                             "file is written by ONE box and another box's copy is a different "
                             "derivation, so judge this on the writing host")
                elif not host:
                    # AND SAY IT WHEN THE SEAL NAMES NOBODY. Measured 2026-09-24: this same
                    # manifest reads 151 ruler-changes and 1 breach on the box that took the seal,
                    # and 74 breaches with 93 files absent on the other box -- because the forward
                    # ledgers are untracked per-box derivations and nothing in the seal said which
                    # box's they were. A verdict that cannot name its subject must say so.
                    where = (f"; this seal names NO host and was checked on {_HOST!r} -- these "
                             "record files are untracked per-box derivations, so a copy on a box "
                             "that did not take the seal is expected to differ and this row is "
                             "UNMEASURED there rather than evidence of a rewrite")
                else:
                    where = ""
                if loc["localised"]:
                    moved = loc["fields_moved"]
                    named = ", ".join(f"{k} x{v}" for k, v in moved.items()) or "none nameable"
                    why = (f"{loc['n_changed']} of the {at} sealed record(s) were rewritten "
                           f"(first at index {loc['first_changed']}); prefix {want} -> {here}. "
                           f"FIELDS MOVED: {named}. FIELDS UNCHANGED: "
                           f"{', '.join(loc['fields_unchanged']) or 'none'}{where}")
                else:
                    why = (f"the sealed prefix over {at} record(s) no longer hashes the same "
                           f"({want} -> {here}): at least one of those records was rewritten. "
                           f"{at} IS THE SEALED PREFIX LENGTH, NOT THE NUMBER OF RECORDS THAT "
                           f"CHANGED -- {loc['why']}{where}")
                rows.append({"path": name, "kind": "append_only", "status": "breach",
                             "why": why, "localisation": loc,
                             "sealed_host": host or None, "host": _HOST})
            elif n_now < n_was:
                rows.append({"path": name, "kind": "append_only", "status": "behind",
                             "why": f"{n_now} record(s) here against {n_was} sealed; the first "
                                    f"{at} are unchanged, the rest is UNMEASURED on this host",
                             "records": n_now})
            else:
                rows.append({"path": name, "kind": "append_only",
                             "status": "verified" if n_now == n_was else "grew",
                             "why": f"{n_was} sealed record(s) unchanged; {n_now - n_was} "
                                    "appended since", "records": n_now})
    return rows


def _vintage_rows(sealed: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    live = vintage_seal()
    for rel, field, why in VINTAGE:
        now = live.get(rel)
        rec = sealed.get(rel)
        if now is None:
            rows.append({"path": rel, "kind": "vintage", "status": "absent",
                         "why": f"no readable {field} here ({why}); UNMEASURED, not verified"})
            continue
        if not isinstance(rec, Mapping):
            rows.append({"path": rel, "kind": "vintage", "status": "unsealed",
                         "why": "not in the signed manifest; run --sign once"})
            continue
        was, stamp = str(rec.get("stamp") or ""), str(now["stamp"])
        if stamp < was:
            rows.append({"path": rel, "kind": "vintage", "status": "breach",
                         "why": f"{field} moved BACKWARDS ({was} -> {stamp}): a measured cost "
                                "surface may be rebuilt, never back-dated"})
        else:
            rows.append({"path": rel, "kind": "vintage",
                         "status": "verified" if stamp == was else "rebuilt",
                         "why": f"{field} {was} -> {stamp}"})
    return rows


# ------------------------------------------------------------- generator isolation (W19)
#: "SEALED DATA NEVER REACHES A GENERATOR." The frozen list guards the judge; this guards the
#: other direction. A proposer that can read the holdout is not proposing, it is fitting -- and
#: the damage is invisible afterwards, because the candidate that comes out looks exactly like
#: one that was found honestly. The only moment this is cheap to catch is the day the line is
#: written, so the check is SOURCE INSPECTION over every organ that can mint a hypothesis.
#:
#: WHAT IS BANNED IS THE READ, NOT THE SPLIT. `expression_factory` constructs a `LockedHoldout`
#: precisely so the tail of each world is sealed away from its own search, and calls
#: `.research()` and never `open_lockbox()`. Banning the import would have banned the correct
#: behaviour and taught the next author to seal nothing.
GENERATOR_ROOTS: tuple[str, ...] = ("desks/mt5/research", "desks/mt5/scripts", "libs/research")
#: A file is a generator if it imports the donation door. Cheap prefilter, AST-confirmed.
GENERATOR_MARKER = "proposer_common"
#: Generators that do not donate through that door and must still be scanned.
EXTRA_GENERATORS: tuple[str, ...] = (
    "libs/research/generators.py",        # the alpha-grammar generators (GFlowNet, symbolic)
    "desks/mt5/research/qd_frontier.py",  # the quality-diversity worker
    "libs/research/adapters/pyribs.py",   # the QD archive adapter
    "desks/mt5/research/representation_forge.py",  # the representation forge
)
#: Organs that JUDGE rather than propose. They are allowed to reach sealed evidence -- that is
#: their function -- and the frozen list above is what guards them instead.
JUDGES: frozenset[str] = frozenset({
    "desks/mt5/scripts/external_gauntlet.py", "desks/mt5/research/promoter.py",
    "desks/mt5/research/blind_reviewer.py", "desks/mt5/research/universal_gate.py",
    "desks/mt5/research/evidence_vault.py", "desks/mt5/research/certificate_truth.py",
})
#: Module whose import by a generator is itself the violation: it IS the sealed-tier vault.
SEALED_MODULES: frozenset[str] = frozenset({"evidence_vault"})
#: Names that read the sealed side. `LockedHoldout` is absent on purpose (see above).
SEALED_NAMES: frozenset[str] = frozenset({"open_lockbox", "LockboxService", "_seal_holdouts"})
#: Path literals that name sealed data. Matched only inside a string that LOOKS like a path, and
#: never inside a docstring, so prose about the holdout is not a finding.
SEALED_PATHS: tuple[str, ...] = ("evidence_vault.json", "data/lockbox", "holdout")


def _docstrings(tree: ast.AST) -> set[int]:
    out: set[int] = set()
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef) \
                and isinstance(body, list) and body and isinstance(body[0], ast.Expr) \
                and isinstance(body[0].value, ast.Constant) \
                and isinstance(body[0].value.value, str):
            out.add(id(body[0].value))
    return out


def _is_donor(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import | ast.ImportFrom):
            # BOTH SPELLINGS. `from research import proposer_common as pc` is an ImportFrom whose
            # MODULE is "research" and whose NAME is the door -- the spelling `expression_factory`
            # actually uses, and reading only the module missed the largest generator in the desk.
            names = [a.name for a in node.names]
            if isinstance(node, ast.ImportFrom):
                names.append(node.module or "")
            if any(n.split(".")[-1] == GENERATOR_MARKER for n in names):
                return True
    return False


def _sealed_reads(rel: str, tree: ast.AST) -> list[dict[str, str]]:
    skip = _docstrings(tree)
    out: list[dict[str, str]] = []
    for node in ast.walk(tree):
        line = getattr(node, "lineno", 0)
        if isinstance(node, ast.Import | ast.ImportFrom):
            mods = [a.name for a in node.names]
            if isinstance(node, ast.ImportFrom):
                mods.append(node.module or "")
            for mod in mods:
                if SEALED_MODULES & set(mod.split(".")):
                    out.append({"file": rel, "line": str(line),
                                "what": f"imports the sealed vault: {mod}"})
        elif isinstance(node, ast.Attribute) and node.attr in SEALED_NAMES:
            out.append({"file": rel, "line": str(line),
                        "what": f"reaches for {node.attr} -- that opens sealed evidence"})
        elif isinstance(node, ast.Name) and node.id in SEALED_NAMES:
            out.append({"file": rel, "line": str(line),
                        "what": f"names {node.id} -- that opens sealed evidence"})
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) \
                and id(node) not in skip and len(node.value) < 200 \
                and ("/" in node.value or node.value.endswith(".json")):
            for tok in SEALED_PATHS:
                if tok in node.value:
                    out.append({"file": rel, "line": str(line),
                                "what": f"names a sealed path: {node.value!r}"})
                    break
    seen: set[tuple[str, str]] = set()
    unique = []
    for row in out:
        key = (row["line"], row["what"])
        if key not in seen:
            seen.add(key)
            unique.append(row)
    return unique


def generator_isolation() -> dict[str, Any]:
    """Every proposer in the desk, and what it was found reaching for.

    Reports WHAT IT SCANNED as well as what it found: a wall that fires on nothing because it
    enumerated nothing is the failure mode this desk has paid for before (L1.49 -- a gate that
    never ran is a claim it cannot cash).
    """
    candidates: dict[str, Path] = {}
    for root in GENERATOR_ROOTS:
        base = ROOT / root
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.py")):
            rel = path.relative_to(ROOT).as_posix()
            if "/tests/" in rel or "__pycache__" in rel or rel in JUDGES:
                continue
            try:
                if GENERATOR_MARKER not in path.read_text("utf-8", errors="replace"):
                    continue
            except OSError:
                continue
            candidates[rel] = path
    for rel in EXTRA_GENERATORS:
        path = ROOT / rel
        if path.is_file() and rel not in JUDGES:
            candidates[rel] = path

    scanned: list[str] = []
    unparsed: list[str] = []
    findings: list[dict[str, str]] = []
    for rel, path in sorted(candidates.items()):
        try:
            tree = ast.parse(path.read_text("utf-8", errors="replace"), filename=rel)
        except (OSError, SyntaxError, ValueError):
            unparsed.append(rel)
            continue
        if rel not in EXTRA_GENERATORS and not _is_donor(tree):
            continue
        scanned.append(rel)
        findings.extend(_sealed_reads(rel, tree))
    return {"scanned": scanned, "n_scanned": len(scanned), "unparsed": unparsed,
            "judges_skipped": sorted(JUDGES), "findings": findings,
            "rule": "sealed data never reaches a generator; a generator may SEAL its own tail "
                    "(LockedHoldout.research) but may never open one"}


# --------------------------------------------------- the rewrite PATH, not only the rewrite (2026-09-24)
#: APPEND-ONLY MUST BE TRUE OF THE CODE, NOT ONLY OF THE FILE. The seal above catches a rewrite
#: AFTER it has happened, on whichever host next runs the fence -- and the 2026-09-24 forensic
#: showed how long that can take and how easily one real rewrite hides among benign ones. This
#: scan catches the CAPABILITY: a module that both names a sealed record file and contains a
#: truncating write is a module that can rewrite history, and it must be declared.
#:
#: Declaring is the point. `backfill_live_ledger_r.py` is a REAL whole-file rewriter and a correct
#: one -- it repaired an R multiple the writer had floored at zero on 141 of 151 live rows -- and
#: the desk should be able to name every such organ on demand. An undeclared one is the finding.
#: PRECISION IS THE WHOLE FENCE. A first cut flagged any module that MENTIONED a sealed file and
#: contained any truncating call anywhere: 157 findings, nearly all of them an organ that READS the
#: live ledger and writes its own report. That is the permanently-red shape this file's own
#: `_hashes` docstring was written about, and it would have been worse than nothing. So the target
#: of the write must be the sealed path: a truncating call is a finding only when the thing being
#: truncated, replaced or removed textually resolves to a sealed record file.
_TRUNCATING_ON_TARGET = ("write_text", "unlink", "truncate", "write_bytes")
_TRUNCATING_ON_DEST = {"replace": 1, "rename": 1, "move": 1, "copy": 1, "copyfile": 1}
INPLACE_DECLARED: dict[str, str] = {
    "scripts/backfill_live_ledger_r.py":
        "DECLARED whole-file rewriter (2026-09-16): repairs `r_multiple` on rows the writer "
        "floored at zero, stamping r_backfilled / r_basis / r_multiple_before. It recomputes from "
        "numbers already on the row and touches no traded quantity.",
}


def _sealed_basenames() -> tuple[str, ...]:
    """The sealed record files this scan can name UNAMBIGUOUSLY, and only those.

    Globbed entries are deliberately excluded and the exclusion is the honest part. The shadow
    ledgers' pattern reduces to the prefix `ledger_`, which is a substring of dozens of unrelated
    identifiers and paths in this repo (`clock_ledger`, `ingestion_ledger`, `throughput_ledger`);
    admitting it produced 65 findings that were all an organ writing its own report. A scan that
    cries wolf on 65 files is a scan nobody reads, so this one covers the two record files whose
    basenames are unique and SAYS SO in `scanned`, rather than covering everything badly.
    """
    return tuple(rel.rsplit("/", 1)[-1] for rel, _mode, _why in APPEND_ONLY if "*" not in rel)


#: Expression shapes that can carry a PATH. Propagating through anything else turned `rows =
#: _read(LEDGER)` into a sealed path, and then -- because the match was a bare substring -- every
#: one-letter variable in the module, and then every write in it. Word boundaries and path shapes
#: are what keep this scan to the writes that are actually aimed at a sealed record file.
_PATH_CALLS = frozenset({"Path", "resolve", "with_suffix", "with_name", "joinpath", "absolute",
                         "expanduser"})


def _path_shaped(value: ast.expr) -> bool:
    if isinstance(value, ast.BinOp) and isinstance(value.op, ast.Div):
        return True
    if isinstance(value, ast.Call):
        fn = value.func
        return (fn.attr if isinstance(fn, ast.Attribute) else
                getattr(fn, "id", "")) in _PATH_CALLS
    if isinstance(value, ast.Attribute):
        return value.attr in {"parent", "path"}
    return isinstance(value, ast.Name | ast.Constant)


def _mentions(text: str, tokens: Sequence[str], attrs: Sequence[str] = ()) -> bool:
    if any(re.search(rf"(?<![\w.]){re.escape(t)}(?![\w])", text) for t in tokens):
        return True
    return any(re.search(rf"\.{re.escape(a)}(?![\w])", text) for a in attrs)


def _sealed_attrs(tree: ast.AST, names: Sequence[str], sealed: set[str]) -> set[str]:
    """CLI option names whose DEFAULT is a sealed record path.

    The desk's one real whole-file rewriter takes the ledger as `--ledger`, defaulted to the
    sealed constant, and then works on `Path(a.ledger)`. Without this hop the scan cannot see the
    rewriter it exists to see, and `INPLACE_DECLARED` would be a hand-entered claim no
    enumeration backs -- the shape of a gate that never ran (L1.49).
    """
    out: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        if not (isinstance(fn, ast.Attribute) and fn.attr == "add_argument"):
            continue
        flag = next((a.value for a in node.args
                     if isinstance(a, ast.Constant) and isinstance(a.value, str)), "")
        default = next((k.value for k in node.keywords if k.arg == "default"), None)
        if not flag.startswith("--") or default is None:
            continue
        try:
            text = ast.unparse(default)
        except (AttributeError, ValueError):
            continue
        if any(n in text for n in names) or _mentions(text, sorted(sealed)):
            out.add(flag.lstrip("-").replace("-", "_"))
    return out


_Scope = ast.Module | ast.FunctionDef | ast.AsyncFunctionDef


def _own_body(scope: ast.AST) -> list[ast.AST]:
    """Every node inside `scope` that is not inside a NESTED function -- the scope's own code.

    SCOPE IS NOT COSMETIC HERE. Without it, `path = DESK / "data" / "live_ledger.jsonl"` in one
    function sealed the NAME `path` for the whole module, and the generic `_atomic_write(path,
    doc)` helper three hundred lines away became "rewrites the live ledger". Both remaining
    findings on the real desk were that, and both were wrong.
    """
    out: list[ast.AST] = []
    stack: list[ast.AST] = list(ast.iter_child_nodes(scope))
    while stack:
        node = stack.pop()
        out.append(node)
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda):
            stack.extend(ast.iter_child_nodes(node))
    return out


def _binds(nodes: Sequence[ast.AST]) -> list[tuple[str, ast.expr, str]]:
    binds: list[tuple[str, ast.expr, str]] = []
    for node in nodes:
        targets: list[ast.expr] = []
        if isinstance(node, ast.Assign):
            targets = list(node.targets)
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            targets = [node.target]
        value = getattr(node, "value", None)
        if not targets or value is None:
            continue
        try:
            text = ast.unparse(value)
        except (AttributeError, ValueError):
            continue
        for t in targets:
            if isinstance(t, ast.Name):
                binds.append((t.id, value, text))
    return binds


def _seal_from(binds: Sequence[tuple[str, ast.expr, str]], names: Sequence[str],
               base: set[str], attrs: Sequence[str] = ()) -> set[str]:
    sealed = set(base) | {v for v, _n, text in binds if any(n in text for n in names)}
    for _ in range(2):                                  # one hop, then settle
        for var, value, text in binds:
            if var not in sealed and _path_shaped(value)                     and _mentions(text, sorted(sealed), attrs):
                sealed.add(var)
    return sealed


def _sealed_vars(tree: ast.AST, names: Sequence[str]) -> set[str]:
    """Module-level variables that resolve to a sealed record PATH (module scope only)."""
    return _seal_from(_binds(_own_body(tree)), names, set())


def _targets_sealed(expr: ast.expr | None, names: Sequence[str], sealed: set[str],
                    attrs: Sequence[str] = ()) -> bool:
    if expr is None:
        return False
    try:
        text = ast.unparse(expr)
    except (AttributeError, ValueError):
        return False
    return any(n in text for n in names) or _mentions(text, sorted(sealed), attrs)


def _rewrite_sites(tree: ast.AST, names: Sequence[str]) -> list[tuple[int, str]]:
    """Truncating writes AIMED AT a sealed record file, judged one lexical scope at a time."""
    module_sealed = _sealed_vars(tree, names)
    attrs = sorted(_sealed_attrs(tree, names, module_sealed))
    scopes: list[tuple[list[ast.AST], set[str]]] = [(_own_body(tree), module_sealed)]
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            body = _own_body(node)
            scopes.append((body, _seal_from(_binds(body), names, module_sealed, attrs)))
    hits: list[tuple[int, str]] = []
    for body, sealed in scopes:
        hits.extend(_scope_sites(body, names, sealed, attrs))
    return sorted(set(hits))


def _scope_sites(nodes: Sequence[ast.AST], names: Sequence[str], sealed: set[str],
                 attrs: Sequence[str] = ()) -> list[tuple[int, str]]:
    hits: list[tuple[int, str]] = []
    for node in nodes:
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        attr = fn.attr if isinstance(fn, ast.Attribute) else ""
        bare = fn.id if isinstance(fn, ast.Name) else ""
        line = getattr(node, "lineno", 0)
        args = list(node.args)
        if attr == "open" or bare == "open":
            target = fn.value if attr == "open" and isinstance(fn, ast.Attribute) else (
                args[0] if args else None)
            mode = ""
            pos = args if attr == "open" else args[1:]
            for arg in pos + [k.value for k in node.keywords if k.arg == "mode"]:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    mode = arg.value
                    break
            if mode[:1] in ("w", "x") and _targets_sealed(target, names, sealed, attrs):
                hits.append((line, f"open(..., {mode!r}) truncates a sealed record file"))
        elif attr in _TRUNCATING_ON_TARGET and isinstance(fn, ast.Attribute) \
                and _targets_sealed(fn.value, names, sealed, attrs):
            hits.append((line, f".{attr}() rewrites or removes a sealed record file"))
        elif attr in _TRUNCATING_ON_DEST:
            idx = _TRUNCATING_ON_DEST[attr]
            if len(args) > idx and _targets_sealed(args[idx], names, sealed, attrs):
                hits.append((line, f"{attr}(..., <sealed record file>) replaces it wholesale"))
    return hits


def inplace_rewrite_scan() -> dict[str, Any]:
    """Every module that can rewrite a sealed record file IN PLACE, declared or not.

    Reports what it enumerated as well as what it found: a wall that scanned nothing would also
    be green (L1.49).
    """
    names = _sealed_basenames()
    scanned: list[str] = []
    findings: list[dict[str, str]] = []
    declared_seen: list[str] = []
    stale = [rel for rel in INPLACE_DECLARED if not (ROOT / rel).is_file()]
    for root in ("scripts", "desks/mt5", "libs", "ops"):
        base = ROOT / root
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.py")):
            rel = path.relative_to(ROOT).as_posix()
            if "/tests/" in rel or "__pycache__" in rel \
                    or rel.rsplit("/", 1)[-1].startswith("test_"):
                continue
            try:
                src = path.read_text("utf-8", errors="replace")
            except OSError:
                continue
            if not any(n in src for n in names):
                continue
            scanned.append(rel)
            try:
                tree = ast.parse(src, filename=rel)
            except (SyntaxError, ValueError):
                continue
            sites = _rewrite_sites(tree, names)
            if not sites:
                continue
            if rel in INPLACE_DECLARED:
                declared_seen.append(rel)
                continue
            line, what = sites[0]
            findings.append({"file": rel, "line": str(line),
                             "what": f"{what} ({len(sites)} site(s)) and is NOT declared: a "
                                     "sealed record is append-only in code as well as on disk -- "
                                     "append instead, or declare it in INPLACE_DECLARED"})
    return {"scanned": scanned, "n_scanned": len(scanned), "declared": sorted(declared_seen),
            "declared_missing": sorted(stale), "undeclared": findings,
            "rule": "a module that can rewrite a sealed record file in place must be declared by "
                    "name with its reason; an undeclared one is the finding"}


def _hashes() -> dict[str, str]:
    """SHA-256 of each guarded file, over LINE-ENDING-NORMALISED bytes.

    WHY NORMALISED, measured 2026-09-12 on the Windows trading box. A signature is a claim about
    CONTENT. Hashing raw bytes made it a claim about content AND about how the checkout happened
    to write newlines, and those two came apart:

        working tree  desks/mt5/research/promoter.py  ->  766a1119abcd663a   (CRLF)
        HEAD blob     desks/mt5/research/promoter.py  ->  8e1f39e3f4a6905f   (LF)

    Identical code, byte-different files. `run_law_gate` judges HEAD in a DETACHED WORKTREE
    whenever the tree is dirty -- and this box's tree is permanently dirty, because live state
    files (gateway_state.json and friends) are tracked and rewritten every pass. So the fence
    always hashed the LF checkout while `--sign` always hashed the CRLF working copy, and the two
    could never agree. The fence reported a BREACH on a file nobody had touched, on every run, and
    since a failing law fence refuses the push, the trading box could not reach origin at all.

    That is the worst shape a constitutional fence can take: permanently red, red about nothing,
    and blocking. A fence that cannot be satisfied by correct code stops being read as evidence
    and starts being read as an obstacle -- and then the day it fires on a REAL tamper, it looks
    exactly like the eleven days it fired on newlines.

    Normalising CRLF -> LF makes the hash mean what it always claimed to mean. It does not weaken
    the guard: any change to a byte that is not a carriage return still changes the digest, so
    every tamper this caught before it still catches.
    """
    out = {}
    for rel in IMMUTABLE:
        p = ROOT / rel
        if not p.exists():
            out[rel] = "<absent>"
            continue
        raw = p.read_bytes().replace(b"\r\n", b"\n")
        out[rel] = hashlib.sha256(raw).hexdigest()[:16]
    return out


def sign(by: str) -> dict[str, object]:
    doc: dict[str, object] = {"signed_utc": datetime.now(tz=UTC).isoformat(), "signed_by": by,
           "files": _hashes(),
           "append_only": append_only_seal(),
           "vintage": vintage_seal(),
           "rule": ("these files judge hypotheses; a change must arrive with a re-signed "
                    "manifest -- research organs may change the hypothesis, never the judge"),
           "record_rule": ("the ledgers, the live fills, the cost surface and the lineage chain "
                           "are RECORDS: the sealed prefix may never change, only grow, and a "
                           "measured cost surface may be rebuilt but never back-dated")}
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(doc, indent=1), "utf-8")
    return doc


def wall_rows() -> list[dict[str, Any]]:
    """Every non-frozen guarded path with its verdict, absent ones included and named.

    Absence is a verdict here, never a pass: a host without the forward ledgers reports them
    UNMEASURED, and `--json` carries the row so a caller can tell "nothing to check" from
    "checked and clean" (L1.28a / WS-005).
    """
    try:
        doc = json.loads(MANIFEST.read_text("utf-8"))
    except (OSError, ValueError):
        doc = {}
    sealed_a = doc.get("append_only") if isinstance(doc, dict) else None
    sealed_v = doc.get("vintage") if isinstance(doc, dict) else None
    return _append_only_rows(sealed_a if isinstance(sealed_a, Mapping) else {}) + \
        _vintage_rows(sealed_v if isinstance(sealed_v, Mapping) else {})


def check() -> list[dict[str, str]]:
    try:
        rec = json.loads(MANIFEST.read_text("utf-8")).get("files") or {}
    except (OSError, ValueError):
        return [{"file": str(MANIFEST), "why": "no IMMUTABLE_MANIFEST.json; run --sign once"}]
    now = _hashes()
    out = []
    for rel, h in now.items():
        if rel not in rec:
            out.append({"file": rel, "why": "immutable file not in the signed manifest"})
        elif rec[rel] != h:
            out.append({"file": rel, "why": f"changed since signing ({rec[rel]} -> {h})"})
    for rel in rec:
        if rel not in now:
            out.append({"file": rel, "why": "in the manifest but no longer declared immutable"})
    for row in wall_rows():
        if row["status"] == "breach":
            out.append({"file": str(row["path"]), "why": str(row["why"])})
    for hit in generator_isolation()["findings"]:
        out.append({"file": f"{hit['file']}:{hit['line']}",
                    "why": f"GENERATOR READS SEALED DATA -- {hit['what']}"})
    for hit in inplace_rewrite_scan()["undeclared"]:
        out.append({"file": f"{hit['file']}:{hit['line']}",
                    "why": f"UNDECLARED IN-PLACE REWRITE OF A SEALED RECORD -- {hit['what']}"})
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sign", action="store_true")
    # SEAL THE RECORDS WITHOUT BLESSING THE CODE. `--sign` re-signs everything, so on a box whose
    # frozen files have already drifted it would launder those drifts in the same act -- the one
    # thing this fence exists to prevent. This flag writes ONLY the record seals and leaves the
    # `files` section exactly as it was, so a stale judge hash stays red while the ledgers,
    # forward clocks and cost surface start being watched today.
    ap.add_argument("--seal-records", action="store_true")
    # RE-SIGN THE JUDGE WITHOUT ERASING THE RECORDS. The mirror of `--seal-records`, and the
    # reason it is needed was measured today: eight frozen files had drifted since the
    # 2026-09-12 signing, and the ONLY way to re-sign them was `--sign`, which also rewrites
    # `append_only` -- overwriting the sealed prefix hashes of 192 forward ledgers with today's
    # bytes in the same act. That is not a re-sign, it is the destruction of the only evidence
    # that can answer "was this record rewritten", performed as a side effect of an unrelated
    # housekeeping step. A fence whose maintenance act destroys its own evidence has a design
    # defect, not a policy problem. This flag writes ONLY `files`.
    ap.add_argument("--sign-files", action="store_true")
    ap.add_argument("--by", default="principal")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    if a.sign_files:
        try:
            doc = json.loads(MANIFEST.read_text("utf-8"))
        except (OSError, ValueError):
            doc = {}
        if not isinstance(doc, dict):
            doc = {}
        files = _hashes()
        doc["files"] = files
        doc["signed_utc"] = datetime.now(tz=UTC).isoformat()
        doc["signed_by"] = a.by
        MANIFEST.parent.mkdir(parents=True, exist_ok=True)
        MANIFEST.write_text(json.dumps(doc, indent=1), "utf-8")
        print(f"judge files signed by {a.by}: {len(files)} files "
              "(the record seals were NOT touched)")
        return 0
    if a.sign:
        d = sign(a.by)
        print(f"immutable manifest signed by {a.by}: {len(d['files'])} files")  # type: ignore[arg-type]
        return 0
    if a.seal_records:
        try:
            doc = json.loads(MANIFEST.read_text("utf-8"))
        except (OSError, ValueError):
            doc = {}
        if not isinstance(doc, dict):
            doc = {}
        seal_a, seal_v = append_only_seal(), vintage_seal()
        doc["append_only"] = seal_a
        doc["vintage"] = seal_v
        doc["records_sealed_utc"] = datetime.now(tz=UTC).isoformat()
        doc["records_sealed_by"] = a.by
        doc["record_rule"] = ("the ledgers, the live fills, the cost surface and the lineage "
                              "chain are RECORDS: the sealed prefix may never change, only "
                              "grow, and a measured cost surface may be rebuilt, never "
                              "back-dated")
        MANIFEST.parent.mkdir(parents=True, exist_ok=True)
        MANIFEST.write_text(json.dumps(doc, indent=1), "utf-8")
        print(f"record wall sealed by {a.by}: {len(seal_a)} append-only, {len(seal_v)} vintage "
              "(the frozen-file section was NOT re-signed)")
        return 0
    findings = check()
    rows = wall_rows()
    gen = generator_isolation()
    inplace = inplace_rewrite_scan()
    tally: dict[str, int] = {}
    for row in rows:
        tally[str(row["status"])] = tally.get(str(row["status"]), 0) + 1
    if a.json:
        print(json.dumps({"ok": not findings, "findings": findings, "wall": rows,
                          "generator_isolation": gen, "inplace_rewrite": inplace}, indent=1))
    else:
        print(f"immutable evaluator: {'OK' if not findings else f'{len(findings)} breach(es)'}")
        print(f"  frozen files {len(IMMUTABLE)}  records {len(rows)} "
              f"({', '.join(f'{k}={v}' for k, v in sorted(tally.items())) or 'none'})  "
              f"generators scanned {gen['n_scanned']}  "
              f"rewrite scan {inplace['n_scanned']} module(s), "
              f"{len(inplace['declared'])} declared rewriter(s)")
        for f in findings:
            print(f"  BREACH {f['file']}: {f['why']}")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
