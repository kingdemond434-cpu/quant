"""Behaviour tests for the frozen-value analyser (L1.66).

THE POSITIVE CONTROLS IN THIS FILE ARE THE POINT, and they exist because the first version of
this analyser reported **0 frozen reads across 13 live daemons** -- a clean, confident, entirely
false null. It scored 0 of 3 against sites verified by hand minutes earlier. A detector that has
never been shown to FIND a known-present defect has not been validated; only its silences have
been observed (``certify_gauntlet.py``, and the desk lesson behind it).

So every shape this module claims to detect is pinned by a fixture that CONTAINS that shape, and
every shape it claims NOT to flag is pinned by a fixture that contains the correct pattern.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from libs.ops import value_staleness as vs


def _mod(tmp_path: Path, name: str, src: str) -> Path:
    p = tmp_path / name
    p.write_text(src, "utf-8")
    return p


# -- positive controls: the shapes this fence exists to find ---------------------------------
def test_module_scope_read_is_frozen(tmp_path: Path) -> None:
    """The base case: a value bound at import from an artifact."""
    m = _mod(tmp_path, "a.py", 'import json\nfrom pathlib import Path\n'
                               '_P = "data/capacity_floor.json"\n'
                               '_V = json.loads(Path(_P).read_text("utf-8"))\n')
    found = vs._Analyser(tmp_path).frozen_reads(m)
    assert [f.name for f in found] == ["_V"]
    assert found[0].kind == "module-scope"
    assert "data/capacity_floor.json" in found[0].artifacts
    assert found[0].resolved


def test_read_through_an_imported_function_is_found(tmp_path: Path) -> None:
    """REGRESSION -- the bug that made the first prototype score 0 of 3.

    Reading functions were resolved only WITHIN the module under analysis, so the dominant real
    shape (``from libs.x import f`` at the top, ``_V = f()`` below) was invisible and the
    analyser returned a confident zero.
    """
    (tmp_path / "libs").mkdir()
    (tmp_path / "libs" / "__init__.py").write_text("", "utf-8")
    (tmp_path / "libs" / "cap.py").write_text(
        'import json\nfrom pathlib import Path\n'
        'def floor():\n    return json.loads(Path("data/capacity_floor.json").read_text())\n',
        "utf-8")
    m = _mod(tmp_path, "b.py", "from libs.cap import floor\n_V = floor()\n")
    found = vs._Analyser(tmp_path).frozen_reads(m)
    assert [f.name for f in found] == ["_V"], "cross-module read resolution regressed"
    assert "data/capacity_floor.json" in found[0].artifacts


def test_memoized_reader_is_frozen(tmp_path: Path) -> None:
    m = _mod(tmp_path, "c.py", 'import json\nfrom functools import lru_cache\nfrom pathlib '
                               'import Path\n@lru_cache\ndef settings():\n'
                               '    return json.loads(Path("data/x.json").read_text())\n')
    found = vs._Analyser(tmp_path).frozen_reads(m)
    assert [(f.name, f.kind) for f in found] == [("settings", "memoized")]


def test_default_argument_binding_is_double_frozen(tmp_path: Path) -> None:
    """A default is evaluated once, at definition -- so even a caller that re-read cannot retune."""
    m = _mod(tmp_path, "d.py", 'import json\nfrom pathlib import Path\n'
                               'FLOORS = json.loads(Path("data/floors.json").read_text())\n'
                               'def apply(w, floors=FLOORS):\n    return w\n')
    kinds = {(f.name, f.kind) for f in vs._Analyser(tmp_path).frozen_reads(m)}
    assert ("FLOORS", "module-scope") in kinds
    assert ("apply(...=FLOORS)", "default-arg") in kinds


# -- negative controls: what must NOT be flagged ----------------------------------------------
def test_a_read_inside_a_function_is_not_frozen(tmp_path: Path) -> None:
    """The desk's own positive control -- the ``_live_params`` shape -- must be invisible here."""
    m = _mod(tmp_path, "e.py", 'import json\nfrom pathlib import Path\n'
                               'def live_params():\n'
                               '    p = Path("data/cashcarry_config.json")\n'
                               '    return json.loads(p.read_text())\n')
    assert vs._Analyser(tmp_path).frozen_reads(m) == []


def test_seed_with_a_live_reread_path_is_refreshed_not_stale(tmp_path: Path) -> None:
    """REGRESSION -- 2 of the first run's 4 findings were this false positive.

    ``run_recorder.py`` seeds ``_SYMBOLS = _universe()`` at import AND re-polls ``_universe()``
    inside its loop. Reporting the seed as frozen would have made the fence wrong on two of
    three recorders on its first run, and a detector that cries wolf gets acked into silence.
    """
    m = _mod(tmp_path, "f.py", 'import json\nfrom pathlib import Path\n'
                               'def universe():\n'
                               '    return json.loads(Path("data/positions.json").read_text())\n'
                               '_SYMBOLS = universe()\n'
                               'def main():\n'
                               '    while True:\n'
                               '        fresh = universe()\n')
    found = [f for f in vs._Analyser(tmp_path).frozen_reads(m) if f.name == "_SYMBOLS"]
    assert len(found) == 1
    assert found[0].refresh_line, "a producer re-run inside a function body is a live re-read path"

    d = vs.Daemon("f.py", (1,), started=time.time(), age_h=5.0)
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "positions.json").write_text("{}", "utf-8")
    assert vs._grade(d, found[0], tmp_path, time.time())[0].status == vs.REFRESHED


