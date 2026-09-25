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

Unreadable or absent reads as NOTHING BANNED for a family the DATA bans -- a missing file must
never silence a family. It reads as STILL BANNED for `PERMANENT`, below.

REFUSAL IS AT THE WRITE DOOR, NOT IN A SWEEP (principal 2026-09-22/23: "Discovered is banned now
btw remember permanently banned and all discovery certificates are discarded n removed ... N
clocks of discovery"). `refuse_if_banned` RAISES, and the doors that call it are the doors that
mint the three things a banned family must never own again:

  - a CLOCK    -- `sleeve_registry.freeze()` (the canonical clock store) and the enrolment loop in
                  `shadow_forward` (the shadow clock stores);
  - a CANDIDATE-- `miner_candidate_compiler` (the docket);
  - a CERTIFICATE -- `external_gauntlet` sets banned specs aside before it judges them.

A sweep that cleans up afterwards is not enforcement: between two sweeps the row exists, organs
downstream read it, and the desk measured 23 banned clocks that every organ agreed should never
have been created. The door is the only place where "never created" is a fact.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

BANNED_FAMILIES_FILE = Path(__file__).resolve().parents[1] / "data" / "banned_families.json"

#: BANS THAT NO EDIT LIFTS. `banned_families.json` is data, and data can be deleted, corrupted or
#: overwritten by any writer on either box -- and `banned_families()` reads an unreadable file as
#: NOTHING BANNED, which is the right answer for a family the data bans and the wrong one for a
#: family the principal banned permanently. `discovered` is permanent: "Discovered is banned now
#: btw remember permanently banned and all discovery certificates are discarded n removed"
#: (2026-09-22), after 85 live closes across 24 sleeves at mean -0.24R, pooled t=-5.2, the whole
#: forex loss on the account. Lifting it is the principal's act, in code, with the reason recorded
#: -- never a file that went missing. `certificate_truth.DISCOVERED` carries the same constant for
#: the same reason; `test_family_policy` pins that the two agree.
PERMANENT: dict[str, dict[str, Any]] = {
    "discovered": {
        "since": "2026-09-16",
        "permanent_since": "2026-09-22",
        "by": "principal",
        "permanent": True,
        "why": ("permanently banned by the principal: certificate discovery itself is banned and "
                "every discovery certificate, clock and candidate is discarded. 85 live closes "
                "across 24 sleeves at mean -0.24R, pooled t=-5.2, the account's whole forex loss. "
                "No later organ may re-admit it and no edit to banned_families.json lifts it."),
    },
}


class BannedFamilyRefused(RuntimeError):
    """A write door was asked to create a clock, certificate or candidate of a banned family.

    Raised, never returned: a caller that ignores a return value creates the row anyway, and the
    whole point of a write door is that there is no path past it.
    """

    def __init__(self, family: str, what: str, key: str, reason: str) -> None:
        self.family, self.what, self.key = family, what, key
        super().__init__(f"refused to create {what} {key!r}: {reason}")


def banned_families(path: Path | None = None) -> dict[str, dict[str, Any]]:
    """{family: {since, by, why}} -- the permanent bans ALWAYS, plus whatever the file records.

    The permanent entries are merged first and win on a key collision, so a file that renames,
    softens or drops `discovered` changes nothing about it.
    """
    out: dict[str, dict[str, Any]] = {k: dict(v) for k, v in PERMANENT.items()}
    p = path or BANNED_FAMILIES_FILE
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return out
    raw = doc.get("banned") if isinstance(doc, dict) else None
    if not isinstance(raw, dict):
        return out
    for k, v in raw.items():
        if str(k).strip().lower() in PERMANENT:
            continue
        out[str(k)] = v if isinstance(v, dict) else {"why": str(v)}
    return out


def family_banned(family: object, path: Path | None = None) -> bool:
    """True when `family` is on the ban list. Case-insensitive on the family name."""
    fam = str(family or "").strip().lower()
    return bool(fam) and fam in {k.lower() for k in banned_families(path)}


def family_permanently_banned(family: object) -> bool:
    """True when the ban is the principal's permanent one, which no data edit can lift."""
    return str(family or "").strip().lower() in PERMANENT


def ban_reason(family: object, path: Path | None = None) -> str:
    fam = str(family or "").strip().lower()
    for k, v in banned_families(path).items():
        if k.lower() == fam:
            since = str(v.get("since") or "")
            by = str(v.get("by") or "")
            why = str(v.get("why") or "")
            perm = " PERMANENTLY" if v.get("permanent") else ""
            return f"family {k!r}{perm} banned{' since ' + since if since else ''}" \
                   f"{' by ' + by if by else ''}{': ' + why if why else ''}"
    return ""


def refuse_if_banned(family: object, *, what: str, key: object = "",
                     path: Path | None = None) -> None:
    """THE WRITE DOOR. Raise `BannedFamilyRefused` when `family` may not own a `what`.

    `what` names the thing the caller is about to create -- "clock", "certificate", "candidate" --
    and `key` the row it would be created under, so the refusal reads as an account of what did
    not happen rather than a bare exception. A family that is not banned returns None and the
    caller proceeds exactly as before: this adds no condition to anything else.
    """
    fam = str(family or "").strip().lower()
    if not fam or not family_banned(fam, path):
        return
    raise BannedFamilyRefused(fam, what, str(key), ban_reason(fam, path))
