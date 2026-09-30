"""THE WALL BEYOND FROZEN CODE, and the isolation of every generator from sealed data (W19).

The evaluator's original fence hashes the files that JUDGE. Two halves of the constitution were
outside it and are pinned here.

THE RECORDS. A ledger cannot be hashed whole -- it grows every hour -- so it is sealed by
PREFIX, and the only property that matters is the one these tests plant a lie against: the
records already written must still be there, unchanged, in the same order. A fence that only
proved "the file is bigger than it was" would pass every rewrite that also appended.

THE GENERATORS. "Sealed data never reaches a generator" is not checkable from an artifact, only
from source, and the precision is the whole point: `expression_factory` imports `LockedHoldout`
to SEAL its own tail and never opens it, which is the correct behaviour and must not be a
finding, while a single `open_lockbox()` in a proposer must be one, with the line number.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import check_immutable_evaluator as M  # noqa: E402


@pytest.fixture
def box(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A fake box: the module's ROOT and MANIFEST repointed into tmp_path, nothing tracked."""
    monkeypatch.setattr(M, "ROOT", tmp_path)
    monkeypatch.setattr(M, "MANIFEST", tmp_path / "manifest.json")
    monkeypatch.setattr(M, "APPEND_ONLY", (
        ("data/live_ledger.jsonl", "lines", "the live ledger"),
        ("reports/shadow/ledger_*.json", "rows", "the forward clocks' ledgers"),
    ))
    monkeypatch.setattr(M, "VINTAGE", (("data/cost_surface.json", "built_at", "the costs"),))
    monkeypatch.setattr(M, "IMMUTABLE", ())
    (tmp_path / "data").mkdir()
    (tmp_path / "reports" / "shadow").mkdir(parents=True)
    return tmp_path


def _seal(box: Path) -> None:
    (box / "manifest.json").write_text(json.dumps({
        "files": {}, "append_only": M.append_only_seal(), "vintage": M.vintage_seal()}), "utf-8")


def _status(path: str) -> dict[str, Any]:
    return next(r for r in M.wall_rows() if r["path"] == path)


def test_an_append_only_ledger_may_grow_and_may_not_be_rewritten(box: Path) -> None:
    led = box / "data" / "live_ledger.jsonl"
    led.write_text("\n".join(f'{{"deal": {i}}}' for i in range(4)), "utf-8")
    _seal(box)
    assert _status("data/live_ledger.jsonl")["status"] == "verified"

    led.write_text(led.read_text("utf-8") + '\n{"deal": 99}', "utf-8")
    grew = _status("data/live_ledger.jsonl")
    assert grew["status"] == "grew" and grew["records"] == 5

    # The lie a "file only got bigger" check would pass: one old record edited, one appended.
    lines = led.read_text("utf-8").split("\n")
    lines[1] = '{"deal": 1, "pl_quote": 999.0}'
    led.write_text("\n".join([*lines, '{"deal": 100}']), "utf-8")
    bad = _status("data/live_ledger.jsonl")
    assert bad["status"] == "breach" and "rewritten" in bad["why"]
    assert any("live_ledger" in f["file"] for f in M.check())


def test_a_shorter_copy_is_behind_but_a_rewritten_prefix_is_still_a_breach(box: Path) -> None:
    led = box / "data" / "live_ledger.jsonl"
    original = [f'{{"deal": {i}}}' for i in range(8)]
    led.write_text("\n".join(original), "utf-8")
    _seal(box)

    # Another host holding an older pull: fewer records, identical as far as it goes.
    led.write_text("\n".join(original[:4]), "utf-8")
    behind = _status("data/live_ledger.jsonl")
    assert behind["status"] == "behind" and behind["records"] == 4
    assert not [f for f in M.check() if "live_ledger" in f["file"]]

    # Shorter AND different where they overlap is the one thing it cannot be.
    led.write_text("\n".join(['{"deal": 0, "pl_quote": -1}', *original[1:4]]), "utf-8")
    assert _status("data/live_ledger.jsonl")["status"] == "breach"


