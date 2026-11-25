"""Lifetime trials survive disk_guard's rollup, and are charged once (audit 2026-10-14).

`scripts/disk_guard.rollup` compacts discovery files older than RETAIN_DAYS into
`rollup_<day>.jsonl.gz` (one contract document per line) and deletes the originals. Reading only
the live files dropped every rolled contract's `tests_run` from the lifetime count.

EVERY OCCURRENCE IS A CHARGE (Audit MF1): distinct charges can be byte-identical (committee
ensembles' `trial_charge` bodies carry no time or nonce), so content is never a dedup key on its
own. Only a true re-read is dropped: the same resolved path reached twice, or a live file whose
own rollup line (same seat directory, same day, same document) was written before its unlink
failed.
"""
from __future__ import annotations

import glob
import gzip
import json
from pathlib import Path

from libs.research import experiment_ledger as el


def _doc(n, fam, stamp):
    return {"tests_run": n, "generated_at": stamp,
            "discoveries": [{"family": fam, "symbol": "EURUSD"}]}


def _seat(tmp_path):
    seat = tmp_path / "data" / "intelligence" / "seat"
    seat.mkdir(parents=True)
    return seat


def test_count_is_unchanged_by_a_rollup(tmp_path, monkeypatch):
    monkeypatch.setattr(el, "DESK", tmp_path)
    seat = _seat(tmp_path)
    docs = [_doc(4, "carry", "2026-10-01T00:00:00Z"), _doc(6, "carry", "2026-10-01T01:00:00Z")]
    for i, d in enumerate(docs):
        (seat / f"discoveries_20261001_{i}.json").write_text(json.dumps(d), "utf-8")
    before = el._proposer_counts()
    assert before == (10, {"carry": 10})
    # exactly what disk_guard.rollup does: one document per line, originals deleted
    with gzip.open(seat / "rollup_20261001.jsonl.gz", "at", encoding="utf-8") as out:
        for i, d in enumerate(docs):
            out.write(json.dumps(d, separators=(",", ":")) + "\n")
            (seat / f"discoveries_20261001_{i}.json").unlink()
    assert el._proposer_counts() == before


def test_a_contract_in_both_a_file_and_a_rollup_is_charged_once(tmp_path, monkeypatch):
    monkeypatch.setattr(el, "DESK", tmp_path)
    seat = _seat(tmp_path)
    d = _doc(7, "formula", "2026-10-02T00:00:00Z")
    (seat / "discoveries_20261002_0.json").write_text(json.dumps(d), "utf-8")  # unlink failed
    with gzip.open(seat / "rollup_20261002.jsonl.gz", "at", encoding="utf-8") as out:
        out.write(json.dumps(d) + "\n")
    assert el._proposer_counts() == (7, {"formula": 7})
    # a second identical line is a second occurrence, matched to no live file: it is charged
    # (an over-count of a re-run append is a tightening; an under-count of a real charge is not)
    with gzip.open(seat / "rollup_20261002.jsonl.gz", "at", encoding="utf-8") as out:
        out.write(json.dumps(d) + "\n")
    assert el._proposer_counts() == (14, {"formula": 14})


def test_distinct_contracts_with_equal_counts_both_count(tmp_path, monkeypatch):
    monkeypatch.setattr(el, "DESK", tmp_path)
    seat = _seat(tmp_path)
    with gzip.open(seat / "rollup_20261003.jsonl.gz", "at", encoding="utf-8") as out:
        out.write(json.dumps(_doc(5, "carry", "2026-10-03T00:00:00Z")) + "\n")
        out.write(json.dumps(_doc(5, "carry", "2026-10-03T01:00:00Z")) + "\n")
        out.write("{torn\n")
    assert el._proposer_counts() == (10, {"carry": 10})


def test_torn_archive_keeps_what_was_readable(tmp_path, monkeypatch):
    monkeypatch.setattr(el, "DESK", tmp_path)
    seat = _seat(tmp_path)
    raw = gzip.compress((json.dumps(_doc(3, "carry", "x")) + "\n").encode() * 50)
    (seat / "rollup_20261004.jsonl.gz").write_bytes(raw[: len(raw) - 8])   # truncated trailer
    stats: dict = {}
    total, _ = el._proposer_counts(stats)
    assert total == 150                       # all 50 lines read before the tear, each a charge
    assert stats["torn_archives"] == ["seat/rollup_20261004"]


