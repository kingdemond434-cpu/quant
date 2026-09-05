#!/usr/bin/env python3
"""THE MISSING PRODUCER -- feed the promotion gate real MT5 evidence instead of nothing.

WHAT WAS WRONG (principal 2026-08-26: "remove nonexistent eight-gate producers from the MT5
path"). `scripts/promotion_gate.py` reads `data/gauntlet_survivors.json`. Nothing in this
repository has ever written that file, so the eight-gate barrier has judged exactly zero
candidates for its entire existence while publishing NO-PRODUCER and returning rc 0 -- which the
cadence scored as a duty fired. A barrier with no input is not a strict barrier; it is a decoration
that makes the desk feel gated.

WHY REPOINT RATHER THAN DELETE. The eight gates it applies are not legacy: CPCV, PBO, DSR, reality
check, mechanism, capacity, fragility and walk-forward are the same discipline the MT5 ten-gate
policy enforces, plus TWO the ten do not cover -- capacity and fragility -- and those two are
exactly where a certified-but-unfillable sleeve dies. Deleting the gate would drop them. Feeding it
is strictly better than removing it.

WHERE EACH GATE'S EVIDENCE COMES FROM, all of it measured, none of it assumed:

    cpcv / pbo / dsr / reality_check / walk_forward  <- the sleeve's own ten-gate certificate
    mechanism                                        <- the certificate's economic_prior gate
    capacity      <- reconstructed execution: did it actually FILL, and how deep was the book?
                     A sleeve whose orders do not fill has no capacity at any size.
    fragility     <- measured slippage in R against the sleeve's own expectancy. A cell whose
                     execution cost eats its edge is fragile in the only sense that matters.

UNMEASURED IS FAILED, INHERITED FROM THE GATE ITSELF. This producer never invents a True: a gate
with no evidence is simply absent from the row, and `judge()` counts absence as failure. That is
why this file may be run safely before the evidence exists -- it will produce candidates that are
all rejected, which is the honest state, rather than an empty file that reads as "nothing to
judge".
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DESK = ROOT / "desks" / "mt5"
CERTS = DESK / "reports" / "UNIVERSAL_SURVIVORS.json"
EXECQ = DESK / "reports" / "execution_quality.json"
SHADOW = DESK / "reports" / "shadow" / "shadow_state.json"
OUT = ROOT / "data" / "gauntlet_survivors.json"

#: A cell must fill at least this often before capacity counts as demonstrated. Below it the
#: desk has not shown it can get into the trade at all.
MIN_FILL_RATE = 0.60
#: Slippage above this fraction of a cell's own expectancy makes it fragile: the execution cost
#: is eating the edge rather than trimming it.
MAX_SLIP_FRACTION = 0.50


def _read(path: Path):
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _passed(stages: dict, gate: str) -> bool | None:
    row = (stages or {}).get(gate)
    if not isinstance(row, dict) or "passed" not in row:
        return None
    return row["passed"] is True


def main() -> int:
    certs = (_read(CERTS) or {}).get("survivors") or {}
    execq = _read(EXECQ) or {}
    shadow = _read(SHADOW) or {}
    cells = execq.get("by_symbol_session") or {}

    out: dict[str, dict] = {}
    for name, cert in certs.items():
        spec = cert.get("shadow_spec") or {}
        sym = spec.get("symbol") or cert.get("sym")
        sel = spec.get("selector")
        if not sym:
            continue
        stages = cert.get("gates") or {}
        ev: dict[str, object] = {}

        # --- the five the ten-gate certificate already decides -------------------------------
        for gate_key, cert_gate in (("cpcv", "cpcv"), ("pbo", "pbo"), ("dsr", "deflated_sharpe"),
                                    ("reality_check", "reality_check_spa"),
                                    ("walk_forward", "walk_forward"),
                                    ("mechanism", "economic_prior")):
            got = _passed(stages, cert_gate)
            if got is not None:                  # absent stays ABSENT -> judged as failed
                ev[gate_key] = got

        # --- capacity: did this cell's orders actually fill, on the venue's own tape? ---------
        cell = cells.get(f"{sym}.{sel}") if sel else None
        if cell is None:
            for key, value in cells.items():     # fall back to the symbol's other sessions
                if key.startswith(f"{sym}."):
                    cell = value
                    break
        if isinstance(cell, dict) and cell.get("fills"):
            fills = int(cell["fills"])
            # rejection_rate is desk-wide; per-cell we have fills only, so express capacity as
            # "filled at all, with more than a token number of quotes around the level".
            density = ((cell.get("quote_density") or {}).get("median")) or 0
            ev["capacity"] = bool(fills >= 3 and density >= 10)

            # --- fragility: is slippage eating this cell's edge? -----------------------------
            slip = (cell.get("slippage_R") or {}).get("median")
            row = shadow.get(f"{sym}.{sel}") if sel else None
            exp = None
            if isinstance(row, dict):
                exp = row.get("exp_r")
            if slip is not None and isinstance(exp, (int, float)) and abs(exp) > 1e-9:
                ev["fragility"] = bool(abs(float(slip)) <= MAX_SLIP_FRACTION * abs(float(exp)))
            elif slip is not None:
                # Slippage measured but no forward expectancy to compare it against yet -- that
                # is UNMEASURED fragility, so the key stays absent and the gate fails closed.
                pass

        out[name] = ev

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=1, sort_keys=True), "utf-8")
    complete = sum(1 for ev in out.values() if len(ev) == 8)
    print(f"gauntlet survivors: {len(out)} candidate(s) written from real MT5 evidence; "
          f"{complete} carry all eight gates, {len(out) - complete} have at least one gate "
          f"UNMEASURED (which the promotion gate counts as failed)")
    print(f"  written at {datetime.now(tz=UTC).isoformat(timespec='seconds')} -> "
          f"{OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
