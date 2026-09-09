"""PIT_CENSUS.json names the sources the judge-side ratchet would refuse (Tier-1 audit V6).

`external_gauntlet.main` splits its docket with `libs.data.pit.is_stamped` and refuses every
unstamped row the moment any stamped row exists. The census now carries, per source, the same
predicate's answer -- `blocks_certification` -- so the sources that must be re-donated before the
already-written ratchet fires are named rather than averaged into a fraction. Measurement and
ordering only: the exit code still belongs to the stamped-fraction ratchet.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import scripts.check_pit as P

from libs.data.pit import is_stamped, stamp

ROOT = Path(__file__).resolve().parents[2]


def _intel(tmp_path: Path, sources: dict[str, tuple[int, int]]) -> Path:
    """An intelligence tree: per source, (stamped rows, unstamped rows) in one discoveries file."""
    intel = tmp_path / "intelligence"
    for name, (n_stamped, n_plain) in sources.items():
        rows: list[dict[str, Any]] = [
            stamp({"title": f"{name} {i}", "found_at": "2026-09-01T00:00:00+00:00"}, name,
                  source_version="test")
            for i in range(n_stamped)
        ] + [{"title": f"{name} plain {i}"} for i in range(n_plain)]
        d = intel / name
        d.mkdir(parents=True)
        (d / "discoveries_20260901_0000.json").write_text(json.dumps(rows), "utf-8")
    intel.mkdir(exist_ok=True)
    return intel


def _census(tmp_path: Path, monkeypatch: Any, sources: dict[str, tuple[int, int]]) -> dict:
    monkeypatch.setattr(P, "INTEL", _intel(tmp_path, sources))
    monkeypatch.setattr(P, "OUT", tmp_path / "reports" / "PIT_CENSUS.json")
    monkeypatch.setattr(P, "CERTIFICATES", tmp_path / "no_certificates")
    return P.run()


def test_blocks_certification_is_the_judges_own_predicate_per_source(tmp_path, monkeypatch):
    doc = _census(tmp_path, monkeypatch, {"clean": (3, 0), "mixed": (2, 1), "bare": (0, 4)})
    ps = doc["per_source"]
    assert ps["clean"]["blocks_certification"] is False and ps["clean"]["unstamped_rows"] == 0
    assert ps["mixed"]["blocks_certification"] is True and ps["mixed"]["unstamped_rows"] == 1
    assert ps["bare"]["blocks_certification"] is True and ps["bare"]["unstamped_rows"] == 4
    assert doc["ratchet"]["armed"] is True
    assert doc["ratchet"]["sources_blocking_certification"] == ["bare", "mixed"]
    assert "is_stamped" in doc["ratchet"]["predicate"]
    # The same predicate, recomputed from the rows on disk: no second definition of "stamped".
    for name, c in ps.items():
        f = next((tmp_path / "intelligence" / name).glob("discoveries_*.json"))
        rows = json.loads(f.read_text("utf-8"))
        assert c["blocks_certification"] == any(not is_stamped(r) for r in rows)
    on_disk = json.loads((tmp_path / "reports" / "PIT_CENSUS.json").read_text("utf-8"))
    assert on_disk["per_source"]["mixed"]["blocks_certification"] is True
    assert on_disk["ratchet"]["sources_blocking_certification"] == ["bare", "mixed"]


def test_a_wholly_unstamped_corpus_is_not_armed_but_every_source_is_named(tmp_path,
                                                                          monkeypatch):
    """The measured state of the desk (0 of 4,768 rows stamped): the ratchet is DEFERRED, and
    the census must still say which sources would be refused the moment it arms -- all of them."""
    doc = _census(tmp_path, monkeypatch, {"a": (0, 2), "b": (0, 3)})
    assert doc["ratchet"]["armed"] is False
    assert doc["ratchet"]["sources_blocking_certification"] == ["a", "b"]
    assert all(c["blocks_certification"] for c in doc["per_source"].values())
    assert doc["total"]["stamped_frac"] == 0.0


def test_the_judge_and_the_census_import_the_same_predicate():
    gauntlet = (ROOT / "desks" / "mt5" / "scripts" / "external_gauntlet.py").read_text("utf-8")
    census = (ROOT / "scripts" / "check_pit.py").read_text("utf-8")
    assert "from libs.data.pit import is_stamped" in gauntlet
    assert "is_stamped" in census and "def is_stamped" not in census
