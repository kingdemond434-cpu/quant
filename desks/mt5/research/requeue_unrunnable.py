"""Send certificates that cannot be executed back through the gauntlet, so they can be re-earned.

THE STUCK STATE. A certificate whose `shadow_spec.params` is None passed all ten gates but
carries no parameterisation, so nothing can replay it: not the forward clock, not the executor,
not the gateway. `survivor_publication` -- the fixer the issue board names -- runs every hour and
cannot help, because it can only publish the parameters a gauntlet run recorded, and this run
recorded none. So the same six certificates were reported as AUTO-REPAIRABLE, the repair ran
hourly, and nothing changed. A fixer that cannot fix the thing it is offered for is worse than
no fixer: it converts a standing defect into a line everybody scrolls past.

The only honest recovery is to TEST THEM AGAIN. The current gauntlet records the parameterisation
it tested, so a cell that passes now is executable by construction. This organ puts them back on
the docket and lets the ordinary pipeline judge them.

WHAT THIS IS NOT. It does not revoke the certificate, invent parameters, or promote anything. The
existing certificate stands exactly as it is until a new run replaces it -- and if the re-run
fails the gates, that is the correct answer to a claim the desk could never have executed anyway.
Requeueing is cheap; guessing the parameters that passed is fabricating evidence.

AN EMPTY MAPPING IS NOT THIS CASE. `{}` is the COMPLETE parameterisation "family defaults" and
enrols normally -- `survivor_publication.unrunnable_reason` draws that line and this module asks
it rather than re-deciding, so the two cannot drift.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
DOCKET = BASE / "data" / "hypotheses" / "external_survivors.json"
OUT = BASE / "reports" / "REQUEUED_UNRUNNABLE.json"

sys.path.insert(0, str(BASE / "research"))


def _canon_rows() -> tuple[list[dict], str]:
    """The certificate canon, read through ADMISSION'S OWN loader.

    A path chosen here would be a second opinion about which file is the canon, and this desk has
    already paid for that: `shadow_admission.CANON_SOURCES` tries the gauntlet's latest sweep
    first and the last SEALED canon second, in that order and for stated reasons. Hardcoding
    `reports/UNIVERSAL_SURVIVORS.json` -- as the first draft of this file did -- makes this organ
    UNANSWERED on any host where only the sealed canon is present, while admission reads it fine
    and enrols from it. Two modules disagreeing about which certificates exist is the failure the
    shared loader exists to prevent.
    """
    from shadow_admission import _canon
    payload, source = _canon(BASE)
    return _rows(payload), source


def _rows(payload: Any) -> list[dict]:
    """Certificates from the canon, each carrying the KEY IT WAS FILED UNDER.

    THE IDENTITY IS IN THE KEY, and the first draft of this threw it away. The canon is a mapping
    of `external.CADJPY.session_range_breakout` -> {gates, shadow_spec, ...}, alongside sibling
    blocks for the policy and the gate report. Taking `payload.values()` returned three "rows":
    the survivors mapping, the policy block and the gate report -- none of them certificates, all
    of them lacking `shadow_spec`, and therefore all three reported as unexecutable. The organ
    would have announced three stuck certificates that do not exist while the real ones went
    unexamined, which is worse than finding nothing.
    """
    def _harvest(mapping: dict) -> list[dict]:
        out = []
        for key, row in mapping.items():
            if isinstance(row, dict) and ("gates" in row or "shadow_spec" in row):
                out.append({**row, "_key": str(key)})
        return out

    if isinstance(payload, list):
        return [r for r in payload if isinstance(r, dict)]
    if not isinstance(payload, dict):
        return []
    for name in ("survivors", "certificates", "rows"):
        value = payload.get(name)
        if isinstance(value, dict):
            return _harvest(value)
        if isinstance(value, list):
            return [r for r in value if isinstance(r, dict)]
    return _harvest(payload)          # the canon is the mapping itself


def _identity(row: dict) -> tuple[str, str]:
    """(symbol, family) for a certificate, from its own fields or else from its filing key.

    Keys look like `external.<SYMBOL>.<family>` with an optional `.p=<hash>` parameter digest, or
    `.rr=1.5_wb=12` selector suffix. Parsed positionally rather than by regex over the whole
    string, so a family containing an underscore or a symbol containing a digit is unaffected.

    A key this cannot read yields ("", "") and the caller REPORTS it rather than requeueing a
    guess -- a docket cell naming the wrong instrument is worse than one that was never written.
    """
    spec = row.get("shadow_spec") if isinstance(row.get("shadow_spec"), dict) else {}
    symbol = str(spec.get("symbol") or row.get("symbol") or "").strip()
    family = str(spec.get("family") or row.get("family") or "").strip()
    if symbol and family:
        return symbol, family
    parts = str(row.get("_key") or "").split(".")
    # lane . SYMBOL . family [. p=hash | . rr=..._wb=...]
    if len(parts) >= 3:
        symbol = symbol or parts[1].strip()
        family = family or parts[2].strip()
    return symbol, family


def unrunnable(rows: list[dict]) -> list[tuple[dict, str]]:
    """Every certificate the shared judge calls unexecutable, with its reason."""
    from survivor_publication import unrunnable_reason
    out = []
    for row in rows:
        why = unrunnable_reason(row)
        if why:
            out.append((row, why))
    return out


def _candidate(row: dict, why: str) -> dict:
    """A docket cell for the thing the certificate claims, carrying no parameters of its own.

    NO PARAMS, DELIBERATELY. The gauntlet's own grid decides what to test; supplying a guess here
    would reintroduce exactly the fabrication this module exists to avoid, and the certificate's
    stored params are the thing that is missing.
    """
    symbol, family = _identity(row)
    return {
        "symbol": symbol,
        "family": family,
        "certificate_key": str(row.get("_key") or ""),
        "params": {},
        "source": "requeue_unrunnable",
        "why": why,
        "requeued_utc": datetime.now(UTC).isoformat(timespec="seconds"),
    }


def main(argv: list[str] | None = None) -> int:
    apply = "--apply" in (argv if argv is not None else sys.argv[1:])
    try:
        rows, source = _canon_rows()
    except Exception as exc:                                            # noqa: BLE001
        print(f"UNANSWERED: the certificate canon could not be read via shadow_admission "
              f"({type(exc).__name__}: {exc}). Nothing is requeued and nothing is claimed.",
              file=sys.stderr)
        return 2
    if not rows:
        print(f"UNANSWERED: the canon ({source}) holds no certificates on this host -- "
              f"an empty canon is not 'nothing is stuck'.", file=sys.stderr)
        return 2

    stuck = unrunnable(rows)
    cells = [_candidate(r, why) for r, why in stuck]
    # A cell naming no symbol or no family cannot be tested and must not be written -- it would
    # sit on the docket forever being refused, which is the shape of the problem, not a fix.
    usable = [c for c in cells if c["symbol"] and c["family"]]
    unusable = [c for c in cells if not (c["symbol"] and c["family"])]

    report = {
        "at": datetime.now(UTC).isoformat(timespec="seconds"),
        "canon_source": source,
        "certificates_examined": len(rows),
        "unrunnable": len(stuck),
        "requeued": len(usable) if apply else 0,
        "would_requeue": len(usable),
        "unusable_no_identity": len(unusable),
        "reasons": sorted({why for _, why in stuck}),
        "cells": usable,
        "applied": apply,
    }

    if apply and usable:
        try:
            docket = json.loads(DOCKET.read_text("utf-8")) if DOCKET.exists() else []
        except ValueError:
            docket = []
        existing = docket if isinstance(docket, list) else []
        # IDEMPOTENT: the hourly cycle runs this every pass, and a docket that grows by six rows
        # an hour forever is its own outage. Identity is (symbol, family, source).
        seen = {(str(c.get("symbol")), str(c.get("family")), str(c.get("source")))
                for c in existing if isinstance(c, dict)}
        fresh = [c for c in usable
                 if (c["symbol"], c["family"], c["source"]) not in seen]
        if fresh:
            existing.extend(fresh)
            DOCKET.parent.mkdir(parents=True, exist_ok=True)
            DOCKET.write_text(json.dumps(existing, indent=1), encoding="utf-8")
        report["requeued"] = len(fresh)
        report["already_on_docket"] = len(usable) - len(fresh)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    verb = "requeued" if apply else "would requeue"
    print(f"{len(stuck)} unexecutable certificate(s); {verb} {report['requeued'] if apply else len(usable)}"
          f"{'' if apply else ' (--apply to write)'}")
    for reason in report["reasons"]:
        print(f"  reason: {reason[:110]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
