"""The promotion gate must fail CLOSED -- an unchecked gate is not a passed gate.

libs/stage15/governance.alpha_governance_gate is the hard barrier into promotion and was
imported by nothing, so the barrier was assembled implicitly per screen. These tests pin the
one property that makes it worth wiring: missing evidence rejects. A safety gate whose
ambiguous branch ALLOWS the action is the defect class this codebase's auditor prompt ranks
first in its own measured history.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from scripts.promotion_gate import _GATES, evidence_to_gates, judge

_ALL = [k for _, k in _GATES]


def _full(**over):
    return {**dict.fromkeys(_ALL, True), **over}


def test_all_eight_gates_passing_accepts():
    assert judge("ok", _full())["accepted"] is True


def test_any_single_failure_rejects():
    for key in _ALL:
        d = judge(key, _full(**{key: False}))
        assert d["accepted"] is False, key


def test_missing_evidence_rejects_and_is_named():
    """The critical property: unchecked must never read as passed."""
    ev = {k: True for k in _ALL if k != "capacity"}
    d = judge("unchecked", ev)
    assert d["accepted"] is False
    assert "capacity" in d["missing_evidence"]
    assert "not passed" in d["note"]


def test_non_true_values_do_not_pass():
    """Truthy-but-not-True (1, 'yes') must not satisfy a safety gate."""
    for bad in (1, "yes", "true", [1]):
        assert evidence_to_gates(_full(dsr=bad))["dsr_passed"] is False


def test_empty_evidence_rejects_every_gate():
    d = judge("nothing", {})
    assert d["accepted"] is False
    assert len(d["rejected_reasons"]) == len(_ALL)


# --- R0353: the gate must never report a pass it did not compute -------------------------------
#
# The eight-gate barrier reported success every cycle while having judged ZERO candidates, for
# three compounding reasons: it read `data/gauntlet_survivors.json` (which nothing in the repo
# writes), it returned early WITHOUT writing an artifact when that file was missing, and it wrote
# to the same filename `scripts/check_promotion_gate.py` refreshes hourly -- so `run_cadence`'s
# existence test was satisfied by a sibling's output. These pin all three.


def _run(monkeypatch, tmp_path, candidates=None):
    """Drive main() with BOTH paths redirected into tmp_path -- never the live data/ store."""
    import scripts.promotion_gate as pg

    out = tmp_path / "verdicts.json"
    cand = tmp_path / "gauntlet_survivors.json"
    if candidates is not None:
        cand.write_text(json.dumps(candidates), "utf-8")
    monkeypatch.setattr(pg, "OUT", out)
    monkeypatch.setattr(pg, "CANDIDATES", cand)
    monkeypatch.setattr(pg, "ROOT", tmp_path)
    monkeypatch.setattr(sys, "argv", ["promotion_gate.py"])
    rc = pg.main()
    return rc, (json.loads(out.read_text("utf-8")) if out.exists() else None)


def test_output_name_does_not_collide_with_the_hourly_ladder_writer():
    """THE ROOT CAUSE. Two scripts wrote one filename and a third read its existence as success."""
    from scripts.check_promotion_gate import _STATE
    from scripts.promotion_gate import OUT

    assert OUT.name != Path(_STATE).name, (
        "promotion_gate.py and check_promotion_gate.py must not share an output filename -- "
        "run_cadence credits this step by asserting the artifact exists, and a sibling writing "
        "that name hourly turns a no-op into a green cadence line")


def test_missing_producer_writes_an_honest_artifact_and_fails(monkeypatch, tmp_path):
    """An ABSENT survivor list must produce a verdict file saying so, and must NOT return 0."""
    rc, rep = _run(monkeypatch, tmp_path, candidates=None)
    assert rc == 1, "a gate that judged nothing may not report success"
    assert rep is not None, "the artifact must be written even when there is nothing to judge"
    assert rep["status"] == "NO-PRODUCER"
    assert rep["measured"] is False
    assert rep["n_candidates"] == 0


def test_present_but_empty_is_a_measured_zero_not_the_same_as_absent(monkeypatch, tmp_path):
    """ABSENT and EMPTY are different claims (L1.55) and the old code collapsed both to rc 0."""
    rc, rep = _run(monkeypatch, tmp_path, candidates={})
    assert rc == 1
    assert rep["status"] == "NO-CANDIDATES"
    assert rep["measured"] is True, "a producer DID run and found nothing -- that is measured"


def test_real_candidates_are_judged_and_the_denominator_is_declared(monkeypatch, tmp_path):
    """The only path that may return 0, and it publishes what it counted (L1.57)."""
    rc, rep = _run(monkeypatch, tmp_path, candidates={
        "good": dict.fromkeys(_ALL, True),
        "no_mechanism": {**dict.fromkeys(_ALL, True), "mechanism": False},
    })
    assert rc == 0
    assert rep["status"] == "JUDGED"
    assert rep["n_candidates"] == 2, "the denominator is what the RUN found, not a literal"
    assert rep["n_accepted"] == 1
    assert {d["candidate"] for d in rep["verdicts"]} == {"good", "no_mechanism"}
