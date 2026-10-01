#!/usr/bin/env python3
"""RESEARCH-LIVE IDENTITY, HOURLY: every LIVE sleeve, the spec it trades beside the spec research
certified -- family, symbol, selector, params and code hash.

    python desks/mt5/research/research_live_identity.py            # write the report
    python desks/mt5/research/research_live_identity.py --dry-run  # print, write nothing

The join and its rules are `libs/tiers/research_live_identity.py`. This organ loads the four
records it joins -- `data/sleeves.json` (what the gateway reads), `UNIVERSAL_SURVIVORS` (what
research certified), `data/sleeve_registry.json` (the clock research froze) and the docket
`data/hypotheses/external_survivors.json` (where the gateway recovers a sleeve's params) -- and
resolves each family's code through `mt5desk.executables.resolve_family`, the resolver the
gateway's own family executor calls, hashing it with `sleeve_registry.code_hash` /
`behaviour_hash`, the functions the forward clock froze it with.

READ-ONLY. It writes one report, `reports/RESEARCH_LIVE_IDENTITY.json`. A MISMATCH row is a named
defect there. Its ONE reader is `libs/tiers/promotion_authority._identity_mismatches`, called by
`review_live`, which the hourly `door` organ (`research/tier_s.py`) runs over the live book and
publishes as `data/tier_s/live_door.json`. NOTHING ACTS ON THAT FILE YET: the promoter's reader
(`retire_tier_s_live`) is the sealed desktop patch `tier_s_promoter_live_door_retirement.patch`
(T4), and until it lands a MISMATCH is published, never retired.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
for _p in (str(BASE), str(BASE / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.tiers import research_live_identity as rli  # noqa: E402

REPORT = BASE / "reports" / "RESEARCH_LIVE_IDENTITY.json"
SLEEVES = BASE / "data" / "sleeves.json"
SURVIVORS = (BASE / "reports" / "UNIVERSAL_SURVIVORS.json",
             BASE / "data" / "UNIVERSAL_SURVIVORS.canon.json")
REGISTRY = BASE / "data" / "sleeve_registry.json"
DOCKET = BASE / "data" / "hypotheses" / "external_survivors.json"


def _read(p: Path) -> Any:
    try:
        return json.loads(p.read_text("utf-8-sig"))
    except (OSError, ValueError):
        return None


def live_rows(doc: Any) -> list[dict[str, Any]]:
    rows = doc.get("sleeves") if isinstance(doc, dict) else doc
    return [r for r in rows if isinstance(r, dict)
            and str(r.get("status") or "").upper() == "LIVE"] if isinstance(rows, list) else []


def survivors() -> tuple[dict[str, Any], str]:
    for p in SURVIVORS:
        d = _read(p)
        if isinstance(d, dict):
            s = d.get("survivors", d)
            if isinstance(s, dict):
                return s, p.relative_to(ROOT).as_posix()
    return {}, rli.UNMEASURED


def docket_index(rows: Any) -> tuple[dict[str, Any], dict[tuple[str, str], list[Any]]]:
    """(cell_id -> params, (symbol, family) -> [params]) over the docket, hashed once."""
    from research.frontier_identity import cell_id
    idx: dict[str, Any] = {}
    by: dict[tuple[str, str], list[Any]] = {}
    for r in rows if isinstance(rows, list) else []:
        if not isinstance(r, dict) or not r.get("symbol") or not r.get("family"):
            continue
        params = r.get("params") if isinstance(r.get("params"), dict) else {}
        try:
            cid = cell_id({**r, "sym": r["symbol"], "family": r["family"], "params": params})
        except Exception:
            continue
        idx.setdefault(cid, params)
        by.setdefault((str(r["symbol"]), str(r["family"])), []).append(params)
    return idx, by


def code_of(family: str) -> tuple[str | None, str | None]:
    """(code_hash, behaviour_hash) of the function the gateway would call for `family` now."""
    try:
        import sleeve_registry as reg  # type: ignore[import-not-found]
        from mt5desk import executables
        fn = executables.resolve_family(family)
    except Exception:
        return None, None
    if fn is None:
        return None, None
    return reg.code_hash(fn), reg.behaviour_hash(fn)


def run(dry_run: bool = False) -> dict[str, Any]:
    live = live_rows(_read(SLEEVES))
    surv, surv_src = survivors()
    reg_doc = _read(REGISTRY)
    registry = (reg_doc or {}).get("sleeves") if isinstance(reg_doc, dict) else None
    registry = registry if isinstance(registry, dict) else {}
    idx, by = docket_index(_read(DOCKET))
    res = rli.judge(live, survivors=surv, registry=registry, docket_index=idx,
                    docket_by_sym_family=by, code_of=code_of)
    status = "MEASURED"
    if not live:
        status = "UNMEASURED: no LIVE row in data/sleeves.json"
    doc = {"generated_utc": datetime.now(UTC).isoformat(timespec="seconds"), "status": status,
           "inputs": {"sleeves": SLEEVES.relative_to(ROOT).as_posix(),
                      "survivors": surv_src, "survivor_rows": len(surv),
                      "registry_rows": len(registry), "docket_cells": len(idx)},
           "fields": list(rli.FIELDS), **res,
           "consumer": ("libs/tiers/promotion_authority._identity_mismatches (via review_live, "
                        "run by research/tier_s.py door -> data/tier_s/live_door.json; that "
                        "file's reader, promoter.retire_tier_s_live, is the unapplied sealed "
                        "patch T4)")}
    if not dry_run:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        tmp = REPORT.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
        tmp.replace(REPORT)
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    doc = run(a.dry_run)
    print(f"research-live identity: {doc['status']} live={doc['n_live']} {doc['counts']} "
          f"mismatched={doc['mismatched'][:8]}")
    for d in doc["defects"][:20]:
        print(f"  DEFECT {d['name']}: {d['why']}")
    return 0 if doc["status"] == "MEASURED" else 2


if __name__ == "__main__":
    sys.exit(main())
