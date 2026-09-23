#!/usr/bin/env python3
"""THE UNDERSTANDING SEAT -- the organ that guarantees nothing stays un-understood.

THE PRINCIPAL'S ORDER (2026-09-17, permanent): maximum multilingual and slang intelligence, so
the desk NEVER has an issue understanding anything and exploits every piece of information in
every global language. **NOTHING IS DROPPED FOR BEING UNREADABLE.**

WHAT THIS IS FOR. `libs/research/polyglot.py` reads a hundred and one languages without a model
or a network call, and it is still not enough on its own: a Georgian competition write-up scores
0.95 on SCRIPT and has no terminology map, a romanised Telegram post scores 0.45 on everything,
and a document in a language nobody here has profiled scores `und`. Before this organ those three
populations had exactly one fate -- read with English rules, found empty, and reported as an empty
forest. That is the L1.28a failure: absence indistinguishable from emptiness.

THE LOOP, and it is the whole module.

    1  READ every normalised moat document, every registry claim and every intelligence row.
    2  UNDERSTAND each one natively through polyglot.
    3  ASK the LLM seats about the ones that are still not understood -- once, tracked by a
       cursor, in the seats' own intake shape.
    4  INGEST their answers back into the claims (translation BESIDE the original, never over
       it) and into the registry's memory.
    5  MEASURE: understood natively / via a seat / still pending, per language, and NAME the
       languages that have no terminology map at all. That last list is the product: it is what
       the source scouts extend polyglot with, and until this organ existed nothing on this desk
       could produce it.

THREE THINGS IT IS DELIBERATE ABOUT.

**THE TRANSLATION NEVER REPLACES THE ORIGINAL.** A claim's `text` column is the source's own
words and this organ does not write to it. The seat's translation lands in `provenance_json`
under `understanding`, beside the verbatim claim, because a silently machine-translated claim
cannot be audited back to its ground -- which is the one thing a verbatim capture is for.

**THE TASK FILE IS AN OBJECT, NOT A LIST, AND THAT IS NOT A STYLE CHOICE.**
`miner_candidate_compiler._rows` harvests every LIST value in every json file under the
intelligence roots. A translation queue written as a list would therefore be read back as
evidence, and the same document would be compiled twice -- once as the claim it is, and once as
the desk's own request to read it -- each paying the multiple-testing charge the two-lane order
exists to protect. Keyed by `task_id`, the file is inert to the compiler and idempotent for the
seats, which want to look a task up by id anyway.

**ASKED ONCE.** The cursor records every `task_id` that has been put to the seats. A pass that
re-asks a question already in flight burns seat budget on work that is already queued, and the
seats have no way to tell the repeat from a new document.

    python understanding_seat.py --budget-s 240
    python understanding_seat.py --dry-run    # measures and prints; writes NOTHING
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
import time
from collections.abc import Iterator, Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parents[1]
for _p in (str(_ROOT), str(_DESK), str(_DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.moat import registry as reg  # noqa: E402
from libs.research import lead_schema as ls  # noqa: E402
from libs.research import polyglot as pg  # noqa: E402

SEAT = "understanding_seat"
#: The two intelligence roots the compiler reads, so this organ measures the same population.
INTEL_ROOTS: tuple[Path, ...] = (_ROOT / "data" / "intelligence",
                                 _DESK / "data" / "intelligence")
#: Seat output goes through `data/intelligence/<seat>/` (CLAUDE.md). Module globals so a test can
#: point the whole organ at `tmp_path`; every path below is derived at call time.
SEAT_DIR = _DESK / "data" / "intelligence" / SEAT
NORMALIZED = _ROOT / "data" / "moat" / "normalized_intel"
REPORT = _DESK / "reports" / "UNDERSTANDING.json"

UNMEASURED = "UNMEASURED"
RULE = pg.RULE

#: What the seats are asked for. Four asks, because a translation alone leaves the desk with a
#: readable sentence and no idea which instrument, which mechanism or which participant it is
#: about -- and those three are what makes a claim testable rather than merely legible.
ASKS: tuple[str, ...] = ("translate", "name_instruments", "name_mechanism", "name_actor")

#: Bounds. This box has 8 GB and eleven thousand intelligence artifacts; a pass that reads them
#: all would be a memory event, not a measurement. Whatever a pass does not reach is reported as
#: `pending`, never as understood and never as absent.
MAX_FILES = 900
MAX_DOCS = 6000
MAX_TASKS = 400
MAX_TEXT_CHARS = 4000
#: A row with less text than this has nothing for a translator to work on: it is a label, not a
#: document. It is still COUNTED (as `too_short`), because a miner producing only labels is a
#: collector defect and hiding it inside a translation backlog is how it stays invisible.
MIN_TASK_CHARS = 24
#: Cursor entries kept. Older asks fall off; a document that reappears is re-asked, which is the
#: correct behaviour for a queue that must never lose an item permanently.
MAX_CURSOR = 20_000


# ------------------------------------------------------------------------- small helpers
def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _stamp() -> str:
    return datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S")


def _atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=1, ensure_ascii=False, default=str)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
    finally:
        with suppress(FileNotFoundError, PermissionError):
            os.unlink(name)


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _rows(doc: Any) -> list[dict[str, Any]]:
    """Rows out of one artifact, the compiler's own reading so the two see one population."""
    if isinstance(doc, list):
        return [r for r in doc if isinstance(r, dict)]
    if not isinstance(doc, dict):
        return []
    if isinstance(doc.get("discoveries"), list):
        return [r for r in doc["discoveries"] if isinstance(r, dict)]
    out: list[dict[str, Any]] = []
    for value in doc.values():
        if isinstance(value, dict) and isinstance(value.get("discoveries"), list):
            out.extend(r for r in value["discoveries"] if isinstance(r, dict))
        elif isinstance(value, list):
            out.extend(r for r in value if isinstance(r, dict))
    return out


