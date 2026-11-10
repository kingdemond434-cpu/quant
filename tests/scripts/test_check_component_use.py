"""ARCH-33: every clocked organ needs a role, a test, a consumer and a tested consumer, or a
declared zero-weight redundancy; the gapped count ratchets down; the census carries the counts."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for p in (str(ROOT), str(ROOT / "scripts")):
    if p not in sys.path:
        sys.path.insert(0, p)

import check_component_use as cu  # noqa: E402


def _tree(tmp: Path) -> Path:
    (tmp / "tests").mkdir()
    (tmp / "tests" / "test_a.py").write_text(
        "from research import organ_a\nimport libs.reader_x as rx\n", "utf-8")
    (tmp / "tests" / "test_b.py").write_text('RUN = "organ_b.py"\n', "utf-8")
    return tmp


CENSUS = {"organs": {
    "desks/mt5/research/organ_a.py": {"planes": ["hourly_leg"], "artifacts": ["A.json"],
                                      "consumers": ["libs/reader_x.py"]},
    "desks/mt5/research/organ_b.py": {"planes": ["box_task"], "artifacts": ["B.json"],
                                      "consumers": ["libs/reader_y.py"]},
    "desks/mt5/research/organ_c.py": {"planes": ["hourly_leg"], "artifacts": ["C.json"],
                                      "consumers": []},
    "desks/mt5/research/unclocked.py": {"planes": [], "artifacts": ["U.json"],
                                       "consumers": []},
}}


@pytest.fixture
def roles(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cu, "roles", lambda root: {
        "desks/mt5/research/organ_a.py": "layer:meta (leg a)",
        "desks/mt5/research/organ_b.py": "box_task:MT5-B"})


def test_test_tokens_read_imports_and_named_files() -> None:
    t = cu.test_tokens("from research.sub import foo, bar as b\nimport baz.qux\n"
                       'x = "desks/mt5/research/zed.py"\n'
                       'importlib.import_module("research.lazy_one")\n')
    assert {"foo", "bar", "qux", "zed", "lazy_one", "sub"} <= t


def test_verdicts_name_each_gap(tmp_path: Path, roles: None,
                                monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cu, "ZERO_WEIGHT", tmp_path / "none.json")
    doc = cu.build(_tree(tmp_path), census=CENSUS)
    o = doc["organs"]
    assert o["desks/mt5/research/organ_a.py"]["verdict"] == "USED"
    assert o["desks/mt5/research/organ_b.py"]["gaps"] == ["CONSUMER_UNTESTED"]
    assert set(o["desks/mt5/research/organ_c.py"]["gaps"]) == {
        "NO_ROLE", "UNTESTED", "NO_CONSUMER"}
    assert "desks/mt5/research/unclocked.py" not in o
    assert doc["counts"] == {"USED": 1, "ZERO_WEIGHT": 0, "GAPPED": 2}


def test_zero_weight_needs_a_declared_redundancy(tmp_path: Path, roles: None,
                                                 monkeypatch: pytest.MonkeyPatch) -> None:
    zw = tmp_path / "zw.json"
    zw.write_text(json.dumps({"components": [
        {"path": "desks/mt5/research/organ_c.py", "reason": "duplicate of a",
         "redundant_with": "desks/mt5/research/organ_a.py"},
        {"path": "desks/mt5/research/organ_b.py", "reason": "no partner named"}]}))
    monkeypatch.setattr(cu, "ZERO_WEIGHT", zw)
    doc = cu.build(_tree(tmp_path), census=CENSUS)
    assert doc["organs"]["desks/mt5/research/organ_c.py"]["verdict"] == "ZERO_WEIGHT"
    assert doc["organs"]["desks/mt5/research/organ_b.py"]["verdict"] == "GAPPED"


def test_ratchet_fails_only_when_gapped_rises(tmp_path: Path,
                                             monkeypatch: pytest.MonkeyPatch,
                                             capsys: pytest.CaptureFixture[str]) -> None:
    base = {"n_clocked": 3, "counts": {"USED": 1, "ZERO_WEIGHT": 0, "GAPPED": 2},
            "gaps": {}, "gapped": ["x", "y"]}
    monkeypatch.setattr(cu, "build", lambda: base)
    monkeypatch.setattr(cu, "MAX_GAPPED", 1)
    assert cu.main(["--ratchet", "--no-write"]) == 1
    monkeypatch.setattr(cu, "MAX_GAPPED", 2)
    assert cu.main(["--ratchet", "--no-write"]) == 0
    monkeypatch.setattr(cu, "MAX_GAPPED", 5)
    assert cu.main(["--ratchet", "--no-write"]) == 0
    assert "lower MAX_GAPPED" in capsys.readouterr().out


def test_this_repository_holds_its_ratchet() -> None:
    doc = cu.build()
    assert doc["n_clocked"] > 100
    assert doc["counts"]["GAPPED"] <= cu.MAX_GAPPED, doc["gapped"][:20]


def test_the_census_carries_the_component_use_counts(tmp_path: Path,
                                                     monkeypatch: pytest.MonkeyPatch) -> None:
    import check_dead_architecture as da
    rep = tmp_path / "desks" / "mt5" / "reports"
    rep.mkdir(parents=True)
    (rep / "COMPONENT_USE.json").write_text(json.dumps(
        {"at": "t", "counts": {"GAPPED": 3}, "used_share": 0.5}))
    doc = da.census(tmp_path)
    assert doc["component_use"]["counts"] == {"GAPPED": 3}
    doc = da.census(tmp_path / "nowhere")
    assert doc["component_use"]["status"] == "UNMEASURED"
