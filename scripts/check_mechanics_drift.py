#!/usr/bin/env python3
"""THE PUBLISHED TERMS AGAINST THE DECLARED ONES: a drift fence, read-only.

The global mining pipeline snapshots broker and prop-firm pages and publishes their numeric
terms, point-in-time, in `desks/mt5/data/mechanics_facts.json`. The desk DECLARES the same terms
elsewhere: a prop account's limits in `mt5desk.account_profile.PROFILES`, the commission it
charges in `mt5desk.engine.Costs`. When a firm changes a rule, the declared number is wrong from
that moment and nothing said so. This fence says so.

WHICH PAGE ANSWERS FOR WHICH NUMBER is a decision, not a derivation -- a rules page names no
account and a spec page names no symbol -- so the join lives in the committed map
`libs/mining/mechanics_map.json`, reviewed like code.

IT WRITES NO CHARGE AND NO LIMIT. It reads, compares and reports to
`desks/mt5/reports/MECHANICS_DRIFT.json`. Making `account_profile` or `cost_truth` CONSUME the
published terms is money-path work and goes to the desktop pass as its own patch.

EXIT CODES. 1 when a mapped `breach` field has MEASURED drift. 0 otherwise, including when the
facts are UNMEASURED (the pipeline has not snapshotted the page yet), which the report states --
absence is never rendered as agreement, and never as a breach either (L1.28a, L1.43).

    python scripts/check_mechanics_drift.py [--root PATH]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FACTS_REL = "desks/mt5/data/mechanics_facts.json"
MAP_REL = "libs/mining/mechanics_map.json"
OUT_REL = "desks/mt5/reports/MECHANICS_DRIFT.json"
TOLERANCE = 1e-9


def _json(p: Path) -> Any:
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def declared_profiles(root: Path) -> dict[str, dict[str, Any]]:
    for p in (str(root / "desks" / "mt5"), str(root)):
        if p not in sys.path:
            sys.path.insert(0, p)
    from mt5desk.account_profile import PROFILES
    return {name: {k: getattr(prof, k, None) for k in
                   ("daily_loss_limit", "max_drawdown_limit", "profit_target")}
            for name, prof in PROFILES.items()}


def charged(root: Path, dotted: str) -> float | None:
    if dotted != "engine.Costs.commission_per_lot":
        return None
    for p in (str(root / "desks" / "mt5"), str(root)):
        if p not in sys.path:
            sys.path.insert(0, p)
    from mt5desk.engine import Costs
    v = Costs.__dataclass_fields__["commission_per_lot"].default
    return float(v) if isinstance(v, (int, float)) else None


def _pages(facts: Any, source_id: str, needle: str) -> list[dict[str, Any]]:
    pages = (facts or {}).get("pages") or {}
    return [p for p in pages.values() if isinstance(p, dict)
            and p.get("source_id") == source_id and needle in str(p.get("source_uri") or "")]


def check(root: Path = ROOT) -> dict[str, Any]:
    facts = _json(root / FACTS_REL)
    mapping = _json(root / MAP_REL) or {}
    rows: list[dict[str, Any]] = []
    profiles = declared_profiles(root)
    for m in mapping.get("prop") or []:
        pages = _pages(facts, m["source_id"], m["uri_contains"])
        decl = profiles.get(m["profile"])
        for fact, attr in (m.get("fields") or {}).items():
            row = {"kind": "prop", "profile": m["profile"], "fact": fact, "declared_attr": attr,
                   "severity": m.get("severity", "breach"), "page": m["uri_contains"]}
            dv = (decl or {}).get(attr)
            pv = next((p["prop_rules"].get(fact) for p in pages
                       if isinstance(p.get("prop_rules"), dict)
                       and fact in p["prop_rules"]), None)
            if decl is None:
                row.update(state="UNMEASURED", why=f"profile {m['profile']} is not declared")
            elif not pages or pv is None:
                row.update(state="UNMEASURED", why="no published vintage of this fact yet")
            elif dv is None:
                row.update(state="UNMEASURED", published=pv / 100.0,
                           why="the profile declares no value for it")
            else:
                pub = float(pv) / 100.0
                row.update(published=pub, declared=float(dv),
                           state="DRIFT" if abs(pub - float(dv)) > TOLERANCE else "AGREES")
            rows.append(row)
    for m in mapping.get("cost") or []:
        pages = _pages(facts, m["source_id"], m["uri_contains"])
        pv = next((p["cost"].get(m["fact"]) for p in pages if isinstance(p.get("cost"), dict)
                   and m["fact"] in p["cost"]), None)
        cv = charged(root, m["charged"])
        row = {"kind": "cost", "fact": m["fact"], "charged_by": m["charged"],
               "severity": m.get("severity", "report"), "page": m["uri_contains"],
               "note": m.get("note", "")}
        if pv is None or cv is None:
            row.update(state="UNMEASURED", why="no published vintage of this fact yet"
                       if pv is None else "charged value unreadable")
        else:
            row.update(published=float(pv), charged=cv,
                       state="DRIFT" if abs(float(pv) - cv) > TOLERANCE else "AGREES")
        rows.append(row)
    breaches = [r for r in rows if r["state"] == "DRIFT" and r["severity"] == "breach"]
    return {"generated_at": datetime.now(tz=UTC).isoformat(),
            "facts_generated_at": (facts or {}).get("generated_at"),
            "facts_status": "UNMEASURED" if not (facts or {}).get("pages") else "MEASURED",
            "rows": rows, "breaches": len(breaches),
            "drift_reported": sum(1 for r in rows if r["state"] == "DRIFT"),
            "rule": "read-only: writes no charge and no limit; consumption is a desktop patch"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", type=Path, default=ROOT)
    args = ap.parse_args(argv)
    rep = check(args.root)
    out = args.root / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=1) + "\n", "utf-8")
    for r in rep["rows"]:
        if r["state"] == "DRIFT":
            print(f"  DRIFT [{r['severity']}] {r.get('profile') or r.get('charged_by')} "
                  f"{r['fact']}: published {r.get('published')} vs declared "
                  f"{r.get('declared', r.get('charged'))} ({r['page']})")
    print(f"mechanics drift: {rep['breaches']} breach(es), {rep['drift_reported']} drift row(s), "
          f"facts {rep['facts_status']}")
    return 1 if rep["breaches"] else 0


if __name__ == "__main__":
    sys.exit(main())
