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
