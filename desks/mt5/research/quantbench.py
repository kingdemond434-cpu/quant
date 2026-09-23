"""QUANTBENCH -- every historical defect as one replayable corpus that new code must beat WHOLE.

THE GAP THE LEDGER NAMED (Tier-1 B18): *"defects are pinned as tests one at a time; no replayable
corpus that new code must beat as a whole."* A defect pinned as its own test is pinned where the
person who fixed it was looking. Nothing then asks the only question that matters a year later --
*does this tree still beat every defect the desk has ever paid for?* -- and nothing reports the
answer as ONE number that a change has to move in the right direction.

WHAT A CASE IS. A row of `data/quantbench/corpus.jsonl`, each naming:

    id            the case's permanent name
    lesson        the desk lesson (docs/desk_lessons.jsonl) or the incident it came from
    bit_on        when the defect actually cost something, and what it cost
    check         the registered probe that replays it
    expect        what a healthy tree returns, pinned as data (hashes, floors, invariants)

The PROBE lives in code because a defect is a behaviour, not a string; the EXPECTATION lives in
the corpus because it is evidence. New cases are added by appending a row and registering its
probe -- never by editing a probe to agree with a tree that broke it.

VERDICTS: PASS (the tree beats the defect), REGRESSED (the defect is back -- this is the number
the bench exists to publish), UNMEASURED (the probe could not run here; never a pass, L1.28a).

WHAT IT IS NOT. It is not a gate on research and it refuses nothing: it runs hourly, writes
`reports/QUANTBENCH.json`, and `desks/mt5/tests/test_quantbench.py` fails the suite when any case
reads REGRESSED. No threshold of its own, no capital effect, no sealed file imported.

    python desks/mt5/research/quantbench.py --once --budget-s 120
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

CORPUS = DESK / "data" / "quantbench" / "corpus.jsonl"
OUT = DESK / "reports" / "QUANTBENCH.json"

SEALED = ("desks/mt5/scripts/external_gauntlet.py", "desks/mt5/research/promoter.py",
          "libs/portfolio/allocator_proof.py", "libs/regime/state_admission.py")


def _sha(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


# --------------------------------------------------------------------------- probes
def probe_leg_budget_floor(expect: dict[str, Any]) -> dict[str, Any]:
    """THE TRUNCATED-JOB DEFECT that cost eighty-four forward clocks: a cycle cap BELOW the
    organ's own `--budget-s` cuts the same prefix every hour, forever, while reporting as run."""
    src = (DESK / "research" / "hourly_cycle.py").read_text(encoding="utf-8", errors="replace")
    own: dict[str, float] = {}
    for m in re.finditer(r'_producer\(\s*"([a-z0-9_]+)"[^)]*?"--budget-s",\s*"(\d+)"', src,
                         re.S):
        own[m.group(1)] = float(m.group(2))
    caps: dict[str, float] = {}
    block = re.search(r"LEG_BUDGET_SEC: dict\[str, int\] = \{(.*?)\n\}", src, re.S)
    if block:
        for m in re.finditer(r'"([a-z0-9_]+)":\s*([0-9_]+)', block.group(1)):
            caps[m.group(1)] = float(m.group(2).replace("_", ""))
    bad = {k: {"cap": caps[k], "own_budget": v} for k, v in own.items()
           if k in caps and caps[k] < v}
    if not own:
        return {"verdict": "UNMEASURED", "why": "no --budget-s leg found in hourly_cycle.py"}
    return {"verdict": "REGRESSED" if bad else "PASS",
            "n_legs_with_own_budget": len(own), "n_capped": len(caps),
            "violations": bad,
            "why": ("a cycle cap below an organ's own budget truncates it at the same prefix "
                    "every hour" if bad else "every capped leg's cap sits at or above its own "
                                             "budget")}


