"""FAMILIES THE PRINCIPAL HAS BANNED -- one file, read by every producer and consumer.

2026-09-16, the `discovered` family: 85 live closes across 24 sleeves at mean -0.24R, pooled
t=-5.2, the account's whole forex loss, on a mechanism that sells statistical richness and lost
on every trending day. The principal's order: ban the discovery hunt, retire its sleeves, keep
the gold ones, and put every research hour into every other mechanism.

A ban is DATA with a reason (`data/banned_families.json`), never a constant in five files, so
that lifting it is one edit and every organ reads the same answer:

  - `hourly_cycle`'s search leg (edge_search mints only `discovered` hypotheses) stands down;
  - `miner_candidate_compiler` refuses candidates of a banned family, so the docket stops filling;
  - `external_gauntlet` sets banned cells aside, so the hour goes to every other mechanism;
  - `promoter` retires roster rows of a banned family and never promotes a candidate of one;
  - the E8 book and executor exclude it and close what it still holds.

Unreadable or absent reads as NOTHING BANNED: a missing file must never silence a family.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

BANNED_FAMILIES_FILE = Path(__file__).resolve().parents[1] / "data" / "banned_families.json"


def banned_families(path: Path | None = None) -> dict[str, dict[str, Any]]:
    """{family: {since, by, why}} as recorded; {} when the file is absent or unreadable."""
    p = path or BANNED_FAMILIES_FILE
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    raw = doc.get("banned") if isinstance(doc, dict) else None
    if not isinstance(raw, dict):
        return {}
    return {str(k): (v if isinstance(v, dict) else {"why": str(v)}) for k, v in raw.items()}


def family_banned(family: object, path: Path | None = None) -> bool:
    """True when `family` is on the ban list. Case-insensitive on the family name."""
    fam = str(family or "").strip().lower()
    return bool(fam) and fam in {k.lower() for k in banned_families(path)}


def ban_reason(family: object, path: Path | None = None) -> str:
    fam = str(family or "").strip().lower()
    for k, v in banned_families(path).items():
        if k.lower() == fam:
            since = str(v.get("since") or "")
            by = str(v.get("by") or "")
            why = str(v.get("why") or "")
            return f"family {k!r} banned{' since ' + since if since else ''}" \
                   f"{' by ' + by if by else ''}{': ' + why if why else ''}"
    return ""