def test_a_rolled_learned_seat_is_still_one_max_charge(tmp_path, monkeypatch):
    # the learned miners re-run one grid daily: their files are reconciled by MAX per seat, and a
    # rollup of those files must neither add a second charge nor drop the first
    monkeypatch.setattr(el, "DESK", tmp_path)
    seat = tmp_path / "data" / "intelligence" / "learned_x"
    seat.mkdir(parents=True)
    docs = [_doc(30, "carry", "2026-10-05T00:00:00Z"), _doc(30, "carry", "2026-10-06T00:00:00Z")]
    for i, d in enumerate(docs):
        (seat / f"discoveries_2026100{5 + i}_0.json").write_text(json.dumps(d), "utf-8")
    before = el._proposer_counts()
    assert before == (30, {"carry": 30})
    with gzip.open(seat / "rollup_20261005.jsonl.gz", "at", encoding="utf-8") as out:
        out.write(json.dumps(docs[0], separators=(",", ":")) + "\n")
    (seat / "discoveries_20261005_0.json").unlink()
    assert el._proposer_counts() == before


def test_a_list_file_counts_the_same_before_and_after_its_rollup(tmp_path, monkeypatch):
    # disk_guard writes a list file's elements one per line; elements without tests_run (the
    # scrapers' rows) are never trials, before or after
    monkeypatch.setattr(el, "DESK", tmp_path)
    seat = _seat(tmp_path)
    rows = [{"source": "s", "url": "u1"}, {"source": "s", "url": "u2"}]
    f = seat / "discoveries_20261007_0.json"
    f.write_text(json.dumps(rows), "utf-8")
    before = el._proposer_counts()
    assert before == (0, {})
    with gzip.open(seat / "rollup_20261007.jsonl.gz", "at", encoding="utf-8") as out:
        for r in rows:
            out.write(json.dumps(r, separators=(",", ":")) + "\n")
    f.unlink()
    assert el._proposer_counts() == before


def _charge(k):
    # committee_ensembles' trial charge: no time, no nonce -- identical bodies for equal k
    return {"source": "committee_ensembles", "kind": "trial_charge", "tests_run": k,
            "discoveries": [], "why": "committee looks"}


def test_two_identical_trial_charge_files_both_count(tmp_path, monkeypatch):
    monkeypatch.setattr(el, "DESK", tmp_path)
    seat = _seat(tmp_path)
    for name in ("discoveries_20261010_101_ab12.json", "discoveries_20261010_202_cd34.json"):
        (seat / name).write_text(json.dumps(_charge(9)), "utf-8")
    assert el._proposer_counts() == (18, {"?": 18})
    # and after both are rolled into one archive (two identical lines), still both
    with gzip.open(seat / "rollup_20261010.jsonl.gz", "at", encoding="utf-8") as out:
        for f in sorted(seat.glob("discoveries_*.json")):
            out.write(json.dumps(json.loads(f.read_text("utf-8")), separators=(",", ":")) + "\n")
            f.unlink()
    assert el._proposer_counts() == (18, {"?": 18})


def test_the_same_file_via_both_roots_counts_once(tmp_path, monkeypatch):
    desk = tmp_path / "desks" / "mt5"
    monkeypatch.setattr(el, "DESK", desk)
    real = desk / "data" / "intelligence" / "seat"
    real.mkdir(parents=True)
    (real / "discoveries_20261011_0.json").write_text(json.dumps(_charge(4)), "utf-8")
    with gzip.open(real / "rollup_20261001.jsonl.gz", "at", encoding="utf-8") as out:
        out.write(json.dumps(_charge(5)) + "\n")
    second = tmp_path / "data" / "intelligence"
    second.mkdir(parents=True)
    (second / "seat").symlink_to(real, target_is_directory=True)   # same resolved paths
    stats: dict = {}
    assert el._proposer_counts(stats)[0] == 9
    assert stats["same_path_skipped"] == 2
    # a genuinely distinct file of the same content under the second root is its own charge
    other = second / "other"
    other.mkdir()
    (other / "discoveries_20261011_0.json").write_text(json.dumps(_charge(4)), "utf-8")
    assert el._proposer_counts()[0] == 13