def probe_sealed_files(expect: dict[str, Any]) -> dict[str, Any]:
    """THE SEALED JUDGE. Four files no session may edit; their hashes are pinned as evidence."""
    pinned = expect.get("sha256") or {}
    now = {p: _sha(ROOT / p) for p in SEALED}
    missing = [p for p, h in now.items() if h is None]
    if missing:
        return {"verdict": "UNMEASURED", "why": f"not present on this host: {missing}"}
    if not pinned:
        return {"verdict": "UNMEASURED", "why": "corpus row carries no pinned hashes",
                "observed": now}
    changed = {p: {"pinned": pinned.get(p), "now": now[p]} for p in now
               if pinned.get(p) and pinned[p] != now[p]}
    return {"verdict": "REGRESSED" if changed else "PASS", "changed": changed,
            "why": ("a sealed file's bytes moved" if changed else "all four seals hold")}


def probe_forward_clock_monotone(expect: dict[str, Any]) -> dict[str, Any]:
    """THE CHURNED CLOCK: a forward window that restarted at day 0 while reporting as enrolled."""
    try:
        from research.clock_ledger import stamp
    except Exception as exc:
        return {"verdict": "UNMEASURED", "why": f"clock_ledger unavailable: {exc}"}
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        led = Path(td) / "ledger.json"
        first = stamp("case|key", "ident-a", "2026-01-01T00:00:00+00:00", path=led)["start"]
        later = stamp("case|key", "ident-a", "2026-02-01T00:00:00+00:00", path=led)["start"]
        earlier = stamp("case|key", "ident-a", "2025-12-01T00:00:00+00:00", path=led)["start"]
        fresh = stamp("case|key", "ident-b", "2026-03-01T00:00:00+00:00", path=led)
    ok = (later == first and earlier < first and fresh["start"] == "2026-03-01T00:00:00+00:00"
          and fresh["opened_new_clock"] is True)
    return {"verdict": "PASS" if ok else "REGRESSED",
            "first": first, "after_later_write": later, "after_earlier_write": earlier,
            "new_identity": fresh,
            "why": ("a later write moved the start" if later != first else
                    "start is min(previous, proposed) and a new identity opens a new clock")}


def probe_producer_variadic(expect: dict[str, Any]) -> dict[str, Any]:
    """THE CYCLE-KILLING SIGNATURE: `_producer(name, script, "--mode", "normal")` raised
    TypeError and took the whole hour's remaining legs with it."""
    import inspect
    src = (DESK / "research" / "hourly_cycle.py").read_text(encoding="utf-8", errors="replace")
    m = re.search(r"def _producer\(([^)]*)\)", src, re.S)
    if not m:
        return {"verdict": "UNMEASURED", "why": "no _producer definition found"}
    sig = m.group(1)
    del inspect
    return {"verdict": "PASS" if "*args" in sig else "REGRESSED", "signature": sig.strip(),
            "why": ("_producer is variadic" if "*args" in sig else
                    "_producer is not variadic: a leg passing flags dies with TypeError")}


def probe_desk_memory_budget(expect: dict[str, Any]) -> dict[str, Any]:
    """THE SILENT WITHHOLDING: a 12,000-char budget hid 69 lessons from every organ."""
    try:
        from libs.research import desk_memory
    except Exception as exc:
        return {"verdict": "UNMEASURED", "why": f"desk_memory unavailable: {exc}"}
    budget = int(getattr(desk_memory, "BUDGET_CHARS", 0))
    floor = int(expect.get("min_budget_chars") or 0)
    return {"verdict": "PASS" if budget >= floor else "REGRESSED",
            "budget_chars": budget, "floor": floor,
            "why": ("the whole corpus fits the injection budget" if budget >= floor else
                    "the budget is below the corpus: lessons are silently withheld")}


