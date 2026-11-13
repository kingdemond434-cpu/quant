"""The campaign lockbox cut the gauntlet LAST USED, published for organs that screen before it.

WHY (Auditor HOLD on #1146, 2026-11-13). A discovery organ that screens history and then donates
what it found to the Judge must never have read the Judge's held-out tail: otherwise the lockbox
gate judges a cell on the very period that selected it. A cell's own dates do not say where that
tail starts -- `gate_policy.lockbox_cut` is taken on the UNION calendar of the whole sweep, so a
late-starting M1 cell sitting under long H1 histories has a campaign cut far earlier than any cut
derived from its own dates.

WHERE THE CUT IS READ. The sealed evaluator (`scripts/external_gauntlet.py`, never edited here)
writes `reports/universal_gates_external.json` after every sweep. That report carries the cut it
used in two places, both read: a top-level / `report` `lockbox_cut` (the sharded path), and every
verdict's `stages.lockbox.cut` with `cut_basis == "campaign"` (the unsharded path). The EARLIEST
campaign cut found is used, because an earlier cut can only withhold more. `publish()` writes what
was read to `reports/LOCKBOX_CUT.json` so the organs' readers and an auditor see one number.

FAILS CLOSED. No readable report, or no campaign cut in it, returns None, and every caller must
then screen NOTHING (the organs report UNMEASURED) -- never "no cut, therefore everything".
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

DESK = Path(__file__).resolve().parents[1]
GAUNTLET_REPORT = DESK / "reports" / "universal_gates_external.json"
PUBLISHED = DESK / "reports" / "LOCKBOX_CUT.json"


def _ts(v: Any) -> pd.Timestamp | None:
    if v in (None, "", "None", "NaT"):
        return None
    try:
        t = pd.Timestamp(str(v))
    except (TypeError, ValueError):
        return None
    if pd.isna(t):
        return None
    return t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")


def read_gauntlet_cut(path: Path | None = None) -> tuple[pd.Timestamp | None, dict[str, Any]]:
    """(earliest campaign cut, provenance). None when the report holds no campaign cut."""
    p = path or GAUNTLET_REPORT
    prov: dict[str, Any] = {"source": str(p)}
    try:
        doc = json.loads(p.read_text("utf-8"))
    except (OSError, ValueError) as exc:
        prov["error"] = type(exc).__name__
        return None, prov
    found: list[pd.Timestamp] = []
    for holder in (doc, doc.get("report") if isinstance(doc.get("report"), dict) else {}):
        t = _ts((holder or {}).get("lockbox_cut"))
        if t is not None:
            found.append(t)
    n_v = 0
    for v in doc.get("verdicts") or []:
        lb = ((v or {}).get("stages") or {}).get("lockbox") if isinstance(v, dict) else None
        if isinstance(lb, dict) and str(lb.get("cut_basis") or "") == "campaign":
            t = _ts(lb.get("cut"))
            if t is not None:
                found.append(t)
                n_v += 1
    prov.update(verdicts_with_campaign_cut=n_v, swept_at=doc.get("swept_at"))
    return (min(found) if found else None), prov


def publish(path: Path | None = None, out: Path | None = None) -> dict[str, Any]:
    cut, prov = read_gauntlet_cut(path)
    doc = {"generated_utc": datetime.now(UTC).isoformat(),
           "campaign_cut": None if cut is None else cut.isoformat(),
           "state": "MEASURED" if cut is not None else
                    "UNMEASURED: the gauntlet's last report holds no campaign lockbox cut",
           **prov}
    o = out or PUBLISHED
    try:
        o.parent.mkdir(parents=True, exist_ok=True)
        o.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    except OSError as exc:
        doc["write_error"] = type(exc).__name__
    return doc


def campaign_cut(path: Path | None = None, *, publish_to: Path | None = None
                 ) -> pd.Timestamp | None:
    """The cut to screen before (UTC), or None -- the caller then screens nothing."""
    doc = publish(path, publish_to) if publish_to is not None else None
    if doc is not None:
        return _ts(doc.get("campaign_cut"))
    return read_gauntlet_cut(path)[0]


def screen_end(own: pd.Timestamp | None, campaign: pd.Timestamp | None) -> pd.Timestamp | None:
    """min(own, campaign), None when the campaign cut is unknown (fail closed)."""
    if campaign is None:
        return None
    if own is None:
        return campaign
    o = own.tz_localize("UTC") if own.tzinfo is None else own.tz_convert("UTC")
    return min(o, campaign)
