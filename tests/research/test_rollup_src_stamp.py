"""disk_guard stamps every rollup line and never re-appends one (Audit ruling C, 5a7ba77eb).

The committed legacy rollups carry double appends: an unlink failure aborted the day and the
next pass re-appended the whole day batch. Ruling C: ship that over-count (more trials is the
strict side) and never subtract it. From now on each line is {"src", "i", "sha", "doc"}, a row
already present is skipped, and the trial ledger dedupes on (seat, src, row, sha) ONLY for
stamped lines. Unstamped lines stay charged exactly as before; the suspected legacy re-appends
are published as their own field and never leave lifetime_trials.
"""
from __future__ import annotations

import gzip
import json
from pathlib import Path

from libs.research import experiment_ledger as el
from scripts import disk_guard

#: Measured at 62da6a5798 (the HOLD-fixed head) on the committed artifacts of this tree.
HEAD_LIFETIME_TRIALS = 257_865
HEAD_PROPOSER_TRIALS = 234_849


def _doc(n, fam, stamp):
    return {"tests_run": n, "generated_at": stamp,
            "discoveries": [{"family": fam, "symbol": "EURUSD"}]}


def _seat(tmp_path, name="seat"):
    seat = tmp_path / "data" / "intelligence" / name
    seat.mkdir(parents=True)
    return seat


def _lines(roll: Path) -> list[dict]:
    with gzip.open(roll, "rt", encoding="utf-8") as fh:
        return [json.loads(ln) for ln in fh]


def test_every_rolled_line_is_stamped(tmp_path):
    seat = _seat(tmp_path)
    docs = [_doc(4, "carry", "a"), [_doc(6, "carry", "b"), {"url": "u"}]]
    for i, d in enumerate(docs):
        (seat / f"discoveries_20261001_{i}.json").write_text(json.dumps(d), "utf-8")
    actions: list[str] = []
    disk_guard.rollup(seat, "20261101", actions)
    rows = _lines(seat / "rollup_20261001.jsonl.gz")
    assert [list(r) for r in rows] == [["src", "i", "sha", "doc"]] * 3
    assert [(r["src"], r["i"]) for r in rows] == [("discoveries_20261001_0", 0),
                                                  ("discoveries_20261001_1", 0),
                                                  ("discoveries_20261001_1", 1)]
    for r in rows:
        assert r["sha"] == el._doc_key(r["doc"]) == disk_guard._canonical_sha(r["doc"])
    assert not list(seat.glob("discoveries_*.json"))


def test_an_unlink_retry_never_re_appends(tmp_path, monkeypatch):
    seat = _seat(tmp_path)
    for i in range(2):
        (seat / f"discoveries_20261002_{i}.json").write_text(
            json.dumps(_doc(5 + i, "carry", str(i))), "utf-8")
    real_unlink = Path.unlink

    def failing_unlink(self, *a, **k):
        if self.name.startswith("discoveries_"):
            raise PermissionError("held open")
        return real_unlink(self, *a, **k)

    monkeypatch.setattr(Path, "unlink", failing_unlink)
    actions: list[str] = []
    disk_guard.rollup(seat, "20261101", actions)
    assert any("unlink failed" in a for a in actions)
    assert len(_lines(seat / "rollup_20261002.jsonl.gz")) == 2
    disk_guard.rollup(seat, "20261101", actions)              # the retry, still failing
    assert len(_lines(seat / "rollup_20261002.jsonl.gz")) == 2
    monkeypatch.setattr(Path, "unlink", real_unlink)
    disk_guard.rollup(seat, "20261101", actions)              # the retry that succeeds
    rows = _lines(seat / "rollup_20261002.jsonl.gz")
    assert len(rows) == 2 and not list(seat.glob("discoveries_*.json"))
    assert any("already present, not re-appended" in a for a in actions)


def test_identical_rows_of_one_file_are_both_rolled_and_both_charged(tmp_path, monkeypatch):
    monkeypatch.setattr(el, "DESK", tmp_path)
    seat = _seat(tmp_path)
    c = {"kind": "trial_charge", "tests_run": 3}
    (seat / "discoveries_20261003_0.json").write_text(json.dumps([c, c]), "utf-8")
    (seat / "discoveries_20261003_1.json").write_text(json.dumps(c), "utf-8")
    assert el._proposer_counts()[0] == 9
    disk_guard.rollup(seat, "20261101", [])
    assert len(_lines(seat / "rollup_20261003.jsonl.gz")) == 3
    assert el._proposer_counts()[0] == 9


