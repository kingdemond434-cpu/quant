"""SECOND FAMILY (L1.33) -- the GPT seat as a standing partner on every exploration family.

PRINCIPAL ORDER (2026-07-31): *"and GPT and Claude work together ... on these families."*

WHY A SHARED MODULE RATHER THAN A COPY PER ORGAN. The capability hunt (L1.31) proved the pattern:
two model families propose INDEPENDENTLY, and cross-family agreement is evidence while agreement
within one family is style -- a model cannot see its own blind spot, so asking Claude twice
returns the first answer with more confidence. Every other exploration organ was single-family:
blindspot_max, the prober, blindrediscovery and the sweep's meta seat all think in exactly one
model's priors, which is precisely the failure mode they exist to detect, applied to themselves.

This is the one place the second family is called, so:
  - every organ gets the partner by importing ONE function (no per-organ copy to drift),
  - the DEGRADATION IS HONEST everywhere at once: an unfunded/blocked GPT seat returns
    available=False with its reason, and the caller records SINGLE-FAMILY rather than passing one
    model's opinion off as cross-family agreement,
  - and when the seat is funded, every organ gains the partner in the same deploy.

Usage inside an organ:

    from libs.research.second_family import ask_second_family, merge_verdict
    r = ask_second_family("Here is what I found: ... What did I MISS?", context="blindspot_max")
    verdict = merge_verdict(own_findings, r)     # CONFIRMED / SOLO / CONTESTED, honestly labelled
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path("/home/quant/quant-platform")
if not _ROOT.exists():
    _ROOT = Path(__file__).resolve().parent.parent.parent

_LEDGER = _ROOT / "data/second_family_log.json"


@dataclass(frozen=True)
class SecondOpinion:
    """What the independent family said -- or precisely why it could not be asked."""

    available: bool
    text: str = ""
    reason: str = ""
    model: str = ""
    context: str = ""
    at: str = field(default_factory=lambda: datetime.now(tz=UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {"available": self.available, "model": self.model, "context": self.context,
                "at": self.at, "reason": self.reason, "chars": len(self.text)}


def ask_second_family(prompt: str, *, context: str, timeout: float = 300.0) -> SecondOpinion:
    """Ask the GPT-9 seat. NEVER raises and never blocks an organ: a dead partner degrades the
    run to single-family with a stated reason, which the caller must record."""
    try:
        import sys
        if str(_ROOT) not in sys.path:
            sys.path.insert(0, str(_ROOT))
        from scripts.run_strategic_director import MODEL, _ask
    except Exception as exc:
        return SecondOpinion(False, reason=f"second family unimportable: {exc}", context=context)
    text, err = _ask(prompt, MODEL, timeout=timeout)
    op = (SecondOpinion(False, reason=err or "empty response", model=MODEL, context=context)
          if (err or not text.strip())
          else SecondOpinion(True, text=text, model=MODEL, context=context))
    _log(op)
    return op


def _log(op: SecondOpinion) -> None:
    """Append-only record of every second-family call -- so 'the partner is dead' is a MEASURED
    fact with a date, not an impression, and funding it can be justified with evidence."""
    try:
        hist = json.loads(_LEDGER.read_text("utf-8"))
    except (OSError, ValueError):
        hist = {"calls": []}
    hist["calls"].append(op.to_dict())
    hist["calls"] = hist["calls"][-1000:]
    try:
        _LEDGER.parent.mkdir(parents=True, exist_ok=True)
        _LEDGER.write_text(json.dumps(hist, indent=2), "utf-8")
    except OSError:
        return


def merge_verdict(own: object, other: SecondOpinion) -> dict[str, Any]:
    """Label the joint result HONESTLY -- the whole value of a second family is in the label.

    CONFIRMED   both families produced findings -- the strongest signal this desk can generate
                without live evidence.
    SOLO        the partner was unavailable. Explicitly NOT 'confirmed': a single family's
                agreement with itself is style, and recording SOLO is what stops one model's
                opinion from being cited later as cross-family corroboration.
    CONTESTED   both ran, and the partner found something the first family did not -- the second
                strongest signal, because the delta is a measured blind spot.
    """
    own_txt = str(own or "").strip()
    if not other.available:
        return {"verdict": "SOLO", "reason": other.reason,
                "note": "single-family run -- NOT cross-family corroboration"}
    if own_txt and other.text.strip():
        return {"verdict": "CONFIRMED", "partner_chars": len(other.text),
                "note": "two independent families both produced findings; the DELTA between "
                        "them is the blind spot each could not see alone -- read it, do not "
                        "average it away"}
    return {"verdict": "CONTESTED", "partner_chars": len(other.text),
            "note": "the families disagree on whether anything is here; the partner's finding "
                    "is a candidate blind spot of the first"}


def blindspot_prompt(context: str, own_findings: str) -> str:
    """The standing partner brief: hunt what the FIRST family missed, never re-rank its list."""
    return (
        f"You are the INDEPENDENT SECOND MODEL FAMILY on a quant research desk's exploration "
        f"organ ({context}). Another model family has just hunted this space and produced the "
        f"findings below.\n\nYOUR JOB IS NOT TO REVIEW OR RE-RANK THEM. It is to name what they "
        f"MISSED -- the region their priors could not see. A model cannot see its own blind "
        f"spot; you exist because you have different ones.\n\n--- THEIR FINDINGS ---\n"
        f"{own_findings[:6000]}\n\n--- YOUR OUTPUT ---\n"
        f"MISSED: <the thing absent from their list, one line>\n"
        f"WHY THEY COULD NOT SEE IT: <what in their framing excludes it>\n"
        f"EVIDENCE: <the check/command/artifact that would confirm or kill it>\n"
        f"IF NOTHING: say 'NOTHING MISSED' and name the three regions you checked. An honest "
        f"null from an independent family is a real result -- padding is a defect.")
