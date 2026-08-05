"""The seat-calibration market was reading keys that do not exist, and calling the result healthy.

Found 2026-08-05 while verifying R0189 (panel aggregation -> calibrated soft voting). `_market()`
asked data/panel_verdicts.jsonl for `seat`/`claim`/`confidence` and a BOOLEAN `outcome`; that file
has carried `provider`/`finding`/`verdict` and a STRING `outcome` for all 47 of its rows since it
was created. Every row was dropped, and data/ancestors.json then published

    "weights are UNIFORM because no claim has settled yet. That is the correct output, not a
     limitation"

while five rows said "validated". Nothing had settled because nothing was ever READ. The note is
the failure path's own output, which is why no artifact reader could have caught it -- the
UNMEASURED-REPORTED-AS-OK lens (L1.40) pointed at a calibration input.

These tests pin the parse AND the honesty of the note, because fixing only the parse would leave
the same class of defect one layer down: an empty market that still cannot say why it is empty.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[2] / "scripts/run_ancestors.py"


def _mod():
    spec = importlib.util.spec_from_file_location("run_ancestors_under_test", _SRC)
    assert spec and spec.loader
    m = importlib.util.module_from_spec(spec)
    sys.modules["run_ancestors_under_test"] = m
    spec.loader.exec_module(m)
    return m


@pytest.fixture
def ra():
    return _mod()


def _write(tmp_path: Path, rows: list[dict]) -> Path:
    p = tmp_path / "panel_verdicts.jsonl"
    p.write_text("".join(json.dumps(r) + "\n" for r in rows), "utf-8")
    return p


# --- the outcome vocabulary ------------------------------------------------------------------

def test_only_the_declared_scoring_terms_settle_a_claim(ra):
    """panel_scorecard.json's own policy is hit_rate = validated/(validated+falsified). Widening
    that vocabulary here would be the desk grading its own homework, so it is not widened."""
    assert ra._settled("validated") is True
    assert ra._settled("falsified") is False
    assert ra._settled(True) is True and ra._settled(False) is False


def test_an_unresolved_outcome_is_a_THIRD_state_not_a_quiet_false(ra):
    """The 47-row file carries 22+ distinct outcome strings, most of them unresolved. Reading an
    unrecognised value as False would score every seat as WRONG for not having resolved yet."""
    for unresolved in ("pending", "rowed", "triaged-degraded-run", "implemented-2026-07-21",
                       "duplicate-gap37", "", None, "some whole sentence about a run"):
        assert ra._settled(unresolved) is None, f"{unresolved!r} must not settle anything"


# --- the parse -------------------------------------------------------------------------------

def test_the_real_on_disk_schema_is_read_not_dropped(ra, tmp_path, monkeypatch):
    """The regression itself: provider/finding/string-outcome rows must reach the market."""
    monkeypatch.setattr(ra, "VERDICTS", _write(tmp_path, [
        {"ts": "2026-07-31T17:00:00Z", "provider": "nvidia/nemotron", "mission": "tier1",
         "finding": "synthesizer-zero-yield-audit", "verdict": "QUEUE-R0151",
         "outcome": "validated"},
        {"ts": "2026-07-31T17:00:00Z", "provider": "cohere", "mission": "audit",
         "finding": "another-finding", "verdict": "flag", "outcome": "pending"},
    ]))
    out = ra._market()
    assert out["rows_parsed"] == 2, "both rows carry provider+finding and must parse"
    assert out["settled_claims"] == 1, "'validated' settles; 'pending' does not"


def test_the_legacy_schema_still_parses(ra, tmp_path, monkeypatch):
    """A writer emitting the shape the old code assumed must not start being dropped in turn --
    the fix widens the reader, it does not swap one exclusive schema for another."""
    monkeypatch.setattr(ra, "VERDICTS", _write(tmp_path, [
        {"seat": "grok", "claim": "c1", "confidence": 0.8, "outcome": True},
        {"seat": "grok", "claim": "c2", "confidence": 0.3, "outcome": False},
    ]))
    out = ra._market()
    assert out["stakes"] == 2 and out["settled_claims"] == 2
    assert out["records"]["grok"]["settled"] == 2


def test_a_boolean_is_never_mistaken_for_a_confidence(ra, tmp_path, monkeypatch):
    """bool is a subclass of int in Python, so `isinstance(p, int|float)` accepts True as p=1.0 --
    a seat that never stated a probability would be recorded as having claimed certainty."""
    monkeypatch.setattr(ra, "VERDICTS", _write(tmp_path, [
        {"provider": "s", "finding": "c", "confidence": True, "outcome": "validated"}]))
    out = ra._market()
    assert out["stakes"] == 0, "True is not a confidence of 1.0"
    assert out["rows_without_confidence"] == 1


# --- the note --------------------------------------------------------------------------------

def test_the_note_refuses_to_blame_time_for_a_missing_field(ra, tmp_path, monkeypatch):
    """'no claim has settled yet' is a fact time fixes; 'no seat states a confidence' is a defect
    time never fixes. Publishing the first when the second is true is what hid this for weeks."""
    monkeypatch.setattr(ra, "VERDICTS", _write(tmp_path, [
        {"provider": "nvidia", "finding": "f1", "verdict": "flag", "outcome": "validated"},
        {"provider": "cohere", "finding": "f2", "verdict": "flag", "outcome": "pending"},
    ]))
    out = ra._market()
    assert out["stakes"] == 0 and out["rows_without_confidence"] == 2
    assert "no claim has settled yet" not in out["note"]
    assert "ZERO stakes" in out["note"] and "confidence" in out["note"]
    assert str(out["rows_parsed"]) in out["note"], "the note must carry the counts it claims"


def test_an_empty_file_still_gets_the_honest_time_will_fix_it_note(ra, tmp_path, monkeypatch):
    """With genuinely nothing on disk, uniform-with-no-record IS the correct report. That half of
    the original behaviour was right and must survive the fix."""
    monkeypatch.setattr(ra, "VERDICTS", _write(tmp_path, []))
    out = ra._market()
    assert out["rows_parsed"] == 0 and out["settled_claims"] == 0
    assert "no claim has settled yet" in out["note"]


def test_weights_stay_uniform_until_a_seat_has_a_real_record(ra, tmp_path, monkeypatch):
    """Parsing more rows must not manufacture authority. Below MIN_SETTLED the market is still
    uniform -- an unproven seat is unproven, not disbelieved."""
    monkeypatch.setattr(ra, "VERDICTS", _write(tmp_path, [
        {"seat": "a", "claim": "c1", "confidence": 0.9, "outcome": True},
        {"seat": "b", "claim": "c1", "confidence": 0.1, "outcome": True},
    ]))
    w = ra._market()["weights"]
    assert set(w) == {"a", "b"}
    assert w["a"] == w["b"], "one settled claim is not a record; weights must stay uniform"
