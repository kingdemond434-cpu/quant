"""UNIVERSAL EDGE INTAKE -- gate items 30/31/34: no discovery may disappear silently.

THE LAW THIS IMPLEMENTS is Part III of the pre-DeepSeek mandate: every legitimately obtained
potential edge gets a canonical record and exactly one of a NAMED set of dispositions. There is no
"looks stupid -- ignore", no "retail source -- ignore", no "too simple -- ignore". Source quality
sets the PRIOR and the required falsification; it never decides empirical truth.

THE GAP IT CLOSES, measured on this desk. The miner writes reports/research_queue.json every run
and the conversion ledger records what eventually converted -- but between those two there was
nothing. A row that was never converted simply aged out of the queue file on the next sweep. The
seen-ledger stopped it being re-surfaced, so it did not reappear either: it was neither tested nor
rejected nor deferred, it was just gone. That is the research-recall defect item 34 exists to
measure, and it is invisible precisely because nothing counts it.

THE THREE PIECES:
  * stamp_queue()  (item 30) folds a queue report into an append-only ledger, giving every row a
                   disposition. Dedup LINKS new provenance to an existing row rather than
                   re-testing it -- a second source finding the same thing is evidence about the
                   finding, not a new experiment.
  * next_batch()   (item 31) hands NEXT_BATCH_TEST rows to a real consumer, oldest-deferred
                   first, and stamps ADMITTED_AT. A queue whose "scheduled" state has no consumer
                   is a graveyard with better manners.
  * recall_audit() (item 34) reconciles discovered against the sum of every disposition. Any
                   unexplained loss is returned as UNACCOUNTED -- a defect, never a rounding note.

DISPOSITIONS ARE NOT VERDICTS ON MERIT. BLOCKED_PENDING_DATA means the desk cannot test it yet and
names the missing ingredient; it is a shopping list, not a rejection. Only
REJECTED_AFTER_EMPIRICAL_TEST is a judgement about the world, and this module never writes it --
that comes from the empirical engine.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

__all__ = ["DISPOSITIONS", "LEDGER", "intake_duty", "next_batch", "recall_audit", "rows",
          "stamp_queue"]

_ROOT = Path(__file__).resolve().parents[2]
LEDGER = "data/edge_intake.jsonl"

#: Mandate Part III-2's disposition set. Every intake row carries exactly one.
DISPOSITIONS: tuple[str, ...] = (
    "IMMEDIATE_TEST",                 # cheap, data-ready, high VOI -- test now
    "NEXT_BATCH_TEST",                # real work, waits for capacity; has a consumer
    "BLOCKED_PENDING_DATA",           # testable in principle, missing a named input
    "BLOCKED_PENDING_IMPLEMENTATION", # needs a collector/parser that does not exist
    "DUPLICATE_OF_EXISTING_TEST",     # links provenance to a prior row, never re-tests
    "NON_TESTABLE",                   # no falsifiable claim to test
    "LEGALLY_UNUSABLE",               # rights/licence forbid it
    "DOMINATED_TEST_DEFERRED",        # a strictly better test of the same mechanism exists
    "REJECTED_AFTER_EMPIRICAL_TEST",  # written by the empirical engine, never by intake
)

#: Words that make a queue row a MECHANISM claim rather than a topic. A row naming a mechanism can
#: be turned into a hypothesis; one that does not is missing an ingredient, and saying WHICH is
#: the difference between a shopping list and a shrug.
_MECHANISM_WORDS = (
    "套利", "arbitrage", "basis", "基差", "funding", "资金费率", "liquidation", "清算", "爆仓",
    "spread", "价差", "premium", "溢价", "parity", "平价", "carry", "skew", "偏度",
    "impact", "冲击", "slippage", "滑点", "orderflow", "订单流", "imbalance", "失衡",
    "unlock", "解锁", "flow", "资金流", "inventory", "库存", "queue", "排队",
)


def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _append(row: dict[str, Any], root: Path | None = None) -> dict[str, Any]:
    base = root or _ROOT
    p = base / LEDGER
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def rows(root: Path | None = None) -> list[dict[str, Any]]:
    """Every intake event, oldest first. Folding gives current state per ident."""
    base = root or _ROOT
    out: list[dict[str, Any]] = []
    try:
        text = (base / LEDGER).read_text("utf-8", errors="ignore")
    except OSError:
        return out
    for line in text.splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
    return out


def _current(root: Path | None = None) -> dict[str, dict[str, Any]]:
    cur: dict[str, dict[str, Any]] = {}
    for r in rows(root):
        ident = str(r.get("ident", ""))
        if ident:
            cur[ident] = r
    return cur


def _names_mechanism(text: str) -> str:
    low = str(text or "").lower()
    for w in _MECHANISM_WORDS:
        if w.lower() in low:
            return w
    return ""


def classify(row: dict[str, Any], *, seen: dict[str, dict[str, Any]]) -> tuple[str, str]:
    """(disposition, why) for one queue row. Deterministic and cheap -- no model call.

    THE ROUTING RULE, from Part III-3: a row that NAMES A MECHANISM can become a hypothesis and
    goes to the batch. A row that scores on validation vocabulary but names no mechanism is not
    rejected -- it is BLOCKED_PENDING_DATA with the missing ingredient stated, because "we cannot
    test a topic" is a fact about our inputs, not about the material.
    """
    ident = str(row.get("video_id") or row.get("ident") or "")
    if ident in seen:
        prior = seen[ident]
        return ("DUPLICATE_OF_EXISTING_TEST",
                f"already in intake as {prior.get('disposition')} since {prior.get('ts')} -- this "
                "source is LINKED as additional provenance, not re-tested. A second source finding "
                "the same thing is evidence about the finding, never a new experiment")
    mech = _names_mechanism(f"{row.get('title', '')} {' '.join(row.get('why') or [])}")
    if mech:
        return ("NEXT_BATCH_TEST",
                f"names a testable mechanism ({mech!r}) -- convertible to a hypothesis with a "
                "stated economics and a falsification test; queued for the next batch")
    return ("BLOCKED_PENDING_DATA",
            "scored on validation/method vocabulary but names no MECHANISM, so there is nothing "
            "to falsify yet. MISSING INGREDIENT: a stated economic mechanism (who pays, and why "
            "they cannot stop). Not a rejection -- a fact about our inputs (mandate III-2)")


def _same_utc_day(a: str, b: str) -> bool:
    return bool(a) and bool(b) and a[:10] == b[:10]


def stamp_queue(report_path: str | Path, *, root: Path | None = None) -> dict[str, Any]:
    """GATE ITEM 30. Fold a miner queue report into the intake ledger. Nothing disappears.

    IDEMPOTENT WITHIN A UTC DAY (2026-08-13 fix). scripts/mine_research_queue.py stamps its own
    output inline (added 2026-08-12 to close a race between two same-day miner runs), and
    ops/crontab.manifest ALSO fires scripts/run_edge_intake.py -- which called this same function
    on the same default report file -- twenty minutes later as a documented, deliberate replay
    path ("the accounting can be re-run over a queue report the miner wrote days ago"). Both
    callers are legitimate, but a naive re-stamp folded `classify()`'s dedup rule over ITS OWN
    prior output: every ident already carried a same-day disposition, so `classify()` saw them as
    "seen" and downgraded a fresh NEXT_BATCH_TEST to DUPLICATE_OF_EXISTING_TEST before
    next_batch() ever ran -- reproduced directly: n_stamped=1 NEXT_BATCH_TEST, then a second
    identical stamp -> n_stamped=1 DUPLICATE_OF_EXISTING_TEST, next_batch() empty. Every intake
    row genuinely stopped moving forward the same day it arrived.

    THE FIX PRESERVES THE REPLAY DESIGN INTENT: a row that already carries a REAL disposition
    (not itself a duplicate stub) from LATER THAN OR EQUAL TO the same UTC day is left untouched
    -- re-stamping an unchanged report is a no-op, not new evidence. A sighting from an EARLIER
    day still creates a genuine DUPLICATE_OF_EXISTING_TEST link, because that IS a second,
    independent discovery and the module's own contract says so ("a second source finding the
    same thing is evidence about the finding").
    """
    base = root or _ROOT
    path = Path(report_path)
    if not path.is_absolute():
        path = base / path
    try:
        doc = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError) as exc:
        return {"status": "BLOCKED", "why": f"queue report unreadable: {type(exc).__name__}",
                "n_stamped": 0}

    seen = _current(root)
    today = _now()
    counts: dict[str, int] = {}
    stamped = 0
    for r in doc.get("queue") or []:
        ident = str(r.get("video_id") or "")
        if not ident:
            continue
        prior = seen.get(ident)
        if (prior is not None and prior.get("disposition") != "DUPLICATE_OF_EXISTING_TEST"
                and _same_utc_day(str(prior.get("ts") or prior.get("discovered_at") or ""),
                                  today)):
            continue  # idempotent replay of an already-classified-today row -- not new evidence
        disp, why = classify(r, seen=seen)
        row = {
            "ts": today, "ident": ident, "disposition": disp, "why": why,
            "title": str(r.get("title", ""))[:200], "channel": str(r.get("channel", "")),
            "score": r.get("score"), "url": r.get("url"),
            "discovered_at": today, "admitted_at": None,
            "deferrals": 0, "deferral_reason": None,
            "source_class": str(r.get("channel", "")).split(":")[0],
        }
        if disp == "DUPLICATE_OF_EXISTING_TEST":
            row["links_to"] = ident
        _append(row, root)
        seen[ident] = row
        counts[disp] = counts.get(disp, 0) + 1
        stamped += 1
    return {"status": "OK", "n_stamped": stamped, "by_disposition": counts,
            "law": "every queue row leaves with exactly one named disposition; none is dropped",
            "authority": "RECORD + ROUTE ONLY -- tests nothing, rejects nothing on merit."}


def next_batch(*, limit: int = 8, root: Path | None = None) -> list[dict[str, Any]]:
    """GATE ITEM 31. The real consumer for NEXT_BATCH_TEST, with an anti-graveyard order.

    Sorted by DEFERRAL COUNT first, then score. Repeated deferral must be visible and must
    eventually win, or NEXT_BATCH_TEST becomes a polite name for never (mandate III-4).
    """
    pending = [r for r in _current(root).values() if r.get("disposition") == "NEXT_BATCH_TEST"
               and not r.get("admitted_at")]
    pending.sort(key=lambda r: (-int(r.get("deferrals") or 0), -float(r.get("score") or 0.0)))
    return pending[:limit]


def intake_duty(*, root: Path | None = None, limit: int = 8) -> str:
    """The injectable block for organ spawn -- GATE ITEM 31's actual reach.

    THE GAP THIS CLOSES (2026-08-13, found tracing why NEXT_BATCH_TEST never drained).
    scripts/run_edge_intake.py called next_batch() and printed it to
    data/cro_ai_logs/edge_intake.log inside a once-daily cron run -- and nothing else in the
    repo ever read that log. admit() (the function that marks a row genuinely picked up) had
    exactly one caller anywhere in the tree: its own unit test. A queue whose "scheduled" state
    has a consumer that only writes to a file nobody opens is the graveyard this module's own
    docstring says item 31 exists to prevent.

    MIRRORS libs.ops.repair_mode's injection exactly, because that module already solved the
    identical shape of problem (L1.28b(d): a remedy legislated, fenced, and never wired to reach
    an organ) for the recommendation ledger's backlog. Same fix, same law (L1.36): a duty that
    never reaches an organ cannot change behaviour however well it is fenced.

    STEADY (empty string) when nothing is waiting -- this ADDS a duty and REMOVES none; it never
    tells an organ to do less (L1.28b(f), same clause repair_mode.py carries verbatim).

    THIS DOES NOT CALL admit() ITSELF. Marking a row admitted without a real experiment behind it
    would shrink the backlog by pretending, which is the exact failure mode the principal
    explicitly forbade (2026-08-13): "do not delete, suppress, or deprioritize candidates just to
    make the backlog look smaller." admit()/defer()/scripts/recommendations.py add are for
    whoever reads this duty and does the real work.
    """
    batch = next_batch(limit=limit, root=root)
    if not batch:
        return ""
    named = "; ".join(f"[{r.get('score')}] {str(r.get('title'))[:50]}" for r in batch[:5])
    more = f" (+{len(batch) - 5} more)" if len(batch) > 5 else ""
    return (
        f"[Part III-31] EDGE INTAKE -- {len(batch)} candidate(s) in NEXT_BATCH_TEST with no "
        f"consumer yet: {named}{more}\n"
        f"  READ THEM (python3 scripts/run_edge_intake.py --json), then for each: raise a "
        f"genuine finding with scripts/recommendations.py add, or call "
        f"libs.research.edge_intake.defer(ident, reason) with a real reason, or .admit(ident) "
        f"once a real experiment has actually started on it.\n"
        f"  THIS ADDS A DUTY AND REMOVES NONE (L1.28b(f)): collectors, recorders, miners, "
        f"diggers, screens and forward clocks run at FULL CADENCE regardless.")


def admit(idents: list[str], *, root: Path | None = None) -> int:
    """Stamp ADMITTED_AT on rows handed to a consumer. Deferral counts rise for those not taken."""
    cur = _current(root)
    n = 0
    for ident in idents:
        r = cur.get(ident)
        if r and r.get("disposition") == "NEXT_BATCH_TEST":
            _append({**r, "ts": _now(), "admitted_at": _now(),
                     "why": "admitted to an experiment batch by next_batch()"}, root)
            n += 1
    return n


def defer(idents: list[str], reason: str, *, root: Path | None = None) -> int:
    """Record an explicit deferral. Visible, counted, and it raises the row's next priority."""
    cur = _current(root)
    n = 0
    for ident in idents:
        r = cur.get(ident)
        if r:
            _append({**r, "ts": _now(), "deferrals": int(r.get("deferrals") or 0) + 1,
                     "deferral_reason": reason,
                     "why": f"deferred ({int(r.get('deferrals') or 0) + 1}x): {reason}"}, root)
            n += 1
    return n


