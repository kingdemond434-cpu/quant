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


def from_candidate(c: dict[str, Any]) -> dict[str, Any]:
    """A proposer candidate has everything a card needs; write it in the card's vocabulary."""
    params = c.get("params") or {}
    return {"hypothesis": c.get("title") or c.get("mechanism"),
            "mechanism": c.get("mechanism"),
            "direction": (params.get("side_mode") or params.get("side") or "as recipe"),
            "variables": sorted(str(k) for k in params),
            "transformations": c.get("family"),
            "universe": [c.get("symbol")],
            "horizon": (params.get("hold_bars") or params.get("ttl_bars")
                        or params.get("horizon_days")),
            "parameters_allowed": dict(params.items()),
            "acceptance_criterion": "the canonical ten-gate gauntlet, deflated by the sweep's "
                                    "own trial count, then the lockbox and shadow",
            "falsifier": (c.get("evidence") or {}).get("screen") or "self-deflated screen"}


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
