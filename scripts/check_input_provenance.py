#!/usr/bin/env python3
"""TRANSITIVE FRESHNESS FENCE (L1.55) -- is a decision-path artifact's own input on record?

WHAT THIS ASKS THAT check_freshness DOES NOT. L1.44 asks "is the file I am reading current?" --
one hop, and only about AGE. It cannot see one level down: whether the producer of that file was
able to read ITS inputs, or quietly defaulted them. So an artifact can be young, well-formed,
pass every min_rows floor, satisfy its freshness contract, and be fabricated end to end. On the
day this fence was written `data/live_guard.json` was exactly that: its ramp block was built from
`data/ramp_state.json`, a file that has never existed on this box, and the chain reported green
at every link -- `read_fresh(max_age_h=0.25)` FRESH to the executor, `check_freshness` OK over
the whole registry. Freshness does not compose, and nothing checked that it did.

SCOPE COMES FROM THE CONSUMER REGISTRY, NOT A SIXTH HAND LIST. `libs/ops/fresh.py` already
builds `data/freshness_contracts.jsonl` from actual reads, so the set of artifacts that steer
decisions is already known and already self-maintaining. This fence walks that set and asks each
member the next question down: do you declare where YOU came from? A hand-enumerated list would
rot exactly as the desk's five producer-side registries rotted, and the whole point of the L1.44
substrate is that it does not have to be maintained.

THE VERDICTS:
  * DECLARED     -- the artifact carries a `provenance` block and every required input READ.
  * HONEST-GAP   -- it carries one, an input is ABSENT/UNREADABLE/DEFAULTED, AND the artifact
                    says so (`measured: false`). This is a CORRECT artifact with a missing
                    producer: the defect is upstream, and it is named rather than hidden.
  * FABRICATED   -- it declares a required input ABSENT/UNREADABLE/DEFAULTED while still
                    presenting the derived value as measured. THE FAILING STATE.
  * UNDECLARED   -- consumed on a decision path, declares nothing. Cannot be distinguished from
                    a fabricated one, which is why it counts against coverage.
  * MISSING      -- consumed but not present on this box.

THE FENCE'S OWN STATUS, and it may never read OK on an empty measurement set (L1.28a):
  FABRICATED (exit 2) -- at least one artifact contradicts itself.
  UNMEASURED (exit 2) -- no consumed artifacts could be examined at all.
  PARTIAL    (exit 0) -- coverage below 100%, nothing fabricated. Deliberately NOT a failure:
                         coverage is a RATCHET (L1.0) whose gap is the work queue, and a fence
                         that fails red from its first day gets switched off (L1.43).
  OK         (exit 0) -- every consumed artifact declares, none fabricates.

    python scripts/check_input_provenance.py [--report-only] [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from libs.ops.fence_exit import fence_exit  # noqa: E402
from libs.ops.input_provenance import _FABRICATING  # noqa: E402
from libs.ops.lawful import guard as _law_guard  # noqa: E402

_REGISTRY = _ROOT / "data/freshness_contracts.jsonl"
_OUT = _ROOT / "data/input_provenance.json"

#: Registry rows whose path escapes the repo are pytest temp dirs and other machines' runs. They
#: are 85% of the registry (the deep sweep's finding) and measuring them would drown the signal.
_FOREIGN_HINTS = ("/tmp/", "pytest-", "/private/var/")  # noqa: S108 -- matched, never written to


def _consumed_paths() -> tuple[list[str], str]:
    """Distinct repo-relative artifacts that some decision path actually READ."""
    if not _REGISTRY.exists():
        return [], f"{_REGISTRY.relative_to(_ROOT)} ABSENT -- no consumer registry to walk"
    seen: dict[str, None] = {}
    try:
        for line in _REGISTRY.read_text("utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue                      # one torn line must not blind the whole fence
            if rec.get("event") != "contract":
                continue
            p = str(rec.get("path") or "")
            if not p or any(h in p for h in _FOREIGN_HINTS) or Path(p).is_absolute():
                continue
            seen.setdefault(p, None)
    except OSError as e:
        return [], f"registry UNREADABLE: {e!r}"
    return sorted(seen), ""


def _provenance_blocks(data: Any) -> list[tuple[str, Any, Any]]:
    """Every (location, provenance, measured) triple in an artifact, at any nesting depth.

    Walks rather than checking the top level, because a producer declares provenance PER
    DERIVED BLOCK -- run_live_guard carries one under `ramp` and another under `stage_gate`,
    and a top-level-only reader would score both as UNDECLARED.
    """
    found: list[tuple[str, Any, Any]] = []

    def walk(node: Any, where: str) -> None:
        if isinstance(node, dict):
            if "provenance" in node:
                found.append((where or "<root>", node.get("provenance"), node.get("measured")))
            for k, v in node.items():
                if k != "provenance":
                    walk(v, f"{where}.{k}" if where else str(k))
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, f"{where}[{i}]")

    walk(data, "")
    return found


def _classify(rel: str) -> dict[str, Any]:
    p = _ROOT / rel
    row: dict[str, Any] = {"artifact": rel}
    try:
        data = json.loads(p.read_text("utf-8"))
    except FileNotFoundError:
        return {**row, "verdict": "MISSING", "detail": "consumed but not present on this box"}
    except (OSError, json.JSONDecodeError) as e:
        return {**row, "verdict": "MISSING", "detail": f"unreadable: {e!r}"}

    blocks = _provenance_blocks(data)
    if not blocks:
        return {**row, "verdict": "UNDECLARED",
                "detail": "no provenance block -- its inputs are unknowable from the artifact"}

    bad: list[str] = []
    lying: list[str] = []
    for where, prov, measured in blocks:
        if not isinstance(prov, list):
            continue
        absent = [str(r.get("path")) for r in prov
                  if isinstance(r, dict) and r.get("status") in _FABRICATING
                  and r.get("required", True)]
        if not absent:
            continue
        bad.append(f"{where}: {', '.join(absent)}")
        # THE CONTRADICTION THIS FENCE EXISTS FOR: a declared-absent input published as measured.
        if measured is not False:
            lying.append(f"{where} declares {', '.join(absent)} absent but measured={measured!r}")

    if lying:
        return {**row, "verdict": "FABRICATED", "detail": "; ".join(lying)}
    if bad:
        return {**row, "verdict": "HONEST-GAP", "detail": "; ".join(bad)}
    return {**row, "verdict": "DECLARED", "detail": f"{len(blocks)} block(s), all inputs READ"}


def build() -> dict[str, Any]:
    paths, why = _consumed_paths()
    rows = [_classify(p) for p in paths]
    by = {v: sum(1 for r in rows if r["verdict"] == v)
          for v in ("DECLARED", "HONEST-GAP", "FABRICATED", "UNDECLARED", "MISSING")}

    examinable = [r for r in rows if r["verdict"] != "MISSING"]
    declared = by["DECLARED"] + by["HONEST-GAP"] + by["FABRICATED"]
    coverage = (declared / len(examinable)) if examinable else None

    if by["FABRICATED"]:
        status = "FABRICATED"
    elif not examinable:
        status = "UNMEASURED"                 # zero measured can never read OK (L1.28a)
    elif coverage is not None and coverage >= 1.0:
        status = "OK"
    else:
        status = "PARTIAL"

    undeclared = [r["artifact"] for r in rows if r["verdict"] == "UNDECLARED"]
    if status == "FABRICATED":
        nxt = ("Fix the contradiction: " + "; ".join(
            r["detail"] for r in rows if r["verdict"] == "FABRICATED"))
    elif status == "UNMEASURED":
        nxt = (why or "no consumed artifact could be examined") + \
              " -- run any organ that calls libs.ops.fresh.read_fresh to populate the registry"
    elif undeclared:
        nxt = (f"Declare inputs in {len(undeclared)} consumed artifact(s), highest-consumed "
               f"first: {', '.join(undeclared[:5])}. Wire with libs.ops.input_provenance.Inputs.")
    else:
        nxt = "every consumed artifact declares its inputs -- hold the floor (L1.0)"

    return {
        "generated": datetime.now(tz=UTC).isoformat(),
        "law": "L1.55",
        "status": status,
        "n_consumed": len(rows),
        "n_examinable": len(examinable),
        "coverage": None if coverage is None else round(coverage, 4),
        "by_verdict": by,
        "artifacts": rows,
        "detail": why,
        "next_action": nxt,
    }


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--report-only", action="store_true",
                    help="write the artifact and always exit 0")
    ap.add_argument("--json", action="store_true", help="print the artifact")
    args = ap.parse_args()

    rep = build()
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(rep, indent=2), "utf-8")

    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        cov = "n/a" if rep["coverage"] is None else f"{rep['coverage']:.0%}"
        print(f"input provenance (L1.55): {rep['status']} -- {rep['n_consumed']} consumed, "
              f"coverage {cov}")
        for r in rep["artifacts"]:
            if r["verdict"] != "DECLARED":
                print(f"  {r['verdict']:<11} {r['artifact']}: {r['detail'][:110]}")
        print(f"  next: {rep['next_action']}")

    if args.report_only:
        return 0
    # Existing pass/fail preserved exactly; only the L1.57 vacuity refusal is added (R0417).
    # Denominator = producers this run could actually examine, so a scope discovery that finds
    # nothing cannot report clean provenance over an empty set.
    code = 2 if rep["status"] in ("FABRICATED", "UNMEASURED") else 0
    return fence_exit("OK" if code == 0 else rep["status"], {"OK"}, scanned=rep["n_examinable"],
                      of="decision-path producers examinable", fence="check_input_provenance.py")


if __name__ == "__main__":
    raise SystemExit(main())
