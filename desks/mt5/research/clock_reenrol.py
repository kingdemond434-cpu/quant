#!/usr/bin/env python3
"""CLOCK RE-ENROLMENT -- hand frozen forward identities back to the engine that advances them.

THE ACT BEHIND THE VERDICT. `clock_liveness` finds a clock FROZEN because its identity is no
longer on `shadow_forward`'s roster: the roster is rebuilt every pass from the certificate canon,
the ledger row is never pruned, so the engine simply stops visiting the key while the row keeps
reading ACTIVE. Reporting that is worthless (LAWS 7: A REPORT IS NOT A REMEDY). This script is
the remedy -- it reconstructs those identities EXACTLY and calls the engine's own
`shadow_forward.main(rows=...)` on them, which is the entry point the pre-certification lane
already uses for its own rows.

RECONSTRUCTION IS EXACT OR IT IS REFUSED. `shadow_admission` forbids inventing lost parameters
from a display name, and a forward series run on guessed parameters is evidence about a strategy
nobody holds. So a key is reconstructed only from the immutable sleeve registry
(`data/sleeve_registry.json`, whose `identity` block carries family, symbol, direction, timeframe,
selector and params verbatim), and only when re-deriving `sleeve_key` from those fields returns
the SAME key byte for byte. Anything else is reported UNRECONSTRUCTIBLE with its reason and left
alone -- never guessed, never dropped silently.

NO ORDER AUTHORITY IS GRANTED, AND NONE IS TAKEN. A forward clock is a SHADOW lane; resuming one
resumes MEASUREMENT. Promotion is a separate certificate-gated act in the sealed
`research/promoter.py`, which this never touches. Nothing here caps enrolment either: every key
handed in that reconstructs exactly is run.

    python desks/mt5/research/clock_reenrol.py --keys-file <json list> --budget-s 240
    python desks/mt5/research/clock_reenrol.py --key "GER40.turn_of_month.continuous" --dry-run
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

REGISTRY = DESK / "data" / "sleeve_registry.json"
REPORT = DESK / "reports" / "CLOCK_REENROL.json"
STATE = DESK / "reports" / "shadow" / "shadow_state.json"

#: One engine row, in `shadow_forward.main(rows=...)`'s own arity:
#: (symbol, window/selector, params, family, side).
ENROL_ROW = tuple[str, str, dict[str, Any], str, str]


def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, ValueError):
        return None


def registry_rows() -> dict[str, dict[str, Any]]:
    doc = _read(REGISTRY)
    rows = doc.get("sleeves") if isinstance(doc, dict) else None
    return rows if isinstance(rows, dict) else {}


def _identity_row(
        ident: Mapping[str, Any]) -> tuple[str, str, dict[str, Any], str, str] | None:
    sym = str(ident.get("symbol") or "")
    win = str(ident.get("selector") or "")
    fam = str(ident.get("family") or "")
    side = str(ident.get("direction") or "LONG").upper()
    params = dict(ident.get("params") or {})
    tf = str(ident.get("timeframe") or "H1").upper()
    if tf and tf != "H1":
        params.setdefault("timeframe", tf)
    cond = ident.get("condition")
    if cond:
        params.setdefault("condition", cond)
    if not sym or not win or not fam:
        return None
    return sym, win, params, fam, side


def reconstruct(
        keys: Sequence[str]) -> tuple[list[ENROL_ROW], list[dict[str, Any]]]:
    """(rows the engine can run, refusals with their reason). Exact match or refusal."""
    import shadow_forward as sf  # type: ignore[import-not-found]

    want = set(keys)
    rows: list[ENROL_ROW] = []
    refused: list[dict[str, Any]] = []
    seen: set[str] = set()
    by_key: dict[str, dict[str, Any]] = {}
    for _name, entry in registry_rows().items():
        ident = entry.get("identity") if isinstance(entry, dict) else None
        if not isinstance(ident, dict):
            continue
        built = _identity_row(ident)
        if built is None:
            continue
        sym, win, params, fam, side = built
        try:
            key = sf.sleeve_key(sym, win, params, fam, side)
        except Exception:
            continue
        by_key.setdefault(key, {"row": (sym, win, params, fam, side), "identity": ident})
    for key in sorted(want):
        hit = by_key.get(key)
        if hit is None:
            refused.append({"key": key, "reason": "UNRECONSTRUCTIBLE",
                            "why": ("no sleeve-registry identity re-derives this key byte for "
                                    "byte; shadow_admission forbids inventing lost parameters "
                                    "from a display name")})
            continue
        if key in seen:
            continue
        seen.add(key)
        rows.append(hit["row"])
    return rows, refused


def run(keys: Sequence[str], budget_s: float, *, apply: bool = True) -> dict[str, Any]:
    t0 = time.monotonic()
    cwd = os.getcwd()
    os.chdir(str(DESK))
    try:
        import shadow_forward as sf
        rows, refused = reconstruct(keys)
        before = _read(STATE) or {}
        stamps_before = {k: (before.get(k) or {}).get("last_attempt_at")
                         for k in keys if isinstance(before.get(k), dict)}
        ran, error = 0, None
        if rows and apply:
            try:
                sf.main(rows=rows, ledger="shadow_state.json")
                ran = len(rows)
            except Exception as exc:          # an engine failure is evidence, not a crash here
                error = f"{type(exc).__name__}: {exc}"
        after = _read(STATE) or {}
        advanced = [k for k, was in stamps_before.items()
                    if isinstance(after.get(k), dict)
                    and str((after[k] or {}).get("last_attempt_at") or "") != str(was or "")]
        return {
            "at": time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime()),
            "asked": len(keys), "reconstructed": len(rows), "ran": ran,
            "advanced": len(advanced), "advanced_keys": advanced[:50],
            "refused": refused[:100], "refused_total": len(refused),
            "error": error, "applied": bool(apply),
            "budget_s": budget_s, "elapsed_s": round(time.monotonic() - t0, 2),
            "rule": ("exact reconstruction from the immutable sleeve registry or refusal; the "
                     "proof is the clock's own stamp moving, never the exit code"),
        }
    finally:
        os.chdir(cwd)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("--keys-file", help="JSON list of sleeve keys to re-enrol")
    ap.add_argument("--key", action="append", default=[], help="one key (repeatable)")
    ap.add_argument("--budget-s", type=float, default=240.0)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    keys: list[str] = list(a.key)
    if a.keys_file:
        doc = _read(Path(a.keys_file))
        if isinstance(doc, list):
            keys += [str(k) for k in doc]
    doc = run(keys, a.budget_s, apply=not a.dry_run)
    try:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    except OSError:
        pass
    print(json.dumps(doc, indent=1, default=str) if a.json else
          (f"clock re-enrol: asked {doc['asked']}, reconstructed {doc['reconstructed']}, "
           f"ran {doc['ran']}, advanced {doc['advanced']}, refused {doc['refused_total']}"
           + (f"; ENGINE ERROR {doc['error']}" if doc.get("error") else "")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
