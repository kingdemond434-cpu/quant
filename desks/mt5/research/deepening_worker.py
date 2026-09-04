"""Work the deepening queue: recover a falsifiable rule from the source, or reject it.

    python desks/mt5/research/deepening_worker.py [--limit N] [--dry-run]

THE QUEUE HAD NO READER. `miner_candidate_compiler` writes
`data/hypotheses/miner_deepening_queue.json` and declares its consumer in the artifact itself --
"hourly/daily research brains must recover a falsifiable rule or reject" -- and a grep for that
filename across every module on this desk returns exactly one hit: the line in the compiler that
DEFINES the write path. Measured 2026-09-03: 705 tasks, every one at status None, from 35 of the
39 miner sources. Of 1,151 evidence rows compiled that hour, 370 became executable candidates and
705 went here to be read by nobody.

That is the whole yield of the world crawler (50 rows, 0 candidates, 50 deepened), amarkets,
reddit, fxblue, bis_speeches, quant_se, github, forextsd_cdx and trading_latam. The desk pays to
crawl the world hourly and then drops most of what it finds into a write-only file.

WHAT THIS DOES NOT DO, and the distinction is the whole point. It does not invent a rule. The
compiler's first line is "without inventing rules" and this reader is held to it harder, because
an LLM will happily supply a plausible strategy for any title you show it. So:

  * the model is given ONLY the row's own text (title, url, tags) and asked what that text
    STATES -- not what would be a good strategy for it;
  * every extraction must carry `evidence`, a verbatim span from the text it was given. No
    evidence, no candidate. A quote that is not actually in the input is a fabrication and is
    rejected as one, checked here rather than trusted;
  * an extracted symbol must be in the desk's own universe, and an extracted family must be
    registered. The model cannot widen either set by naming something;
  * anything ambiguous is REJECTED with its reason recorded. A rejection is a result: it stops
    the row being re-billed every hour forever.

ENRICH AND RE-COMPILE, NEVER EMIT DIRECTLY. A recovered symbol or recipe is written back onto a
copy of the ORIGINAL row and passed through `compile_row`, the same function every miner row
goes through. This reader therefore adds no new admission path to the candidate store -- it can
only cause the existing door to open, never bypass it, and every guard the compiler already
applies still applies. The gauntlet remains the arbiter of profitability.

COSTS ARE BOUNDED BY CONSTRUCTION. `libs.ops.llm_seat` carries the monthly cap and the spend
ledger; this adds a per-run task limit on top, and an append-only worked-ledger so a task is
paid for ONCE. Re-running the hour is free for everything already decided.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
sys.path.insert(0, str(BASE / "research"))
sys.path.insert(0, str(ROOT))

from miner_candidate_compiler import (  # noqa: E402
    DEEPEN,
    compile_row,
    known_symbols,
)

#: Append-only: one line per task ever decided, so a decision is paid for once. Deliberately not
#: a set inside the output file -- that file is rewritten each run and a crash mid-write would
#: lose the record of work already billed.
WORKED = BASE / "data" / "hypotheses" / "deepening_worked.jsonl"
#: Candidates recovered here, in the compiler's own contract, for the same consumers.
OUT = BASE / "data" / "hypotheses" / "deepened_candidates.json"
LOG = BASE / "logs" / "deepening_worker.log"

#: A run's ceiling. The queue is 705 deep and grows hourly; working it all in one pass would
#: spend the month's cap in an afternoon on the least-certain rows the desk holds.
DEFAULT_LIMIT = 25

_SYSTEM = (
    "You read one row of trading research evidence and report only what its text STATES. "
    "You never propose a strategy, never fill a gap with something plausible, and never name a "
    "symbol or rule the text does not contain. Reporting that the text is insufficient is a "
    "correct and useful answer; inventing a rule is the one unacceptable one."
)

_CONTRACT = """Return ONE JSON object, no prose around it:

