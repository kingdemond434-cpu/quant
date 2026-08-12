"""ZERO NOVELTY = ZERO CLAUDE — principal directive 2026-08-12, §11/§12/§13/§16/§17.

THE CENTRAL TOKEN-SAVING ARCHITECTURE, and the one idea the whole directive rests on:

    LOCAL FETCH -> LOCAL PARSE -> LOCAL DEDUP -> NOVELTY DETECTION -> ACCUMULATE
    -> TRIGGER THRESHOLD -> OPUS/FABLE ANALYSIS

COLLECTION FREQUENCY IS NOT REASONING FREQUENCY. Fetching is cheap: HTTP, a parser and a hash.
Reasoning is the expensive half, and until now every collection fired a Claude session whether
or not the collection found anything. Today's measurement makes the cost concrete -- a Chinese
sweep two hours after the previous one returned 36 new rows out of 658 fetched while Bilibili
returned zero and spent a soft refusal doing it, and BOTH triggered a full session.

WHAT THIS MODULE REFUSES:

  * A MODEL CALL WITH NOTHING NEW TO SAY. `decide()` returns SUPPRESS and a machine-readable
    status. The desk does not pay premium tokens for an essay explaining that nothing happened.
  * A CALL PER ITEM. Evidence accumulates in a buffer and fires ONE batched call when the
    threshold or the staleness floor is reached (§13).
  * RE-REASONING OVER KNOWN ITEMS. Content hashes are checked against everything already
    analysed, so an article three miners all find is reasoned about once (§17).
  * RE-SENDING UNCHANGED CONTEXT. `delta_context()` returns only what changed since the last
    successful cycle (§18).

THE ONE THING IT MUST NEVER DO is drop evidence. Suppressing a MODEL CALL is not discarding a
FINDING: novel rows still land in the buffer and still reach canonical intake. The optimisation
is WAIT / BATCH / DEDUP / COMPRESS, never IGNORE (§33). A staleness floor guarantees that a
slowly-accumulating buffer still gets read eventually rather than waiting forever for a
threshold it will never reach -- which is how a batching rule quietly becomes a memory hole.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

__all__ = [
    "STATUSES",
    "Decision",
    "buffer_add",
    "decide",
    "delta_context",
    "fingerprint",
    "mark_analysed",
]

_ROOT = Path(__file__).resolve().parents[2]
BUFFER = "data/novelty_buffer.jsonl"
SEEN = "data/novelty_analysed.json"

#: §12/§23. Cheap machine-readable outcomes. None of these costs a premium token.
STATUSES: tuple[str, ...] = (
    "NEW_EVIDENCE", "NO_NEW_DATA", "SATURATED", "SOFT_REFUSAL", "RATE_LIMIT",
    "SOURCE_UNAVAILABLE", "PARSER_FAILURE", "SIGNATURE_GATE", "AUTH_GATE", "ANTI_BOT",
    "NETWORK_FAILURE", "UNMEASURED",
)

#: Fire a batched analysis at this many novel items...
DEFAULT_BATCH = 20
#: ...or when the oldest buffered item reaches this age, whichever comes first. The floor is what
#: stops a slow source's evidence waiting forever for a batch that never fills.
MAX_BUFFER_AGE_H = 26.0


@dataclass(frozen=True)
class Decision:
    invoke: bool
    status: str
    n_novel: int
    why: str
    batch: list[dict[str, Any]] | None = None


def fingerprint(item: dict[str, Any]) -> str:
    """Content identity for cross-miner dedup (§17).

    Keyed on the IDENT plus normalised title, not on the URL: the same article reached through
    three mirrors has three URLs and one identity, and the desk should reason about it once.
    """
    ident = str(item.get("video_id") or item.get("ident") or item.get("url") or "")
    title = " ".join(str(item.get("title", "")).lower().split())
    return hashlib.sha256(f"{ident}|{title}".encode()).hexdigest()[:20]


def _load_seen(root: Path | None = None) -> set[str]:
    try:
        raw = json.loads(((root or _ROOT) / SEEN).read_text("utf-8"))
    except (OSError, ValueError):
        return set()
    return set(raw.get("analysed") or []) if isinstance(raw, dict) else set()


def mark_analysed(fps: list[str], *, root: Path | None = None) -> int:
    """Record that these items have been REASONED ABOUT, so no later run pays for them again."""
    base = root or _ROOT
    seen = _load_seen(base) | {str(f) for f in fps}
    p = base / SEEN
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(json.dumps({"analysed": sorted(seen)}), "utf-8")
    tmp.replace(p)
    return len(seen)


def buffer_add(miner: str, items: list[dict[str, Any]], *,
               root: Path | None = None) -> dict[str, Any]:
    """Accumulate NOVEL evidence only. Already-analysed items are dropped from the BUFFER, not
    from the desk -- they are already in canonical intake, which is where evidence lives."""
    base = root or _ROOT
    seen = _load_seen(base)
    fresh, dupes = [], 0
    for it in items:
        fp = fingerprint(it)
        if fp in seen:
            dupes += 1
            continue
        fresh.append({**it, "_fp": fp, "_miner": miner,
                      "_buffered_utc": datetime.now(tz=UTC).isoformat(timespec="seconds")})
    if fresh:
        p = base / BUFFER
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as fh:
            for row in fresh:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return {"miner": miner, "buffered": len(fresh), "duplicates_filtered": dupes,
            "why": "duplicates are filtered from the REASONING buffer, never from canonical "
                   "intake -- the desk already holds them (§17)"}


def _buffer_rows(root: Path | None = None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        text = ((root or _ROOT) / BUFFER).read_text("utf-8", errors="ignore")
    except OSError:
        return out
    for line in text.splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
    return out


def _oldest_age_h(rows: list[dict[str, Any]]) -> float:
    now = datetime.now(tz=UTC)
    oldest = 0.0
    for r in rows:
        try:
            ts = datetime.fromisoformat(str(r.get("_buffered_utc", "")))
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=UTC)
            oldest = max(oldest, (now - ts).total_seconds() / 3600.0)
        except ValueError:
            # L1.41: an unparseable stamp is UNKNOWN age, and unknown must not read as fresh --
            # that would let a row sit in the buffer forever.
            return float("inf")
    return oldest


def decide(*, miner: str, source_status: str = "NEW_EVIDENCE",
           batch_size: int = DEFAULT_BATCH, max_age_h: float = MAX_BUFFER_AGE_H,
           root: Path | None = None) -> Decision:
    """§12. Should this cycle spend a premium model call at all?

    A refusal, a rate limit or a saturated sweep returns its status and SUPPRESSES -- §23 is
    explicit that an unchanged refusal does not deserve repeated Claude analysis. Nothing about
    a 429 becomes clearer by asking a model to describe it.
    """
    st = str(source_status or "UNMEASURED").upper()
    rows = _buffer_rows(root)
    n = len(rows)

    if st != "NEW_EVIDENCE":
        return Decision(False, st, n,
                        f"source status {st} -- persisted as a cheap machine-readable fact. An "
                        "unchanged refusal does not deserve premium reasoning, and nothing about "
                        "a rate limit becomes clearer by paying a model to describe it (§23)")
    if n == 0:
        return Decision(False, "NO_NEW_DATA", 0,
                        "nothing novel buffered. No essay is written explaining that nothing "
                        "happened (§12)")

    age = _oldest_age_h(rows)
    if n >= int(batch_size):
        return Decision(True, "NEW_EVIDENCE", n,
                        f"{n} novel item(s) >= batch {batch_size} -- one strong batched call "
                        "rather than {n} small ones (§13)", rows)
    if age >= float(max_age_h):
        return Decision(True, "NEW_EVIDENCE", n,
                        f"{n} novel item(s) below batch {batch_size}, but the oldest has waited "
                        f"{age:.1f}h (floor {max_age_h:.0f}h). The staleness floor is what stops "
                        "batching becoming a memory hole for slow sources (§33)", rows)
    return Decision(False, "NEW_EVIDENCE", n,
                    f"{n} novel item(s) accumulating, oldest {age:.1f}h. HELD, not dropped -- "
                    f"fires at {batch_size} items or {max_age_h:.0f}h, whichever comes first")


def drain(root: Path | None = None) -> int:
    """Clear the buffer after a successful batched analysis. Items stay in canonical intake."""
    p = (root or _ROOT) / BUFFER
    try:
        n = len(_buffer_rows(root))
        p.unlink()
        return n
    except OSError:
        return 0


def delta_context(*, current: dict[str, Any], previous: dict[str, Any]) -> dict[str, Any]:
    """§18. What CHANGED since the last successful cycle -- not the whole history again.

    Recurring cycles were re-sending entire miner outputs, unchanged policy text and full source
    history every run, paying input tokens to tell the model things it was told yesterday. This
    returns added/changed/removed keys only, and reports the reduction so the saving is measured
    rather than assumed.
    """
    cur, prev = dict(current or {}), dict(previous or {})
    added = {k: v for k, v in cur.items() if k not in prev}
    changed = {k: v for k, v in cur.items() if k in prev and prev[k] != v}
    removed = sorted(k for k in prev if k not in cur)
    delta = {**added, **changed}
    full_len = len(json.dumps(cur, default=str, ensure_ascii=False))
    delta_len = len(json.dumps(delta, default=str, ensure_ascii=False))
    return {
        "delta": delta,
        "added_keys": sorted(added),
        "changed_keys": sorted(changed),
        "removed_keys": removed,
        "full_chars": full_len,
        "delta_chars": delta_len,
        "reduction": round(1.0 - (delta_len / full_len), 4) if full_len else 0.0,
        "law": "send new evidence, changed evidence and unresolved state -- not the entire "
               "history, unchanged policy or repository state (§18)",
    }
