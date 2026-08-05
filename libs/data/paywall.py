"""PAYWALL ENCOUNTERS -- every paid dataset the desk WALKS INTO gets noted, automatically.

THE GAP THIS CLOSES, and it was found by walking into it. `docs/research/paid_dataset_targets.md`
(charter §42) is a good standing registry of 18 paid vendors, each with a live free-replacement
status, and the standing rule says every digger ADDS any paid dataset it encounters. On 2026-08-05
a collector hit DefiLlama's emissions endpoint, got HTTP 402 Payment Required, wrote the fact into
its own status artifact and a cron comment -- and DefiLlama's paid tier never reached the registry.
The rule was right; nothing mechanical enforced it, so it depended on whoever wrote the collector
remembering. That is the by-hand step that runs at zero when nobody is looking.

So a paywall encounter is now a RECORDED EVENT, appended the moment a fetch is refused for payment,
and a separate fence checks that every vendor in the encounter ledger appears in the registry. The
desk cannot silently accumulate paywalls it forgot to hunt replacements for.

WHAT COUNTS AS A PAYWALL, and why the list is narrow. HTTP 402 is unambiguous. 403 is not -- it is
also a WAF, a bad UA, or a geo block, and recording all of those as paid datasets would fill the
registry with things nobody sells and bury the ones somebody does. So 403 is recorded ONLY with a
corroborating signal in the body or the caller's own declaration, and the distinction is kept in
the row rather than resolved away.

NOTHING HERE BUYS ANYTHING, and nothing here decides to. A licensed vendor feed is the principal's
decision -- the desk's job is to NOTICE the paywall, state what it would unlock, and hunt a free
route (primary-source reconstruction first, since facts are not copyrightable, then
differently-licensed vendors, mirrors, community corpora, regional venues and archives). This
module does the noticing and the recording; the hunt is a dig deliverable and the purchase is not
the desk's call at all.
"""
from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

__all__ = ["LEDGER", "PAYWALL_MARKERS", "classify", "record", "vendors_encountered"]

_ROOT = Path(__file__).resolve().parents[2]

#: Append-only. A paywall the desk walked into and then forgot is the whole failure mode, so the
#: record outlives the run that produced it and is never rewritten.
LEDGER = "data/paywall_encounters.jsonl"

#: Body/text markers that corroborate a 403 as a PAYWALL rather than a bot block. Kept separate
#: from the status code because "you must pay" and "you look like a robot" are different findings
#: and lead to different work -- one is a registry row and a replacement hunt, the other is a
#: routing problem.
PAYWALL_MARKERS: tuple[str, ...] = (
    "payment required", "subscription", "upgrade your plan", "api key required",
    "pro plan", "enterprise plan", "billing", "quota exceeded", "paid tier",
    "requires a paid", "purchase", "pricing",
)


def classify(status: int | None, body: str = "", *, declared: bool = False) -> tuple[str, str]:
    """(verdict, why). PAYWALL / MAYBE-PAYWALL / NOT-A-PAYWALL.

    402 is unambiguous and needs no corroboration. 403 needs a marker or an explicit declaration
    from the caller, because a 403 is far more often a WAF than a price -- and a registry full of
    bot blocks would bury the vendors somebody actually sells.
    """
    low = " ".join(str(body or "").lower().split())[:4000]
    marker = next((m for m in PAYWALL_MARKERS if m in low), "")
    if status == 402:
        return "PAYWALL", "HTTP 402 Payment Required -- unambiguous, the vendor is charging"
    if status == 403 and (marker or declared):
        return "PAYWALL", (f"HTTP 403 corroborated by {marker!r}" if marker
                           else "HTTP 403 declared a paywall by the caller")
    if status == 403:
        return "MAYBE-PAYWALL", ("HTTP 403 with no payment marker -- far more often a WAF, a bad "
                                 "user-agent or a geo block. Recorded as UNRESOLVED rather than "
                                 "filed as a paid dataset: a registry full of bot blocks buries "
                                 "the vendors somebody actually sells")
    if status in (401, 407) or marker:
        return "MAYBE-PAYWALL", (f"status {status} / marker {marker!r} -- may be credentials "
                                 "rather than a price; the two are not the same finding")
    return "NOT-A-PAYWALL", f"status {status} carries no payment signal"


def _vendor(url: str) -> str:
    host = re.sub(r"^https?://", "", str(url or "")).split("/")[0].lower()
    host = re.sub(r"^(www|api|pro)\.", "", host)
    return host or "unknown"


def record(url: str, *, status: int | None, unlocks: str, body: str = "",
           declared: bool = False, root: Path | None = None) -> dict[str, Any]:
    """Append one encounter. Returns the row. Never raises -- a collector must survive this.

    `unlocks` is REQUIRED and is the load-bearing field: "what would the desk be able to measure
    if it had this?" Without it the registry becomes a list of hosts that said no, which nobody can
    prioritise. With it, the free-replacement hunt has a target -- reconstruct THAT, not the vendor.
    """
    base = root or _ROOT
    verdict, why = classify(status, body, declared=declared)
    row = {
        "observed_utc": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "vendor": _vendor(url), "url": str(url)[:300], "status": status,
        "verdict": verdict, "why": why,
        "unlocks": str(unlocks)[:400],
        "free_replacement_status": "UNHUNTED",
        "hunt_order": ("primary-source reconstruction FIRST (facts are not copyrightable), then "
                       "differently-licensed vendors, mirrors, community corpora, regional venues, "
                       "archives -- searched across forums, obscure repos, papers and NON-ENGLISH "
                       "sources"),
        "authority": ("NOTICE AND RECORD ONLY. Buying a licensed feed is the principal's decision, "
                      "never a collector's."),
    }
    try:
        path = base / LEDGER
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError:
        pass                    # a collector must not die because the ledger is unwritable
    return row


def vendors_encountered(root: Path | None = None, *,
                        only_paywalls: bool = True) -> dict[str, dict[str, Any]]:
    """Vendor -> the most recent encounter. Used by the fence that checks the registry lists them.

    MAYBE-PAYWALL rows are excluded by default: demanding a registry entry for every 403 would
    train the desk to add noise to the registry, and a registry nobody trusts is not consulted.
    They stay in the ledger, so a 403 that later turns out to be a price is still on the record.
    """
    base = root or _ROOT
    out: dict[str, dict[str, Any]] = {}
    try:
        text = (base / LEDGER).read_text("utf-8", errors="ignore")
    except OSError:
        return out
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if only_paywalls and row.get("verdict") != "PAYWALL":
            continue
        out[str(row.get("vendor", ""))] = row
    out.pop("", None)
    return out
