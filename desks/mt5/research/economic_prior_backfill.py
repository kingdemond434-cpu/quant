"""Economic-prior backfill: which families still owe the six-field EconomicPrior (H3).

Gate 1 (`frontier_identity.economic_prior`) now asks every NAMED cell for the six-field
`EconomicPrior` -- why the edge exists, why it might fail, why it might be overfit, why it might
decay, how decay is detected, what replaces it. Families on the 2026-11-18 grandfather roster keep
passing without one, so nothing already hunted or certified is cut by the new rule. This report is
the other half of that bargain: it names, every hour, the debt the grandfather path carries, so the
exemption is a measured backlog rather than a silent pass.

Per family it reads the prior from `desks/mt5/data/economic_priors.json` and says COMPLETE,
INCOMPLETE (with the missing fields) or UNMEASURED (no prior written), together with how many
docket rows, certificates and sleeves stand on it. It also counts docket rows that gate 1 would
record PRIOR_INCOMPLETE: a NAMED family off the roster with no complete prior.

Writes desks/mt5/reports/ECONOMIC_PRIOR_BACKFILL.json. Read-only on everything else; changes no
verdict, no certificate and no sleeve.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.research.family_firing import iter_json_array  # noqa: E402
from research.frontier_identity import (  # noqa: E402
    GRANDFATHERED_FAMILIES,
    PRIOR_REGISTRY_PATH,
    economic_prior,
    prior_missing,
)

DOCKET = DESK / "data" / "hypotheses" / "external_survivors.json"
CERTS = DESK / "reports" / "UNIVERSAL_SURVIVORS.json"
SLEEVES = DESK / "data" / "sleeves.json"
OUT = DESK / "reports" / "ECONOMIC_PRIOR_BACKFILL.json"


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _docket_counts(path: Path) -> tuple[Counter[str], Counter[str], str]:
    """Rows per family, and gate-1 verdicts per family, streamed. UNMEASURED when unreadable."""
    rows: Counter[str] = Counter()
    verdicts: Counter[str] = Counter()
    if not path.exists():
        return rows, verdicts, "UNMEASURED"
    try:
        for h in iter_json_array(path):
            if not isinstance(h, dict):
                continue
            fam = str(h.get("family") or "")
            rows[fam] += 1
            stage = economic_prior({"family": fam, "mechanism_status": h.get("mechanism_status"),
                                    "economic_prior": h.get("economic_prior")})
            verdicts[str(stage["verdict"])] += 1
    except (OSError, ValueError):
        return Counter(), Counter(), "UNMEASURED"
    return rows, verdicts, "MEASURED"


def build(docket: Path = DOCKET, certs: Path = CERTS, sleeves: Path = SLEEVES,
          registry: Path = PRIOR_REGISTRY_PATH) -> dict[str, Any]:
    reg_doc = _read_json(registry)
    reg = (reg_doc or {}).get("families") if isinstance(reg_doc, dict) else None
    reg = reg if isinstance(reg, dict) else {}

    d_rows, d_verdicts, d_state = _docket_counts(docket)

    c_doc = _read_json(certs)
    cert_fams: Counter[str] = Counter()
    certs_state = "UNMEASURED"
    if isinstance(c_doc, dict) and isinstance(c_doc.get("survivors"), dict):
        certs_state = "MEASURED"
        for row in c_doc["survivors"].values():
            spec = (row or {}).get("shadow_spec") or {}
            cert_fams[str(spec.get("family") or (row or {}).get("family") or "")] += 1

    s_doc = _read_json(sleeves)
    sleeve_fams: Counter[str] = Counter()
    sleeves_state = "UNMEASURED"
    if isinstance(s_doc, dict) and isinstance(s_doc.get("sleeves"), list):
        sleeves_state = "MEASURED"
        for row in s_doc["sleeves"]:
            if isinstance(row, dict) and row.get("status") != "RETIRED":
                sleeve_fams[str(row.get("family") or "")] += 1

    families = sorted(set(GRANDFATHERED_FAMILIES) | set(reg) | set(d_rows) - {""})
    per_family = []
    status_counts: Counter[str] = Counter()
    for fam in families:
        prior = reg.get(fam) if isinstance(reg.get(fam), dict) else None
        missing = prior_missing(prior)
        status = "COMPLETE" if not missing else ("INCOMPLETE" if prior else "UNMEASURED")
        status_counts[status] += 1
        per_family.append({
            "family": fam, "status": status, "missing": missing,
            "grandfathered": fam in GRANDFATHERED_FAMILIES,
            "docket_rows": d_rows.get(fam, 0), "certificates": cert_fams.get(fam, 0),
            "sleeves_not_retired": sleeve_fams.get(fam, 0),
        })
    # Largest exposure first: the families whose prior would cover the most of the desk.
    per_family.sort(key=lambda r: (r["status"] == "COMPLETE", -r["docket_rows"],
                                   -r["certificates"], r["family"]))
    return {
        "schema": "economic_prior_backfill/1",
        "generated_at": datetime.now(UTC).isoformat(),
        "producer": "desks/mt5/research/economic_prior_backfill.py",
        "rule": ("gate 1 requires the six-field EconomicPrior of a NAMED cell; families on the "
                 "2026-11-18 grandfather roster pass without one (GRANDFATHERED_UNMEASURED) and "
                 "are listed here as backfill debt; any other family without a complete prior "
                 "is recorded PRIOR_INCOMPLETE"),
        "registry": str(registry.relative_to(ROOT)) if registry.is_relative_to(ROOT) else str(registry),
        "grandfathered_families": len(GRANDFATHERED_FAMILIES),
        "family_status": dict(status_counts),
        "docket": {"state": d_state, "rows": sum(d_rows.values()),
                   "gate1_verdicts": dict(d_verdicts)},
        "certificates": {"state": certs_state, "n": sum(cert_fams.values())},
        "sleeves": {"state": sleeves_state, "not_retired": sum(sleeve_fams.values())},
        "families": per_family,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--docket", type=Path, default=DOCKET)
    args = ap.parse_args(argv)
    report = build(docket=args.docket)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    tmp = args.out.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(report, indent=1, sort_keys=False) + "\n", encoding="utf-8")
    tmp.replace(args.out)
    print(f"economic_prior_backfill: families {report['family_status']}; docket "
          f"{report['docket']['state']} {report['docket']['rows']} rows, gate-1 verdicts "
          f"{report['docket']['gate1_verdicts']}; certificates {report['certificates']['n']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