def test_a_live_file_and_its_own_rollup_line_count_once(tmp_path, monkeypatch):
    monkeypatch.setattr(el, "DESK", tmp_path)
    seat = _seat(tmp_path)
    # disk_guard wrote both lines of day 20261012, then the first unlink failed
    a, b = _charge(6), _charge(6)
    (seat / "discoveries_20261012_1_aa.json").write_text(json.dumps(a), "utf-8")
    (seat / "discoveries_20261012_2_bb.json").write_text(json.dumps(b), "utf-8")
    with gzip.open(seat / "rollup_20261012.jsonl.gz", "at", encoding="utf-8") as out:
        out.write(json.dumps(a, separators=(",", ":")) + "\n")
    stats: dict = {}
    # two live files + one rollup line of the same document: the line is one live file's
    # re-read, the other live file is a separate charge -- 2 charges, not 1 and not 3
    assert el._proposer_counts(stats)[0] == 12
    assert stats["rollup_lines_matched_to_live"] == 1
    assert stats["matched_by_rollup"] == {"seat/rollup_20261012": 1}


def test_a_live_file_dated_after_the_rollup_is_not_subtracted(tmp_path, monkeypatch):
    monkeypatch.setattr(el, "DESK", tmp_path)
    seat = _seat(tmp_path)
    with gzip.open(seat / "rollup_20261013.jsonl.gz", "at", encoding="utf-8") as out:
        out.write(json.dumps(_charge(8)) + "\n")
    (seat / "discoveries_20261014_0.json").write_text(json.dumps(_charge(8)), "utf-8")
    stats: dict = {}
    assert el._proposer_counts(stats)[0] == 16
    assert stats["rollup_lines_matched_to_live"] == 0
    # nor is a live file of the same day in a DIFFERENT seat directory
    other = tmp_path / "data" / "intelligence" / "other"
    other.mkdir()
    (other / "discoveries_20261013_0.json").write_text(json.dumps(_charge(8)), "utf-8")
    assert el._proposer_counts()[0] == 24


def _live_only_base(desk):
    """The pre-rollup reader verbatim (a902ed371): live desk-root dict files, learned max."""
    total, learned = 0, {}
    for f in glob.glob(str(desk / "data" / "intelligence" / "*" / "discoveries_*.json")):
        try:
            doc = json.loads(Path(f).read_text("utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(doc, dict) or not isinstance(doc.get("tests_run"), (int, float)):
            continue
        seat = Path(f).parent.name
        if seat.startswith("learned_"):
            learned[seat] = max(learned.get(seat, 0), int(doc["tests_run"]))
            continue
        total += int(doc["tests_run"])
    return total + sum(learned.values())


def test_n_is_never_below_the_live_only_base_on_a_mixed_fixture(tmp_path, monkeypatch):
    desk = tmp_path / "desks" / "mt5"
    monkeypatch.setattr(el, "DESK", desk)
    intel = desk / "data" / "intelligence"
    s, lx = intel / "committee", intel / "learned_x"
    s.mkdir(parents=True)
    lx.mkdir()
    for i in range(3):                                           # identical charges, same day
        (s / f"discoveries_20261015_{i}_r.json").write_text(json.dumps(_charge(5)), "utf-8")
    (s / "discoveries_20261016_0.json").write_text(json.dumps(_doc(7, "carry", "t")), "utf-8")
    (s / "discoveries_20261016_1.json").write_text("{torn", "utf-8")
    (s / "discoveries_20261016_2.json").write_text(json.dumps([_charge(2), {"url": "u"}]), "utf-8")
    with gzip.open(s / "rollup_20261015.jsonl.gz", "at", encoding="utf-8") as out:
        for _ in range(5):                                       # more lines than live files
            out.write(json.dumps(_charge(5)) + "\n")
    with gzip.open(s / "rollup_20261001.jsonl.gz", "at", encoding="utf-8") as out:
        out.write(json.dumps(_doc(11, "formula", "old")) + "\n")
    for d, n in (("20261015", 30), ("20261016", 40)):
        (lx / f"discoveries_{d}_0.json").write_text(json.dumps(_doc(n, "carry", d)), "utf-8")
    with gzip.open(lx / "rollup_20261001.jsonl.gz", "at", encoding="utf-8") as out:
        out.write(json.dumps(_doc(55, "carry", "old")) + "\n")
    second = tmp_path / "data" / "intelligence" / "committee"
    second.mkdir(parents=True)
    (second / "discoveries_20261015_9_z.json").write_text(json.dumps(_charge(5)), "utf-8")
    base = _live_only_base(desk)
    total, _ = el._proposer_counts()
    assert base == 15 + 7 + 40
    # live 15 + 7 + 2 (list element) + rollup_20261015 (5 lines - 3 matched = 2 x 5) + 11
    # + learned max(30, 40, 55) + second root 5
    assert total == 15 + 7 + 2 + 10 + 11 + 55 + 5
    assert total >= base
