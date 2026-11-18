"""Every reader walks the shadow ledgers through `forward_ledger`, and the allocator joins by key.

The per-key writer (7b70e945b) fixed what `shadow_forward` WRITES and eight readers. About thirty
more still globbed `ledger_*.json` -- the allocator's forward join and state conditioning among
them -- so a frozen shared legacy file (one several clock keys wrote, its rows carrying no key)
was still read as a sleeve, and a mirror's stale copy beside the clock's own file. These tests
pin the rest of the fix (Auditor rulings on #937): one way to walk the ledgers, the allocator's
gold_asia column read from its own clock by exact key, and no new reader that globs past it.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DESK = ROOT / "desks" / "mt5"
for _p in (str(DESK / "research"), str(DESK), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.research import forward_ledger as fl  # noqa: E402

GOLD = ["XAUUSD.asia", "XAUUSD.asia#rr=1.5", "XAUUSD.asia#rr=2.5"]


def _rows(r: float, day: str = "2026-11-02") -> list[dict]:
    return [{"entry_time": f"{day} 04:00:00", "r_multiple": r, "phase": "forward"}]


def _write(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows), "utf-8")


def _gold_shadow(shadow: Path) -> None:
    """The box after the per-key writer ran: the shared legacy file frozen, each key its own."""
    _write(shadow / "ledger_XAUUSD_asia.json", _rows(9.0))           # shared by all three keys
    fl.freeze_collisions(GOLD, shadow)
    for key, r in zip(GOLD, (2.0, -1.0, 0.5), strict=True):
        _write(fl.writer_path(key, shadow), _rows(r))


# ------------------------------------------------------------------------- the one walk
def test_iter_ledgers_skips_frozen_files_and_labels_are_unique(tmp_path: Path) -> None:
    shadow = tmp_path / "shadow"
    _gold_shadow(shadow)
    _write(shadow / "ledger_EURUSD_london.json", _rows(1.0))
    names = [p.name for p in fl.iter_ledgers(shadow)]
    assert "ledger_XAUUSD_asia.json" not in names                    # frozen: no clock's series
    labels = [fl.label_of(p) for p in fl.iter_ledgers(shadow)]
    assert len(labels) == len(set(labels)) == 4
    assert all(lab.split("_")[0] in ("XAUUSD", "EURUSD") for lab in labels)


def test_a_mirror_without_a_registry_never_serves_a_frozen_copy(tmp_path: Path) -> None:
    shadow, mirror = tmp_path / "shadow", tmp_path / "mirror"
    _gold_shadow(shadow)
    _write(mirror / "ledger_XAUUSD_asia.json", _rows(9.0))           # stale copy, no registry
    names = [p.name for p in fl.iter_ledgers([shadow, mirror])]
    assert "ledger_XAUUSD_asia.json" not in names
    per_dir = [p.name for p in fl.iter_ledgers(mirror, also_frozen=fl.frozen_names([shadow]))]
    assert per_dir == []


def test_also_frozen_refuses_before_any_registry_exists(tmp_path: Path) -> None:
    shadow = tmp_path / "shadow"
    _write(shadow / "ledger_XAUUSD_asia.json", _rows(9.0))
    assert [p.name for p in fl.iter_ledgers(shadow)] == ["ledger_XAUUSD_asia.json"]
    assert list(fl.iter_ledgers(shadow, also_frozen=fl.collisions(GOLD))) == []


# ------------------------------------------------------------------- the allocator's join
def test_gold_asia_reads_its_own_clock_never_a_variant_or_the_frozen_file(
        tmp_path: Path, monkeypatch) -> None:
    from research import portfolio_evidence as pe

    shadow = tmp_path / "shadow"
    _gold_shadow(shadow)
    monkeypatch.setattr(pe, "SHADOW", shadow)
    series = pe.daily_series()
    assert series["gold_asia"] == {"2026-11-02": 2.0}                # XAUUSD.asia's own +2.0
    assert "XAUUSD_asia" not in series                               # the frozen file: unjoined
    status = pe.column_clock_status()
    assert status["gold_asia"]["status"] == "JOINED"
    assert status["gold_asia"]["ledger"] == fl.writer_path("XAUUSD.asia", shadow).name


def test_only_gold_asia_is_mapped_the_other_gold_columns_read_unmeasured(
        tmp_path: Path, monkeypatch) -> None:
    from research import portfolio_evidence as pe

    assert pe.COLUMN_CLOCKS == {"gold_asia": "XAUUSD.asia"}
    shadow = tmp_path / "shadow"
    _write(shadow / "ledger_XAUUSD_asia.json", _rows(9.0))           # unfrozen: one owner only
    monkeypatch.setattr(pe, "SHADOW", shadow)
    series = pe.daily_series()
    assert "gold_london_am" not in series and "gold_afternoon" not in series
    status = pe.column_clock_status()
    assert status["gold_london_am"]["status"] == "UNMEASURED"
    assert status["gold_afternoon"]["status"] == "UNMEASURED"
    assert status["gold_asia"]["status"] == "JOINED"                 # a never-collided base key


def test_a_frozen_gold_file_reads_as_a_named_gap_not_as_gold_asia(
        tmp_path: Path, monkeypatch) -> None:
    from research import portfolio_evidence as pe

    shadow = tmp_path / "shadow"
    _write(shadow / "ledger_XAUUSD_asia.json", _rows(9.0))
    fl.freeze_collisions(GOLD, shadow)                               # frozen, own file not yet
    monkeypatch.setattr(pe, "SHADOW", shadow)
    series = pe.daily_series()
    assert "gold_asia" not in series
    assert pe.column_clock_status()["gold_asia"]["status"] == fl.UNMEASURED_SHARED_LEDGER


def test_the_allocation_artifact_publishes_the_forward_join() -> None:
    src = (DESK / "research" / "pf_allocator.py").read_text("utf-8")
    assert '"forward_join": dict(_FORWARD_JOIN)' in src
    assert "column_clock_status()" in src


# ---------------------------------------------------------------------------- the guard
#: A reader that walks or parses ledger names past `forward_ledger`. A glob is allowed only when
#: the same line filters the frozen registry (the per-key writer's own readers do).
_GLOB = re.compile(r"""glob\([^)]*["']ledger_""")
_PARSE = re.compile(r"""removeprefix\(\s*["']ledger_|\.stem\[len\(\s*["']ledger_["']\)|\[7:-5\]""")


def test_no_reader_globs_or_parses_ledger_names_past_forward_ledger() -> None:
    offenders: list[str] = []
    for base in (DESK, ROOT / "scripts", ROOT / "libs"):
        for path in base.rglob("*.py"):
            rel = path.relative_to(ROOT).as_posix()
            if "/tests/" in f"/{rel}" or path.name == "forward_ledger.py":
                continue
            try:
                text = path.read_text("utf-8", errors="replace")
            except OSError:
                continue
            for i, line in enumerate(text.splitlines(), 1):
                if (_GLOB.search(line) and "frozen" not in line) or _PARSE.search(line):
                    offenders.append(f"{rel}:{i}: {line.strip()}")
    assert not offenders, "walk ledgers with forward_ledger.iter_ledgers:\n" + "\n".join(offenders)