def task_id_of(doc_id: str, text: str) -> str:
    """The identity of one ASK. Text-sensitive, so a re-crawled document whose body changed is a
    new question and an unchanged one is never asked twice."""
    payload = f"{doc_id}\x00{text[:400]}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


# ------------------------------------------------------------------------- the documents
@dataclass(frozen=True)
class Doc:
    """One readable thing, wherever it came from: a moat document, a registry claim, a row."""

    doc_id: str
    source_id: str
    text: str
    url: str
    origin: str
    declared_language: str = ""
    claim_id: str = ""


def _declared_language(row: Mapping[str, Any]) -> str:
    """The language a row CLAIMS, ignoring the fields that mean something else.

    `github` rows carry `language: "Python"` -- a PROGRAMMING language -- and reading that as a
    natural language would file every repository under a language that does not exist. The
    declared value is therefore only trusted when polyglot knows it as a language code.
    """
    for key in ("lang", "language", "locale"):
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            code = value.strip()
            if code in pg.LANGUAGES or code.split("-")[0] in pg.LANGUAGES:
                return code
    return ""


def normalized_documents(limit: int = MAX_DOCS) -> Iterator[Doc]:
    """The moat's normalised documents. The collectors wrote them; this reads them."""
    root = NORMALIZED
    if not root.exists():
        return
    seen = 0
    for path in sorted(root.rglob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        doc = _read_json(path)
        if not isinstance(doc, dict):
            continue
        text = str(doc.get("text") or "")[:MAX_TEXT_CHARS]
        provenance = doc.get("provenance")
        url = str(provenance.get("url") or "") if isinstance(provenance, Mapping) else ""
        yield Doc(doc_id=str(doc.get("doc_id") or path.stem),
                  source_id=str(doc.get("source_id") or path.parent.name),
                  text=text, url=url, origin="moat",
                  declared_language=_declared_language(doc))
        seen += 1
        if seen >= limit:
            return


def registry_claims(conn: Any, limit: int = MAX_DOCS) -> list[Doc]:
    """The registry's claims table. Each claim is its own document for understanding purposes --
    it is the unit the desk counts, deduplicates and contradicts."""
    try:
        rows = conn.execute(
            "SELECT claim_id, doc_id, source_id, text, language, provenance_json FROM claims "
            "ORDER BY created_at DESC LIMIT ?", (int(limit),)).fetchall()
    except Exception:            # a registry without the moat tables is UNMEASURED, not a crash
        return []
    out: list[Doc] = []
    for row in rows:
        data = dict(row)
        provenance = {}
        with suppress(ValueError, TypeError):
            provenance = json.loads(data.get("provenance_json") or "{}")
        out.append(Doc(doc_id=str(data.get("doc_id") or ""),
                       source_id=str(data.get("source_id") or ""),
                       text=str(data.get("text") or "")[:MAX_TEXT_CHARS],
                       url=str(provenance.get("url") or "") if isinstance(provenance, dict) else "",
                       origin="claims",
                       declared_language=_declared_language(data),
                       claim_id=str(data.get("claim_id") or "")))
    return out


def intelligence_documents(budget_s: float, limit: int = MAX_DOCS,
                           max_files: int = MAX_FILES) -> Iterator[Doc]:
    """Every intelligence row under both roots, newest artifact first, read through the desk's
    ONE intake contract (`lead_schema.leads_from_intelligence_row`).

    Reusing the lead schema rather than a private field chain is the point: this organ then
    measures exactly the population the compiler compiles, so "understood" and "compiled" are
    counts of the same thing and the two reports can be compared.
    """
    started = time.monotonic()
    by_dir: dict[str, list[Path]] = {}
    for root in INTEL_ROOTS:
        if not root.exists():
            continue
        for p in root.rglob("*.json"):
            if p.is_file() and p.parent.name != SEAT:
                by_dir.setdefault(str(p.parent), []).append(p)
    # ROUND-ROBIN ACROSS SOURCE DIRECTORIES, newest first inside each, and that ordering is the
    # whole reason the gap list means anything. A flat newest-first walk is dominated by whichever
    # miner wrote last -- measured on this box, the first 900 artifacts by mtime were one English
    # crawler, so the language census said "en" and the gap list came back empty. A forest that
    # is not sampled reports as absent, which is the exact failure this organ exists to end.
    for group in by_dir.values():
        group.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    paths: list[Path] = []
    depth = 0
    while len(paths) < max_files:
        added = False
        for group in by_dir.values():
            if depth < len(group):
                paths.append(group[depth])
                added = True
                if len(paths) >= max_files:
                    break
        if not added:
            break
        depth += 1
    seen = 0
    for path in paths:
        if time.monotonic() - started > budget_s:
            return
        for row in _rows(_read_json(path)):
            leads = ls.leads_from_intelligence_row(row, seat=path.parent.name)
            for lead in leads:
                yield Doc(doc_id=lead.doc_id, source_id=lead.source_id,
                          text=lead.claim_text[:MAX_TEXT_CHARS], url=lead.url_or_ref,
                          origin=f"intel:{path.parent.name}",
                          declared_language=_declared_language(row))
                seen += 1
                if seen >= limit:
                    return


# ------------------------------------------------------------------------- the cursor
def cursor_path() -> Path:
    return SEAT_DIR / "cursor.json"


def read_cursor() -> dict[str, Any]:
    doc = _read_json(cursor_path())
    if not isinstance(doc, dict):
        return {"asked": {}, "answered": {}, "updated_at": ""}
    doc.setdefault("asked", {})
    doc.setdefault("answered", {})
    return doc


def write_cursor(cursor: Mapping[str, Any]) -> Path:
    asked = dict(cursor.get("asked") or {})
    answered = dict(cursor.get("answered") or {})
    if len(asked) > MAX_CURSOR:
        keep = sorted(asked.items(), key=lambda kv: str(kv[1].get("at") or ""),
                      reverse=True)[:MAX_CURSOR]
        asked = dict(keep)
    path = cursor_path()
    _atomic_json(path, {"asked": asked, "answered": answered, "updated_at": _now(),
                        "rule": RULE})
    return path


# ------------------------------------------------------------------------- tasks
def task_row(doc: Doc, u: pg.Understanding) -> dict[str, Any]:
    """ONE TASK, in the seats' intake shape.

    `{kind, text, lang_guess, url, doc_id, asks}` is the contract; everything else on the row is
    what polyglot already worked out, so a seat is not asked to redo the part the desk can do
    for free and can correct the part it got wrong.
    """
    return {
        "kind": "understand",
        "task_id": task_id_of(doc.doc_id, doc.text),
        "text": doc.text,
        "lang_guess": u.lang,
        "url": doc.url,
        "doc_id": doc.doc_id,
        "asks": list(ASKS),
        "seat": SEAT,
        "at": _now(),
        "source_id": doc.source_id,
        "claim_id": doc.claim_id,
        "origin": doc.origin,
        "script": u.script,
        "confidence": round(u.confidence, 3),
        "alternatives": [[a, b] for a, b in u.alternatives],
        "declared_language": doc.declared_language,
        "why": u.needs_seat_reason,
        "priority": ("no_terminology_map" if not u.has_terminology
                     else "non_latin_script" if u.script not in ("Latin", "")
                     else "low_confidence"),
        "has_terminology": u.has_terminology,
        "polyglot_instruments": list(u.instruments),
        "polyglot_concepts": [c.concept_id for c in u.concepts],
        "answer_shape": ANSWER_SHAPE,
        "rule": RULE,
    }


#: The shape an ANSWER must come back in, carried ON the task so a seat never has to guess.
ANSWER_SHAPE: dict[str, str] = {
    "kind": "understanding_answer",
    "task_id": "the task_id this answers",
    "doc_id": "the doc_id this answers",
    "lang": "BCP-47-ish code of the ORIGINAL text, e.g. ka, am, ug",
    "translation": "English translation of `text`, verbatim in meaning, no summarising",
    "instruments": "[MT5 symbols the text is about, e.g. XAUUSD]",
    "mechanism": "one mechanism class the claim is about, or '' when it names none",
    "actor": "who is forced or incentivised to act, or '' when the text names none",
    "concepts": "[desk concept ids, or community terms the desk has no id for]",
    "terms": "{native term: english gloss} for the slang the text used",
    "seat": "kimi | deepseek | ...",
}


def write_tasks(rows: Sequence[Mapping[str, Any]]) -> Path:
    """Land one batch of tasks.

    THE CONTAINER IS AN OBJECT KEYED BY task_id, and that is load-bearing:
    `miner_candidate_compiler._rows` reads every LIST value under the intelligence roots as
    evidence, so a task list would be compiled into candidates -- the same document once as a
    claim and once as the desk's own request to read it, both paying the multiplicity charge.
    """
    path = SEAT_DIR / f"tasks_{_stamp()}.json"
    _atomic_json(path, {
        "kind": "understand_tasks", "seat": SEAT, "at": _now(), "n": len(rows),
        "asks": list(ASKS), "answer_shape": ANSWER_SHAPE, "rule": RULE,
        "tasks": {str(r["task_id"]): dict(r) for r in rows},
    })
    return path


# ------------------------------------------------------------------------- answers
@dataclass
class Answer:
    """One seat's reading of one document."""

    task_id: str
    doc_id: str
    lang: str = ""
    translation: str = ""
    instruments: list[str] = field(default_factory=list)
    mechanism: str = ""
    actor: str = ""
    concepts: list[str] = field(default_factory=list)
    terms: dict[str, str] = field(default_factory=dict)
    seat: str = ""
    path: str = ""


def _answer_from(row: Mapping[str, Any], path: str) -> Answer | None:
    doc_id = str(row.get("doc_id") or "")
    task = str(row.get("task_id") or "")
    if not doc_id and not task:
        return None
    raw_terms = row.get("terms")
    return Answer(
        task_id=task, doc_id=doc_id,
        lang=str(row.get("lang") or row.get("language") or ""),
        translation=str(row.get("translation") or row.get("english") or ""),
        instruments=[str(s) for s in (row.get("instruments") or []) if isinstance(s, str)],
        mechanism=str(row.get("mechanism") or ""),
        actor=str(row.get("actor") or ""),
        concepts=[str(c) for c in (row.get("concepts") or []) if isinstance(c, str)],
        terms={str(k): str(v) for k, v in (raw_terms.items()
                                           if isinstance(raw_terms, Mapping) else ())},
        seat=str(row.get("seat") or ""), path=path)


def read_answers() -> list[Answer]:
    """Every answer the seats have written. Tolerant of both containers: this organ writes an
    OBJECT keyed by task_id and a seat may perfectly reasonably write a list."""
    out: list[Answer] = []
    if not SEAT_DIR.exists():
        return out
    for path in sorted(SEAT_DIR.glob("answers_*.json")):
        doc = _read_json(path)
        rows: list[Mapping[str, Any]] = []
        if isinstance(doc, list):
            rows = [r for r in doc if isinstance(r, Mapping)]
        elif isinstance(doc, Mapping):
            answers = doc.get("answers")
            if isinstance(answers, Mapping):
                rows = [r for r in answers.values() if isinstance(r, Mapping)]
            elif isinstance(answers, list):
                rows = [r for r in answers if isinstance(r, Mapping)]
            elif doc.get("doc_id") or doc.get("task_id"):
                rows = [doc]
        for row in rows:
            answer = _answer_from(row, str(path))
            if answer is not None:
                out.append(answer)
    return out


def ingest_answer(conn: Any, answer: Answer) -> dict[str, int]:
    """One answer into the claims table and the registry's memory.

    THE ORIGINAL TEXT IS NOT TOUCHED. The translation, the concepts and the instruments land in
    `provenance_json` under `understanding`, BESIDE the verbatim claim. The `language` column is
    corrected only when the seat named one -- a blank answer never overwrites a measurement.
    """
    counts = {"claims_updated": 0, "memories": 0}
    rows: list[Mapping[str, Any]] = []
    with suppress(Exception):
        rows = [dict(r) for r in conn.execute(
            "SELECT claim_id, language, instruments_json, provenance_json FROM claims "
            "WHERE doc_id=?", (answer.doc_id,)).fetchall()]
    block = {
        "understood_by": answer.seat or "seat", "at": _now(), "task_id": answer.task_id,
        "translation": answer.translation, "lang": answer.lang, "mechanism": answer.mechanism,
        "actor": answer.actor, "concepts": list(answer.concepts), "terms": dict(answer.terms),
        "instruments": list(answer.instruments), "source_file": answer.path,
        "rule": RULE,
    }
    for row in rows:
        provenance: dict[str, Any] = {}
        with suppress(ValueError, TypeError):
            parsed = json.loads(str(row.get("provenance_json") or "{}"))
            provenance = parsed if isinstance(parsed, dict) else {}
        provenance["understanding"] = block
        instruments: list[str] = []
        with suppress(ValueError, TypeError):
            parsed_i = json.loads(str(row.get("instruments_json") or "[]"))
            instruments = [str(s) for s in parsed_i] if isinstance(parsed_i, list) else []
        for symbol in answer.instruments:
            if symbol not in instruments:
                instruments.append(symbol)
        language = answer.lang or str(row.get("language") or "")
        with suppress(Exception):
            conn.execute(
                "UPDATE claims SET language=?, instruments_json=?, provenance_json=? "
                "WHERE claim_id=?",
                (language, json.dumps(instruments, sort_keys=True),
                 json.dumps(provenance, sort_keys=True, ensure_ascii=False, default=str),
                 row.get("claim_id")))
            counts["claims_updated"] += 1
    statement = (f"understood {answer.doc_id} ({answer.lang or 'lang UNMEASURED'}) via "
                 f"{answer.seat or 'a seat'}: {answer.translation[:280]}")
    with suppress(Exception):
        reg.remember("understanding", statement, kind="understanding",
                     memory_key=f"understanding:{answer.doc_id}", result="understood",
                     payload=block, conn=conn)
        counts["memories"] += 1
    return counts


# ------------------------------------------------------------------------- the pass
def _blank_lang_row() -> dict[str, Any]:
    return {"documents": 0, "understood_native": 0, "understood_via_seat": 0, "pending": 0,
            "pending_too_short": 0, "has_terminology": False, "slang_hits": 0,
            "instruments_named": 0}


def run(*, budget_s: float = 240.0, dry_run: bool = False, max_docs: int = MAX_DOCS,
        max_tasks: int = MAX_TASKS, conn: Any = None) -> dict[str, Any]:
    """One pass: read, understand, ask, ingest, measure. Returns the report payload."""
    started = time.monotonic()
    close_after = conn is None
    c = conn if conn is not None else reg.connect()
    cursor = read_cursor()
    asked: dict[str, Any] = dict(cursor.get("asked") or {})
    answered: dict[str, Any] = dict(cursor.get("answered") or {})

    report: dict[str, Any] = {
        "at": _now(), "seat": SEAT, "budget_s": float(budget_s), "dry_run": bool(dry_run),
        "documents": 0, "understood_native": 0, "understood_via_seat": 0, "pending": 0,
        "pending_too_short": 0,
        "by_language": {}, "languages_seen": [], "languages_without_terminology": [],
        "slang_hits": 0, "instruments_named": 0, "concepts": {},
        "by_origin": {}, "tasks_written": 0, "tasks_file": "", "tasks_already_asked": 0,
        "tasks_too_short": 0, "answers_seen": 0, "answers_ingested": 0, "claims_updated": 0,
        "memories_written": 0, "budget_stopped": False,
        "unmeasured": {}, "rule": RULE,
    }
    try:
        # ---------------------------------------------------------- 1. the answers already in
        answers = read_answers()
        report["answers_seen"] = len(answers)
        understood_via_seat: set[str] = {a.doc_id for a in answers if a.doc_id}
        if not dry_run:
            for answer in answers:
                key = answer.task_id or answer.doc_id
                if key in answered:
                    continue
                counts = ingest_answer(c, answer)
                report["claims_updated"] += counts["claims_updated"]
                report["memories_written"] += counts["memories"]
                report["answers_ingested"] += 1
                answered[key] = {"at": _now(), "doc_id": answer.doc_id, "seat": answer.seat}
            with suppress(Exception):
                c.commit()

        # ---------------------------------------------------------- 2. read and understand
        left = budget_s - (time.monotonic() - started)
        sources: list[Iterator[Doc] | list[Doc]] = [
            normalized_documents(max_docs),
            registry_claims(c, max_docs),
            intelligence_documents(max(left, 1.0), max_docs),
        ]
        by_language: dict[str, dict[str, Any]] = report["by_language"]
        by_origin: dict[str, dict[str, int]] = report["by_origin"]
        concept_counts: dict[str, int] = report["concepts"]
        seen_docs: set[str] = set()
        candidates: list[tuple[Doc, pg.Understanding]] = []

        for stream in sources:
            for doc in stream:
                if time.monotonic() - started > budget_s:
                    report["budget_stopped"] = True
                    break
                key = f"{doc.origin}:{doc.doc_id}:{doc.claim_id}"
                if key in seen_docs:
                    continue
                seen_docs.add(key)
                if report["documents"] >= max_docs:
                    report["budget_stopped"] = True
                    break
                u = pg.understand(doc.text)
                report["documents"] += 1
                lang = u.lang or "und"
                row = by_language.setdefault(lang, _blank_lang_row())
                row["documents"] += 1
                row["has_terminology"] = u.has_terminology
                row["slang_hits"] += len(u.concepts)
                row["instruments_named"] += len(u.instruments)
                report["slang_hits"] += len(u.concepts)
                report["instruments_named"] += len(u.instruments)
                for concept in u.concepts:
                    concept_counts[concept.concept_id] = \
                        concept_counts.get(concept.concept_id, 0) + 1
                origin_row = by_origin.setdefault(doc.origin.split(":")[0],
                                                  {"documents": 0, "pending": 0})
                origin_row["documents"] += 1

                if not u.needs_seat:
                    report["understood_native"] += 1
                    row["understood_native"] += 1
                elif doc.doc_id in understood_via_seat:
                    report["understood_via_seat"] += 1
                    row["understood_via_seat"] += 1
                else:
                    report["pending"] += 1
                    row["pending"] += 1
                    origin_row["pending"] += 1
                    # A LABEL IS NOT A FOREIGN DOCUMENT. "News EA" is seven characters and no
                    # translator can do anything with it; counting it beside a Georgian article
                    # would make the backlog look like a language problem when it is a collector
                    # one. Still pending, still named, counted apart.
                    if len(doc.text.strip()) < MIN_TASK_CHARS:
                        report["pending_too_short"] += 1
                        row["pending_too_short"] += 1
                    candidates.append((doc, u))
            if report["budget_stopped"]:
                break

        # ---------------------------------------------------------- 3. ask, once
        # PRIORITY IS NOT A FILTER. Everything pending stays pending and is asked on some pass;
        # this only decides WHICH ONES GO FIRST when the batch is bounded. A language with no
        # terminology map buys the most understanding per seat call, a non-Latin script the next
        # most, and a short ASCII label the least -- and the last group is mostly collector
        # debris that the compiler already calls EMPTY_CAPTURE.
        candidates.sort(key=lambda pair: (
            pair[1].has_terminology,
            pair[1].script in ("Latin", ""),
            round(pair[1].confidence, 2),
            -len(pair[0].text),
        ))
        task_rows: list[dict[str, Any]] = []
        for doc, u in candidates:
            if len(task_rows) >= max_tasks:
                break
            if len(doc.text.strip()) < MIN_TASK_CHARS:
                report["tasks_too_short"] += 1
                continue
            tid = task_id_of(doc.doc_id, doc.text)
            if tid in asked:
                report["tasks_already_asked"] += 1
                continue
            row_out = task_row(doc, u)
            task_rows.append(row_out)
            asked[tid] = {"at": _now(), "doc_id": doc.doc_id, "lang": u.lang,
                          "why": u.needs_seat_reason[:160]}
        if task_rows and not dry_run:
            path = write_tasks(task_rows)
            report["tasks_written"] = len(task_rows)
            report["tasks_file"] = str(path)
        elif task_rows:
            report["tasks_written"] = 0
            report["tasks_file"] = f"DRY RUN: {len(task_rows)} task(s) not written"
        # THE CURSOR IS WRITTEN WHENEVER EITHER HALF MOVED, not only when tasks were. The first
        # version wrote it only alongside a task file, so a pass that ingested answers and asked
        # nothing new lost the `answered` half -- and re-ingested every answer, every hour,
        # forever, each one a fresh registry memory for a document already understood.
        if not dry_run and (task_rows or report["answers_ingested"]):
            write_cursor({"asked": asked, "answered": answered})

        # ---------------------------------------------------------- 4. measure
        report["languages_seen"] = sorted(by_language)
        report["languages_without_terminology"] = pg.languages_without_terminology(by_language)
        # THE SECOND GAP LIST, and it is about RETRIEVAL rather than reading: a language the desk
        # can read but cannot SEARCH in its own words is a forest it will keep finding empty.
        # Native semantic search is the principal's rule -- native-script queries built from local
        # terminology per source layer, never one English phrase translated once -- so the layers
        # with no native vocabulary are published here for the source scouts, never filled in with
        # a translation that would hide the hole.
        report["native_query_languages"] = list(pg.query_languages())
        report["native_query_coverage"] = pg.query_coverage()
        report["query_layers_unmeasured"] = {
            lang: pg.layers_unmeasured(lang) for lang in sorted(by_language)
            if pg.layers_unmeasured(lang)}
        report["source_layers"] = list(pg.SOURCE_LAYERS)
        report["evidence_policy"] = {
            "keep_fringe": pg.PRESERVE_FRINGE.keep_fringe,
            "keep_contradictory": pg.PRESERVE_FRINGE.keep_contradictory,
            "keep_low_confidence": pg.PRESERVE_FRINGE.keep_low_confidence,
            "why": pg.PRESERVE_FRINGE.why}
        if report["documents"] == 0:
            report["unmeasured"]["documents"] = (
                "no document reached this pass: the coverage shares are UNMEASURED, not 0.0 -- "
                "check that data/moat/normalized_intel, the registry claims table and the two "
                "data/intelligence roots exist and hold rows")
        if not report["languages_without_terminology"]:
            report["unmeasured"]["gap_list"] = (
                "every language seen this pass has a terminology map; that is a statement about "
                "what was SEEN, never a claim that the world has no other languages")
        report["coverage"] = pg.COVERAGE
        # THE PROPOSER SEAT, OPTIONAL: candidate explanations for what is still PENDING.
        # A pending document is one this seat measured and could not understand natively, which
        # is exactly the shape a candidate name is for. The proposal is attached to the report
        # and changes no cursor, no claim, no coverage share and no task status -- the document
        # stays pending until something actually understands it. {} on a box with no panel.
        try:
            from libs.research import proposer_seat as _ps
            report["proposer_seat"] = _ps.ask(
                "understanding_seat", "names",
                records=[{"key": str(k), "claim": str(v)[:180]}
                         for k, v in list((report.get("concepts") or {}).items())[:10]]).to_row()
        except Exception as _exc:                         # pragma: no cover - optional seat
            report["proposer_seat"] = {"verdict": UNMEASURED,
                                       "why": f"{type(_exc).__name__}: {_exc}"}
        report["seconds"] = round(time.monotonic() - started, 2)
        return report
    finally:
        if close_after:
            with suppress(Exception):
                c.close()


def understanding_coverage() -> dict[str, Any]:
    """The last measured coverage, for the dashboards. UNMEASURED when no pass has run -- an
    absent artifact is a verdict (L1.28a) and never a zero."""
    doc = _read_json(REPORT)
    if not isinstance(doc, dict):
        return {"at": UNMEASURED, "documents": 0, "understood_native": 0,
                "understood_via_seat": 0, "pending": 0, "by_language": {},
                "languages_seen": [], "languages_without_terminology": [],
                "unmeasured": {"report": f"{REPORT} does not exist: the understanding seat has "
                                         "not run on this box"},
                "rule": RULE}
    total = int(doc.get("documents") or 0)
    native = int(doc.get("understood_native") or 0)
    via = int(doc.get("understood_via_seat") or 0)
    out = dict(doc)
    out["understood_share"] = None if total == 0 else round((native + via) / total, 4)
    out["native_share"] = None if total == 0 else round(native / total, 4)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--budget-s", type=float, default=240.0)
    ap.add_argument("--max-docs", type=int, default=MAX_DOCS)
    ap.add_argument("--max-tasks", type=int, default=MAX_TASKS)
    ap.add_argument("--dry-run", action="store_true",
                    help="measure and print; write no task file, no cursor, no report")
    ap.add_argument("--report", default=str(REPORT))
    a = ap.parse_args(argv)
    doc = run(budget_s=a.budget_s, dry_run=a.dry_run, max_docs=a.max_docs,
              max_tasks=a.max_tasks)
    if not a.dry_run:
        _atomic_json(Path(a.report), doc)
    printable = {k: v for k, v in doc.items()
                 if k not in ("by_language", "concepts", "native_query_coverage")}
    print(json.dumps(printable, indent=1, ensure_ascii=False, default=str))
    for lang in sorted(doc["by_language"], key=lambda k: -doc["by_language"][k]["documents"])[:25]:
        row = doc["by_language"][lang]
        flag = "" if row["has_terminology"] else "   NO TERMINOLOGY MAP"
        print(f"  {lang:10} docs={row['documents']:<7} native={row['understood_native']:<7}"
              f" seat={row['understood_via_seat']:<5} pending={row['pending']:<7}{flag}")
    if doc["languages_without_terminology"]:
        print("  GAP LIST -- no terminology map (feed these to the source scouts): "
              + ", ".join(doc["languages_without_terminology"]))
    if doc.get("query_layers_unmeasured"):
        print("  GAP LIST -- no NATIVE QUERY vocabulary, so these forests cannot be searched in "
              "their own words:")
        for lang, layers in sorted(doc["query_layers_unmeasured"].items()):
            print(f"    {lang:10} {', '.join(layers)}")
    if a.dry_run:
        print("  (dry run: nothing written)")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI
    raise SystemExit(main())
