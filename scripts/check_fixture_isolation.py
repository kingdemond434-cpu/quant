#!/usr/bin/env python
"""FENCE: no synthetic fixture stands in a survivor, certificate, sleeve or performance record
(ARCH-17).

WHY. The desk manufactures strategies it knows are fake, on purpose and every hour:
`research/adversary.py` builds poison canaries (family `canary_<name>`, symbol `CANARY`) and
`research/placebo_audit.py` builds a known-good positive control and its planted-defect twins
(family `placebo_<name>`), and both hand them to the real `run_gauntlet`. The positive control is
BUILT TO PASS all ten gates. Promotion is automatic: a certified spec is written LIVE on the
cycle its clock matures. Until this fence nothing checked that those identities stay in their own
reports -- a refactor that let the audit's docket reach the survivor register would have put a
synthetic series' Sharpe in the book the allocator sizes from, and no artifact would have said so.

WHAT IT READS. `RECORDS`: the survivor register and ledger, the certificate provenance, the
sleeve roster and registry, the forward reconcile and the live deal ledger. Every identity field
of every row, however nested, and the keys of the survivor map.

WHAT IT FAILS. A record row whose identity carries a fixture marker (`PREFIXES`, `EXACT`). The
markers are the producers' own: `wiring()` proves from their source that the audits still mint
under these names, so a renamed fixture family fails here instead of walking past a stale list.

WHAT IT DOES NOT DO. It removes nothing and retires nothing; the box's state is the box's, and
the repair belongs to the organ that wrote the row. An absent record is UNMEASURED and named,
never clean (L1.28a). It caps nothing and gates no capital.

    python scripts/check_fixture_isolation.py [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
_D = "desks/mt5/data/"
_R = "desks/mt5/reports/"

#: The survivor, certificate, sleeve and performance records. `jsonl` is one row per line.
RECORDS: tuple[tuple[str, str], ...] = (
    (_R + "UNIVERSAL_SURVIVORS.json", "json"),
    (_R + "SURVIVORS_LEDGER.json", "json"),
    (_D + "certificate_provenance.json", "json"),
    (_D + "sleeves.json", "json"),
    (_D + "sleeve_registry.json", "json"),
    (_D + "forward_reconcile.json", "json"),
    (_D + "live_ledger.jsonl", "jsonl"),
)

#: Fields that NAME what a row is about. Prose fields (notes, reasons, rules) are not identities
#: and are not read: a rule that says "canaries are excluded" is not a canary.
IDENTITY_KEYS = frozenset({
    "family", "sym", "symbol", "hunt", "cell", "name", "sleeve", "tag", "key", "id", "spec",
    "certificate", "cert", "source_cell", "parent", "mechanism_family",
})

#: Maps whose KEYS are identities (`<hunt>.<cell>` in the survivor register).
IDENTITY_MAPS = frozenset({"survivors", "certificates", "sleeves", "clocks", "rows"})

#: An identity with a segment that STARTS with one of these (case-insensitive) is a fixture.
PREFIXES = ("canary_", "placebo_", "fixture_")
#: An identity with a segment that EQUALS one of these (case-insensitive) is a fixture.
EXACT = ("canary", "fixture")

#: Where each marker is minted: (producer source, the literal that must still be in it).
MINTED_BY: tuple[tuple[str, str], ...] = (
    ("desks/mt5/research/adversary.py", 'f"canary_{name}"'),
    ("desks/mt5/research/adversary.py", 'CANARY_SYMBOL = "CANARY"'),
    ("desks/mt5/research/placebo_audit.py", 'f"placebo_{p.name}"'),
)

_SEPARATORS = str.maketrans(dict.fromkeys("|/:.,;()[]", " "))


def is_fixture(value: Any) -> bool:
    """Does this identity name a synthetic fixture? Judged on each of its segments."""
    if not isinstance(value, str):
        return False
    return any(seg in EXACT or seg.startswith(PREFIXES)
               for seg in value.lower().translate(_SEPARATORS).split())


def _walk(node: Any, path: str, in_identity_map: bool = False) -> Iterator[tuple[str, str]]:
    """Yield (where, identity) for every identity the node carries."""
    if isinstance(node, dict):
        for k, v in node.items():
            here = f"{path}.{k}" if path else str(k)
            if in_identity_map:
                yield here, str(k)
            if k in IDENTITY_KEYS and isinstance(v, str):
                yield here, v
            yield from _walk(v, here, k in IDENTITY_MAPS and isinstance(v, dict))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _walk(v, f"{path}[{i}]")


def scan(doc: Any) -> list[dict[str, str]]:
    """Every fixture identity in one parsed record."""
    return [{"where": where, "identity": ident[:160]}
            for where, ident in _walk(doc, "") if is_fixture(ident)]


def _load(path: Path, layout: str) -> Any:
    if layout == "jsonl":
        rows = []
        with path.open(encoding="utf-8-sig") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    try:
                        rows.append(json.loads(line))
                    except ValueError:
                        continue
        return rows
    return json.loads(path.read_text("utf-8-sig"))


def wiring(root: Path = ROOT) -> list[str]:
    """The markers are still the names the audits mint under."""
    problems = []
    for rel, literal in MINTED_BY:
        try:
            src = (root / rel).read_text("utf-8")
        except OSError:
            problems.append(f"{rel} is missing: the fence no longer knows what a fixture is called")
            continue
        if literal not in src:
            problems.append(f"{rel} no longer contains {literal!r}: the fixture family was "
                            "renamed, so re-derive the markers before a fixture walks past them")
    return problems


def measure(root: Path = ROOT) -> dict[str, Any]:
    problems = wiring(root)
    records: dict[str, dict[str, Any]] = {}
    unmeasured: list[str] = []
    for rel, layout in RECORDS:
        path = root / rel
        if not path.exists():
            records[rel] = {"status": "UNMEASURED", "why": "absent"}
            unmeasured.append(rel)
            continue
        try:
            doc = _load(path, layout)
        except (OSError, ValueError) as exc:
            records[rel] = {"status": "UNMEASURED", "why": f"unreadable ({type(exc).__name__})"}
            unmeasured.append(rel)
            continue
        hits = scan(doc)
        records[rel] = {"status": "FAIL" if hits else "CLEAN", "fixtures": hits[:20],
                        "n_fixtures": len(hits)}
        for h in hits[:5]:
            problems.append(f"{rel}: synthetic fixture {h['identity']!r} at {h['where']}")
        if len(hits) > 5:
            problems.append(f"{rel}: and {len(hits) - 5} more")
    verdict = "FAIL" if problems else "UNMEASURED" if unmeasured else "PASS"
    return {"verdict": verdict, "problems": problems, "unmeasured": unmeasured,
            "records": records, "markers": {"prefixes": list(PREFIXES), "exact": list(EXACT)},
            "rule": "a synthetic fixture's identity may stand only in the audit that minted it; "
                    "an absent record is UNMEASURED, never clean"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    doc = measure()
    if args.json:
        print(json.dumps(doc, indent=2))
    else:
        clean = sum(1 for r in doc["records"].values() if r["status"] == "CLEAN")
        print(f"FIXTURE ISOLATION: {doc['verdict']} -- {clean} of {len(doc['records'])} "
              "record(s) read clean")
        for p in doc["problems"]:
            print(f"  FAIL {p}")
        for u in doc["unmeasured"]:
            print(f"  UNMEASURED {u}")
    return 1 if doc["verdict"] == "FAIL" else 0


if __name__ == "__main__":
    sys.exit(main())
