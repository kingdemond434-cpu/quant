"""side_channels/full_pipeline is a second UNIVERSAL_SURVIVORS pen (daily 06:00 timer).

Audit 2026-10-14 (T8 v3 spec readers, inherited finding): it minted at its own charged trial
count (>= 7 x effective cells), took no lock, and turned an unreadable authority into `{}` and
then wrote it -- wiping the main writer's certificates. Each test below fails on that code.
"""
from __future__ import annotations

import ast
import json
import sys
from contextlib import contextmanager
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for p in (str(ROOT), str(DESK), str(DESK / "side_channels")):
    if p not in sys.path:
        sys.path.insert(0, p)

import full_pipeline as fp  # noqa: E402

_VERDICT = {"passed": True, "cell": "EURUSD.carry.{}", "sym": "EURUSD", "family": "carry",
            "params": {"lb": 20}, "days": 400, "stages": {"x": {"passed": True}}}


@contextmanager
def _lane(granted: bool):
    yield granted


def _with_lane(monkeypatch: pytest.MonkeyPatch, granted: bool, seen: list[str]) -> None:
    import research.job_lock as jl

    def fake(name: str, need_mb: int = 0, **_kw):
        seen.append(name)
        return _lane(granted)
    monkeypatch.setattr(jl, "exclusive_job", fake)


def test_an_unreadable_authority_is_never_overwritten(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(fp, "REPORTS", tmp_path)
    _with_lane(monkeypatch, True, [])
    auth = tmp_path / "UNIVERSAL_SURVIVORS.json"
    auth.write_text('{"survivors": {"external.KEEP": {"cell": "k"}}, TRUNCATED', "utf-8")
    before = auth.read_bytes()
    assert fp.step_certify({"verdicts": [_VERDICT]}) is None
    assert auth.read_bytes() == before, "an unreadable authority was overwritten"


def test_it_writes_only_under_the_main_writers_lane(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(fp, "REPORTS", tmp_path)
    seen: list[str] = []
    _with_lane(monkeypatch, False, seen)
    assert fp.step_certify({"verdicts": [_VERDICT]}) is None
    assert seen == ["certification_lane"]
    assert not (tmp_path / "UNIVERSAL_SURVIVORS.json").exists(), "wrote without the lane"


def test_with_the_lane_it_merges_and_never_drops_a_certificate(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(fp, "REPORTS", tmp_path)
    seen: list[str] = []
    _with_lane(monkeypatch, True, seen)
    auth = tmp_path / "UNIVERSAL_SURVIVORS.json"
    auth.write_text(json.dumps({"survivors": {"external.KEEP": {"cell": "k"}}}), "utf-8")
    out = fp.step_certify({"verdicts": [_VERDICT]})
    doc = json.loads(auth.read_text("utf-8"))
    assert seen == ["certification_lane"]
    assert set(doc["survivors"]) == {"external.KEEP", "external.EURUSD.carry.{}"}
    assert out is not None and len(out) == 2


def test_its_dsr_charges_the_tier_s_bar_n_and_reports_the_count() -> None:
    tree = ast.parse((DESK / "side_channels" / "full_pipeline.py").read_text("utf-8"))
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
             and isinstance(n.func, ast.Name) and n.func.id == "dsr_canon"]
    assert calls, "the DSR call moved; re-point this test"
    for c in calls:
        kw = {k.arg: k.value for k in c.keywords}
        arg = kw["n_trials"]
        assert isinstance(arg, ast.Call) and getattr(arg.func, "id", "") == "bar_n", \
            ast.unparse(arg)


def test_the_self_heal_copy_carries_the_same_fix() -> None:
    """fix_gauntlet restores full_pipeline.py from the canonical twin on drift; a stale twin
    would restore the unlocked, trial-scaled writer."""
    sc = DESK / "side_channels"
    assert (sc / "full_pipeline.canonical.py").read_text("utf-8") == \
        (sc / "full_pipeline.py").read_text("utf-8")
