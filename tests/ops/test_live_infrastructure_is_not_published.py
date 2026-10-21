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

import re
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
MAX_RETIRED_SITES = 44

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
    "desks/mt5/data/universe/broker_info.json":
        "broker registry snapshot written by the desk. Untrack this path.",
    # Box-written state: editing the committed copy on origin is reverted by the box's next push
    # (libs/ops/release.py STATE_PREFIXES), so the WRITER was fixed instead and the stale copy
    # clears itself. Delete each entry once the box has rewritten the file -- the
    # stale-exemption test below fails until you do.
    "desks/mt5/data/cost_truth_quotes.json":
        "box-written state; writer fixed in desks/mt5/research/cost_truth.py, and since v5g "
        "the publisher withholds the login on the next sync (libs/ops/account_withhold.py)",
}


#: THE TWO LEDGERS ARE NO LONGER WHOLE-FILE DEBTS (2026-10-20). Their writers stamp a hashed
#: `account_key` (mt5desk/provenance.py, gateway `_record_intent`) and every reader hashes a
#: legacy row on read, so from the first `account_key` row onward these files are fenced like any
#: other: a live identifier in a row after the cutover fails `test_no_LIVE_...` below.
#:
#: The rows BEFORE the cutover keep the raw login, deliberately. They cannot be rewritten in place:
#: `live_ledger.jsonl`'s prefix is sealed in IMMUTABLE_MANIFEST.json and every audited reader
#: (libs/ops/live_ledger_view.py) raises on a changed prefix -- which would stop the promoter, the
#: allocator and k_eff, i.e. the money path -- and the gateway appends to both files while it runs.
#: Rewriting them buys nothing either: the rows are already on origin and in history, and
#: scrubbing history is `git filter-repo`, the principal's call alone.
#: PINNED, NOT MARKED (audit v5): each exempt prefix is {records, sha256} measured on LIVE, and
#: every row after it is judged; a prefix that changed is judged WHOLE (it fails closed here as it
#: does in the publisher).
#: REMOVAL TRIGGER: `test_the_legacy_prefixes_still_need_the_exemption` fails once a prefix no
#: longer carries a forbidden identifier (history scrubbed and the file restarted). Delete the
#: entry from `libs/ops/login_fence.LEGACY_PIN` then; this fence and the publisher's share it.
from libs.ops import login_fence as _lf  # noqa: E402
from libs.ops.login_fence import LEGACY_PIN  # noqa: E402


def _judged_text(path: str, text: str) -> str:
    """What the fence judges: the whole file, or for a pinned ledger only the rows after its
    pinned prefix -- and the whole file when that prefix no longer hashes to its pin."""
    body, _offset, _changed = _lf._judged(path, text.encode("utf-8"))
    return body.decode("utf-8", errors="replace")


def _legacy_prefix(path: str, text: str) -> str:
    lines = text.splitlines(keepends=True)
    return "".join(lines[:int(LEGACY_PIN[path]["records"])])


def _tracked() -> list[str]:
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True)
    return [ln.strip() for ln in out.stdout.splitlines() if ln.strip()]


def _contains_identifier(text: str, needle: str) -> bool:
    # A measured decimal such as 7.495044 is not an account identifier.
    # Keep integer tokens, quoted identifiers and prose identifiers detectable.
    return re.search(r"(?<![\d.])" + re.escape(needle) + r"(?![\d.])", text) is not None


def test_identifier_matching_preserves_real_identifiers():
    needle = next(iter(LIVE))
    assert _contains_identifier('account ' + needle, needle)
    assert _contains_identifier('"account": ' + needle + ',', needle)
    assert _contains_identifier('"account": "' + needle + '"', needle)
    assert not _contains_identifier('"q99": 7.' + needle, needle)
    assert not _contains_identifier('"sample": 1' + needle + '2', needle)


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
            if q and q != me and _contains_identifier(
                _judged_text(q, (ROOT / q).read_text(encoding="utf-8", errors="replace")),
                needle)]


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
        if not any(_contains_identifier(text, n) for n in FORBIDDEN):
            unneeded.append(path)
    assert not unneeded, (
        f"these files no longer contain a forbidden identifier and their exemption is stale: "
        f"{unneeded}. Delete the ALLOWED entries.")


def test_the_two_ledgers_are_fenced_and_not_whole_file_allowed() -> None:
    for path in LEGACY_PIN:
        assert path not in ALLOWED, f"{path} is a whole-file debt again; it is fenced by rows"
    assert set(LEGACY_PIN) == {"desks/mt5/data/live_ledger.jsonl",
                                  "desks/mt5/data/order_intents.jsonl"}


def test_the_legacy_prefixes_still_need_the_exemption() -> None:
    """The removal trigger. A prefix that no longer carries a forbidden identifier is a paid
    debt: delete its LEGACY_PIN entry so the whole file is fenced."""
    unneeded = []
    for path in LEGACY_PIN:
        full = ROOT / path
        if not full.exists():
            continue
        prefix = _legacy_prefix(path, full.read_text(encoding="utf-8", errors="replace"))
        if not any(_contains_identifier(prefix, n) for n in FORBIDDEN):
            unneeded.append(path)
    assert not unneeded, (
        f"these ledgers' legacy prefixes no longer carry a forbidden identifier: {unneeded}. "
        f"Delete their libs/ops/login_fence.LEGACY_PIN entries.")


def test_a_row_after_the_pinned_prefix_is_judged_and_a_changed_prefix_is_judged_whole() -> None:
    needle = next(iter(LIVE))
    path = "desks/mt5/data/live_ledger.jsonl"
    held = (ROOT / path).read_text(encoding="utf-8")
    pin = LEGACY_PIN[path]
    assert _lf.measure_prefix("".join(held.splitlines(keepends=True)[:pin["records"]]).encode()) \
        == {"records": pin["records"], "sha256": pin["sha256"]}, "the pin is not this prefix"
    new = '{"deal": 2, "account_key": "sha256:0123456789abcdef"}\n'
    old = '{"deal": 1, "account": ' + needle + '}\n'
    assert not _contains_identifier(_judged_text(path, held + new), needle)
    assert _contains_identifier(_judged_text(path, held + new + old), needle)
    # one byte changed inside the prefix: the whole file is judged (and the publisher refuses)
    lines = held.splitlines(keepends=True)
    lines[0] = lines[0].replace("{", "{ ", 1)
    assert _contains_identifier(_judged_text(path, "".join(lines)), needle)
    assert _contains_identifier(_judged_text("desks/mt5/data/other.jsonl", old), needle)
