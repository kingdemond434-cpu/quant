"""Tests for the point-in-time vintage store (R0316).

THE ONE PROPERTY EVERYTHING ELSE SERVES: reading the panel at an earlier date must return the
value that was known THEN, not the value that is known now. Every other test here exists to stop
some plausible implementation from quietly returning today's number -- because a store that
back-fills is worse than no store at all: it looks like point-in-time discipline while delivering
exactly the look-ahead the discipline exists to remove.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest

from libs.research.vintage import (
    as_of,
    latest_known,
    read_log,
    record,
    revisions,
    summarise,
)

# The Receita Federal shape, which is what the store was measured against: a month first published
# low, then revised UP months later as late filings arrive.
_V1 = "2026-08-10"
_V2 = "2026-08-11"


@pytest.fixture
def store(tmp_path: Path) -> Path:
    record(tmp_path, "M2SL", {"2026-05-01": 21000.0, "2026-06-01": 21500.0}, vintage=_V1)
    record(
        tmp_path,
        "M2SL",
        {"2026-05-01": 21000.0, "2026-06-01": 21987.3, "2026-07-01": 22100.0},
        vintage=_V2,
    )
    return tmp_path


# ------------------------------------------------------------------------------- as_of semantics --
def test_as_of_returns_the_unrevised_value(store: Path) -> None:
    """THE WHOLE POINT. On 08-10 June read 21500; the 21987.3 restatement did not exist yet."""
    assert as_of(store, "M2SL", _V1) == {"2026-05-01": 21000.0, "2026-06-01": 21500.0}


def test_as_of_picks_up_the_revision_on_its_own_vintage(store: Path) -> None:
    assert as_of(store, "M2SL", _V2) == {
        "2026-05-01": 21000.0,
        "2026-06-01": 21987.3,
        "2026-07-01": 22100.0,
    }


def test_a_period_not_yet_published_is_absent_not_zero(store: Path) -> None:
    """July did not exist on 08-10. Absent and zero are different claims (L1.28a)."""
    assert "2026-07-01" not in as_of(store, "M2SL", _V1)


def test_before_any_vintage_nothing_is_knowable(store: Path) -> None:
    assert as_of(store, "M2SL", "2026-08-09") == {}


def test_as_of_after_the_last_vintage_matches_current_belief(store: Path) -> None:
    assert as_of(store, "M2SL", "2030-01-01") == latest_known(store, "M2SL")


def test_as_of_accepts_a_full_timestamp(store: Path) -> None:
    """Collectors stamp an ISO instant; readers ask by date. Both must key the same day."""
    assert as_of(store, "M2SL", "2026-08-10T23:59:59+00:00") == as_of(store, "M2SL", _V1)


# --------------------------------------------------------------------------- the append-only log --
def test_only_changed_values_are_appended(store: Path) -> None:
    """Re-recording an unchanged panel must cost nothing, or keeping every vintage is
    unaffordable.
    """
    before = len(read_log(store, "M2SL"))
    written = record(
        store,
        "M2SL",
        {"2026-05-01": 21000.0, "2026-06-01": 21987.3, "2026-07-01": 22100.0},
        vintage="2026-08-12",
    )
    assert written == 0
    assert len(read_log(store, "M2SL")) == before


def test_the_first_vintage_records_everything(tmp_path: Path) -> None:
    assert record(tmp_path, "X", {"2026-01-01": 1.0, "2026-02-01": 2.0}, vintage=_V1) == 2


def test_a_tiny_revision_is_still_a_revision(tmp_path: Path) -> None:
    """Rounding to a tolerance would drop the smallest revisions -- the half nobody would notice."""
    record(tmp_path, "X", {"2026-01-01": 100.0}, vintage=_V1)
    assert record(tmp_path, "X", {"2026-01-01": 100.00000001}, vintage=_V2) == 1


def test_history_survives_a_later_truncated_fetch(store: Path) -> None:
    """THE ROLLING-WINDOW TRAP. The collector truncates to ~1200 days; May must not vanish.

    An implementation that mirrored each fetch instead of logging revisions would silently drop
    every period that aged out of the source's window -- destroying exactly the deep history the
    store exists to preserve.
    """
    record(store, "M2SL", {"2026-07-01": 22100.0}, vintage="2026-08-12")
    assert as_of(store, "M2SL", "2026-08-12")["2026-05-01"] == 21000.0


def test_series_are_stored_separately(tmp_path: Path) -> None:
    record(tmp_path, "M2SL", {"2026-01-01": 1.0}, vintage=_V1)
    record(tmp_path, "WALCL", {"2026-01-01": 9.0}, vintage=_V1)
    assert as_of(tmp_path, "M2SL", _V1) == {"2026-01-01": 1.0}
    assert as_of(tmp_path, "WALCL", _V1) == {"2026-01-01": 9.0}


def test_a_series_id_cannot_escape_the_store_directory(tmp_path: Path) -> None:
    """Series ids come from config and one day will come from a source. Flatten, never traverse."""
    store = (tmp_path / "data" / "vintages").resolve()
    record(tmp_path, "../../etc/passwd", {"2026-01-01": 1.0}, vintage=_V1)
    written = list(store.glob("*.jsonl"))
    assert len(written) == 1
    # The property is CONTAINMENT, not the absence of dots in the name: a flattened
    # `.._.._etc_passwd.jsonl` sitting inside the store is exactly the intended outcome.
    assert written[0].resolve().parent == store
    assert not (tmp_path.parent / "etc" / "passwd").exists()


def test_a_trailing_partial_line_does_not_poison_the_log(store: Path) -> None:
    """Append-only means the only possible corruption is an unterminated final write."""
    path = store / "data" / "vintages" / "M2SL.jsonl"
    with path.open("a", encoding="utf-8") as fh:
        fh.write('{"series": "M2SL", "period": "2026-08-')
    assert as_of(store, "M2SL", _V2)["2026-06-01"] == 21987.3


# -------------------------------------------------------------------------- revisions and status --
def test_revisions_measures_the_move(store: Path) -> None:
    moved = revisions(store, "M2SL")
    assert [r["period"] for r in moved] == ["2026-06-01"]
    assert moved[0]["first"] == 21500.0 and moved[0]["latest"] == 21987.3
    assert moved[0]["n_revisions"] == 1
    assert moved[0]["pct_change"] == pytest.approx(2.2665, abs=1e-3)


def test_an_unrevised_series_reports_no_revisions(tmp_path: Path) -> None:
    """A source that never restates can be read at current vintage -- but say so from evidence."""
    record(tmp_path, "X", {"2026-01-01": 1.0}, vintage=_V1)
    record(tmp_path, "X", {"2026-01-01": 1.0, "2026-02-01": 2.0}, vintage=_V2)
    assert revisions(tmp_path, "X") == []


def test_no_history_is_unmeasured(tmp_path: Path) -> None:
    assert summarise(tmp_path, "NOPE")["status"] == "UNMEASURED"


def test_one_vintage_is_accruing_not_ok(tmp_path: Path) -> None:
    """ONE vintage cannot show a revision, so "none found" would describe the sample, not the
    source.
    """
    record(tmp_path, "X", {"2026-01-01": 1.0}, vintage=_V1)
    report = summarise(tmp_path, "X")
    assert report["status"] == "ACCRUING"
    assert report["n_vintages"] == 1


def test_two_vintages_can_be_graded(store: Path) -> None:
    report = summarise(store, "M2SL")
    assert report["status"] == "OK"
    assert report["n_vintages"] == 2 and report["n_revised_periods"] == 1


# -------------------------------------------------------------- the collector actually wires it --
def _load_collector() -> Any:
    path = Path(__file__).resolve().parents[2] / "scripts" / "collect_fred_macro.py"
    spec = importlib.util.spec_from_file_location("collect_fred_macro", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_collector_records_a_vintage_before_overwriting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """WIRED, NOT SHELVED. Until this, every run destroyed the previous vintage permanently.

    The archive write is a full overwrite AND the fetch truncates to a rolling window, so a store
    that is merely importable changes nothing. This drives main() with the network faked and
    asserts the log on disk.
    """
    collector = _load_collector()
    monkeypatch.setattr(collector, "_ROOT", tmp_path)
    monkeypatch.setattr(collector, "_ARCHIVE", tmp_path / "data" / "fred_macro.json")
    monkeypatch.setattr(collector, "_WEB", tmp_path / "web" / "fred_macro.json")
    monkeypatch.setattr(collector, "_SERIES", ("M2SL",))
    monkeypatch.setattr(collector, "_key", lambda: "fake-key-never-used")
    monkeypatch.setattr(collector, "_fetch", lambda key, sid: [("2026-06-01", 21500.0)])
    collector.main()

    assert latest_known(tmp_path, "M2SL") == {"2026-06-01": 21500.0}
    assert json.loads((tmp_path / "data" / "fred_macro.json").read_text())["series"]

    # Second run, same period revised UP: the archive is replaced, the vintage is not.
    monkeypatch.setattr(collector, "_fetch", lambda key, sid: [("2026-06-01", 21987.3)])
    collector.main()
    log = read_log(tmp_path, "M2SL")
    assert len(log) == 2, "the revision must be appended, not overwrite the first publication"
    assert log[0]["value"] == 21500.0 and log[1]["value"] == 21987.3
