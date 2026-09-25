"""Pre-registration: the hypothesis is hashed before the result exists.

Before an experiment runs it writes what it claims and how it will be judged:

    hypothesis, mechanism, direction, variables, transformations, universe, horizon,
    parameters allowed, acceptance criterion, falsifier

and the hash of that card is the experiment's name from then on. A verdict that arrives
without the card's hash, or with a card whose hash no longer matches, is a reinterpretation
after the fact -- the exact move p-hacking needs -- and `check` reports it. No AI, and no
person, gets to decide what the hypothesis was after seeing what the data said.

APPEND-ONLY, one card per line in `data/preregistrations.jsonl`. `register` returns the hash;
proposers and the compiler carry it on the candidate as `prereg_hash`; `record_verdicts` in
the hypothesis graph carries it on the node; `check` joins the two.
"""
from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

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


def register(card: dict[str, Any], *, source: str, path: Path = LEDGER) -> str:
    missing = validate(card)
    if missing:
        raise ValueError(f"pre-registration incomplete: missing {missing}")
    h = card_hash(card)
    row = {"prereg_hash": h, "registered_utc": datetime.now(tz=UTC).isoformat(),
           "source": source, **{k: card.get(k) for k in REQUIRED},
           "transformations": card.get("transformations")}
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
        return register(card, source=source, path=path if path is not None else LEDGER), None
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
        if card_hash(reg[h]) != h:
            mismatched.append(h)
            continue
        ok += 1
    return {"ok": not unregistered and not mismatched, "registered": ok,
            "unregistered": unregistered[:20], "mismatched": mismatched[:20],
            "n_cards": len(reg)}