def test_a_forward_clock_ledger_is_read_as_rows_and_its_history_is_sealed(box: Path) -> None:
    led = box / "reports" / "shadow" / "ledger_XAUUSD_asia.json"
    trades = [{"entry_time": f"2026-08-{d:02d}", "r_multiple": 0.1 * d} for d in range(1, 6)]
    led.write_text(json.dumps(trades), "utf-8")
    _seal(box)
    rel = "reports/shadow/ledger_XAUUSD_asia.json"
    assert _status(rel)["status"] == "verified"

    trades[2]["r_multiple"] = 9.9          # a losing forward trade improved after the fact
    trades.append({"entry_time": "2026-08-06", "r_multiple": 0.6})
    led.write_text(json.dumps(trades), "utf-8")
    assert _status(rel)["status"] == "breach"


def test_an_absent_record_file_is_unmeasured_and_never_reads_as_verified(box: Path) -> None:
    _seal(box)                                     # nothing on disk at all
    statuses = {r["path"]: r["status"] for r in M.wall_rows()}
    assert statuses["data/live_ledger.jsonl"] == "absent"
    assert statuses["reports/shadow/ledger_*.json"] == "absent"
    assert "verified" not in set(statuses.values())
    assert all("UNMEASURED" in r["why"] for r in M.wall_rows() if r["status"] == "absent")
    assert not M.check()                           # absence is a verdict, not a breach


def test_the_cost_surface_may_be_rebuilt_and_may_not_be_back_dated(box: Path) -> None:
    surface = box / "data" / "cost_surface.json"
    surface.write_text(json.dumps({"built_at": "2026-09-20T00:00:00+00:00", "symbols": {}}),
                       "utf-8")
    _seal(box)
    assert _status("data/cost_surface.json")["status"] == "verified"

    surface.write_text(json.dumps({"built_at": "2026-09-22T00:00:00+00:00", "symbols": {}}),
                       "utf-8")
    assert _status("data/cost_surface.json")["status"] == "rebuilt"
    assert not M.check()

    surface.write_text(json.dumps({"built_at": "2026-08-01T00:00:00+00:00", "symbols": {}}),
                       "utf-8")
    back = _status("data/cost_surface.json")
    assert back["status"] == "breach" and "BACKWARDS" in back["why"]


# ------------------------------------------------------------------ generator isolation
def _generator(path: Path, body: str, *, doc: str = "") -> None:
    """A file the desk counts as a generator: it imports the donation door."""
    path.parent.mkdir(parents=True, exist_ok=True)
    head = f'"""{doc}"""\n\n' if doc else ""
    path.write_text(head + "from research.proposer_common import donate\n\n" + body, "utf-8")


@pytest.fixture
def desk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(M, "ROOT", tmp_path)
    monkeypatch.setattr(M, "GENERATOR_ROOTS", ("research",))
    monkeypatch.setattr(M, "EXTRA_GENERATORS", ())
    monkeypatch.setattr(M, "JUDGES", frozenset({"research/judge.py"}))
    (tmp_path / "research").mkdir()
    return tmp_path


def test_a_generator_that_opens_a_lockbox_is_caught_with_its_file_and_line(desk: Path) -> None:
    _generator(desk / "research" / "greedy.py",
               "def run(box):\n    held = box.open_lockbox()\n    return donate(held)\n")
    out = M.generator_isolation()
    assert out["scanned"] == ["research/greedy.py"]
    assert len(out["findings"]) == 1
    hit = out["findings"][0]
    assert hit["file"] == "research/greedy.py" and hit["line"] == "4"
    assert "open_lockbox" in hit["what"]


def test_sealing_your_own_tail_is_the_correct_behaviour_and_is_not_a_finding(desk: Path) -> None:
    """`expression_factory`'s real shape: import the holdout, seal with it, read only research."""
    _generator(desk / "research" / "factory.py",
               "from libs.validation.lockbox import LockedHoldout\n\n"
               "def run(bars):\n"
               "    box = LockedHoldout(bars, holdout_fraction=0.3)\n"
               "    return donate(box.research())\n")
    assert M.generator_isolation()["findings"] == []


