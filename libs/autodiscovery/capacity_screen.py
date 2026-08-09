"""Pre-scoring capacity screen + the retirement bank (L1.17: mechanisms preserved, never deleted).

WHY THIS EXISTS (max_audit 2026-08-05). 1051 of 1799 scored candidates in the autodiscovery store
were UNFILLABLE on the live book -- the desk would BE the edge -- and the same 1051 had
growth_runway < 1 (already outgrown). Both §42 checks fired on inventory the desk cannot trade at
any size, and the audit's own prescription is the design here: "These should be screened out
before scoring, not carried as candidates" and "retire them and bank the mechanism, do not keep
ranking them."

THE BOUNDARY RULE. Before a candidate is persisted as scored, its MEASURED capacity is banded by
THE capacity policy (``libs.research.capacity_policy`` -- one definition, imported, never
inlined). UNFILLABLE at today's live book, or a growth runway below 1x, means the candidate is
appended to the retirement bank instead of the store. UNKNOWN IS NOT UNFILLABLE: capacity 0.0
means nobody measured (R0080 -- no ADV, no capacity number), and screening the unmeasured would
silently retire every candidate the day a volume feed breaks. Only a measured positive capacity
below the viability line is screened -- which is also the ONLY legitimate capacity kill under
L1.18a (sub-viable/unfillable; size is never otherwise a tiebreaker in either direction).

BOTH AUDIT CRITERIA, DELIBERATELY. ``capacity_band`` honours a declared allocation (the band a
scorer would judge the candidate by) while ``growth_runway`` is equal-weight by construction, so
the two can disagree on a declared sleeve. Screening their UNION means no candidate that either
§42 check would flag can ever be persisted as scored again.

THE BANK IS RESEARCH DEBT, NOT A GRAVE. Nothing banked is refuted -- the mechanism may be real
and simply too small for THIS book. Every record carries the full mechanism and a named
resurrection condition (L1.16a), so a shrinking book or a grown edge brings it back by a
deliberate act rather than by the population quietly re-ranking it. Records are appended, never
rewritten, never deleted.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from libs.research.capacity_policy import capacity_band, growth_runway

#: The retirement bank -- append-only JSONL, one full mechanism record per retired candidate.
BANK_PATH = Path(__file__).resolve().parents[2] / "data/capacity_retired_bank.jsonl"

#: L1.16a: resurrection is a NAMED change, never a quiet re-rank.
RESURRECT_CONDITION = ("L1.16a named change -- live book shrinks/edge capacity grows such that "
                       "required slice fits")


def screen_reason(capacity_usd: float, subtype: str, *, book_usd: float,
                  n_sleeves: int) -> str | None:
    """The bank-or-pass decision. Returns the retirement reason, or None to persist as scored.

    ``subtype`` is passed as the sleeve name so a DECLARED allocation is honoured exactly as
    ``max_audit.check_capacity_hunt`` honours it (capacity_band resolves the declaration itself)
    -- the screen and the audit must be two readers of one rule, never two rules.
    """
    cap = float(capacity_usd or 0.0)
    if cap <= 0.0:
        return None                      # unknown is not unfillable: nobody measured (R0080)
    if capacity_band(cap, book_usd, n_sleeves, sleeve=subtype) == "UNFILLABLE":
        return "unfillable-at-scoring"   # the desk would BE the edge -- L1.18a's one honest kill
    if growth_runway(cap, book_usd, n_sleeves) < 1.0:
        return "already-outgrown-at-scoring"   # fillable by declaration, outgrown at equal weight
    return None


def build_bank_record(*, candidate_id: str, family: str, subtype: str, symbol: str,
                      params: dict[str, float], content_hash: str, mechanism: str,
                      capacity_usd: float, book_usd: float, n_sleeves: int,
                      metrics: dict[str, Any], campaign_id: str, status_at_retirement: str,
                      survived: bool, rejection_reason: str | None, reason: str,
                      hypothesis_text: str | None = None,
                      failure_modes: list[str] | None = None) -> dict[str, Any]:
    """One retirement record, same shape from both writers (factory screen + one-shot retirer).

    Carries everything needed to resurrect without the store row: identity (id/content_hash),
    the full mechanism (family/subtype/symbol/params/mechanism/hypothesis text), the measurement
    it was retired on (capacity, band, runway, the book and sleeve count they were computed
    against), and the named way back.
    """
    cap = float(capacity_usd or 0.0)
    return {
        "id": candidate_id,
        "name": f"{family}/{subtype}/{symbol}",
        "family": family,
        "subtype": subtype,
        "symbol": symbol,
        "params": dict(params),
        "content_hash": content_hash,
        "mechanism": mechanism,
        "hypothesis": hypothesis_text,
        "failure_modes": list(failure_modes) if failure_modes else [],
        "capacity_usd": cap,
        "band": capacity_band(cap, book_usd, n_sleeves, sleeve=subtype),
        "runway": growth_runway(cap, book_usd, n_sleeves),
        "book_usd": float(book_usd),
        "n_sleeves": int(n_sleeves),
        "metrics": dict(metrics),
        "campaign_id": campaign_id,
        "status_at_retirement": status_at_retirement,
        "survived": bool(survived),
        "rejection_reason": rejection_reason,
        "retired_ts": datetime.now(tz=UTC).isoformat(),
        "reason": reason,
        "resurrect_condition": RESURRECT_CONDITION,
    }


def bank_append(record: dict[str, Any], *, bank: Path | None = None) -> None:
    """Append one record to the bank. RAISES on failure -- a screen that silently drops the
    record when the disk misbehaves would destroy the mechanism, which is the exact thing L1.17
    forbids; better the cycle fails loudly than the bank lies quietly."""
    path = bank if bank is not None else BANK_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, sort_keys=True) + "\n")


def banked_hashes(bank: Path | None = None) -> frozenset[str]:
    """Content hashes of everything ever banked -- the dedup rung for banked-not-stored.

    A candidate the screen banks never reaches the store, so ``CandidateStore.exists`` cannot
    dedup it; without this the factory would re-backtest and re-bank the same hypothesis every
    cycle. Missing bank means nothing banked; a malformed line is skipped rather than fatal
    (the bank is append-only history and one bad line must not blind the dedup to the rest).
    """
    path = bank if bank is not None else BANK_PATH
    try:
        lines = path.read_text("utf-8").splitlines()
    except OSError:
        return frozenset()
    out: set[str] = set()
    for ln in lines:
        try:
            h = json.loads(ln).get("content_hash")
        except (json.JSONDecodeError, AttributeError):
            continue
        if h:
            out.add(str(h))
    return frozenset(out)


def banked_ids(bank: Path | None = None) -> frozenset[str]:
    """Store ids of everything ever banked -- the idempotency rung for the one-shot retirer
    (a crash between bank-append and store-mark must not double-bank on the re-run)."""
    path = bank if bank is not None else BANK_PATH
    try:
        lines = path.read_text("utf-8").splitlines()
    except OSError:
        return frozenset()
    out: set[str] = set()
    for ln in lines:
        try:
            i = json.loads(ln).get("id")
        except (json.JSONDecodeError, AttributeError):
            continue
        if i:
            out.add(str(i))
    return frozenset(out)
