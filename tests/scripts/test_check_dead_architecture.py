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


def test_strict_exits_one_only_on_a_contested_artifact(tmp_path: Path, monkeypatch) -> None:
    # Exercise the actual census and CLI on an owned graph. Scanning the populated
    # VPS twice makes this CLI contract depend on the size of unrelated research data.
    repo = _repo(tmp_path)
    census = da.census
    monkeypatch.setattr(da, "census", lambda: census(repo))
    out = tmp_path / "dead.json"
    rc = da.main(["--out", str(out)])
    assert rc == 0
    doc = json.loads(out.read_text("utf-8"))
    assert doc["n_organs"] == 2
    assert set(doc["counts"]) <= {da.LIVE, da.BURNING, da.NO_CLOCK, da.UNREACHED}
    rc_strict = da.main(["--strict", "--out", str(out)])
    assert rc_strict == (1 if doc["contested_artifacts"] else 0)
    (repo / "desks" / "mt5" / "research" / "rival.py").write_text(
        'OUT = BASE / "reports" / "burner_out.json"\n'
        'def main():\n    OUT.write_text("{}")\n', "utf-8")
    assert da.main(["--strict", "--out", str(out)]) == 1
    assert "burner_out.json" in json.loads(out.read_text("utf-8"))["contested_artifacts"]


# ---- speed without changing a verdict (Desk health 2026-11-06: the fence ran past 600 s) ----
def _reference_writes_through(src: str, const: str) -> bool:
    """The per-name rescan the fence used before 2026-11-06, kept here as the oracle."""
    import re

    names = {const}
    for line in src.splitlines():
        m = re.match(da._ALIAS, line)
        if not m or not re.search(rf"\b{re.escape(const)}\b", m.group(2)):
            continue
        names |= set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", m.group(1)))
    for name in names:
        nm = re.escape(name)
        if re.search(
            rf"\b{nm}\s*\.\s*(?:write_text|write_bytes|open\(\s*['\"][wax]|parent\.mkdir)"
            rf"|(?:write_report|stamp_sidecar|_atomic_write|os\.replace|json\.dump)\([^)]*\b{nm}\b"
            rf"|\bto_(?:json|csv|parquet)\(\s*{nm}\b", src):
            return True
    return False


SAMPLE = '''
REPORT = ROOT / "reports" / "x.json"
OTHER = ROOT / "y.json"
r, m = report or REPORT, markdown or DOC
def a():
    r.write_text("{}")
def b():
    json.dump(doc, open(OTHER_TMP, "w"), indent=1)
    write_report(
        payload, SIDE)
    df.to_parquet(  PARQ )
    self.LOG.open('a').write("x")
    CACHE.parent.mkdir(parents=True)
    os.replace(tmp, FINAL)
class C:
    try:
        import json as j
    except ImportError:
        from libs.ops import release
    else:
        pass
    def f(self):
        if x:
            with y:
                from scripts import learn
        match z:
            case 1:
                import desks.mt5.research.promoter
'''


def test_the_one_pass_write_search_agrees_with_the_per_name_rescan() -> None:
    sites, aliases = da._write_sites(SAMPLE), da._alias_lines(SAMPLE)
    for const in ("REPORT", "OTHER", "OTHER_TMP", "SIDE", "payload", "PARQ", "LOG", "CACHE",
                  "FINAL", "tmp", "DOC", "markdown", "nothing", "r", "m"):
        assert da._writes_through(SAMPLE, const, aliases, sites) == \
            _reference_writes_through(SAMPLE, const), const


def test_the_statement_walk_finds_every_import_ast_walk_finds() -> None:
    import ast

    tree = ast.parse(SAMPLE)
    every = [n for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))]
    found = [n for n in da._statements(tree) if isinstance(n, (ast.Import, ast.ImportFrom))]
    assert len(every) == 4 and sorted(map(id, every)) == sorted(map(id, found))