def test_prose_about_the_holdout_is_not_a_finding_but_a_sealed_path_is(desk: Path) -> None:
    _generator(desk / "research" / "talker.py", "def run():\n    return donate([])\n",
               doc="Never reads desks/mt5/data/lockbox, and never the evidence_vault.json.")
    assert M.generator_isolation()["findings"] == []

    _generator(desk / "research" / "reacher.py",
               "def run():\n"
               '    path = "desks/mt5/data/lockbox/XAUUSD.parquet"\n'
               "    return donate(path)\n")
    hits = M.generator_isolation()["findings"]
    assert [h["file"] for h in hits] == ["research/reacher.py"]
    assert hits[0]["line"] == "4"


def test_a_judge_is_skipped_and_a_non_proposer_is_never_scanned(desk: Path) -> None:
    _generator(desk / "research" / "judge.py", "def run(box):\n    return box.open_lockbox()\n")
    (desk / "research" / "plumbing.py").write_text(
        "def run(box):\n    return box.open_lockbox()\n", "utf-8")
    out = M.generator_isolation()
    assert out["scanned"] == [] and out["findings"] == []
    assert "research/judge.py" in out["judges_skipped"]


def test_the_real_desk_is_scanned_and_is_clean_today() -> None:
    """The enumeration itself is the claim: a wall that scanned nothing would also be green."""
    out = M.generator_isolation()
    assert out["n_scanned"] >= 15, out["n_scanned"]
    assert "libs/research/generators.py" in out["scanned"]
    assert "desks/mt5/research/qd_frontier.py" in out["scanned"]
    assert "desks/mt5/research/expression_factory.py" in out["scanned"]
    assert out["unparsed"] == []
    assert out["findings"] == [], out["findings"]


# ------------------------------------- WHICH record, WHICH field, WHICH host (2026-09-24)
def test_a_breach_names_the_records_and_the_fields_that_moved(box: Path) -> None:
    """THE ESCALATION THIS PREVENTS. "the sealed prefix of 151 record(s) changed" was read as
    "151 execution records were rewritten"; it meant "at least one of 151". The fence must say
    WHICH -- and because a re-rounded float and a changed price wore the same word, WHICH FIELDS
    moved, so "did a traded quantity change?" is answered by the fence, not by a session.
    """
    led = box / "data" / "live_ledger.jsonl"
    rows = [{"deal": i, "pl_quote": 1.5 * i, "volume": 0.02, "sleeve": "gold_asia",
             "r_multiple": 0.0} for i in range(6)]
    led.write_text("\n".join(json.dumps(r) for r in rows), "utf-8")
    _seal(box)
    assert _status("data/live_ledger.jsonl")["status"] == "verified"

    rows[2]["r_multiple"] = 1.9547            # the documented backfill: an inert field, one row
    led.write_text("\n".join(json.dumps(r) for r in rows), "utf-8")
    bad = _status("data/live_ledger.jsonl")
    loc = bad["localisation"]
    assert bad["status"] == "breach"
    assert loc["localised"] is True
    assert loc["n_changed"] == 1 and loc["first_changed"] == 2
    assert loc["fields_moved"] == {"r_multiple": 1}
    assert "pl_quote" in loc["fields_unchanged"] and "volume" in loc["fields_unchanged"]
    assert "1 of the 6 sealed record(s) were rewritten" in bad["why"]
    assert "r_multiple x1" in bad["why"]

    rows[4]["pl_quote"] = -999.0              # the serious one: a traded quantity
    led.write_text("\n".join(json.dumps(r) for r in rows), "utf-8")
    worse = _status("data/live_ledger.jsonl")["localisation"]
    assert worse["n_changed"] == 2
    assert worse["fields_moved"] == {"r_multiple": 1, "pl_quote": 1}