def test_the_reader_dedupes_stamped_lines_only(tmp_path, monkeypatch):
    monkeypatch.setattr(el, "DESK", tmp_path)
    seat = _seat(tmp_path)
    d = _doc(7, "formula", "x")
    stamped = {"src": "discoveries_20261004_0", "i": 0, "sha": el._doc_key(d), "doc": d}
    with gzip.open(seat / "rollup_20261004.jsonl.gz", "at", encoding="utf-8") as out:
        out.write(json.dumps(stamped, separators=(",", ":")) + "\n")
        out.write(json.dumps(stamped, separators=(",", ":")) + "\n")   # a re-append
        out.write(json.dumps(d) + "\n")                                # legacy line: counted
        out.write(json.dumps(d) + "\n")                                # legacy line: counted
    stats: dict = {}
    assert el._proposer_counts(stats) == (21, {"formula": 21})
    assert stats["stamped_documents"] == 1
    assert stats["stamped_duplicates_skipped"] == 1
    # a different src with the same body is a different charge
    other = dict(stamped, src="discoveries_20261004_1")
    with gzip.open(seat / "rollup_20261004.jsonl.gz", "at", encoding="utf-8") as out:
        out.write(json.dumps(other, separators=(",", ":")) + "\n")
    assert el._proposer_counts()[0] == 28


def test_a_stamped_line_still_cancels_against_its_live_file(tmp_path, monkeypatch):
    monkeypatch.setattr(el, "DESK", tmp_path)
    seat = _seat(tmp_path)
    d = _doc(8, "carry", "y")
    (seat / "discoveries_20261005_0.json").write_text(json.dumps(d), "utf-8")
    line = {"src": "discoveries_20261005_0", "i": 0, "sha": el._doc_key(d), "doc": d}
    with gzip.open(seat / "rollup_20261005.jsonl.gz", "at", encoding="utf-8") as out:
        out.write(json.dumps(line, separators=(",", ":")) + "\n")
    assert el._proposer_counts()[0] == 8


def test_legacy_lines_stay_counted_and_reappends_are_reported_not_subtracted(tmp_path,
                                                                              monkeypatch):
    monkeypatch.setattr(el, "DESK", tmp_path / "desks" / "mt5")
    seat = _seat(tmp_path / "desks" / "mt5", "survivor_distiller")
    batch = [json.dumps(_doc(n, "carry", str(n)), separators=(",", ":")) + "\n"
             for n in (10, 20, 30)]
    with gzip.open(seat / "rollup_20260907.jsonl.gz", "at", encoding="utf-8") as out:
        out.writelines(batch + batch)                       # the whole day batch, twice
    stats: dict = {}
    total, _ = el._proposer_counts(stats)
    assert total == 120                                     # every legacy line charged
    rep = stats["legacy_suspected_reappends"]
    assert rep["documents"] == 3 and rep["tests_run"] == 60 and rep["subtracted"] is False
    assert rep["by_seat"]["survivor_distiller"]["documents"] == 3
    assert rep["by_seat"]["survivor_distiller"]["tests_run"] == 60
    doc = el.lifetime(write=False)
    assert doc["screened_cells"] >= 120
    published = doc["proposer_sources"]["legacy_rollup_suspected_reappends"]
    assert published["tests_run"] == 60 and published["subtracted"] is False


def test_a_non_repeating_legacy_archive_reports_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(el, "DESK", tmp_path)
    seat = _seat(tmp_path)
    with gzip.open(seat / "rollup_20261006.jsonl.gz", "at", encoding="utf-8") as out:
        for n in (1, 2, 3):
            out.write(json.dumps(_doc(n, "carry", str(n))) + "\n")
    stats: dict = {}
    assert el._proposer_counts(stats)[0] == 6
    assert stats["legacy_suspected_reappends"]["documents"] == 0


def test_lifetime_never_falls_below_head_on_the_committed_rollups():
    stats: dict = {}
    proposer, _ = el._proposer_counts(stats)
    assert proposer >= HEAD_PROPOSER_TRIALS
    assert stats["stamped_duplicates_skipped"] == 0         # nothing committed is stamped yet
    doc = el.lifetime(write=False)
    assert doc["lifetime_trials"] >= HEAD_LIFETIME_TRIALS
    assert doc["lifetime_trials"] == (doc["judged_cells"] + doc["screened_cells"]
                                      + doc["source_selection_trials"])
    rep = doc["proposer_sources"]["legacy_rollup_suspected_reappends"]
    assert rep["subtracted"] is False
    assert rep["documents"] > 0 and rep["tests_run"] > 0
