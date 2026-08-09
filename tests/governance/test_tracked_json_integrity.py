"""Every git-tracked JSON artifact parses; no tracked text file carries conflict markers.

Born 2026-07-31 from a live incident: a merge committed unresolved conflict markers into
docs/research/recommendation_ledger.json and PUSHED them to origin -- and the ledger CLI's
silent-except then read the corrupt file as a healthy EMPTY ledger ("0 total, nothing
overdue"), one `add` away from atomically saving the empty dict over all 174 rows. JSON
corruption is silent by default because most loaders fall back; this fence makes it loud
at commit/CI time instead. Tracked *.json total ~800KB, so parsing all of them is cheap.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_MARKERS = ("<<<<<<< ", ">>>>>>> ")  # '=======' alone is legal prose; these two are not


def _tracked(pattern: str) -> list[Path]:
    out = subprocess.run(["git", "ls-files", pattern], cwd=_ROOT,
                         capture_output=True, text=True, check=True).stdout
    return [_ROOT / line for line in out.splitlines() if line.strip()]


def test_every_tracked_json_parses() -> None:
    bad = []
    for p in _tracked("*.json"):
        try:
            json.loads(p.read_text("utf-8"))
        except Exception as e:
            bad.append(f"{p.relative_to(_ROOT)}: {e}")
    assert not bad, f"unparseable tracked JSON (corrupt commit?): {bad}"


def test_every_tracked_jsonl_parses_per_line() -> None:
    bad = []
    for p in _tracked("*.jsonl"):
        for n, line in enumerate(p.read_text("utf-8").splitlines(), 1):
            if not line.strip():
                continue
            # Full-line '#' comments are the ledger format's own documented convention: the
            # reader that owns it (libs/research/desk_memory.py) skips them in three places, and
            # docs/desk_lessons.jsonl carries its append-only contract as a '#' header. A comment
            # is a deliberate line, not corruption -- markers and broken JSON still fail below.
            if line.lstrip().startswith("#"):
                continue
            try:
                json.loads(line)
            except Exception as e:
                bad.append(f"{p.relative_to(_ROOT)}:{n}: {e}")
                break
    assert not bad, f"unparseable tracked JSONL lines: {bad}"


def test_no_conflict_markers_in_tracked_sources() -> None:
    bad = []
    for pattern in ("*.json", "*.jsonl", "*.py"):
        for p in _tracked(pattern):
            if p == Path(__file__):
                continue
            text = p.read_text("utf-8", errors="ignore")
            for line in text.splitlines():
                if line.startswith(_MARKERS):
                    bad.append(str(p.relative_to(_ROOT)))
                    break
    assert not bad, f"tracked files carrying merge-conflict markers: {bad}"


def test_every_terminal_ledger_row_carries_a_disposition_timestamp() -> None:
    """R0259. A row that reached a verdict must record WHEN, or the verdict is unauditable.

    Same class as the corruption fence above and the same reason it belongs here: the damage is
    silent by construction. `dispose` stamps `disposed`; an organ that opens the JSON and sets
    `status` directly does not, and nothing downstream can tell the two apart -- the row simply
    stops being counted as a disposition. check_conversion measures the queue by differencing
    arrivals against dispositions in a trailing window, so every unstamped row biases that
    verdict toward RUNNING AWAY and manufactures backlog pressure out of work already done.

    Measured 2026-08-05, before the backfill: 35 terminal rows with no timestamp -- and only 15
    of them were the `done`/`screened` vocabulary drift the row was raised about. The other 20
    carried perfectly CLI-legal statuses and still arrived unstamped, all from bulk triage
    workflows writing the file directly. That is the finding: teaching the CLI new words fixes
    the 15 and prevents none of the 20, because the defect is the WRITE PATH, not the vocabulary.
    Making the invariant loud here is what stops it drifting back while that path is unfixed.
    """
    rows = json.loads((_ROOT / "docs/research/recommendation_ledger.json").read_text("utf-8"))
    unstamped = [r["id"] for r in rows["recommendations"]
                 if r.get("status") not in ("open", "scheduled") and not r.get("disposed")]
    assert not unstamped, (
        f"{len(unstamped)} terminal ledger row(s) carry no `disposed` stamp: {unstamped[:12]}. "
        "Dispose through scripts/recommendations.py rather than writing the JSON directly -- an "
        "unstamped verdict is invisible to every rate the conversion fence computes.")