{
  "symbols":  ["EURUSD"],          // instruments the TEXT names; [] if it names none
  "family":   "session_range_breakout" | null,   // only if the text states an exact mechanism
  "params":   {"lookback": 20} | null,           // only parameters the text actually gives
  "evidence": "verbatim span copied from the text above that supports the above",
  "why_not":  "why nothing could be extracted, if symbols is [] and family is null"
}

Rules you must follow:
- `evidence` MUST be copied character-for-character from the text you were given. If you cannot
  quote it, you have nothing to report: return empty symbols, null family, and say why in
  `why_not`.
- A generic mention of "forex", "trading" or "MT5" is NOT a symbol. Only concrete instruments.
- Do not infer a family from a tag. "scalping" is a style, not an exact mechanism.
- Prefer returning nothing over returning something you had to reason your way to."""


def dlog(msg: str) -> None:
    line = f"{datetime.now(tz=UTC).isoformat(timespec='seconds')} {msg}"
    print(line)
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        pass


def task_id(task: dict) -> str:
    """Stable across runs and across queue rebuilds: the row's own identity, not its position."""
    key = f"{task.get('source')}|{task.get('url')}|{task.get('title')}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


def worked_ids() -> set[str]:
    if not WORKED.exists():
        return set()
    out: set[str] = set()
    for line in WORKED.read_text("utf-8").splitlines():
        if not line.strip():
            continue
        try:
            out.add(str(json.loads(line)["id"]))
        except (ValueError, KeyError):
            continue
    return out


def record(entry: dict) -> None:
    WORKED.parent.mkdir(parents=True, exist_ok=True)
    with WORKED.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, separators=(",", ":"), default=str) + "\n")


def task_text(task: dict) -> str:
    """Everything the model is allowed to see. No fetching: the row is the evidence."""
    tags = ", ".join(str(t) for t in (task.get("mechanism_tags") or []))
    return "\n".join([
        f"TITLE: {task.get('title') or ''}",
        f"URL: {task.get('url') or ''}",
        f"TAGS: {tags}",
        f"SOURCE: {task.get('source') or ''}",
        f"SYMBOLS ALREADY RESOLVED: {task.get('symbols') or []}",
    ])


def _parse(text: str) -> dict | None:
    """The object, or None. A model that wraps JSON in prose is common; a broken one is not fatal."""
    text = (text or "").strip()
    if text.startswith("```"):
        text = text.split("```")[1] if "```" in text[3:] else text.strip("`")
        text = text[4:] if text.lower().startswith("json") else text
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        v = json.loads(text[start:end + 1])
    except ValueError:
        return None
    return v if isinstance(v, dict) else None


def validate(found: dict, source_text: str, universe: set[str]) -> tuple[dict, str]:
    """The extraction, cleaned -- or ({}, reason) when it may not be trusted.

    EVERY REJECTION HERE IS A FABRICATION CAUGHT. The quote check is the one that matters: a
    model that cannot ground its answer in the text will still return a confident answer, and
    without this it would enter the candidate store wearing the miner's provenance.
    """
    evidence = str(found.get("evidence") or "").strip()
    symbols = [str(s).upper().strip() for s in (found.get("symbols") or []) if str(s).strip()]
    family = found.get("family")
    family = str(family).strip() if isinstance(family, str) and family.strip() else None
    params = found.get("params") if isinstance(found.get("params"), dict) else None

    if not symbols and not family:
        return {}, f"nothing extractable: {found.get('why_not') or 'no reason given'}"
    if not evidence:
        return {}, "extraction carried no evidence span"
    # Normalised containment: models re-wrap whitespace even when quoting faithfully.
    hay = " ".join(source_text.split()).lower()
    needle = " ".join(evidence.split()).lower()
    if needle not in hay:
        return {}, f"evidence span is not in the source text (fabricated quote): {evidence[:80]!r}"

    unknown = [s for s in symbols if s not in universe]
    if unknown:
        return {}, f"symbols outside the desk universe: {unknown}"
    if params is not None and any(isinstance(v, (dict, list)) for v in params.values()):
        return {}, "params must be flat scalars"
    return {"symbols": symbols, "family": family, "params": params, "evidence": evidence}, ""


