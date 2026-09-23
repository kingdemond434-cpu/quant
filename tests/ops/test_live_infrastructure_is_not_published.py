"""NO LIVE BROKERAGE OR HOST IDENTIFIER LANDS IN A TRACKED FILE.

An external review on 2026-09-11 pointed out that this repository publishes, in plain text, a
broker name, a live account login, the account equity and leverage, a production host IP, the SSH
user and repo path, and the exact filenames the secret loader expects. It found no credentials --
`check_credentials.py` and the redaction layer do their job -- and was right that credentials are
not the issue. Account number + broker + equity + host + path + expected secret filenames is a
TARGETING KIT: enough for a credible approach to the broker's support desk, and enough that anyone
scanning a hosting provider's ranges knows what is behind that address and what file to look for.

WHAT THE REVIEW GOT WRONG, AND WHY IT STILL MATTERS. Every identifier it named is RETIRED. The
account it found (Vantage 34049153) was replaced by Fusion 495044; the host it found
(95.216.191.70, Hetzner) was replaced by 62.171.172.249. So the published kit points at
decommissioned infrastructure and the finding is far less urgent than it reads -- but the reason
it points at dead infrastructure is that the desk MIGRATED, not that a gate stopped it. The live
identifiers would land the same way, and two of them already had. That is the defect: the desk's
protection against publishing its own live identity was that its identity kept changing.

SCOPE, deliberately narrow. This fences IDENTIFIERS OF LIVE INFRASTRUCTURE, not secrets (that is
`check_credentials.py`) and not the historical record: retired identifiers stay listed here so
that reintroducing one is also caught, and so a reader can see what was already published rather
than discovering it in a review. Scrubbing them from git HISTORY is a separate, destructive
operation (`git filter-repo`) that only the principal may authorise.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

#: Identifiers that must never appear in a tracked file. Retired entries stay so that a rollback,
#: a restored backup or a copied doc cannot quietly republish them.
#: LIVE identifiers: zero tolerance. Nothing that names the account or host currently carrying
#: risk may be committed, and there is no ratchet here -- a new one is a defect, not a debt.
LIVE: dict[str, str] = {
    "495044": "LIVE brokerage login (Fusion)",
    "62.171.172.249": "LIVE trading box (Contabo) public IP",
}

#: RETIRED identifiers: a DOWNWARD RATCHET, not a hard bar. These are already published, and in
#: git history besides -- deleting them from working files does not unpublish them, so failing the
#: suite until ~20 dead scratch scripts are edited would buy no security at all and would buy it
#: by blocking the work that does. What it CAN do is guarantee the number never grows, so a doc
#: copied forward or a scratch script revived cannot quietly re-spread them. Removing them from
#: history is `git filter-repo` and only the principal may authorise it.
RETIRED: dict[str, str] = {
    "95.216.191.70": "retired research VPS (Hetzner) public IP",
    "34049153": "retired live brokerage login (Vantage)",
}

FORBIDDEN: dict[str, str] = {**LIVE, **RETIRED}

#: Tracked files carrying a retired identifier, measured 2026-09-11. MAY ONLY GO DOWN.
MAX_RETIRED_SITES = 46

#: Files that legitimately carry a live identifier and cannot simply drop it, each with the reason
#: and the plan. AN ENTRY HERE IS A DEBT, NOT A PARDON: it is the list a reader checks first.
#:
#: The account number in these two is written by the desk's own organs from what the broker
#: reports -- `live_ledger.jsonl` stamps each fill with the account it was filled on (that is the
#: whole point of the stamp: it is what proves a ledger belongs to THIS account and not another),
#: and `broker_info.json` is the registry snapshot. Removing the stamp would break the ledger's
#: provenance check, which is a real safety property. The right fix is that these paths stop being
#: tracked at all, which is a state-path change and is queued rather than done here.
ALLOWED: dict[str, str] = {
    "desks/mt5/data/live_ledger.jsonl":
        "per-fill account stamp; removing it breaks ledger provenance. Untrack this path.",
    "desks/mt5/data/universe/broker_info.json":
        "broker registry snapshot written by the desk. Untrack this path.",
}


def _tracked() -> list[str]:
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True)
    return [ln.strip() for ln in out.stdout.splitlines() if ln.strip()]


def _hits(needle: str) -> list[str]:
    """Tracked files containing `needle`, via git grep so untracked scratch is never scanned."""
    out = subprocess.run(["git", "grep", "-l", "-F", needle], cwd=ROOT,
                         capture_output=True, text=True)
    # rc 1 means "no matches", which is the passing case and not an error.
    #
    # THIS FILE IS EXCLUDED FROM ITS OWN SCAN. A fence has to name what it forbids, so the
    # identifiers appear here by construction; without this the gate fails on itself the moment it
    # is committed, and the obvious "fix" is to delete the gate. Nothing else is excluded.
    me = Path(__file__).resolve().relative_to(ROOT).as_posix()
    return [q for q in (ln.strip().replace("\\", "/") for ln in out.stdout.splitlines())
            if q and q != me]


def _offenders(table: dict[str, str]) -> list[str]:
    out: list[str] = []
    for needle, what in table.items():
        for path in _hits(needle):
            if path in ALLOWED:
                continue
            out.append(f"{path}: contains {what}")
    return sorted(out)


def test_no_LIVE_infrastructure_identifier_is_tracked() -> None:
    """The account and host currently carrying risk. No ratchet and no grace period."""
    offenders = _offenders(LIVE)
    assert not offenders, (
        "a LIVE infrastructure identifier is committed to a tracked file. Move it to a gitignored "
        "config or an environment variable read at runtime; if the file genuinely cannot drop it, "
        "add it to ALLOWED with the reason and the plan to untrack it.\n  "
        + "\n  ".join(offenders))


def test_retired_identifier_sites_only_ever_decrease() -> None:
    """Already published, so the bar is that the spread STOPS -- not that it is undone today."""
    offenders = _offenders(RETIRED)
    assert len(offenders) <= MAX_RETIRED_SITES, (
        f"{len(offenders)} tracked files carry a retired identifier, up from "
        f"{MAX_RETIRED_SITES}. These name dead infrastructure, but they are still a map of how "
        f"this desk is built and must not spread further.\n  " + "\n  ".join(offenders))


def test_the_allowlist_only_holds_files_that_still_exist() -> None:
    """An allowlist entry for a deleted file hides the next file that takes its name."""
    tracked = set(_tracked())
    stale = [p for p in ALLOWED if p not in {t.replace("\\", "/") for t in tracked}]
    assert not stale, (
        f"ALLOWED names files that are no longer tracked: {stale}. Remove the entries -- an "
        f"allowlist that outlives its file is a hole waiting for a namesake.")


def test_the_allowlist_entries_actually_still_need_the_exemption() -> None:
    """When a debt is paid the entry must go, or the list stops meaning anything."""
    unneeded = []
    for path in ALLOWED:
        text = (ROOT / path).read_text(encoding="utf-8", errors="replace")
        if not any(n in text for n in FORBIDDEN):
            unneeded.append(path)
    assert not unneeded, (
        f"these files no longer contain a forbidden identifier and their exemption is stale: "
        f"{unneeded}. Delete the ALLOWED entries.")