def test_a_seal_without_per_record_digests_says_so_rather_than_implying_a_count(
        box: Path) -> None:
    """An OLD seal must not read as though it had localised. It states the limit in words."""
    led = box / "data" / "live_ledger.jsonl"
    led.write_text("\n".join(f'{{"deal": {i}}}' for i in range(4)), "utf-8")
    seal = M.append_only_seal()
    for entry in seal.values():                          # a pre-2026-09-24 manifest
        entry.pop("rows", None)
        entry.pop("fields", None)
    (box / "manifest.json").write_text(
        json.dumps({"files": {}, "append_only": seal, "vintage": {}}), "utf-8")
    led.write_text('{"deal": 0, "pl_quote": 9}\n'
                   + "\n".join(f'{{"deal": {i}}}' for i in range(1, 4)), "utf-8")
    bad = _status("data/live_ledger.jsonl")
    assert bad["status"] == "breach"
    assert bad["localisation"]["localised"] is False
    assert "SEALED PREFIX LENGTH, NOT THE NUMBER OF RECORDS THAT CHANGED" in bad["why"]


def test_a_seal_taken_on_another_host_is_named_as_such_and_stays_red(
        box: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A record file is written by ONE box; another box's copy is a different derivation of the
    same history. That is a sync fact, not proof a record was rewritten -- and it stays red."""
    led = box / "data" / "live_ledger.jsonl"
    led.write_text("\n".join(f'{{"deal": {i}}}' for i in range(4)), "utf-8")
    monkeypatch.setattr(M, "_HOST", "the-trading-box")
    _seal(box)
    monkeypatch.setattr(M, "_HOST", "some-build-box")
    led.write_text('{"deal": 0, "pl_quote": 9}\n'
                   + "\n".join(f'{{"deal": {i}}}' for i in range(1, 4)), "utf-8")
    bad = _status("data/live_ledger.jsonl")
    assert bad["status"] == "breach" and bad["sealed_host"] == "the-trading-box"
    assert "judge this on the writing host" in bad["why"]
    assert [f for f in M.check() if "live_ledger" in f["file"]]


# ---------------------------------------- the rewrite PATH, not only the rewrite (2026-09-24)
def _module(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, "utf-8")


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(M, "ROOT", tmp_path)
    monkeypatch.setattr(M, "APPEND_ONLY", (
        ("desks/mt5/data/live_ledger.jsonl", "lines", "the live ledger"),
        ("desks/mt5/reports/shadow/ledger_*.json", "rows", "the forward clocks"),
    ))
    monkeypatch.setattr(M, "INPLACE_DECLARED", {})
    (tmp_path / "scripts").mkdir()
    return tmp_path


def test_an_undeclared_in_place_rewrite_of_the_live_ledger_is_a_finding(repo: Path) -> None:
    _module(repo / "scripts" / "helpful.py",
            'from pathlib import Path\n'
            'LEDGER = Path("desks/mt5/data/live_ledger.jsonl")\n\n'
            'def fix(rows):\n'
            '    LEDGER.write_text("".join(rows), "utf-8")\n')
    out = M.inplace_rewrite_scan()
    assert [f["file"] for f in out["undeclared"]] == ["scripts/helpful.py"]
    assert out["undeclared"][0]["line"] == "5"
    assert any("UNDECLARED IN-PLACE REWRITE" in f["why"] for f in M.check())


def test_the_atomic_tmp_then_replace_dance_is_caught_too(repo: Path) -> None:
    """The real shape: write a sibling .tmp, then os.replace it over the sealed file."""
    _module(repo / "scripts" / "sneaky.py",
            'import os\nfrom pathlib import Path\n'
            'LEDGER = Path("desks/mt5/data/live_ledger.jsonl")\n\n'
            'def fix(rows):\n'
            '    tmp = LEDGER.with_suffix(".tmp")\n'
            '    with tmp.open("w") as f:\n'
            '        f.write(rows)\n'
            '    os.replace(tmp, LEDGER)\n')
    found = M.inplace_rewrite_scan()["undeclared"]
    assert [f["file"] for f in found] == ["scripts/sneaky.py"]
    assert "2 site(s)" in found[0]["what"]


def test_appending_is_not_a_finding_and_neither_is_writing_your_own_report(repo: Path) -> None:
    """The precision that makes this fence readable: the first cut produced 157 findings and
    every one of them was an organ that READS the ledger and writes its own report."""
    _module(repo / "scripts" / "honest.py",
            'import json\nfrom pathlib import Path\n'
            'LEDGER = Path("desks/mt5/data/live_ledger.jsonl")\n'
            'OUT = Path("desks/mt5/reports/mine.json")\n\n'
            'def run():\n'
            '    rows = LEDGER.read_text("utf-8").splitlines()\n'
            '    with LEDGER.open("a", encoding="utf-8") as f:\n'
            '        f.write("{}\\n")\n'
            '    OUT.write_text(json.dumps({"n": len(rows)}), "utf-8")\n')
    assert M.inplace_rewrite_scan()["undeclared"] == []


def test_one_functions_local_path_does_not_seal_that_name_module_wide(repo: Path) -> None:
    """Scope, measured: without it a generic `_atomic_write(path, doc)` helper was reported as a
    live-ledger rewriter because another function had a local called `path`."""
    _module(repo / "scripts" / "scoped.py",
            'import json\nfrom pathlib import Path\n'
            'DESK = Path("desks/mt5")\n\n'
            'def read_ledger():\n'
            '    path = DESK / "data" / "live_ledger.jsonl"\n'
            '    return path.read_text("utf-8")\n\n'
            'def write_state(doc):\n'
            '    path = DESK / "data" / "equity_series.json"\n'
            '    path.write_text(json.dumps(doc), "utf-8")\n')
    assert M.inplace_rewrite_scan()["undeclared"] == []


def test_a_declared_rewriter_is_named_rather_than_hidden(
        repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _module(repo / "scripts" / "backfill.py",
            'from pathlib import Path\n'
            'LEDGER = Path("desks/mt5/data/live_ledger.jsonl")\n\n'
            'def fix(rows):\n'
            '    LEDGER.write_text("".join(rows), "utf-8")\n')
    monkeypatch.setattr(M, "INPLACE_DECLARED", {"scripts/backfill.py": "the declared backfill"})
    out = M.inplace_rewrite_scan()
    assert out["undeclared"] == [] and out["declared"] == ["scripts/backfill.py"]


def test_the_real_desk_has_exactly_one_declared_rewriter_and_no_undeclared_one() -> None:
    """The enumeration is the claim (L1.49). `backfill_live_ledger_r.py` is a REAL whole-file
    rewriter -- it repaired `r_multiple` on 141 of 151 live rows the writer had floored at zero,
    reaching it through `--ledger`, which is why the scan follows a CLI default -- and the desk
    must be able to name every such organ on demand."""
    out = M.inplace_rewrite_scan()
    assert out["n_scanned"] >= 40, out["n_scanned"]
    assert out["declared"] == ["scripts/backfill_live_ledger_r.py"], out["declared"]
    assert out["declared_missing"] == []
    assert out["undeclared"] == [], out["undeclared"]


# ------------------------------------------------- THE RULER THE SEAL WAS TAKEN WITH (2026-09-24)
#: The fence changed its own canonical form 23 hours AFTER the standing record seal was taken and
#: then reported 152 of 192 forward ledgers as rewritten. 151 of them had not moved a byte: their
#: sealed prefixes reproduce exactly under the pre-change form. These tests pin both halves --
#: the ruler change must NOT read as a rewrite, and a rewrite must still read as one.


def _legacy_seal(box: Path) -> None:
    """A seal in the shape taken before 2026-09-24: every field hashed, no `ruler`, no digests."""
    entry = {}
    for rel, mode, _why in M.APPEND_ONLY:
        for name, path in M._expand(rel):
            recs = M._records(path, mode, drop=frozenset())
            if recs is None:
                continue
            half = len(recs) // 2
            entry[name] = {"records": len(recs), "prefix_sha": M._prefix_sha(recs, len(recs)),
                           "half": half, "half_sha": M._prefix_sha(recs, half), "mode": mode}
    (box / "manifest.json").write_text(
        json.dumps({"files": {}, "append_only": entry, "vintage": M.vintage_seal()}), "utf-8")


def _rows_with_stamps(n: int, r: float = 1.5) -> str:
    return json.dumps([{"entry_time": f"2026-08-1{i} 05:00:00+00:00", "side": -1, "entry": 1.0,
                        "exit": 1.1, "r_multiple": r, "reason": "ttl", "phase": "historical",
                        "bars_fetched_utc": "2026-09-23T02:34:28+00:00",
                        "bars_freshest": "2026-09-23T02:00:00+00:00", "bars_stale": False}
                       for i in range(n)])


def test_a_pass_stamp_rederivation_under_an_old_seal_is_verified_not_breached(box: Path) -> None:
    """The 151. The derivation stamps moved because every pass re-stamps them, and the seal that
    covered them was taken before the fence learned to drop them. The bytes still reproduce the
    sealed hash under the ruler it was taken with, so nothing was rewritten and the fence must
    say exactly that instead of 'a record was rewritten'."""
    led = box / "reports" / "shadow" / "ledger_AUDCAD_asia.json"
    led.write_text(_rows_with_stamps(6), "utf-8")
    _legacy_seal(box)
    row = _status("reports/shadow/ledger_AUDCAD_asia.json")
    assert row["status"] == "ruler_change", row
    assert row["sealed_ruler"] == M._LEGACY_RULER
    assert "not one byte of evidence moved" in row["why"]
    assert not [f for f in M.check() if "ledger_AUDCAD_asia" in f["file"]]


def test_an_evidence_field_rewritten_is_a_breach_under_every_ruler(box: Path) -> None:
    """The 1. `r_multiple` is evidence, not a fact about the pass, so no ruler forgives it: the
    file must reproduce NEITHER canonical form and the verdict must stay BREACH."""
    led = box / "reports" / "shadow" / "ledger_AUDCAD_asia.json"
    led.write_text(_rows_with_stamps(6, r=1.5), "utf-8")
    _legacy_seal(box)
    led.write_text(_rows_with_stamps(6, r=9.9), "utf-8")
    row = _status("reports/shadow/ledger_AUDCAD_asia.json")
    assert row["status"] == "breach", row
    assert [f for f in M.check() if "ledger_AUDCAD_asia" in f["file"]]


def test_a_breach_on_a_seal_that_names_no_host_says_it_cannot_attribute(box: Path) -> None:
    """These ledgers are untracked per-box derivations. A seal with no host cannot tell 'rewritten'
    from 'another box's copy', and a verdict that cannot name its subject must say so (L1.28a)."""
    led = box / "reports" / "shadow" / "ledger_AUDCAD_asia.json"
    led.write_text(_rows_with_stamps(6, r=1.5), "utf-8")
    _legacy_seal(box)
    led.write_text(_rows_with_stamps(6, r=9.9), "utf-8")
    assert "names NO host" in _status("reports/shadow/ledger_AUDCAD_asia.json")["why"]


def test_every_new_seal_records_the_ruler_it_was_taken_with(box: Path) -> None:
    """The structural half: a measurement whose units are not written down cannot be re-checked,
    and that is the whole defect this class of breach came from."""
    led = box / "reports" / "shadow" / "ledger_AUDCAD_asia.json"
    led.write_text(_rows_with_stamps(3), "utf-8")
    (box / "data" / "live_ledger.jsonl").write_text('{"deal": 1}\n', "utf-8")
    seal = M.append_only_seal()
    assert seal, "the seal enumerated nothing"
    for name, rec in seal.items():
        assert rec["ruler"] == M._RULER, name
        assert rec["host"] == M._HOST, name


def test_sign_files_leaves_the_record_seals_untouched(box: Path, capsys: pytest.CaptureFixture[str],
                                                      monkeypatch: pytest.MonkeyPatch) -> None:
    """Re-signing the judge must never erase the records. `--sign` rewrites `append_only` in the
    same act, which would destroy the only evidence that can answer 'was this record rewritten'
    -- so the maintenance act the desk actually needs has to be separable, and this pins it."""
    led = box / "reports" / "shadow" / "ledger_AUDCAD_asia.json"
    led.write_text(_rows_with_stamps(3), "utf-8")
    _legacy_seal(box)
    before = json.loads((box / "manifest.json").read_text("utf-8"))["append_only"]
    monkeypatch.setattr(sys, "argv", ["check", "--sign-files", "--by", "test"])
    assert M.main() == 0
    after = json.loads((box / "manifest.json").read_text("utf-8"))
    assert after["append_only"] == before
    assert after["signed_by"] == "test"
    capsys.readouterr()
