"""THE DATA-MACRO FENCE JUDGES macro_state.json BY ITS OWN `updated`, NEVER BY MTIME.

A git checkout rewrites mtime, so a macro_state.json frozen at 2026-09-12 read as minutes old to
this fence for six weeks (diagnosis 2026-10-21). An absent or unparseable `updated` is a breach:
an age that cannot be proved is never a pass.
"""
from __future__ import annotations

import importlib.util
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 10, 21, 12, tzinfo=UTC)


def _load():
    spec = importlib.util.spec_from_file_location(
        "_h_macro_test", _ROOT / "scripts" / "check_research_health.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _write(p: Path, doc: object) -> Path:
    p.write_text(json.dumps(doc) if not isinstance(doc, str) else doc, "utf-8")
    os.utime(p, (NOW.timestamp(), NOW.timestamp()))    # a fresh mtime, as a checkout leaves it
    return p


def test_a_fresh_mtime_does_not_hide_a_stale_updated(tmp_path: Path) -> None:
    h = _load()
    p = _write(tmp_path / "macro_state.json",
               {"updated": "2026-09-12T11:26:35.233173+00:00", "series": {}})
    age = h._updated_age_h(p, NOW)
    assert age is not None and age > 24 * 30
    assert h._mtime_age_h(p, NOW) < 1.0, "precondition: mtime alone would have read fresh"


def test_a_fresh_updated_reads_fresh(tmp_path: Path) -> None:
    h = _load()
    p = _write(tmp_path / "macro_state.json",
               {"updated": (NOW - timedelta(hours=2)).isoformat()})
    assert h._updated_age_h(p, NOW) == pytest.approx(2.0)
    z = _write(tmp_path / "z.json", {"updated": "2026-10-21T10:00:00Z"})
    assert h._updated_age_h(z, NOW) == pytest.approx(2.0)


@pytest.mark.parametrize("doc", [{"series": {}}, {"updated": ""}, {"updated": "yesterday"},
                                 {"updated": 12345}, [1, 2], "not json {"])
def test_absent_or_unparseable_updated_is_never_a_pass(tmp_path: Path, doc: object) -> None:
    h = _load()
    p = _write(tmp_path / "macro_state.json", doc)
    assert h._updated_age_h(p, NOW) is None


def test_a_missing_file_has_no_age(tmp_path: Path) -> None:
    assert _load()._updated_age_h(tmp_path / "absent.json", NOW) is None


def test_the_fence_breaches_on_a_stale_updated(tmp_path: Path, monkeypatch) -> None:
    """End to end through collect(): fresh mtime, stale `updated` -> a DATA-MACRO breach."""
    h = _load()
    desk = tmp_path / "desk"
    (desk / "data").mkdir(parents=True)
    _write(desk / "data" / "macro_state.json", {"updated": "2026-09-12T11:26:35+00:00"})
    monkeypatch.setattr(h, "DESK", desk)
    monkeypatch.setattr(h, "ROOT", tmp_path)
    monkeypatch.setattr(h, "STATE", tmp_path / "data" / "research_health_state.json")
    breaches, m = h.collect(NOW)
    macro = [b for b in breaches if b.startswith("DATA-MACRO")]
    assert macro and "h old" in macro[0], breaches
    assert m["data_macro_age_h"] > 24 * 30


def test_the_fence_breaches_when_updated_is_absent(tmp_path: Path, monkeypatch) -> None:
    h = _load()
    desk = tmp_path / "desk"
    (desk / "data").mkdir(parents=True)
    _write(desk / "data" / "macro_state.json", {"series": {}})
    monkeypatch.setattr(h, "DESK", desk)
    monkeypatch.setattr(h, "ROOT", tmp_path)
    monkeypatch.setattr(h, "STATE", tmp_path / "data" / "research_health_state.json")
    breaches, m = h.collect(NOW)
    macro = [b for b in breaches if b.startswith("DATA-MACRO")]
    assert macro and "parseable `updated`" in macro[0], breaches
    assert m["data_macro_age_h"] is None