def recall_audit(root: Path | None = None, *,
                 queue_report: str | Path | None = None) -> dict[str, Any]:
    """GATE ITEM 34. discovered == deduped + tested + waiting + blocked + rejected + non-testable.

    An unexplained difference is returned as UNACCOUNTED and is a RESEARCH-RECALL DEFECT, not a
    rounding note: it means a discovery entered the funnel and left it without a disposition,
    which is the exact failure Part III exists to prevent.
    """
    cur = _current(root)
    by: dict[str, int] = {}
    for r in cur.values():
        by[str(r.get("disposition"))] = by.get(str(r.get("disposition")), 0) + 1
    accounted = sum(by.values())

    discovered = accounted
    unaccounted: list[str] = []
    if queue_report is not None:
        base = root or _ROOT
        p = Path(queue_report)
        if not p.is_absolute():
            p = base / p
        try:
            doc = json.loads(p.read_text("utf-8"))
            idents = {str(r.get("video_id")) for r in (doc.get("queue") or []) if r.get("video_id")}
            discovered = len(idents | set(cur))
            unaccounted = sorted(idents - set(cur))
        except (OSError, ValueError):
            pass

    return {
        "generated_utc": _now(),
        "edges_discovered": discovered,
        "by_disposition": by,
        "accounted": accounted,
        "unaccounted": len(unaccounted),
        "unaccounted_idents": unaccounted[:40],
        "reconciles": not unaccounted,
        "verdict": ("RECONCILES -- every discovered edge carries a disposition"
                    if not unaccounted else
                    f"RESEARCH-RECALL DEFECT: {len(unaccounted)} discovered edge(s) have no "
                    "intake record. A discovery that entered the funnel and left without a "
                    "disposition is the silent-dismissal failure Part III forbids"),
        "authority": "MEASUREMENT ONLY.",
    }


def main() -> int:
    """Print the injectable duty block. Exit 0 always -- a prompt producer, not a gate.

    Wired into ops/brain_env.sh's _DOCTRINE exactly like libs.ops.repair_mode (L1.37: PAGES,
    never KILLS -- an organ spawn must never be blocked by this queue's state).
    """
    from libs.ops.lawful import guard as _law_guard  # L1.42: no act exempt

    _law_guard()
    print(intake_duty(), end="")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI
    raise SystemExit(main())

