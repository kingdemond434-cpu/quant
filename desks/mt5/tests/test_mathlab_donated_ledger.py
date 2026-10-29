"""A row the donation door refused is never marked donated (the 10-13 math/physics lab silence).

The labs kept a "donated once, never again" ledger of what they OFFERED to
`proposer_common.donate`. Every row a door turned away (wrong lane, no PIT stamp) was marked
too, so one refusing pass burned those objects for good and a deterministic lab that finds the
same objects again donated nothing, every pass, with exit 0. These pin: only written rows are
marked, a v1 ledger is rebuilt from the files actually written, and a zero pass names its cause.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_DESK = str(Path(__file__).resolve().parents[1])
if _DESK not in sys.path:
    sys.path.insert(0, _DESK)

from research import math_lab as ML  # noqa: E402
from research import proposer_common as PC  # noqa: E402


def test_only_rows_the_door_wrote_are_marked(tmp_path: Path,
                                             monkeypatch: pytest.MonkeyPatch) -> None:
    ledger = tmp_path / "donated.json"
    monkeypatch.setattr(PC, "LAST_WRITTEN", [{"mathlab_object_id": "kept"}])
    ML.mark_donated(ledger, {"old"})
    doc = json.loads(ledger.read_text("utf-8"))
    assert doc["version"] == ML.DONATED_LEDGER_VERSION
    assert doc["object_ids"] == ["kept", "old"]
    ids, how = ML.load_donated(ledger, "mathlab")
    assert ids == {"kept", "old"} and how == {"ledger": "v2"}


def test_donate_that_refuses_everything_writes_nothing_to_mark(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(PC, "_blinded", lambda s, c: (c, {}))
    monkeypatch.setattr(PC, "_lane_filtered", lambda c: ([], c))
    assert PC.donate("mathlab", [{"mathlab_object_id": "x"}], tests_run=1) is None
    assert PC.donated_rows() == []


def test_a_v1_ledger_is_rebuilt_from_the_files_written(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(PC, "INTEL", tmp_path / "intel")
    seat = tmp_path / "intel" / "mathlab"
    seat.mkdir(parents=True)
    (seat / "discoveries_20261010_1800.json").write_text(json.dumps(
        {"discoveries": [{"mathlab_object_id": "written"}]}), "utf-8")
    ledger = tmp_path / "donated.json"
    ledger.write_text(json.dumps({"object_ids": ["written", "refused_1", "refused_2"]}), "utf-8")
    ids, how = ML.load_donated(ledger, "mathlab")
    assert ids == {"written"}
    assert how["reoffered"] == 2 and how["files_read"] == 1


def test_no_ledger_yet_is_empty_and_reads_no_files(tmp_path: Path) -> None:
    assert ML.load_donated(tmp_path / "absent.json", "mathlab") == (set(), {"ledger": "new"})


@pytest.mark.parametrize(("rows", "donated", "already", "refused", "want"), [
    (5, 5, 0, 0, "DONATED"),
    (5, 0, 0, 0, "REFUSED_AT_THE_DOOR"),
    (0, 0, 132, 0, "NOTHING_NEW"),
    (0, 0, 0, 3, "NOTHING_TRADEABLE"),
    (0, 0, 0, 0, "NO_SURVIVORS"),
])
def test_a_pass_names_why_it_gave_what_it_gave(rows: int, donated: int, already: int,
                                               refused: int, want: str) -> None:
    assert ML.donation_status(rows, donated, already, refused) == want
