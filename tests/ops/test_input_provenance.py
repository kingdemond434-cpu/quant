"""Tests for the transitive-freshness recorder (L1.55).

THE DISTINCTIONS ARE THE PRODUCT. This module exists because `_load(path, default)` collapsed
four different situations -- read it, read something old, the file is missing, the file is
corrupt -- into one silent default, and a desk that cannot tell them apart debugs the wrong
organ. So the tests assert the distinctions hold, and that the rollup fails in the loud
direction: an artifact with nothing declared must never read OK (L1.28a).
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.ops.input_provenance import (  # noqa: E402
    ABSENT,
    DEFAULTED,
    DEGRADED,
    OK,
    STALE,
    UNMEASURED,
    UNREADABLE,
    Inputs,
)


def _write(p: Path, obj: object) -> Path:
    p.write_text(json.dumps(obj), "utf-8")
    return p


def test_zero_declared_inputs_is_unmeasured_never_ok(tmp_path: Path) -> None:
    """L1.28a: an organ that declares nothing is indistinguishable from one that measured
    nothing, and the safe reading of that ambiguity is the loud one."""
    assert Inputs("nobody").status() == UNMEASURED
    assert Inputs("nobody").measured() is False


def test_absent_is_distinct_from_unreadable(tmp_path: Path) -> None:
    """The two demand opposite responses: ABSENT means no producer has ever run, UNREADABLE
    means one ran and wrote garbage. The idiom this replaces conflated them."""
    missing = Inputs("c")
    missing.read_json(tmp_path / "never_written.json", default={})
    assert missing.block()[0]["status"] == ABSENT

    corrupt = Inputs("c")
    (tmp_path / "torn.json").write_text("{not json", "utf-8")
    corrupt.read_json(tmp_path / "torn.json", default={})
    assert corrupt.block()[0]["status"] == UNREADABLE

    assert missing.status() == UNMEASURED and corrupt.status() == UNMEASURED


def test_read_returns_the_default_exactly_as_the_idiom_it_replaces(tmp_path: Path) -> None:
    """Adoption must not require restructuring a call site: the return contract is unchanged,
    only the absence is now written down."""
    inp = Inputs("c")
    sentinel = {"floor": 0.10}
    assert inp.read_json(tmp_path / "gone.json", default=sentinel) is sentinel


def test_stale_degrades_but_does_not_unmeasure(tmp_path: Path) -> None:
    """An old measurement is still a measurement -- DEGRADED, not UNMEASURED."""
    p = _write(tmp_path / "old.json", {"generated": "2020-01-01T00:00:00+00:00", "v": 1})
    inp = Inputs("c")
    inp.read_json(p, max_age_h=1.0)
    assert inp.block()[0]["status"] == STALE
    assert inp.status() == DEGRADED
    assert inp.measured() is True


def test_fresh_content_stamp_outranks_mtime(tmp_path: Path) -> None:
    """A deploy rewrites files, so mtime lies FRESH -- the dangerous direction. The artifact's
    own stamp wins where it has one."""
    p = _write(tmp_path / "stamped.json", {"generated": "2020-01-01T00:00:00+00:00"})
    p.touch()                                   # mtime is NOW; the stamp says years ago
    inp = Inputs("c")
    inp.read_json(p, max_age_h=24.0)
    assert inp.block()[0]["status"] == STALE, "mtime must not override the content stamp"


def test_epoch_seconds_stamp_is_understood(tmp_path: Path) -> None:
    p = _write(tmp_path / "e.json", {"ts": time.time() - 7200})
    inp = Inputs("c")
    inp.read_json(p, max_age_h=1.0)
    assert inp.block()[0]["status"] == STALE


def test_ok_only_when_every_input_read(tmp_path: Path) -> None:
    p = _write(tmp_path / "good.json", {"generated": "2020-01-01T00:00:00+00:00"})
    inp = Inputs("c")
    inp.read_json(p)                            # no max_age declared -> age cannot fail it
    assert inp.status() == OK


def test_defaulted_unmeasures_even_though_a_value_exists(tmp_path: Path) -> None:
    """The state that makes a fresh stamp a lie: a number nobody read from anywhere."""
    inp = Inputs("c")
    inp.defaulted("size_fraction", "ladder constant substituted")
    assert inp.block()[0]["status"] == DEFAULTED
    assert inp.status() == UNMEASURED


def test_optional_input_absence_does_not_unmeasure(tmp_path: Path) -> None:
    """required=False is how a caller says 'nice to have'. Without it every optional enrichment
    would unmeasure an artifact and the fence would cry wolf (L1.43)."""
    good = _write(tmp_path / "core.json", {"v": 1})
    inp = Inputs("c")
    inp.read_json(good)
    inp.read_json(tmp_path / "extra.json", required=False)
    assert inp.status() == DEGRADED
    assert inp.measured() is True
    assert inp.fabricated() == []


def test_derived_is_the_refusal_path(tmp_path: Path) -> None:
    """A caller routing published numbers through derived() cannot print a default as a
    finding -- the entire defect this module exists to prevent."""
    inp = Inputs("c")
    inp.read_json(tmp_path / "absent.json", default={})
    assert inp.derived(0.10) is None
    assert inp.derived(0.10, unmeasured="UNMEASURED") == "UNMEASURED"

    ok = Inputs("c")
    ok.read_json(_write(tmp_path / "there.json", {"v": 1}))
    assert ok.derived(0.10) == 0.10


def test_why_names_the_absent_artifact(tmp_path: Path) -> None:
    """A verdict that does not name the file sends the reader hunting."""
    inp = Inputs("c")
    inp.read_json(tmp_path / "ramp_state.json", default={})
    assert "ramp_state.json" in inp.why() and "ABSENT" in inp.why()
    assert inp.fabricated() == [str(tmp_path / "ramp_state.json")]


def test_worst_case_rollup_across_many_inputs(tmp_path: Path) -> None:
    """One absent input among many good ones must decide the verdict."""
    inp = Inputs("c")
    for n in ("a", "b", "c"):
        inp.read_json(_write(tmp_path / f"{n}.json", {"v": 1}))
    assert inp.status() == OK
    inp.read_json(tmp_path / "missing.json", default={})
    assert inp.status() == UNMEASURED