def test_no_reread_path_stays_frozen(tmp_path: Path) -> None:
    """The bybit shape: same seed, no refresh in the loop. This one IS the defect."""
    m = _mod(tmp_path, "g.py", 'import json\nfrom pathlib import Path\n'
                               'def universe():\n'
                               '    return json.loads(Path("data/positions.json").read_text())\n'
                               '_SYMBOLS = universe()\n'
                               'def main():\n'
                               '    for s in _SYMBOLS:\n        pass\n')
    found = [f for f in vs._Analyser(tmp_path).frozen_reads(m) if f.name == "_SYMBOLS"]
    assert len(found) == 1
    assert not found[0].refresh_line


# -- the refusal paths ------------------------------------------------------------------------
@pytest.mark.parametrize("status", [vs.UNVERIFIABLE, vs.UNRESOLVED, vs.UNMEASURED,
                                    vs.NO_DAEMONS_HERE])
def test_refusal_statuses_are_structurally_absent_from_passing(status: str) -> None:
    """UNMEASURED must never read as fine (L1.28a). Pinned structurally, not by inspection."""
    assert status not in vs.PASSING


def test_unresolvable_artifact_is_counted_never_dropped(tmp_path: Path) -> None:
    """REGRESSION -- WS-005, committed by the instrument built to detect a cousin of it.

    The prototype ``continue``d past a read whose artifact it could not resolve, which makes
    "I could not tell" and "there is nothing here" byte-identical to every reader.
    """
    fr = vs.FrozenRead("m.py", "_V", 3, "module-scope", artifacts=())
    d = vs.Daemon("m.py", (1,), started=time.time(), age_h=5.0)
    pairs = vs._grade(d, fr, tmp_path, time.time())
    assert [p.status for p in pairs] == [vs.FROZEN_UNRESOLVED]


def test_source_drift_refuses_a_value_verdict(tmp_path: Path) -> None:
    """REGRESSION -- the false green this fence would otherwise create with its own repairs.

    Every verdict is derived from source on disk while the claim is about a running process.
    Patch a frozen read into a refreshing one and the fence would flip green the instant the
    file is saved, while the daemon holds the old value until restart -- L0004 with a checkmark.
    """
    m = _mod(tmp_path, "h.py", "_V = 1\n")
    fr = vs.FrozenRead("h.py", "_V", 1, "module-scope", artifacts=("data/x.json",))
    started = m.stat().st_mtime - 3600          # process predates the edit
    d = vs.Daemon("h.py", (1,), started=started, age_h=2.0)
    pairs = vs._grade(d, fr, tmp_path, time.time())
    assert [p.status for p in pairs] == [vs.SOURCE_DRIFTED]


def test_exemption_requires_a_reason(tmp_path: Path) -> None:
    """A bare tag is not a tag -- mirrors L1.60's ``attrition-ok``."""
    assert vs._exempt_reason(["x = 1  # frozen-ok:"], 1) == ""
    assert vs._exempt_reason(["x = 1  # frozen-ok: schema constant"], 1) == "schema constant"


def test_no_daemons_is_a_refusal_not_a_pass(tmp_path: Path, monkeypatch: pytest.MonkeyPatch
                                            ) -> None:
    """Off the box there is nothing running; that is a statement about the vantage point."""
    monkeypatch.setattr(vs, "live_daemons", lambda *a, **k: ([], 7, 7))
    rep = vs.build_report(tmp_path)
    assert rep.status == vs.NO_DAEMONS_HERE
    assert rep.status not in vs.PASSING
    assert rep.notes


def test_daemons_but_zero_pairs_reads_unmeasured(tmp_path: Path,
                                                 monkeypatch: pytest.MonkeyPatch) -> None:
    """The exact state the broken prototype produced. It must never render as a clean desk."""
    (tmp_path / "q.py").write_text("x = 1\n", "utf-8")
    monkeypatch.setattr(vs, "live_daemons",
                        lambda *a, **k: ([vs.Daemon("q.py", (1,), time.time(), 5.0)], 3, 0))
    rep = vs.build_report(tmp_path)
    assert rep.status == vs.UNMEASURED
    assert rep.status not in vs.PASSING
    assert any("ZERO frozen reads" in n for n in rep.notes)


def test_proc_start_is_not_the_procfs_directory_mtime() -> None:
    """L0070: ``Path('/proc/<pid>').stat().st_mtime`` reads ~now for any polled process.

    That is what welded ``check_stale_daemons`` shut for ten days, and this module carries a
    second copy of the correct parse. Our own pid has a real start time in the past.
    """
    import os as _os
    started = vs.proc_start(_os.getpid())
    assert started is not None
    assert 0 < time.time() - started < 86400 * 365
    assert vs.proc_start(2 ** 30) is None, "an exited pid returns None rather than raising"


def test_attrition_is_counted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """L1.60: a denominator that loses members in silence is a coverage claim we cannot cash."""
    (tmp_path / "bad.py").write_text("def (\n", "utf-8")       # unparseable
    monkeypatch.setattr(vs, "live_daemons",
                        lambda *a, **k: ([vs.Daemon("bad.py", (1,), time.time(), 5.0)], 4, 1))
    rep = vs.build_report(tmp_path)
    assert rep.attempted >= 4
    assert rep.skipped >= 2, "an unparseable module must land in attrition, not vanish"
