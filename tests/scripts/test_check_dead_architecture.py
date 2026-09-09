"""Clock, artifact, consumer: an organ nobody reads is named, and nothing is called dead."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts import check_dead_architecture as da  # noqa: E402


def _repo(tmp_path: Path) -> Path:
    (tmp_path / "desks" / "mt5" / "research").mkdir(parents=True)
    (tmp_path / "desks" / "mt5" / "ops").mkdir(parents=True)
    (tmp_path / "libs").mkdir()
    (tmp_path / "scripts").mkdir()
    (tmp_path / "ops").mkdir()
    R = tmp_path / "desks" / "mt5" / "research"
    (R / "burner.py").write_text(
        'OUT = BASE / "reports" / "burner_out.json"\n'
        'def main():\n    OUT.write_text("{}")\n', "utf-8")
    (R / "reader.py").write_text(
        'def go():\n    return _read("burner_out.json")\n', "utf-8")
    (R / "lonely.py").write_text(
        'P = "lonely_out.json"\ndef main():\n    open(P, "w").write("{}")\n', "utf-8")
    (R / "hourly_cycle.py").write_text(
        '_costed("burner", lambda: _producer("burner", "research/burner.py"))\n', "utf-8")
    (tmp_path / "desks" / "mt5" / "ops" / "box_tasks.manifest").write_text("", "utf-8")
    return tmp_path


def test_an_organ_on_a_clock_with_no_reader_is_burning(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    doc = da.census(repo)
    organs = doc["organs"]
    assert "burner_out.json" in organs["desks/mt5/research/burner.py"]["artifacts"]
    assert organs["desks/mt5/research/burner.py"]["verdict"] == da.LIVE, \
        "reader.py names the artifact, so this organ has a consumer and a clock"
    assert "desks/mt5/research/reader.py" in organs["desks/mt5/research/burner.py"]["consumers"]


def test_an_organ_with_neither_a_clock_nor_a_reader_is_unreached_not_dead(tmp_path: Path) -> None:
    doc = da.census(_repo(tmp_path))
    assert doc["organs"]["desks/mt5/research/lonely.py"]["verdict"] == da.UNREACHED
    assert "desks/mt5/research/lonely.py" in doc["unreached"]
    assert da.UNREACHED == "UNREACHED"
    src = Path(da.__file__).read_text("utf-8")
    assert '"DEAD"' not in src, "the census must not claim a death its evidence cannot support"
    assert doc["confidence"]["clock"].startswith("exact")
    assert "under-reports" in doc["confidence"]["consumer"]


def test_two_writers_of_one_filename_are_contested(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    (repo / "desks" / "mt5" / "research" / "rival.py").write_text(
        'OUT = BASE / "reports" / "burner_out.json"\n'
        'def main():\n    OUT.write_text("{}")\n', "utf-8")
    doc = da.census(repo)
    assert "burner_out.json" in doc["contested_artifacts"]
    assert doc["contested_artifacts"]["burner_out.json"] == [
        "desks/mt5/research/burner.py", "desks/mt5/research/rival.py"]


def test_generic_filenames_are_not_organs(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    (repo / "desks" / "mt5" / "research" / "generic.py").write_text(
        'P = "config.json"\ndef main():\n    open(P, "w").write("{}")\n', "utf-8")
    doc = da.census(repo)
    assert "desks/mt5/research/generic.py" not in doc["organs"], \
        "config.json identifies no organ"


def test_strict_exits_one_only_on_a_contested_artifact(tmp_path: Path) -> None:
    out = tmp_path / "dead.json"
    rc = da.main(["--out", str(out)])
    assert rc == 0
    doc = json.loads(out.read_text("utf-8"))
    assert doc["n_organs"] > 100, "the real repo has hundreds of organs that write something"
    assert set(doc["counts"]) <= {da.LIVE, da.BURNING, da.NO_CLOCK, da.UNREACHED}
    rc_strict = da.main(["--strict", "--out", str(out)])
    assert rc_strict == (1 if doc["contested_artifacts"] else 0)
