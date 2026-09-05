"""The dead-wire fence must catch the COT shape and stay quiet on everything that works.

The defect it exists for: `edge_search` and `orthogonal_sweep` read `cot.json`, `cot_tff.json`
and `cot_disagg.json`, and nothing in the repository has ever written any of them. Both legs fell
through and resolved with no COT, silently, for the whole life of the search leg.

The hard part of this fence is not finding that. It is not finding a hundred other things: this
desk writes through helpers, so the filename literal usually does not share a line with the verb
that produces it. The first version flagged 224 artifacts, 169 in production code, and would have
been switched off within a day. Pinned here: the exact COT shape fails, every way a real producer
can exist passes, and the ratchet only moves down.
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(_ROOT / "scripts"))

import check_read_without_writer as rw  # noqa: E402


def _tree(tmp_path: Path, files: dict[str, str]) -> Path:
    for rel, body in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, "utf-8")
    return tmp_path


def _names(doc: dict) -> list[str]:
    return sorted(d["artifact"] for d in doc["read_without_writer"])


def test_the_cot_shape_is_caught(tmp_path, monkeypatch) -> None:
    """THE ORIGINAL DEFECT, reduced. Two readers, no producer, no file."""
    monkeypatch.setattr(rw, "ROOT", _tree(tmp_path, {
        "desks/mt5/research/edge_search.py":
            'for name in ("cot_tff.json", "cot.json"):\n'
            '    doc = _read(BASE / "data" / name)\n',
        "desks/mt5/research/orthogonal_sweep.py":
            'doc = _read(BASE / "data" / "cot.json")\n',
    }))
    assert _names(rw.scan()) == ["cot.json", "cot_tff.json"]


def test_a_producer_anywhere_clears_it(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(rw, "ROOT", _tree(tmp_path, {
        "desks/mt5/research/reader.py": 'doc = _read(BASE / "data" / "macro_state.json")\n',
        "scripts/build_macro.py": 'OUT.write_text(json.dumps(d))  # "macro_state.json"\n',
    }))
    assert _names(rw.scan()) == []


def test_a_file_that_simply_exists_clears_it(tmp_path, monkeypatch) -> None:
    """The lake and most artifacts are gitignored and produced on the box. A name that is
    already sitting on disk is wired by definition, whatever this scan can see of the writer."""
    monkeypatch.setattr(rw, "ROOT", _tree(tmp_path, {
        "desks/mt5/research/reader.py": 'doc = _read(BASE / "data" / "cost_surface.json")\n',
        "desks/mt5/data/cost_surface.json": "{}\n",
    }))
    assert _names(rw.scan()) == []


def test_a_name_mentioned_outside_a_read_is_never_called_dead(tmp_path, monkeypatch) -> None:
    """THE FALSE-POSITIVE RULE THAT MAKES THIS SHIPPABLE. `_write(P, doc)` puts the verb and the
    filename on different lines, so a line-based scan cannot see the producer. A name assigned
    to a constant, passed to a helper or listed in a manifest has a life this scan cannot
    follow, and calling it dead would flag correct code."""
    monkeypatch.setattr(rw, "ROOT", _tree(tmp_path, {
        "scripts/producer.py":
            'OUT = ROOT / "data" / "verdicts.json"\n'      # named, not a read, not a write line
            'def save(doc):\n'
            '    _write(OUT, doc)\n',
        "scripts/consumer.py": 'doc = _read(ROOT / "data" / "verdicts.json")\n',
    }))
    assert _names(rw.scan()) == []


def test_a_fixture_only_tests_name_is_not_a_leg_input(tmp_path, monkeypatch) -> None:
    """Tests build and delete their own files, and several assert on ABSENCE on purpose."""
    monkeypatch.setattr(rw, "ROOT", _tree(tmp_path, {
        "tests/execution/test_canary.py": 'assert not _read(tmp_path / "absent.json")\n',
        "desks/mt5/tests/test_x.py": 'doc = _read(tmp_path / "adm.json")\n',
    }))
    assert _names(rw.scan()) == []


def test_a_hostname_in_a_comment_does_not_count_as_a_read(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(rw, "ROOT", _tree(tmp_path, {
        "scripts/note.py": '# we used to _read("old_thing.json") here; retired 2026-08-18\n'
                           'X = 1\n',
    }))
    assert _names(rw.scan()) == []


def test_the_ratchet_fails_only_on_a_new_wire(tmp_path, monkeypatch, capsys) -> None:
    """At or below the recorded count is a debt being worked down. One more is a defect."""
    monkeypatch.setattr(rw, "ROOT", _tree(tmp_path, {
        "scripts/a.py": 'x = _read(P / "one.json")\ny = _read(P / "two.json")\n',
    }))
    monkeypatch.setattr(rw, "OUT", tmp_path / "out.json")
    monkeypatch.setattr(sys, "argv", ["check_read_without_writer.py"])

    monkeypatch.setattr(rw, "MAX_DANGLING", 2)
    assert rw.main() == 0
    assert "one.json" in capsys.readouterr().out, "a tolerated wire is still NAMED"

    monkeypatch.setattr(rw, "MAX_DANGLING", 1)
    assert rw.main() == 1
    assert "A NEW one was added" in capsys.readouterr().out


def test_the_ratchet_asks_to_be_tightened_when_the_count_falls(tmp_path, monkeypatch,
                                                               capsys) -> None:
    """A floor that never follows the count down stops being a floor."""
    monkeypatch.setattr(rw, "ROOT", _tree(tmp_path, {
        "scripts/a.py": 'x = _read(P / "one.json")\n'}))
    monkeypatch.setattr(rw, "OUT", tmp_path / "out.json")
    monkeypatch.setattr(sys, "argv", ["check_read_without_writer.py"])
    monkeypatch.setattr(rw, "MAX_DANGLING", 9)
    assert rw.main() == 0
    assert "RATCHET: lower MAX_DANGLING to 1" in capsys.readouterr().out
