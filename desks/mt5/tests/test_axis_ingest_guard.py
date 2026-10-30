"""AN EMPTY FETCH MUST NEVER OVERWRITE A POPULATED AXIS.

Measured 2026-09-24: `desks/mt5/data/axes/fred.json` on the trading box was 893 bytes and thirty
minutes old, refreshed faithfully every hour, beside `bis.json` at 85.9 MB, `cot.json` at 1.1 MB
and `ecb.json` at 786 KB -- all four written by the same driver on the same clock. The lane was
not idle. It was diligently rewriting a populated axis into an empty one, every hour, and nothing
anywhere read as broken because the file kept getting newer.

The mechanism, and it is worth naming exactly because the shape recurs: `ingest_fred` catches
every per-series exception, so it NEVER raises. The driver's `except` -- whose comment already
says "the previous per-axis file on disk still stands" -- therefore never fires. The success path
computes `state = "OK" if n else "EMPTY"`, a verdict nothing consumes, and writes the empty
document anyway. Absence resolved into a confident verdict, with a timestamp on it.

Pinned here:

  1. An empty pass over a populated file writes NOTHING and says so (`EMPTY_REFUSED_OVERWRITE`),
     with the count it preserved -- a non-write is a positive, dated fact, never a silence.
  2. An empty pass over an axis that has NEVER landed still writes its failure record, because
     that record is the only evidence the next session gets. It is how this defect was found.
  3. A populated pass writes normally, and the guard can never become a reason not to refresh.
  4. The write is ATOMIC, so a crash mid-write cannot truncate an axis by the slower route.
  5. The FRED fetch carries its own allowlisted client token, scoped to FRED so the three axes
     that were working on the shared one keep working.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import axis_ingest_all as A  # noqa: E402

POPULATED = {"axis": "macro_state", "n_series": 7, "series": {"DGS10": {"n": 900}}}
EMPTY = {"axis": "macro_state", "n_series": 0, "n_failed": 7,
         "failed": {"DGS10": "TimeoutError: The read operation timed out"}}


def test_an_empty_pass_never_replaces_a_populated_axis(tmp_path: Path) -> None:
    """THE RULE. The fetch came back empty; the world did not."""
    target = tmp_path / "fred.json"
    target.write_text(json.dumps(POPULATED), encoding="utf-8")

    out = A._write_axis(target, EMPTY, 0)

    assert out["written"] is False
    assert out["write_state"] == "EMPTY_REFUSED_OVERWRITE"
    assert out["preserved_n"] == 7
    assert json.loads(target.read_text(encoding="utf-8"))["n_series"] == 7, (
        "the populated axis was overwritten -- this is the whole defect")


def test_the_refusal_is_a_recorded_fact_not_a_silence(tmp_path: Path) -> None:
    """A guard that quietly does nothing is the same class of invisible as the bug it replaced."""
    target = tmp_path / "fred.json"
    target.write_text(json.dumps(POPULATED), encoding="utf-8")

    out = A._write_axis(target, EMPTY, 0)

    assert "never overwrites a populated axis" in out["why"]
    assert "7" in out["why"], "the preserved count belongs in the reason"


def test_an_axis_that_never_landed_still_records_its_failure(tmp_path: Path) -> None:
    """The 893-byte fred.json IS the evidence that found this bug. Refusing to write a first
    failure record would trade one blindness for another."""
    target = tmp_path / "fred.json"

    out = A._write_axis(target, EMPTY, 0)

    assert out["written"] is True
    assert out["write_state"] == "WRITTEN_FIRST_RECORD"
    assert json.loads(target.read_text(encoding="utf-8"))["n_failed"] == 7


def test_a_populated_pass_writes_normally(tmp_path: Path) -> None:
    """The guard may never become a reason not to refresh a working axis."""
    target = tmp_path / "fred.json"
    target.write_text(json.dumps({"n_series": 3}), encoding="utf-8")

    out = A._write_axis(target, POPULATED, 7)

    assert out["written"] is True and out["write_state"] == "WRITTEN"
    assert json.loads(target.read_text(encoding="utf-8"))["n_series"] == 7


def test_a_corrupt_previous_file_does_not_freeze_the_lane(tmp_path: Path) -> None:
    """An unreadable document is not evidence of data worth protecting. Treating it as such would
    pin a broken axis in place forever, which is a worse failure than the one being fixed."""
    target = tmp_path / "fred.json"
    target.write_text("{not json at all", encoding="utf-8")

    assert A._on_disk(target) == 0
    assert A._write_axis(target, POPULATED, 7)["written"] is True


def test_the_write_leaves_no_temp_file_behind(tmp_path: Path) -> None:
    """Atomic via tmp+replace: the temp must not survive a successful write, or the next pass
    inherits a directory that grows without bound."""
    target = tmp_path / "cot.json"

    A._write_axis(target, POPULATED, 7)

    assert target.exists()
    assert list(tmp_path.glob("*.tmp")) == []


def test_run_all_reports_the_refusals_it_made(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                              ) -> None:
    """The driver's report is where an operator meets this. A refusal that is not in the report
    is a refusal nobody learns about."""
    monkeypatch.setattr(A, "OUT_DIR", tmp_path)
    (tmp_path / "fred.json").write_text(json.dumps(POPULATED), encoding="utf-8")

    import types
    stub = types.ModuleType("axis_ingest")
    stub.INGESTERS = {"fred": lambda: EMPTY, "cot": lambda: {"n_rows": 4060}}  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "axis_ingest", stub)
    doc = A.run_all(apply=True)

    assert doc["n_write_refused"] == 1 and doc["write_refused"] == ["fred"]
    assert doc["axes"]["fred"]["write_state"] == "EMPTY_REFUSED_OVERWRITE"
    assert doc["axes"]["cot"]["written"] is True
    assert json.loads((tmp_path / "fred.json").read_text(encoding="utf-8"))["n_series"] == 7


def test_the_fred_token_is_scoped_and_prefixed() -> None:
    """MEASURED on the box: the publisher's edge allowlists the FIRST token of the User-Agent and
    tarpits anything else -- no HTTP status, so it arrives as a timeout and reads like a network
    fault. The desk's own identity stays as the second token so the publisher can still see who
    is asking, and the shared `UA` is untouched because BIS, COT and ECB work on it."""
    from research import axis_ingest as ai

    assert ai.FRED_UA.split()[0] == "curl/8.4.0"
    assert "quant-desk-axis-ingest" in ai.FRED_UA, (
        "the allowlisted token is PREFIXED, never substituted -- the desk still identifies itself")
    assert ai.UA == "quant-desk-axis-ingest/1.0 (research)", (
        "the shared token must not change: three axes were ingesting 85.9 MB, 1.1 MB and 786 KB "
        "on it, and a global change would risk them to repair a fourth")
    src = (_DESK / "research" / "axis_ingest.py").read_text(encoding="utf-8")
    fred_call = src.split("def ingest_fred", 1)[1]
    assert 'headers={"User-Agent": FRED_UA}' in fred_call, (
        "ingest_fred must send the scoped token, not the shared one")
    assert 'headers={"User-Agent": UA}' in src.split("def ingest_fred", 1)[0], (
        "the other ingesters must still send the shared token")
