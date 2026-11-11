"""The cert book's door: a principal order that releases a pin removes it, through an organ.

`data/CERT_BOOK_LIVE.json` lays fixed fractions over the allocator's book per venue (fusion, e8),
and its own rule says a key NOT named in a venue block keeps the allocator's fraction. Its zeros
are pins: "send nothing on this window". Until now the only way a pin left the book was a hand
edit on the box, which is exactly what the desk's state law forbids (fix the organ, never the
ledger).

WHAT THIS DOES, AND ALL IT DOES. For each RELEASE below whose principal journal row exists in
`context/decision_journal.jsonl`, it removes the named keys from the named venue blocks when --
and only when -- they are pinned at exactly 0.0. A positive fraction is never touched (that is a
size, not a pin), no number is ever written, and a key that is already absent is already
released. The window is then sized like every other sleeve: the allocator's earned fraction,
bounded by the survival envelope and the per-trade rails, which this file does not touch.

FAIL CLOSED, EVERY WAY. A missing or unreadable journal, book, or release row changes nothing.
The book's `enabled: false` changes nothing. The revert switch `data/GOLD_ASIA_ONLY_ENABLED`
(the principal's switch that folds the gold-asia-only pin back in) changes nothing. Every write
keeps a timestamped backup under `reports/cert_book_door_backups/` (never beside the book
in data/), appends a `released_by` note to the venue's `<venue>_by` prose, and records what it
removed -- and what it could NOT release (E8, NEEDS_SIZE) -- in `reports/CERT_BOOK_DOOR.json`.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parent.parent
BOOK = BASE / "data" / "CERT_BOOK_LIVE.json"
JOURNAL = ROOT / "context" / "decision_journal.jsonl"
REPORT = BASE / "reports" / "CERT_BOOK_DOOR.json"
REVERT_SWITCH = BASE / "data" / "GOLD_ASIA_ONLY_ENABLED"
#: Backups live with the report, never beside the book in data/ (#956 audit S1).
BACKUPS = BASE / "reports" / "cert_book_door_backups"

#: The principal orders that release pins, by journal row, and exactly which pins each releases.
#: zuck 2026-11-05 "all accounts trade everything", journalled by #954 (Max-growth; #953
#: re-ided), retires the gold-asia-only pin on Fusion and E8.
#:
#: E8 IS NOT RELEASED HERE (#956 audit M1). On E8 an ENABLED cert book is a whitelist
#: (`prop/e8_gold.window_risk`: a window absent from the e8 block "stands aside" at 0), so
#: deleting its zero sends nothing either -- reporting that as RELEASED would be a lie. E8's
#: windows are reported NEEDS_SIZE until e8_gold reads an absent key as "the allocator's
#: fraction" (Max-growth's separate PROTECTED PR).
RELEASES: tuple[dict[str, Any], ...] = (
    {"journal_id": "D-20261111-071", "title_starts": "All accounts trade everything",
     "order": "zuck 2026-11-05: all accounts trade everything (#954)",
     "pins": {"fusion": ("gold_london_am", "gold_afternoon")},
     "needs_size": {"e8": ("gold_london_am", "gold_afternoon")}},
)


def journal_ids(path: Path = JOURNAL) -> dict[str, str] | None:
    """{decision id: title} for the whole journal, or None when it cannot be read."""
    try:
        lines = path.read_text("utf-8").splitlines()
    except OSError:
        return None
    ids: dict[str, str] = {}
    for line in lines:
        try:
            row = json.loads(line) if line.strip() else None
        except ValueError:
            continue
        if isinstance(row, dict) and row.get("id"):
            ids[str(row["id"])] = str(row.get("title") or "")
    return ids


def released(book: dict[str, Any], ids: dict[str, str],
             releases: tuple[dict[str, Any], ...] = RELEASES
             ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """(the book with every released ZERO pin removed, what was removed). Pure. Each venue block
    that lost a pin gets a text-only `released_by` note appended to its `<venue>_by` prose
    (#956 audit S2), so a reader of the book sees why the key is gone."""
    out = json.loads(json.dumps(book))
    removed: list[dict[str, Any]] = []
    for rel in releases:
        # THE ROW MUST BE THE ORDER, not merely an id: journal ids are minted per branch and have
        # collided before, so a row with the right id and another decision's title releases
        # nothing.
        if not ids.get(rel["journal_id"], "").startswith(rel["title_starts"]):
            continue
        for venue, keys in rel["pins"].items():
            block = out.get(venue)
            if not isinstance(block, dict):
                continue
            for key in keys:
                if key in block and isinstance(block[key], (int, float)) and block[key] == 0.0:
                    del block[key]
                    removed.append({"venue": venue, "key": key, "was": 0.0,
                                    "journal_id": rel["journal_id"], "order": rel["order"]})
    for venue in sorted({r["venue"] for r in removed}):
        keys = ", ".join(r["key"] for r in removed if r["venue"] == venue)
        note = (f" | released_by research/cert_book_door.py: removed the 0.0 pin(s) {keys} "
                f"per {removed[0]['journal_id']} ({removed[0]['order']}); the allocator sizes "
                f"them under the survival envelope")
        out[f"{venue}_by"] = str(out.get(f"{venue}_by") or "") + note
    return out, removed


def needs_size(book: dict[str, Any], ids: dict[str, str],
               releases: tuple[dict[str, Any], ...] = RELEASES) -> list[dict[str, Any]]:
    """The pins a principal order released on a venue whose cert book cannot yet be released by
    deletion (E8: an enabled book is a whitelist). Reported, never changed."""
    out: list[dict[str, Any]] = []
    for rel in releases:
        if not ids.get(rel["journal_id"], "").startswith(rel["title_starts"]):
            continue
        for venue, keys in (rel.get("needs_size") or {}).items():
            block = book.get(venue) if isinstance(book.get(venue), dict) else {}
            for key in keys:
                out.append({"venue": venue, "key": key, "pinned": block.get(key),
                            "journal_id": rel["journal_id"],
                            "why": ("an enabled e8 block is a whitelist (prop/e8_gold): deleting "
                                    "the pin would still send nothing; needs e8_gold to read an "
                                    "absent key as the allocator's fraction")})
    return out


def run(book_path: Path = BOOK, journal_path: Path = JOURNAL, report_path: Path = REPORT,
        revert_switch: Path = REVERT_SWITCH, backups: Path = BACKUPS) -> dict[str, Any]:
    now = datetime.now(UTC).isoformat(timespec="seconds")
    doc: dict[str, Any] = {"at": now, "removed": [], "status": "NO_CHANGE"}
    if revert_switch.exists():
        doc.update(status="HELD", why=f"{revert_switch.name} exists: the principal's revert "
                                      "switch holds the gold-asia-only pin")
        return _report(doc, report_path)
    ids = journal_ids(journal_path)
    if ids is None:
        doc.update(status="UNMEASURED", why="journal unreadable; nothing released")
        return _report(doc, report_path)
    try:
        book = json.loads(book_path.read_text("utf-8"))
    except (OSError, ValueError) as exc:
        doc.update(status="UNMEASURED", why=f"cert book unreadable ({type(exc).__name__})")
        return _report(doc, report_path)
    if not isinstance(book, dict) or book.get("enabled") is False:
        doc.update(status="NO_CHANGE", why="cert book disabled or not an object")
        return _report(doc, report_path)
    new, removed = released(book, ids)
    pending = needs_size(book, ids)
    if pending:
        doc.update(needs_size=pending)
        if not removed:
            doc.update(status="NEEDS_SIZE")
    if removed:
        stamp = now.replace(":", "").replace("-", "")
        backups.mkdir(parents=True, exist_ok=True)
        bak = backups / f"{book_path.name}.bak_door_{stamp}"
        bak.write_text(book_path.read_text("utf-8"), encoding="utf-8")
        tmp = book_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(new, indent=1), encoding="utf-8")
        os.replace(tmp, book_path)
        doc.update(status="RELEASED", removed=removed, backup=bak.name)
    return _report(doc, report_path)


def _report(doc: dict[str, Any], report_path: Path) -> dict[str, Any]:
    try:
        prior = json.loads(report_path.read_text("utf-8")) if report_path.exists() else {}
    except (OSError, ValueError):
        prior = {}
    history = list((prior.get("history") or []) if isinstance(prior, dict) else [])
    if doc.get("removed"):
        history.append({"at": doc["at"], "removed": doc["removed"]})
    out = {**doc, "history": history[-200:]}
    try:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(out, indent=1), encoding="utf-8")
    except OSError:
        pass
    return out


def main() -> int:
    doc = run()
    print(f"cert_book_door: {doc['status']}"
          + (f" -- removed {len(doc['removed'])} pin(s)" if doc.get("removed") else "")
          + (f" ({doc['why']})" if doc.get("why") else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