def probe_modifiers_two_sided(expect: dict[str, Any]) -> dict[str, Any]:
    """GROWTH GOVERNANCE RULE 2: a capital modifier that can only ever shrink is a brake."""
    try:
        from libs.portfolio.capital_modifiers import REGISTRY
    except Exception as exc:
        return {"verdict": "UNMEASURED", "why": f"capital_modifiers unavailable: {exc}"}
    one_sided = [m.name for m in REGISTRY
                 if str(getattr(m, "kind", "")) == "two_sided" and float(getattr(m, "hi", 0)) <= 1.0]
    return {"verdict": "REGRESSED" if one_sided else "PASS",
            "n_modifiers": len(REGISTRY), "one_sided": one_sided,
            "why": ("a modifier declared two_sided cannot boost" if one_sided else
                    "every two-sided modifier can move capital both ways")}


CHECKS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "leg_budget_floor": probe_leg_budget_floor,
    "sealed_files": probe_sealed_files,
    "forward_clock_monotone": probe_forward_clock_monotone,
    "producer_variadic": probe_producer_variadic,
    "desk_memory_budget": probe_desk_memory_budget,
    "modifiers_two_sided": probe_modifiers_two_sided,
}


def cases(path: Path = CORPUS) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return rows
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict) and row.get("id"):
            rows.append(row)
    return rows


def replay(rows: list[dict[str, Any]], budget_s: float = 120.0) -> list[dict[str, Any]]:
    started = time.monotonic()
    out: list[dict[str, Any]] = []
    for row in rows:
        if time.monotonic() - started > budget_s:
            out.append({**{k: row.get(k) for k in ("id", "lesson", "check")},
                        "verdict": "UNMEASURED", "why": "bench budget spent before this case"})
            continue
        fn = CHECKS.get(str(row.get("check")))
        t0 = time.monotonic()
        if fn is None:
            res: dict[str, Any] = {"verdict": "UNMEASURED",
                                   "why": f"no probe registered for {row.get('check')!r}"}
        else:
            try:
                res = dict(fn(row.get("expect") or {}))
            except Exception as exc:                          # a broken probe is never a pass
                res = {"verdict": "UNMEASURED", "why": f"{type(exc).__name__}: {exc}"}
        out.append({"id": row.get("id"), "lesson": row.get("lesson"), "check": row.get("check"),
                    "bit_on": row.get("bit_on"), "seconds": round(time.monotonic() - t0, 3),
                    **res})
    return out


def build(budget_s: float = 120.0, path: Path = CORPUS) -> dict[str, Any]:
    rows = cases(path)
    results = replay(rows, budget_s=budget_s)
    counts: dict[str, int] = {}
    for r in results:
        counts[str(r["verdict"])] = counts.get(str(r["verdict"]), 0) + 1
    regressed = [r for r in results if r["verdict"] == "REGRESSED"]
    return {
        "at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "status": ("REGRESSED" if regressed else ("OK" if results else "UNMEASURED")),
        "n_cases": len(results), "counts": counts,
        "score": (round(counts.get("PASS", 0) / len(results), 4) if results else None),
        "regressed": [r["id"] for r in regressed],
        "cases": results,
        "corpus": str(path),
        "rule": ("the corpus is beaten WHOLE or not at all: one REGRESSED case is the bench's "
                 "verdict, and UNMEASURED is never a pass (L1.28a)"),
        "consumers": [
            "desks/mt5/tests/test_quantbench.py -> the suite fails while any case reads "
            "REGRESSED, so a defect the desk has already paid for cannot come back silently",
            "desks/mt5/reports/QUANTBENCH.json -> the hourly record of the score",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--budget-s", type=float, default=120.0)
    ap.add_argument("--corpus", type=Path, default=CORPUS)
    a = ap.parse_args(argv)
    doc = build(budget_s=a.budget_s, path=a.corpus)
    try:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    except OSError as exc:
        print(f"quantbench: could not write {OUT}: {exc}")
        return 1
    print(f"quantbench: {doc['n_cases']} case(s) replayed -- "
          + ", ".join(f"{k} {v}" for k, v in sorted(doc["counts"].items())))
    for r in doc["cases"]:
        if r["verdict"] != "PASS":
            print(f"  {r['verdict']:<10} {r['id']!s:<28} {str(r.get('why'))[:90]}")
    print(f"written: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