def extract(task: dict, *, chat=None) -> tuple[dict, str]:
    """Ask the seat what the row's own text states. ({}, reason) on any doubt."""
    if chat is None:
        from libs.ops import llm_seat
        chat = llm_seat.chat
    text = task_text(task)
    reply, err = chat(f"{text}\n\n{_CONTRACT}", system=_SYSTEM, max_tokens=700, temperature=0.0)
    if err:
        return {}, f"seat error: {err}"
    found = _parse(reply)
    if found is None:
        return {}, "reply was not a JSON object"
    return validate(found, text, known_symbols())


def work_task(task: dict, universe: set[str], *, chat=None) -> tuple[list[dict], str]:
    """Candidates recovered from this task, and the disposition recorded for it.

    The recovered fields are written onto a COPY of the original row and re-compiled by
    `compile_row`. Nothing here writes a candidate itself, so no guard in the compiler can be
    skipped by coming through this door.
    """
    found, why = extract(task, chat=chat)
    if not found:
        return [], f"REJECTED: {why}"

    enriched = dict(task)
    if found["symbols"]:
        enriched["symbols"] = found["symbols"]
    if found["family"]:
        enriched["family"] = found["family"]
        enriched["params"] = found["params"] or {}
    enriched["mechanism"] = f"deepened from source text: {found['evidence'][:160]}"

    candidates, disposition = compile_row(str(task.get("source") or "unknown"),
                                          enriched, universe)
    if not candidates:
        # The compiler still refused it. That is the compiler's call, not this reader's.
        return [], f"STILL_{disposition}"
    for c in candidates:
        c["deepened"] = True
        c["evidence"] = found["evidence"][:400]
    return candidates, f"RECOVERED_{disposition}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    ap.add_argument("--dry-run", action="store_true",
                    help="report what would be worked; call no seat and write nothing")
    args = ap.parse_args()

    queue = json.loads(DEEPEN.read_text("utf-8")) if DEEPEN.exists() else {}
    tasks = [t for t in (queue.get("tasks") or []) if isinstance(t, dict)]
    if not tasks:
        dlog("queue empty or unreadable -- nothing to work")
        return 0

    done = worked_ids()
    pending = [t for t in tasks if task_id(t) not in done]
    dlog(f"queue={len(tasks)} already-decided={len(done)} pending={len(pending)} "
         f"limit={args.limit}")
    if args.dry_run:
        for t in pending[:args.limit]:
            dlog(f"  would work {task_id(t)} [{t.get('source')}] {str(t.get('title'))[:70]}")
        return 0
    if not pending:
        dlog("every queued task already has a decision -- no spend this run")
        return 0

    universe = known_symbols()
    recovered: list[dict] = []
    counts: dict[str, int] = {}
    for task in pending[:args.limit]:
        tid = task_id(task)
        try:
            candidates, disposition = work_task(task, universe)
        except Exception as exc:                                  # noqa: BLE001
            # One bad row must not end the run: the rest of the batch is still worth working,
            # and the failure is recorded so it is not silently retried forever.
            candidates, disposition = [], f"ERROR: {type(exc).__name__}: {exc}"
        head = disposition.split(":")[0]
        counts[head] = counts.get(head, 0) + 1
        recovered.extend(candidates)
        record({"id": tid, "at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
                "source": task.get("source"), "url": task.get("url"),
                "disposition": disposition, "n_candidates": len(candidates)})
        dlog(f"  {tid} [{task.get('source')}] {disposition} -> {len(candidates)} candidate(s)")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    prior = []
    if OUT.exists():
        try:
            prior = (json.loads(OUT.read_text("utf-8")) or {}).get("candidates") or []
        except ValueError:
            prior = []
    OUT.write_text(json.dumps({
        "built_at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "candidates": prior + recovered,
        "recovered_this_run": len(recovered),
        "dispositions": counts,
    }, indent=1), encoding="utf-8")
    dlog(f"worked {sum(counts.values())} task(s): {counts}; "
         f"{len(recovered)} new candidate(s) -> {OUT.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
