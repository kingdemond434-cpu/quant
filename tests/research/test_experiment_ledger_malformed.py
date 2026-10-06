"""A malformed trial-ledger line is skipped and counted; every line after it is charged."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from libs.research import experiment_ledger as el


def _write(path: Path, rows: list[object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\n".join(r if isinstance(r, bytes) else json.dumps(r).encode()
                                for r in rows) + b"\n")


@pytest.fixture
def desk(tmp_path, monkeypatch):
    monkeypatch.setattr(el, "DESK", tmp_path)
    monkeypatch.setattr(el, "_MALFORMED", {})
    return tmp_path


def test_side_ledgers_charge_every_line_after_a_bad_one(desk) -> None:
    data = desk / "data"
    _write(data / "coevolution_trials.jsonl",
           [{"pairings": 2}, b"{not json", {"pairings": 3}])
    _write(data / "null_pass_trials.jsonl",
           [{"tests_run": 4}, b"\xff\xfe garbage", [1, 2], {"tests_run": 6}])
    _write(data / "learned_miners_trials.jsonl",
           [{"family": "a:x"}, b"{", {"family": "a:y"}, {"family": "a:y", "donated": True}])
    total, by_fam = el._proposer_counts()
    assert total == 2 + 3 + 4 + 6 + 2
    assert by_fam["model_pairing"] == 5 and by_fam["x"] == 1 and by_fam["y"] == 1
    assert el._MALFORMED == {"coevolution_trials.jsonl": 1, "null_pass_trials.jsonl": 2,
                             "learned_miners_trials.jsonl": 1}


def test_mass_screen_and_swarm_skip_bad_lines(desk, tmp_path) -> None:
    ms = tmp_path / "ms.jsonl"
    _write(ms, [{"family": "f", "cells_screened": 10}, b"oops",
                {"family": "f", "cells_screened": 5}])
    assert el._mass_screen_counts(ms) == (15, {"f": 15})
    sw = tmp_path / "sw.jsonl"
    _write(sw, [{"family": "g", "cells": ["n1", "n2"]}, b"\x00bad",
                {"family": "g", "cells": ["n3"]}])
    total, fam, skipped = el._swarm_counts(frozenset({"n2"}), sw)
    assert (total, fam, skipped) == (2, {"g": 2}, 1)
    assert el._MALFORMED["ms.jsonl"] == 1 and el._MALFORMED["sw.jsonl"] == 1


def test_lifetime_publishes_the_malformed_count(desk, monkeypatch) -> None:
    _write(desk / "data" / "coevolution_trials.jsonl", [b"bad", {"pairings": 1}])
    monkeypatch.setattr(el, "_graph_judged", lambda: (0, {}, set()))
    monkeypatch.setattr(el, "_claim_selection_counts", lambda: (0, {}))
    monkeypatch.setattr(el, "_prereg_counts", lambda: 0)
    for name in ("MASS_SCREEN_TRIALS", "UNKNOWN_UNKNOWN_TRIALS", "REGIME_SPLIT_TRIALS",
                 "PRODUCER_SWARM_TRIALS"):
        monkeypatch.setattr(el, name, desk / "absent" / f"{name}.jsonl")
    monkeypatch.setattr(el, "_mass_screen_counts",
                        lambda path=None: (0, {}))
    monkeypatch.setattr(el, "_swarm_counts", lambda *a, **k: (0, {}, 0))
    doc = el.lifetime(write=False)
    assert doc["lifetime_trials"] == 1
    assert doc["malformed_ledger_lines"]["coevolution_trials.jsonl"] == 1
